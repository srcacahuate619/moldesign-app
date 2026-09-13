"""Debug: trace exact failure point in GNN-v3 inference."""
import sys, os, tempfile, traceback
sys.path.insert(0, "D:/moldesign-build/rescoring")
from gnn_v2.inference import GNNv2Predictor
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
RDLogger.logger().setLevel(RDLogger.ERROR)

import json
ckpt = json.load(open("D:/moldesign-build/data/gnn_fixed/benchmark_checkpoint_5ht1a.json"))

# Test first molecule
r = ckpt["results"][0]
smi = r["smiles"]
pq = r["pose_pdbqt"]
target = "D:/moldesign-build/data/pdbs/7E2Y.pdb"

print(f"SMILES: {smi}")
print(f"PDBQT len: {len(pq)}")

# Step 1: SMILES to SDF
mol = Chem.MolFromSmiles(smi)
mol = Chem.AddHs(mol)
Chem.AllChem.Compute2DCoords(mol)
mol = Chem.RemoveHs(mol)
fd, sdf_path = tempfile.mkstemp(suffix=".sdf")
os.close(fd)
w = Chem.SDWriter(sdf_path)
w.write(mol)
w.close()
print(f"SDF created at: {sdf_path} ({os.path.getsize(sdf_path)} bytes)")

# Step 2: Write PDBQT
fd2, pdbqt_path = tempfile.mkstemp(suffix=".pdbqt")
os.close(fd2)
with open(pdbqt_path, "w") as f:
    f.write(pq)
print(f"PDBQT created at: {pdbqt_path} ({os.path.getsize(pdbqt_path)} bytes)")

# Step 3: Parse PDBQT manually  
from gnn_v2.data import _parse_docked_pdbqt
try:
    parsed = _parse_docked_pdbqt(pdbqt_path)
    print(f"Parsed PDBQT: {len(parsed['elements'])} atoms")
except Exception as e:
    print(f"PARSE ERROR: {e}")
    traceback.print_exc()

# Step 4: Build protein graph manually
from gnn_v2.data import _build_protein_graph
import numpy as np
lig_coords = np.array([[0.,0.,0.]])  # dummy
try:
    prot_graph = _build_protein_graph(target, lig_coords)
    if prot_graph is None:
        print("Protein graph: None (no pocket residues?)")
    else:
        print(f"Protein graph: {prot_graph.x.shape[0]} residues")
except Exception as e:
    print(f"PROTEIN GRAPH ERROR: {e}")
    traceback.print_exc()

# Step 5: Full predict
predictor = GNNv2Predictor(device="cpu", mc_samples=10)
try:
    prob, std = predictor.predict(smi, pdbqt_path, target)
    print(f"Predict: prob={prob:.4f}, std={std:.4f}, silent={predictor.silent_failures}")
except Exception as e:
    print(f"PREDICT ERROR: {e}")
    traceback.print_exc()

# Cleanup
for p in [sdf_path, pdbqt_path]:
    try: os.unlink(p)
    except: pass
