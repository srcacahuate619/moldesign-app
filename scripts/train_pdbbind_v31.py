"""
scripts/train_pdbbind_v31.py — GNN-v3.1 training on PDBbind + ECIF

Loads PLComplexDataset (708 pre-built graphs) + ecif_pdbbind_crystal.npz (ECIF features),
trains GNNv31Classifier with multi-task BCE+delta loss.

Usage:
  python scripts/train_pdbbind_v31.py --epochs 200 --batch-size 16 --lr 1e-3
"""
import argparse, json, random, sys, time, os
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, roc_auc_score
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, Dataset
from torch_geometric.data import Batch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
from gnn_v2.models import GNNv31Classifier, count_parameters

ARTIFACTS = PROJECT_ROOT / "rescoring" / "artifacts"
ECIF_PATH = PROJECT_ROOT / "data" / "gnn_v31" / "ecif_pdbbind_crystal.npz"
PLCOMPLEX_PATH = PROJECT_ROOT / "data" / "gnn_v2_dataset" / "processed" / "gnn_v2_complexes.pt"


def load_complexes():
    data, _ = torch.load(PLCOMPLEX_PATH, weights_only=False)
    return list(data)


def load_ecif():
    d = np.load(ECIF_PATH, allow_pickle=True)
    pid_to_idx = {p: i for i, p in enumerate(d["pid"])}
    return d["X"], d["y_pki"], d["y_binary"], pid_to_idx


class PDBbindV31Dataset(Dataset):
    def __init__(self, indices, complexes, ecif_X, ecif_y_pki, ecif_y_bin, pid_to_ecif):
        self.indices = indices
        self.complexes = complexes
        self.ecif_X = ecif_X
        self.ecif_y_pki = ecif_y_pki
        self.ecif_y_bin = ecif_y_bin
        self.pid_to_ecif = pid_to_ecif

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, idx):
        i = self.indices[idx]
        c = self.complexes[i]
        pid = c["pdb_id"]
        ecif_idx = self.pid_to_ecif.get(pid, -1)
        if ecif_idx >= 0:
            ecif = self.ecif_X[ecif_idx].copy()
            pki = float(self.ecif_y_pki[ecif_idx])
            yb = int(self.ecif_y_bin[ecif_idx])
        else:
            ecif = np.zeros(self.ecif_X.shape[1], dtype=np.float32)
            pki = 0.0
            yb = int(c.get("y_binary", 0))
        return {
            "protein": c["protein"],
            "ligand": c["ligand"],
            "cross": c["cross"],
            "y": float(c.get("y", 0)),
            "y_binary": yb,
            "y_pki": pki,
            "ecif": ecif,
            "pdb_id": pid,
        }


def collate(batch):
    proteins = [item["protein"] for item in batch]
    ligands = [item["ligand"] for item in batch]
    prot_batch = Batch.from_data_list(proteins)
    lig_batch = Batch.from_data_list(ligands)

    cross_edges = []
    po, lo = 0, 0
    for i, item in enumerate(batch):
        cross = item["cross"]
        if cross.numel() > 0:
            reindexed = cross.clone()
            reindexed[0] += lo
            reindexed[1] += po
            cross_edges.append(reindexed)
        po += proteins[i].num_nodes
        lo += ligands[i].num_nodes
    cross_batch = torch.cat(cross_edges, dim=1) if cross_edges else torch.empty((2, 0), dtype=torch.long)

    y_binary = torch.tensor([item["y_binary"] for item in batch], dtype=torch.float32)
    y_pki = torch.tensor([item["y_pki"] for item in batch], dtype=torch.float32)
    y_delta = y_pki  # since vina_score=0 for crystal, delta = pKi - 0 = pKi
    has_delta = (y_pki > 0).float()

    ecifs = np.stack([item["ecif"] for item in batch])
    ecif_t = torch.from_numpy(ecifs.astype(np.float32))

    return {
        "prot_x": prot_batch.x, "prot_edge_index": prot_batch.edge_index, "prot_batch": prot_batch.batch,
        "lig_x": lig_batch.x, "lig_edge_index": lig_batch.edge_index, "lig_batch": lig_batch.batch,
        "cross_edge_index": cross_batch,
        "y_binary": y_binary, "y_pki": y_pki, "y_delta": y_delta, "has_delta": has_delta,
        "ecif": ecif_t,
    }


def to_device(b, dev):
    return {k: v.to(dev) if torch.is_tensor(v) else v for k, v in b.items()}


def train_epoch(model, loader, opt, device, ld):
    model.train()
    bce_sum, delta_sum, correct, total = 0.0, 0.0, 0, 0
    for batch in loader:
        batch = to_device(batch, device)
        prob_logit, delta_pred = model(
            batch["prot_x"], batch["prot_edge_index"],
            batch["lig_x"], batch["lig_edge_index"],
            batch["cross_edge_index"],
            lig_batch=batch["lig_batch"], prot_batch=batch["prot_batch"],
            ecif=batch["ecif"],
        )
        bce = F.binary_cross_entropy_with_logits(prob_logit, batch["y_binary"])
        mask = batch["has_delta"].bool()
        loss = bce
        if mask.sum() > 0 and ld > 0:
            mse = F.mse_loss(delta_pred[mask], batch["y_delta"][mask])
            loss = bce + ld * mse
            delta_sum += float(mse.item())
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        bce_sum += float(bce.item())
        pred = (torch.sigmoid(prob_logit) > 0.5).float()
        correct += int((pred == batch["y_binary"]).sum().item())
        total += len(batch["y_binary"])
    n = max(len(loader), 1)
    return bce_sum/n, delta_sum/n, correct/max(total,1)


@torch.no_grad()
def eval_model(model, loader, device):
    model.eval()
    ys, ps = [], []
    for batch in loader:
        batch = to_device(batch, device)
        prob_logit, _ = model(
            batch["prot_x"], batch["prot_edge_index"],
            batch["lig_x"], batch["lig_edge_index"],
            batch["cross_edge_index"],
            lig_batch=batch["lig_batch"], prot_batch=batch["prot_batch"],
            ecif=batch["ecif"],
        )
        ps.extend(torch.sigmoid(prob_logit).cpu().numpy())
        ys.extend(batch["y_binary"].cpu().numpy())
    ys, ps = np.array(ys), np.array(ps)
    if len(set(ys)) < 2:
        return {"roc_auc": 0.5, "pr_auc": 0.5}
    return {"roc_auc": float(roc_auc_score(ys, ps)),
            "pr_auc": float(average_precision_score(ys, ps))}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--epochs", type=int, default=200)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--hidden-dim", type=int, default=128)
    p.add_argument("--dropout", type=float, default=0.2)
    p.add_argument("--lambda-delta", type=float, default=0.3)
    p.add_argument("--patience", type=int, default=30)
    p.add_argument("--device", type=str, default="auto")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    device = "cuda" if (args.device == "auto" and torch.cuda.is_available()) else (args.device if args.device != "auto" else "cpu")
    print(f"Device: {device}")

    print("Loading PLComplexDataset...")
    complexes = load_complexes()
    print(f"  {len(complexes)} complexes")

    print(f"Loading ECIF: {ECIF_PATH.name}")
    ecif_X, ecif_y_pki, ecif_y_bin, pid_to_ecif = load_ecif()
    print(f"  ECIF X: {ecif_X.shape}, with_pki={(ecif_y_pki>0).sum()}")

    # Z-score ECIF
    ecif_mean = ecif_X.mean(axis=0, keepdims=True)
    ecif_std = ecif_X.std(axis=0, keepdims=True) + 1e-8
    ecif_X = (ecif_X - ecif_mean) / ecif_std
    ecif_X = np.nan_to_num(ecif_X, nan=0.0)

    # Split indices (stratified by y_binary)
    idx_pos = [i for i, c in enumerate(complexes) if pid_to_ecif.get(c["pdb_id"], -1)>=0 and ecif_y_bin[pid_to_ecif[c["pdb_id"]]] == 1]
    idx_neg = [i for i, c in enumerate(complexes) if pid_to_ecif.get(c["pdb_id"], -1)>=0 and ecif_y_bin[pid_to_ecif[c["pdb_id"]]] == 0]
    print(f"  Will use: {len(idx_pos)} positive + {len(idx_neg)} negative = {len(idx_pos)+len(idx_neg)} total with ECIF")
    all_idx = idx_pos + idx_neg
    random.shuffle(all_idx)
    n = len(all_idx)
    n_val = max(1, n//10); n_test = max(1, n//10); n_train = n - n_val - n_test
    train_idx = all_idx[:n_train]; val_idx = all_idx[n_train:n_train+n_val]; test_idx = all_idx[n_train+n_val:]
    print(f"  split: train={len(train_idx)} val={len(val_idx)} test={len(test_idx)}")

    ds_args = (complexes, ecif_X, ecif_y_pki, ecif_y_bin, pid_to_ecif)
    train_ds = PDBbindV31Dataset(train_idx, *ds_args)
    val_ds = PDBbindV31Dataset(val_idx, *ds_args)
    test_ds = PDBbindV31Dataset(test_idx, *ds_args)

    loaders = {
        "train": DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, collate_fn=collate),
        "val": DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, collate_fn=collate),
        "test": DataLoader(test_ds, batch_size=args.batch_size, shuffle=False, collate_fn=collate),
    }

    model = GNNv31Classifier(hidden_dim=args.hidden_dim, dropout=args.dropout,
                             ecif_in=ecif_X.shape[1], use_delta_head=(args.lambda_delta>0)).to(device)
    n_params = count_parameters(model)
    print(f"Model params: {n_params:,}")

    opt = AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    sched = CosineAnnealingLR(opt, T_max=args.epochs, eta_min=1e-6)

    best_val_auc, best_epoch, patience_left = 0.0, -1, args.patience
    out_pt = ARTIFACTS / "gnn_v31_best.pt"
    history = []
    t0 = time.time()
    print(f"\n=== Training {args.epochs} epochs ===")
    for ep in range(1, args.epochs+1):
        bce, dlt, acc = train_epoch(model, loaders["train"], opt, device, args.lambda_delta)
        val = eval_model(model, loaders["val"], device)
        sched.step()
        st = f"Epoch {ep:3d} | BCE {bce:.4f} | D {dlt:.4f} | acc {acc:.3f} | val_AUC {val['roc_auc']:.4f}"
        history.append({"epoch":ep,"bce":bce,"delta":dlt,"acc":acc,"val_auc":val["roc_auc"],"val_pr":val["pr_auc"]})
        improved = False
        if val["roc_auc"] > best_val_auc:
            best_val_auc = val["roc_auc"]; best_epoch = ep; patience_left = args.patience
            torch.save(model.state_dict(), out_pt); improved = True
            st += " *"
        else:
            patience_left -= 1
            st += f" (p{patience_left})"
        t = time.time()-t0
        print(f"  {st}  [{t:.0f}s]")
        if patience_left <= 0:
            print(f"Early stopping at epoch {ep}")
            break

    print(f"\nBest val_AUC={best_val_auc:.4f} at epoch {best_epoch}")
    model.load_state_dict(torch.load(out_pt, weights_only=False))
    test = eval_model(model, loaders["test"], device)
    print(f"Test ROC-AUC: {test['roc_auc']:.4f}  PR-AUC: {test['pr_auc']:.4f}")

    results = {"best_val_auc": best_val_auc,"best_epoch": best_epoch,
               "n_params": n_params,"n_train": len(train_idx),"n_val": len(val_idx),"n_test": len(test_idx),
               "test_metrics": test,"config": vars(args),"history": history,
               "total_time_s": round(time.time()-t0,1)}
    out_json = ARTIFACTS / "gnn_v31_results.json"
    with open(out_json,"w") as f: json.dump(results, f, indent=2)
    print(f"\nSaved: {out_pt.name} ({out_pt.stat().st_size/1024:.0f} KB), {out_json.name}")


if __name__ == "__main__":
    main()
