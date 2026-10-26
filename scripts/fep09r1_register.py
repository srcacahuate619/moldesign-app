"""FEP-09-R1: registra las condiciones ANTES de medir; no se ejecuta sobre resultados.

    python scripts/fep09r1_register.py --product <commit del producto medido>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from fep09_inputs import write_json

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "scripts/artifacts_science/FEP-09-R1"
PRERREGISTRO = "docs/auditorias/FEP-09-R1-prerregistro.md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    args = ap.parse_args()
    manifest = json.loads((ART / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("sealed") or any(p.stat().st_size for p in (ART / "_work").glob("*/per_complex.jsonl")):
        raise SystemExit("No registrar después de resultados o sello")
    inventario = json.loads((ART / "inventory.json").read_text(encoding="utf-8"))
    write_json(ART / "registered_conditions.json", {
        "product_under_test": {"commit": args.product, "receptor_mode": "respetar", "python": "3.11.9", "vina": "1.2.7",
                               "exhaustiveness": 8, "num_poses": 9, "seed": 42, "ph": 7.4,
                               "tautomer_mode": "sin forzar; efectivo «entrada» (por defecto desde 039d9858)"},
        "preregistration": {"path": PRERREGISTRO,
                            "sha256": hashlib.sha256((ROOT / PRERREGISTRO).read_bytes()).hexdigest(),
                            "inventory_sha256": hashlib.sha256((ART / "inventory.json").read_bytes()).hexdigest(),
                            "fep09_inventory_sha256": hashlib.sha256(
                                (ROOT / "scripts/artifacts_science/FEP-09-SENSIBILIDAD/inventory.json").read_bytes()).hexdigest()},
        "benchmark": {"repo": "https://github.com/openforcefield/protein-ligand-benchmark", "commit": inventario["plb_commit"],
                      "license_data": "CC BY 4.0", "license_code": "MIT",
                      "attribution": "Hahn et al., LiveCoMS 2022, DOI 10.33011/livecoms.4.1.1497"},
    })
    print("Condiciones registradas sin medidas")


if __name__ == "__main__":
    main()
