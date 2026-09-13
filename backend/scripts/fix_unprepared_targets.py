"""Arregla targets del Grupo A: prepara receptores con la cadena correcta.

Los targets no-preparados (is_prepared=0) heredaron chain="A" del seed, pero
sus PDBs usan otras cadenas (B, L/H, etc.). Este script:
  1. Detecta la cadena con más átomos ATOM del PDB local.
  2. Prepara el receptor (PDBQT) con esa cadena.
  3. Actualiza la DB: chain, is_prepared=1, prepared_file_path.

También sirve para re-preparar targets con cadena incorrecta.

Uso:
    python scripts/fix_unprepared_targets.py [--pdb-ids 7PAC,1SM3] [--all]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT.parent)
os.environ["APP_MODE"] = "DESKTOP"


def find_local_pdb(pdb_id: str) -> Path | None:
    pdb_id = pdb_id.upper()
    for base in (Path(r"D:\moldesign-build\data\target_library"),
                 Path(r"D:\moldesign-build\data\targets")):
        for p in base.rglob("*.pdb"):
            if p.stem.split("_")[0].upper() == pdb_id:
                return p
    return None


def dominant_chain(pdb_path: Path) -> str:
    """Cadena con más átomos ATOM (el receptor principal)."""
    counts = Counter()
    for line in pdb_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("ATOM"):
            counts[(line[21:22].strip() or "A")] += 1
    if not counts:
        return "A"
    return counts.most_common(1)[0][0]


async def fix_one(db, pdb_id: str, repo) -> tuple[bool, str]:
    from services.docking.preparer import prepare_target
    from core.models import TargetORM
    from sqlalchemy import select, update as _sa_update

    stmt = select(TargetORM).where(TargetORM.pdb_id == pdb_id)
    t = (await db.execute(stmt)).scalar_one_or_none()
    if t is None:
        return False, "no está en DB"
    p = find_local_pdb(pdb_id)
    if p is None:
        return False, "sin PDB local"

    chain = dominant_chain(p)
    center = (float(t.grid_center_x or 0), float(t.grid_center_y or 0),
              float(t.grid_center_z or 0))
    size = (float(t.grid_size_x or 20), float(t.grid_size_y or 20),
            float(t.grid_size_z or 20))
    if center == (0, 0, 0):
        return False, "grid center nulo (no calibrado)"
    whitelist = []
    try:
        import json as _json
        if t.cofactors_whitelist:
            wl = _json.loads(t.cofactors_whitelist) if isinstance(t.cofactors_whitelist, str) else t.cofactors_whitelist
            whitelist = wl if isinstance(wl, list) else []
    except Exception:
        whitelist = []

    try:
        path = await prepare_target(pdb_id=pdb_id, chain_id=chain, center=center,
                                    size=size, force_reprepare=True,
                                    cofactors_whitelist=whitelist)
    except Exception as exc:
        return False, f"prepare falló: {str(exc)[:120]}"

    # UPDATE directo vía Core (immune a StaleDataError del ORM en commits
    # parciales de una sesión compartida).
    from core.database import commit_with_retry
    await db.execute(
        _sa_update(TargetORM)
        .where(TargetORM.pdb_id == pdb_id)
        .values(chain=chain, is_prepared=True, prepared_file_path=path)
    )
    await commit_with_retry(db)
    return True, f"preparado chain={chain} → {path}"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdb-ids", type=str, default=None,
                    help="Lista separada por comas. Si no se da, usa los no-preparados.")
    ap.add_argument("--all", action="store_true", help="Procesar todos los targets no-preparados")
    args = ap.parse_args()

    from core.database import get_db_session
    from db.repository import Repository
    from core.models import TargetORM
    from sqlalchemy import select

    async with get_db_session() as db:
        if args.pdb_ids:
            ids = [x.strip().upper() for x in args.pdb_ids.split(",") if x.strip()]
        else:
            stmt = select(TargetORM).where(TargetORM.is_prepared == False)  # noqa: E712
            ids = [t.pdb_id for t in (await db.execute(stmt)).scalars().all()]
        print(f"A procesar: {len(ids)} targets: {ids}", flush=True)

        ok = []
        fail = []
        for pid in ids:
            success, msg = await fix_one(db, pid, Repository(db))
            if success:
                ok.append((pid, msg))
                print(f"  ✓ {pid}: {msg}", flush=True)
            else:
                fail.append((pid, msg))
                print(f"  ✗ {pid}: {msg}", flush=True)

    print(f"\nOK: {len(ok)} | FALLOS: {len(fail)}")
    for pid, msg in fail:
        print(f"  {pid}: {msg}")
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
