"""
run_ache_benchmark.py
Wrapper to run benchmark_ef_vina pipeline for AChE (1gpk) target.
Hydrolase family, completely new target family.

Launches Vina docking + feature extraction + XGB scoring.
"""
import json, os, sys, shutil, tempfile, traceback, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import subprocess, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Validate data exists
ache_dir = DATA_DIR / "multitarget" / "ache"
for f in ["actives.txt", "decoys.smi", "1gpk_vina.pdbqt"]:
    if not (ache_dir / f).exists():
        print(f"FATAL: {f} not found in {ache_dir}")
        sys.exit(1)

print("All data files present.")

# Launch benchmark_ef_vina directly (target 1gpk is already in TARGET_CONFIGS)
cmd = [
    sys.executable, str(PROJECT_ROOT / "scripts" / "benchmark_ef_vina.py"),
    "--target", "1gpk",
    "--workers", "4",
    "--exhaust", "8",
]
print("Running:", " ".join(cmd))
sys.exit(subprocess.call(cmd))
