#!/usr/bin/env python3
"""Debug ACE benchmark initialization."""
import sys, os
sys.path.insert(0, r"D:\moldesign-build\scripts")
sys.path.insert(0, r"D:\moldesign-build\backend")
sys.path.insert(0, r"D:\moldesign-build\rescoring")

from pathlib import Path
import benchmark_ef_vina as bm
bm.PROJECT_ROOT = Path(r"D:\moldesign-build")
bm.DATA_DIR = bm.PROJECT_ROOT / "data"

# Test 1: load_dataset
print("=== Test 1: load_dataset ===")
actives, decoys = bm.load_dataset("1o86")
print(f"Actives: {len(actives)}, Decoys: {len(decoys)}")
if actives:
    print(f"First active: {actives[0]['smiles'][:60]} pki={actives[0].get('pki')}")

# Test 2: target config
print("\n=== Test 2: TARGET_CONFIGS ===")
config = bm.TARGET_CONFIGS.get("1o86")
if config:
    print(f"name: {config['name']}")
    print(f"family: {config['family']}")
    print(f"center: {config['center']}")
    print(f"data_dir: {config['data_dir'](bm.DATA_DIR)} — exists: {config['data_dir'](bm.DATA_DIR).exists()}")
    print(f"pdb_local: {config['pdb_local'](bm.DATA_DIR)} — exists: {config['pdb_local'](bm.DATA_DIR).exists()}")
    print(f"pdbqt_local: {config['pdbqt_local'](bm.DATA_DIR)} — exists: {config['pdbqt_local'](bm.DATA_DIR).exists()}")
else:
    print("CONFIG NOT FOUND!")

# Test 3: _get_target_path
print("\n=== Test 3: _get_target_path ===")
try:
    receptor = bm._get_target_path("1o86")
    if receptor:
        print(f"Protein PDB: {receptor.get('protein_pdb', 'N/A')}")
        print(f"Vina PDBQT: {receptor.get('vina_pdbqt', 'N/A')}")
        print(f"Center: {receptor.get('center', 'N/A')}")
        print(f"Target ID: {receptor.get('target_id', 'N/A')}")
    else:
        print("_get_target_path returned None!")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

print("\n=== DONE ===")
