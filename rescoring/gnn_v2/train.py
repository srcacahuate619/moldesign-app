"""
gnn_v2/train.py — Training script for GNN-v3 protein-ligand binding classifier.

Usage:
  python -m gnn_v2.train --epochs 200 --batch-size 16 --lr 1e-3
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import (
    average_precision_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from torch import nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader
from torch_geometric.data import Batch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from gnn_v2.data import PLComplexDataset
from gnn_v2.models import GNNv2Classifier, count_parameters

ARTIFACTS_DIR = PROJECT_ROOT / "rescoring" / "artifacts"


# ═══════════════════════════════════════════════════════════════════════
# Collate function for batches of dicts
# ═══════════════════════════════════════════════════════════════════════

def collate_complexes(batch: list[dict]) -> dict:
    """Collate a list of complex dicts into a batched dict."""
    proteins = [item["protein"] for item in batch]
    ligands = [item["ligand"] for item in batch]
    
    # Batch protein and ligand graphs
    prot_batch = Batch.from_data_list(proteins)
    lig_batch = Batch.from_data_list(ligands)
    
    # Re-index cross edges for batching
    cross_edges = []
    prot_offset = 0
    lig_offset = 0
    for i, item in enumerate(batch):
        cross = item["cross"]
        if cross.numel() > 0:
            reindexed = cross.clone()
            reindexed[0] += lig_offset  # ligand indices
            reindexed[1] += prot_offset  # protein indices
            cross_edges.append(reindexed)
        prot_offset += proteins[i].num_nodes
        lig_offset += ligands[i].num_nodes
    
    cross_batch = torch.cat(cross_edges, dim=1) if cross_edges else torch.empty((2, 0), dtype=torch.long)
    
    # Labels
    y = torch.tensor([item["y"] for item in batch], dtype=torch.float32)
    y_binary = torch.tensor([item["y_binary"] for item in batch], dtype=torch.long)
    
    return {
        "prot_x": prot_batch.x,
        "prot_edge_index": prot_batch.edge_index,
        "prot_pos": prot_batch.pos,
        "prot_batch": prot_batch.batch,
        "lig_x": lig_batch.x,
        "lig_edge_index": lig_batch.edge_index,
        "lig_pos": lig_batch.pos,
        "lig_batch": lig_batch.batch,
        "cross_edge_index": cross_batch,
        "y": y,
        "y_binary": y_binary,
    }


# ═══════════════════════════════════════════════════════════════════════
# Metrics
# ═══════════════════════════════════════════════════════════════════════

@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: str) -> dict:
    """Evaluate on validation/test set."""
    model.eval()
    all_logits = []
    all_labels = []
    
    for batch in loader:
        batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
        
        logits = model(
            batch["prot_x"], batch["prot_edge_index"],
            batch["lig_x"], batch["lig_edge_index"],
            batch["cross_edge_index"],
            lig_pos=batch.get("lig_pos"),
            prot_pos=batch.get("prot_pos"),
            lig_batch=batch["lig_batch"],
            prot_batch=batch["prot_batch"],
        )
        
        all_logits.append(logits.cpu())
        all_labels.append(batch["y_binary"].cpu())
    
    logits = torch.cat(all_logits)
    labels = torch.cat(all_labels)
    probs = torch.sigmoid(logits)
    
    # ROC-AUC
    try:
        roc_auc = roc_auc_score(labels.numpy(), probs.numpy())
    except ValueError:
        roc_auc = 0.5
    
    # PR-AUC
    try:
        pr_auc = average_precision_score(labels.numpy(), probs.numpy())
    except ValueError:
        pr_auc = 0.0
    
    # Accuracy at threshold 0.5
    preds = (probs > 0.5).long()
    acc = (preds == labels).float().mean()
    
    # Spearman (on full pKi labels)
    from scipy.stats import spearmanr
    spearman = spearmanr(logits.numpy(), batch["y"].cpu().numpy())[0] if hasattr(batch, "y") else 0.0
    
    # Binary cross-entropy
    bce = F.binary_cross_entropy(probs, labels.float())
    
    return {
        "roc_auc": float(roc_auc),
        "pr_auc": float(pr_auc),
        "accuracy": float(acc),
        "bce": float(bce),
        "spearman": float(spearman) if not math.isnan(spearman) else 0.0,
    }


# ═══════════════════════════════════════════════════════════════════════
# Training
# ═══════════════════════════════════════════════════════════════════════

def train_epoch(model, loader, optimizer, device):
    model.train()
    total_loss = 0
    for batch in loader:
        batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
        
        optimizer.zero_grad()
        logits = model(
            batch["prot_x"], batch["prot_edge_index"],
            batch["lig_x"], batch["lig_edge_index"],
            batch["cross_edge_index"],
            lig_pos=batch.get("lig_pos"),
            prot_pos=batch.get("prot_pos"),
            lig_batch=batch["lig_batch"],
            prot_batch=batch["prot_batch"],
        )
        
        loss = F.binary_cross_entropy_with_logits(logits, batch["y_binary"].float())
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        
        total_loss += loss.item()
    
    return total_loss / len(loader)


def main():
    parser = argparse.ArgumentParser(description="Train GNN-v2")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--patience", type=int, default=30)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=0)
    args = parser.parse_args()
    
    # Setup
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    if args.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    
    print("=" * 55)
    print("  GNN-v2 Training")
    print(f"  Device: {device}")
    print(f"  Epochs: {args.epochs}, Batch: {args.batch_size}, LR: {args.lr}")
    print("=" * 55)
    
    # Load dataset
    print("\nLoading dataset...")
    ds = PLComplexDataset()
    print(f"  {len(ds)} complexes loaded")
    
    # Split: 80/10/10 stratified by binder class
    all_labels = np.array([d["y_binary"] for d in ds])
    all_pki = np.array([d["y"] for d in ds])
    
    # Stratified split by pKi bins
    pki_bins = np.digitize(all_pki, bins=[5, 6, 7, 8, 9])
    
    train_idx, test_idx = train_test_split(
        np.arange(len(ds)), test_size=0.2, random_state=args.seed,
        stratify=pki_bins,
    )
    val_idx, test_idx = train_test_split(
        test_idx, test_size=0.5, random_state=args.seed,
        stratify=pki_bins[test_idx],
    )
    
    print(f"  Train: {len(train_idx)}, Val: {len(val_idx)}, Test: {len(test_idx)}")
    print(f"  Train binders: {all_labels[train_idx].sum()} / {len(train_idx)}")
    print(f"  Val binders:   {all_labels[val_idx].sum()} / {len(val_idx)}")
    print(f"  Test binders:  {all_labels[test_idx].sum()} / {len(test_idx)}")
    
    train_ds = [ds[i] for i in train_idx]
    val_ds = [ds[i] for i in val_idx]
    test_ds = [ds[i] for i in test_idx]
    
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                              collate_fn=collate_complexes, num_workers=args.workers)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                            collate_fn=collate_complexes, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False,
                             collate_fn=collate_complexes, num_workers=0)
    
    # Model
    model = GNNv2Classifier(
        prot_in=ds.num_features_prot,
        lig_in=ds.num_features_lig,
        hidden_dim=args.hidden_dim,
        dropout=args.dropout,
    ).to(device)
    
    print(f"\nModel: {count_parameters(model):,} parameters")
    
    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-5)
    
    best_val_auc = 0.0
    best_epoch = 0
    patience_counter = 0
    
    print("\nTraining...")
    t0 = time.time()
    
    for epoch in range(1, args.epochs + 1):
        train_loss = train_epoch(model, train_loader, optimizer, device)
        val_metrics = evaluate(model, val_loader, device)
        scheduler.step()
        
        if val_metrics["roc_auc"] > best_val_auc:
            best_val_auc = val_metrics["roc_auc"]
            best_epoch = epoch
            patience_counter = 0
            
            # Save checkpoint
            ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_metrics": val_metrics,
                "config": vars(args),
            }, ARTIFACTS_DIR / "gnn_v3_best.pt")
        else:
            patience_counter += 1
        
        if epoch % 5 == 0 or epoch == 1:
            elapsed = time.time() - t0
            print(f"  Epoch {epoch:3d} | loss={train_loss:.4f} | "
                  f"val_auc={val_metrics['roc_auc']:.4f} | "
                  f"val_pr={val_metrics['pr_auc']:.4f} | "
                  f"lr={scheduler.get_last_lr()[0]:.1e} | "
                  f"best={best_val_auc:.4f} (ep {best_epoch}) | "
                  f"{elapsed:.0f}s")
        
        if patience_counter >= args.patience:
            print(f"\nEarly stopping at epoch {epoch} (patience={args.patience})")
            break
    
    # Final evaluation on test set
    print("\n" + "=" * 55)
    print("  Final Evaluation (Test Set)")
    print("=" * 55)
    
    # Load best model
    checkpoint = torch.load(ARTIFACTS_DIR / "gnn_v3_best.pt", map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    
    test_metrics = evaluate(model, test_loader, device)
    print(f"  ROC-AUC:  {test_metrics['roc_auc']:.4f}")
    print(f"  PR-AUC:   {test_metrics['pr_auc']:.4f}")
    print(f"  Accuracy: {test_metrics['accuracy']:.4f}")
    print(f"  BCE:      {test_metrics['bce']:.4f}")
    print(f"  Best epoch: {checkpoint['epoch']}")
    
    # Save results
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    results = {
        "test_metrics": {k: round(v, 4) for k, v in test_metrics.items()},
        "best_val_auc": round(best_val_auc, 4),
        "best_epoch": best_epoch,
        "n_params": count_parameters(model),
        "n_train": len(train_idx),
        "n_val": len(val_idx),
        "n_test": len(test_idx),
        "config": vars(args),
    }
    with open(ARTIFACTS_DIR / "gnn_v3_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved: {ARTIFACTS_DIR / 'gnn_v3_results.json'}")
    print(f"Model saved: {ARTIFACTS_DIR / 'gnn_v3_best.pt'}")


if __name__ == "__main__":
    main()
