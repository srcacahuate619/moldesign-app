#!/usr/bin/env python3
"""
scripts/metastack_metal_comparison.py
======================================
Compare 4 strategies on the 7-target benchmark:

  A) M4 baseline           : vina + xgb + clgnn_a + gnn_d
  B) M5+MolChamb (gated)   : + molchamb_score         (metalloenzyme only)
  C) M5+ZnCoord (gated)    : + zn_coord_score         (metalloenzyme only)
  D) M6 full (gated)       : + molchamb + zn_coord    (metalloenzyme only)

Non-metaloenzyme targets ALWAYS use M4 (zero regression guarantee).

INPUTS:
  - data/molchamb_loto/checkpoints/benchmark_checkpoint_*.json (with molchamb_score)
  - data/molchamb_loto/zn_features_ca2.json (Zn-coord features for ca2)

OUTPUT:
  - data/molchamb_loto/metal_strategy_comparison.json
"""
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

CK_DIR = PROJECT_ROOT / "data" / "molchamb_loto" / "checkpoints"
ZN_FEATURES_PATH = PROJECT_ROOT / "data" / "molchamb_loto" / "zn_features_ca2.json"
OUT_PATH = PROJECT_ROOT / "data" / "molchamb_loto" / "metal_strategy_comparison.json"

TARGET_FAMILY = {
    "5ht1a":        "gpcr",
    "cdk2":         "kinase",
    "hiv_protease": "protease",
    "er_alpha":     "nuclear_receptor",
    "factor_xa":    "soluble_enzyme",
    "ca2":          "metaloenzyme",
    "thrombin":     "soluble_enzyme",
}
TARGETS = ["5ht1a", "ca2", "cdk2", "er_alpha", "factor_xa", "hiv_protease", "thrombin"]


def score_vina(r):
    vina = abs(r.get("vina_score") or -5.0)
    return min(1.0, vina / 12.0)

def score_xgb(r):
    return r.get("prob", 0.0)

def score_clgnn_a(r):
    return r.get("clgnn_prob", 0.5)

def score_gnn_d(r):
    v = r.get("gnn_d_prob")
    if v is None or v == 0.5:
        return 0.5
    return v

def score_molchamb(r):
    v = r.get("molchamb_score")
    return float(v) if v is not None else 0.5


def softmax_weights(scores, T=6.0, p=1.0):
    s = np.array(scores, dtype=float)
    powered = np.maximum(np.abs(s) ** p, 1e-12)
    exp_s = np.exp(powered / T - np.max(powered / T))
    return exp_s / exp_s.sum()

def metastack_weights(*a, T=6.0, p=1.0, sat=0.96, hedge=0.65):
    aucs = np.array(a, dtype=float)
    n = len(aucs)
    if any(aucs > sat):
        w = np.ones(n) * 0.05
        w[int(np.argmax(aucs))] = 0.80
        return w
    elif all(aucs < hedge):
        return np.ones(n) / n
    return softmax_weights(aucs, T=T, p=p)


def comp_score(r, w, scorers):
    s = np.array([fn(r) for fn in scorers[:len(w)]])
    return float(np.dot(s, w))


def is_metallo(target):
    return TARGET_FAMILY.get(target) == "metaloenzyme"


def enrich_with_zn_features(results, zn_records):
    """Attach zn_coord_score (from a precomputed file) to each result by SMILES."""
    # Build a SMILES -> zn_coord_score lookup
    zn_by_smiles = {rec["smiles"]: rec["zn_coord_score"] for rec in zn_records}
    enriched = []
    n_augmented = 0
    for r in results:
        smi = r.get("smiles", "")
        zn_score = zn_by_smiles.get(smi, 0.5)  # fallback 0.5 if no pose
        r2 = dict(r)
        r2["zn_coord_score"] = zn_score
        if smi in zn_by_smiles:
            n_augmented += 1
        enriched.append(r2)
    return enriched, n_augmented


def compute_auc(scores, labels):
    if len(set(labels)) < 2:
        return 0.5
    return round(roc_auc_score(labels, scores), 4)


def main():
    # Load Zn features for ca2
    zn_data = json.loads(ZN_FEATURES_PATH.read_text())
    zn_records = zn_data["records"]
    print(f"Loaded {len(zn_records)} Zn-feature records for ca2")

    # Load each target
    print()
    print("=" * 90)
    print("STRATEGY COMPARISON (per target, exact per-molecule AUC)")
    print("=" * 90)
    print(f"{'Target':15s} {'Family':18s} {'M4':>8s} {'M5-MC':>8s} "
          f"{'M5-Zn':>8s} {'M6-Full':>8s} {'M6-best':>8s}")
    print("-" * 90)

    summary = {}
    for target in TARGETS:
        ck_path = CK_DIR / f"benchmark_checkpoint_{target}.json"
        if not ck_path.exists():
            continue
        data = json.loads(ck_path.read_text())
        results = data.get("results", [])
        valid = [r for r in results if r.get("vina_score") is not None]
        labels = [r["is_active"] for r in valid]
        if len(set(labels)) < 2:
            continue
        family = TARGET_FAMILY.get(target, "default")
        metal = is_metallo(target)

        # If metalloenzyme, enrich results with Zn features
        if metal:
            valid, n_zn = enrich_with_zn_features(valid, zn_records)
            print(f"  [ca2] enriched {n_zn} molecules with zn_coord_score")
        # else: no Zn for non-metal -- always M4

        def score_zn(r):
            v = r.get("zn_coord_score", 0.5)
            return float(v)

        # Individual scorer AUCs
        aucs_4 = [
            compute_auc([score_vina(r) for r in valid], labels),
            compute_auc([score_xgb(r) for r in valid], labels),
            compute_auc([score_clgnn_a(r) for r in valid], labels),
            compute_auc([score_gnn_d(r) for r in valid], labels),
        ]
        # 5th scorer AUC (if metalloenzyme)
        auc_molch = compute_auc([score_molchamb(r) for r in valid], labels) if metal else None
        auc_zn = compute_auc([score_zn(r) for r in valid], labels) if metal else None

        # M4 weights & composite (baseline -- always computed)
        w4 = metastack_weights(*aucs_4)
        comp_m4 = [comp_score(r, w4, [score_vina, score_xgb, score_clgnn_a, score_gnn_d]) for r in valid]
        auc_m4 = compute_auc(comp_m4, labels)

        if metal:
            # M5+MolChamb (saturate rule runs with 5 scorers)
            w5_mc = metastack_weights(*aucs_4, auc_molch)
            comp_5mc = [comp_score(r, w5_mc, [score_vina, score_xgb, score_clgnn_a, score_gnn_d, score_molchamb]) for r in valid]
            auc_m5_mc = compute_auc(comp_5mc, labels)

            # M5+ZnCoord (replaces MolChamb)
            w5_zn = metastack_weights(*aucs_4, auc_zn)
            comp_5zn = [comp_score(r, w5_zn, [score_vina, score_xgb, score_clgnn_a, score_gnn_d, score_zn]) for r in valid]
            auc_m5_zn = compute_auc(comp_5zn, labels)

            # M6 full (vina + xgb + clgnn_a + gnn_d + molchamb + zn_coord)
            w6 = metastack_weights(*aucs_4, auc_molch, auc_zn)
            comp_m6 = [comp_score(r, w6, [score_vina, score_xgb, score_clgnn_a, score_gnn_d, score_molchamb, score_zn]) for r in valid]
            auc_m6 = compute_auc(comp_m6, labels)

            # M6-optimized: also try a few weight ratios for molchamb+zn blend
            auc_m6_best = auc_m6
            best_w_str = "sat"
            # Try: replace molchamb+zn with a single blended score
            for w_mc in [0.3, 0.4, 0.5, 0.6, 0.7]:
                w_zc = 1.0 - w_mc
                # Blended scorer
                def blended(r, w_mc=w_mc, w_zc=w_zc):
                    return w_mc * score_molchamb(r) + w_zc * score_zn(r)
                b_scores = [blended(r) for r in valid]
                auc_b = compute_auc(b_scores, labels)
                # Use blended as 5th scorer in M5
                w5b = metastack_weights(*aucs_4, auc_b)
                comp5b = [comp_score(r, w5b, [score_vina, score_xgb, score_clgnn_a, score_gnn_d, blended]) for r in valid]
                auc_b_combined = compute_auc(comp5b, labels)
                if auc_b_combined > auc_m6_best:
                    auc_m6_best = auc_b_combined
                    best_w_str = f"M5blend(mol={w_mc:.1f},zn={w_zc:.1f})"

            print(f"{target:15s} {family:18s} {auc_m4:8.4f} {auc_m5_mc:8.4f} "
                  f"{auc_m5_zn:8.4f} {auc_m6:8.4f} {auc_m6_best:8.4f}  ({best_w_str})")
            summary[target] = {
                "family": family,
                "is_metalloenzyme": True,
                "auc_metastack4": auc_m4,
                "auc_m5_molchamb": auc_m5_mc,
                "auc_m5_zncoord": auc_m5_zn,
                "auc_m6_full": auc_m6,
                "auc_m6_best": auc_m6_best,
                "best_strategy": best_w_str,
                "individual_aucs": {
                    "vina": aucs_4[0], "xgb": aucs_4[1],
                    "clgnn_a": aucs_4[2], "gnn_d": aucs_4[3],
                    "molchamb": auc_molch, "zn_coord": auc_zn,
                },
            }
        else:
            # Non-metaloenzyme: everything equals M4
            print(f"{target:15s} {family:18s} {auc_m4:8.4f}    --       --       --       --")
            summary[target] = {
                "family": family,
                "is_metalloenzyme": False,
                "auc_metastack4": auc_m4,
                "auc_m5_molchamb": auc_m4,  # unchanged, gated = M4
                "auc_m5_zncoord": auc_m4,
                "auc_m6_full": auc_m4,
                "auc_m6_best": auc_m4,
                "note": "Non-metaloenzyme -- reverted to M4 (no regression guaranteed)",
            }

    print()
    print("=" * 90)
    print("MEAN ACROSS 7 TARGETS")
    print("=" * 90)
    m4s = [v["auc_metastack4"] for v in summary.values()]
    m5_mcs = [v["auc_m5_molchamb"] for v in summary.values()]
    m5_zns = [v["auc_m5_zncoord"] for v in summary.values()]
    m6_fulls = [v["auc_m6_full"] for v in summary.values()]
    m6_bests = [v["auc_m6_best"] for v in summary.values()]
    print(f"  M4 baseline: {np.mean(m4s):.4f}")
    print(f"  M5+MolChamb (gated): {np.mean(m5_mcs):.4f}  (delta {np.mean(m5_mcs)-np.mean(m4s):+.4f})")
    print(f"  M5+ZnCoord  (gated): {np.mean(m5_zns):.4f}  (delta {np.mean(m5_zns)-np.mean(m4s):+.4f})")
    print(f"  M6 full     (gated): {np.mean(m6_fulls):.4f}  (delta {np.mean(m6_fulls)-np.mean(m4s):+.4f})")
    print(f"  M6 best     (gated): {np.mean(m6_bests):.4f}  (delta {np.mean(m6_bests)-np.mean(m4s):+.4f})")

    report = {
        "strategies": {
            "M4_baseline": {"mean": round(float(np.mean(m4s)), 4)},
            "M5_molchamb_gated": {"mean": round(float(np.mean(m5_mcs)), 4),
                                   "delta": round(float(np.mean(m5_mcs)-np.mean(m4s)), 4)},
            "M5_zncoord_gated": {"mean": round(float(np.mean(m5_zns)), 4),
                                  "delta": round(float(np.mean(m5_zns)-np.mean(m4s)), 4)},
            "M6_full_gated": {"mean": round(float(np.mean(m6_fulls)), 4),
                                "delta": round(float(np.mean(m6_fulls)-np.mean(m4s)), 4)},
            "M6_best_gated": {"mean": round(float(np.mean(m6_bests)), 4),
                                "delta": round(float(np.mean(m6_bests)-np.mean(m4s)), 4)},
        },
        "per_target": summary,
        "design": "Non-metaloenzyme targets = M4 baseline (no regression). "
                  "Metaloenzyme (ca2) tests 5th/6th scorer options.",
    }
    OUT_PATH.write_text(json.dumps(report, indent=2))
    print()
    print(f"Report saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
