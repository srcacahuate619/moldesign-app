#!/usr/bin/env python3
"""Bootstrap confidence intervals for Universal Metal Score deltas.

Tests whether the M4 -> M5_gated improvement is statistically significant
via 10,000 bootstrap resamples with replacement. Computes 95% CI for:
  - Individual scorer AUCs
  - M4 AUC
  - M5_gated AUC
  - Delta (M5 - M4)

If the 95% CI of the delta excludes 0, the improvement is significant.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).parent))
from universal_metal_score import detect_warheads

N_BOOTSTRAP = 10000
SEED = 42
np.random.seed(SEED)


def warhead_only_score(smi):
    """PURE SMARTS warhead component (the paper's core invariant).

    Returns 0.0 if no warhead detected; 0.85-0.95 scaled by warhead count.
    Matches the SMARTS-only rows of Table 3.4, delong_paired_test.py, and ef_metrics.py.
    NOTE: do NOT use the checkpoint's `universal_metal_score` field — that
    stores the legacy multi-component UMS (warhead + donor + MolChamb) and
    would produce values inconsistent with the paper's warhead-only framing.
    """
    wh = detect_warheads(smi)
    if not any(wh.values()):
        return 0.0
    # V2: `n` cuenta GRUPOS QUIMICOS distintos, no claves que casaron. Varias de
    # las siete describen el mismo grupo -una sulfonamida primaria casa tambien
    # `sulfonamide`-, y la formula es monotona en n, asi que el doble conteo
    # subia el score. Produccion usa la misma funcion: si esto se separa, el
    # script del paper deja de reproducir lo que el producto calcula.
    n = contar_warheads_distintos(wh)
    return 0.85 + 0.10 * min(n / 3.0, 1.0)


def load_mmp9():
    """Load MMP9 benchmark checkpoint with warhead-only score recomputed."""
    ckpt = json.loads(Path("data/benchmark_checkpoint_mmp9.json").read_bytes().decode("utf-8"))
    mols = []
    for r in ckpt["results"]:
        smi = r.get("smiles", "")
        is_a = r.get("is_active", False)
        vina = r.get("vina_score")
        prob = r.get("prob")
        if vina is None or prob is None:
            continue
        ums = warhead_only_score(smi)
        mols.append({
            "is_active": 1 if is_a else 0,
            "vina": abs(vina),
            "prob": prob,
            "ums": ums,
        })
    return mols


def load_ca2():
    """Load CA2 LOTO checkpoint with warhead-only score recomputed."""
    ckpt = json.loads(Path("data/molchamb_loto/checkpoints/benchmark_checkpoint_ca2.json").read_bytes().decode("utf-8"))
    mols = []
    for r in ckpt["results"]:
        smi = r.get("smiles", "")
        is_a = r.get("is_active", False)
        vina = r.get("vina_score")
        prob = r.get("prob")
        gnn = r.get("gnn_d_prob")
        if vina is None or prob is None or gnn is None:
            continue
        ums = warhead_only_score(smi)
        mols.append({
            "is_active": 1 if is_a else 0,
            "vina": abs(vina),
            "prob": prob,
            "gnn": gnn,
            "ums": ums,
        })
    return mols


def safe_auc(y, s):
    """Compute AUC, return 0.5 if degenerate."""
    if len(set(y)) < 2 or len(s) == 0:
        return 0.5
    return roc_auc_score(y, s)


def compute_m4_m5(mols, target):
    """Compute M4 and M5_gated AUC for a target's molecules."""
    n = len(mols)
    y = np.array([m["is_active"] for m in mols])

    if target == "ca2":
        # M4 = Vina + XGB + CLGNN + GNN-D (use adaptive weighting from LOTO)
        # Simple equal weights for bootstrap
        vina = np.array([m["vina"] for m in mols])
        vmax = vina.max() if vina.max() > 0 else 12
        vn = np.minimum(vina / vmax, 1.0)
        xgb = np.array([m["prob"] for m in mols])
        gnn = np.array([m["gnn"] for m in mols])
        ums = np.array([m["ums"] for m in mols])

        # Use equal weights for M4
        m4 = 0.25 * vn + 0.25 * xgb + 0.25 * gnn
        # M5_gated adds UMS
        m5 = 0.20 * vn + 0.20 * xgb + 0.20 * gnn + 0.40 * ums
    else:  # mmp9
        # CLGNN disabled (0.5 constant), so M4 = XGB
        xgb = np.array([m["prob"] for m in mols])
        ums = np.array([m["ums"] for m in mols])

        m4 = 1.0 * xgb
        m5 = 0.75 * xgb + 0.25 * ums

    return y, m4, m5, ums


def bootstrap_auc_delta(y, m4, m5, n_boot=N_BOOTSTRAP):
    """Bootstrap 95% CI for M4 AUC, M5 AUC, and delta."""
    n = len(y)
    rng = np.random.RandomState(SEED)

    m4_aucs = []
    m5_aucs = []
    deltas = []
    ums_aucs = []

    for _ in range(n_boot):
        idx = rng.randint(0, n, n)
        yb = y[idx]
        m4b = m4[idx]
        m5b = m5[idx]
        if len(set(yb)) < 2:
            continue
        a4 = roc_auc_score(yb, m4b)
        a5 = roc_auc_score(yb, m5b)
        m4_aucs.append(a4)
        m5_aucs.append(a5)
        deltas.append(a5 - a4)

    m4_aucs = np.array(m4_aucs)
    m5_aucs = np.array(m5_aucs)
    deltas = np.array(deltas)

    return {
        "m4_mean": float(m4_aucs.mean()),
        "m4_ci_low": float(np.percentile(m4_aucs, 2.5)),
        "m4_ci_high": float(np.percentile(m4_aucs, 97.5)),
        "m5_mean": float(m5_aucs.mean()),
        "m5_ci_low": float(np.percentile(m5_aucs, 2.5)),
        "m5_ci_high": float(np.percentile(m5_aucs, 97.5)),
        "delta_mean": float(deltas.mean()),
        "delta_ci_low": float(np.percentile(deltas, 2.5)),
        "delta_ci_high": float(np.percentile(deltas, 97.5)),
        "delta_p": float((deltas <= 0).mean()),  # p-value: fraction of bootstraps with delta <= 0
        "n_bootstrap": int(len(deltas)),
    }


def main():
    print("="*65)
    print("BOOTSTRAP CONFIDENCE INTERVALS (10,000 iterations)")
    print("="*65)
    print()

    results = {}

    # CA2
    print("[CA2] Loading checkpoint...")
    ca2_mols = load_ca2()
    print(f"  {len(ca2_mols)} molecules ({sum(m['is_active'] for m in ca2_mols)} actives)")
    y, m4, m5, ums = compute_m4_m5(ca2_mols, "ca2")
    print(f"  Point estimates: M4={safe_auc(y,m4):.4f}  M5={safe_auc(y,m5):.4f}  Delta={safe_auc(y,m5)-safe_auc(y,m4):+.4f}")
    print(f"  Bootstrapping...", end=" ", flush=True)
    t0 = time.time()
    r_ca2 = bootstrap_auc_delta(y, m4, m5)
    print(f"done ({time.time()-t0:.1f}s)")
    results["ca2"] = r_ca2
    print(f"  M4: {r_ca2['m4_mean']:.4f}  [{r_ca2['m4_ci_low']:.4f}, {r_ca2['m4_ci_high']:.4f}]")
    print(f"  M5: {r_ca2['m5_mean']:.4f}  [{r_ca2['m5_ci_low']:.4f}, {r_ca2['m5_ci_high']:.4f}]")
    print(f"  Delta: {r_ca2['delta_mean']:+.4f}  [{r_ca2['delta_ci_low']:+.4f}, {r_ca2['delta_ci_high']:+.4f}]")
    print(f"  p-value (delta <= 0): {r_ca2['delta_p']:.6f}")
    print(f"  Significant (95% CI excludes 0): {'YES' if r_ca2['delta_ci_low'] > 0 or r_ca2['delta_ci_high'] < 0 else 'NO'}")
    print()

    # MMP9
    print("[MMP9] Loading checkpoint...")
    mmp9_mols = load_mmp9()
    print(f"  {len(mmp9_mols)} molecules ({sum(m['is_active'] for m in mmp9_mols)} actives)")
    y, m4, m5, ums = compute_m4_m5(mmp9_mols, "mmp9")
    print(f"  Point estimates: M4={safe_auc(y,m4):.4f}  M5={safe_auc(y,m5):.4f}  Delta={safe_auc(y,m5)-safe_auc(y,m4):+.4f}")
    print(f"  Bootstrapping...", end=" ", flush=True)
    t0 = time.time()
    r_mmp9 = bootstrap_auc_delta(y, m4, m5)
    print(f"done ({time.time()-t0:.1f}s)")
    results["mmp9"] = r_mmp9
    print(f"  M4: {r_mmp9['m4_mean']:.4f}  [{r_mmp9['m4_ci_low']:.4f}, {r_mmp9['m4_ci_high']:.4f}]")
    print(f"  M5: {r_mmp9['m5_mean']:.4f}  [{r_mmp9['m5_ci_low']:.4f}, {r_mmp9['m5_ci_high']:.4f}]")
    print(f"  Delta: {r_mmp9['delta_mean']:+.4f}  [{r_mmp9['delta_ci_low']:+.4f}, {r_mmp9['delta_ci_high']:+.4f}]")
    print(f"  p-value (delta <= 0): {r_mmp9['delta_p']:.6f}")
    print(f"  Significant (95% CI excludes 0): {'YES' if r_mmp9['delta_ci_low'] > 0 or r_mmp9['delta_ci_high'] < 0 else 'NO'}")
    print()

    # Summary
    print("="*65)
    print("SUMMARY: Bootstrap 95% Confidence Intervals")
    print("="*65)
    print(f"{'Target':10s} | {'M4 [CI]':30s} | {'M5 [CI]':30s} | {'Delta [CI]':25s} | p-value")
    print("-"*120)
    for tgt, r in results.items():
        m4_str = f"{r['m4_mean']:.4f} [{r['m4_ci_low']:.4f}, {r['m4_ci_high']:.4f}]"
        m5_str = f"{r['m5_mean']:.4f} [{r['m5_ci_low']:.4f}, {r['m5_ci_high']:.4f}]"
        d_str = f"{r['delta_mean']:+.4f} [{r['delta_ci_low']:+.4f}, {r['delta_ci_high']:+.4f}]"
        sig = "*" if (r['delta_ci_low'] > 0 or r['delta_ci_high'] < 0) else ""
        print(f"{tgt:10s} | {m4_str:30s} | {m5_str:30s} | {d_str:25s} | {r['delta_p']:.4f} {sig}")
    print()
    print("* = 95% CI excludes 0 (statistically significant)")
    print()

    # Save
    Path("data/molchamb_loto/bootstrap_ci_report.json").write_text(json.dumps(results, indent=2))
    print("Report: data/molchamb_loto/bootstrap_ci_report.json")


if __name__ == "__main__":
    main()
