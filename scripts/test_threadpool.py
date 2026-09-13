#!/usr/bin/env python3
"""Test dock_and_extract via ThreadPoolExecutor (same as benchmark)."""
import sys, os, time, concurrent.futures, traceback
sys.path.insert(0, r"D:\moldesign-build\scripts")
sys.path.insert(0, r"D:\moldesign-build\backend")
sys.path.insert(0, r"D:\moldesign-build\rescoring")
os.chdir(r"D:\moldesign-build")

from pathlib import Path
import benchmark_ef_vina as bm
bm.PROJECT_ROOT = Path(r"D:\moldesign-build")
bm.DATA_DIR = bm.PROJECT_ROOT / "data"

receptor = bm._get_target_path("1o86")
actives, decoys = bm.load_dataset("1o86")
mol = actives[0]

print(f"Testing dock_and_extract via ThreadPoolExecutor...")
print(f"Molecule: {mol['smiles'][:60]}...")
print(f"Receptor: {receptor['vina_pdbqt']}")

t0 = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(bm.dock_and_extract, mol, receptor)
    try:
        result = future.result(timeout=300)
        elapsed = time.time() - t0
        print(f"DONE in {elapsed:.1f}s")
        if result:
            print(f"vina_score: {result.get('vina_score')}")
            print(f"prob: {result.get('prob')}")
            print(f"features: {len(result.get('features', {}))} keys")
        else:
            print("Result is None/empty")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"FAILED after {elapsed:.1f}s: {e}")
        traceback.print_exc()
