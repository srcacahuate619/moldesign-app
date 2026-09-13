"""Corrige hotspots con doble-escape JSON en la DB (v1.7.2 hotfix).

El re-curado anterior guardó `json.dumps(lista)` en una columna JSONB cuyo
serializer ya hace json.dumps → el valor quedó como string JSON *dentro* de
otro string JSON ("[{\\"name\\": ...}]"). Este script:
  1. Lee cada target con hotspots.
  2. Si el valor parsea a STRING que a su vez parsea a LISTA → reasigna la
     lista (el serializer JSONB se encarga de serializar una sola vez).
  3. Si es None/"null"/"[]" → lo deja (lo regenera el pipeline).

Uso:
    python scripts/fix_hotspots_double.py [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
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


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from core.database import get_db_session, commit_with_retry
    from core.models import TargetORM
    from sqlalchemy import select

    fixed = 0
    already_ok = 0
    errors = []

    async with get_db_session() as db:
        stmt = select(TargetORM).where(TargetORM.hotspots.isnot(None))
        targets = (await db.execute(stmt)).scalars().all()
        print(f"Targets con hotspots no-null: {len(targets)}", flush=True)

        for t in targets:
            val = t.hotspots
            # Si ya es lista → OK
            if isinstance(val, list):
                already_ok += 1
                continue
            if not isinstance(val, str):
                continue
            s = val.strip()
            if s in ("", "null", "[]"):
                already_ok += 1
                continue
            try:
                parsed = json.loads(s)
            except Exception:
                continue
            # Doble-escape: parsed es un STRING que contiene JSON de lista
            if isinstance(parsed, str):
                try:
                    inner = json.loads(parsed)
                except Exception:
                    continue
                if isinstance(inner, list) and len(inner) > 0:
                    if args.dry_run:
                        print(f"  [dry] {t.pdb_id}: doble-escape → {len(inner)} hotspots", flush=True)
                        fixed += 1
                        continue
                    t.hotspots = inner  # JSONB serializer lo serializa una vez
                    try:
                        await commit_with_retry(db)
                        fixed += 1
                        print(f"  ✓ {t.pdb_id}: {len(inner)} hotspots (corregido)", flush=True)
                    except Exception as exc:
                        errors.append(f"{t.pdb_id}: {exc}")
                        await db.rollback()
                else:
                    already_ok += 1
            elif isinstance(parsed, list) and len(parsed) > 0:
                already_ok += 1

    print(flush=True)
    print(f"Corregidos: {fixed} | ya OK: {already_ok} | errores: {len(errors)}")
    for e in errors[:10]:
        print(f"  ! {e}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
