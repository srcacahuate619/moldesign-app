#!/usr/bin/env python3
"""
scripts/metastack5_loto_eval.py
================================
Evaluate Metastack5 (vina + xgb + clgnn_a + gnn_d + molchamb) LOTO.

PREREQUISITE:
  python scripts/molchamb_populate_checkpoints.py
  (populates data/molchamb_loto/checkpoints/ with molchamb_score)

SAFETY: Read-only. Never modifies checkpoints or existing reports.
OUTPUT: data/molchamb_loto/metastack5_report.json

METHODOLOGY:
  - MolChamb is ligand-only (no protein dependency), so its scores are
    the same for all LOTO folds. Only GNN-D scores change between folds.
  - For "biased" comparison: full GNN-D scores from checkpoints.
    We evaluate Metastack5 on the full (biased) set first.
  - For "honest" LOTO comparison: GNN-D LOTO AUCs from
    loto_honest_report.json + MolChamb AUC computed here from checkpoints.
    Metastack5 weights computed from the LOTO AUCs.
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

TARGETS = ["5ht1a", "ca2", "cdk2", "er_alpha", "factor_xa", "hiv_protease", "thrombin"]

# ── Scoring utils ──

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

# ── Compute composite ──

SCORERS = [score_vina, score_xgb, score_clgnn_a, score_gnn_d, score_molchamb]

def composite_score(r, w):
    s = np.array([fn(r) for fn in SCORERS[:len(w)]])
    return float(np.dot(s, w))

# ── Pe-target evaluation ──

def evaluate_target(results, weights):
    labels = [r["is_active"] for r in results]
    comp = [composite_score(r, weights) for r in results]
    if len(set(labels)) > 1:
        auc = round(roc_auc_score(labels, comp), 4)
    else:
        auc = 0.5
    return auc

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ──
    # (A) Compute MolChamb individual AUCs from checkpoints (biased, full set)
    # ──
    print("=" * 70)
    print("STEP A: Computing MolChamb & individual AUCs from checkpoints")
    print("=" * 70)

    indiv_aucs = {}
    for target in TARGETS:
        ck_file = CHECKPOINT_DIR / f"benchmark_checkpoint_{target}.json"
        if not ck_file.exists():
            print(f"  [SKIP] {target}: checkpoint not found")
            continue
        data = json.loads(ck_file.read_text())
        results = data.get("results", [])
        valid = [r for r in results if r.get("vina_score") is not None]
        if not valid:
            continue
        labels = [r["is_active"] for r in valid]

        v_scores = [score_vina(r) for r in valid]
        x_scores = [score_xgb(r) for r in valid]
        c_scores = [score_clgnn_a(r) for r in valid]
        d_scores = [score_gnn_d(r) for r in valid]
        m_scores = [score_molchamb(r) for r in valid]

        def auc(scores, lbls):
            if len(set(lbls)) > 1:
                return round(roc_auc_score(lbls, scores), 4)
            return 0.5

        indiv_aucs[target] = {
            "n": len(valid),
            "n_active": sum(labels),
            "auc_vina": auc(v_scores, labels),
            "auc_xgb": auc(x_scores, labels),
            "auc_clgnn_a": auc(c_scores, labels),
            "auc_gnn_d": auc(d_scores, labels),
            "auc_molchamb": auc(m_scores, labels),
        }
        print(f"  {target:15s} n={len(valid):5d}  vina={indiv_aucs[target]['auc_vina']:.4f}  "
              f"xgb={indiv_aucs[target]['auc_xgb']:.4f}  "
              f"clgnn={indiv_aucs[target]['auc_clgnn_a']:.4f}  "
              f"gnn_d={indiv_aucs[target]['auc_gnn_d']:.4f}  "
              f"molchamb={indiv_aucs[target]['auc_molchamb']:.4f}")

    # ──
    # (B) BIASED: Metastack5 on full checkpoints (compare to Metastack4)
    # ──
    print()
    print("=" * 70)
    print("STEP B: Biased Metastack5 evaluation (full GNN-D scores)")
    print("=" * 70)

    biased_results = {}
    for target in TARGETS:
        ck_file = CHECKPOINT_DIR / f"benchmark_checkpoint_{target}.json"
        if not ck_file.exists() or target not in indiv_aucs:
            continue
        data = json.loads(ck_file.read_text())
        results = data.get("results", [])
        valid = [r for r in results if r.get("vina_score") is not None]
        labels = [r["is_active"] for r in valid]

        a = indiv_aucs[target]

        # Metastack4 weights (vina, xgb, clgnn_a, gnn_d)
        w4 = metastack_weights(a["auc_vina"], a["auc_xgb"], a["auc_clgnn_a"], a["auc_gnn_d"])
        # Metastack5 weights (vina, xgb, clgnn_a, gnn_d, molchamb)
        w5 = metastack_weights(a["auc_vina"], a["auc_xgb"], a["auc_clgnn_a"], a["auc_gnn_d"], a["auc_molchamb"])

        comp4 = [composite_score(r, w4) for r in valid]  # same as m4, just using generic fn
        comp5 = [composite_score(r, w5) for r in valid]

        if len(set(labels)) > 1:
            auc4 = round(roc_auc_score(labels, comp4), 4)
            auc5 = round(roc_auc_score(labels, comp5), 4)
        else:
            auc4 = auc5 = 0.5

        delta = round(auc5 - auc4, 4)

        biased_results[target] = {
            "auc_metastack4": auc4,
            "auc_metastack5": auc5,
            "delta": delta,
            "metastack5_weights": [round(float(w), 3) for w in w5],
            "metastack4_weights": [round(float(w), 3) for w in w4],
        }
        arrow = "UP" if delta > 0 else ("DN" if delta < 0 else "=")
        print(f"  {target:15s}  m4={auc4:.4f}  m5={auc5:.4f}  delta={delta:+.4f} {arrow}  "
              f"w5={[round(float(w),2) for w in w5]}")

    biased_mean_m4 = np.mean([v["auc_metastack4"] for v in biased_results.values()])
    biased_mean_m5 = np.mean([v["auc_metastack5"] for v in biased_results.values()])
    print()
    print(f"  BIASED MEAN:  m4={biased_mean_m4:.4f}  m5={biased_mean_m5:.4f}  "
          f"delta={biased_mean_m5 - biased_mean_m4:+.4f}")

    # ──
    # (C) LOTO HONEST: Metastack5 using LOT GNN-D AUCs + MolChamb AUCs from checkpoints
    # ──
    print()
    print("=" * 70)
    print("STEP C: LOTO Honest Metastack5 (GNN-D LOTO AUCs from report)")
    print("=" * 70)

    if not LOTO_REPORT.exists():
        print(f"  [SKIP] {LOTO_REPORT} not found")
        loto_results = {}
    else:
        loto_data = json.loads(LOTO_REPORT.read_text())
        loto_per_target = loto_data.get("loto_results", {})

        loto_results = {}
        for target in TARGETS:
            if target not in loto_per_target:
                print(f"  [SKIP] {target}: no loto data")
                continue
            lt = loto_per_target[target]

            # LOTO individual AUCs from report
            auc_v = round(lt["auc_v"], 4)
            auc_x = round(lt["auc_x"], 4)
            auc_c = round(lt["auc_c"], 4)
            auc_d = round(lt["auc_d"], 4)
            auc_m3 = round(lt["auc_m3"], 4)
            auc_m4 = round(lt["auc_m4"], 4)

            # MolChamb AUC from checkpoint (MolChamb is ligand-only, no LOTO fold dependency!)
            auc_m = indiv_aucs.get(target, {}).get("auc_molchamb", 0.5)

            # Metastack5 weights from LOTO AUCs
            w5 = metastack_weights(auc_v, auc_x, auc_c, auc_d, auc_m)

            # Estimate Metastack5 AUC
            # We use the LOTO individual AUCs + the composite formula
            # For a weighted average of scores, the AUC of the weighted composite
            # is APPROXIMATELY the weighted average of individual AUCs, but not exactly.
            # We need per-molecule scores.
            #
            # Since we don't have LOTO per-molecule GNN-D scores, we approximate:
            # The softmax-metastack produces a convex combination of the individual
            # score vectors. The AUC of this combination is usually close to the
            # AUC-based weighted prediction, especially when correlations are low.
            #
            # Let's estimate using the weighted average formula:
            auc_m5_est = round(np.dot([auc_v, auc_x, auc_c, auc_d, auc_m], w5), 4)

            loto_results[target] = {
                "auc_vina": auc_v,
                "auc_xgb": auc_x,
                "auc_clgnn_a": auc_c,
                "auc_gnn_d_loto": auc_d,
                "auc_molchamb": auc_m,
                "auc_metastack3": auc_m3,
                "auc_metastack4": auc_m4,
                "auc_metastack5_est": auc_m5_est,
                "metastack5_weights": [round(float(w), 3) for w in w5],
            }
            delta = round(auc_m5_est - auc_m4, 4)
            arrow = "UP" if delta > 0 else ("DN" if delta < 0 else "=")
            print(f"  {target:15s}  m4={auc_m4:.4f}  m5_est={auc_m5_est:.4f}  "
                  f"delta={delta:+.4f} {arrow}  w5={[round(float(w),2) for w in w5]} "
                  f"[d={auc_d:.3f} m={auc_m:.3f}]")

        if loto_results:
            loto_mean_m4 = np.mean([v["auc_metastack4"] for v in loto_results.values()])
            loto_mean_m5 = np.mean([v["auc_metastack5_est"] for v in loto_results.values()])
            print()
            print(f"  LOTO MEAN:  m4={loto_mean_m4:.4f}  m5_est={loto_mean_m5:.4f}  "
                  f"delta={loto_mean_m5 - loto_mean_m4:+.4f}")

    # ──
    # (D) BIASED per-molecule Metastack5 (compute exact AUC from composites)
    # ──
    print()
    print("=" * 70)
    print("STEP D: Biased Exact Metastack5 per-molecule AUC (full checkpoints)")
    print("=" * 70)

    exact_biased = {}
    for target in TARGETS:
        ck_file = CHECKPOINT_DIR / f"benchmark_checkpoint_{target}.json"
        if not ck_file.exists() or target not in indiv_aucs:
            continue
        data = json.loads(ck_file.read_text())
        results = data.get("results", [])
        valid = [r for r in results if r.get("vina_score") is not None]
        if not valid:
            continue
        labels = [r["is_active"] for r in valid]
        a = indiv_aucs[target]

        # Metastack4 exact
        w4 = metastack_weights(a["auc_vina"], a["auc_xgb"], a["auc_clgnn_a"], a["auc_gnn_d"])
        comp4 = [composite_score(r, w4) for r in valid]

        # Metastack5 exact
        w5 = metastack_weights(a["auc_vina"], a["auc_xgb"], a["auc_clgnn_a"], a["auc_gnn_d"], a["auc_molchamb"])
        comp5 = [composite_score(r, w5) for r in valid]

        def compute_auc(scores, lbls):
            if len(set(lbls)) > 1:
                return round(roc_auc_score(lbls, scores), 4)
            return 0.5

        exact_biased[target] = {
            "auc_metastack4": compute_auc(comp4, labels),
            "auc_metastack5": compute_auc(comp5, labels),
            "delta": round(compute_auc(comp5, labels) - compute_auc(comp4, labels), 4),
            "metastack5_weights": [round(float(w), 3) for w in w5],
        }
        delta = exact_biased[target]["delta"]
        mark = "UP" if delta > 0 else ("DN" if delta < 0 else "=")
        print(f"  {target:15s}  m4={exact_biased[target]['auc_metastack4']:.4f}  "
              f"m5={exact_biased[target]['auc_metastack5']:.4f}  delta={delta:+.4f} {mark}")

    exact_mean_m4 = np.mean([v["auc_metastack4"] for v in exact_biased.values()])
    exact_mean_m5 = np.mean([v["auc_metastack5"] for v in exact_biased.values()])
    print()
    print(f"  EXACT BIASED MEAN:  m4={exact_mean_m4:.4f}  m5={exact_mean_m5:.4f}  "
          f"delta={exact_mean_m5 - exact_mean_m4:+.4f}")

    # ──
    # SAVE REPORT
    # ──
    report = {
        "individual_aucs": indiv_aucs,
        "biased_metastack5": exact_biased,
        "biased_mean_metastack4": round(float(exact_mean_m4), 4),
        "biased_mean_metastack5": round(float(exact_mean_m5), 4),
        "biased_mean_delta": round(float(exact_mean_m5 - exact_mean_m4), 4),
        "loto_honest_metastack5": loto_results if loto_results else None,
    }
    if loto_results:
        report["loto_mean_metastack4"] = round(float(loto_mean_m4), 4)
        report["loto_mean_metastack5"] = round(float(loto_mean_m5), 4)
        report["loto_mean_delta"] = round(float(loto_mean_m5 - loto_mean_m4), 4)

    out_path = OUTPUT_DIR / "metastack5_report.json"
    out_path.write_text(json.dumps(report, indent=2))
    print()
    print(f"Report saved: {out_path}")

    # Summary
    print()
    print("=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print(f"  Biased Metastack4 mean: {exact_mean_m4:.4f}")
    print(f"  Biased Metastack5 mean: {exact_mean_m5:.4f}")
    print(f"  Biased delta: {exact_mean_m5 - exact_mean_m4:+.4f}")
    if loto_results:
        print()
        print(f"  LOTO Metastack4 mean:  {loto_mean_m4:.4f}")
        print(f"  LOTO Metastack5 est:   {loto_mean_m5:.4f}")
        print(f"  LOTO delta:            {loto_mean_m5 - loto_mean_m4:+.4f}")


if __name__ == "__main__":
    main()
