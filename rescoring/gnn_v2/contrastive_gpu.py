"""
gnn_v2/contrastive_gpu.py — CL-GNN GPU: Contrastive Learning para modelos GPU.

Reentrena CL-GNN usando datos de docking Vina-GPU.
Genera artifacts/gpu/clgnn_finetuned.pt.
NO modifica el original contrastive.py.

Uso:
    cd rescoring
    python -m gnn_v2.contrastive_gpu --pretrain --epochs 50
    python -m gnn_v2.contrastive_gpu --finetune --epochs 100
    python -m gnn_v2.contrastive_gpu --all --epochs 50 --ft-epochs 100
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import roc_auc_score
from torch import nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from gnn_v2.data import PLComplexDataset
from gnn_v2.models import ContrastiveGNN, GNNv2Classifier, count_parameters

# ── GPU paths ───────────────────────────────────────────────────────────
GPU_ARTIFACTS_DIR = PROJECT_ROOT / "rescoring" / "artifacts" / "gpu"
GPU_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_GPU_DATA = PROJECT_ROOT / "data" / "gpu_poses"


# ═══════════════════════════════════════════════════════════════════════
# NT-Xent Loss
# ═══════════════════════════════════════════════════════════════════════

class NTXentLoss(nn.Module):
    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature

    def forward(self, z1: torch.Tensor, z2: torch.Tensor) -> torch.Tensor:
        z1 = F.normalize(z1, dim=-1)
        z2 = F.normalize(z2, dim=-1)
        B = z1.shape[0]
        z = torch.cat([z1, z2], dim=0)
        sim = (z @ z.T) / self.temperature
        sim.fill_diagonal_(-float('inf'))
        labels = torch.cat([torch.arange(B, B*2), torch.arange(B)], dim=0).to(sim.device)
        loss = F.cross_entropy(sim, labels)
        return loss


# ═══════════════════════════════════════════════════════════════════════
# Contrastive Dataset: generates positive/negative pairs
# ═══════════════════════════════════════════════════════════════════════

class ContrastiveDataset:
    """Wraps PLComplexDataset into (anchor, positive) pairs."""
    def __init__(self, dataset):
        self.dataset = dataset

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, idx):
        complex_item = self.dataset[idx]

        def add_noise(item):
            noisy = {}
            for k, v in item.items():
                if k == "ligand":
                    noisy_lig = type(v)()
                    for attr in ["x", "edge_index", "edge_attr", "pos", "batch"]:
                        if hasattr(v, attr):
                            val = getattr(v, attr)
                            if attr == "pos" and val is not None:
                                val = val.clone() + torch.randn_like(val) * 0.1
                            elif val is not None:
                                val = val.clone()
                            setattr(noisy_lig, attr, val)
                    noisy[k] = noisy_lig
                else:
                    noisy[k] = v
            return noisy

        return {
            "anchor": complex_item,
            "positive": add_noise(complex_item),
        }


def collate_contrastive(batch: list[dict]) -> dict:
    """Collate anchor-positive pairs into batched dicts."""
    from torch_geometric.data import Batch

    anchors = [item["anchor"] for item in batch]
    positives = [item["positive"] for item in batch]

    def _collate_one(items):
        prot_list = [i["protein"] for i in items]
        lig_list = [i["ligand"] for i in items]
        prot_b = Batch.from_data_list(prot_list)
        lig_b = Batch.from_data_list(lig_list)
        cross_edges = []
        po, lo = 0, 0
        for i, item in enumerate(items):
            cross = item["cross"]
            if cross.numel() > 0:
                rc = cross.clone()
                rc[0] += lo
                rc[1] += po
                cross_edges.append(rc)
            po += prot_list[i].num_nodes
            lo += lig_list[i].num_nodes
        cross_b = torch.cat(cross_edges, dim=1) if cross_edges else torch.empty((2, 0), dtype=torch.long)
        return {
            "prot_x": prot_b.x, "prot_edge_index": prot_b.edge_index,
            "prot_pos": prot_b.pos, "prot_batch": prot_b.batch,
            "lig_x": lig_b.x, "lig_edge_index": lig_b.edge_index,
            "lig_pos": lig_b.pos, "lig_batch": lig_b.batch,
            "cross_edge_index": cross_b,
        }

    return {"anchor": _collate_one(anchors), "positive": _collate_one(positives)}


# ═══════════════════════════════════════════════════════════════════════
# Pretraining (unsupervised contrastive)
# ═══════════════════════════════════════════════════════════════════════

def pretrain(args):
    print("=" * 55)
    print("  CL-GNN GPU: Pretraining (contrastive)")
    print(f"  Data: {args.gpu_data_dir}")
    print(f"  Output: {GPU_ARTIFACTS_DIR}")
    print("=" * 55)

    import gnn_v2.data as gnn_data
    gnn_data.REDOCK_DIR = args.gpu_data_dir / "pdbs"

    dataset = PLComplexDataset(root=str(args.gpu_data_dir))
    cd = ContrastiveDataset(dataset)
    loader = DataLoader(cd, batch_size=args.batch_size, shuffle=True, collate_fn=collate_contrastive)
    print(f"  Complexes: {len(dataset)}")

    device = args.device if args.device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")
    model = ContrastiveGNN(hidden_dim=args.hidden_dim).to(device)
    print(f"  Device: {device}")
    print(f"  Parameters: {count_parameters(model):,}")

    criterion = NTXentLoss(temperature=0.07)
    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs)

    best_loss = float("inf")
    t0 = time.time()
    print(f"\n  Training {args.epochs} epochs...")

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0

        for batch in loader:
            a = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch["anchor"].items()}
            p = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch["positive"].items()}

            optimizer.zero_grad()
            z_a = model(a["prot_x"], a["prot_edge_index"], a["lig_x"], a["lig_edge_index"],
                        a["cross_edge_index"], lig_pos=a.get("lig_pos"), prot_pos=a.get("prot_pos"),
                        lig_batch=a["lig_batch"], prot_batch=a["prot_batch"])
            z_p = model(p["prot_x"], p["prot_edge_index"], p["lig_x"], p["lig_edge_index"],
                        p["cross_edge_index"], lig_pos=p.get("lig_pos"), prot_pos=p.get("prot_pos"),
                        lig_batch=p["lig_batch"], prot_batch=p["prot_batch"])
            loss = criterion(z_a, z_p)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()

        scheduler.step()
        avg_loss = total_loss / len(loader)

        if avg_loss < best_loss:
            best_loss = avg_loss
            torch.save({"model_state_dict": model.state_dict(), "loss": avg_loss, "epoch": epoch},
                       GPU_ARTIFACTS_DIR / "clgnn_pretrained.pt")

        if epoch % 10 == 0 or epoch == 1:
            elapsed = time.time() - t0
            print(f"  Epoch {epoch:3d} | loss={avg_loss:.6f} | best={best_loss:.6f} | {elapsed:.0f}s")

    print(f"\n  Pretraining done in {(time.time()-t0)/60:.1f} min")
    print(f"  Best loss: {best_loss:.6f}")
    print(f"  Model: {GPU_ARTIFACTS_DIR / 'clgnn_pretrained.pt'}")


# ═══════════════════════════════════════════════════════════════════════
# Fine-tuning (supervised)
# ═══════════════════════════════════════════════════════════════════════

def finetune(args):
    print("=" * 55)
    print("  CL-GNN GPU: Fine-tuning")
    print(f"  Data: {args.gpu_data_dir}")
    print(f"  Output: {GPU_ARTIFACTS_DIR}")
    print("=" * 55)

    import gnn_v2.data as gnn_data
    gnn_data.REDOCK_DIR = args.gpu_data_dir / "pdbs"

    dataset = PLComplexDataset(root=str(args.gpu_data_dir))
    n = len(dataset)
    train_ds = [dataset[i] for i in range(int(n * 0.7))]
    val_ds = [dataset[i] for i in range(int(n * 0.7), int(n * 0.85))]
    print(f"  Train: {len(train_ds)}, Val: {len(val_ds)}")

    from gnn_v2.train import collate_complexes
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, collate_fn=collate_complexes)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, collate_fn=collate_complexes)

    device = args.device if args.device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")
    model = GNNv2Classifier(hidden_dim=args.hidden_dim).to(device)

    pretrained_path = GPU_ARTIFACTS_DIR / "clgnn_pretrained.pt"
    if pretrained_path.exists():
        ck = torch.load(pretrained_path, map_location=device, weights_only=False)
        contrastive_model = ContrastiveGNN(hidden_dim=args.hidden_dim)
        contrastive_model.load_state_dict(ck["model_state_dict"])
        contrastive_model.to(device)
        contrastive_model.load_pretrained_to_classifier(model)
        print(f"  Pretrained encoder loaded (epoch {ck.get('epoch', '?')})")
    else:
        print(f"  No pretrained model found at {pretrained_path}. Training from scratch.")

    optimizer = AdamW(model.parameters(), lr=args.ft_lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.ft_epochs)

    best_val_auc = 0.0
    t0 = time.time()
    print(f"\n  Training {args.ft_epochs} epochs...")

    for epoch in range(1, args.ft_epochs + 1):
        model.train()
        total_loss = 0
        for batch in train_loader:
            batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
            optimizer.zero_grad()
            logits = model(batch["prot_x"], batch["prot_edge_index"], batch["lig_x"],
                          batch["lig_edge_index"], batch["cross_edge_index"],
                          lig_pos=batch.get("lig_pos"), prot_pos=batch.get("prot_pos"),
                          lig_batch=batch["lig_batch"], prot_batch=batch["prot_batch"])
            loss = F.binary_cross_entropy_with_logits(logits, batch["y_binary"].float())
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()

        model.eval()
        val_probs, val_labels = [], []
        with torch.no_grad():
            for batch in val_loader:
                batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
                logits = model(batch["prot_x"], batch["prot_edge_index"], batch["lig_x"],
                              batch["lig_edge_index"], batch["cross_edge_index"],
                              lig_pos=batch.get("lig_pos"), prot_pos=batch.get("prot_pos"),
                              lig_batch=batch["lig_batch"], prot_batch=batch["prot_batch"])
                val_probs.append(torch.sigmoid(logits).cpu())
                val_labels.append(batch["y_binary"].cpu())
        val_probs = torch.cat(val_probs)
        val_labels = torch.cat(val_labels)
        val_auc = roc_auc_score(val_labels.numpy(), val_probs.numpy()) if len(set(val_labels.numpy())) > 1 else 0.5
        scheduler.step()

        if val_auc > best_val_auc:
            best_val_auc = val_auc
            torch.save(model.state_dict(), GPU_ARTIFACTS_DIR / "clgnn_finetuned.pt")

        if epoch % 10 == 0 or epoch == 1:
            elapsed = time.time() - t0
            print(f"  Epoch {epoch:3d} | loss={total_loss/len(train_loader):.4f} | val_auc={val_auc:.4f} | best={best_val_auc:.4f} | {elapsed:.0f}s")

    print(f"\n  Fine-tuning done in {(time.time()-t0)/60:.1f} min")
    print(f"  Best val AUC: {best_val_auc:.4f}")
    print(f"  Model: {GPU_ARTIFACTS_DIR / 'clgnn_finetuned.pt'}")


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="CL-GNN GPU: Contrastive Learning + Fine-tuning")
    parser.add_argument("--pretrain", action="store_true")
    parser.add_argument("--finetune", action="store_true")
    parser.add_argument("--all", action="store_true", help="Run pretrain + finetune")
    parser.add_argument("--gpu-data-dir", type=str, default=str(DEFAULT_GPU_DATA))
    parser.add_argument("--epochs", type=int, default=50, help="Pretraining epochs")
    parser.add_argument("--ft-epochs", type=int, default=100, help="Fine-tuning epochs")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--ft-lr", type=float, default=5e-4)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    args.gpu_data_dir = Path(args.gpu_data_dir)

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    if args.all:
        pretrain(args)
        finetune(args)
    elif args.pretrain:
        pretrain(args)
    elif args.finetune:
        finetune(args)
    else:
        print("Specify --pretrain, --finetune, or --all")
        return


if __name__ == "__main__":
    main()
