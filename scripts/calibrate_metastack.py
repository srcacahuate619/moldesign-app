"""
calibrate_metastack.py v2 - precompute optimal weights.
"""
import json, pickle, sys
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score

ROOT = Path("D:/moldesign-build")
sys.path.insert(0, str(ROOT / "rescoring" / "gnn_v2"))
from metastack import metastack_weights

OUT = ROOT / "data" / "gnn_fixed" / "phase0"
RAW = OUT / "raw_scores.pkl"

with open(RAW, "rb") as f:
    raw = pickle.load(f)

targets = {}
for name, d in raw.items():
    targets[name] = {
        "labels": np.array(d["labels"]),
        "vina_n": np.array(d["vina_n"]),
        "xgb": np.array(d["xgb"]),
        "clgnn": np.array(d["clgnn"]),
    }

# Precompute individual AUCs and optimal weights for each target
target_aucs = {}
target_opt = {}
target_opt_auc = {}
for name, t in targets.items():
    auc_v = float(roc_auc_score(t["labels"], t["vina_n"]))
    auc_x = float(roc_auc_score(t["labels"], t["xgb"]))
    auc_c = float(roc_auc_score(t["labels"], t["clgnn"]))
    target_aucs[name] = {"vina": auc_v, "xgb": auc_x, "clgnn": auc_c}
    
    best_auc = 0.0
    best_w = None
    for w_v in np.arange(0, 1.01, 0.05):
        for w_x in np.arange(0, 1.01 - w_v, 0.05):
            w_c = 1.0 - w_v - w_x
            if w_c < 0: continue
            scores = t["vina_n"] * w_v + t["xgb"] * w_x + t["clgnn"] * w_c
            auc = roc_auc_score(t["labels"], scores)
            if auc > best_auc:
                best_auc = auc
                best_w = (w_v, w_x, w_c)
    target_opt[name] = best_w
    target_opt_auc[name] = best_auc

# Quick calibration
T_candidates = list(range(0, 21, 1))
p_candidates = [1.0, 1.5, 2.0, 2.5, 3.0]

best_err = float("inf")
best_params = None
all_results = []

for T in T_candidates:
    for p in p_candidates:
        total_mse = 0.0
        total_auc_loss = 0.0
        for name, t in targets.items():
            a = target_aucs[name]
            w_v, w_x, w_c, info = metastack_weights(a["vina"], a["xgb"], a["clgnn"], T=T, p=p)
            opt_w = target_opt[name]
            mse = (w_v - opt_w[0])**2 + (w_x - opt_w[1])**2 + (w_c - opt_w[2])**2
            total_mse += mse
            
            pred_scores = t["vina_n"] * w_v + t["xgb"] * w_x + t["clgnn"] * w_c
            pred_auc = roc_auc_score(t["labels"], pred_scores)
            total_auc_loss += target_opt_auc[name] - pred_auc
        
        mean_mse = total_mse / len(targets)
        mean_loss = total_auc_loss / len(targets)
        
        if mean_mse < best_err:
            best_err = mean_mse
            best_params = (T, p)
            best_loss = mean_loss
        
        all_results.append({"T": T, "p": p, "mse": round(mean_mse, 6), "auc_loss": round(mean_loss, 6)})

all_results.sort(key=lambda r: r["mse"])
best = all_results[0]
print(f"Best calibration: T={best['T']}, p={best['p']}, MSE={best['mse']}, AUC_loss={best['auc_loss']}")

print(f"\n  COMPARISON: metastack (T={best['T']}, p={best['p']}) vs optimal vs canonical vs sigma vs baseline")
print(f"  {'target':<14} {'baseline':>10} {'canonical':>10} {'sigma':>10} {'metastack':>10} {'opt':>10}")
print(f"  " + "-" * 75)

totals = {"base": 0, "can": 0, "sigma": 0, "meta": 0, "opt": 0}
for name, t in targets.items():
    a = target_aucs[name]
    
    # Baseline (Vina+XGB)
    base = 0.7 * t["xgb"] + 0.3 * t["vina_n"]
    auc_base = float(roc_auc_score(t["labels"], base))
    
    # Canonical (0.2, 0.6, 0.2)
    can = t["vina_n"] * 0.2 + t["xgb"] * 0.6 + t["clgnn"] * 0.2
    auc_can = float(roc_auc_score(t["labels"], can))
    
    # Sigma adaptive
    max_pre = max(a["vina"], a["xgb"])
    if max_pre >= 0.93:
        gnn_ret = 0.0
    elif max_pre >= 0.83:
        gnn_ret = (0.93 - max_pre) / 0.10
    else:
        gnn_ret = 1.0
    w_v_s = 0.2 * (1 - gnn_ret * 0.2) if gnn_ret < 1 else 0.2
    w_x_s = 0.6 + (0.2 - 0.2 * gnn_ret) if gnn_ret > 0 else 0.8
    w_c_s = 0.2 * gnn_ret
    sigma_scores = t["vina_n"] * 0.2 + t["xgb"] * 0.6 + t["clgnn"] * 0.2 * gnn_ret
    auc_sigma = float(roc_auc_score(t["labels"], sigma_scores))
    
    # Metastack
    w_v, w_x, w_c, info = metastack_weights(a["vina"], a["xgb"], a["clgnn"], T=best["T"], p=best["p"])
    meta = t["vina_n"] * w_v + t["xgb"] * w_x + t["clgnn"] * w_c
    auc_meta = float(roc_auc_score(t["labels"], meta))
    
    auc_opt = target_opt_auc[name]
    
    totals["base"] += auc_base
    totals["can"] += auc_can
    totals["sigma"] += auc_sigma
    totals["meta"] += auc_meta
    totals["opt"] += auc_opt
    
    print(f"  {name:<14} {auc_base:>10.4f} {auc_can:>10.4f} {auc_sigma:>10.4f} {auc_meta:>10.4f} {auc_opt:>10.4f}")

n = len(targets)
print(f"  " + "-" * 75)
print(f"  {'MEAN':<14} {totals['base']/n:>10.4f} {totals['can']/n:>10.4f} {totals['sigma']/n:>10.4f} {totals['meta']/n:>10.4f} {totals['opt']/n:>10.4f}")
print(f"  {'vs baseline':<14} {'':>10} {totals['can']/n - totals['base']/n:>+10.4f} {totals['sigma']/n - totals['base']/n:>+10.4f} {totals['meta']/n - totals['base']/n:>+10.4f} {totals['opt']/n - totals['base']/n:>+10.4f}")

# Save
with open(OUT / "metastack_calibration.json", "w") as f:
    json.dump({
        "best_params": {"T": best["T"], "p": best["p"]},
        "best_mse": best["mse"],
        "auc_loss": best["auc_loss"],
        "top10_params": all_results[:10],
        "target_aucs": target_aucs,
    }, f, indent=2)
print(f"\n  Saved: {OUT / 'metastack_calibration.json'}")
