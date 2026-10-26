"""Verifica intervenciones contra originales, antes de pedir corridas a la API."""
import argparse
import json
import tempfile
from pathlib import Path
from fep09_inputs import atoms, materialize, read_target, sha

ap = argparse.ArgumentParser()
ap.add_argument("--plb", type=Path, default=Path("E:/MolDesign-science/openff-plb"))
args = ap.parse_args()
root = Path(__file__).resolve().parents[1]
plan = json.loads((root / "scripts/artifacts_science/FEP-09-SENSIBILIDAD/inventory.json").read_text(encoding="utf-8"))
checked = 0
with tempfile.TemporaryDirectory(prefix="fep09-inputcheck-", dir=root / "tmp") as temp:
    for system in plan["systems"]:
        original, _, _, _ = read_target(args.plb, system["target"])
        original_atoms = atoms(original)
        assert sha(original) == system["pdb_sha256"]
        for case in (c for c in plan["cases"] if c["target"] == system["target"]):
            output = Path(temp) / "input.pdb"
            materialize(args.plb, system, case, output)
            changed_atoms = atoms(output.read_bytes())
            op = case["defect"].get("operation")
            normalize = lambda a: (tuple(a["key"]), a["name"], a["element"], tuple(a["xyz"]))
            before = [normalize(a) for a in original_atoms]
            after = [normalize(a) for a in changed_atoms]
            if op in {None, "replace_smiles", "renumber_serials"}:
                assert before == after, case["case_id"]
            elif op in {"remove_residues", "remove_chain"}:
                keys = {tuple(k) for k in case["defect"].get("residues", [])}
                expected = [normalize(a) for a in original_atoms if tuple(a["key"]) not in keys
                            and not (op == "remove_chain" and a["key"][0] == case["defect"]["chain"])]
                assert expected == after and len(after) < len(before), case["case_id"]
            elif op in {"flip_histidine", "protonate_acid"}:
                key = tuple(case["defect"]["residue"])
                assert [a for a in before if a[0] != key] == [a for a in after if a[0][:3] != key[:3]], case["case_id"]
                assert len(after) == len(before)+(op == "protonate_acid"), case["case_id"]
                old_heavy = [(a[1:]) for a in before if a[0] == key and a[2] != "H"]
                new_heavy = [(a[1:]) for a in after if a[0][:3] == key[:3] and a[2] != "H"]
                assert old_heavy == new_heavy, case["case_id"]
            checked += 1
print(f"Intervenciones verificadas: {checked}; originales y geometría ajena conservados")
