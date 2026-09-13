"""
Re-score 5-HT1A benchmark checkpoint with GNN-v3.
Reuses docked PDBQT poses from previous Vina runs.
~22 min for 2550 molecules on CPU.
"""
import json, sys, time, tempfile, os
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))

from gnn_v2.inference import GNNv2Predictor

CHECKPOINT = PROJECT_ROOT / "data" / "gnn_fixed" / "benchmark_checkpoint_5ht1a.json"
TARGET_PDB = PROJECT_ROOT / "data" / "pdbs" / "7E2Y.pdb"
TEMP = tempfile.mkdtemp(prefix="gnnv3_rescore_")
OUTPUT = PROJECT_ROOT / "data" / "gnn_fixed" / "ef_report_5ht1a_gnnv3.json"

print(f"Loading checkpoint: {CHECKPOINT}")
with open(CHECKPOINT) as f:
    ckpt = json.load(f)

results = ckpt["results"]
completed = ckpt.get("completed_smiles", [])
print(f"Checkpoint: {len(results)} molecules, {len(completed)} completed")

predictor = GNNv2Predictor(device="cpu", mc_samples=10)
predictor.reset_silent_failures()
print(f"Model: {'CUDA' if 'cuda' in predictor.device else 'CPU'}")

probs = []
stds = []
labels = []
silent = 0
success = 0
errors = 0
n = len(results)
t_start = time.time()

for i, item in enumerate(results):
    smiles = item.get("smiles", "")
    pdbqt_block = item.get("pose_pdbqt", "")
    is_active = item.get("is_active", False)

    if not pdbqt_block or not smiles:
        silent += 1
        continue

    tmp_path = os.path.join(TEMP, f"pose_{i}.pdbqt")
    with open(tmp_path, "w") as f:
        f.write(pdbqt_block)

    try:
        prob, std = predictor.predict(smiles, tmp_path, str(TARGET_PDB))
        probs.append(float(prob))
        stds.append(float(std))
        labels.append(bool(is_active))
        success += 1
    except Exception as e:
        errors += 1
        if errors <= 5:
            print(f"  ERROR [{i}]: {e}")

    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    if (i + 1) % 500 == 0 or i == 0:
        elapsed = time.time() - t_start
        eta = elapsed / (i + 1) * (n - i - 1) if i > 0 else 0
        print(f"  [{i+1:4d}/{n}] {success} scored | {silent} silent | "
              f"{elapsed:.0f}s elapsed | ETA {eta:.0f}s")

elapsed = time.time() - t_start

if len(probs) < 10:
    print("FAILED: not enough predictions")
    sys.exit(1)

probs_arr = np.array(probs)
labels_arr = np.array(labels)

auc = roc_auc_score(labels_arr, probs_arr)
n_actives = labels_arr.sum()

# EF@1%
sorted_idx = np.argsort(probs_arr)[::-1]
ranked_labels = labels_arr[sorted_idx]
cutoff = max(1, int(len(labels_arr) * 0.01))
ef1 = ranked_labels[:cutoff].sum() / (n_actives * 0.01) if n_actives > 0 else 0

# EF@5%
cutoff5 = max(1, int(len(labels_arr) * 0.05))
ef5 = ranked_labels[:cutoff5].sum() / (n_actives * 0.05) if n_actives > 0 else 0

# EF@10%
cutoff10 = max(1, int(len(labels_arr) * 0.10))
ef10 = ranked_labels[:cutoff10].sum() / (n_actives * 0.10) if n_actives > 0 else 0

silent_rate = (silent + errors) / n * 100

print(f"\n{'='*60}")
print(f"GNN-v3 5-HT1A Re-Score Results")
print(f"{'='*60}")
print(f"  Total molecules: {n}")
print(f"  Successful: {success}")
print(f"  Silent fails: {silent} ({silent_rate:.1f}%)")
print(f"  Errors: {errors}")
print(f"  Actives: {int(n_actives)} / Decoys: {len(labels_arr) - int(n_actives)}")
print(f"  Time: {elapsed:.0f}s ({elapsed/n:.2f}s/mol)")
print(f"")
print(f"  ROC-AUC: {auc:.4f}")
print(f"  EF@1%:   {ef1:.1f}x")
print(f"  EF@5%:   {ef5:.1f}x")
print(f"  EF@10%:  {ef10:.1f}x")
print(f"")
print(f"  Mean P(active): {probs_arr[labels_arr].mean():.4f}")
print(f"  Mean P(decoy):  {probs_arr[~labels_arr].mean():.4f}")
print(f"")
print(f"{'='*60}")
print(f"ACCEPTANCE CHECK")
print(f"{'='*60}")
print(f"  AUC >= 0.80:   {'PASS' if auc >= 0.80 else 'FAIL'} ({auc:.4f})")
print(f"  Silent <= 1%:  {'PASS' if silent_rate <= 1 else 'FAIL'} ({silent_rate:.1f}%)")
print(f"  Speed < 1s:    {'PASS' if elapsed/n < 1 else 'FAIL'} ({elapsed/n:.2f}s/mol)")

report = {
    "version": "gnn_v3",
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "target": "5-HT1A (7E2Y)",
    "n_total": n,
    "n_actives": int(n_actives),
    "n_decoys": len(labels_arr) - int(n_actives),
    "n_success": success,
    "n_silent_fails": silent,
    "n_errors": errors,
    "silent_fail_rate_pct": round(silent_rate, 2),
    "inference_time_s": round(elapsed, 1),
    "time_per_mol_s": round(elapsed / n, 3),
    "metrics": {
        "roc_auc": round(auc, 4),
        "ef_1pct": round(ef1, 1),
        "ef_5pct": round(ef5, 1),
        "ef_10pct": round(ef10, 1),
        "mean_prob_active": round(float(probs_arr[labels_arr].mean()), 4),
        "mean_prob_decoy": round(float(probs_arr[~labels_arr].mean()), 4),
    },
    "acceptance": {
        "auc_ge_08": auc >= 0.80,
        "silent_fail_le_1pct": silent_rate <= 1,
        "speed_lt_1s": elapsed / n < 1,
    },
    "config": {
        "hidden_dim": 128,
        "lig_in_dim": 38,
        "mc_samples": 10,
        "device": predictor.device,
    },
}

with open(OUTPUT, "w") as f:
    json.dump(report, f, indent=2)
print(f"\nReport saved: {OUTPUT}")

import shutil
shutil.rmtree(TEMP, ignore_errors=True)
