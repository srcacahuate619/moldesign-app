#!/usr/bin/env python3
"""
scripts/metastack_family_gated.py
=================================
Family-gated Metastack5+4 hybrid.

Strategy:
  - For metalloenzyme targets (family == "metaloenzyme"):
      use Metastack5 (vina + xgb + clgnn_a + gnn_d + molchamb)
  - For all other targets:
      use Metastack4 (vina + xgb + clgnn_a + gnn_d) -- IDENTICAL to existing

This guarantees ZERO regression on non-metal targets while enabling
MolChamb only where it adds value.

INPUTS:
  - data/molchamb_loto/checkpoints/benchmark_checkpoint_*.json
    (must have molchamb_score populated -- run molchamb_populate_checkpoints.py first)
  - data/gnn_fixed/phase0/loto_honest_report.json
    (for LOTO GNN-D AUCs)

OUTPUT:
  - data/molchamb_loto/metastack_family_gated_report.json
"""
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

CHECKPOINT_DIR = PROJECT_ROOT / "data" / "molchamb_loto" / "checkpoints"
OUTPUT_DIR = PROJECT_ROOT / "data" / "molchamb_loto"
LOTO_REPORT = PROJECT_ROOT / "data" / "gnn_fixed" / "phase0" / "loto_honest_report.json"

# Family mapping from stacking_ef.py TARGET_CONFIGS
TARGET_FAMILY = {
    "5ht1a":        "gpcr",
    "cdk2":         "kinase",
    "hiv_protease": "protease",
    "er_alpha":     "nuclear_receptor",
    "factor_xa":    "soluble_enzyme",
    "ca2":          "metaloenzyme",
    "thrombin":     "soluble_enzyme",
    "glp1r":        "gpcr",
}

TARGETS = ["5ht1a", "ca2", "cdk2", "er_alpha", "factor_xa", "hiv_protease", "thrombin"]


# ── Scoring functions ──

def score_vina(r):
    vina = abs(r.get("vina_score") or -5.0)
    return min(1.0, vina / 12.0)

def score_xgb(r):
    return r.get("prob", 0.0)

def score_clgnn_a(r):
    return r.get("clgnn_prob", 0.5)

def score_gnn_d(r):
    val = r.get("gnn_d_prob")
    if val is None or val == 0.5:
        return 0.5
    return val

def score_molchamb(r):
    val = r.get("molchamb_score")
    if val is None:
        return 0.5
    return float(val)

SCORERS_4 = [score_vina, score_xgb, score_clgnn_a, score_gnn_d]
SCORERS_5 = [score_vina, score_xgb, score_clgnn_a, score_gnn_d, score_molchamb]


# ── Softmax metastack weights ──

def softmax_weights(scores, T=6.0, p=1.0):
    scores = np.array(scores, dtype=float)
    powered = np.abs(scores) ** p
    powered = np.maximum(powered, 1e-12)
    scaled = powered / T
    exp_s = np.exp(scaled - np.max(scaled))
    return exp_s / exp_s.sum()

def metastack_weights(*args, T=6.0, p=1.0, saturation_thresh=0.96, hedge_thresh=0.65):
    aucs = np.array(args, dtype=float)
    n = len(aucs)
    if any(aucs > saturation_thresh):
        w = np.ones(n) * 0.05
        winner = int(np.argmax(aucs))
        w[winner] = 0.80
        return w
    elif all(aucs < hedge_thresh):
        return np.ones(n) / n
    else:
        return softmax_weights(aucs, T=T, p=p)


def composite_score(r, w, scorers):
    s = np.array([fn(r) for fn in scorers[:len(w)]])
    return float(np.dot(s, w))


def use_molchamb(target):
    """Family gate: ONLY activate MolChamb for metalloenzyme targets."""
    return TARGET_FAMILY.get(target, "default") == "metaloenzyme"


def evaluate_target_biased(target, indiv_aucs):
    """Returns (auc_m4, auc_m5_or_m4, weights, used_molchamb)."""
    ck_file = CHECKPOINT_DIR / f"benchmark_checkpoint_{target}.json"
    if not ck_file.exists():
        return None
    data = json.loads(ck_file.read_text())
    results = data.get("results", [])
    valid = [r for r in results if r.get("vina_score") is not None]
    if not valid:
        return None
    labels = [r["is_active"] for r in valid]
    if len(set(labels)) < 2:
        return None

    a = indiv_aucs[target]
    family = TARGET_FAMILY.get(target, "default")
    is_metal = use_molchamb(target)

    # Metastack4 (baseline -- always computed for reference)
    w4 = metastack_weights(a["auc_vina"], a["auc_xgb"], a["auc_clgnn_a"], a["auc_gnn_d"])
    comp4 = [composite_score(r, w4, SCORERS_4) for r in valid]
    auc4 = round(roc_auc_score(labels, comp4), 4)

    if is_metal:
        # Metalloenzyme: use Metastack5 (with MolChamb)
        w_active = metastack_weights(
            a["auc_vina"], a["auc_xgb"], a["auc_clgnn_a"], a["auc_gnn_d"], a["auc_molchamb"]
        )
        comp_active = [composite_score(r, w_active, SCORERS_5) for r in valid]
        auc_active = round(roc_auc_score(labels, comp_active), 4)
        used_molchamb = True
        w_active_report = [round(float(w), 3) for w in w_active]
    else:
        # Non-metal: revert to Metastack4 (IDENTICAL to existing pipeline)
        auc_active = auc4
        used_molchamb = False
        w_active_report = [round(float(w), 3) for w in w4]

    delta = round(auc_active - auc4, 4)
    return {
        "family": family,
        "is_metalloenzyme": is_metal,
        "used_molchamb": used_molchamb,
        "auc_metastack4": auc4,
        "auc_family_gated": auc_active,
        "delta_vs_m4": delta,
        "active_weights": w_active_report,
        "n": len(valid),
        "n_active": sum(labels),
    }


def evaluate_loto(target, indiv_aucs):
    """LOTO honest estimation -- AUC-weighted average (approximate, biased low)."""
    if not LOTO_REPORT.exists():
        return None
    loto_data = json.loads(LOTO_REPORT.read_text())
    loto_per_target = loto_data.get("loto_results", {})
    if target not in loto_per_target:
        return None
    lt = loto_per_target[target]

    auc_v = round(lt["auc_v"], 4)
    auc_x = round(lt["auc_x"], 4)
    auc_c = round(lt["auc_c"], 4)
    auc_d = round(lt["auc_d"], 4)
    auc_m3 = round(lt["auc_m3"], 4)
    auc_m4 = round(lt["auc_m4"], 4)
    auc_m = indiv_aucs.get(target, {}).get("auc_molchamb", 0.5)

    is_metal = use_molchamb(target)

    # Always compute M4 weights (using LOTO AUCs)
    w4 = metastack_weights(auc_v, auc_x, auc_c, auc_d)
    # AUC-weighted approximate M4 (for reference only)
    auc_m4_est = float(np.dot([auc_v, auc_x, auc_c, auc_d], w4))

    if is_metal:
        # Metalloenzyme: M5 weights with MolChamb
        w_active = metastack_weights(auc_v, auc_x, auc_c, auc_d, auc_m)
        auc_active_est = float(np.dot([auc_v, auc_x, auc_c, auc_d, auc_m], w_active))
        w_active_report = [round(float(w), 3) for w in w_active]
        used_molchamb = True
    else:
        # Non-metal: M4 (no change)
        auc_active_est = auc_m4_est
        w_active_report = [round(float(w), 3) for w in w4]
        used_molchamb = False

    return {
        "auc_vina": auc_v,
        "auc_xgb": auc_x,
        "auc_clgnn_a": auc_c,
        "auc_gnn_d_loto": auc_d,
        "auc_molchamb": auc_m,
        "auc_metastack4_exact": auc_m4,        # from LOTO report (exact)
        "auc_metastack4_est": round(auc_m4_est, 4),  # AUC-weighted (approx)
        "auc_family_gated_est": round(auc_active_est, 4),
        "used_molchamb": used_molchamb,
        "active_weights": w_active_report,
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step A: individual AUCs
    print("=" * 72)
    print("STEP A: Individual AUCs from checkpoints")
    print("=" * 72)
    indiv_aucs = {}
    for target in TARGETS:
        ck_file = CHECKPOINT_DIR / f"benchmark_checkpoint_{target}.json"
        if not ck_file.exists():
            continue
        data = json.loads(ck_file.read_text())
        results = data.get("results", [])
        valid = [r for r in results if r.get("vina_score") is not None]
        if not valid:
            continue
        labels = [r["is_active"] for r in valid]
        if len(set(labels)) < 2:
            continue

        def auc(scores):
            return round(roc_auc_score(labels, scores), 4)

        indiv_aucs[target] = {
            "n": len(valid),
            "auc_vina": auc([score_vina(r) for r in valid]),
            "auc_xgb": auc([score_xgb(r) for r in valid]),
            "auc_clgnn_a": auc([score_clgnn_a(r) for r in valid]),
            "auc_gnn_d": auc([score_gnn_d(r) for r in valid]),
            "auc_molchamb": auc([score_molchamb(r) for r in valid]),
        }
        a = indiv_aucs[target]
        fam = TARGET_FAMILY.get(target, "?")
        mc_flag = "MOLCHAMB-ON" if use_molchamb(target) else "m4-only   "
        print(f"  {target:15s} [{fam:18s}] {mc_flag}  "
              f"vina={a['auc_vina']:.3f} xgb={a['auc_xgb']:.3f} "
              f"clgnn={a['auc_clgnn_a']:.3f} gnn_d={a['auc_gnn_d']:.3f} "
              f"molch={a['auc_molchamb']:.3f}")

    # Step B: Biased family-gated evaluation
    print()
    print("=" * 72)
    print("STEP B: BIASED family-gated Metastack (exact per-molecule)")
    print("=" * 72)
    biased_results = {}
    for target in TARGETS:
        if target not in indiv_aucs:
            continue
        r = evaluate_target_biased(target, indiv_aucs)
        if r is None:
            continue
        biased_results[target] = r
        mark = "M5" if r["used_molchamb"] else "M4"
        delta = r["delta_vs_m4"]
        sign = "+" if delta > 0 else ("" if delta == 0 else "")
        print(f"  {target:15s} [{r['family']:18s}] {mark}  "
              f"m4={r['auc_metastack4']:.4f}  gated={r['auc_family_gated']:.4f}  "
              f"delta={sign}{delta:.4f}  w={r['active_weights']}")

    biased_m4_mean = np.mean([v["auc_metastack4"] for v in biased_results.values()])
    biased_gated_mean = np.mean([v["auc_family_gated"] for v in biased_results.values()])
    print()
    print(f"  BIASED MEAN:  M4={biased_m4_mean:.4f}  FamilyGated={biased_gated_mean:.4f}  "
          f"delta={biased_gated_mean - biased_m4_mean:+.4f}")

    # Step C: LOTO family-gated (approximate)
    print()
    print("=" * 72)
    print("STEP C: LOTO family-gated (AUC-weighted estimate -- biased low)")
    print("=" * 72)
    loto_results = {}
    for target in TARGETS:
        r = evaluate_loto(target, indiv_aucs)
        if r is None:
            continue
        loto_results[target] = r
        mark = "M5" if r["used_molchamb"] else "M4"
        print(f"  {target:15s} {mark}  "
              f"m4_exact={r['auc_metastack4_exact']:.4f}  "
              f"gated_est={r['auc_family_gated_est']:.4f}  "
              f"auc_m={r['auc_molchamb']:.3f}  w={r['active_weights']}")

    # For LOTO, the meaningful baseline is the EXACT M4 from the report
    # (not the AUC-weighted approximation which is biased low).
    loto_m4_exact_mean = np.mean([v["auc_metastack4_exact"] for v in loto_results.values()])
    # The gated estimate is ALSO AUC-weighted (biased low), so to compare fairly
    # we compare against the AUC-weighted M4 too.
    loto_m4_est_mean = np.mean([v["auc_metastack4_est"] for v in loto_results.values()])
    loto_gated_mean = np.mean([v["auc_family_gated_est"] for v in loto_results.values()])
    print()
    print(f"  LOTO MEAN (exact M4 from report):  {loto_m4_exact_mean:.4f}")
    print(f"  LOTO MEAN (AUC-weighted M4 est):   {loto_m4_est_mean:.4f}")
    print(f"  LOTO MEAN (family-gated est):      {loto_gated_mean:.4f}")
    print(f"  LOTO delta (gated - est_m4):        {loto_gated_mean - loto_m4_est_mean:+.4f}")
    print(f"  NOTE: AUC-weighted estimates are biased LOW. Exact LOTO M5 requires")
    print(f"        re-scoring each LOTO fold with GNN-D LOTO + MolChamb (~2-3h GPU).")

    # Save report
    report = {
        "strategy": "family_gated_metastack",
        "rule": "MolChamb active ONLY for family == 'metaloenzyme'",
        "individual_aucs": indiv_aucs,
        "biased_family_gated": biased_results,
        "biased_mean_metastack4": round(float(biased_m4_mean), 4),
        "biased_mean_family_gated": round(float(biased_gated_mean), 4),
        "biased_delta": round(float(biased_gated_mean - biased_m4_mean), 4),
        "loto_family_gated": loto_results,
        "loto_mean_metastack4_exact": round(float(loto_m4_exact_mean), 4),
        "loto_mean_metastack4_est": round(float(loto_m4_est_mean), 4),
        "loto_mean_family_gated_est": round(float(loto_gated_mean), 4),
        "loto_delta_est": round(float(loto_gated_mean - loto_m4_est_mean), 4),
        "loto_caveat": "AUC-weighted estimates are biased low -- exact LOTO M5 requires per-molecule re-scoring",
    }
    out_path = OUTPUT_DIR / "metastack_family_gated_report.json"
    out_path.write_text(json.dumps(report, indent=2))
    print()
    print(f"Report saved: {out_path}")

    # Final summary
    print()
    print("=" * 72)
    print("FAMILY-GATED SUMMARY")
    print("=" * 72)
    print(f"  BIASED:  M4 mean = {biased_m4_mean:.4f}")
    print(f"           Family-gated mean = {biased_gated_mean:.4f}")
    print(f"           Delta = {biased_gated_mean - biased_m4_mean:+.4f}")
    print()
    print(f"  TARGET-BY-TARGET (biased, exact):")
    for t, r in biased_results.items():
        mark = " [MOLCHAMB-ON]" if r["used_molchamb"] else " [m4-only, no regression]"
        print(f"    {t:15s} M4={r['auc_metastack4']:.4f} gated={r['auc_family_gated']:.4f} "
              f"delta={r['delta_vs_m4']:+.4f}{mark}")


if __name__ == "__main__":
    main()
