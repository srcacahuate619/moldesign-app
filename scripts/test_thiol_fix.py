#!/usr/bin/env python3
"""Verify thiol pattern fix and compute ACE UMS AUC."""
import sys
sys.path.insert(0, "scripts")
from universal_metal_score import detect_warheads, compute_universal_metal_score
from sklearn.metrics import roc_auc_score

# Test captopril and thiol detection
test_smis = [
    ("captopril (PubChem)", "C[C@H](CS)C(=O)N1CCC[C@H]1C(=O)O"),
    ("captopril thioether", "CC(C)SCC(C)C(=O)N1CCCC1C(=O)O"),
    ("propyl mercaptan", "CCCS"),
    ("cysteine", "C[C@@H](C(=O)O)N"),
]
for name, smi in test_smis:
    wh = detect_warheads(smi)
    print(f"{name:25s}: thiol={wh['thiol']}, carboxylate={wh['carboxylate']}, any={any(wh.values())}  smi={smi[:50]}")

# ACE actives - count thiol now
with open("data/multitarget/ace/actives.txt") as f:
    actives = [l.split()[0] for l in f if l.strip()]
thiol_count = sum(1 for smi in actives if detect_warheads(smi).get("thiol"))
print(f"ACE actives with thiol: {thiol_count}/{len(actives)} ({100*thiol_count/len(actives):.1f}%)")

# Full warhead summary
from collections import Counter
wh_counts = Counter()
for smi in actives:
    wh = detect_warheads(smi)
    for k, v in wh.items():
        if v: wh_counts[k] += 1
print(f"ACE warheads: {dict(wh_counts)}")

# Recompute UMS AUC for ACE
with open("data/multitarget/ace/decoys.smi") as f:
    decoys = [l.strip() for l in f if l.strip()][:1000]
y_true = [1]*len(actives) + [0]*len(decoys)
y_score = [compute_universal_metal_score(smi, 0.5, "metaloenzyme")[0] for smi in (actives + decoys)]
auc = roc_auc_score(y_true, y_score)
print(f"\nACE UMS AUC post-fix: {auc:.4f}")
print(f"Actives: {len(actives)}, Decoys: {len(decoys)} (sample)")
print(f"Active mean score: {sum(y_score[:len(actives)])/len(actives):.4f}")
print(f"Decoy mean score: {sum(y_score[len(actives):])/len(decoys):.4f}")
