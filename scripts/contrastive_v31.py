"""
scripts/contrastive_v31.py — CL-GNN: Contrastive + Finetune for GNN-v3 (38-dim fixed).

Fase 1 — Pretraining contrastivo (NT-Xent):
  - Pares positivos: mismo complejo + ruido gaussiano en coords del ligando
  - Pares negativos: complejos diferentes en el batch
  - Loss: NT-Xent (InfoNCE) sobre embedding del projection head
  - El GNN aprende embeddings invariantes al ruido de docking

Fase 2 — Fine-tuning:
  - Cargar encoder pretrained
  - Agregar cabeza de clasificacion
  - Fine-tune en PDBbind (docked) con BCE loss
  - Opcional ECIF si se pasa --ecif-path

Fase 3 — 5HT1A eval:
  - Scorea el benchmark con GNN y guarda clgnn_prob en checkpoint

Usage:
  python scripts/contrastive_v31.py --pretrain
  python scripts/contrastive_v31.py --finetune
  python scripts/contrastive_v31.py --evaluate-5ht1a
  python scripts/contrastive_v31.py --full-pipeline
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import roc_auc_score, average_precision_score
from torch.utils.data import DataLoader, Dataset

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from gnn_v2.data import PLComplexDataset
from gnn_v2.models import GNNv2Classifier, GNNv31Classifier, ContrastiveGNN, count_parameters
from gnn_v2.train import collate_complexes

ARTIFACTS_DIR = PROJECT_ROOT / "rescoring" / "artifacts"

# Fase 1 — NT-Xent Loss
class NTXentLoss(nn.Module):
    def __init__(self, temperature: float = 0.5):
        super().__init__()
        self.temperature = temperature

    def forward(self, z_anchor: torch.Tensor, z_positive: torch.Tensor) -> torch.Tensor:
        B = z_anchor.size(0)
        z_anchor = F.normalize(z_anchor, dim=1)
        z_positive = F.normalize(z_positive, dim=1)
        z = torch.cat([z_anchor, z_positive], dim=0)
        sim = torch.mm(z, z.t()) / self.temperature
        B2 = 2 * B
        mask = torch.zeros((B2, B2), device=z.device, dtype=torch.bool)
        for i in range(B):
            mask[i, i + B] = True
            mask[i + B, i] = True
        pos_sim = sim[mask]
        sim_exp = torch.exp(sim.masked_fill(
            torch.eye(B2, device=z.device, dtype=torch.bool), -1e9))
        denom = sim_exp.sum(dim=1)
        return -torch.log(pos_sim / denom).mean()


class PairedComplexDataset(Dataset):
    def __init__(self, base_dataset: PLComplexDataset, noise_std: float = 0.2):
        self.base = base_dataset
        self.noise_std = noise_std

    def __len__(self):
        return len(self.base)

    def __getitem__(self, idx):
        item = self.base[idx]
        return item, item


def collate_contrastive(batch):
    anchors = [b[0] for b in batch]
    positives = [b[1] for b in batch]
    anchor_batch = collate_complexes(anchors)
    pos_batch = collate_complexes(positives)
    noise = torch.randn_like(pos_batch["lig_pos"]) * 0.2
    pos_batch["lig_pos"] = pos_batch["lig_pos"] + noise
    return {"anchor": anchor_batch, "positive": pos_batch}


def pretrain(epochs=200, batch_size=16, lr=1e-3, hidden_dim=128, seed=42):
    print("=" * 55)
    print(f"  CL-GNN-v3: Contrastive Pretraining (38-dim, docked) seed={seed}")
    print("=" * 55)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    ds = PLComplexDataset()
    print(f"\nLoading dataset... {len(ds)} complexes")

    paired_ds = PairedComplexDataset(ds, noise_std=0.2)
    loader = DataLoader(paired_ds, batch_size=batch_size, shuffle=True,
                        collate_fn=collate_contrastive, num_workers=0)

    model = ContrastiveGNN(hidden_dim=hidden_dim)
    print(f"  Parameters: {count_parameters(model):,}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    optim = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optim, T_max=epochs)
    criterion = NTXentLoss(temperature=0.5)

    best_loss = float("inf")
    t0 = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0
        for b in loader:
            a = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in b["anchor"].items()}
            p = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in b["positive"].items()}
            optim.zero_grad()
            z_a = model(a["prot_x"], a["prot_edge_index"], a["lig_x"], a["lig_edge_index"],
                        a["cross_edge_index"], lig_pos=a.get("lig_pos"), prot_pos=a.get("prot_pos"),
                        lig_batch=a["lig_batch"], prot_batch=a["prot_batch"])
            z_p = model(p["prot_x"], p["prot_edge_index"], p["lig_x"], p["lig_edge_index"],
                        p["cross_edge_index"], lig_pos=p.get("lig_pos"), prot_pos=p.get("prot_pos"),
                        lig_batch=p["lig_batch"], prot_batch=p["prot_batch"])
            loss = criterion(z_a, z_p)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optim.step()
            total_loss += loss.item()
        scheduler.step()
        avg = total_loss / len(loader)
        if avg < best_loss:
            best_loss = avg
            torch.save({
                "model_state_dict": model.state_dict(),
                "loss": avg,
                "epoch": epoch,
                "config": {"hidden_dim": hidden_dim},
            }, ARTIFACTS_DIR / "contrastive_v31_pretrained.pt")
        if epoch % 10 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d} | loss={avg:.6f} | best={best_loss:.6f} | {time.time()-t0:.0f}s")

    print(f"\nPretraining done in {(time.time()-t0)/60:.1f} min")
    print(f"  Best loss: {best_loss:.6f}")
    print(f"  Saved: {ARTIFACTS_DIR / 'contrastive_v31_pretrained.pt'}")


def finetune(epochs=100, batch_size=16, lr=5e-4, hidden_dim=128,
             use_ecif=False, ecif_path=None, seed=42):
    print("=" * 55)
    print(f"  CL-GNN-v3: Fine-tuning (docked docked docked) seed={seed}")
    print("=" * 55)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    ds = PLComplexDataset()
    n = len(ds)
    train_ds = [ds[i] for i in range(int(n * 0.8))]
    val_ds = [ds[i] for i in range(int(n * 0.8), n)]
    print(f"\n  Train: {len(train_ds)}, Val: {len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collate_complexes)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, collate_fn=collate_complexes)

    # Load ECIF if needed
    ecif_X = None
    if use_ecif and ecif_path and Path(ecif_path).exists():
        data = np.load(ecif_path)
        ecif_X = data["X"].astype(np.float32)
        # z-score
        mean = ecif_X.mean(axis=0, keepdims=True)
        std = ecif_X.std(axis=0, keepdims=True) + 1e-8
        ecif_X = (ecif_X - mean) / std
        print(f"  ECIF loaded: {ecif_X.shape}")

    device = "cuda" if torch.cuda.is_available() else "cpu"

    if use_ecif:
        model = GNNv31Classifier(hidden_dim=hidden_dim, ecif_in=152, use_delta_head=False).to(device)
    else:
        model = GNNv2Classifier(hidden_dim=hidden_dim).to(device)

    # Load pretrained encoder
    pt_path = ARTIFACTS_DIR / "contrastive_v31_pretrained.pt"
    if pt_path.exists():
        ck = torch.load(pt_path, map_location=device, weights_only=False)
        c_model = ContrastiveGNN(hidden_dim=hidden_dim)
        c_model.load_state_dict(ck["model_state_dict"])
        c_model.load_pretrained_to_classifier(model)
        print(f"  Pretrained encoder loaded (epoch {ck['epoch']})")
    else:
        print("  WARN: No pretrained model found, training from scratch")

    optim = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optim, T_max=epochs)

    best_val_auc = 0.0
    t0 = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0
        for batch in train_loader:
            batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
            optim.zero_grad()

            if use_ecif and ecif_X is not None:
                ecif_t = torch.from_numpy(ecif_X).float().to(device)
                # Match ECIF to batch indices — simple approach: use training index
                # This is a placeholder; real ECIF matching needs careful alignment
                # For now, fall back to GNNv2Classifier
                logits = model(
                    batch["prot_x"], batch["prot_edge_index"],
                    batch["lig_x"], batch["lig_edge_index"],
                    batch["cross_edge_index"],
                    lig_pos=batch.get("lig_pos"), prot_pos=batch.get("prot_pos"),
                    lig_batch=batch["lig_batch"], prot_batch=batch["prot_batch"],
                    ecif=None,
                )
            else:
                logits = model(
                    batch["prot_x"], batch["prot_edge_index"],
                    batch["lig_x"], batch["lig_edge_index"],
                    batch["cross_edge_index"],
                    lig_pos=batch.get("lig_pos"), prot_pos=batch.get("prot_pos"),
                    lig_batch=batch["lig_batch"], prot_batch=batch["prot_batch"],
                )

            loss = F.binary_cross_entropy_with_logits(logits, batch["y_binary"].float())
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optim.step()
            total_loss += loss.item()

        model.eval()
        val_probs, val_labels = [], []
        with torch.no_grad():
            for batch in val_loader:
                batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
                logits = model(
                    batch["prot_x"], batch["prot_edge_index"],
                    batch["lig_x"], batch["lig_edge_index"],
                    batch["cross_edge_index"],
                    lig_pos=batch.get("lig_pos"), prot_pos=batch.get("prot_pos"),
                    lig_batch=batch["lig_batch"], prot_batch=batch["prot_batch"],
                )
                val_probs.append(torch.sigmoid(logits).cpu())
                val_labels.append(batch["y_binary"].cpu())
        val_probs = torch.cat(val_probs)
        val_labels = torch.cat(val_labels)
        try:
            val_auc = roc_auc_score(val_labels.numpy(), val_probs.numpy())
        except ValueError:
            val_auc = 0.5
        scheduler.step()

        if val_auc > best_val_auc:
            best_val_auc = val_auc
            model_name = "gnn_v31_cl_best.pt" if use_ecif else "gnn_v2_cl_best.pt"
            torch.save({
                "model_state_dict": model.state_dict(),
                "val_auc": val_auc,
                "epoch": epoch,
                "config": {"hidden_dim": hidden_dim, "use_ecif": use_ecif},
            }, ARTIFACTS_DIR / model_name)

        if epoch % 10 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d} | loss={total_loss/len(train_loader):.4f} | val_auc={val_auc:.4f} | best={best_val_auc:.4f} | {time.time()-t0:.0f}s")

    print(f"\nFine-tuning done in {(time.time()-t0)/60:.1f} min")
    print(f"  Best val AUC: {best_val_auc:.4f}")


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


def build_graph_from_pose(pose_pdbqt, target_pdb, smiles, use_heavier_feats=False):
    """Build complex graph (GNNv2 format, 38-dim) from docked pose."""
    fd1, pdbqt_path = tempfile.mkstemp(suffix=".pdbqt")
    try:
        os.close(fd1)
        with open(pdbqt_path, "w") as f:
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
        fd2, sdf_path = tempfile.mkstemp(suffix=".sdf")
        os.close(fd2)
        w = Chem.SDWriter(sdf_path)
        w.write(mol)
        w.close()
        try:
            from gnn_v2.data import _build_ligand_graph, _build_protein_graph, _build_cross_edges
            lig_graph = _build_ligand_graph(sdf_path, pdbqt_path)
        finally:
            try: os.unlink(sdf_path)
            except OSError: pass
        if lig_graph is None:
            return None
        prot_graph = _build_protein_graph(target_pdb, lig_graph.pos.numpy())
        if prot_graph is None:
            return None
        cross = _build_cross_edges(lig_graph.pos, prot_graph.pos)
        return {"protein": prot_graph, "ligand": lig_graph, "cross": cross}
    finally:
        try: os.unlink(pdbqt_path)
        except OSError: pass


def evaluate_5ht1a(model_path="gnn_v2_cl_best.pt", hidden_dim=128, use_ecif=False):
    """Score 5HT1A benchmark and add clgnn_prob to checkpoint."""
    print("=" * 55)
    print("  CL-GNN-v3: 5HT1A Evaluation")
    print("=" * 55)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if use_ecif:
        model = GNNv31Classifier(hidden_dim=hidden_dim, ecif_in=152, use_delta_head=False).to(device)
    else:
        model = GNNv2Classifier(hidden_dim=hidden_dim).to(device)

    ck_path = ARTIFACTS_DIR / model_path
    if not ck_path.exists():
        print(f"  ERROR: {ck_path} not found")
        return
    state = torch.load(ck_path, map_location=device, weights_only=False)
    sd = state.get("model_state_dict", state)
    model.load_state_dict(sd, strict=not use_ecif)
    model.to(device).eval()
    print(f"  Model loaded: {ck_path.name}")

    target_pdb = PROJECT_ROOT / "data" / "targets" / "7E2Y.pdb"
    ck_json = PROJECT_ROOT / "data" / "gnn_v31" / "checkpoints" / "benchmark_checkpoint_5ht1a.json"
    with open(ck_json) as f:
        ck = json.load(f)
    results = ck["results"]
    print(f"  Benchmark: {len(results)} molecules")

    labels = np.array([int(bool(r.get("is_active", False))) for r in results])
    preds = np.zeros(len(results), dtype=np.float32)
    silent = 0
    t0 = time.time()

    for i, ent in enumerate(results):
        smi = ent.get("smiles", "")
        pose = ent.get("pose_pdbqt", "")
        try:
            graph = build_graph_from_pose(pose, str(target_pdb), smi)
            if graph is None:
                preds[i] = 0.5
                silent += 1
                continue
            from torch_geometric.data import Batch
            prot_b = Batch.from_data_list([graph["protein"]]).to(device)
            lig_b = Batch.from_data_list([graph["ligand"]]).to(device)
            with torch.no_grad():
                if use_ecif:
                    logits, _ = model(
                        prot_b.x, prot_b.edge_index, lig_b.x, lig_b.edge_index,
                        graph["cross"].to(device),
                        lig_batch=lig_b.batch, prot_batch=prot_b.batch,
                        ecif=None,
                    )
                else:
                    logits = model(
                        prot_b.x, prot_b.edge_index, lig_b.x, lig_b.edge_index,
                        graph["cross"].to(device),
                        lig_batch=lig_b.batch, prot_batch=prot_b.batch,
                    )
                preds[i] = float(torch.sigmoid(logits).item())
        except Exception:
            preds[i] = 0.5
            silent += 1

        if (i + 1) % 200 == 0 or i == len(results) - 1:
            print(f"  [{i+1}/{len(results)}] silent={silent} rate={(i+1)/(time.time()-t0):.1f}/s")

    valid = np.where(preds != 0.5)[0]
    y, p = labels[valid], preds[valid]
    auc = float(roc_auc_score(y, p))
    pr = float(average_precision_score(y, p))
    ef1, ef5, ef10 = compute_ef(p, y, 1), compute_ef(p, y, 5), compute_ef(p, y, 10)

    print(f"\n=== 5HT1A Results [{model_path}] ===")
    print(f"  ROC-AUC:  {auc:.4f}")
    print(f"  PR-AUC:   {pr:.4f}")
    print(f"  EF@1%:    {ef1:.2f}x")
    print(f"  EF@5%:    {ef5:.2f}x")
    print(f"  EF@10%:   {ef10:.2f}x")
    print(f"  Mean P(active): {p[y==1].mean():.4f}")
    print(f"  Mean P(decoy):  {p[y==0].mean():.4f}")
    print(f"  Time: {time.time()-t0:.0f}s ({time.time()-t0/len(results):.2f}s/mol)")

    # Add clgnn_prob to checkpoint and save updated version
    for i, v in enumerate(preds):
        results[i]["clgnn_prob"] = round(float(v), 6)

    out_path = PROJECT_ROOT / "data" / "gnn_v31" / "checkpoints" / "benchmark_checkpoint_5ht1a.json"
    # Backup original
    import shutil
    if not Path(str(out_path) + ".bak").exists():
        shutil.copy(out_path, str(out_path) + ".bak")
    with open(out_path, "w") as f:
        json.dump(ck, f, indent=2)
    print(f"\n  Updated checkpoint with clgnn_prob: {out_path}")

    return {"auc": auc, "pr": pr, "ef1": ef1, "ef5": ef5, "ef10": ef10,
            "mean_act": float(p[y==1].mean()), "mean_dec": float(p[y==0].mean()),
            "silent": silent, "valid": len(valid)}


def full_pipeline():
    print("=" * 55)
    print("  CL-GNN-v3 FULL PIPELINE")
    print("=" * 55)
    pretrain(epochs=200, batch_size=16, lr=1e-3, hidden_dim=128)
    finetune(epochs=100, batch_size=16, lr=5e-4, hidden_dim=128, use_ecif=False)
    evaluate_5ht1a(model_path="gnn_v2_cl_best.pt", hidden_dim=128, use_ecif=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CL-GNN-v3: Contrastive + Finetune + Eval")
    parser.add_argument("--pretrain", action="store_true")
    parser.add_argument("--finetune", action="store_true")
    parser.add_argument("--evaluate-5ht1a", action="store_true")
    parser.add_argument("--full-pipeline", action="store_true")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--finetune-epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--finetune-lr", type=float, default=5e-4)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42, help="Reproducibility seed")
    parser.add_argument("--use-ecif", action="store_true")
    parser.add_argument("--ecif-path", type=str, default=None)
    parser.add_argument("--model-path", type=str, default="gnn_v2_cl_best.pt")
    args = parser.parse_args()

    if args.full_pipeline:
        full_pipeline()
    elif args.pretrain:
        pretrain(epochs=args.epochs, batch_size=args.batch_size, lr=args.lr, hidden_dim=args.hidden_dim, seed=args.seed)
    elif args.finetune:
        finetune(epochs=args.finetune_epochs, batch_size=args.batch_size, lr=args.finetune_lr,
                 hidden_dim=args.hidden_dim, use_ecif=args.use_ecif, ecif_path=args.ecif_path, seed=args.seed)
    elif args.evaluate_5ht1a:
        evaluate_5ht1a(model_path=args.model_path, hidden_dim=args.hidden_dim, use_ecif=args.use_ecif)
    else:
        print("Use --pretrain, --finetune, --evaluate-5ht1a, or --full-pipeline")
        print("\nRecommended:")
        print("  python scripts/contrastive_v31.py --pretrain --epochs 200")
        print("  python scripts/contrastive_v31.py --finetune --finetune-epochs 100")
        print("  python scripts/contrastive_v31.py --evaluate-5ht1a")
