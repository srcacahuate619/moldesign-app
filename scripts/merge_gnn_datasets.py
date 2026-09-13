"""
merge_gnn_datasets.py - Mergea el dataset GNN original (708) con el nuevo (2687).
"""
import sys, time
from pathlib import Path

PROJECT_ROOT = Path("D:/moldesign-build")
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))

import torch
from gnn_v2.data import PLComplexDataset

NEW_DATA_PATH = PROJECT_ROOT / "data" / "gnn_v31" / "curated_new" / "gnn_general_complexes.pt"
OUT_PATH = PROJECT_ROOT / "data" / "gnn_v2_dataset" / "processed" / "gnn_v2_complexes_merged.pt"

# Load original
print("Loading original dataset (708)...")
ds = PLComplexDataset()
original_len = len(ds)
print(f"  Original: {original_len} complexes")

# Load new
print(f"\nLoading new dataset ({NEW_DATA_PATH})...")
new_data, _ = torch.load(NEW_DATA_PATH, weights_only=False)
new_len = len(new_data)
print(f"  New: {new_len} complexes")

# Merge
all_data = tuple(ds._samples) + tuple(new_data)
print(f"\nMerged: {len(all_data)} complexes")
torch.save((all_data, {}), OUT_PATH)
print(f"Saved: {OUT_PATH} ({OUT_PATH.stat().st_size/1024/1024:.1f} MB)")
print(f"\nDone in {time.time():.0f}s")
