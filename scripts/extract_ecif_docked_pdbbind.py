"""
scripts/extract_ecif_docked_pdbbind.py
Extract ECIF/Shell features for PLComplexDataset complexes using DOCKED PDBQT poses.

For each PDBbind entry (708 complexes):
  - Read docked PDBQT from data/pdbbind/redocked_v2/{pid}_docked.pdbqt
  - Read protein PDB from data/pdbbind/{pid}/{pid}_protein.pdb
  - Extract ECIF via InteractionFeatureExtractor.extract_from_pose(pose_pdbqt_block, target_pdb)
  - Save as data/gnn_v31/ecif_pdbbind_docked.npz

Output is used to train GNNv31Classifier with ECIF fused with graph embedding,
matching the docked distribution (NOT crystal).

Usage:
  python scripts/extract_ecif_docked_pdbbind.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from feature_extractor import InteractionFeatureExtractor, ALL_3D_FEATURES

PDBBIND_DIR = PROJECT_ROOT / "data" / "pdbbind"
REDOCK_DIR = PDBBIND_DIR / "redocked_v2"
INDEX_PATH = PDBBIND_DIR / "INDEX_refined_data.2020"
OUT_DIR = PROJECT_ROOT / "data" / "gnn_v31"

# Filter to ECIF/Shell only (matches GNNv31Classifier input)
ECIF_SHELL_KEYS = [k for k in ALL_3D_FEATURES
                   if k.startswith("shell_") or k.startswith("ecif_")]
print(f"Features target: {len(ECIF_SHELL_KEYS)} (shell + ecif)")


# Load PDB ids from PLComplexDataset
PIDS_FILE = OUT_DIR / "pids_in_dataset.txt"
if not PIDS_FILE.exists():
    print("ERROR: pids_in_dataset.txt not found. Run extract_ecif_plcomplex.py first.")
    sys.exit(1)
with open(PIDS_FILE) as f:
    PIDS = [line.strip() for line in f if line.strip()]
print(f"Target PDB ids: {len(PIDS)}")

# Load pKi labels
pki_map = {}
if INDEX_PATH.exists():
    with open(INDEX_PATH) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) >= 6 and parts[4] == "//":
                try:
                    pki_map[parts[0]] = float(parts[5])
                except ValueError:
                    pass
print(f"pKi labels: {len(pki_map)}")

# Extract ECIF for each complex using DOCKED PDBQT
ext = InteractionFeatureExtractor()

OUT_PATH = OUT_DIR / "ecif_pdbbind_docked.npz"
if OUT_PATH.exists():
    print(f"WARN: {OUT_PATH} already exists, will OVERWRITE")

n_feat = len(ECIF_SHELL_KEYS)
X = np.zeros((len(PIDS), n_feat), dtype=np.float32)
pids_arr = np.array([None] * len(PIDS), dtype=object)
pki_arr = np.zeros(len(PIDS), dtype=np.float32)
n_ok = n_fail = n_labeled = 0
missing_pdbqt = 0
missing_pdb = 0
t0 = time.time()

for i, pid in enumerate(PIDS):
    pdbqt_path = REDOCK_DIR / f"{pid}_docked.pdbqt"
    pdb_path = PDBBIND_DIR / pid / f"{pid}_protein.pdb"

    if not pdbqt_path.exists():
        missing_pdbqt += 1
    if not pdb_path.exists():
        missing_pdb += 1

    feats: dict = {}
    if pdbqt_path.exists() and pdb_path.exists():
        try:
            pose_block = pdbqt_path.read_text()
            feats = ext.extract_from_pose(pose_block, str(pdb_path), skip_prolif=False)
        except Exception as e:
            print(f"  [WARN] {pid}: {type(e).__name__}: {str(e)[:80]}")
            feats = {}

    v = np.zeros(n_feat, dtype=np.float32)
    if feats:
        for j, k in enumerate(ECIF_SHELL_KEYS):
            try:
                v[j] = float(feats.get(k, 0.0))
            except (TypeError, ValueError):
                pass

    n_nonzero = int((v != 0).sum())
    if n_nonzero > 0:
        X[i] = v
        n_ok += 1
    else:
        n_fail += 1

    pids_arr[i] = pid
    if pid in pki_map:
        pki_arr[i] = pki_map[pid]
        n_labeled += 1

    if (i + 1) % 50 == 0 or i == len(PIDS) - 1:
        t = time.time() - t0
        rate = (i + 1) / t if t > 0 else 0
        eta = (len(PIDS) - i - 1) / rate if rate > 0 else 0
        print(f"  [{i + 1}/{len(PIDS)}] ok={n_ok} fail={n_fail} lab={n_labeled} "
              f"miss_pdbqt={missing_pdbqt} miss_pdb={missing_pdb} rate={rate:.1f}/s eta={eta:.0f}s")

y_bin = (pki_arr > 7.0).astype(np.int8)
np.savez_compressed(
    OUT_PATH,
    X=X,
    pid=pids_arr,
    y_pki=pki_arr.astype(np.float32),
    y_binary=y_bin,
    feature_keys=np.array(ECIF_SHELL_KEYS, dtype=object),
)

total = time.time() - t0
print(f"\n=== Done in {total:.0f}s ({total / 60:.1f} min) ===")
print(f"X shape: {X.shape}")
print(f"OK: {n_ok}  Fail(zero): {n_fail}  Missing pdbqt: {missing_pdbqt}  Missing pdb: {missing_pdb}")
print(f"pKi labeled: {n_labeled}")
strong = int(y_bin.sum())
weak = int((pki_arr > 0).sum()) - strong
print(f"Binders: {strong} strong (pKi>7), {weak} weak (pKi<=7)")
print(f"Saved: {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.0f} KB)")
