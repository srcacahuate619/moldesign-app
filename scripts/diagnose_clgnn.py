"""
scripts/diagnose_clgnn.py — CL-GNN / GNN-v3 signal diagnostic (Bucket C, track C2).

Read-only. No modifica artifacts. Solo lee los checkpoints de 5HT1A / CDK2
y responde las Hipótesis A/B/C de docs/23_BUCKET_C_RESEARCH_TRACK.md §3.

Hipótesis A — CL-GNN comparte encoder 18-dim con GNN-v2 -> ruido / no discrimina
Hipótesis B — CL-GNN fue retrained 38-dim pero igual degenera
Hipótesis C — hay signal pero stacking la anula (bug en stacking_ef.py)

Métricas por checkpoint:
  - N (actives/decoys/ratio)
  - Distribución de clgnn_prob / gnn_prob (mean, std, min, max, n_unique)
  - Detección de silent-fail: % mols con prob == 0.5 (default)
  - Pearson y Spearman corr(prob, is_active) — ¿discrimina?
  - Rank corr(clgnn_prob, vina_score), corr(clgnn_prob, xgb_prob) — ¿orto?
  - AUC local de cada scorer individual (vina, xgb_prob, clgnn_prob, gnn_prob)
  - AUC del stacking actual (según stacking_weights.json)
  - Diferentes ensemble cuts: Vina+XGB, Vina+XGB+CLGNN, Vina+XGB+GNN, all four

Output:
  stdout + JSON en data/gnn_v31/checkpoints/diagnose_clgnn_report.json

Uso:
  python scripts/diagnose_clgnn.py
  python scripts/diagnose_clgnn.py --targets 5ht1a,cdk2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import roc_auc_score


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CKPT_DIR = PROJECT_ROOT / "data" / "gnn_v31" / "checkpoints"
WEIGHTS_FILE = PROJECT_ROOT / "rescoring" / "artifacts" / "stacking_weights.json"
OUT_FILE = CKPT_DIR / "diagnose_clgnn_report.json"

DEFAULT_TARGETS = ["5ht1a", "cdk2", "er_alpha", "factor_xa", "hiv_protease"]


# ── Utilidades ──────────────────────────────────────────────────────────────

def _safe_corr(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Pearson + Spearman con n>2 y varianza != 0. Si no, devuelve NaN."""
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan"), float("nan")
    r_p, _ = pearsonr(x, y)
    r_s, _ = spearmanr(x, y)
    return float(r_p), float(r_s)


def _auc(scores: np.ndarray, y: np.ndarray) -> float:
    """AUC-ROC. NaN si no hay dos clases."""
    if len(np.unique(y)) < 2:
        return float("nan")
    try:
        return float(roc_auc_score(y, scores))
    except Exception:
        return float("nan")


def _pct_nan(arr: np.ndarray) -> float:
    """Porcentaje de NaN (valores None serializados) en el arreglo."""
    if arr.size == 0:
        return 0.0
    return float(100 * np.mean(np.isnan(arr)))


def _describe(arr: np.ndarray) -> dict[str, float | int]:
    return {
        "n": int(len(arr)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "n_unique": int(len(np.unique(arr))),
        "pct_eq_0_5": float(100 * np.mean(np.isclose(arr, 0.5))),
    }


def _stack(scores_dict: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray:
    """Stacking lineal normalizado. faltantes weighting -> 0.
    scores_dict: {scorer_name: np.array}. weights: {scorer_name: float}.
    Solo scorers que aparezcan AMBOS en scores_dict y en weights se combinan.
    """
    used = {k: v for k, v in scores_dict.items() if k in weights and weights[k] > 0}
    if not used:
        return np.zeros_like(next(iter(scores_dict.values())))
    # rank-normalize a [0,1] para combinar escalas distintas
    ranks = {}
    for k, v in used.items():
        order = np.argsort(v)
        ranks[k] = order.argsort() / max(len(v) - 1, 1)
    total_w = sum(weights[k] for k in ranks)
    stacked = np.zeros_like(next(iter(ranks.values())))
    for k, r in ranks.items():
        stacked += (weights[k] / total_w) * r
    return stacked


# ── Per-target diagnostic ───────────────────────────────────────────────────

def diagnose_target(target: str) -> dict[str, Any]:
    path = CKPT_DIR / f"benchmark_checkpoint_{target}.json"
    if not path.exists():
        return {"target": target, "error": f"checkpoint no existe: {path}"}

    with open(path) as f:
        d = json.load(f)
    results = d["results"]

    # Extraer arreglos
    vina = np.array([r.get("vina_score", np.nan) for r in results], dtype=float)
    xgb = np.array(
        [r.get("prob", np.nan) for r in results], dtype=float
    )
    clgnn = np.array(
        [r.get("clgnn_prob", np.nan) for r in results], dtype=float
    )
    gnn = np.array(
        [r.get("gnn_prob", np.nan) for r in results], dtype=float
    )
    gnn_d = np.array(
        [r.get("gnn_d_prob", np.nan) for r in results], dtype=float
    )
    clgnn_std = np.array(
        [r.get("clgnn_std", np.nan) for r in results], dtype=float
    )
    y = np.array([int(bool(r.get("is_active", 0))) for r in results], dtype=int)

    # Limpieza: NaN -> 0.5 para probs (solo para estadística descriptiva;
    # la ausencia real se reporta aparte como pct_missing)
    def fill(arr, val):
        return np.where(np.isnan(arr), val, arr)

    clgnn_c = fill(clgnn, 0.5)
    gnn_c = fill(gnn, 0.5)
    gnn_d_c = fill(gnn_d, 0.5)
    xgb_c = fill(xgb, 0.5)
    # vina: invertir signo para que "más negativo = más afín" -> "mayor score = más activo"
    vina_c = fill(vina, 0.0)

    n = len(y)
    n_act = int(y.sum())
    n_dec = n - n_act

    # Distribuciones
    dist = {
        "clgnn_prob": _describe(clgnn_c),
        "gnn_prob": _describe(gnn_c),
        "gnn_d_prob": _describe(gnn_d_c),
        "xgb_prob": _describe(xgb_c),
        "vina_score": _describe(vina_c),
        "clgnn_std": _describe(clgnn_std),
    }
    # [A3] Métricas de ausencia real (None → NaN): silent-fail ya NO es solo 0.5
    for key, raw in (("clgnn_prob", clgnn), ("gnn_prob", gnn), ("gnn_d_prob", gnn_d), ("xgb_prob", xgb)):
        dist[key]["n_missing"] = int(np.sum(np.isnan(raw)))
        dist[key]["pct_missing"] = _pct_nan(raw)

    # Correlación con is_active (¿discrimina?)
    corr_act = {
        "vina": _safe_corr(-vina_c, y),       # signo invertido: -vina es proporcional a affinity
        "xgb": _safe_corr(xgb_c, y),
        "clgnn": _safe_corr(clgnn_c, y),
        "gnn": _safe_corr(gnn_c, y),
        "gnn_d": _safe_corr(gnn_d_c, y),
    }

    # Correlación cruzada (¿ortogonalidad?)
    # Usar vina directa (no signo-invertida) — la ortogonalidad no depende del signo
    corr_cross = {
        "clgnn_vs_vina": _safe_corr(clgnn_c, vina_c),
        "clgnn_vs_xgb": _safe_corr(clgnn_c, xgb_c),
        "clgnn_vs_gnn": _safe_corr(clgnn_c, gnn_c),
        "gnn_vs_vina": _safe_corr(gnn_c, vina_c),
        "gnn_vs_xgb": _safe_corr(gnn_c, xgb_c),
        "gnn_vs_clgnn": _safe_corr(gnn_c, clgnn_c),
    }

    # AUC individual
    auc_individual = {
        "vina": _auc(-vina_c, y),       # más negativo = más afín = más alto en ranking
        "xgb": _auc(xgb_c, y),
        "clgnn": _auc(clgnn_c, y),
        "gnn": _auc(gnn_c, y),
        "gnn_d": _auc(gnn_d_c, y),
    }

    # Pesos de stacking
    weights = {}
    if WEIGHTS_FILE.exists():
        with open(WEIGHTS_FILE) as f:
            w_all = json.load(f)
        # Heuristic: usar 'lofo_canonical' (default non-metal) para no-metal targets.
        # Si target es metaloenzyme, usarían 'metaloenzyme'. Por simplicidad, reporto ambos.
        # Mapeo de nombres: stacking_weights usa "vina", "xgb", "gnn", "clgnn".
        # En el checkpoint tenemos "vina", "prob"(=xgb), "gnn_prob", "clgnn_prob".
        weights_default = w_all.get("lofo_canonical", {})
        weights_met = w_all.get("metaloenzyme", {})
        weights_gpcr = w_all.get("gpcr", {})
    else:
        weights_default, weights_met, weights_gpcr = {}, {}, {}

    # ----- M4 canonical (no-metal): vina + xgb + gnn + clgnn -----
    scores_m4 = {
        "vina": -vina_c,
        "xgb": xgb_c,
        "gnn": gnn_c,
        "clgnn": clgnn_c,
    }
    stacking_cuts = {}

    # Vina+XGB solos (paper claim)
    stacking_cuts["vina_xgb_only"] = _auc(
        _stack(scores_m4, {"vina": 0.5, "xgb": 0.5, "gnn": 0, "clgnn": 0}), y
    )
    # M4 con weights lofo_canonical
    stacking_cuts["m4_lofo_canonical"] = _auc(_stack(scores_m4, weights_default), y)
    # M4 sin CL-GNN
    w_no_clgnn = {k: v for k, v in weights_default.items() if k != "clgnn"}
    stacking_cuts["m4_no_clgnn"] = _auc(_stack(scores_m4, w_no_clgnn), y)
    # M4 solo CL-GNN (no-paper, sanity check)
    w_clgnn_only = {"vina": 0, "xgb": 0, "gnn": 0, "clgnn": 1.0}
    stacking_cuts["clgnn_only"] = _auc(_stack(scores_m4, w_clgnn_only), y)
    # GPCR config (Vina+XGB+GNN, sin clgnn)
    stacking_cuts["gpcr_config"] = _auc(_stack(scores_m4, weights_gpcr), y)

    return {
        "target": target,
        "checkpoint_path": str(path),
        "n_total": n,
        "n_actives": n_act,
        "n_decoys": n_dec,
        "active_ratio": n_act / n if n else 0,
        "distributions": dist,
        "corr_with_active": corr_act,
        "cross_correlations": corr_cross,
        "auc_individual": auc_individual,
        "stacking_cuts": stacking_cuts,
        "stacking_weights_used": {
            "lofo_canonical": weights_default,
            "metaloenzyme": weights_met,
            "gpcr": weights_gpcr,
        },
        "silent_fail_pct": {
            "clgnn": dist["clgnn_prob"]["pct_eq_0_5"] + dist["clgnn_prob"]["pct_missing"],
            "gnn": dist["gnn_prob"]["pct_eq_0_5"] + dist["gnn_prob"]["pct_missing"],
        },
        "verdict": _verdict(corr_act, corr_cross, dist, auc_individual, stacking_cuts),
    }


def _verdict(
    corr_act: dict, corr_cross: dict, dist: dict,
    auc: dict, stacking: dict
) -> dict[str, Any]:
    """Devuelve el diagnóstico de las 3 hipótesis A/B/C."""
    c_clgnn = corr_act["clgnn"][0]    # Pearson clgnn vs active
    s_clgnn = corr_act["clgnn"][1]    # Spearman clgnn vs active
    silent_clgnn = dist["clgnn_prob"]["pct_eq_0_5"] + dist["clgnn_prob"]["pct_missing"]
    n_unique_clgnn = dist["clgnn_prob"]["n_unique"]
    std_clgnn = dist["clgnn_prob"]["std"]

    hipothesis = ""
    if silent_clgnn > 95:
        hipothesis = "SILENT_FAIL (>=95% prob=0.5) -> modelo/array roto en load"
    elif abs(c_clgnn) < 0.05 and std_clgnn > 0.01:
        hipothesis = "A/B (ruido puro: alta var, baja corr con active) -> encoder in_proj mismatch heredado de GNN-v2 (Bug B)"
    elif abs(c_clgnn) > 0.2 and auc["clgnn"] > 0.5:
        hipothesis = "C (signal existe, steaking la aplana) -> bug en stacking_ef.py / pesos desoptimizados"
    elif abs(c_clgnn) > 0.05 and abs(corr_cross["clgnn_vs_vina"][0]) > 0.8:
        hipothesis = "DEGEN_CON_VINA (CL-GNN collinear con Vina -> no aporta signal independiente)"
    else:
        hipothesis = "INCONCLUSO (corr media, sin collinealidad ni signal fuerte)"

    delta_clgnn = stacking.get("m4_lofo_canonical", float("nan")) - \
                  stacking.get("m4_no_clgnn", float("nan"))

    return {
        "hipothesis": hipothesis,
        "clgnn_discrimina": abs(c_clgnn) > 0.1,
        "clgnn_ortogonal_a_vina": abs(corr_cross["clgnn_vs_vina"][0]) < 0.5,
        "clgnn_ortogonal_a_xgb": abs(corr_cross["clgnn_vs_xgb"][0]) < 0.5,
        "auc_delta_m4_with_vs_without_clgnn": float(delta_clgnn)
            if not np.isnan(delta_clgnn) else None,
        "n_unique_clgnn_probs": n_unique_clgnn,
        "clgnn_silent_fail_pct": silent_clgnn,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--targets",
        default=",".join(DEFAULT_TARGETS),
        help="CSV de targets (default: %(default)s)",
    )
    ap.add_argument("--json", default=str(OUT_FILE), help="output JSON path")
    args = ap.parse_args()

    targets = [t.strip().lower() for t in args.targets.split(",") if t.strip()]

    print(f"\n{'='*70}")
    print(f"CL-GNN / GNN-v3 DIAGNOSTIC — Bucket C track C2")
    print(f"{'='*70}\n")

    full = {
        "script": "scripts/diagnose_clgnn.py",
        "weights_file": str(WEIGHTS_FILE),
        "checkpoint_dir": str(CKPT_DIR),
        "targets": {},
    }

    for t in targets:
        print(f"--- {t.upper()} ---")
        r = diagnose_target(t)
        full["targets"][t] = r
        if "error" in r:
            print(f"  ⚠ {r['error']}\n")
            continue

        n = r["n_total"]
        na = r["n_actives"]
        print(f"  N={n}  actives={na}  ratio=1:{(n-na)//max(na,1)}")
        print()
        print(f"  DISTRIBUTION (clgnn_prob, gnn_prob, xgb_prob, vina):")
        for k in ("clgnn_prob", "gnn_prob", "xgb_prob", "vina_score"):
            dd = r["distributions"][k]
            print(
                f"    {k:14s} mean={dd['mean']:.4f} std={dd['std']:.4f} "
                f"unique={dd['n_unique']:5d} %eq0.5={dd['pct_eq_0_5']:5.1f} "
                f"%missing={dd.get('pct_missing', 0.0):5.1f}"
            )
        print()
        print(f"  CORR WITH ACTIVE (Pearson, Spearman):")
        for k, v in r["corr_with_active"].items():
            pp = v[0] if not np.isnan(v[0]) else 0.0
            ss = v[1] if not np.isnan(v[1]) else 0.0
            print(f"    {k:7s} rho={pp:+.4f}  spearman={ss:+.4f}")
        print()
        print(f"  CROSS-CORR:")
        for k, v in r["cross_correlations"].items():
            pp = v[0] if not np.isnan(v[0]) else 0.0
            print(f"    {k:18s} rho={pp:+.4f}")
        print()
        print(f"  AUC INDIVIDUAL:")
        for k, v in r["auc_individual"].items():
            vv = v if not np.isnan(v) else 0.0
            print(f"    {k:7s} AUC={vv:.4f}")
        print()
        print(f"  STACKING CUTS (AUC):")
        for k, v in r["stacking_cuts"].items():
            vv = v if not np.isnan(v) else 0.0
            print(f"    {k:22s} AUC={vv:.4f}")
        print()
        v = r["verdict"]
        print(f"  >> VERDICTO: {v['hipothesis']}")
        print(f"     discrimina={v['clgnn_discrimina']}  "
              f"ortogonal_a_vina={v['clgnn_ortogonal_a_vina']}  "
              f"ortogonal_a_xgb={v['clgnn_ortogonal_a_xgb']}")
        print(f"     delta_AUC (M4 con CL-GNN - sin CL-GNN) = "
              f"{v['auc_delta_m4_with_vs_without_clgnn']}")
        print()

    out_path = Path(args.json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(full, f, indent=2, default=str)
    print(f"JSON full: {out_path}\n")


if __name__ == "__main__":
    main()
