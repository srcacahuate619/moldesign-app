"""
stacking_ef.py — Stacking: Vina + XGBoost + CL-GNN + MM-GBSA.

Calcula EF@1%, EF@5%, EF@10%, ROC-AUC para cada combinación:

  1. Vina only (baseline)
  2. Vina + XGBoost (lo que tenemos hoy)
  3. CL-GNN only (contrastive)
  4. Vina + XGBoost + CL-GNN (propuesto)
  5. Equal weights (simple average de los 3)

Modalidades:
  --adaptive: activa stacking adaptativo por saturation de scorer.
    Si el mejor scorer individual (Vina o XGB) tiene AUC > threshold,
    el peso del CL-GNN se reduce o anula para evitar que aporte ruido
    sobre targets ya saturados.

Usage:
  python scripts/stacking_ef.py                                          # 5-HT1A
  python scripts/stacking_ef.py --target 3PP0                            # CDK2
  python scripts/stacking_ef.py --target 1HSG                            # HIV
  python scripts/stacking_ef.py --all                                     # todos
  python scripts/stacking_ef.py --all --optimize-weights                  # encuentra pesos óptimos
  python scripts/stacking_ef.py --all --adaptive                          # stacking adaptativo
  python scripts/stacking_ef.py --all --metastack                     # meta-stacking 3 scorers
  python scripts/stacking_ef.py --all --metastack4                     # meta-stacking 4 scorers (+GNN-D)
  python scripts/stacking_ef.py --all --adaptive --adaptive-thresh 0.93  # threshold personalizado
  python scripts/stacking_ef.py --all --adaptive --adaptive-thresh 0.93  # threshold personalizado
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
METASTACK_DIR = PROJECT_ROOT / "rescoring"

TARGET_CONFIGS = {
    "7E2Y": {"name": "5ht1a", "checkpoint": "gnn_v31/checkpoints/benchmark_checkpoint_5ht1a.json", "family": "gpcr"},
    "3PP0": {"name": "cdk2", "checkpoint": "gnn_v31/checkpoints/benchmark_checkpoint_cdk2.json", "family": "kinase"},
    "1HSG": {"name": "hiv_protease", "checkpoint": "gnn_v31/checkpoints/benchmark_checkpoint_hiv_protease.json", "family": "protease"},
    "3ERT": {"name": "er_alpha", "checkpoint": "gnn_v31/checkpoints/benchmark_checkpoint_er_alpha.json", "family": "nuclear_receptor"},
    "1F0R": {"name": "factor_xa", "checkpoint": "gnn_v31/checkpoints/benchmark_checkpoint_factor_xa.json", "family": "soluble_enzyme",
             "pdb": "3CYX"},
    "1BN1": {"name": "ca2", "checkpoint": "gnn_v31/checkpoints/benchmark_checkpoint_ca2.json", "family": "metaloenzyme",
             "pdb": "3DC3"},
    "1c4u": {"name": "thrombin", "checkpoint": "gnn_v31/checkpoints/benchmark_checkpoint_thrombin.json", "family": "soluble_enzyme"},
    "1XP0": {"name": "pde5", "checkpoint": "gnn_v31/checkpoints/benchmark_checkpoint_pde5.json", "family": "phosphodiesterase"},
}

STACKING_WEIGHTS = {
    "gpcr":               {"vina": 0.4, "prob": 0.4, "gnn": 0.0, "clgnn": 0.2},
    "kinase":             {"vina": 0.2, "prob": 0.8, "gnn": 0.0, "clgnn": 0.0},
    "protease":           {"vina": 0.2, "prob": 0.7, "gnn": 0.0, "clgnn": 0.1},
    "nuclear_receptor":   {"vina": 0.3, "prob": 0.5, "gnn": 0.0, "clgnn": 0.2},
    "soluble_enzyme":     {"vina": 0.3, "prob": 0.5, "gnn": 0.0, "clgnn": 0.2},
    "metaloenzyme":       {"vina": 0.0, "prob": 0.1, "gnn": 0.0, "clgnn": 0.9},
    "phosphodiesterase":  {"vina": 0.3, "prob": 0.5, "gnn": 0.0, "clgnn": 0.2},
    "default":            {"vina": 0.3, "prob": 0.5, "gnn": 0.0, "clgnn": 0.2},
}


def ef(scores, labels, pct):
    n = len(scores)
    n_act = sum(labels)
    if n_act == 0:
        return 1.0
    top_n = max(1, int(n * pct / 100))
    pairs = sorted(zip(scores, labels), key=lambda x: x[0], reverse=True)
    found = sum(1 for _, a in pairs[:top_n] if a)
    expected = n_act * top_n / n
    return round(found / expected, 2) if expected > 0 else 1.0


def _component(r, key):
    """Extrae un score numérico finito de un resultado, o None si está ausente.
    [A3] Sin defaults fabricados: None/NaN/bool → componente no disponible."""
    v = r.get(key)
    if v is None or isinstance(v, bool):
        return None
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return None
    return fv if math.isfinite(fv) else None


def composite_vina_xgb(r):
    """Vina + XGBoost composite (replicando score_with_classifier).
    [A3] Sin prob clasifiable → regresión pura con vina (no fabrica 0.5)."""
    vina = _component(r, "vina_score")
    if vina is None:
        return None
    vina_norm = min(1.0, abs(vina) / 12.0)
    prob = _component(r, "prob")
    if prob is not None and prob > 0.01:
        return round(prob * 0.70 + vina_norm * 0.30, 4)
    return round(vina_norm, 4)


def composite_stacking(r, w_vina=0.15, w_xgb=0.55, w_gnn=0.30, clgnn_key="clgnn_prob", w_gnn_d=0.0):
    """Stacking: Vina + XGBoost + CL-GNN + opcional GNN-D.
    [A3] Componentes ausentes (None/NaN) se excluyen y los pesos se
    re-normalizan sobre los disponibles. Sin componentes → None."""
    terms = []
    vina = _component(r, "vina_score")
    if vina is not None and w_vina > 0:
        terms.append((min(1.0, abs(vina) / 12.0), w_vina))
    xgb_prob = _component(r, "prob")
    if xgb_prob is not None and w_xgb > 0:
        terms.append((xgb_prob, w_xgb))
    gnn_prob = _component(r, clgnn_key)
    if gnn_prob is not None and w_gnn > 0:
        terms.append((gnn_prob, w_gnn))
    if w_gnn_d > 0:
        gnn_d_prob = _component(r, "gnn_d_prob")
        if gnn_d_prob is not None:
            terms.append((gnn_d_prob, w_gnn_d))
    total_w = sum(w for _, w in terms)
    if total_w <= 0:
        return None
    score = sum(v * w for v, w in terms) / total_w
    return round(score, 4)


def composite_stacking_molchamb(r, w_vina=0.15, w_xgb=0.45, w_gnn=0.25, w_molchamb=0.15):
    """Stacking: Vina + XGBoost + CL-GNN + MolChamb quantum score.
    [A3] Componentes ausentes (None/NaN) se excluyen y los pesos se
    re-normalizan sobre los disponibles. Sin componentes → None."""
    terms = []
    vina = _component(r, "vina_score")
    if vina is not None and w_vina > 0:
        terms.append((min(1.0, abs(vina) / 12.0), w_vina))
    xgb_prob = _component(r, "prob")
    if xgb_prob is not None and w_xgb > 0:
        terms.append((xgb_prob, w_xgb))
    gnn_prob = _component(r, "clgnn_prob")
    if gnn_prob is not None and w_gnn > 0:
        terms.append((gnn_prob, w_gnn))
    molchamb = _component(r, "molchamb_score")
    if molchamb is not None and w_molchamb > 0:
        terms.append((molchamb, w_molchamb))
    total_w = sum(w for _, w in terms)
    if total_w <= 0:
        return None
    score = sum(v * w for v, w in terms) / total_w
    return round(score, 4)


def compute_molchamb_scores(results: list[dict]):
    """Compute MolChamb quantum scores for all molecules and attach to results.
    [A3] Sin 0.5 fabricado: None si no hay smiles, el cálculo falla o devuelve
    un score no finito. El componente queda excluido del stacking."""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    try:
        from compute_quantum_features import compute_quantum_score
    except ImportError:
        print("  [WARN molchamb_unavailable] compute_quantum_features no importable; molchamb_score = None")
        for r in results:
            if "molchamb_score" not in r:
                r["molchamb_score"] = None
        return
    n_total = 0
    n_failed = 0
    for r in results:
        if "molchamb_score" in r:
            continue
        n_total += 1
        smi = r.get("smiles", "")
        if not smi:
            r["molchamb_score"] = None
            n_failed += 1
            print("  [WARN molchamb_missing] sin smiles; score=None")
            continue
        try:
            val = compute_quantum_score(smi)
            if val is None or not math.isfinite(float(val)):
                r["molchamb_score"] = None
                n_failed += 1
                print(f"  [WARN molchamb_missing] score no computable smiles={smi[:40]}")
            else:
                r["molchamb_score"] = float(val)
        except Exception as exc:
            r["molchamb_score"] = None
            n_failed += 1
            print(f"  [WARN molchamb_missing] {type(exc).__name__}: {str(exc)[:60]} smiles={smi[:40]}")
    if n_failed:
        print(f"  [WARN] MolChamb None en {n_failed}/{n_total} moléculas (re-normalización lo excluye)")


def optimize_weights(results, labels):
    """Grid search para encontrar los pesos óptimos del stacking."""
    from sklearn.metrics import roc_auc_score

    best_auc = 0.0
    best_w = None
    for w_g in np.arange(0.0, 0.61, 0.1):
        for w_v in np.arange(0.0, 0.41, 0.1):
            w_x = 1.0 - w_v - w_g
            if w_x < 0 or w_x > 1:
                continue
            scores = [composite_stacking(r, w_v, w_x, w_g) for r in results]
            pairs = [(s, l) for s, l in zip(scores, labels) if s is not None]
            if len(pairs) < 2:
                continue
            auc = roc_auc_score([l for _, l in pairs], [s for s, _ in pairs])
            if auc > best_auc:
                best_auc = auc
                best_w = (w_v, w_x, w_g)
    return best_w, best_auc


def adaptive_weights(results, labels, family_weights, thresh_auc=0.93):
    """
    Calcula pesos adaptativos por saturation de scorer.
    
    Si el mejor scorer individual (Vina o XGB) tiene AUC > thresh_auc,
    reduce el peso del CL-GNN proporcionalmente. La masa se reasigna al
    scorer con mayor AUC individual.
    
    Retorna: (w_vina, w_xgb, w_clgnn) normalizados
    """
    from sklearn.metrics import roc_auc_score

    vina_scores = np.array([abs(r["vina_score"]) for r in results])
    vina_norm = np.array([min(1.0, v / 12.0) for v in vina_scores])
    pairs = []
    for r, l in zip(results, labels):
        xp = _component(r, "prob")
        if xp is not None:
            pairs.append((min(1.0, abs(r["vina_score"]) / 12.0), xp, l))
    if len(pairs) < 2 or len({l for _, _, l in pairs}) < 2:
        bv = family_weights.get("vina", 0.15)
        bx = family_weights.get("prob", 0.55)
        bc = family_weights.get("clgnn", 0.30)
        total = bv + bx + bc
        return (bv / total, bx / total, bc / total, 1.0)
    vina_ok = np.array([vn for vn, _, _ in pairs])
    xgb_ok = np.array([xp for _, xp, _ in pairs])
    labels_ok = np.array([l for _, _, l in pairs])

    auc_v = roc_auc_score(labels_ok, vina_ok)
    auc_x = roc_auc_score(labels_ok, xgb_ok)
    max_pre_gnn = max(auc_v, auc_x)
    
    base_w = family_weights
    w_v = base_w.get("vina", 0.15)
    w_x = base_w.get("prob", 0.55)
    w_c = base_w.get("clgnn", 0.30)
    
    # Si satura, reducir peso GNN
    thresh_uncertain = thresh_auc - 0.10
    if max_pre_gnn >= thresh_auc:
        gnn_retention = 0.0  # GNN se apaga completamente
    elif max_pre_gnn >= thresh_uncertain:
        gnn_retention = (thresh_auc - max_pre_gnn) / (thresh_auc - thresh_uncertain)
    else:
        gnn_retention = 1.0  # GNN mantiene peso
    
    w_c_eff = w_c * gnn_retention
    
    # Reasignar masa liberada al mejor scorer individual
    if w_c_eff < w_c:
        extra = w_c - w_c_eff
        if auc_x >= auc_v:
            w_x += extra
        else:
            w_v += extra
    
    # Normalizar
    total = w_v + w_x + w_c_eff
    if total > 0:
        w_v, w_x, w_c_eff = w_v / total, w_x / total, w_c_eff / total
    
    return w_v, w_x, w_c_eff, gnn_retention


def run_target(target_id, optimize=False, adaptive=False, adaptive_thresh=0.93, metastack=False, metastack4=False):
    cfg = TARGET_CONFIGS[target_id]
    ck_path = DATA_DIR / cfg["checkpoint"]
    if not ck_path.exists():
        print(f"  [SKIP] No checkpoint for {target_id}")
        return

    with open(ck_path) as f:
        data = json.load(f)
    results = [r for r in data["results"] if r.get("vina_score") is not None]
    if not results:
        print(f"  [SKIP] No valid results for {target_id}")
        return

    family = cfg.get("family", "default")
    weights = STACKING_WEIGHTS.get(family, STACKING_WEIGHTS["default"])

    labels = [r["is_active"] for r in results]
    n_act = sum(labels)
    n_tot = len(labels)

    print(f"\n{'='*60}")
    display_id = cfg.get("pdb", target_id)
    print(f"  {cfg['name']} ({display_id}) — {family}")
    print(f"  N={n_tot} | Actives={n_act} | Decoys={n_tot-n_act} | Ratio=1:{max(1,(n_tot-n_act)//max(1,n_act))}")
    print(f"  Weights: {weights}")
    print(f"{'='*60}")

    vina_scores = [abs(r["vina_score"]) for r in results]
    xgb_scores = [r.get("prob") for r in results]
    gnn_scores = [r.get("clgnn_prob") for r in results]
    gnn_d_scores = [r.get("gnn_d_prob") for r in results]
    composite_xgb = [composite_vina_xgb(r) for r in results]

    # Per-family calibrated stacking
    cal_scores = [composite_stacking(r, weights["vina"], weights["prob"], weights["clgnn"]) for r in results]

    # Adaptive stacking (sigma)
    aw_v, aw_x, aw_c, gnn_ret = weights["vina"], weights["prob"], weights["clgnn"], 1.0
    if adaptive:
        aw_v, aw_x, aw_c, gnn_ret = adaptive_weights(
            results, labels, weights, thresh_auc=adaptive_thresh
        )
    ada_scores = [composite_stacking(r, aw_v, aw_x, aw_c) for r in results]

    # Metastack (adaptive weights from individual AUCs)
    meta_label = None
    meta_scores = None
    meta4_label = None
    meta4_scores = None
    if metastack:
        sys.path.insert(0, str(METASTACK_DIR))
        from gnn_v2.metastack import metastack_weights
        from sklearn.metrics import roc_auc_score
        m_pairs = [(min(1.0, abs(r["vina_score"]) / 12.0), r.get("prob"), r.get("clgnn_prob"), l)
                   for r, l in zip(results, labels)]
        m_pairs = [p for p in m_pairs if p[1] is not None and p[2] is not None]
        if len(m_pairs) >= 2 and len({p[3] for p in m_pairs}) >= 2:
            m_vina_n = np.array([p[0] for p in m_pairs])
            m_xgb = np.array([p[1] for p in m_pairs])
            m_clgnn = np.array([p[2] for p in m_pairs])
            labels_m = [p[3] for p in m_pairs]
            auc_v = float(roc_auc_score(labels_m, m_vina_n))
            auc_x = float(roc_auc_score(labels_m, m_xgb))
            auc_c = float(roc_auc_score(labels_m, m_clgnn))
            mw_v, mw_x, mw_c, meta_info = metastack_weights(auc_v, auc_x, auc_c, T=6.0, p=1.0)
            meta_scores = [composite_stacking(r, mw_v, mw_x, mw_c) for r in results]
            meta_label = f"Metastack ({mw_v:.2f},{mw_x:.2f},{mw_c:.2f})"

    # Metastack4 (4 scorers: +GNN-D)
    if metastack4:
        sys.path.insert(0, str(METASTACK_DIR))
        from gnn_v2.metastack import metastack_weights
        from sklearn.metrics import roc_auc_score
        # Filter valid gnn_d entries (presence check; no 0.5-sentinel)
        valid_gnnd = np.array([r.get("gnn_d_prob") is not None for r in results])
        n_valid = int(valid_gnnd.sum())
        if n_valid > 50:
            p4 = []
            for i, r in enumerate(results):
                if not valid_gnnd[i]:
                    continue
                p4.append((i, min(1.0, abs(r["vina_score"]) / 12.0), r.get("prob"),
                           r.get("clgnn_prob"), r.get("gnn_d_prob"), labels[i]))
            p4 = [x for x in p4 if x[2] is not None and x[3] is not None]
            if len(p4) >= 2 and len({x[5] for x in p4}) >= 2:
                m_vina_n = np.array([x[1] for x in p4])
                m_xgb = np.array([x[2] for x in p4])
                m_clgnn = np.array([x[3] for x in p4])
                m_gnnd = np.array([x[4] for x in p4])
                labels_v = [x[5] for x in p4]
                auc_v = float(roc_auc_score(labels_v, m_vina_n))
                auc_x = float(roc_auc_score(labels_v, m_xgb))
                auc_c = float(roc_auc_score(labels_v, m_clgnn))
                auc_d = float(roc_auc_score(labels_v, m_gnnd))
                w_list, meta4_info = metastack_weights([auc_v, auc_x, auc_c, auc_d], T=6.0, p=1.0)
                mw_v, mw_x, mw_c, mw_d = w_list
                meta4_scores = [composite_stacking(r, mw_v, mw_x, mw_c, w_gnn_d=mw_d) for r in results]
                meta4_label = (f"Metastack4 ({mw_v:.2f},{mw_x:.2f},{mw_c:.2f},{mw_d:.2f}) n_valid={n_valid}/{len(results)}")

    # MolChamb stacking
    compute_molchamb_scores(results)
    molchamb_w = {"w_vina": 0.15, "w_xgb": 0.4, "w_gnn": 0.3, "w_molchamb": 0.15}
    molchamb_scores = [composite_stacking_molchamb(r, **molchamb_w) for r in results]

    from sklearn.metrics import roc_auc_score, average_precision_score

    def print_metrics(scores, label, weights_str=""):
        valid = []
        for s, l in zip(scores, labels):
            if s is None:
                continue
            try:
                fs = float(s)
            except (TypeError, ValueError):
                continue
            if math.isnan(fs):
                continue
            valid.append((fs, l))
        if len(valid) < 2 or len({l for _, l in valid}) < 2:
            print(f"  {label:35s} — INSUFICIENTE ({len(valid)}/{len(scores)} scores válidos) {weights_str}")
            return
        ys = [s for s, _ in valid]
        lbl = [l for _, l in valid]
        auc = roc_auc_score(lbl, ys)
        prauc = average_precision_score(lbl, ys)
        ef1 = ef(ys, lbl, 1)
        ef5 = ef(ys, lbl, 5)
        ef10 = ef(ys, lbl, 10)
        verdict = "STRONG" if ef1 >= 5 else ("MODERATE" if ef1 >= 2 else "WEAK")
        print(f"  {label:35s} EF@1%={ef1:>6.2f}x  EF@5%={ef5:>5.2f}x  AUC={auc:.4f}  PR={prauc:.4f}  {weights_str}")

    print_metrics(vina_scores, "Vina only")
    print_metrics(gnn_scores, "CL-GNN only")
    print_metrics(xgb_scores, "XGBoost only")
    n_gnnd_valid = sum(1 for s in gnn_d_scores if s is not None)
    if n_gnnd_valid > 10:
        print_metrics(gnn_d_scores, f"GNN-D only (n={n_gnnd_valid})")
    print_metrics(composite_xgb, "Vina + XGBoost")
    print_metrics(cal_scores, f"Stacking ({family})", f"w={weights}")
    print_metrics(ada_scores, f"Stacking adaptive (sigma)", f"thresh={adaptive_thresh} gnn_ret={gnn_ret:.2f}")
    if metastack and meta_label:
        print_metrics(meta_scores, meta_label, f"auc_v={auc_v:.3f} auc_x={auc_x:.3f} auc_c={auc_c:.3f}")
    if metastack4 and meta4_label:
        print_metrics(meta4_scores, meta4_label, f"auc_v={auc_v:.3f} auc_x={auc_x:.3f} auc_c={auc_c:.3f} auc_d={auc_d:.3f}")
    print_metrics(molchamb_scores, f"Stacking + MolChamb", f"w={molchamb_w}")

    # Optimize weights if requested
    best_weights = {}
    if optimize:
        best_w, best_auc = optimize_weights(results, labels)
        if best_w is None:
            print(f"  {target_id}: optimize_weights sin combinación válida (sin scores)")
            return None
        opt_scores = [composite_stacking(r, *best_w) for r in results]
        w_v, w_x, w_g = best_w
        print_metrics(opt_scores, f"Stack optimized", f"w=({w_v:.1f},{w_x:.1f},{w_g:.1f})")
        best_weights[target_id] = {"vina": round(w_v, 2), "xgb": round(w_x, 2), "gnn": round(w_g, 2)}

    return best_weights


def save_weights_to_artifacts(all_weights: dict):
    """Save optimized stacking weights to artifacts for engine.py to use."""
    # Map PDB IDs to family names
    family_map = {"7E2Y": "gpcr", "3PP0": "kinase", "1HSG": "protease"}
    weights_by_family = {"default": {"vina": 0.3, "xgb": 0.5, "gnn": 0.2}}
    for pdb_id, w in all_weights.items():
        family = family_map.get(pdb_id, "default")
        weights_by_family[family] = w

    artifacts_dir = PROJECT_ROOT / "rescoring" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    with open(artifacts_dir / "stacking_weights.json", "w") as f:
        json.dump(weights_by_family, f, indent=2)
    print(f"\n  Weights saved: {artifacts_dir / 'stacking_weights.json'}")
    for fam, w in weights_by_family.items():
        print(f"    {fam}: w_vina={w['vina']} w_xgb={w['xgb']} w_gnn={w['gnn']}")


def main():
    parser = argparse.ArgumentParser(description="Stacking EF Benchmark")
    parser.add_argument("--target", type=str, default="7E2Y", choices=list(TARGET_CONFIGS.keys()) + [""])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--optimize-weights", action="store_true")
    parser.add_argument("--adaptive", action="store_true",
                        help="Usa stacking adaptativo: reduce peso GNN si scorer satura")
    parser.add_argument("--adaptive-thresh", type=float, default=0.93,
                        help="Threshold AUC para activar reduccion GNN en adaptive mode (default: 0.93)")
    parser.add_argument("--metastack", action="store_true",
                        help="Usa meta-stacking 3 scorers: pesos desde AUC individuales (T=6, p=1.0)")
    parser.add_argument("--metastack4", action="store_true",
                        help="Usa meta-stacking 4 scorers (+GNN-D)")
    args = parser.parse_args()

    print("=" * 60)
    print("  STACKING BENCHMARK — Vina + XGBoost + CL-GNN + GNN-D")
    if args.adaptive:
        print(f"  Modo: STACKING ADAPTATIVO (thresh={args.adaptive_thresh})")
    if args.metastack:
        print("  Modo: META-STACKING (3 scorers)")
    if args.metastack4:
        print("  Modo: META-STACKING 4 (vina+xgb+clgnn+gnnd)")
    print("=" * 60)

    all_weights = {}
    targets = [args.target] if not args.all else list(TARGET_CONFIGS.keys())
    for t in targets:
        w = run_target(t, optimize=args.optimize_weights,
                       adaptive=args.adaptive, adaptive_thresh=args.adaptive_thresh,
                       metastack=args.metastack, metastack4=args.metastack4)
        if w:
            all_weights.update(w)

    if args.optimize_weights and all_weights:
        save_weights_to_artifacts(all_weights)


if __name__ == "__main__":
    main()
