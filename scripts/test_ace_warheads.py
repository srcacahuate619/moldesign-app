#!/usr/bin/env python3
"""Quick test: compute Universal Metal Score on ACE actives and decoys."""
import sys
sys.path.insert(0, "scripts")
from universal_metal_score import compute_universal_metal_score, detect_warheads

actives = []
with open("data/multitarget/ace/actives.txt") as f:
    for line in f:
        parts = line.strip().split()
        if parts:
            actives.append(parts[0])

decoys = []
with open("data/multitarget/ace/decoys.smi") as f:
    for line in f:
        smi = line.strip()
        if smi:
            decoys.append(smi)

# Sample 10 actives
print("=== ACE actives UMS scores ===")
for smi in actives[:10]:
    score, feats = compute_universal_metal_score(smi, 0.5, "metaloenzyme")
    wh = [k for k, v in feats["warheads"].items() if v]
    print(f"  UMS={score:.4f} | warheads={wh} | donor={feats['donor_count']:2d} | smi={smi[:60]}")

print(f"\n=== ACE decoys UMS scores (first 10) ===")
for smi in decoys[:10]:
    score, feats = compute_universal_metal_score(smi, 0.5, "metaloenzyme")
    wh = [k for k, v in feats["warheads"].items() if v]
    print(f"  UMS={score:.4f} | warheads={wh} | donor={feats['donor_count']:2d} | smi={smi[:60]}")

# Full AUC estimate
from sklearn.metrics import roc_auc_score
import numpy as np

# Compute scores for all actives and sampled decoys
y_true = [1] * len(actives) + [0] * len(decoys)
y_score = []
for smi in actives + decoys:
    score, feats = compute_universal_metal_score(smi, 0.5, "metaloenzyme")
    y_score.append(score)

auc = roc_auc_score(y_true, y_score)
print(f"\n=== AUC estimate ===")
print(f"  Actives: {len(actives)} | Decoys: {len(decoys)}")
print(f"  Universal Metal Score AUC: {auc:.4f}")
