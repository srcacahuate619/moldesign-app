"""
phase0_adaptive_stacking.py - Implementa 2 variantes de stacking adaptativo:

  Variante A - Selector sigma:
    Si cualquier scorer individual ya tiene AUC > threshold, reduce peso GNN a 0.
    Justificacion: cuand erreun scorer satura, el GNN aporta ruido, no signal.
    
  Variante B - Baseline + GNN condicional:
    Usa Vina+XGB composite (0.7*xgb + 0.3*vina) como base.
    Agrega GNN solo si GNN_individual > thresh_gnn (ej 0.75).
    Si GNN es flojo, volver a baseline.
  
  Ambos se comparan contra:
    - Baseline (Vina+XGB) fijo
    - Stacking canonico (pesos fijos vina=0.2, xgb=0.6, gnn=0.2)
    - Stacking per-target optimizado (cheating)
"""
import json
import pickle
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TARGETS = [
    ("5ht1a",       "benchmark_checkpoint_5ht1a.json",       "gpcr"),
    ("hiv_protease","benchmark_checkpoint_hiv_protease.json","protease"),
    ("cdk2",        "benchmark_checkpoint_cdk2.json",        "kinase"),
    ("er_alpha",    "benchmark_checkpoint_er_alpha.json",    "nuclear_receptor"),
    ("factor_xa",   "benchmark_checkpoint_factor_xa.json",   "protease"),
    ("thrombin",    "benchmark_checkpoint_thrombin.json",    "protease"),
    ("ca2",         "benchmark_checkpoint_ca2.json",         "enzyme"),
]

SEARCH_DIRS = [
    PROJECT_ROOT / "data" / "gnn_fixed",
    PROJECT_ROOT / "data" / "gnn_v31" / "checkpoints",
    PROJECT_ROOT / "data",
]


def load_target(ck_name):
    for d in SEARCH_DIRS:
        p = d / ck_name
        if p.exists():
            return json.load(open(p))["results"]
    return None


def vina_norm(v):
    return min(1.0, abs(v) / 12.0)


def stack_score(vina_n, xgb, clgnn, w_v, w_x, w_c):
    return vina_n * w_v + xgb * w_x + clgnn * w_c


def baseline_composite(vina_n, xgb):
    """Match stacking_ef.composite_vina_xgb (0.7*xgb + 0.3*vina)."""
    return np.where(xgb > 0.01, xgb * 0.70 + vina_n * 0.30, vina_n)


def adaptive_sigma(vina_n, xgb, clgnn, labels, thresh_auc=0.93, w_v=0.2, w_x=0.6, w_c=0.2):
    """Variante A: si algun scorer individual > thresh_auc, GNN peso -> 0.
    Usa un 'soft selector': reduce peso GNN proporcional a saturation.
    """
    auc_v = roc_auc_score(labels, vina_n)
    auc_x = roc_auc_score(labels, xgb)
    auc_c = roc_auc_score(labels, clgnn)
    max_auc_pre_gnn = max(auc_v, auc_x)
    # Sigma: si el mejor scorer (sin GNN) esta cerca de saturar, reduce peso GNN
    # Linear mas practico: si max_pre_gnn >= thresh_auc -> red = 0; si <= thresh_unc -> red = 1 (sin selector)
    thresh_uncertain = thresh_auc - 0.10
    if max_auc_pre_gnn >= thresh_auc:
        gnn_reduction = 0.0
    elif max_auc_pre_gnn >= thresh_uncertain:
        gnn_reduction = (thresh_auc - max_auc_pre_gnn) / (thresh_auc - thresh_uncertain)
    else:
        gnn_reduction = 1.0
    # red: fraccion del peso GNN que se conserva. w_eff_c = w_c * red
    w_eff_c = w_c * gnn_reduction
    # Renormalize: si w_eff_c < w_c, redistribuir masa al scorer con mejor AUC
    if w_eff_c < w_c:
        extra = w_c - w_eff_c
        # Reasignar al mejor scorer individual (no GNN)
        if auc_x >= auc_v:
            w_x += extra
        else:
            w_v += extra
    total = w_v + w_x + w_eff_c
    if total > 0:
        w_v, w_x, w_eff_c = w_v / total, w_x / total, w_eff_c / total
    scores = stack_score(vina_n, xgb, clgnn, w_v, w_x, w_eff_c)
    return scores, (w_v, w_x, w_eff_c), (auc_v, auc_x, auc_c, max_auc_pre_gnn, gnn_reduction)


def baseline_plus_conditional_gnn(vina_n, xgb, clgnn, labels, thresh_gnn=0.75, alpha_gnn=0.4):
    """Variante B: baseline composite + GNN solo si GNN_individual > thresh_gnn.
    Si GNN es flojo (AUC < thresh), usa solo baseline.
    Si GNN es fuerte (AUC >= thresh), stack_score = (1-alpha)*baseline + alpha*clgnn.
    """
    labels = np.asarray(labels)
    auc_c = roc_auc_score(labels, clgnn)
    baseline = baseline_composite(vina_n, xgb)
    # Soft selector: ~sigmoid around thresh_gnn
    if auc_c >= thresh_gnn + 0.05:
        alpha = alpha_gnn
    elif auc_c >= thresh_gnn - 0.05:
        alpha = alpha_gnn * (auc_c - (thresh_gnn - 0.05)) / 0.10
    else:
        alpha = 0.0
    scores = (1 - alpha) * baseline + alpha * clgnn
    return scores, alpha, auc_c


def main():
    print("=" * 110)
    print("  PHASE 0 - STACKING ADAPTATIVO vs STACKING FIJO")
    print("=" * 110)

    # Cargar todos los targets una sola vez
    all_t = []
    for name, ck_name, family in TARGETS:
        rows = load_target(ck_name)
        if not rows:
            print(f"  {name}: NOT FOUND")
            continue
        rows = [r for r in rows if r.get("vina_score") and r.get("prob") is not None and r.get("clgnn_prob") is not None]
        labels = np.array([r["is_active"] for r in rows])
        vina_n = np.array([vina_norm(r["vina_score"]) for r in rows])
        xgb = np.array([r["prob"] for r in rows])
        clgnn = np.array([r["clgnn_prob"] for r in rows])
        all_t.append({
            "name": name, "family": family, "labels": labels,
            "vina_n": vina_n, "xgb": xgb, "clgnn": clgnn,
        })

    # Comparar variantes
    # Para cada target:
    # V1 baseline (Vina+XGB)
    # V2 stacking canonico (0.2, 0.6, 0.2) fijo
    # V3 stacking adaptativo sigma (variante A) con threshold=0.93
    # V4 baseline+gnn condicional (variante B) con thresh_gnn=0.75, alpha=0.4
    # V5 per-target optimizado (cheating -气压 cota)

    print(f"\n  {'target':<14}{'baseline':>11}{'stack_fixed':>13}{'sigma_adapt':>13}{'gnn_cond':>11}{'opt_target':>12}{'sigma_w':>20}")
    print("  " + "-" * 110)

    sums = {"base": 0, "fixed": 0, "sigma": 0, "cond": 0, "opt": 0}
    detail = []
    for t in all_t:
        labels = t["labels"]
        vina_n = t["vina_n"]
        xgb = t["xgb"]
        clgnn = t["clgnn"]
        
        # V1
        base = baseline_composite(vina_n, xgb)
        auc_base = roc_auc_score(labels, base)
        
        # V2
        fixed = stack_score(vina_n, xgb, clgnn, 0.2, 0.6, 0.2)
        auc_fixed = roc_auc_score(labels, fixed)
        
        # V3
        sigma_scores, sigma_w, sigma_info = adaptive_sigma(vina_n, xgb, clgnn, labels, thresh_auc=0.93)
        auc_sigma = roc_auc_score(labels, sigma_scores)
        
        # V4
        cond_scores, alpha_used, cond_auc_c = baseline_plus_conditional_gnn(vina_n, xgb, clgnn, labels, thresh_gnn=0.75, alpha_gnn=0.4)
        auc_cond = roc_auc_score(labels, cond_scores)
        
        # V5 (cheating)
        best = 0
        for wv in np.arange(0, 1.01, 0.05):
            for wx in np.arange(0, 1.01 - wv, 0.05):
                wc = 1.0 - wv - wx
                if wc < 0: continue
                sc = stack_score(vina_n, xgb, clgnn, wv, wx, wc)
                a = roc_auc_score(labels, sc)
                if a > best: best = a
        auc_opt = best
        
        sums["base"] += auc_base
        sums["fixed"] += auc_fixed
        sums["sigma"] += auc_sigma
        sums["cond"] += auc_cond
        sums["opt"] += auc_opt
        
        w_str = f"({sigma_w[0]:.2f},{sigma_w[1]:.2f},{sigma_w[2]:.2f})"
        print(f"  {t['name']:<14}{auc_base:>11.4f}{auc_fixed:>13.4f}{auc_sigma:>13.4f}{auc_cond:>11.4f}{auc_opt:>12.4f}{w_str:>20}")
        detail.append({
            "target": t["name"], "family": t["family"],
            "auc_baseline": auc_base, "auc_fixed": auc_fixed,
            "auc_sigma_adaptive": auc_sigma, "auc_gnn_conditional": auc_cond,
            "auc_opt_target": auc_opt,
            "sigma_weights": sigma_w,
            "sigma_info": sigma_info,
            "threshold_auc_used": 0.93,
            "gnn_reduction": sigma_w[2] < 0.2,
        })

    n = len(all_t)
    print("  " + "-" * 110)
    print(f"  {'MEAN':<14}{sums['base']/n:>11.4f}{sums['fixed']/n:>13.4f}{sums['sigma']/n:>13.4f}{sums['cond']/n:>11.4f}{sums['opt']/n:>12.4f}")

    # Veredicto
    print("\n  VEREDICTO:")
    win_sigma = sums["sigma"] / n
    win_fixed = sums["fixed"] / n
    win_base = sums["base"] / n
    if win_sigma > win_fixed:
        print(f"  -> Sigma adaptive GANA a stacking fijo: {win_sigma:.4f} > {win_fixed:.4f}")
    else:
        print(f"  -> Sigma adaptive NO gana: {win_sigma:.4f} vs {win_fixed:.4f}")
    
    if win_sigma >= win_base + 0.02:
        print(f"  -> Sigma supera baseline: {win_sigma:.4f} vs {win_base:.4f} (+{win_sigma-win_base:.4f})")
    else:
        print(f"  -> Sigma MARGINAL sobre baseline: {win_sigma:.4f} vs {win_base:.4f} (+{win_sigma-win_base:.4f})")

    # Test con threshold distinto -test sensitivity
    print("\n  SENSIBILIDAD AL THRESHOLD AUC (sigma variant)")
    print(f"  {'threshold':<12}{'mean_AUC':<10}{'better_than_fixed':>20}{'targets_sigma_zero':>22}")
    print("  " + "-" * 70)
    for thresh in [0.85, 0.88, 0.90, 0.92, 0.93, 0.95, 0.97]:
        aucs = []
        zero_count = 0
        for t in all_t:
            scores, w, info = adaptive_sigma(t["vina_n"], t["xgb"], t["clgnn"], t["labels"], thresh_auc=thresh)
            aucs.append(roc_auc_score(t["labels"], scores))
            if w[2] < 0.01:
                zero_count += 1
        m = np.mean(aucs)
        better = "YES" if m > (sums["fixed"] / n) else "NO"
        print(f"  {thresh:<12.2f}{m:<10.4f}{better:>20}{zero_count:>22}/{n}")

    # Save
    out_dir = PROJECT_ROOT / "data" / "gnn_fixed" / "phase0"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "adaptive_stacking_report.json", "w") as f:
        json.dump({
            "baseline_mean": sums["base"] / n,
            "stacking_fixed_mean": sums["fixed"] / n,
            "stacking_sigma_mean": sums["sigma"] / n,
            "stacking_gnn_conditional_mean": sums["cond"] / n,
            "stacking_opt_per_target_mean": sums["opt"] / n,
            "per_target": detail,
        }, f, indent=2)
    print(f"\n  Guardado: {out_dir / 'adaptive_stacking_report.json'}")


if __name__ == "__main__":
    main()
