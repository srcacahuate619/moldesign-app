"""Re-curación masiva de targets: regenera hotspots y valida grid centers.

PROBLEMA (v1.7.2): el `curated_targets.json` (y por tanto la DB) guardó el
campo `hotspots` como el string literal "null" para 386/387 targets. Como el
seed (`_auto_seed_curated_targets_if_empty`) copia el campo tal cual, la DB
quedó con hotspots="null" en ~380/382 targets preparados. Consecuencia:
    - `hotspots_hit` siempre vacío en las evaluaciones
    - El filtro geométrico de poses no tiene anclaje
    - La validación científica (LE, score breakdown) no puede contrastar
      contra residuos del sitio activo

Además, 11 targets tienen grid centers con |coord| > 200 Å (1DIY, 1FE2, 1IGZ,
2OYE, 4O1Z con ~250,105,-36 — sospechosamente repetidos), probablemente mal
calculados al generar el JSON.

SOLUCIÓN: para cada target con PDB local, corre `discover_pocket_from_pdb`
(que detecta el ligando holo y mina los 15 hotspots del sitio activo) y
recalcula el grid center sobre el ligando detectado. Actualiza la DB.

Uso:
    python scripts/recure_targets.py --dry-run     # solo reporta
    python scripts/recure_targets.py               # aplica cambios
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# UTF-8 para consolas Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

GRID_ABS_MAX = 200.0     # |coord| > 200 Å → grid sospechoso
GRID_DIFF_MAX = 10.0     # diferencia > 10 Å entre grid DB y detectado → corregir


def find_local_pdb(pdb_id: str) -> Path | None:
    pdb_id = pdb_id.upper()
    for base in (Path(r"D:\moldesign-build\data\target_library"),
                 Path(r"D:\moldesign-build\data\targets")):
        for p in base.rglob("*.pdb"):
            if p.stem.split("_")[0].upper() == pdb_id:
                return p
    return None


def recure_one(pdb_path: Path, pdb_id: str) -> dict:
    """Regenera hotspots + grid center para un PDB. Retorna dict de resultado."""
    from utils.structural import discover_pocket_from_pdb

    content = pdb_path.read_text(encoding="utf-8", errors="replace")
    res = discover_pocket_from_pdb(content)

    out = {
        "pdb_id": pdb_id,
        "success": bool(res.get("success")),
        "apo_molpocket": bool(res.get("apo_molpocket")),
        "n_hotspots": len(res.get("suggested_hotspots", []) or []),
        "hotspots": res.get("suggested_hotspots", []) or [],
        "grid_center": res.get("grid_center"),
        "grid_size": res.get("grid_size"),
        "ligand_name": res.get("ligand_name"),
        "warnings": (res.get("warnings") or [])[:3],
    }
    return out


async def recure_one_async(pdb_path: Path, pdb_id: str) -> dict:
    """Versión async de recure_one (para usar con asyncio.run en dry-run)."""
    return await asyncio.to_thread(recure_one, pdb_path, pdb_id)


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="Solo reporta qué se corregiría (no escribe DB).")
    ap.add_argument("--db", type=str, default=None,
                    help="Ruta a la DB (default: usa core.database).")
    args = ap.parse_args()

    # Cargar catálogo
    catalog_path = Path(r"D:\moldesign-build\curated_targets.json")
    rows = json.loads(catalog_path.read_text(encoding="utf-8"))
    print(f"Catálogo: {len(rows)} targets", flush=True)

    # Pasar 1: detectar qué necesita re-curación
    need_hotspots = []
    need_grid = []
    for row in rows:
        pdb_id = row.get("pdb_id", "").strip().upper()
        if not pdb_id:
            continue
        hs = row.get("hotspots")
        hs_bad = (hs is None or hs == "null" or hs == "" or
                  (isinstance(hs, str) and hs.strip() in ("", "null", "[]")))
        if hs_bad:
            need_hotspots.append(pdb_id)
        gx = float(row.get("grid_center_x", 0) or 0)
        gy = float(row.get("grid_center_y", 0) or 0)
        gz = float(row.get("grid_center_z", 0) or 0)
        if max(abs(gx), abs(gy), abs(gz)) > GRID_ABS_MAX:
            need_grid.append(pdb_id)

    print(f"  sin hotspots válidos: {len(need_hotspots)}")
    print(f"  con grid anómalo (>{GRID_ABS_MAX}): {len(need_grid)}")
    print(flush=True)

    # Combinar lista de targets a reprocesar
    to_fix = sorted(set(need_hotspots) | set(need_grid))
    print(f"A reprocesar: {len(to_fix)} targets", flush=True)

    if args.dry_run:
        import math as _math
        print("  [dry-run] detalle:")
        n_grid_corr = 0
        n_hs_only = 0
        for pid in to_fix:
            pdb_path = find_local_pdb(pid)
            if pdb_path is None:
                continue
            try:
                r = await recure_one_async(pdb_path, pid)
            except Exception:
                continue
            row = next((x for x in rows if x.get("pdb_id", "").strip().upper() == pid), None)
            if row is None or not r["success"]:
                continue
            db_g = (float(row.get("grid_center_x", 0) or 0),
                    float(row.get("grid_center_y", 0) or 0),
                    float(row.get("grid_center_z", 0) or 0))
            if r["grid_center"]:
                det = (float(r["grid_center"][0]), float(r["grid_center"][1]), float(r["grid_center"][2]))
                diff = _math.dist(db_g, det)
                grid_bad = max(abs(v) for v in db_g) > GRID_ABS_MAX
                if grid_bad or diff > GRID_DIFF_MAX:
                    n_grid_corr += 1
                    print(f"    {pid}: grid DB={tuple(round(v,1) for v in db_g)} → det={tuple(round(v,1) for v in det)} (diff={diff:.0f}Å{' ANÓMALO' if grid_bad else ''})")
                else:
                    n_hs_only += 1
            else:
                n_hs_only += 1
        print(f"  [dry-run] grids a corregir: {n_grid_corr}, solo hotspots: {n_hs_only}")
        print("  (no se escribió nada)")
        return 0

    # Pasar 2: reprocesar y actualizar
    from core.database import get_db_session
    from db.repository import Repository
    from core.models import TargetORM
    from sqlalchemy import select
    import math as _math

    updated_hs = 0
    updated_grid = 0
    errors = []

    async with get_db_session() as db:
        repo = Repository(db)
        for i, pdb_id in enumerate(to_fix, 1):
            # Skip idempotente: si el target ya tiene hotspots válidos y grid
            # dentro de rango, no lo reprocesamos (acelera re-ejecuciones).
            stmt0 = select(TargetORM).where(TargetORM.pdb_id == pdb_id)
            t0 = (await db.execute(stmt0)).scalar_one_or_none()
            if t0 is not None and t0.hotspots and str(t0.hotspots).strip() not in ("", "null", "[]"):
                gx0 = float(t0.grid_center_x or 0)
                gy0 = float(t0.grid_center_y or 0)
                gz0 = float(t0.grid_center_z or 0)
                if max(abs(gx0), abs(gy0), abs(gz0)) <= GRID_ABS_MAX:
                    print(f"  - {pdb_id}: ya corregido (skip)", flush=True)
                    continue

            pdb_path = find_local_pdb(pdb_id)
            if pdb_path is None:
                errors.append(f"{pdb_id}: sin PDB local")
                continue
            try:
                r = await asyncio.to_thread(recure_one, pdb_path, pdb_id)
            except Exception as exc:
                errors.append(f"{pdb_id}: error {exc}")
                continue

            if not r["success"]:
                errors.append(f"{pdb_id}: discover falló")
                continue

            stmt = select(TargetORM).where(TargetORM.pdb_id == pdb_id)
            target = (await db.execute(stmt)).scalar_one_or_none()
            if target is None:
                errors.append(f"{pdb_id}: no está en DB")
                continue

            changed = False
            # Hotspots: regenerar si estaban vacíos/null
            if r["hotspots"] and pdb_id in need_hotspots:
                # La columna es JSONB → asignar la LISTA (el serializer del
                # engine se encarga del JSON). NO json.dumps (doble-escape).
                target.hotspots = r["hotspots"]
                updated_hs += 1
                changed = True

            # Grid: corregir si era anómalo (>200) O difiere >10 Å del detectado
            if r["grid_center"]:
                cx, cy, cz = (float(v) for v in r["grid_center"])
                db_gx, db_gy, db_gz = (float(target.grid_center_x or 0),
                                       float(target.grid_center_y or 0),
                                       float(target.grid_center_z or 0))
                diff = _math.dist((cx, cy, cz), (db_gx, db_gy, db_gz))
                grid_bad = max(abs(db_gx), abs(db_gy), abs(db_gz)) > GRID_ABS_MAX
                if grid_bad or diff > GRID_DIFF_MAX:
                    target.grid_center_x, target.grid_center_y, target.grid_center_z = cx, cy, cz
                    if r.get("grid_size"):
                        target.grid_size_x = float(r["grid_size"][0])
                        target.grid_size_y = float(r["grid_size"][1])
                        target.grid_size_z = float(r["grid_size"][2])
                    updated_grid += 1
                    changed = True
                    grid_reason = "anómalo>200" if grid_bad else f"diff={diff:.0f}Å"
                else:
                    grid_reason = "ok"
            else:
                grid_reason = "n/a"

            if changed:
                # v1.7.2: flush del ORM (usa el serializer JSONB de la columna).
                # La asignación es de lista Python (no string) para evitar
                # doble-escape. commit por target para persistencia parcial.
                from core.database import commit_with_retry
                try:
                    await commit_with_retry(db)
                    print(f"  ✓ {pdb_id}: hotspots={r['n_hotspots']} grid[{grid_reason}]={r['grid_center']}", flush=True)
                except Exception as exc:
                    errors.append(f"{pdb_id}: commit falló {exc}")
                    await db.rollback()
            else:
                print(f"  - {pdb_id}: sin cambios (grid {grid_reason})", flush=True)

        await db.commit()

    print(flush=True)
    print(f"Hotspots actualizados: {updated_hs}")
    print(f"Grids actualizados: {updated_grid}")
    print(f"Errores: {len(errors)}")
    for e in errors[:20]:
        print(f"  ! {e}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
