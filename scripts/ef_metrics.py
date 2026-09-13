#!/usr/bin/env python3
"""
scripts/ef_metrics.py — Early-enrichment metrics for PAPER_UMS (Issue 8).

Computes EF@1%, EF@5%, EF@10% (and BEDROC alpha=20 if scikit-optimized
implementation available) for M4, M5_gated, and individual scorers on the
three full-pipeline targets (CA2, MMP9, ACE).

Reuses the exact M4/M5 definitions from scripts/delong_paired_test.py so the
enrichment table is consistent with Table 3.2.

Usage:
  python scripts/ef_metrics.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from universal_metal_score import detect_warheads

OUT = Path("data/molchamb_loto/ef_metrics_report.json")


# ── Data loaders (identical to delong_paired_test.py) ──

def load_ca2():
    ckpt = json.loads(Path("data/molchamb_loto/checkpoints/benchmark_checkpoint_ca2.json")
                      .read_bytes().decode("utf-8"))
    mols = []
    for r in ckpt["results"]:
        vina, prob, gnn = r.get("vina_score"), r.get("prob"), r.get("gnn_d_prob")
        if vina is None or prob is None or gnn is None:
            continue
        # Warhead-only PURE: recomputed from SMILES with the canonical detector
        # (NOT the checkpoint's universal_metal_score, which mixes donor+molchamb)
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


def warhead_only_score(smi):
    """PURE SMARTS warhead component (the paper's core invariant).

    Returns 0.0 if no warhead detected; 0.85-0.95 scaled by warhead count.
    Matches the SMARTS-only rows of Table 3.4.
    """
    wh = detect_warheads(smi)
    if not any(wh.values()):
        return 0.0
    n = sum(1 for v in wh.values() if v)
    return 0.85 + 0.10 * min(n / 3.0, 1.0)


def build_scores(mols, target):
    """Return (y, m4, m5, scores_dict) replicating delong_paired_test.py."""
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
        indiv = {"Vina": vn, "XGBoost": xgb, "GNN-D": gnn, "Warhead (SMARTS)": ums}
    elif target == "mmp9":
        m4 = 1.0 * xgb
        m5 = 0.75 * xgb + 0.25 * ums
        indiv = {"Vina": vn, "XGBoost": xgb, "Warhead (SMARTS)": ums}
    elif target == "ace":
        m4 = vn * 0.3 + xgb * 0.7
        m5 = vn * 0.2 + xgb * 0.4 + ums * 0.4
        indiv = {"Vina": vn, "XGBoost": xgb, "Warhead (SMARTS)": ums}
    else:
        raise ValueError(target)
    return y, m4, m5, indiv


def ef_at_fraction(y_true, y_score, fraction):
    """Enrichment factor at the given fraction of the ranked list.

    EF@f = (actives in top f% / top f% size) / (total actives / total size)
    """
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    n = len(y_true)
    k = max(1, int(round(fraction * n)))
    top_idx = np.argsort(-y_score)[:k]
    n_act = y_true.sum()
    n_act_top = y_true[top_idx].sum()
    if n_act == 0:
        return 0.0, 0.0
    ef = (n_act_top / k) / (n_act / n)
    return float(ef), int(n_act_top)


def bedroc(y_true, y_score, alpha=20.0):
    """BEDROC (Truchon & Bayly 2007) with exponential weighting.

    Corrected implementation (2026-08-06): the closed-form RIE_max/RIE_min
    require a factor 1/(n_a) in the denominator:
        RIE_max = (1 - exp(-a*n_a/n)) / (n_a * (1 - exp(-a)))
        RIE_min = (1 - exp(+a*n_a/n)) / (n_a * (1 - exp(+a)))
    A previous version omitted the n_a factor, producing degenerate values
    (~0 for perfect ranking) and spurious negatives. Sanity checks:
    perfect -> 1.0, random -> ~0, worst -> ~-1 (with average ties).
    """
    y_true = np.asarray(y_true, dtype=float)
    y_score = np.asarray(y_score, dtype=float)
    n = len(y_true)
    n_pos = int(y_true.sum())
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    # Ranks with average ties: 1 = best (highest score)
    order = np.argsort(-y_score, kind="mergesort")
    ranks = np.empty(n)
    ranks[order] = np.arange(1, n + 1)
    sorted_s = y_score[order]
    i = 0
    while i < n:
        j = i
        while j < n and sorted_s[j] == sorted_s[i]:
            j += 1
        ranks[order[i:j]] = (i + 1 + j) / 2.0
        i = j
    pos_ranks = ranks[y_true == 1]

    factor = (1 - np.exp(-alpha)) / (np.exp(alpha / n) - 1)
    RIE = (1.0 / n_pos) * np.sum(np.exp(-alpha * pos_ranks / n)) / factor
    RIE_max = (1 - np.exp(-alpha * n_pos / n)) / (n_pos * (1 - np.exp(-alpha)))
    RIE_min = (1 - np.exp(+alpha * n_pos / n)) / (n_pos * (1 - np.exp(+alpha)))
    denom = RIE_max - RIE_min
    if denom == 0:
        return float("nan")
    return float((RIE - RIE_min) / denom)


def main():
    report = {}
    for target, loader in [("ca2", load_ca2), ("mmp9", load_mmp9), ("ace", load_ace)]:
        mols = loader()
        y, m4, m5, indiv = build_scores(mols, target)
        n = len(y)
        n_act = int(y.sum())

        rec = {"n_total": n, "n_act": n_act,
               "random_ef1": 1.0, "random_ef5": 1.0, "random_ef10": 1.0,
               "models": {}}

        models = {"M4 (baseline)": m4, "M5_gated": m5}
        models.update({f"Individual: {k}": v for k, v in indiv.items()})

        for name, score in models.items():
            entry = {}
            for frac, key in [(0.01, "ef1"), (0.05, "ef5"), (0.10, "ef10")]:
                ef, n_top = ef_at_fraction(y, score, frac)
                entry[key] = round(ef, 2)
                entry[f"{key}_hits"] = int(n_top)
            entry["auc"] = round(float(roc_auc_score(y, score)), 4)
            entry["bedroc_a20"] = round(bedroc(y, score, 20.0), 3)
            rec["models"][name] = entry

        # Theoretical ceiling: EF@f is maximized when all top-f% slots are actives.
        # If n_act >= k (enough actives to fill the top slice): EF_max = n/n_act.
        # If n_act < k (too few actives): EF_max = n/k = 1/fraction.
        k1 = max(1, int(round(0.01 * n)))
        k5 = max(1, int(round(0.05 * n)))
        k10 = max(1, int(round(0.10 * n)))
        rec["ceiling_ef1"] = round(n / n_act if n_act >= k1 else n / k1, 2)
        rec["ceiling_ef5"] = round(n / n_act if n_act >= k5 else n / k5, 2)
        rec["ceiling_ef10"] = round(n / n_act if n_act >= k10 else n / k10, 2)
        report[target] = rec

        print(f"\n[{target.upper()}] n={n} actives={n_act}")
        print(f"  Ceilings: EF@1%={rec['ceiling_ef1']}  EF@5%={rec['ceiling_ef5']}  EF@10%={rec['ceiling_ef10']}")
        print(f"  {'Model':28s} {'EF@1%':>6s} {'EF@5%':>6s} {'EF@10%':>7s} {'AUC':>6s} {'BEDROC':>7s}")
        for name, entry in rec["models"].items():
            print(f"  {name:28s} {entry['ef1']:6.2f} {entry['ef5']:6.2f} {entry['ef10']:7.2f} "
                  f"{entry['auc']:6.4f} {entry['bedroc_a20']:7.3f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSaved: {OUT}")


# ── DUD-E full-dataset mode (literature-comparable enrichment) ──

DUD_E_TARGETS = {
    "ca2":   ("actives.txt", "decoys.smi"),
    "mmp9":  ("actives.txt", "decoys.smi"),
    "ace":   ("actives.txt", "decoys.smi"),
    "hdac6": ("actives_hydroxamic.txt", "decoys_hydroxamic.smi"),
    "mmp2":  ("actives_hydroxamic.txt", "decoys_hydroxamic.smi"),
}

OUT_DUDE = Path("data/molchamb_loto/ef_metrics_dude_full.json")


def main_dude_full():
    """EF@1%/5%/10% for the PURE warhead detector on the FULL DUD-E-style
    datasets (CA2 31,664; MMP9 2,858; ACE 2,238), the same sample scale the
    virtual-screening literature uses for enrichment reporting (e.g.,
    DUD-E, Mysinger et al. 2012). Also reports the LOTO-checkpoint EF for
    M5_gated (pipeline) as a secondary, clearly-labelled subset.

    NOTE: the M5_gated pipeline EF is only computable on the LOTO checkpoints
    (1,933-2,003 molecules) because M4/M5 require Vina poses; running the full
    docking pipeline on ~31k CA2 molecules is a multi-day computation. The
    standalone warhead EF on DUD-E full is the literature-comparable number.
    """
    report = {}

    # (1) Full DUD-E datasets: pure warhead detector
    for name, (af, df) in DUD_E_TARGETS.items():
        base = Path("data/multitarget") / name
        actives = [l.split()[0] for l in (base / af).read_text(encoding="utf-8").splitlines() if l.strip()]
        decoys = [l.split()[0] for l in (base / df).read_text(encoding="utf-8").splitlines() if l.strip()]
        if not actives or not decoys:
            print(f"[SKIP] {name}: missing files")
            continue
        y = np.array([1] * len(actives) + [0] * len(decoys))
        scores = np.array([warhead_only_score(s) for s in actives + decoys])
        n = len(y)
        n_act = int(y.sum())
        rec = {
            "dataset": "DUD-E full",
            "n_total": n, "n_act": n_act,
            "auc": round(float(roc_auc_score(y, scores)), 4),
            "models": {},
        }
        for label, score in [("Warhead (SMARTS) standalone", scores)]:
            entry = {}
            for frac, key in [(0.01, "ef1"), (0.05, "ef5"), (0.10, "ef10")]:
                ef, n_top = ef_at_fraction(y, score, frac)
                entry[key] = round(ef, 2)
                entry[f"{key}_hits"] = int(n_top)
            entry["bedroc_a20"] = round(bedroc(y, score, 20.0), 3)
            rec["models"][label] = entry
        k1 = max(1, int(round(0.01 * n)))
        rec["ceiling_ef1"] = round(n / n_act if n_act >= k1 else n / k1, 2)
        report[name] = rec

        print(f"\n[{name.upper()}] DUD-E full: n={n} actives={n_act} AUC={rec['auc']:.4f}")
        print(f"  Ceiling EF@1%={rec['ceiling_ef1']}")
        for label, entry in rec["models"].items():
            print(f"  {label:32s} EF@1%={entry['ef1']:6.2f} EF@5%={entry['ef5']:6.2f} "
                  f"EF@10%={entry['ef10']:7.2f} BEDROC={entry['bedroc_a20']:.3f}")

    # (2) LOTO-checkpoint pipeline EF (clearly labelled subset)
    report["_note"] = (
        "M5_gated pipeline EF is computable only on LOTO checkpoints (1,933-2,003 mols) "
        "because M4/M5 require Vina poses; full DUD-E pipeline would need multi-day docking. "
        "Warhead standalone EF above is the literature-comparable number."
    )
    report["_loto_pipeline"] = {}
    for target, loader in [("ca2", load_ca2), ("mmp9", load_mmp9), ("ace", load_ace)]:
        mols = loader()
        y, m4, m5, indiv = build_scores(mols, target)
        n = len(y)
        n_act = int(y.sum())
        rec = {"n_total": n, "n_act": n_act, "models": {}}
        for name, score in [("M4", m4), ("M5_gated", m5)]:
            entry = {}
            for frac, key in [(0.01, "ef1"), (0.05, "ef5"), (0.10, "ef10")]:
                ef, n_top = ef_at_fraction(y, score, frac)
                entry[key] = round(ef, 2)
                entry[f"{key}_hits"] = int(n_top)
            entry["auc"] = round(float(roc_auc_score(y, score)), 4)
            rec["models"][name] = entry
        report["_loto_pipeline"][target] = rec
        print(f"\n[{target.upper()}] LOTO checkpoint: n={n} actives={n_act}")
        for name, entry in rec["models"].items():
            print(f"  {name:12s} EF@1%={entry['ef1']:6.2f} EF@5%={entry['ef5']:6.2f} EF@10%={entry['ef10']:7.2f} AUC={entry['auc']:.4f}")

    OUT_DUDE.parent.mkdir(parents=True, exist_ok=True)
    OUT_DUDE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSaved: {OUT_DUDE}")


if __name__ == "__main__":
    main()
