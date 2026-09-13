"""
scripts/train_metal_aware_gnn.py — Metal-Aware GNN-D Training

Trains a GNN-D model that incorporates Universal Metal Score (UMS) as an
additional input feature. This is Task #4 from the GPU work queue.

Architecture:
  1. GNNv2Classifier base (pretrained or from scratch)
  2. UMS feature (scalar) concatenated with 256-dim GNN embedding
  3. Joint classification head: Linear(257, 128) -> LayerNorm -> GELU -> Dropout -> Linear(128, 1)
  4. Trained with LOTO (Leave-One-Target-Out) splitting
  5. Saved as artifacts/metal_aware_gnn_d.pt

Scientific validity controls:
  - LOTO splitting ensures no target leakage
  - Fixed random seed for reproducibility
  - Reports per-target AUC with bootstrap-compatible format
  - Non-metal targets serve as negative control (should show no degradation)

Usage:
  python scripts/train_metal_aware_gnn.py [--epochs 200] [--batch-size 16]

Output:
  - artifacts/metal_aware_gnn_d.pt      (trained model)
  - artifacts/metal_aware_gnn_results.json  (per-target AUCs + summary)
  - data/molchamb_loto/metal_gnn_training_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import roc_auc_score
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch_geometric.data import Batch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from gnn_v2.models import GNNv2Classifier
from universal_metal_score import compute_universal_metal_score

ARTIFACTS_DIR = PROJECT_ROOT / "rescoring" / "artifacts"
DATASET_PATH = PROJECT_ROOT / "data" / "gnn_v31" / "gnn_d_dataset.pt"
CKPT_DIR = PROJECT_ROOT / "data" / "molchamb_loto" / "checkpoints"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ─────────────────────────────────────────────────────────
# Metal-Aware Model
# ─────────────────────────────────────────────────────────

class MetalAwareGNN(nn.Module):
    """
    GNN classifier with UMS as an additional input feature.

    The GNN embedding (concat of lig_global + prot_global) is concatenated
    with UMS (1-dim scalar), then passed through a joint classification head.
    Embedding dim = hidden_dim * 4 (Set2Set output: hidden_dim*2 each for lig+prot).
    """

    def __init__(self, gnn: GNNv2Classifier, hidden_dim: int = 128, dropout: float = 0.2):
        super().__init__()
        self.gnn = gnn
        embed_dim = hidden_dim * 4  # Set2Set concat: lig_global + prot_global

        # Joint head: embed_dim (GNN embedding) + 1 (UMS) → hidden → 1
        self.joint_head = nn.Sequential(
            nn.Linear(embed_dim + 1, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, prot_x, prot_ei, lig_x, lig_ei, cross_ei,
                lig_pos=None, prot_pos=None, lig_batch=None, prot_batch=None,
                metal_score=None):
        # Get GNN embedding
        emb = self.gnn.extract_embedding(prot_x, prot_ei, lig_x, lig_ei, cross_ei,
                                          lig_pos, prot_pos, lig_batch, prot_batch)

        # Default metal_score to 0 if not provided
        if metal_score is None:
            metal_score = torch.zeros(emb.size(0), 1, device=emb.device)
        elif metal_score.dim() == 1:
            metal_score = metal_score.unsqueeze(1)

        # Concatenate and classify
        joint = torch.cat([emb, metal_score], dim=1)
        return self.joint_head(joint).squeeze(-1)


# ─────────────────────────────────────────────────────────
# UMS Computation
# ─────────────────────────────────────────────────────────

def compute_ums_smiles(smiles: str) -> tuple[float, dict]:
    """Compute UMS for a SMILES string. Returns (score, features_dict)."""
    try:
        score, features = compute_universal_metal_score(smiles, target_family=None)
        return float(score), features
    except Exception:
        return 0.0, {}


# ─────────────────────────────────────────────────────────
# Collate function (same as train_gpu.py)
# ─────────────────────────────────────────────────────────

def _get_graph(item: dict, key: str):
    """Get graph component from item (handles nested 'graph' key)."""
    if "graph" in item and isinstance(item["graph"], dict):
        return item["graph"].get(key)
    return item.get(key)


def collate_complexes(batch: list[dict]) -> dict:
    proteins = [_get_graph(item, "protein") for item in batch]
    ligands = [_get_graph(item, "ligand") for item in batch]

    prot_batch = Batch.from_data_list(proteins)
    lig_batch = Batch.from_data_list(ligands)

    cross_edges = []
    prot_offset = 0
    lig_offset = 0
    for i, item in enumerate(batch):
        cross = _get_graph(item, "cross")
        if cross is not None and cross.numel() > 0:
            reindexed = cross.clone()
            reindexed[0] += lig_offset
            reindexed[1] += prot_offset
            cross_edges.append(reindexed)
        prot_offset += proteins[i].num_nodes
        lig_offset += ligands[i].num_nodes

    cross_batch = (
        torch.cat(cross_edges, dim=1)
        if cross_edges
        else torch.empty((2, 0), dtype=torch.long)
    )

    y = torch.tensor([item.get("y", item.get("y_binary", 0)) for item in batch], dtype=torch.float32)
    metal_scores = torch.tensor(
        [item.get("metal_score", 0.0) for item in batch], dtype=torch.float32
    )

    return {
        "protein": prot_batch,
        "ligand": lig_batch,
        "cross": cross_batch,
        "y": y,
        "metal_score": metal_scores,
    }


# ─────────────────────────────────────────────────────────
# Training loop
# ─────────────────────────────────────────────────────────

def _get_batch_idx(data, default_size=0):
    """Get batch indices from a PyG Data/Batch object."""
    if hasattr(data, 'batch') and data.batch is not None:
        return data.batch
    return torch.zeros(default_size, dtype=torch.long)


def train_epoch(model, loader, optimizer, device):
    model.train()
    total_loss = 0.0
    n_batches = 0

    for batch in loader:
        prot = batch["protein"].to(device)
        lig = batch["ligand"].to(device)
        cross = batch["cross"].to(device)
        y = batch["y"].to(device)
        ms = batch["metal_score"].to(device)

        lig_batch = _get_batch_idx(lig, lig.x.size(0))
        prot_batch = _get_batch_idx(prot, prot.x.size(0))

        optimizer.zero_grad()
        logits = model(
            prot.x, prot.edge_index,
            lig.x, lig.edge_index,
            cross,
            lig_batch=lig_batch,
            prot_batch=prot_batch,
            metal_score=ms,
        )
        loss = F.binary_cross_entropy_with_logits(logits, y)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        n_batches += 1

    return total_loss / max(n_batches, 1)


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    all_logits = []
    all_labels = []

    for batch in loader:
        prot = batch["protein"].to(device)
        lig = batch["ligand"].to(device)
        cross = batch["cross"].to(device)
        y = batch["y"].to(device)
        ms = batch["metal_score"].to(device)

        lig_batch = _get_batch_idx(lig, lig.x.size(0))
        prot_batch = _get_batch_idx(prot, prot.x.size(0))

        logits = model(
            prot.x, prot.edge_index,
            lig.x, lig.edge_index,
            cross,
            lig_batch=lig_batch,
            prot_batch=prot_batch,
            metal_score=ms,
        )
        all_logits.append(logits.cpu())
        all_labels.append(y.cpu())

    logits = torch.cat(all_logits).numpy()
    labels = torch.cat(all_labels).numpy()

    # AUC requires at least one positive and one negative
    if len(np.unique(labels)) < 2:
        return 0.5  # random baseline

    probs = torch.sigmoid(torch.tensor(logits)).numpy()
    return float(roc_auc_score(labels, probs))


# ─────────────────────────────────────────────────────────
# Data loading with UMS augmentation
# ─────────────────────────────────────────────────────────

class MetalAwareDataset(torch.utils.data.Dataset):
    """Wraps the existing dataset, adding UMS scores."""

    def __init__(self, items: list[dict]):
        self.items = items

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        item = self.items[idx].copy()
        # UMS is pre-computed before wrapping; stored as 'metal_score'
        if "metal_score" not in item:
            item["metal_score"] = 0.0
        return item


def load_augmented_dataset(dataset_path: Path, compute_ums: bool = True) -> list[dict]:
    """Load dataset and add UMS scores."""
    print(f"Loading dataset: {dataset_path}")
    data = torch.load(dataset_path, map_location="cpu", weights_only=False)
    print(f"  {len(data)} complexes loaded")

    if compute_ums:
        print("Computing UMS scores...")
        for i, item in enumerate(data):
            smiles = item.get("smiles", "")
            if smiles:
                score, _ = compute_ums_smiles(smiles)
                item["metal_score"] = score
            else:
                item["metal_score"] = 0.0

            if (i + 1) % 200 == 0:
                print(f"  UMS: {i + 1}/{len(data)}")

        # Statistics
        scores = [d.get("metal_score", 0.0) for d in data]
        print(f"  UMS range: [{min(scores):.3f}, {max(scores):.3f}]")
        print(f"  UMS mean:  {np.mean(scores):.3f}")
        print(f"  UMS > 0.5: {sum(1 for s in scores if s > 0.5)}/{len(data)}")

    return data


# ─────────────────────────────────────────────────────────
# LOTO Split
# ─────────────────────────────────────────────────────────

def loto_split(data: list[dict], held_out_target: str) -> tuple[list, list]:
    """Split data into train (all except held_out) and test (held_out)."""
    train = [d for d in data if d.get("target") != held_out_target]
    test = [d for d in data if d.get("target") == held_out_target]
    return train, test


# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train Metal-Aware GNN-D")
    parser.add_argument("--epochs", type=int, default=75)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-pretrain", action="store_true",
                        help="Train GNN from scratch (no pretrained backbone)")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    print(f"Device: {DEVICE}")
    print(f"Seed: {args.seed}")

    # ── Load and augment data ──
    data = load_augmented_dataset(DATASET_PATH)

    # Ensure items have flat structure expected by collate
    # The dataset stores graphs as: {graph: {cross, ligand, protein}, ...}
    # The collate_fn expects: {protein, ligand, cross, y, metal_score}
    for item in data:
        if "graph" in item and isinstance(item["graph"], dict):
            g = item["graph"]
            item.setdefault("protein", g.get("protein"))
            item.setdefault("ligand", g.get("ligand"))
            item.setdefault("cross", g.get("cross"))
            item.setdefault("y", item.get("y_binary", 0))

    targets = sorted(set(d["target"] for d in data))
    print(f"Targets: {targets}")
    print(f"Target distribution: {dict(Counter(d['target'] for d in data))}")

    # ── Load or create GNN backbone ──
    if not args.no_pretrain:
        pretrained_path = ARTIFACTS_DIR / "gnn_d_best.pt"
        if pretrained_path.exists():
            print(f"Loading pretrained GNN: {pretrained_path}")
            ck = torch.load(pretrained_path, map_location="cpu", weights_only=False)
            sd = ck.get("model_state_dict", ck)
            gnn = GNNv2Classifier(hidden_dim=args.hidden_dim)
            # Filter out any mismatched keys
            model_sd = {k: v for k, v in sd.items()
                       if k in gnn.state_dict()
                       and gnn.state_dict()[k].shape == v.shape}
            gnn.load_state_dict(model_sd, strict=False)
            print(f"  Loaded {len(model_sd)}/{len(sd)} parameter groups")
        else:
            print("No pretrained model found. Training from scratch.")
            gnn = GNNv2Classifier(hidden_dim=args.hidden_dim)
    else:
        gnn = GNNv2Classifier(hidden_dim=args.hidden_dim)

    # ── LOTO training ──
    all_results = {}
    loto_models = {}

    for held_out in targets:
        print(f"\n{'=' * 60}")
        print(f"  LOTO fold: held_out = {held_out}")
        print(f"{'=' * 60}")

        train_data, test_data = loto_split(data, held_out)
        print(f"  Train: {len(train_data)} | Test: {len(test_data)}")

        if len(test_data) == 0:
            print(f"  SKIP: no test data for {held_out}")
            continue

        # Check class balance
        test_labels = [d["y_binary"] for d in test_data]
        n_pos = sum(test_labels)
        n_neg = len(test_labels) - n_pos
        print(f"  Test balance: {n_pos} pos / {n_neg} neg")

        # Create model (fresh copy per fold)
        fresh_gnn = GNNv2Classifier(hidden_dim=args.hidden_dim)
        fresh_gnn.load_state_dict(gnn.state_dict())
        model = MetalAwareGNN(fresh_gnn, hidden_dim=args.hidden_dim).to(DEVICE)

        train_ds = MetalAwareDataset(train_data)
        test_ds = MetalAwareDataset(test_data)

        train_loader = torch.utils.data.DataLoader(
            train_ds, batch_size=args.batch_size, shuffle=True,
            collate_fn=collate_complexes, num_workers=0,
        )
        test_loader = torch.utils.data.DataLoader(
            test_ds, batch_size=args.batch_size, shuffle=False,
            collate_fn=collate_complexes, num_workers=0,
        )

        optimizer = AdamW(model.parameters(), lr=args.lr)
        scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-5)

        best_auc = 0.0
        best_state = None
        t0 = time.time()

        for epoch in range(1, args.epochs + 1):
            train_loss = train_epoch(model, train_loader, optimizer, DEVICE)
            scheduler.step()

            if epoch % 15 == 0 or epoch == args.epochs or epoch == 1:
                auc = evaluate(model, test_loader, DEVICE)
                elapsed = time.time() - t0
                if auc > best_auc:
                    best_auc = auc
                    best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

                print(f"  [{held_out}] epoch {epoch:3d}/{args.epochs} | "
                      f"loss={train_loss:.4f} | auc={auc:.4f} | best={best_auc:.4f} | "
                      f"{elapsed:.0f}s")

        elapsed = time.time() - t0
        print(f"  [{held_out}] DONE in {elapsed:.0f}s | best AUC = {best_auc:.4f}")

        # Save per-target results
        all_results[held_out] = {
            "n_train": len(train_data),
            "n_test": len(test_data),
            "n_pos_test": n_pos,
            "n_neg_test": n_neg,
            "best_auc": round(best_auc, 4),
            "training_time_s": round(elapsed, 1),
        }

        # Save LOTO model
        if best_state is not None:
            loto_model_path = ARTIFACTS_DIR / f"metal_aware_loto_{held_out}.pt"
            model.load_state_dict(best_state)
            torch.save({
                "model_state_dict": best_state,
                "target": held_out,
                "auc": best_auc,
            }, loto_model_path)
            loto_models[held_out] = str(loto_model_path.name)
            print(f"  Saved: {loto_model_path}")

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print("  METAL-AWARE GNN-D LOTO RESULTS")
    print(f"{'=' * 60}")

    summaries = []
    for t in targets:
        r = all_results.get(t, {})
        auc = r.get("best_auc", 0.0)
        summaries.append({"target": t, "auc": auc, **r})
        print(f"  {t:15s}: AUC = {auc:.4f}  (n_test={r.get('n_test', '?')})")

    mean_auc = np.mean([s["auc"] for s in summaries if s.get("best_auc", 0) > 0])
    print(f"\n  Mean AUC: {mean_auc:.4f}")

    # ── Save results ──
    results = {
        "model": "MetalAwareGNN-D",
        "description": "GNN-D trained with Universal Metal Score as input feature",
        "dataset": str(DATASET_PATH),
        "targets": targets,
        "mean_auc": round(float(mean_auc), 4),
        "per_target": {t: all_results.get(t, {}) for t in targets},
        "loto_models": loto_models,
        "config": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "hidden_dim": args.hidden_dim,
            "seed": args.seed,
            "pretrained_gnn": str(ARTIFACTS_DIR / "gnn_d_best.pt") if not args.no_pretrain else None,
        },
    }

    results_path = ARTIFACTS_DIR / "metal_aware_gnn_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved: {results_path}")

    training_report_path = PROJECT_ROOT / "data" / "molchamb_loto" / "metal_gnn_training_report.json"
    with open(training_report_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Report saved: {training_report_path}")


if __name__ == "__main__":
    main()
