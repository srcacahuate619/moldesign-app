import json, sys
sys.path.insert(0, "D:/moldesign-build/rescoring")
from gnn_v2.inference import GNNv2Predictor
import tempfile, os, time

ckpt = json.load(open("D:/moldesign-build/data/gnn_fixed/benchmark_checkpoint_5ht1a.json"))
target_pdb = "D:/moldesign-build/data/pdbs/7E2Y.pdb"
predictor = GNNv2Predictor(device="cpu", mc_samples=10)

# Test first 5 molecules manually
for i in range(5):
    r = ckpt["results"][i]
    smi = r["smiles"]
    pq = r["pose_pdbqt"]
    gn = r.get("gnn_prob", "N/A")
    print(f"[{i}] SMILES={smi[:50]}")
    print(f"    pose_pdbqt len={len(pq)}")
    print(f"    old gnn_prob={gn}")

    tmp = tempfile.mktemp(suffix=".pdbqt")
    with open(tmp, "w") as f:
        f.write(pq)

    t0 = time.time()
    prob, std = predictor.predict(smi, tmp, target_pdb)
    elapsed = time.time() - t0
    print(f"    new prob={prob:.4f} std={std:.4f} | {elapsed:.2f}s | silent_fails={predictor.silent_failures}")
    try:
        os.unlink(tmp)
    except:
        pass
    print()
