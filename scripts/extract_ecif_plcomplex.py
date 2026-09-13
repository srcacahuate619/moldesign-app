"""Extract ECIF/Shell features ONLY for PLComplexDataset complexes (708 PDBbind)."""
import sys, time, json
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
from feature_extractor import InteractionFeatureExtractor

PDBBIND_DIR = PROJECT_ROOT / "data" / "pdbbind"
INDEX_PATH = PDBBIND_DIR / "INDEX_refined_data.2020"
OUT_DIR = PROJECT_ROOT / "data" / "gnn_v31"

ECIF_SHELL_KEYS = []
for k in __import__('feature_extractor').ALL_3D_FEATURES:
    if k.startswith("shell_") or k.startswith("ecif_"):
        ECIF_SHELL_KEYS.append(k)
print(f"Features: {len(ECIF_SHELL_KEYS)}")

# Load PDB ids from PLComplexDataset
with open(OUT_DIR / "pids_in_dataset.txt") as f:
    PIDS = [l.strip() for l in f if l.strip()]
print(f"Target PDB ids: {len(PIDS)}")

# Load pKi labels
pki_map = {}
if INDEX_PATH.exists():
    with open(INDEX_PATH) as f:
        for line in f:
            if line.startswith("#") or not line.strip(): continue
            parts = line.strip().split()
            if len(parts) >= 6 and parts[4] == "//":
                try: pki_map[parts[0]] = float(parts[5])
                except: pass
print(f"pKi labels: {len(pki_map)}")

ext = InteractionFeatureExtractor()
out = OUT_DIR / "ecif_pdbbind_crystal.npz"
if out.exists():
    print(f"SKIP: {out} exists")
    sys.exit(0)

n_feat = len(ECIF_SHELL_KEYS)
X = np.zeros((len(PIDS), n_feat), dtype=np.float32)
pids_arr = [None] * len(PIDS)
pki_arr = np.zeros(len(PIDS), dtype=np.float32)
n_ok = n_fail = n_labeled = 0
t0 = time.time()

for i, pid in enumerate(PIDS):
    pdb = str(PDBBIND_DIR / pid / f"{pid}_protein.pdb")
    sdf = str(PDBBIND_DIR / pid / f"{pid}_ligand.sdf")
    try:
        feats = ext.extract_from_files(pdb, sdf)
    except Exception:
        feats = {}
    v = np.zeros(n_feat, dtype=np.float32)
    if feats:
        for j, k in enumerate(ECIF_SHELL_KEYS):
            try: v[j] = float(feats.get(k, 0.0))
            except: pass
    nx = int((v != 0).sum())
    if nx > 0:
        X[i] = v; n_ok += 1
    else:
        n_fail += 1
    pids_arr[i] = pid
    if pid in pki_map:
        pki_arr[i] = pki_map[pid]; n_labeled += 1
    if (i+1) % 50 == 0 or i == len(PIDS)-1:
        t = time.time()-t0; r = (i+1)/t; e = (len(PIDS)-i-1)/r if r>0 else 0
        print(f"  [{i+1}/{len(PIDS)}] ok={n_ok} fail={n_fail} lab={n_labeled} rate={r:.1f}/s eta={e:.0f}s")

y_bin = (pki_arr > 7.0).astype(np.int8)
np.savez_compressed(out, X=X, pid=np.array(pids_arr,dtype=object),
                    y_pki=pki_arr.astype(np.float32), y_binary=y_bin,
                    feature_keys=np.array(ECIF_SHELL_KEYS, dtype=object))

tt = time.time()-t0
print(f"\nDone in {tt:.0f}s ({tt/60:.1f}min)")
print(f"X: {X.shape}, ok={n_ok}, fail={n_fail}, labeled={n_labeled}")
print(f"pKi mean={pki_arr[pki_arr>0].mean():.2f}, strong={y_bin.sum()}, weak={(pki_arr>0).sum()-y_bin.sum()}")
print(f"Saved {out} ({out.stat().st_size/1024:.0f} KB)")
