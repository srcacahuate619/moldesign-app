"""FEP-09-R1: el inventario de FEP-09 sobre el producto con P01 arreglado, y estereoquímica con n≥8.

No importa el producto. Reutiliza sin cambios `fep09_inputs.describe` (el arnés sellado en
FEP-09-SENSIBILIDAD) y añade una sola cosa: hasta tres ligandos con algún estereocentro asignado
por diana, en el orden del SDF, cada uno con su propia línea base. El receptor, la cadena y la caja
son los de la diana en FEP-09; la variante borra la asignación del primer estereocentro, como allí.

    python scripts/fep09r1_inputs.py --plb E:/MolDesign-science/openff-plb --output <inventory.json>
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from fep09_inputs import describe, write_json

#: Ligandos con estereocentro asignado que se toman por diana, en el orden del SDF.
ESTEREO_POR_DIANA = 3


def extender_estereo(plan: dict) -> list[dict]:
    """Casos nuevos: línea base y variante sin asignar para cada ligando elegido que no esté ya."""
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    nuevos = []
    for sistema in plan["systems"]:
        elegidos = []
        for i, mol in enumerate(Chem.SDMolSupplier(sistema["sdf_path"], removeHs=False)):
            if mol is None:
                continue
            pesado = Chem.RemoveHs(mol)
            asignados = [(a, t) for a, t in Chem.FindMolChiralCenters(pesado, includeUnassigned=True) if t != "?"]
            if asignados:
                elegidos.append((i, mol, pesado, asignados))
            if len(elegidos) == ESTEREO_POR_DIANA:
                break
        for i, mol, pesado, asignados in elegidos:
            # El registro de FEP-09 ya tiene su caso contra `<diana>__baseline__0`.
            if i == sistema["record"]:
                continue
            nombre = mol.GetProp("_Name") if mol.HasProp("_Name") else f"record{i}"
            base = f"{sistema['target']}__baseline_estereo__{i}"
            nuevos.append({"case_id": base, "target": sistema["target"], "ligand": nombre, "arm": "B",
                           "category": "baseline_estereo", "repeat": i, "defect": {}, "record": i,
                           "smiles": Chem.MolToSmiles(pesado), "baseline_id": base})
            atomo = asignados[0][0]
            variante = Chem.Mol(pesado)
            variante.GetAtomWithIdx(atomo).SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
            nuevos.append({"case_id": f"{sistema['target']}__estereo_sin_asignar__{i}", "target": sistema["target"],
                           "ligand": nombre, "arm": "A", "category": "estereo_sin_asignar", "repeat": i, "record": i,
                           "defect": {"operation": "replace_smiles", "atom_index": atomo, "record": i},
                           "smiles": Chem.MolToSmiles(variante), "baseline_id": base})
    return nuevos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plb", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    plan = describe(args.plb.resolve())
    extension = extender_estereo(plan)
    plan["cases"].extend(extension)
    plan["applicable"] = dict(Counter(c["category"] for c in plan["cases"]))
    plan["extension_estereo"] = {"ligandos_por_diana": ESTEREO_POR_DIANA, "casos": [c["case_id"] for c in extension]}
    plan.pop("product_commit", None)  # el commit medido lo fija el prerregistro de R1, no el arnés de FEP-09
    write_json(args.output, plan)
    print(json.dumps({"targets": len(plan["systems"]), "cases": len(plan["cases"]), "applicable": plan["applicable"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
