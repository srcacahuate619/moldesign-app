#!/usr/bin/env python3
"""Compute M5_gated for ACE after benchmark completes."""
import json, sys, time
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).parent))
from scipy.stats import pearsonr

# ── LA VARIANTE DE UMS, QUE ERA LA EQUIVOCADA ────────────────────────────
#
# Este script usaba `compute_universal_metal_score` —el UMS HISTÓRICO, que
# mezcla warheads, número de donantes y MolChamb— mientras `bootstrap_ci.py`,
# `delong_paired_test.py` y `ef_metrics.py` usan la variante SMARTS pura. Es la
# inconsistencia del §9.4 de `docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md`, y
# explica por qué `ace_m5_report_postfix.json` no se podía reconciliar con
# `delong_paired_report.json`: no estaban midiendo la misma señal.
#
# El §2 del ADR autoriza una sola, y `services/pipeline/protocols/m5/zinc.py`
# es su única implementación de producción. Este script la importa en vez de
# tener la suya: es el gate §10.3.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from services.pipeline.protocols.m5.zinc import ums_desde_smiles  # noqa: E402

CKPT_PATH = Path("data/benchmark_checkpoint_ace.json")
REPORT_PATH = Path("data/molchamb_loto/ace_m5_report.json")

def main():
    if not CKPT_PATH.exists():
        print(f"Checkpoint not found: {CKPT_PATH}")
        return

    print(f"Loading ACE checkpoint: {CKPT_PATH.name} ({CKPT_PATH.stat().st_size/1024/1024:.0f}MB)")
    data = json.loads(CKPT_PATH.read_bytes().decode("utf-8"))
    results = data.get("results", [])
    print(f"Molecules: {len(results)}")

    mols = []
    for r in results:
        smi = r.get("smiles", "")
        is_a = r.get("is_active", False)
        vina = r.get("vina_score")
        prob = r.get("prob")          # XGBoost
        if vina is None or prob is None:
            continue

        # El UMS autorizado: SMARTS puro. MolChamb ya no entra —el histórico
        # lo mezclaba— y por eso este reporte no coincidía con el de DeLong.
        ums_score = ums_desde_smiles(smi)

        mols.append({
            "is_active": 1 if is_a else 0,
            "vina": abs(vina),
            "prob": prob,
            "ums": ums_score,
        })

    n = len(mols)
    n_act = sum(m["is_active"] for m in mols)
    print(f"Valid: {n} mols ({n_act} actives)")

    y = np.array([m["is_active"] for m in mols])

    # Normalize Vina
    v_vals = [m["vina"] for m in mols]
    vmax = max(v_vals)
    vn = np.array([min(1.0, v / vmax) for v in v_vals])
    xb = np.array([m["prob"] for m in mols])
    um = np.array([m["ums"] for m in mols])

    # Individual AUCs
    auc_vina = roc_auc_score(y, vn)
    auc_xgb = roc_auc_score(y, xb)
    auc_ums = roc_auc_score(y, um)
    print(f"\nIndividual AUCs:")
    print(f"  Vina:     {auc_vina:.4f}")
    print(f"  XGBoost:  {auc_xgb:.4f}")
    print(f"  UnivMetal: {auc_ums:.4f}")

    # M4 = Vina + XGB (Vina-only is random, CLGNN disabled)
    # Fixed equal weights
    m4_eq = vn * 0.3 + xb * 0.7
    auc_m4_eq = roc_auc_score(y, m4_eq)
    print(f"\nM4 (vina=0.3, xgb=0.7): {auc_m4_eq:.4f}")

    # M5_gated = Vina + XGB + UMS with equal weights
    m5_eq = vn * 0.2 + xb * 0.4 + um * 0.4
    auc_m5_eq = roc_auc_score(y, m5_eq)
    print(f"M5 (vina=0.2, xgb=0.4, ums=0.4): {auc_m5_eq:.4f}")
    print(f"Delta (equal weights): {auc_m5_eq - auc_m4_eq:+.4f}")

    # Bootstrap CI with fixed weights
    n_boot = 10000
    rng = np.random.RandomState(42)
    deltas_fixed = []
    m4_fixed = []
    m5_fixed = []
    for _ in range(n_boot):
        idx = rng.randint(0, n, n)
        yb = y[idx]
        if len(set(yb)) < 2:
            continue
        m4b = vn[idx] * 0.3 + xb[idx] * 0.7
        m5b = vn[idx] * 0.2 + xb[idx] * 0.4 + um[idx] * 0.4
        a4 = roc_auc_score(yb, m4b)
        a5 = roc_auc_score(yb, m5b)
        m4_fixed.append(a4)
        m5_fixed.append(a5)
        deltas_fixed.append(a5 - a4)

    deltas = np.array(deltas_fixed)
    m4_arr = np.array(m4_fixed)
    m5_arr = np.array(m5_fixed)

    delta_ci_low = np.percentile(deltas, 2.5)
    delta_ci_high = np.percentile(deltas, 97.5)
    p_value = (deltas <= 0).mean()

    print(f"\nBootstrap CI (10k iter, fixed weights):")
    print(f"  M4:  {m4_arr.mean():.4f} [{np.percentile(m4_arr, 2.5):.4f}, {np.percentile(m4_arr, 97.5):.4f}]")
    print(f"  M5:  {m5_arr.mean():.4f} [{np.percentile(m5_arr, 2.5):.4f}, {np.percentile(m5_arr, 97.5):.4f}]")
    print(f"  Delta: {deltas.mean():+.4f} [{delta_ci_low:+.4f}, {delta_ci_high:+.4f}]")
    print(f"  p-value: {p_value:.6f}")
    sig = "SIGNIFICANT" if delta_ci_low > 0 else "NOT significant at 95%"
    print(f"  Verdict: {sig}")

    # Individual scorer contributions
    print(f"\nIndividual AUCs for stacking:")
    print(f"  Vina:       {auc_vina:.4f}")
    print(f"  XGBoost:    {auc_xgb:.4f}")
    print(f"  UnivMetal:  {auc_ums:.4f}")

    # Summary
    report = {
        "target": "ace",
        "pdb": "1o86",
        "n_total": n,
        "n_actives": n_act,
        "auc_vina": round(auc_vina, 4),
        "auc_xgb": round(auc_xgb, 4),
        "auc_univ_metal": round(auc_ums, 4),
        "auc_m4_equal": round(auc_m4_eq, 4),
        "auc_m5_equal": round(auc_m5_eq, 4),
        "delta_equal": round(auc_m5_eq - auc_m4_eq, 4),
        "delta_bootstrap_mean": round(float(deltas.mean()), 4),
        "delta_bootstrap_ci_low": round(float(delta_ci_low), 4),
        "delta_bootstrap_ci_high": round(float(delta_ci_high), 4),
        "p_value": round(float(p_value), 6),
        "significant": bool(delta_ci_low > 0),
        "m4_ci": [round(float(np.percentile(m4_arr, 2.5)), 4), round(float(np.percentile(m4_arr, 97.5)), 4)],
        "m5_ci": [round(float(np.percentile(m5_arr, 2.5)), 4), round(float(np.percentile(m5_arr, 97.5)), 4)],
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"\nReport saved: {REPORT_PATH}")

    # Final consolidated table row
    print(f"\n{'='*70}")
    print(f"ACE FINAL: target={report['target']}, pdb={report['pdb']}")
    print(f"  M4={report['auc_m4_equal']:.4f} -> M5={report['auc_m5_equal']:.4f}, delta={report['delta_equal']:+.4f}")
    print(f"  Bootstrap: [{report['delta_bootstrap_ci_low']:+.4f}, {report['delta_bootstrap_ci_high']:+.4f}], p={report['p_value']}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
