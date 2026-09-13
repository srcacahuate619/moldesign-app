"""Backfill de contexto fisiológico para TODOS los targets del catálogo.

El endpoint real de contexto fisiológico (services/blockchain/target_info.py:
PDB RCSB → UniProt → traducción a español) solo se ejecutaba lazy al generar
un PDF y únicamente cuando description estaba VACÍA. El resultado: 385 de 387
targets tienen la descripción GENÉRICA del seed ("Target pre-curado... Familia:
X") que NO es contexto fisiológico.

Este script recorre el catálogo completo y, para cada target cuya description
sea genérica o vacía, obtiene el contexto fisiológico real y actualiza la BD.
Si la llamada falla (sin red, PDB inexistente), PRESERVA la descripción actual
(genérica) para no degradar nada.

Uso:
    python scripts/backfill_target_descriptions.py            # todos los targets
    python scripts/backfill_target_descriptions.py --pdb-ids 7E2Y,1HSG   # solo algunos
    python scripts/backfill_target_descriptions.py --dry-run # no escribe
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
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

# Marcadores de descripción GENÉRICA del seed (no es contexto fisiológico real)
_GENERIC_PREFIXES = (
    "Target pre-curado para virtual screening offline",
    "Target pre-curado de la libreria offline",
    "Target pre-curado offline",
    "Target pre-curado (",
    "Target pre-curado para virtual screening",
)

# Fallbacks conocidos del fetch (no son contexto real tampoco)
_FALLBACK_PREFIXES = (
    "Descripción del receptor no disponible.",
    "Receptor Biológico PDB:",
)


def is_generic(desc: str | None) -> bool:
    if not desc:
        return True
    d = desc.strip()
    if not d:
        return True
    return any(d.startswith(p) for p in _GENERIC_PREFIXES + _FALLBACK_PREFIXES)


async def backfill_all(pdb_ids: list[str] | None, dry_run: bool, include_short: bool = False) -> int:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from core.database import get_session_factory
    from core.models import TargetORM
    from services.blockchain.target_info import fetch_and_translate_target_info

    updated = 0
    failed = 0
    skipped = 0

    async with get_session_factory()() as db:
        stmt = select(TargetORM).options(selectinload(TargetORM.molecules))
        if pdb_ids:
            stmt = stmt.where(TargetORM.pdb_id.in_([p.upper() for p in pdb_ids]))
        targets = (await db.execute(stmt)).scalars().all()

        if not pdb_ids:
            # Modo catálogo completo: solo targets con descripción genérica o vacía
            targets = [t for t in targets if is_generic(t.description)]
        elif include_short:
            # Re-procesar también descripciones cortas (<100 chars = probable
            # título sin función UniProt, ahora enriquece con entidad)
            targets = [t for t in targets if is_generic(t.description) or (t.description and len(t.description.strip()) < 100)]
        else:
            targets = list(targets)

        print(f"Targets a procesar: {len(targets)} (dry_run={dry_run})")

        for i, t in enumerate(targets, 1):
            pdb = (t.pdb_id or "").upper()
            print(f"[{i}/{len(targets)}] {pdb} ({t.name or '?'})... ", end="", flush=True)
            try:
                desc = await fetch_and_translate_target_info(pdb)
                if not desc or desc.startswith(_FALLBACK_PREFIXES):
                    print("FALLBACK (sin contexto nuevo) — sin cambio")
                    skipped += 1
                    continue
                if dry_run:
                    print(f"OK (dry-run) → {desc[:70]}...")
                else:
                    t.description = desc
                    await db.commit()
                    print(f"OK → {desc[:70]}...")
                updated += 1
            except Exception as e:
                failed += 1
                print(f"ERROR: {e}")
                continue

    print("\n=== RESUMEN ===")
    print(f"  actualizados: {updated}")
    print(f"  fallidos (preservan descripción): {failed}")
    print(f"  sin contexto nuevo: {skipped}")
    return updated


def main():
    parser = argparse.ArgumentParser(description="Backfill de contexto fisiológico de targets")
    parser.add_argument("--pdb-ids", type=str, default=None, help="PDB IDs separados por coma (opcional)")
    parser.add_argument("--dry-run", action="store_true", help="No escribir en la BD")
    parser.add_argument("--include-short", action="store_true", help="Re-procesar también descripciones cortas (<100 chars)")
    args = parser.parse_args()

    pdb_ids = [p.strip() for p in args.pdb_ids.split(",") if p.strip()] if args.pdb_ids else None
    asyncio.run(backfill_all(pdb_ids, args.dry_run, args.include_short))


if __name__ == "__main__":
    main()
