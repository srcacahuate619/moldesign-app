#!/usr/bin/env python3
"""
scripts/delong_paired_test.py — Paired DeLong test for M4 vs M5_gated (SC-13).

Implements the paired DeLong test (DeLong et al., 1988; Sun & Xu, 2014)
comparing two correlated ROC curves on the SAME molecules, replacing the
informal bootstrap p-value (fraction of bootstraps with delta <= 0).

Replicates EXACTLY the M4/M5 definitions from:
  - scripts/bootstrap_ci.py   (CA2, MMP9)
  - scripts/compute_ace_m5.py (ACE)

Usage:
  python scripts/delong_paired_test.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from universal_metal_score import detect_warheads


# ── Paired DeLong implementation (Sun & Xu 2014 style) ──

def _auc_components(y_true, y_score):
    """Return (auc, V10 for positives, V01 for negatives)."""
    y_true = np.asarray(y_true, dtype=int)
    y_score = np.asarray(y_score, dtype=float)
    pos_idx = np.where(y_true == 1)[0]
    neg_idx = np.where(y_true == 0)[0]
    n1, n0 = len(pos_idx), len(neg_idx)
    if n1 == 0 or n0 == 0:
        raise ValueError("Need both classes")

    s_pos = y_score[pos_idx]
    s_neg = y_score[neg_idx]

    # V10[i] = mean over negatives of I(s_pos[i] > s_neg[j]) + 0.5*I(==)
    # Computed via pairwise comparison on sorted negatives (efficient).
    neg_sorted = np.sort(s_neg)
    # For each positive score, count negatives strictly below and equal.
    # Use searchsorted on sorted negatives.
    lt = np.searchsorted(neg_sorted, s_pos, side="left")
    le = np.searchsorted(neg_sorted, s_pos, side="right")
    V10 = (lt + 0.5 * (le - lt)) / n0

    # V01[j] = mean over positives of I(s_pos[i] > s_neg[j]) + 0.5*I(==)
    pos_sorted = np.sort(s_pos)
    lt_p = np.searchsorted(pos_sorted, s_neg, side="left")
    le_p = np.searchsorted(pos_sorted, s_neg, side="right")
    V01 = (n1 - le_p + 0.5 * (le_p - lt_p)) / n1

    auc = float(np.mean(V10))
    return auc, V10, V01, pos_idx, neg_idx


def delong_paired(y_true, score1, score2):
    """Paired DeLong test H0: AUC(score1) == AUC(score2).

    Returns dict with auc1, auc2, var1, cov, var2, z, p.
    """
    auc1, V10_1, V01_1, pos_idx, neg_idx = _auc_components(y_true, score1)
    auc2, V10_2, V01_2, _, _ = _auc_components(y_true, score2)

    n1 = len(pos_idx)
    n0 = len(neg_idx)

    # Structural covariance matrix S (2x2) — DeLong (1988) U-statistic:
    # S[k,l] = (1/n1) * Cov_muestral(V10_k, V10_l)
    #        + (1/n0) * Cov_muestral(V01_k, V01_l)
    # NOTE: the (1/n1) and (1/n0) factors are REQUIRED — they are the
    # variance of the U-statistic mean. Without them (an easy bug),
    # the variance is inflated by ~n1/n0 and significance is lost.
    d10_1 = V10_1 - auc1
    d10_2 = V10_2 - auc2
    d01_1 = V01_1 - auc1
    d01_2 = V01_2 - auc2

    S11 = (1 / (n1 * (n1 - 1))) * np.sum(d10_1 * d10_1) + (1 / (n0 * (n0 - 1))) * np.sum(d01_1 * d01_1)
    S22 = (1 / (n1 * (n1 - 1))) * np.sum(d10_2 * d10_2) + (1 / (n0 * (n0 - 1))) * np.sum(d01_2 * d01_2)
    S12 = (1 / (n1 * (n1 - 1))) * np.sum(d10_1 * d10_2) + (1 / (n0 * (n0 - 1))) * np.sum(d01_1 * d01_2)

    var_diff = S11 + S22 - 2 * S12
    if var_diff <= 0:
        z = float("inf")
        p = 0.0
    else:
        z = (auc1 - auc2) / np.sqrt(var_diff)
        p = 2.0 * (1.0 - stats.norm.cdf(abs(z)))

    return {
        "auc_m4": float(auc1),
        "auc_m5": float(auc2),
        "delta": float(auc2 - auc1),
        "var_m4": float(S11),
        "cov": float(S12),
        "var_m5": float(S22),
        "z": float(z),
        "p_delong": float(p),
        "n_total": int(len(y_true)),
        "n_pos": int(n1),
        "n_neg": int(n0),
    }


# ── Data loaders (replicating ef_metrics.py / bootstrap_ci.py) ──

def warhead_only_score(smi):
    """PURE SMARTS warhead component (the paper's core invariant).

    Returns 0.0 if no warhead detected; 0.85-0.95 scaled by warhead count.
    Matches the SMARTS-only rows of Table 3.4 and ef_metrics.py.
    NOTE: do NOT use the checkpoint's `universal_metal_score` field — that
    stores the legacy multi-component UMS (warhead + donor + MolChamb) and
    would produce values inconsistent with the paper's warhead-only framing.
    """
    wh = detect_warheads(smi)
    if not any(wh.values()):
        return 0.0
    n = sum(1 for v in wh.values() if v)
    return 0.85 + 0.10 * min(n / 3.0, 1.0)


def load_ca2():
    ckpt = json.loads(Path("data/molchamb_loto/checkpoints/benchmark_checkpoint_ca2.json")
                      .read_bytes().decode("utf-8"))
    mols = []
    for r in ckpt["results"]:
        vina, prob, gnn = r.get("vina_score"), r.get("prob"), r.get("gnn_d_prob")
        if vina is None or prob is None or gnn is None:
            continue
        smi = r.get("smiles", "")
        mols.append({"is_active": 1 if r.get("is_active") else 0,
                     "smiles": smi, "vina": abs(vina), "prob": prob, "gnn": gnn})
    return mols


def load_mmp9():
    ckpt = json.loads(Path("data/benchmark_checkpoint_mmp9.json").read_bytes().decode("utf-8"))
    mols = []
    for r in ckpt["results"]:
        smi, vina, prob = r.get("smiles", ""), r.get("vina_score"), r.get("prob")
        if vina is None or prob is None:
            continue
        mols.append({"is_active": 1 if r.get("is_active") else 0,
                     "smiles": smi, "vina": abs(vina), "prob": prob})
    return mols


def load_ace():
    ckpt = json.loads(Path("data/benchmark_checkpoint_ace.json").read_bytes().decode("utf-8"))
    mols = []
    for r in ckpt["results"]:
        smi, vina, prob = r.get("smiles", ""), r.get("vina_score"), r.get("prob")
        if vina is None or prob is None:
            continue
        mols.append({"is_active": 1 if r.get("is_active") else 0,
                     "smiles": smi, "vina": abs(vina), "prob": prob})
    return mols


def build_scores(mols, target):
    """Return (y, m4, m5) replicating ef_metrics.py (warhead-only pure)."""
    y = np.array([m["is_active"] for m in mols])
    vina = np.array([m["vina"] for m in mols])
    vmax = vina.max() if vina.max() > 0 else 12
    vn = np.minimum(vina / vmax, 1.0)
    xgb = np.array([m["prob"] for m in mols])
    ums = np.array([warhead_only_score(m["smiles"]) for m in mols])

    if target == "ca2":
        gnn = np.array([m["gnn"] for m in mols])
        m4 = 0.25 * vn + 0.25 * xgb + 0.25 * gnn
        m5 = 0.20 * vn + 0.20 * xgb + 0.20 * gnn + 0.40 * ums
    elif target == "mmp9":
        m4 = 1.0 * xgb
        m5 = 0.75 * xgb + 0.25 * ums
    elif target == "ace":
        m4 = vn * 0.3 + xgb * 0.7
        m5 = vn * 0.2 + xgb * 0.4 + ums * 0.4
    else:
        raise ValueError(target)
    return y, m4, m5


def main():
    report = {}
    for target, loader in [("ca2", load_ca2), ("mmp9", load_mmp9), ("ace", load_ace)]:
        mols = loader()
        y, m4, m5 = build_scores(mols, target)
        # Sanity: point estimates must match the paper's Table 3.2
        auc4 = roc_auc_score(y, m4)
        auc5 = roc_auc_score(y, m5)
        res = delong_paired(y, m4, m5)
        res["auc_m4_sklearn"] = float(auc4)
        res["auc_m5_sklearn"] = float(auc5)
        report[target] = res
        print(f"\n[{target.upper()}] n={res['n_total']} (pos={res['n_pos']}, neg={res['n_neg']})")
        print(f"  M4 AUC = {res['auc_m4']:.4f} (sklearn {res['auc_m4_sklearn']:.4f})")
        print(f"  M5 AUC = {res['auc_m5']:.4f} (sklearn {res['auc_m5_sklearn']:.4f})")
        print(f"  Delta  = {res['delta']:+.4f}")
        print(f"  Paired DeLong: z = {res['z']:.2f}, p = {res['p_delong']:.2e}")
        print(f"  var_m4={res['var_m4']:.2e} cov={res['cov']:.2e} var_m5={res['var_m5']:.2e}")
        verdict = "SIGNIFICANT" if res["p_delong"] < 0.05 else "NOT significant"
        print(f"  Verdict: {verdict}")

    out = Path("data/molchamb_loto/delong_paired_report.json")
    out.write_text(json.dumps(report, indent=2))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
