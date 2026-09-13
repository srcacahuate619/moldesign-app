"""
scripts/eval_gnn_v31_5ht1a.py — GNN-v3.1 final 5HT1A evaluation

Evaluates the trained GNN-v3.1 on the held-out 5HT1A benchmark
(2550 molecules, never seen during training).

Reuses cached ECIF features inline in the benchmark checkpoint.
Outputs AUC, EF@1%, EF@5%, EF@10% + comparison vs:
  - GNN-v3 baseline (AUC 0.4917)
  - Vina+XGB (AUC 0.8288, paper primary)
  - Vina only (AUC 0.7975)

Usage:
  python scripts/eval_gnn_v31_5ht1a.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from gnn_v2.models import GNNv31Classifier
from gnn_v2.data import (
    ELEMENTS, ELEM_TO_IDX,
    _build_ligand_graph, _build_protein_graph, _build_cross_edges,
)

ARTIFACTS = PROJECT_ROOT / "rescoring" / "artifacts"
CKPT_PATH = ARTIFACTS / "gnn_v31_best.pt"
BENCH_PATH = PROJECT_ROOT / "data" / "gnn_v31" / "checkpoints" / "benchmark_checkpoint_5ht1a.json"
TARGET_PDB = PROJECT_ROOT / "data" / "targets" / "7E2Y.pdb"
ECIF_NORM_STATS = PROJECT_ROOT / "data" / "gnn_v31" / "ecif_all_zscored.npz"


def build_graph_from_pose(pose_pdbqt: str, target_pdb_path: str, smiles: str):
    """Construct complex graph dict for a 5HT1A entry."""
    fd, pdbqt = tempfile.mkstemp(suffix=".pdbqt")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(pose_pdbqt)
        from rdkit import Chem, RDLogger
        from rdkit.Chem import AllChem
        RDLogger.DisableLog("rdApp.*")
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        mol = Chem.AddHs(mol)
        AllChem.Compute2DCoords(mol)
        mol = Chem.RemoveHs(mol)
        sdf_fd, sdf_path = tempfile.mkstemp(suffix=".sdf")
        with os.fdopen(sdf_fd, "w") as f:
            f.close()
        w = Chem.SDWriter(sdf_path)
        w.write(mol)
        w.close()
        try:
            lig_graph = _build_ligand_graph(sdf_path, pdbqt)
        finally:
            try: os.unlink(sdf_path)
            except OSError: pass
        if lig_graph is None:
            return None
        prot_graph = _build_protein_graph(target_pdb_path, lig_graph.pos.numpy())
        if prot_graph is None:
            return None
        cross = _build_cross_edges(lig_graph.pos, prot_graph.pos)
        return {"protein": prot_graph, "ligand": lig_graph, "cross": cross}
    finally:
        try: os.unlink(pdbqt)
        except OSError: pass


def compute_ef(scores, labels, pct):
    """Compute enrichment factor at top X%."""
    n = len(labels)
    th = max(1, int(n * pct / 100.0))
    order = np.argsort(-scores)
    top = order[:th]
    n_actives_total = int(sum(labels))
    if n_actives_total == 0:
        return 0.0
    n_actives_top = int(sum(labels[i] for i in top))
    expected = th * (n_actives_total / n)
    if expected == 0:
        return 0.0
    return n_actives_top / expected


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    print(f"Target: 5HT1A held-out eval")
    print(f"Target PDB: {TARGET_PDB.name}")

    print("\nLoading model...")
    model = GNNv31Classifier(
        hidden_dim=128, dropout=0.2, ecif_in=152, use_delta_head=True
    )
    state = torch.load(CKPT_PATH, map_location=device, weights_only=False)
    model.load_state_dict(state, strict=False)
    model.to(device).eval()
    print(f"Model loaded from {CKPT_PATH.name}")

    # Load normalization stats
    norm = np.load(ECIF_NORM_STATS)
    mean, std = norm["mean"], norm["std"]

    print("\nLoading 5HT1A benchmark checkpoint...")
    with open(BENCH_PATH) as f:
        ck = json.load(f)
    results = ck["results"]
    print(f"  N molecules: {len(results)}")
    labels = np.array([int(bool(x.get("is_active", False))) for x in results])
    print(f"  Actives: {int(labels.sum())}/{len(labels)}")

    print("\n=== Predicting ===")
    preds = np.zeros(len(results), dtype=np.float32)
    silent = 0
    t0 = time.time()
    for i, ent in enumerate(results):
        smi = ent.get("smiles", "")
        pose = ent.get("pose_pdbqt", "")
        feats = ent.get("features", {}) or {}
        # Build ECIF vector (152-dim from inline features)
        ecif_keys = sorted([k for k in feats
                            if k.startswith("shell_") or k.startswith("ecif_")])
        if not ecif_keys:
            import warnings
            warnings.warn("No ECIF/Shell features found in checkpoint entries")
            ecif_keys = []
        v = np.zeros(152, dtype=np.float32)
        if len(ecif_keys) == 152:
            for j, k in enumerate(ecif_keys):
                try:
                    v[j] = float(feats.get(k, 0.0))
                except (TypeError, ValueError):
                    pass
            v = (v - mean[0]) / std[0]
            v = np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)
        elif len(ecif_keys) > 0:
            # Align keys if not 152
            print(f"  WARN: ecif_keys={len(ecif_keys)} != 152")
        ecif_t = torch.from_numpy(v).float().unsqueeze(0).to(device)

        try:
            graph = build_graph_from_pose(pose, str(TARGET_PDB), smi)
            if graph is None:
                preds[i] = 0.5
                silent += 1
                continue
            from torch_geometric.data import Batch
            prot_b = Batch.from_data_list([graph["protein"]]).to(device)
            lig_b = Batch.from_data_list([graph["ligand"]]).to(device)
            with torch.no_grad():
                prob_logit, _ = model(
                    prot_b.x, prot_b.edge_index,
                    lig_b.x, lig_b.edge_index,
                    graph["cross"].to(device),
                    lig_batch=lig_b.batch, prot_batch=prot_b.batch,
                    ecif=ecif_t,
                )
                preds[i] = float(torch.sigmoid(prob_logit).item())
        except Exception as e:
            preds[i] = 0.5
            silent += 1
        if (i + 1) % 100 == 0 or i == len(results) - 1:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(results) - i - 1) / rate
            print(f"  [{i+1}/{len(results)}] silent={silent} rate={rate:.1f}/s eta={eta:.0f}s")

    # Metrics
    valid = np.where(preds != 0.5)[0]
    if len(valid) == 0:
        print("\nERROR: No valid predictions!")
        return
    y = labels[valid]
    p = preds[valid]
    auc = float(roc_auc_score(y, p))
    pr = float(average_precision_score(y, p))
    ef1 = float(compute_ef(p, y, 1))
    ef5 = float(compute_ef(p, y, 5))
    ef10 = float(compute_ef(p, y, 10))
    n_actives = int(y.sum())

    print("\n=== GNN-v3.1 5HT1A HELD-OUT EVAL ===")
    print(f"Total molecules: {len(results)}")
    print(f"Successful predictions: {len(valid)}")
    print(f"Silent fails: {silent} ({silent/len(results)*100:.2f}%)")
    print(f"Actives: {n_actives}")
    print(f"Time: {time.time()-t0:.0f}s ({(time.time()-t0)/len(results):.2f}s/mol)")
    print(f"\n  ROC-AUC:  {auc:.4f}")
    print(f"  PR-AUC:   {pr:.4f}")
    print(f"  EF@1%:    {ef1:.2f}x")
    print(f"  EF@5%:    {ef5:.2f}x")
    print(f"  EF@10%:   {ef10:.2f}x")
    print(f"  Mean P(active): {p[y==1].mean():.4f}")
    print(f"  Mean P(decoy):  {p[y==0].mean():.4f}")

    print("\n=== Comparison ===")
    baselines = {
        "GNN-v3 (current)":  {"auc": 0.4917, "ef1": 2.1, "ef5": 1.3, "ef10": 1.1},
        "Vina only":          {"auc": 0.7975, "ef1": 19.51, "ef5": 5.97, "ef10": 4.05},
        "Vina+XGB (paper)":   {"auc": 0.8288, "ef1": 36.85, "ef5": 9.39, "ef10": 5.33},
        "GNN-v3.1 (ours)":    {"auc": auc, "ef1": ef1, "ef5": ef5, "ef10": ef10},
    }
    print(f"  {'Model':22} {chr(34):>10}{'AUC':10}{chr(34):>10}{'EF@1%':10}{chr(34):>10}{'EF@5%':10}{chr(34):>10}{'EF@10%':10}")
    for name, m in baselines.items():
        print(f"  {name:22} {m['auc']:10.4f} {m['ef1']:10.2f} {m['ef5']:10.2f} {m['ef10']:10.2f}")

    out = {
        "version": "GNN-v3.1 ECIF-augmented multi-task",
        "target": "5HT1A",
        "family": "gpcr",
        "n_total": len(results),
        "n_actives": int(sum(bool(x.get('is_active')) for x in results)),
        "n_valid": len(valid),
        "n_silent_fails": silent,
        "silent_fail_rate_pct": round(silent / len(results) * 100, 2),
        "inference_time_s": round(time.time() - t0, 1),
        "time_per_mol_s": round((time.time() - t0) / len(results), 3),
        "metrics": {
            "roc_auc": auc,
            "pr_auc": pr,
            "ef_1pct": ef1, "ef_5pct": ef5, "ef_10pct": ef10,
            "mean_prob_active": float(p[y == 1].mean()),
            "mean_prob_decoy": float(p[y == 0].mean()),
        },
        "baseline_comparison": baselines,
        "predictions": preds.tolist(),
        "model_path": str(CKPT_PATH),
    }
    out_path = PROJECT_ROOT / "data" / "gnn_fixed" / "ef_report_5ht1a_gnnv31.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
