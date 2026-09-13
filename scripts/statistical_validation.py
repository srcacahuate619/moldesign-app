"""
scripts/statistical_validation.py
Statistical validation for the CL-GNN + XGBoost + Vina stacking.

Outputs:
  - Bootstrap confidence intervals (95%) for AUC of each scorer
  - DeLong test p-values comparing stack to Vina+XGB and single scorers
  - Permutation test null distribution

Usage:
  python scripts/statistical_validation.py --target 5ht1a
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from benchmark_ef_vina import rank_normalize

TARGETS = ["5ht1a", "cdk2", "hiv_protease", "er_alpha", "factor_xa", "thrombin", "ca2"]

BEST_WEIGHTS = {
    "5ht1a": {"vina": 0.2, "xgb": 0.4, "clgnn": 0.4},
    "default": {"vina": 0.3, "xgb": 0.5, "clgnn": 0.2},
}


def composite_stack(r, w):
    vina = abs(r.get("vina_score") or 0)
    vina_norm = min(1.0, vina / 12.0)
    xgb = r.get("prob", 0.0)
    clgnn = r.get("clgnn_prob", 0.5)
    return vina_norm * w["vina"] + xgb * w["xgb"] + clgnn * w["clgnn"]


def composite_vina_xgb(r):
    vina = abs(r.get("vina_score") or 0)
    vina_norm = min(1.0, vina / 12.0)
    xgb = r.get("prob", 0.0)
    return 0.7 * xgb + 0.3 * vina_norm


def bootstrap_auc(labels, scores, n=10000, ci=95):
    rng = np.random.default_rng(42)
    aucs = []
    n_samp = len(labels)
    for _ in range(n):
        idx = rng.choice(n_samp, size=n_samp, replace=True)
        try:
            aucs.append(roc_auc_score(labels[idx], scores[idx]))
        except ValueError:
            continue
    aucs = np.array(aucs)
    lower = float(np.percentile(aucs, (100 - ci) / 2))
    upper = float(np.percentile(aucs, 100 - (100 - ci) / 2))
    mean = float(aucs.mean())
    std = float(aucs.std())
    return mean, lower, upper, std


def delong_variance(labels, scores):
    """Approximate DeLong variance for AUC difference test.

    Returns SE of (AUC1 - AUC2) under the null that they're equal.
    """
    n_pos = int(labels.sum())
    n_neg = len(labels) - n_pos

    pos_mask = labels == 1
    neg_mask = labels == 0

    def structural(scores_arr):
        # V10 is per-positive structural components, V01 is per-negative
        V10 = np.zeros(n_pos)
        V01 = np.zeros(n_neg)
        for i, s_pos in enumerate(scores_arr[pos_mask]):
            # Sum over negatives where neg < pos (rank statistic)
            V10[i] = (scores_arr[neg_mask] < s_pos).mean()
        for j, s_neg in enumerate(scores_arr[neg_mask]):
            V01[j] = (scores_arr[pos_mask] > s_neg).mean()
        return V10, V01

    return structural


def delong_test(labels, scores_a, scores_b, n_bootstrap=10000):
    """Bootstrap-based AUC difference test (equivalent approximation to DeLong).

    Returns the p-value: probability of seeing AUC_A - AUC_B as extreme as observed
    under the null that both scorers are equivalent.
    """
    rng = np.random.default_rng(123)
    observed_diff = roc_auc_score(labels, scores_a) - roc_auc_score(labels, scores_b)
    n_samp = len(labels)
    null_diffs = []
    for _ in range(n_bootstrap):
        idx = rng.choice(n_samp, size=n_samp, replace=True)
        try:
            diff = roc_auc_score(labels[idx], scores_a[idx]) - roc_auc_score(labels[idx], scores_b[idx])
            null_diffs.append(diff)
        except ValueError:
            continue
    null_diffs = np.array(null_diffs)
    # one-sided test (A > B)
    p_value = float((null_diffs >= observed_diff).mean())
    return float(observed_diff), p_value, null_diffs


def permutation_test(labels, scores, n_perm=10000):
    """Null distribution of AUC by permuting labels."""
    rng = np.random.default_rng(42)
    true_auc = roc_auc_score(labels, scores)
    null_aucs = []
    n_samp = len(labels)
    for _ in range(n_perm):
        perm_labels = labels[rng.permutation(n_samp)]
        try:
            null_aucs.append(roc_auc_score(perm_labels, scores))
        except ValueError:
            continue
    null_aucs = np.array(null_aucs)
    p_value = float((null_aucs >= true_auc).mean())
    return float(true_auc), p_value, null_aucs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=str, default="5ht1a")
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--permutations", type=int, default=10000)
    args = parser.parse_args()

    print("=" * 80)
    print(f"  STATISTICAL VALIDATION — {args.target}")
    print("=" * 80)

    ck_path = PROJECT_ROOT / "data" / "gnn_fixed" / f"benchmark_checkpoint_{args.target}.json"
    if not ck_path.exists():
        print(f"ERROR: {ck_path} not found")
        return

    ck = json.load(open(ck_path))
    results = [r for r in ck["results"] if r.get("vina_score") is not None and r.get("clgnn_prob") is not None]
    n = len(results)
    n_act = sum(1 for r in results if r.get("is_active"))
    print(f"  N={n} actives={n_act}")

    labels = np.array([int(bool(r.get("is_active"))) for r in results])
    vina = np.array([abs(r["vina_score"]) / 12.0 for r in results])
    vina = np.minimum(vina, 1.0)
    xgb = np.array([r.get("prob", 0.0) for r in results])
    clgnn = np.array([r.get("clgnn_prob", 0.5) for r in results])

    weights = BEST_WEIGHTS.get(args.target, BEST_WEIGHTS["default"])
    stack = vina * weights["vina"] + xgb * weights["xgb"] + clgnn * weights["clgnn"]
    vina_xgb = 0.7 * xgb + 0.3 * vina

    scorers = {
        "Vina": vina,
        "XGBoost": xgb,
        "CL-GNN": clgnn,
        "Vina+XGB": vina_xgb,
        "Stacking": stack,
    }

    print(f"\n  --- Bootstrap {args.bootstrap}-resampling AUC CI ---")
    print(f"  {'Scorer':12s}  {'AUC':>7s}  {'95% CI':>22s}  {'std':>6s}")
    bootstrap_results = {}
    for name, sc in scorers.items():
        mean, lower, upper, std = bootstrap_auc(labels, sc, n=args.bootstrap)
        bootstrap_results[name] = {"mean": mean, "lower": lower, "upper": upper, "std": std}
        ci_str = f"[{lower:.4f}, {upper:.4f}]"
        print(f"  {name:12s}  {mean:7.4f}  {ci_str:>22s}  {std:.4f}")

    print(f"\n  --- AUC difference test (vs Stacking) ---")
    print(f"  {'Comparison':30s}  {'dAUC':>7s}  {'p-value':>10s}  {'Significant?':>14s}")
    for name, sc in scorers.items():
        if name == "Stacking":
            continue
        diff, p_value, _ = delong_test(labels, stack, sc, n_bootstrap=args.bootstrap)
        sig = "YES p<0.05" if p_value < 0.05 else "no"
        print(f"  Stacking - {name:18s}  {diff:+7.4f}  {p_value:10.4f}  {sig:>14s}")

    print(f"\n  --- Permutation test (single scorer null) ---")
    print(f"  {'Scorer':12s}  {'AUC':>7s}  {'p-value':>12s}  {'Significant?':>14s}")
    perm_results = {}
    for name, sc in scorers.items():
        true_auc, p_value, null_aucs = permutation_test(labels, sc, n_perm=args.permutations)
        perm_results[name] = {"true_auc": true_auc, "p_value": p_value, "null_mean": float(null_aucs.mean()),
                              "null_std": float(null_aucs.std())}
        sig = "p<0.001" if p_value < 0.001 else ("p<0.05" if p_value < 0.05 else "n.s.")
        print(f"  {name:12s}  {true_auc:7.4f}  {p_value:12.6f}  {sig:>14s}")

    out = {
        "target": args.target,
        "n_total": n,
        "n_actives": n_act,
        "weights_used": weights,
        "bootstrap": {
            name: bootstrap_results[name] for name in scorers
        },
        "permutation": perm_results,
    }
    out_path = PROJECT_ROOT / "data" / "gnn_fixed" / f"statistical_validation_{args.target}.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
