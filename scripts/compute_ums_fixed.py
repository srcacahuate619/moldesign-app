#!/usr/bin/env python3
"""Compute UMS AUC with fixed decoys for all curated targets."""
import sys
sys.path.insert(0, "scripts")
from universal_metal_score import compute_universal_metal_score
from sklearn.metrics import roc_auc_score
import json

TARGETS = [
    ("ace", "data/multitarget/ace/actives.txt", "data/multitarget/ace/decoys.smi"),
    ("pde5a", "data/multitarget/pde5a/actives.txt", "data/multitarget/pde5a/decoys.smi"),
    ("cyp3a4", "data/multitarget/cyp3a4/actives.txt", "data/multitarget/cyp3a4/decoys.smi"),
]

results = {}
for name, act_path, dec_path in TARGETS:
    with open(act_path) as f:
        actives = [l.split()[0] for l in f if l.strip()]
    with open(dec_path) as f:
        decoys = [l.strip() for l in f if l.strip()][:1000]

    y_true = [1]*len(actives) + [0]*len(decoys)
    y_score = [compute_universal_metal_score(smi, 0.5, "metaloenzyme")[0] for smi in (actives + decoys)]
    auc = roc_auc_score(y_true, y_score)

    # Warhead stats
    from universal_metal_score import detect_warheads
    wh_act = sum(1 for smi in actives if any(detect_warheads(smi).values()))
    wh_dec = sum(1 for smi in decoys if any(detect_warheads(smi).values()))

    results[name] = {"auc": round(auc, 4), "n_active": len(actives), "n_decoy": len(decoys),
                     "warhead_pct_active": round(100*wh_act/len(actives), 1),
                     "warhead_pct_decoy": round(100*wh_dec/len(decoys), 1)}
    print(f"{name:7s} | AUC={auc:.4f} | act={len(actives)} dec={len(decoys)} | "
          f"warhead_active={100*wh_act/len(actives):.0f}% warhead_decoy={100*wh_dec/len(decoys):.0f}%")

print(f"\n=== Summary ===")
for name, r in results.items():
    print(f"{name:7s}: AUC={r['auc']} (act={r['n_active']}, dec={r['n_decoy']}, "
          f"wh_act={r['warhead_pct_active']}%, wh_dec={r['warhead_pct_decoy']}%)")

json.dump(results, open("data/molchamb_loto/ums_auc_fixed_decoys.json", "w"), indent=2)
print("\nSaved to data/molchamb_loto/ums_auc_fixed_decoys.json")
