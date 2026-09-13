"""
phase0_diagnostic.py - Phase 0: diagnostico del pipeline actual.

Genera:
  1. Tabla AUC por scorer por target (Vina, XGB, CL-GNN, Vina+XGB, Stacking)
  2. Correlaciones pairwise entre scorers por target
  3. Grid search global: UNA terna de pesos para los 7 targets
  4. Tabla AUC con pesos globales vs pesos por familia
  5. Cohen's d effect size del delta stacking vs baseline (Vina+XGB)
  6. Bootstrap CI del delta AUC (stacking - Vina+XGB) por target

Uso:
  python scripts/phase0_diagnostic.py
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

# Pesos por familia (heuristica actual del repo, lineas 41-50 de stacking_ef.py)
PER_FAMILY_WEIGHTS = {
    "gpcr":              {"vina": 0.4, "xgb": 0.4, "clgnn": 0.2},
    "kinase":            {"vina": 0.2, "xgb": 0.8, "clgnn": 0.0},
    "protease":          {"vina": 0.2, "xgb": 0.7, "clgnn": 0.1},
    "nuclear_receptor":  {"vina": 0.3, "xgb": 0.5, "clgnn": 0.2},
    "enzyme":            {"vina": 0.3, "xgb": 0.5, "clgnn": 0.2},
    "default":           {"vina": 0.3, "xgb": 0.5, "clgnn": 0.2},
}


def load_target(name, ck_name):
    for d in SEARCH_DIRS:
        p = d / ck_name
        if p.exists():
            data = json.load(open(p))
            results = [r for r in data["results"]
                       if r.get("vina_score") is not None
                       and r.get("clgnn_prob") is not None
                       and r.get("prob") is not None]
            return results
    raise FileNotFoundError(f"{ck_name} not found in any search dir")


def vina_norm(v):
    return min(1.0, abs(v) / 12.0)


def stack_score(vina_n, xgb, clgnn, w_v, w_x, w_c):
    return vina_n * w_v + xgb * w_x + clgnn * w_c


def vina_xgb_composite(vina_n, xgb):
    """Match stacking_ef.composite_vina_xgb for honest comparison."""
    if xgb > 0.01:
        return xgb * 0.70 + vina_n * 0.30
    return vina_n


def ef_at(scores, labels, pct):
    n = len(scores)
    n_act = int(sum(labels))
    if n_act == 0:
        return 1.0
    top_n = max(1, int(n * pct / 100))
    pairs = sorted(zip(scores, labels), key=lambda x: x[0], reverse=True)
    found = sum(1 for _, a in pairs[:top_n] if a)
    expected = n_act * top_n / n
    return round(found / expected, 2) if expected > 0 else 1.0


def cohens_d(a, b):
    """Cohen's d between paired AUC samples (bootstrap)."""
    a = np.asarray(a)
    b = np.asarray(b)
    diff = a - b
    return float(diff.mean() / (diff.std(ddof=1) + 1e-12))


def bootstrap_auc(scores, labels, n_boot=2000, seed=42):
    """Return array of bootstrap AUC values."""
    rng = np.random.default_rng(seed)
    n = len(scores)
    scores = np.asarray(scores)
    labels = np.asarray(labels)
    aucs = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        if labels[idx].sum() == 0 or labels[idx].sum() == n:
            aucs[i] = 0.5
            continue
        aucs[i] = roc_auc_score(labels[idx], scores[idx])
    return aucs


def grid_search_global(per_target):
    """Find ONE (w_vina, w_xgb, w_clgnn) that maximizes MEAN rank across targets.
    Returns dict of evaluated grid points sorted by mean AUC (descending)."""
    results = []
    grid = np.arange(0.0, 1.01, 0.05)
    for w_v in grid:
        for w_x in grid:
            w_c = 1.0 - w_v - w_x
            if w_c < -1e-6 or w_c > 1.0 + 1e-6:
                continue
            w_c = max(0.0, w_c)
            aucs = []
            for t in per_target:
                scores = stack_score(t["vina_n"], t["xgb"], t["clgnn"], w_v, w_x, w_c)
                aucs.append(roc_auc_score(t["labels"], scores))
            results.append({
                "w_vina": float(round(w_v, 2)),
                "w_xgb":  float(round(w_x, 2)),
                "w_clgnn": float(round(w_c, 2)),
                "mean_auc": float(np.mean(aucs)),
                "min_auc": float(np.min(aucs)),
                "max_auc": float(np.max(aucs)),
                "per_target_auc": aucs,
            })
    results.sort(key=lambda r: r["mean_auc"], reverse=True)
    return results


def main():
    print("=" * 110)
    print("  PHASE 0 - DIAGNOSTICO DEL PIPELINE ACTUAL")
    print("  Pregunta: en cuantos de 7 targets el stacking supera significativamente al baseline?")
    print("=" * 110)

    per_target = []
    print(f"\n{'target':<14}{'family':<18}{'N':>6}{'act':>5} | {'AUC_vina':>9}{'AUC_xgb':>9}{'AUC_clgnn':>10}{'AUC_v+x':>9} | {'corr(v,x)':>10}{'corr(v,c)':>10}{'corr(x,c)':>10}")
    print("-" * 130)

    for name, ck_name, family in TARGETS:
        results = load_target(name, ck_name)
        labels = np.array([r["is_active"] for r in results])
        vina = np.array([abs(r["vina_score"]) for r in results])
        vina_n = np.array([vina_norm(r["vina_score"]) for r in results])
        xgb = np.array([r["prob"] for r in results])
        clgnn = np.array([r["clgnn_prob"] for r in results])
        vina_xgb = np.array([vina_xgb_composite(vina_norm(r["vina_score"]), r["prob"]) for r in results])

        auc_v = roc_auc_score(labels, vina)
        auc_x = roc_auc_score(labels, xgb)
        auc_c = roc_auc_score(labels, clgnn)
        auc_vx = roc_auc_score(labels, vina_xgb)

        cv_x = float(np.corrcoef(vina, xgb)[0, 1])
        cv_c = float(np.corrcoef(vina, clgnn)[0, 1])
        cx_c = float(np.corrcoef(xgb, clgnn)[0, 1])

        n = len(labels)
        n_act = int(labels.sum())

        print(f"{name:<14}{family:<18}{n:>6}{n_act:>5} | {auc_v:>9.4f}{auc_x:>9.4f}{auc_c:>10.4f}{auc_vx:>9.4f} | {cv_x:>10.4f}{cv_c:>10.4f}{cx_c:>10.4f}")

        per_target.append({
            "name": name, "family": family, "n": n, "n_act": n_act,
            "labels": labels, "vina": vina, "vina_n": vina_n, "xgb": xgb, "clgnn": clgnn, "vina_xgb": vina_xgb,
            "auc_vina": auc_v, "auc_xgb": auc_x, "auc_clgnn": auc_c, "auc_vina_xgb": auc_vx,
            "corr_vx": cv_x, "corr_vc": cv_c, "corr_xc": cx_c,
        })

    # -------- 0.4: Correlacion global (ya impresa arriba) --------
    print("\n" + "=" * 110)
    print("  0.4 CORRELACIONES - ortogonalidad entre los 3 scorers")
    print("=" * 110)
    print(f"\n  Mean |corr(Vina,XGB)|   = {np.mean([abs(t['corr_vx']) for t in per_target]):.4f}")
    print(f"  Mean |corr(Vina,CL-GNN)|= {np.mean([abs(t['corr_vc']) for t in per_target]):.4f}")
    print(f"  Mean |corr(XGB,CL-GNN)| = {np.mean([abs(t['corr_xc']) for t in per_target]):.4f}")
    print("  Interpretacion: <0.3 = signal ortogonal | >0.5 = redundancy")

    # -------- 0.1: Grid search global --------
    print("\n" + "=" * 110)
    print("  0.1 GRID SEARCH GLOBAL -una sola terna de pesos para los 7 targets")
    print("=" * 110)
    grid = grid_search_global(per_target)
    print("\n  Top 10 ternas por AUC promedio:")
    print(f"  {'rank':<6}{'w_vina':<8}{'w_xgb':<8}{'w_clgnn':<10}{'mean_auc':<10}{'min_auc':<10}{'max_auc':<10}")
    for i, r in enumerate(grid[:10]):
        print(f"  {i+1:<6}{r['w_vina']:<8.2f}{r['w_xgb']:<8.2f}{r['w_clgnn']:<10.2f}{r['mean_auc']:<10.4f}{r['min_auc']:<10.4f}{r['max_auc']:<10.4f}")

    canonical = grid[0]
    print(f"\n  >> Terna canonica propuesta: vina={canonical['w_vina']:.2f} xgb={canonical['w_xgb']:.2f} clgnn={canonical['w_clgnn']:.2f}")
    print(f"     Mean AUC = {canonical['mean_auc']:.4f}  (min={canonical['min_auc']:.4f}, max={canonical['max_auc']:.4f})")

    # -------- 0.1b: Comparar pesos globales vs per-family vs optimizados por target --------
    print("\n" + "=" * 110)
    print("  0.1b AUC COMPARATIVO: pesos optimizados por target | per-family | canonico global")
    print("=" * 110)
    print(f"\n  {'target':<14}{'family':<18}{'baseline':>10}{'per-family':>12}{'opt/target':>12}{'canonico':>12}{'opt-canon':>12}")
    print("  " + "-" * 100)

    sums = {"base": 0, "fam": 0, "opt_target": 0, "canon": 0, "opt_canon": 0}
    for t in per_target:
        labels = t["labels"]
        baseline = t["auc_vina_xgb"]

        w_fam = PER_FAMILY_WEIGHTS.get(t["family"], PER_FAMILY_WEIGHTS["default"])
        fam_scores = stack_score(t["vina_n"], t["xgb"], t["clgnn"],
                                 w_fam["vina"], w_fam["xgb"], w_fam["clgnn"])
        auc_fam = roc_auc_score(labels, fam_scores)

        # Optimo por target individual
        best = 0.0
        for w_v in np.arange(0, 1.01, 0.05):
            for w_x in np.arange(0, 1.01 - w_v, 0.05):
                w_c = 1.0 - w_v - w_x
                if w_c < 0: continue
                sc = stack_score(t["vina_n"], t["xgb"], t["clgnn"], w_v, w_x, w_c)
                auc_t = roc_auc_score(labels, sc)
                if auc_t > best:
                    best = auc_t
        auc_opt_target = best

        canon_scores = stack_score(t["vina_n"], t["xgb"], t["clgnn"],
                                  canonical["w_vina"], canonical["w_xgb"], canonical["w_clgnn"])
        auc_canon = roc_auc_score(labels, canon_scores)

        # Optimo: pesos del canonico pero excluyendo este target (LOO)
        # ya esta en canonical (no, no lo esta - hay que recalcular). Lo dejamos para Phase 2
        opt_v, opt_x, opt_c = 0.2, 0.4, 0.4
        opt_scores = stack_score(t["vina_n"], t["xgb"], t["clgnn"], opt_v, opt_x, opt_c)
        # este sera el optimo de 5HT1A aplicado a otros; lo marcamos pero NO es canonico
        # lo dejo informativo para ver cuanto se degrada vs per-target opt
        opt_canon = roc_auc_score(labels, opt_scores)

        sums["base"] += baseline
        sums["fam"] += auc_fam
        sums["opt_target"] += auc_opt_target
        sums["canon"] += auc_canon
        sums["opt_canon"] += opt_canon

        print(f"  {t['name']:<14}{t['family']:<18}{baseline:>10.4f}{auc_fam:>12.4f}{auc_opt_target:>12.4f}{auc_canon:>12.4f}{opt_canon:>12.4f}")

    n = len(per_target)
    print("  " + "-" * 100)
    print(f"  {'MEAN':<32}{sums['base']/n:>10.4f}{sums['fam']/n:>12.4f}{sums['opt_target']/n:>12.4f}{sums['canon']/n:>12.4f}{sums['opt_canon']/n:>12.4f}")

    # -------- 0.2 + 0.3: Cohen's d + Bootstrap CI del delta --------
    print("\n" + "=" * 110)
    print("  0.2+0.3 DELTA STACKING vs BASELINE (Vina+XGB): Cohen's d + Bootstrap CI 95%")
    print("=" * 110)
    print(f"\n  {'target':<14}{'AUC_base':>10}{'AUC_stack':>11}{'delta':>8}{'Cohen_d':>10}{'CI_low':>10}{'CI_high':>10}{'signif':>10}")
    print("  " + "-" * 90)

    n_boot = 2000
    bootstrap_data = []
    signif_count = 0
    for t in per_target:
        labels = t["labels"]
        w = canonical
        stack_scores = stack_score(t["vina_n"], t["xgb"], t["clgnn"],
                                   w["w_vina"], w["w_xgb"], w["w_clgnn"])

        boot_base = bootstrap_auc(t["vina_xgb"], labels, n_boot=n_boot, seed=42)
        boot_stack = bootstrap_auc(stack_scores, labels, n_boot=n_boot, seed=42)

        d_boots = boot_stack - boot_base
        d_mean = float(d_boots.mean())
        ci_low = float(np.percentile(d_boots, 2.5))
        ci_high = float(np.percentile(d_boots, 97.5))
        d_cohen = cohens_d(boot_stack, boot_base)
        signif = ci_low > 0
        if signif:
            signif_count += 1

        bootstrap_data.append({
            "target": t["name"],
            "auc_base": float(boot_base.mean()),
            "auc_stack": float(boot_stack.mean()),
            "delta": d_mean,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "cohens_d": d_cohen,
            "signif": signif,
        })
        signif_str = "YES" if signif else "NO"
        print(f"  {t['name']:<14}{boot_base.mean():>10.4f}{boot_stack.mean():>11.4f}{d_mean:>8.4f}{d_cohen:>10.3f}{ci_low:>10.4f}{ci_high:>10.4f}{signif_str:>10}")

    print("  " + "-" * 100)
    print(f"  >> Targets con delta significativo (CI 95% > 0): {signif_count} / {n}")
    if signif_count >= 5:
        print("     >> GATE: el stacking aporta signal en >=5/7 targets -se justifica el pipeline")
    elif signif_count >= 3:
        print("     >> GATE: delta positivo pero acotado -revisar family weights en Phase 2")
    else:
        print("     >> GATE: solo funciona en pocos targets -reformular claim antes de avanzar")

    # -------- Guardar todos los resultados --------
    out_dir = PROJECT_ROOT / "data" / "gnn_fixed" / "phase0"
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "grid_search_global.json", "w") as f:
        json.dump(grid[:50], f, indent=2)

    with open(out_dir / "bootstrap_delta_report.json", "w") as f:
        json.dump({
            "n_bootstrap": n_boot,
            "canonical_weights": canonical,
            "per_target": bootstrap_data,
            "signif_count": signif_count,
            "n_targets": n,
            "summary_verdict": (
                "STACKING_APORTE_FUERTE" if signif_count >= 5 else
                "STACKING_APORTE_MODERADO" if signif_count >= 3 else
                "STACKING_APORTE_DEBIL"
            ),
        }, f, indent=2)

    # Save raw arrays for Phase 2 (LOFO)
    raw = {}
    for t in per_target:
        raw[t["name"]] = {
            "family": t["family"],
            "labels": t["labels"].tolist(),
            "vina_n": t["vina_n"].tolist(),
            "xgb": t["xgb"].tolist(),
            "clgnn": t["clgnn"].tolist(),
            "vina_xgb": t["vina_xgb"].tolist(),
        }
    with open(out_dir / "raw_scores.pkl", "wb") as f:
        pickle.dump(raw, f)

    print(f"\n  Guardado en: {out_dir}")
    print(f"  - grid_search_global.json (top 50 ternas)")
    print(f"  - bootstrap_delta_report.json (Cohen's d + CI por target)")
    print(f"  - raw_scores.pkl (para Phase 2 LOFO)")
    print("\n" + "=" * 110)
    print("  PHASE 0 COMPLETADO")
    print("=" * 110)


if __name__ == "__main__":
    main()
