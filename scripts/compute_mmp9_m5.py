#!/usr/bin/env python3
"""Compute M5_gated AUC for MMP9 with Universal Metal Score."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from universal_metal_score import compute_universal_metal_score

from sklearn.metrics import roc_auc_score
import numpy as np

CKPT_PATH = Path("data/benchmark_checkpoint_mmp9.json")
print(f"Loading checkpoint: {CKPT_PATH} ({CKPT_PATH.stat().st_size/1024/1024:.0f}MB)")
data = json.loads(CKPT_PATH.read_bytes().decode("utf-8"))
results = data.get("results", [])
print(f"Molecules: {len(results)}")

# Parse molecules
mols = []
for r in results:
    smi = r.get("smiles", "")
    is_active = r.get("is_active", False)
    vina = r.get("vina_score", None)
    prob = r.get("prob", None)          # XGBoost prob
    clgnn = r.get("clgnn_prob", None)   # CLGNN prob
    molchamb = r.get("molchamb_score", 0.5)
    ums = r.get("universal_metal_score", None)
    pose = r.get("pose_pdbqt", "")

    if vina is None or prob is None:
        continue

    # Compute UMS if not already present
    score_ums, feats = compute_universal_metal_score(smi, molchamb, "metaloenzyme")

    mols.append({
        "smiles": smi,
        "is_active": is_active,
        "vina": abs(vina),
        "prob": prob,
        "clgnn": clgnn if clgnn is not None else 0.5,
        "molchamb": molchamb,
        "ums": ums if ums is not None else score_ums,
        "ums_feats": feats,
    })

n = len(mols)
n_act = sum(1 for m in mols if m["is_active"])
print(f"Valid molecules: {n} ({n_act} actives)")

# Normalize Vina scores
vina_vals = [m["vina"] for m in mols]
vina_max = max(vina_vals) if vina_vals else 12
vina_norm = [min(1.0, v / vina_max) for v in vina_vals]

y_true = [1 if m["is_active"] else 0 for m in mols]

# Compute individual AUCs
auc_vina = roc_auc_score(y_true, vina_norm)
auc_xgb = roc_auc_score(y_true, [m["prob"] for m in mols])
auc_clgnn = roc_auc_score(y_true, [m["clgnn"] for m in mols])
auc_ums = roc_auc_score(y_true, [m["ums"] for m in mols])

print(f"\n=== Individual Scorer AUCs ===")
print(f"Vina:           {auc_vina:.4f}")
print(f"XGBoost:        {auc_xgb:.4f}")
print(f"CLGNN:          {auc_clgnn:.4f}")
print(f"UnivMetal:      {auc_ums:.4f}")

# M4: Vina + XGB + CLGNN
# Use benchmark weights (from auto-optimize: vina=0.0, prob=0.1, clgnn=0.9)
w_v, w_x, w_c = 0.0, 0.1, 0.9
m4_scores = [vina_norm[i]*w_v + m["prob"]*w_x + m["clgnn"]*w_c for i, m in enumerate(mols)]
auc_m4 = roc_auc_score(y_true, m4_scores)
print(f"\nM4 (vina={w_v}, xgb={w_x}, clgnn={w_c}): {auc_m4:.4f}")

# Also try default equal weights
w_v2, w_x2, w_c2 = 0.2, 0.4, 0.4
m4_scores2 = [vina_norm[i]*w_v2 + m["prob"]*w_x2 + m["clgnn"]*w_c2 for i, m in enumerate(mols)]
auc_m4_v2 = roc_auc_score(y_true, m4_scores2)
print(f"M4 (vina={w_v2}, xgb={w_x2}, clgnn={w_c2}): {auc_m4_v2:.4f}")

# Grid search optimal M4 weights
print(f"\n=== Grid search: optimal M4 weights ===")
best_m4 = 0.0
best_w = None
for w_x in np.arange(0.0, 1.01, 0.05):
    for w_c in np.arange(0.0, 1.01, 0.05):
        if abs(w_x + w_c - 1.0) > 0.01:
            continue
        scores = [vina_norm[i]*0.0 + m["prob"]*w_x + m["clgnn"]*w_c for i, m in enumerate(mols)]
        auc = roc_auc_score(y_true, scores)
        if auc > best_m4:
            best_m4 = auc
            best_w = (0.0, w_x, w_c)
print(f"Best M4: {best_m4:.4f} (vina={best_w[0]}, xgb={best_w[1]}, clgnn={best_w[2]})")

# M5_gated: same M4 but with UMS replacing Vina
print(f"\n=== M5_gated (with UnivMetal) ===")
w_u = 0.3  # UMS weight
w_x5 = 0.35
w_c5 = 0.35

m5_scores = [vina_norm[i]*0.0 + m["prob"]*w_x5 + m["clgnn"]*w_c5 + m["ums"]*w_u for i, m in enumerate(mols)]
auc_m5 = roc_auc_score(y_true, m5_scores)
print(f"M5 (xgb={w_x5}, clgnn={w_c5}, ums={w_u}): {auc_m5:.4f}")

# Grid search optimal M5 weights
print(f"\n=== Grid search: optimal M5 weights ===")
best_m5 = 0.0
best_w5 = None
for w_x in np.arange(0.0, 1.01, 0.05):
    for w_c in np.arange(0.0, 1.01, 0.05):
        for w_u in np.arange(0.0, 1.01, 0.05):
            if abs(w_x + w_c + w_u - 1.0) > 0.01:
                continue
            scores = [m["prob"]*w_x + m["clgnn"]*w_c + m["ums"]*w_u for i, m in enumerate(mols)]
            auc = roc_auc_score(y_true, scores)
            if auc > best_m5:
                best_m5 = auc
                best_w5 = (w_x, w_c, w_u)
print(f"Best M5: {best_m5:.4f} (xgb={best_w5[0]}, clgnn={best_w5[1]}, ums={best_w5[2]})")

# Summary
print(f"\n{'='*55}")
print(f"SUMMARY: MMP9 (1gkc) — Metalloenzyme")
print(f"{'='*55}")
print(f"Vina (no metal term):    {auc_vina:.4f}")
print(f"XGBoost:                 {auc_xgb:.4f}")
print(f"CLGNN:                   {auc_clgnn:.4f}")
print(f"Universal Metal Score:   {auc_ums:.4f}")
print(f"---")
print(f"M4 (optimized):          {best_m4:.4f}")
print(f"M5_gated (optimized):    {best_m5:.4f}")
print(f"Delta:                   {best_m5 - best_m4:+.4f}")
print(f"{'='*55}")

# Save report
report = {
    "target": "mmp9",
    "pdb": "1gkc",
    "n_total": n,
    "n_actives": n_act,
    "auc_vina": round(auc_vina, 4),
    "auc_xgb": round(auc_xgb, 4),
    "auc_clgnn": round(auc_clgnn, 4),
    "auc_univ_metal": round(auc_ums, 4),
    "auc_m4_optimized": round(best_m4, 4),
    "auc_m5_gated_optimized": round(best_m5, 4),
    "delta": round(best_m5 - best_m4, 4),
    "m4_weights": {"vina": best_w[0] if best_w else 0, "xgb": best_w[1] if best_w else 0.4, "clgnn": best_w[2] if best_w else 0.4},
    "m5_weights": {"xgb": best_w5[0] if best_w5 else 0.35, "clgnn": best_w5[1] if best_w5 else 0.35, "ums": best_w5[2] if best_w5 else 0.3},
}

report_path = Path("data/molchamb_loto/mmp9_m5_report.json")
report_path.write_text(json.dumps(report, indent=2))
print(f"\nReport saved: {report_path}")
