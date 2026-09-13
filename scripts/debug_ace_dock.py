#!/usr/bin/env python3
"""Debug ACE docking - test dock_and_extract in isolation."""
import sys, os, traceback, time, json

# Set up path BEFORE importing benchmark
sys.path.insert(0, r"D:\moldesign-build\scripts")
sys.path.insert(0, r"D:\moldesign-build\backend")
sys.path.insert(0, r"D:\moldesign-build\rescoring")
os.chdir(r"D:\moldesign-build")

from pathlib import Path
import benchmark_ef_vina as bm

# Must set these AFTER import (they're defined at module level)
bm.PROJECT_ROOT = Path(r"D:\moldesign-build")
bm.DATA_DIR = bm.PROJECT_ROOT / "data"

print("=== Step 1: get receptor ===")
receptor = bm._get_target_path("1o86")
if receptor:
    for k, v in receptor.items():
        val = str(v)[:80]
        print(f"  {k}: {val}")
else:
    print("  FAILED - receptor is None")
    sys.exit(1)

print("\n=== Step 2: load dataset ===")
actives, decoys = bm.load_dataset("1o86")
print(f"  Actives: {len(actives)}, Decoys: {len(decoys)}")
if not actives:
    print("  FAILED - no actives")
    sys.exit(1)

mol = actives[0]
print(f"  Test molecule: {mol['smiles'][:60]}...")
print(f"  is_active: {mol.get('is_active')}")

print("\n=== Step 3: dock_and_extract ===")
t0 = time.time()
try:
    result = bm.dock_and_extract(mol, receptor)
    elapsed = time.time() - t0
    print(f"  Elapsed: {elapsed:.1f}s")
    if result:
        print(f"  Keys: {list(result.keys())}")
        print(f"  vina_score: {result.get('vina_score')}")
        print(f"  prob: {result.get('prob')}")
        print(f"  clgnn_prob: {result.get('clgnn_prob')}")
        print(f"  features count: {len(result.get('features', {}))}")
    else:
        print("  FAILED - result is None/empty")
        print("  (This happens when Vina fails to dock or feature extraction errors)")
except Exception as e:
    elapsed = time.time() - t0
    print(f"  Exception after {elapsed:.1f}s:")
    traceback.print_exc()

print("\n=== DONE ===")
