"""
scripts/experiment_ecif_clgnn.py — Camino 2: CL-GNN + ECIF (versión simple).

Estrategia:
  1. Reusa el contrastive pretraining existente (solo graph, no ECIF en pretrain)
  2. Finetune GNNv31Classifier (hidden_dim=128, ecif_in=152, delta_head) con ECIF docked
  3. Eval 5HT1A

ECIF encoder (152->64, ~18K params) aprende desde cero durante finetune — es suficientemente chico.

Usage:
  python scripts/experiment_ecif_clgnn.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))

from gnn_v2.data import PLComplexDataset
from gnn_v2.models import GNNv31Classifier, ContrastiveGNN, count_parameters
from gnn_v2.train import collate_complexes

ARTIFACTS = PROJECT_ROOT / "rescoring" / "artifacts"
ECIF_PATH = PROJECT_ROOT / "data" / "gnn_v31" / "ecif_pdbbind_docked.npz"
HIDDEN_DIM = 128
SEED = 42


def finetune(epochs=100, batch_size=16, lr=5e-4):
    print("=" * 55)
    print("  GNNv31 + ECIF docked + CL pretrain: Finetune")
    print("=" * 55)

    # Dataset
    ds = PLComplexDataset()
    n = len(ds)
    # Use same split as original CL finetune for comparability
    all_labels = np.array([d["y_binary"] for d in ds])
    from sklearn.model_selection import train_test_split
    train_idx, val_idx = train_test_split(
        np.arange(n), test_size=0.2, random_state=SEED,
        stratify=np.digitize([d["y"] for d in ds], bins=[5, 6, 7, 8, 9]),
    )
    print(f"  Train: {len(train_idx)}, Val: {len(val_idx)}")

    # ECIF: load docked, z-score
    ecif_data = np.load(ECIF_PATH)
    ecif_X = ecif_data["X"].astype(np.float32)
    ecif_mean = ecif_X.mean(axis=0, keepdims=True)
    ecif_std = ecif_X.std(axis=0, keepdims=True) + 1e-8
    ecif_X = (ecif_X - ecif_mean) / ecif_std
    ecif_t_full = torch.from_numpy(ecif_X).float()
    print(f"  ECIF: {ecif_X.shape}")

    # Proper ECIF alignment: create indexed dataset
    class IndexedComplexDataset:
        def __init__(self, base_ds, indices, ecif_t):
            self.base = base_ds
            self.indices = indices
            self.ecif = ecif_t
        def __len__(self):
            return len(self.indices)
        def __getitem__(self, i):
            idx = self.indices[i]
            item = self.base[idx]
            item["_idx"] = idx  # track original index
            item["_ecif"] = self.ecif[idx]
            return item

    def collate_with_ecif(batch):
        # Extract ECIF before collation
        ecif_vectors = torch.stack([b.pop("_ecif") for b in batch], dim=0)
        idxs = [b.pop("_idx") for b in batch]
        collated = collate_complexes(batch)
        collated["ecif"] = ecif_vectors
        return collated

    train_ds = IndexedComplexDataset(ds, train_idx, ecif_t_full)
    val_ds = IndexedComplexDataset(ds, val_idx, ecif_t_full)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                              collate_fn=collate_with_ecif)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False,
                            collate_fn=collate_with_ecif)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = GNNv31Classifier(hidden_dim=HIDDEN_DIM, ecif_in=152, use_delta_head=True).to(device)
    print(f"  Params: {count_parameters(model):,}")

    # Load CL pretrained graph encoders only (not ECIF)
    pt_path = ARTIFACTS / "contrastive_v31_pretrained.pt"
    if pt_path.exists():
        ck = torch.load(pt_path, map_location="cpu", weights_only=False)
        c_model = ContrastiveGNN(hidden_dim=HIDDEN_DIM)
        c_model.load_state_dict(ck["model_state_dict"])
        # Copy graph encoders to GNNv31Classifier
        model.prot_encoder.load_state_dict(c_model.prot_encoder.state_dict())
        model.lig_encoder.load_state_dict(c_model.lig_encoder.state_dict())
        model.cross_attn.load_state_dict(c_model.cross_attn.state_dict())
        print(f"  CL graph encoders loaded (epoch {ck['epoch']})")

    optim = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optim, T_max=epochs)

    best_val_auc = 0.0
    t0 = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        total = 0
        for batch in train_loader:
            batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
            optim.zero_grad()
            prob_logit, delta_pred = model(
                batch["prot_x"], batch["prot_edge_index"],
                batch["lig_x"], batch["lig_edge_index"],
                batch["cross_edge_index"],
                lig_pos=batch.get("lig_pos"), prot_pos=batch.get("prot_pos"),
                lig_batch=batch["lig_batch"], prot_batch=batch["prot_batch"],
                ecif=batch["ecif"],
            )
            loss = F.binary_cross_entropy_with_logits(prob_logit, batch["y_binary"].float())
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optim.step()
            total += loss.item()

        scheduler.step()

        # Val
        model.eval()
        val_logits, val_labels = [], []
        with torch.no_grad():
            for batch in val_loader:
                b = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
                logits, _ = model(
                    b["prot_x"], b["prot_edge_index"], b["lig_x"], b["lig_edge_index"],
                    b["cross_edge_index"], lig_pos=b.get("lig_pos"), prot_pos=b.get("prot_pos"),
                    lig_batch=b["lig_batch"], prot_batch=b["prot_batch"],
                    ecif=b["ecif"],
                )
                val_logits.append(logits.cpu())
                val_labels.append(b["y_binary"].cpu())
        vp = torch.cat(val_logits).sigmoid()
        vl = torch.cat(val_labels)
        try:
            val_auc = roc_auc_score(vl.numpy(), vp.numpy())
        except ValueError:
            val_auc = 0.5

        if val_auc > best_val_auc:
            best_val_auc = val_auc
            torch.save(model.state_dict(), ARTIFACTS / "gnn_v31_ecif_cl_best.pt")
        if epoch % 10 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d} | loss={total/len(train_loader):.4f} | val_auc={val_auc:.4f} | best={best_val_auc:.4f} | {time.time()-t0:.0f}s")

    print(f"\nDone in {(time.time()-t0)/60:.1f} min")
    print(f"  Best val AUC: {best_val_auc:.4f}")


def evaluate_5ht1a():
    print("=" * 55)
    print("  GNNv31+ECIF+CL: 5HT1A Eval")
    print("=" * 55)

    import json, tempfile, shutil, importlib.util
    from torch_geometric.data import Batch

    # Load build_graph_from_pose from sibling module
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from contrastive_v31 import build_graph_from_pose

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = GNNv31Classifier(hidden_dim=HIDDEN_DIM, ecif_in=152, use_delta_head=False).to(device)
    ck_path = ARTIFACTS / "gnn_v31_ecif_cl_best.pt"
    state = torch.load(ck_path, map_location=device, weights_only=False)
    sd = state.get("model_state_dict", state)
    model.load_state_dict(sd, strict=False)
    model.to(device).eval()
    print(f"  Loaded: {ck_path.name}")

    # ECIF normalization (same stats used during finetune)
    ecif_data = np.load(ECIF_PATH)
    ecif_mean = ecif_data["X"].astype(np.float32).mean(axis=0, keepdims=True)
    ecif_std = ecif_data["X"].astype(np.float32).std(axis=0, keepdims=True) + 1e-8

    # Feature keys for 5HT1A inline ECIF
    from feature_extractor import ALL_3D_FEATURES
    ecif_keys = sorted([k for k in ALL_3D_FEATURES if k.startswith("shell_") or k.startswith("ecif_")])

    target_pdb = PROJECT_ROOT / "data" / "targets" / "7E2Y.pdb"
    ck_json = PROJECT_ROOT / "data" / "gnn_v31" / "checkpoints" / "benchmark_checkpoint_5ht1a.json"
    with open(ck_json) as f:
        ck = json.load(f)
    results = ck["results"]
    labels = np.array([int(bool(r.get("is_active", False))) for r in results])
    print(f"  Benchmark: {len(results)} mols, actives={int(labels.sum())}")

    preds = np.zeros(len(results), dtype=np.float32)
    silent = 0
    t0 = time.time()

    for i, ent in enumerate(results):
        smi = ent.get("smiles", "")
        pose = ent.get("pose_pdbqt", "")
        feats = ent.get("features", {}) or {}
        # Build ECIF vector
        v = np.zeros(152, dtype=np.float32)
        if feats:
            for j, k in enumerate(ecif_keys):
                try:
                    v[j] = float(feats.get(k, 0.0))
                except (TypeError, ValueError):
                    pass
            v = (v - ecif_mean[0]) / ecif_std[0]
            v = np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)
        ecif_t = torch.from_numpy(v).float().unsqueeze(0).to(device)

        try:
            graph = build_graph_from_pose(pose, str(target_pdb), smi)
            if graph is None:
                preds[i] = 0.5; silent += 1; continue
            prot_b = Batch.from_data_list([graph["protein"]]).to(device)
            lig_b = Batch.from_data_list([graph["ligand"]]).to(device)
            with torch.no_grad():
                logits, _ = model(
                    prot_b.x, prot_b.edge_index, lig_b.x, lig_b.edge_index,
                    graph["cross"].to(device), lig_batch=lig_b.batch, prot_batch=prot_b.batch,
                    ecif=ecif_t,
                )
                preds[i] = float(torch.sigmoid(logits).item())
        except Exception:
            preds[i] = 0.5; silent += 1

        if (i + 1) % 500 == 0 or i == len(results) - 1:
            rate = (i + 1) / (time.time() - t0 + 1e-6)
            print(f"  [{i+1}/{len(results)}] silent={silent} rate={rate:.1f}/s")

    valid = np.where(preds != 0.5)[0]
    y, p = labels[valid], preds[valid]
    auc = float(roc_auc_score(y, p))
    print(f"\n  5HT1A AUC = {auc:.4f}")
    print(f"  Mean P(active)={p[y==1].mean():.4f}  P(decoy)={p[y==0].mean():.4f}")
    print(f"  Time: {time.time()-t0:.0f}s")

    # Save predictions
    for i, v in enumerate(preds):
        results[i]["gnn_v31_ecif_cl_prob"] = round(float(v), 6)
    out_path = PROJECT_ROOT / "data" / "gnn_v31" / "checkpoints" / "benchmark_checkpoint_5ht1a.json"
    shutil.copy(out_path, str(out_path) + ".bak_ecif") if not Path(str(out_path)+".bak_ecif").exists() else None
    with open(out_path, "w") as f:
        json.dump(ck, f, indent=2)
    print(f"  Saved predictions to checkpoint")
    return auc


if __name__ == "__main__":
    import random
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--finetune", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--full-pipeline", action="store_true")
    args = parser.parse_args()

    if args.full_pipeline or not any([args.finetune, args.evaluate]):
        finetune()
        evaluate_5ht1a()
    elif args.finetune:
        finetune()
    elif args.evaluate:
        evaluate_5ht1a()
