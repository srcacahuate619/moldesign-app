"""Sello de la revisión activa del catálogo y del panel DOCK-016."""

import csv
import hashlib
import json
from pathlib import Path

from services.docking.selectivity import ANTI_TARGET_PANEL

ROOT = Path(__file__).resolve().parents[2]
#: El manifiesto VIGENTE es el de fecha más alta; los anteriores se conservan como
#: procedencia (cada uno declara qué versión reemplaza). Se ordena por la fecha
#: del nombre, no alfabéticamente: `aaa-2026-01` no puede adelantar a `zzz-2026-09`.
MANIFEST = max((ROOT / "docs/catalog_versions").glob("*-????-??-??.json"),
               key=lambda p: p.stem[-10:])


def test_catalogo_activo_coincide_con_el_manifiesto():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for filename, key in (
        ("curated_targets.json", "curated_targets_json_sha256"),
        ("curated_targets.csv", "curated_targets_csv_sha256"),
    ):
        assert hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == manifest["active"][key]


def test_herg_y_panel_comparten_la_cavidad_tetramerica():
    rows = json.loads((ROOT / "curated_targets.json").read_text(encoding="utf-8"))
    herg = next(row for row in rows if row["pdb_id"] == "5VA1")
    panel = next(row for row in ANTI_TARGET_PANEL if row["pdb_id"] == "5VA1")
    assert herg["site_chains"] == ["A", "B", "C", "D"]
    assert herg["site_chain_atoms"] == {c: 273 for c in "ABCD"}
    center = tuple(herg[f"grid_center_{axis}"] for axis in "xyz")
    size = tuple(herg[f"grid_size_{axis}"] for axis in "xyz")
    assert center == panel["center"] == (73.15, 73.15, 78.53)
    assert size == panel["size"] == (28.8, 28.8, 30.0)
    expected = {f"{c}:{res}{n}" for c in "ABCD" for res, n in (
        ("THR", 623), ("SER", 624), ("TYR", 652), ("PHE", 656))}
    assert {h["name"] for h in herg["hotspots"]} == expected


def test_panel_no_presenta_homologos_como_dianas_humanas():
    ids = {row["pdb_id"] for row in ANTI_TARGET_PANEL}
    assert ids == {"5VA1", "4NC3"}
    with (ROOT / "curated_targets.csv").open(encoding="utf-8", newline="") as fh:
        csv_rows = {row["pdb_id"]: row for row in csv.DictReader(fh)}
    assert "HER2" in csv_rows["3PP0"]["name"]
    assert "NavAb" in csv_rows["6MVW"]["name"]
    assert "PDE3B" in csv_rows["1SO2"]["name"]
