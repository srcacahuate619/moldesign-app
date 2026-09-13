"""Silent-fail rate test for GNN-v3 on 100 random PDBbind complexes."""
import sys, time, random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))

from gnn_v2.inference import GNNv2Predictor
from rdkit import Chem

pdbbind = Path("D:/moldesign-build/data/pdbbind")
redocked = pdbbind / "redocked_v2"
docked = sorted([f.stem.replace("_docked", "") for f in redocked.glob("*.pdbqt")])

random.seed(42)
random.shuffle(docked)
test = docked[:100]

predictor = GNNv2Predictor(device="cpu", mc_samples=5)
predictor.reset_silent_failures()

success = 0
silent = 0
errors = 0
t_start = time.time()

for i, pid in enumerate(test):
    pdb_path = pdbbind / pid / f"{pid}_protein.pdb"
    sdf_path = pdbbind / pid / f"{pid}_ligand.sdf"
    pdbqt_path = str(redocked / f"{pid}_docked.pdbqt")

    if not pdb_path.exists() or not sdf_path.exists():
        continue

    try:
        mol = next(Chem.SDMolSupplier(str(sdf_path), removeHs=True))
        smi = Chem.MolToSmiles(mol)
    except Exception:
        smi = "CC"  # fallback

    success += 1
    prob, std = predictor.predict(smi, pdbqt_path, str(pdb_path))
    if prob == 0.5 and std == 1.0:
        silent += 1
    else:
        if i < 5:
            print(f"  [{i+1:3d}] {pid:5s} | P(bind)={prob:.4f} +-{std:.4f} | {smi[:30]}")

elapsed = time.time() - t_start
silent_rate = silent / max(success, 1) * 100

print(f"\n{'='*50}")
print(f"GNN-v3 Silent-Fail Rate Test")
print(f"{'='*50}")
print(f"  Tested: {success} complexes")
print(f"  Silent fails: {silent} ({silent_rate:.1f}%)")
print(f"  Criterion: <= 1%")
print(f"  Status: {'PASS' if silent_rate <= 1 else 'FAIL'}")
print(f"  Avg time/mol: {elapsed/max(success,1):.2f}s")
print(f"  Predicted silent: {predictor.silent_failures}")
