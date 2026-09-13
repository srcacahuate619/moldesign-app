"""
phase2_lofo.py - Leave-One-Family-Out grid search for canonical weights.

1. For each family: hold out targets of that family
2. Optimize (w_vina, w_xgb, w_clgnn) on remaining targets
3. Apply to held-out targets
4. Pick the weight set with best LOFO mean AUC

Input: raw_scores.pkl from Phase 0
Output: canonical weights + LOFO report
"""
import json, pickle, sys
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score

ROOT = Path("D:/moldesign-build")
OUT = ROOT / "data" / "gnn_fixed" / "phase0"
RAW = OUT / "raw_scores.pkl"

with open(RAW, "rb") as f:
    raw = pickle.load(f)

# Target -> family mapping
FAMILY_MAP = {
    "5ht1a": "gpcr",
    "hiv_protease": "protease",
    "cdk2": "kinase",
    "er_alpha": "nuclear_receptor",
    "factor_xa": "protease",
    "thrombin": "protease",
    "ca2": "enzyme",
}

ALL_FAMILIES = sorted(set(FAMILY_MAP.values()))
print(f"Familes: {ALL_FAMILIES}")

# Prepare per-target arrays
targets = {}
for name, family in FAMILY_MAP.items():
    d = raw[name]
    targets[name] = {
        "family": family,
        "labels": np.array(d["labels"]),
        "vina_n": np.array(d["vina_n"]),
        "xgb": np.array(d["xgb"]),
        "clgnn": np.array(d["clgnn"]),
    }

def stack_score(vina_n, xgb, clgnn, w_v, w_x, w_c):
    return vina_n * w_v + xgb * w_x + clgnn * w_c

# Grid
grid = np.arange(0, 1.01, 0.05)

# LOFO
results = []
for held_out_family in ALL_FAMILIES:
    train_targets = {n: t for n, t in targets.items() if t["family"] != held_out_family}
    test_targets = {n: t for n, t in targets.items() if t["family"] == held_out_family}
    
    train_names = list(train_targets.keys())
    test_names = list(test_targets.keys())
    
    best_mean = 0.0
    best_w = None
    best_held_aucs = None
    
    for w_v in grid:
        for w_x in grid:
            w_c = 1.0 - w_v - w_x
            if w_c < -0.001 or w_c > 1.001:
                continue
            w_c = max(0.0, w_c)
            
            # AUC on training targets
            train_aucs = []
            for n in train_names:
                t = train_targets[n]
                scores = stack_score(t["vina_n"], t["xgb"], t["clgnn"], w_v, w_x, w_c)
                train_aucs.append(roc_auc_score(t["labels"], scores))
            mean_auc = float(np.mean(train_aucs))
            
            if mean_auc > best_mean:
                best_mean = mean_auc
                best_w = (float(w_v), float(w_x), float(w_c))
                # AUC on held-out targets
                held_aucs = {}
                for n in test_names:
                    t = test_targets[n]
                    scores = stack_score(t["vina_n"], t["xgb"], t["clgnn"], w_v, w_x, w_c)
                    held_aucs[n] = float(roc_auc_score(t["labels"], scores))
                best_held_aucs = held_aucs
    
    results.append({
        "held_out_family": held_out_family,
        "best_w": best_w,
        "best_mean_train_auc": best_mean,
        "n_train": len(train_names),
        "n_test": len(test_names),
        "held_out_auc": best_held_aucs,
        "mean_held_auc": float(np.mean(list(best_held_aucs.values()))) if best_held_aucs else 0.0,
    })
    print(f"  Held-out: {held_out_family:20s} | best_w=({best_w[0]:.2f},{best_w[1]:.2f},{best_w[2]:.2f}) | "
          f"train_mean={best_mean:.4f} | held_auc={results[-1]['mean_held_auc']:.4f} "
          f"| held={test_names}")

# Now find CANONICAL weights: try EVERY weight combination on every held-out fold
print(f"\n  {'='*70}")
print(f"  CANONICAL WEIGHTS")
print(f"  {'='*70}")

# Build held-out sets per family
held_out_data = {}
for fam in ALL_FAMILIES:
    held_out_data[fam] = {n: t for n, t in targets.items() if t["family"] == fam}

candidates = []
for w_v in grid:
    for w_x in grid:
        w_c = 1.0 - w_v - w_x
        if w_c < -0.001 or w_c > 1.001:
            continue
        w_c = max(0.0, w_c)
        
        # For each fold, evaluate THIS weight set on the held-out family
        lofo_held_aucs = []
        for held_fam, test_set in held_out_data.items():
            for n, t in test_set.items():
                scores = stack_score(t["vina_n"], t["xgb"], t["clgnn"], w_v, w_x, w_c)
                lofo_held_aucs.append(roc_auc_score(t["labels"], scores))
        mean_held = float(np.mean(lofo_held_aucs)) if lofo_held_aucs else 0.0
        
        # In-sample mean across ALL targets
        all_aucs = []
        for n, t in targets.items():
            scores = stack_score(t["vina_n"], t["xgb"], t["clgnn"], w_v, w_x, w_c)
            all_aucs.append(roc_auc_score(t["labels"], scores))
        mean_all = float(np.mean(all_aucs))
        
        candidates.append({
            "w_vina": float(w_v),
            "w_xgb": float(w_x),
            "w_clgnn": float(w_c),
            "lofo_mean_held_auc": mean_held,
            "in_sample_mean_auc": mean_all,
        })

candidates.sort(key=lambda c: -c["lofo_mean_held_auc"])
canonical = candidates[0]

print(f"\n  Best canonical:  vina={canonical['w_vina']:.2f} xgb={canonical['w_xgb']:.2f} clgnn={canonical['w_clgnn']:.2f}")
print(f"  LOFO mean AUC:   {canonical['lofo_mean_held_auc']:.4f}")
print(f"  In-sample AUC:   {canonical['in_sample_mean_auc']:.4f}")
print(f"  vs baseline (V+X): {canonical['in_sample_mean_auc'] - roc_auc_score(targets['5ht1a']['labels'], 0.7*targets['5ht1a']['xgb']+0.3*targets['5ht1a']['vina_n']):.4f}")

# Top 5
print(f"\n  Top 5 candidates:")
for c in candidates[:5]:
    print(f"    v={c['w_vina']:.2f} x={c['w_xgb']:.2f} c={c['w_clgnn']:.2f} | "
          f"lofo={c['lofo_mean_held_auc']:.4f} in={c['in_sample_mean_auc']:.4f}")

# Per-target with canonical
print(f"\n  {'='*70}")
print(f"  PER-TARGET WITH CANONICAL WEIGHTS")
print(f"  {'='*70}")
print(f"  {'target':<14}{'family':<18}{'baseline':>10}{'canonical':>12}{'sigma_adap':>12}")
for n, t in targets.items():
    base_score = 0.7 * t["xgb"] + 0.3 * t["vina_n"]
    auc_base = roc_auc_score(t["labels"], base_score)
    canon_score = stack_score(t["vina_n"], t["xgb"], t["clgnn"], canonical["w_vina"], canonical["w_xgb"], canonical["w_clgnn"])
    auc_canon = roc_auc_score(t["labels"], canon_score)
    print(f"  {n:<14}{t['family']:<18}{auc_base:>10.4f}{auc_canon:>12.4f}")

# Save
out = {
    "method": "LOFO (leave-one-family-out grid search)",
    "grid_step": 0.05,
    "canonical_weights": canonical,
    "top_10_candidates": candidates[:10],
    "lofo_per_family": results,
    "per_target_canonical_auc": {
        n: {"family": t["family"], "auc_canon": float(roc_auc_score(t["labels"], stack_score(t["vina_n"], t["xgb"], t["clgnn"], canonical["w_vina"], canonical["w_xgb"], canonical["w_clgnn"])))}
        for n, t in targets.items()
    },
}
with open(OUT / "lofo_canonical_weights.json", "w") as f:
    json.dump(out, f, indent=2)
print(f"\n  Saved: {OUT / 'lofo_canonical_weights.json'}")
