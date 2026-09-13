"""
SC-8: Regenera curated_targets.json desde la DB real de producción.

PROBLEMA (2026-08-04): la DB real (moldesign_local.db) tiene 384/387 targets con
hotspots reales (minados por recure_targets.py), PERO el JSON fuente
(curated_targets.json) quedó con 385/387 con hotspots literal "null" — el seed
(_auto_seed_curated_targets_if_empty en backend/api/main.py) lee del JSON, así
que un usuario NUEVO que instale la app heredaría el bug de hotspots vacíos.

SOLUCIÓN: exportar los targets desde la DB real (fuente de verdad) hacia el JSON
fuente. Así el seed siembra hotspots reales.

Uso:
    python scripts/sync_curated_targets_from_db.py --dry-run   # solo reporta
    python scripts/sync_curated_targets_from_db.py             # escribe JSON
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_DB_PATH = Path.home() / "MolDesign" / "data" / "moldesign_local.db"
# El seed de producción (backend/api/main.py:623) lee de la RAÍZ del repo:
#   Path(__file__).resolve().parent.parent.parent / "curated_targets.json"
# main.py está en backend/api/ → parents[2] = raíz del repo.
# Este script está en backend/scripts/ → parents[2] también es la raíz.
_JSON_PATH = Path(__file__).resolve().parents[2] / "curated_targets.json"

# Columnas que el seed lee (backend/api/main.py:661-689)
_SEED_COLUMNS = [
    "pdb_id", "name", "chain", "description",
    "grid_center_x", "grid_center_y", "grid_center_z",
    "grid_size_x", "grid_size_y", "grid_size_z",
    "requires_cns", "structural_family", "organism", "resolution",
    "hotspots", "affinity_threshold", "specificity_floor", "is_hot",
    "spearman_rho", "calibration_date", "prepared_file_path", "is_prepared",
    "cofactors_whitelist", "is_private", "is_community",
    "is_anti_target", "anti_target_risk",
]


def _parse_json_field(v: str | None):
    """Convierte un campo JSONB→TEXT de SQLite a objeto (o None si inválido).

    PROBLEMA (2026-08-04, SC-8): la columna hotspots tiene TRES formatos:
      1. JSON normal:        `[{"name": "MET99", ...}]`
      2. DOBLE serializado:  `"[{\\"name\\": \\"R:PHE403\\", ...}]"` — el string
         JSON escapa comillas internas con backslash (json.dumps 2 veces). El
         json.loads directo devuelve un str, no la lista.
      3. Literal 'null':     `null`
    Este parser maneja los tres: doble json.loads si el nivel 1 es un string.
    """
    if v is None:
        return None
    s = v.strip() if isinstance(v, str) else v
    if not s or s in ("null", "[]"):
        return None
    try:
        first = json.loads(s)
        # Doble serialización: el nivel 1 es un string → parsear de nuevo
        if isinstance(first, str):
            second = json.loads(first)
            return second
        return first
    except (json.JSONDecodeError, TypeError):
        # No es JSON (string plano) → devolver el string crudo
        return v


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Solo reporta, no escribe.")
    ap.add_argument("--db", type=str, default=str(_DB_PATH), help="Ruta a la DB.")
    ap.add_argument("--out", type=str, default=str(_JSON_PATH), help="Ruta JSON destino.")
    args = ap.parse_args()

    if not Path(args.db).exists():
        print(f"ERROR: DB no encontrada: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(f"SELECT {', '.join(_SEED_COLUMNS)} FROM targets ORDER BY pdb_id")
    rows = cur.fetchall()
    conn.close()

    print(f"DB: {len(rows)} targets leídos de {Path(args.db).name}")

    exported = []
    n_hotspots_real = 0
    n_hotspots_null = 0
    n_rho = 0

    for row in rows:
        d = dict(row)

        # Hotspots: string JSON → objeto (para que el seed no guarde "null")
        hs = _parse_json_field(d.get("hotspots"))
        d["hotspots"] = hs if isinstance(hs, list) and len(hs) > 0 else None
        if d["hotspots"]:
            n_hotspots_real += 1
        else:
            n_hotspots_null += 1

        # cofactors_whitelist: JSON → lista
        cw = _parse_json_field(d.get("cofactors_whitelist"))
        d["cofactors_whitelist"] = cw if isinstance(cw, list) else []

        if d.get("spearman_rho") is not None:
            n_rho += 1

        exported.append(d)

    print(f"  hotspots reales: {n_hotspots_real} | hotspots null: {n_hotspots_null}")
    print(f"  spearman_rho (no None): {n_rho}")

    if args.dry_run:
        print("\nDRY-RUN: no se escribió el JSON.")
        return 0

    # Escribir JSON con indent para que sea revisable en git
    out_path = Path(args.out)
    out_path.write_text(
        json.dumps(exported, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nJSON actualizado: {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
