"""
scripts/ensemble_clgnn.py — Snapshot Ensemble of 3 CL-GNN seeds.

Eficiencia: entrena 3 seeds en GPU, evalua cada una, promedia predicciones.
Calidad: ensemble reduce varianza y suele superar individuales.
Validez cientifica: reporta AUC mean/std del ensemble frente a scorers.

Usage:
  python scripts/ensemble_clgnn.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"
ARTIFACTS = PROJECT_ROOT / "rescoring" / "artifacts"
CKPT_PATH = PROJECT_ROOT / "data" / "gnn_v31" / "checkpoints" / "benchmark_checkpoint_5ht1a.json"

SEEDS = [42, 43, 44]
SCRIPT = SCRIPTS / "contrastive_v31.py"


def run(cmd, label=""):
    print(f"\n  [{label}] Running: {cmd}")
    t0 = time.time()
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3600)
    elapsed = time.time() - t0
    if r.returncode != 0:
        print(f"  ERROR ({elapsed:.0f}s): {r.stderr[-500:]}")
        raise RuntimeError(label)
    print(f"  OK ({elapsed:.0f}s)")
    return r.stdout


def compute_ef(scores, labels, pct):
    n = len(labels)
    th = max(1, int(n * pct / 100.0))
    order = np.argsort(-scores)
    top = order[:th]
    n_act_total = int(sum(labels))
    if n_act_total == 0:
        return 0.0
    n_act_top = int(sum(labels[i] for i in top))
    expected = th * (n_act_total / n)
    return n_act_top / expected if expected > 0 else 0.0


def main():
    print("=" * 70)
    print("  CL-GNN SNAPSHOT ENSEMBLE (3 seeds)")
    print(f"  Seeds: {SEEDS}")
    print(f"  GPU: {os.system('python -c \"import torch; print(torch.cuda.is_available())\"')}")
    print("=" * 70)

    # Phase 1: Train + eval each seed
    all_preds = {}  # seed -> predictions array

    for seed in SEEDS:
        print(f"\n{'=' * 70}")
        print(f"  SEED {seed}")
        print(f"{'=' * 70}")
        t0 = time.time()

        # 1a. Pretrain
        run(f'python {SCRIPT} --pretrain --epochs 200 --batch-size 16 --lr 1e-3 --hidden-dim 128 --seed {seed}',
            label=f"seed={seed} pretrain")

        # 1b. Finetune
        run(f'python {SCRIPT} --finetune --finetune-epochs 100 --batch-size 16 --finetune-lr 5e-4 --hidden-dim 128 --seed {seed}',
            label=f"seed={seed} finetune")

        # 1c. Save model copy
        shutil.copy(ARTIFACTS / "gnn_v2_cl_best.pt", ARTIFACTS / f"gnn_v2_cl_seed{seed}.pt")
        print(f"  Saved gnn_v2_cl_seed{seed}.pt")

        # 1d. Eval on 5HT1A
        run(f'python {SCRIPT} --evaluate-5ht1a --model-path "gnn_v2_cl_best.pt" --hidden-dim 128',
            label=f"seed={seed} eval")
        elapsed = time.time() - t0
        print(f"  seed={seed} complete in {elapsed:.0f}s")

        # 1e. Extract predictions from checkpoint
        ck = json.load(open(CKPT_PATH))
        preds = np.array([r.get("clgnn_prob", 0.5) for r in ck["results"]])
        all_preds[seed] = preds
        labels = np.array([int(bool(r.get("is_active", False))) for r in ck["results"]])
        auc = roc_auc_score(labels, preds)
        print(f"  seed={seed} AUC={auc:.4f}")

    # Phase 2: Average predictions
    print(f"\n{'=' * 70}")
    print("  ENSEMBLE AVERAGING")
    print(f"{'=' * 70}")

    preds_stack = np.stack([all_preds[s] for s in SEEDS], axis=0)
    ensemble_mean = preds_stack.mean(axis=0)
    ensemble_std = preds_stack.std(axis=0)

    ck = json.load(open(CKPT_PATH))
    labels = np.array([int(bool(r.get("is_active", False))) for r in ck["results"]])
    valid = ~np.isnan(ensemble_mean)
    y, p = labels[valid], ensemble_mean[valid]

    auc = roc_auc_score(y, p)
    pr = average_precision_score(y, p)
    ef1 = compute_ef(p, y, 1)
    ef5 = compute_ef(p, y, 5)
    ef10 = compute_ef(p, y, 10)

    print(f"\n  Individual seeds:")
    for seed in SEEDS:
        a = roc_auc_score(labels, all_preds[seed])
        print(f"    seed {seed}: AUC = {a:.4f}")
    print(f"  ---")
    print(f"  Ensemble (mean of {len(SEEDS)}):")
    print(f"    ROC-AUC:  {auc:.4f}")
    print(f"    PR-AUC:   {pr:.4f}")
    print(f"    EF@1%:    {ef1:.2f}x")
    print(f"    EF@5%:    {ef5:.2f}x")
    print(f"    EF@10%:   {ef10:.2f}x")

    # Phase 3: Save ensemble predictions to checkpoint
    for i, r in enumerate(ck["results"]):
        r["clgnn_prob"] = round(float(ensemble_mean[i]), 6)
        r["clgnn_std"] = round(float(ensemble_std[i]), 6)

    # Save to all locations
    for dest in [PROJECT_ROOT / "data" / "gnn_v31" / "checkpoints",
                 PROJECT_ROOT / "data" / "gnn_fixed",
                 PROJECT_ROOT / "data"]:
        path = dest / "benchmark_checkpoint_5ht1a.json"
        if not Path(str(path) + ".bak_ensemble").exists():
            shutil.copy(path, str(path) + ".bak_ensemble")
        with open(path, "w") as f:
            json.dump(ck, f, indent=2)
        print(f"  Saved: {path}")

    # Phase 4: Report
    report = {
        "version": "CL-GNN ensemble",
        "seeds": SEEDS,
        "individual_aucs": {str(s): float(roc_auc_score(labels, all_preds[s])) for s in SEEDS},
        "individual_auc_mean": float(np.mean([roc_auc_score(labels, all_preds[s]) for s in SEEDS])),
        "individual_auc_std": float(np.std([roc_auc_score(labels, all_preds[s]) for s in SEEDS])),
        "ensemble_auc": auc,
        "ensemble_pr": pr,
        "ensemble_ef1": ef1,
        "ensemble_ef5": ef5,
        "ensemble_ef10": ef10,
    }
    out_path = PROJECT_ROOT / "data" / "gnn_fixed" / "ensemble_report.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved: {out_path}")
    print(f"\n{'=' * 70}")
    print("  ENSEMBLE COMPLETE")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
