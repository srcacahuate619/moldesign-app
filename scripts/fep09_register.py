"""Completa el registro ANTES de medir; no se ejecuta sobre resultados."""
import hashlib
import json
from pathlib import Path
from fep09_inputs import write_json

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "scripts/artifacts_science/FEP-09-SENSIBILIDAD"
manifest = json.loads((ART / "manifest.json").read_text(encoding="utf-8"))
if (ART / "per_complex.jsonl").stat().st_size or manifest.get("sealed") or any(p.stat().st_size for p in (ART / "_work").glob("*/per_complex.jsonl")):
    raise SystemExit("No registrar después de resultados o sello")
inventory = json.loads((ART / "inventory.json").read_text(encoding="utf-8"))
conditions = {"product_under_test": {"commit": "f183e0af", "receptor_mode": "respetar", "python": "3.11.9", "vina": "1.2.7",
                                       "exhaustiveness": 8, "num_poses": 9, "seed": 42, "ph": 7.4},
                 "preregistration": {"path": "docs/auditorias/FEP-09-prerregistro.md",
                                     "sha256": hashlib.sha256((ROOT / "docs/auditorias/FEP-09-prerregistro.md").read_bytes()).hexdigest(),
                                     "inventory_sha256": hashlib.sha256((ART / "inventory.json").read_bytes()).hexdigest()},
                 "benchmark": {"repo": "https://github.com/openforcefield/protein-ligand-benchmark", "commit": inventory["plb_commit"],
                               "license_data": "CC BY 4.0", "license_code": "MIT", "attribution": "Hahn et al., LiveCoMS 2022, DOI 10.33011/livecoms.4.1.1497"}}
write_json(ART / "registered_conditions.json", conditions)
write_json(ART / "manifest.json", manifest)
table_path = ROOT / "scripts/sellos_no_distribuidos.json"
table = json.loads(table_path.read_text(encoding="utf-8"))
entry = {"prefijo": "E:/MolDesign-science/openff-plb/", "experimentos": ["FEP-09-SENSIBILIDAD"], "clase": "NO_VERSIONADO",
         "motivo": "Datos OpenFF PLB CC BY 4.0: se guardan hashes y resultados; las estructuras no se copian al repositorio.",
         "como_obtenerlo": "Clonar https://github.com/openforcefield/protein-ligand-benchmark con git-lfs y fijar fd88824f9114244f95a14b485e6d6c96c1de716d. Atribuir a Hahn et al., LiveCoMS 2022 (10.33011/livecoms.4.1.1497)."}
if not any(e.get("prefijo") == entry["prefijo"] and "FEP-09-SENSIBILIDAD" in e.get("experimentos", []) for e in table["entradas"]):
    table["entradas"].append(entry)
    write_json(table_path, table)
print("Prerregistro completado sin medidas")
