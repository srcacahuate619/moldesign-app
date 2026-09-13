"""
scripts/optimize-stacking-weights.py
Re-optimiza stacking_weights.json usando los checkpoints con GNN-v2 funcional.
Grid search por familia buscando max AUC sobre {vina, prob, gnn, clgnn}.

Lee:   data/gnn_fixed/benchmark_checkpoint_<ds>.json
Escribe: rescoring/artifacts/stacking_weights.json  (con backup del previo)
"""

import json
import shutil
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from benchmark_ef_vina import rank_normalize

CHECKPOINTS_DIR = PROJECT_ROOT / "data" / "gnn_fixed"
WEIGHTS_PATH = PROJECT_ROOT / "rescoring" / "artifacts" / "stacking_weights.json"

TARGETS = {
    "5ht1a":        "gpcr",
    "cdk2":         "kinase",
    "hiv_protease": "protease",
    "er_alpha":     "nuclear_receptor",
    "factor_xa":    "soluble_enzyme",
}


def optimize_family(results):
    """Grid search max AUC over {vina, prob, gnn, clgnn} with sum=1."""
    labels = [1 if r["is_active"] else 0 for r in results]
    vina_raw = [abs(r["vina_score"]) if r.get("vina_score") is not None else 0.0 for r in results]
    vina = rank_normalize(vina_raw, higher_better=True)
    prob  = rank_normalize([r.get("prob", 0.5) for r in results], higher_better=True)
    gnn   = rank_normalize([r.get("gnn_prob", 0.5) for r in results], higher_better=True)
    clgnn = rank_normalize([r.get("clgnn_prob", 0.5) for r in results], higher_better=True)

    best = {"auc": 0.0, "w": None}
    for wv in np.arange(0.0, 0.81, 0.1):
        for wp in np.arange(0.0, 0.81, 0.1):
            for wg in np.arange(0.0, 0.61, 0.1):
                wc = round(1.0 - wv - wp - wg, 2)
                if wc < 0 or wc > 1.0:
                    continue
                scores = [vina[i]*wv + prob[i]*wp + gnn[i]*wg + clgnn[i]*wc for i in range(len(labels))]
                auc = roc_auc_score(labels, scores)
                if auc > best["auc"]:
                    best = {"auc": auc, "w": (round(wv,2), round(wp,2), round(wg,2), round(wc,2))}
    return best


def main():
    print("=" * 60)
    print("  OPTIMIZE STACKING WEIGHTS (con GNN-v2 funcional)")
    print("=" * 60)

    if WEIGHTS_PATH.exists():
        backup = WEIGHTS_PATH.with_suffix(".json.bak_pre_gnn")
        shutil.copy2(WEIGHTS_PATH, backup)
        print(f"  Backup: {backup}")

    with open(WEIGHTS_PATH) as f:
        current = json.load(f)

    new_weights = {}
    for ds, family in TARGETS.items():
        ck = CHECKPOINTS_DIR / f"benchmark_checkpoint_{ds}.json"
        if not ck.exists():
            print(f"  [SKIP] No checkpoint for {ds}")
            continue
        with open(ck) as f:
            data = json.load(f)
        results = data.get("results", [])
        if not any("gnn_prob" in r for r in results):
            print(f"  [SKIP] No gnn_prob in {ds}")
            continue
        res = optimize_family(results)
        wv, wp, wg, wc = res["w"]
        new_weights[family] = {
            "vina": wv, "prob": wp, "gnn": wg, "clgnn": wc,
            "molchamb_sign": current.get(family, {}).get("molchamb_sign", 1.0),
            "_optimized_from": ds,
            "_auc": round(res["auc"], 4),
        }
        print(f"  {ds:14s} ({family:18s})  AUC={res['auc']:.4f}  vina={wv} prob={wp} gnn={wg} clgnn={wc}")

    # Preserve default
    new_weights["default"] = current.get("default", {
        "vina": 0.3, "prob": 0.5, "gnn": 0.0, "clgnn": 0.2, "molchamb_sign": 1.0
    })
    # Preserve other families not re-optimized
    for fam, w in current.items():
        if fam not in new_weights:
            new_weights[fam] = w

    with open(WEIGHTS_PATH, "w") as f:
        json.dump(new_weights, f, indent=2)
    print(f"\n  Saved: {WEIGHTS_PATH}")
    print("  DONE")


if __name__ == "__main__":
    main()