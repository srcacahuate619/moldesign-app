"""Sonda posterior: contrasta el alcance original y el acotado, sin reescribir la entrega."""
import hashlib
import json
from pathlib import Path

from rdkit import Chem

HERE = Path(__file__).resolve().parent
PREV = HERE.parent / "investigacion-d04-2026-11-15"
GUARDA = Chem.MolFromSmarts("[CX3](=O)[OX1-]")
PATRONES = {
    "aminoester": "[NX4+;H3]-[CX4;H1,H2]-[CX3](=[OX1])-[OX2;H0]-[$([CH3]),$([CH2]-[CH3])]",
    "alquilmorfolina": "[NX4+;H1;R1]1(-[CX4;!R;H2,H3])[CH2;R1][CH2;R1][OX2;H0;R1][CH2;R1][CH2;R1]1",
}


def hits(smi, patterns):
    mol = Chem.MolFromSmiles(smi)
    assert mol is not None, smi
    if mol.HasSubstructMatch(GUARDA):
        return []
    return sorted(k for k, qs in patterns.items() if any(mol.HasSubstructMatch(q) for q in qs))


def main():
    original = json.loads((PREV / "resultados.json").read_bytes())["patrones_SMARTS"]
    broad = {k: [Chem.MolFromSmarts(s) for s in original[k]] for k in PATRONES}
    narrow = {k: [Chem.MolFromSmarts(s)] for k, s in PATRONES.items()}
    assert all(q is not None for qs in narrow.values() for q in qs)
    controls = json.loads((PREV / "controles.json").read_bytes())
    records = [{"nombre": r["nombre"], "origen": r["origen"],
                "original": hits(r["smiles_ensayado"], broad),
                "acotado": hits(r["smiles_ensayado"], narrow)} for r in controls]
    measures = json.loads((PREV / "medidas.json").read_bytes())
    admitted = []
    for name, smi, cation, branches, data in measures["compuestos"]:
        if any(measures["fuentes"][source]["nivel"] == "A" and branch in PATRONES
               for branch, source, value, locator in data):
            admitted.append({"nombre": name, "acotado": hits(cation, narrow)})
    assert len(admitted) == 17 and all(r["acotado"] for r in admitted)
    correct = [r for r in records if r["origen"] == "CORRECTAS_VERIFICADAS"]
    assert len(correct) == 17 and not any(r["acotado"] for r in correct)
    borders = {
        "ester_secundario": ("COC(=O)C[NH2+]C", []),
        "ester_terciario": ("COC(=O)C[NH+](C)C", []),
        "ester_neutro": ("COC(=O)CN", []),
        "ester_fenilico": ("[NH3+]CC(=O)Oc1ccccc1", []),
        "ester_zwitterion": ("COC(=O)[C@@H]([NH3+])CC(=O)[O-]", []),
        "morfolina_carbono_sustituido": ("C[NH+]1C(C)COCC1", []),
        "morfolina_N_isopropilo": ("CC(C)[NH+]1CCOCC1", []),
        "morfolina_N_metilo": ("C[NH+]1CCOCC1", ["alquilmorfolina"]),
        "MOPS_N_protonado": ("O=S(=O)([O-])CCC[NH+]1CCOCC1", ["alquilmorfolina"]),
        "MOPS_N_neutro_molecula_anionica": ("O=S(=O)([O-])CCCN1CCOCC1", []),
    }
    edges = []
    for name, (smi, expected) in borders.items():
        found = hits(smi, narrow)
        assert found == expected, (name, found, expected)
        edges.append({"nombre": name, "smiles": smi, "esperado": expected, "observado": found})
    result = {"naturaleza": "Revisión post hoc de alcance; no calibración de pKa ni nueva preparación",
              "patrones_acotados": PATRONES, "padres_A_conservados": admitted,
              "correctas_versionadas": {"n": len(correct), "marcadas": 0},
              "controles_originales": records, "fronteras_adicionales": edges,
              "entradas_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in (PREV / "medidas.json", PREV / "controles.json", PREV / "resultados.json")}}
    (HERE / "d04-alcance.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"padres_A_conservados": len(admitted), "correctas": len(correct),
                      "marcadas": 0, "controles_releidos": len(records), "fronteras": len(edges),
                      "coincidencias_retiradas": [r for r in records if r["original"] != r["acotado"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
