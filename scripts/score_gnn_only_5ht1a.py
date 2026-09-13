#!/usr/bin/env python3
# scripts/score_gnn_only_5ht1a.py
# Run re-score for ONLY 5ht1a (avoids iterating on other targets).
# Usage: python score_gnn_only_5ht1a.py

import sys, time, json, importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

# Load re_score_gnn.py as a module
RSG_PATH = str(PROJECT_ROOT / "scripts" / "re-score-gnn.py")
spec = importlib.util.spec_from_file_location("re_score_gnn", RSG_PATH)
rsg = importlib.util.module_from_spec(spec)
sys.modules["re_score_gnn"] = rsg
spec.loader.exec_module(rsg)

ORIG_TARGETS = dict(rsg.TARGETS)
rsg.TARGETS.clear()
rsg.TARGETS.update({"5ht1a": ORIG_TARGETS["5ht1a"]})

print(f"Filtered TARGETS to single target: {list(rsg.TARGETS.keys())}")

t0 = time.time()
rsg.main()
elapsed = time.time() - t0
print(f"\nElapsed: {elapsed/60:.1f} min")
