"""
gnn_v2/train_gpu.py

COPIA GPU-AWARE de gnn_v2/train.py.
NO modifica el original. La ÚNICA diferencia es:
  1. Los pesos del modelo se guardan en artifacts/gpu/ en lugar de artifacts/
  2. Se añade --gpu-data-dir para apuntar al dataset generado por Vina-GPU

La arquitectura del modelo (GNNv2Classifier), el entrenamiento,
el optimizador, el scheduler y las métricas son 100% idénticos.

Uso:
  cd rescoring
  python -m gnn_v2.train_gpu --epochs 200 --batch-size 16 --lr 1e-3

El modelo resultante se guarda en:
  artifacts/gpu/gnn_v3_best.pt
  artifacts/gpu/gnn_v3_results.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, roc_auc_score
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

# ── ÚNICA diferencia: GPU artifacts dir ──────────────────────────────────
GPU_ARTIFACTS_DIR = PROJECT_ROOT / "rescoring" / "artifacts" / "gpu"
GPU_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


# ── Collate function (idéntica al original) ──────────────────────────────
def collate_complexes(batch: list[dict]) -> dict:
    """Collate a list of complex dicts into a batched dict."""
    proteins = [item["protein"] for item in batch]
    ligands = [item["ligand"] for item in batch]

    prot_batch = Batch.from_data_list(proteins)
    lig_batch = Batch.from_data_list(ligands)

    cross_edges = []
    prot_offset = 0
    lig_offset = 0
    for i, item in enumerate(batch):
        cross = item["cross"]
        if cross.numel() > 0:
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

    y = torch.tensor([item["y"] for item in batch], dtype=torch.float32)
    y_binary = torch.tensor(
        [item["y_binary"] for item in batch], dtype=torch.long
    )

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


# ── Metrics (idénticas al original) ─────────────────────────────────────
@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: str) -> dict:
    """Evaluate on validation/test set."""
    model.eval()
    all_logits = []
    all_labels = []

    for batch in loader:
        batch = {
            k: v.to(device) if isinstance(v, torch.Tensor) else v
            for k, v in batch.items()
        }
        logits = model(
            batch["prot_x"],
            batch["prot_edge_index"],
            batch["lig_x"],
            batch["lig_edge_index"],
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

    try:
        roc_auc = roc_auc_score(labels.numpy(), probs.numpy())
    except ValueError:
        roc_auc = 0.5

    try:
        pr_auc = average_precision_score(labels.numpy(), probs.numpy())
    except ValueError:
        pr_auc = 0.0

    preds = (probs > 0.5).long()
    acc = (preds == labels).float().mean()
    bce = F.binary_cross_entropy(probs, labels.float())

    return {
        "roc_auc": float(roc_auc),
        "pr_auc": float(pr_auc),
        "accuracy": float(acc),
        "bce": float(bce),
    }


def train_epoch(model, loader, optimizer, device):
    model.train()
    total_loss = 0
    for batch in loader:
        batch = {
            k: v.to(device) if isinstance(v, torch.Tensor) else v
            for k, v in batch.items()
        }
        optimizer.zero_grad()
        logits = model(
            batch["prot_x"],
            batch["prot_edge_index"],
            batch["lig_x"],
            batch["lig_edge_index"],
            batch["cross_edge_index"],
            lig_pos=batch.get("lig_pos"),
            prot_pos=batch.get("prot_pos"),
            lig_batch=batch["lig_batch"],
            prot_batch=batch["prot_batch"],
        )
        loss = F.binary_cross_entropy_with_logits(
            logits, batch["y_binary"].float()
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        total_loss += loss.item()
    return total_loss / len(loader)


def main():
    parser = argparse.ArgumentParser(
        description="Train GNN-v2 with GPU-docked poses"
    )
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
    # ── Argumento nuevo: apunta al dataset GPU ──
    parser.add_argument(
        "--gpu-data-dir",
        type=str,
        default=None,
        help="Directorio con poses PDBQT generadas por Vina-GPU. "
             "Si no se especifica, busca en data/gpu_poses/.",
    )
    args = parser.parse_args()

    # Setup
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    if args.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    print(f"[GPU Train] Using device: {device}")
    print(f"[GPU Train] Output: {GPU_ARTIFACTS_DIR}")

    # Dataset — usa gpu_data_dir si se especificó
    data_dir = (
        Path(args.gpu_data_dir)
        if args.gpu_data_dir
        else PROJECT_ROOT / "data" / "gpu_poses"
    )
    print(f"[GPU Train] Loading dataset from: {data_dir}")

    # Override REDOCK_DIR in gnn_v2.data so it parses GPU poses instead of CPU poses
    import gnn_v2.data as gnn_data
    gnn_data.REDOCK_DIR = data_dir / "pdbs"
    
    dataset = PLComplexDataset(root=str(data_dir))

    # Split idéntico al original (70/15/15)
    n = len(dataset)
    idx = list(range(n))
    random.shuffle(idx)
    train_end = int(0.70 * n)
    val_end = int(0.85 * n)
    train_idx = idx[:train_end]
    val_idx = idx[train_end:val_end]
    test_idx = idx[val_end:]

    train_loader = DataLoader(
        [dataset[i] for i in train_idx],
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=collate_complexes,
        num_workers=args.workers,
    )
    val_loader = DataLoader(
        [dataset[i] for i in val_idx],
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=collate_complexes,
        num_workers=args.workers,
    )
    test_loader = DataLoader(
        [dataset[i] for i in test_idx],
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=collate_complexes,
        num_workers=args.workers,
    )

    print(f"[GPU Train] Dataset: {n} complexes | train={len(train_idx)} "
          f"val={len(val_idx)} test={len(test_idx)}")

    # Modelo — misma arquitectura que el original
    model = GNNv2Classifier(
        hidden_dim=args.hidden_dim,
        dropout=args.dropout,
    ).to(device)
    print(f"[GPU Train] Parameters: {count_parameters(model):,}")

    optimizer = AdamW(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs)

    best_val_auc = 0.0
    best_epoch = 0
    patience_counter = 0
    t0 = time.time()

    print(f"\n[GPU Train] Training for {args.epochs} epochs...")
    for epoch in range(1, args.epochs + 1):
        train_loss = train_epoch(model, train_loader, optimizer, device)
        val_metrics = evaluate(model, val_loader, device)
        scheduler.step()

        if val_metrics["roc_auc"] > best_val_auc:
            best_val_auc = val_metrics["roc_auc"]
            best_epoch = epoch
            patience_counter = 0
            # ── Guardar en artifacts/gpu/ ──
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_metrics": val_metrics,
                    "config": vars(args),
                    "engine": "gpu",  # Metadata identificador
                },
                GPU_ARTIFACTS_DIR / "gnn_v3_best.pt",
            )
        else:
            patience_counter += 1

        if epoch % 5 == 0 or epoch == 1:
            elapsed = time.time() - t0
            print(
                f"  Epoch {epoch:3d} | loss={train_loss:.4f} | "
                f"val_auc={val_metrics['roc_auc']:.4f} | "
                f"best={best_val_auc:.4f} (ep {best_epoch}) | "
                f"{elapsed:.0f}s"
            )

        if patience_counter >= args.patience:
            print(f"\nEarly stopping at epoch {epoch}")
            break

    # Evaluación final
    print("\n" + "=" * 55)
    print("  Final Evaluation (Test Set) — GPU Model")
    print("=" * 55)

    checkpoint = torch.load(
        GPU_ARTIFACTS_DIR / "gnn_v3_best.pt", map_location=device
    )
    model.load_state_dict(checkpoint["model_state_dict"])

    test_metrics = evaluate(model, test_loader, device)
    print(f"  ROC-AUC:  {test_metrics['roc_auc']:.4f}")
    print(f"  PR-AUC:   {test_metrics['pr_auc']:.4f}")
    print(f"  Accuracy: {test_metrics['accuracy']:.4f}")
    print(f"  BCE:      {test_metrics['bce']:.4f}")
    print(f"  Best epoch: {checkpoint['epoch']}")

    # Guardar resultados en artifacts/gpu/
    results = {
        "test_metrics": {k: round(v, 4) for k, v in test_metrics.items()},
        "best_val_auc": round(best_val_auc, 4),
        "best_epoch": best_epoch,
        "n_params": count_parameters(model),
        "n_train": len(train_idx),
        "n_val": len(val_idx),
        "n_test": len(test_idx),
        "config": vars(args),
        "engine": "gpu",
    }
    with open(GPU_ARTIFACTS_DIR / "gnn_v3_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved: {GPU_ARTIFACTS_DIR / 'gnn_v3_results.json'}")
    print(f"Model saved:   {GPU_ARTIFACTS_DIR / 'gnn_v3_best.pt'}")


if __name__ == "__main__":
    main()
