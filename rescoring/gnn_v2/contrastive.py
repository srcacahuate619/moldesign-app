"""
gnn_v2/contrastive.py — CL-GNN: Contrastive Learning Pretraining for GNN-v2.

Arquitectura:
  Fase 1 — Pre-training contrastivo (sin etiquetas):
    - Generar pares positivos: mismo complejo + ruido gaussiano en coords del ligando
    - Generar pares negativos: complejos diferentes
    - Loss: NT-Xent (InfoNCE) — maximiza similitud entre pares positivos,
            minimiza entre pares negativos
    - La GNN aprende un embedding invariante al ruido de docking

  Fase 2 — Fine-tuning:
    - Descartar la cabeza de proyección contrastiva
    - Agregar cabeza de clasificación (P(binder))
    - Fine-tune en PDBbind con BCE loss

  Fase 3 — Evaluación:
    - Validar en benchmark 5-HT1A (EF@1%, ROC-AUC)
    - Comparar contra GNN-v2 sin pretraining

Usage:
  python -m gnn_v2.contrastive --pretrain
  python -m gnn_v2.contrastive --finetune
  python -m gnn_v2.contrastive --evaluate
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader, Dataset

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from gnn_v2.data import PLComplexDataset
from gnn_v2.models import ContrastiveGNN, GNNv2Classifier, count_parameters
from gnn_v2.train import collate_complexes

ARTIFACTS_DIR = PROJECT_ROOT / "rescoring" / "artifacts"


# ═══════════════════════════════════════════════════════════════════════
# NT-Xent Loss
# ═══════════════════════════════════════════════════════════════════════

class NTXentLoss(nn.Module):
    """
    Normalized Temperature-Scaled Cross-Entropy Loss.
    
    Takes a batch of paired embeddings (z_i, z_j) where:
      - z_i and z_j are embeddings of positive pairs (same complex)
      - All other pairs in the batch are negatives
    """

    def __init__(self, temperature: float = 0.5):
        super().__init__()
        self.temperature = temperature

    def forward(self, z_anchor: torch.Tensor, z_positive: torch.Tensor) -> torch.Tensor:
        """
        Args:
            z_anchor: (B, D) embeddings of anchor examples
            z_positive: (B, D) embeddings of positive pairs
        Returns:
            NT-Xent loss (scalar)
        """
        batch_size = z_anchor.size(0)
        device = z_anchor.device

        # Normalize embeddings to unit sphere
        z_anchor = F.normalize(z_anchor, dim=1)
        z_positive = F.normalize(z_positive, dim=1)

        # Concatenate: [anchor_0, positive_0, anchor_1, positive_1, ...]
        z = torch.cat([z_anchor, z_positive], dim=0)  # (2B, D)

        # Similarity matrix (2B × 2B)
        sim = torch.mm(z, z.t()) / self.temperature  # (2B, 2B)

        # Mask: positive pairs are at (i, i+B) and (i+B, i)
        batch_size_2 = 2 * batch_size
        mask = torch.zeros((batch_size_2, batch_size_2), device=device, dtype=torch.bool)
        for i in range(batch_size):
            mask[i, i + batch_size] = True
            mask[i + batch_size, i] = True

        # Remove self-similarity (diagonal)
        sim_exp = torch.exp(sim.masked_fill(torch.eye(batch_size_2, device=device, dtype=torch.bool), -1e9))

        # Loss numerator: exp(sim(pos_pair))
        pos_sim = sim[mask]  # (2B,)

        # Loss denominator: sum(exp(sim(all_pairs_except_self)))
        denom = sim_exp.sum(dim=1)  # (2B,)

        loss = -torch.log(pos_sim / denom).mean()
        return loss


# ═══════════════════════════════════════════════════════════════════════
# Paired Dataset — positive pairs via coordinate noise
# ═══════════════════════════════════════════════════════════════════════

class PairedComplexDataset(Dataset):
    """
    Generates paired samples for contrastive learning.
    
    For each complex, creates a positive pair by adding gaussian noise
    to the ligand coordinates (simulating different docking poses).
    """

    def __init__(self, base_dataset: PLComplexDataset, noise_std: float = 0.2):
        self.base = base_dataset
        self.noise_std = noise_std

    def __len__(self):
        return len(self.base)

    def __getitem__(self, idx):
        item = self.base[idx]
        return item, item  # We add noise in collate function


def collate_contrastive(batch: list[tuple[dict, dict]]) -> dict:
    """Collate function that generates positive pairs by adding noise.
    
    Each batch contains (anchor, positive) pairs where the anchor
    is the original complex and positive has noise added to ligand coords.
    """
    anchors = [b[0] for b in batch]
    positives = [b[1] for b in batch]

    # Collate anchors normally
    anchor_batch = collate_complexes(anchors)

    # Collate positives (as separate batch)
    pos_batch = collate_complexes(positives)

    # Add gaussian noise to positive ligand coordinates
    noise = torch.randn_like(pos_batch["lig_pos"]) * 0.2
    pos_batch["lig_pos"] = pos_batch["lig_pos"] + noise

    return {
        "anchor": anchor_batch,
        "positive": pos_batch,
    }


# ═══════════════════════════════════════════════════════════════════════
# Pretraining
# ═══════════════════════════════════════════════════════════════════════

def pretrain(epochs: int = 200, batch_size: int = 16, lr: float = 1e-3):
    print("=" * 55)
    print("  CL-GNN: Contrastive Pretraining")
    print("=" * 55)

    # Load dataset (all PDBbind complexes for pretraining)
    print("\nLoading dataset...")
    ds = PLComplexDataset()
    print(f"  {len(ds)} complexes")

    paired_ds = PairedComplexDataset(ds, noise_std=0.2)
    loader = DataLoader(paired_ds, batch_size=batch_size, shuffle=True,
                        collate_fn=collate_contrastive, num_workers=0)

    # Model
    model = ContrastiveGNN(hidden_dim=64)
    print(f"  Parameters: {count_parameters(model):,}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    print(f"  Device: {device}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = NTXentLoss(temperature=0.5)

    best_loss = float("inf")

    print("\nPretraining...")
    t0 = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0

        for batch in loader:
            a = batch["anchor"]
            p = batch["positive"]

            # Move to GPU
            a = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in a.items()}
            p = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in p.items()}

            optimizer.zero_grad()

            z_anchor = model(a["prot_x"], a["prot_edge_index"], a["lig_x"], a["lig_edge_index"],
                             a["cross_edge_index"], lig_pos=a.get("lig_pos"), prot_pos=a.get("prot_pos"),
                             lig_batch=a["lig_batch"], prot_batch=a["prot_batch"])
            z_positive = model(p["prot_x"], p["prot_edge_index"], p["lig_x"], p["lig_edge_index"],
                               p["cross_edge_index"], lig_pos=p.get("lig_pos"), prot_pos=p.get("prot_pos"),
                               lig_batch=p["lig_batch"], prot_batch=p["prot_batch"])

            loss = criterion(z_anchor, z_positive)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            total_loss += loss.item()

        scheduler.step()

        avg_loss = total_loss / len(loader)

        if avg_loss < best_loss:
            best_loss = avg_loss
            torch.save({
                "model_state_dict": model.state_dict(),
                "loss": avg_loss,
                "epoch": epoch,
            }, ARTIFACTS_DIR / "clgnn_pretrained.pt")

        if epoch % 10 == 0 or epoch == 1:
            elapsed = time.time() - t0
            print(f"  Epoch {epoch:3d} | loss={avg_loss:.6f} | best={best_loss:.6f} | lr={scheduler.get_last_lr()[0]:.1e} | {elapsed:.0f}s")

    print(f"\nPretraining done in {(time.time()-t0)/60:.1f} min")
    print(f"Best loss: {best_loss:.6f}")
    print(f"Model: {ARTIFACTS_DIR / 'clgnn_pretrained.pt'}")


# ═══════════════════════════════════════════════════════════════════════
# Fine-tuning
# ═══════════════════════════════════════════════════════════════════════

def finetune(epochs: int = 100, batch_size: int = 16, lr: float = 5e-4):
    print("=" * 55)
    print("  CL-GNN: Fine-tuning")
    print("=" * 55)

    # Load dataset
    print("\nLoading dataset...")
    ds = PLComplexDataset()
    train_ds = [ds[i] for i in range(int(len(ds) * 0.8))]
    val_ds = [ds[i] for i in range(int(len(ds) * 0.8), len(ds))]
    print(f"  Train: {len(train_ds)}, Val: {len(val_ds)}")

    from gnn_v2.train import collate_complexes as collate_fn
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, collate_fn=collate_fn)

    # Model with pretrained encoder
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = GNNv2Classifier(hidden_dim=64).to(device)

    # Load pretrained weights
    pretrained_path = ARTIFACTS_DIR / "clgnn_pretrained.pt"
    if pretrained_path.exists():
        checkpoint = torch.load(pretrained_path, map_location=device, weights_only=False)
        contrastive_model = ContrastiveGNN(hidden_dim=64)
        contrastive_model.load_state_dict(checkpoint["model_state_dict"])
        contrastive_model.to(device)
        contrastive_model.load_pretrained_to_classifier(model)
        print(f"  Pretrained encoder loaded from epoch {checkpoint['epoch']}")
    else:
        print("  No pretrained model found. Training from scratch.")

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_acc = 0.0

    print("\nFine-tuning...")
    t0 = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0

        for batch in train_loader:
            batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
            optimizer.zero_grad()

            logits = model(batch["prot_x"], batch["prot_edge_index"], batch["lig_x"], batch["lig_edge_index"],
                          batch["cross_edge_index"], lig_pos=batch.get("lig_pos"), prot_pos=batch.get("prot_pos"),
                          lig_batch=batch["lig_batch"], prot_batch=batch["prot_batch"])
            loss = F.binary_cross_entropy_with_logits(logits, batch["y_binary"].float())
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()

        # Validation
        model.eval()
        val_probs, val_labels = [], []
        with torch.no_grad():
            for batch in val_loader:
                batch = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in batch.items()}
                logits = model(batch["prot_x"], batch["prot_edge_index"], batch["lig_x"], batch["lig_edge_index"],
                              batch["cross_edge_index"], lig_pos=batch.get("lig_pos"), prot_pos=batch.get("prot_pos"),
                              lig_batch=batch["lig_batch"], prot_batch=batch["prot_batch"])
                val_probs.append(torch.sigmoid(logits).cpu())
                val_labels.append(batch["y_binary"].cpu())

        val_probs = torch.cat(val_probs)
        val_labels = torch.cat(val_labels)
        val_acc = ((val_probs > 0.5) == val_labels).float().mean()
        scheduler.step()

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), ARTIFACTS_DIR / "clgnn_finetuned.pt")

        if epoch % 10 == 0 or epoch == 1:
            elapsed = time.time() - t0
            print(f"  Epoch {epoch:3d} | loss={total_loss/len(train_loader):.4f} | val_acc={val_acc:.4f} | best_acc={best_val_acc:.4f} | {elapsed:.0f}s")

    print(f"\nFine-tuning done in {(time.time()-t0)/60:.1f} min")
    print(f"Best val accuracy: {best_val_acc:.4f}")
    print(f"Model: {ARTIFACTS_DIR / 'clgnn_finetuned.pt'}")


# ═══════════════════════════════════════════════════════════════════════
# Evaluate on 5-HT1A
# ═══════════════════════════════════════════════════════════════════════

def evaluate():
    """Evaluate fine-tuned model on 5-HT1A benchmark."""
    print("=" * 55)
    print("  CL-GNN: Evaluation on 5-HT1A")
    print("=" * 55)

    import shutil
    import subprocess
    import tempfile

    from meeko import MoleculePreparation, PDBQTWriterLegacy
    from rdkit import Chem, RDLogger
    from rdkit.Chem import AllChem

    RDLogger.logger().setLevel(RDLogger.ERROR)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = GNNv2Classifier(hidden_dim=64).to(device)
    model_path = ARTIFACTS_DIR / "clgnn_finetuned.pt"
    if model_path.exists():
        model.load_state_dict(torch.load(model_path, map_location=device, weights_only=False))
        model.eval()
        print(f"  Model loaded: {model_path}")
    else:
        print("  No fine-tuned model found.")
        return

    # Load benchmark molecules and run inference
    data_dir = PROJECT_ROOT / "data"
    ck_path = data_dir / "benchmark_checkpoint_v2.json"
    if not ck_path.exists():
        print("  No benchmark checkpoint found.")
        return

    ck = json.loads(ck_path.read_text())
    results = ck["results"]
    print(f"  Benchmark molecules: {len(results)}")

    # For each molecule, run GNN + compare with existing scores
    from gnn_v2.data import (
        _build_cross_edges,
        _build_protein_graph,
        _parse_docked_pdbqt,
    )

    protein_pdb = str(data_dir / "7E2Y.pdb")
    vina_receptor = str(data_dir / "7E2Y_obabel.pdbqt")
    cx, cy, cz = 103.03, 114.79, 108.36

    predictions = []
    t0 = time.time()

    for i, r in enumerate(results[:50]):  # First 50 for speed
        smiles = r["smiles"]
        tmp_dir = tempfile.mkdtemp(prefix="clgnn_eval_")
        try:
            # Dock with Vina
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                continue
            mol = Chem.AddHs(mol)
            AllChem.EmbedMolecule(mol, AllChem.ETKDG())
            AllChem.MMFFOptimizeMolecule(mol)
            prep = MoleculePreparation()
            mol_setups = prep.prepare(mol)
            pdbqt_str, is_ok, _ = PDBQTWriterLegacy.write_string(mol_setups[0])
            if not is_ok:
                continue

            lig_path = os.path.join(tmp_dir, "lig.pdbqt")
            with open(lig_path, "w") as f:
                f.write(pdbqt_str)

            out_path = os.path.join(tmp_dir, "out.pdbqt")
            subprocess.run([
                str(PROJECT_ROOT / "tools" / "vina" / "vina.exe"),
                "--receptor", vina_receptor, "--ligand", lig_path,
                "--center_x", str(cx), "--center_y", str(cy), "--center_z", str(cz),
                "--size_x", "25", "--size_y", "25", "--size_z", "25",
                "--exhaustiveness", "4", "--num_modes", "1", "--out", out_path,
            ], capture_output=True, text=True, timeout=60)

            if not os.path.exists(out_path):
                continue

            # Build graphs
            parsed = _parse_docked_pdbqt(out_path)
            lig_coords = parsed["coords"][[i for i, e in enumerate(parsed["elements"]) if e not in ("H",)]]
            if len(lig_coords) == 0:
                continue

            # Quick ligand graph (use existing function from data.py)
            from gnn_v2.data import _build_ligand_graph as build_lig
            sdf_path = os.path.join(tmp_dir, "tmp.sdf")
            mol_sdf = Chem.MolFromSmiles(smiles)
            mol_sdf = Chem.AddHs(mol_sdf)
            AllChem.Compute2DCoords(mol_sdf)
            mol_sdf = Chem.RemoveHs(mol_sdf)
            writer = Chem.SDWriter(sdf_path)
            writer.write(mol_sdf)
            writer.close()

            lig_graph = build_lig(sdf_path, out_path)
            if lig_graph is None:
                continue

            prot_graph = _build_protein_graph(protein_pdb, lig_graph.pos.numpy())
            if prot_graph is None:
                continue

            cross_edges = _build_cross_edges(lig_graph.pos, prot_graph.pos)

            # GNN inference (single graph, no batch dim)
            with torch.no_grad():
                logits = model(
                    prot_graph.x.to(device),
                    prot_graph.edge_index.to(device),
                    lig_graph.x.to(device),
                    lig_graph.edge_index.to(device),
                    cross_edges.to(device),
                    lig_pos=lig_graph.pos.to(device),
                    prot_pos=prot_graph.pos.to(device),
                )
                prob = torch.sigmoid(logits).item()

            predictions.append({"smiles": smiles, "gnn_prob": prob, "actual": r["is_active"]})

        except Exception:
            pass
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        if (i + 1) % 10 == 0:
            elapsed = time.time() - t0
            print(f"  [{i+1}/{min(50,len(results))}] {elapsed:.0f}s | {(elapsed/(i+1)):.1f}s/mol")

    elapsed = time.time() - t0

    if len(predictions) > 1:
        from sklearn.metrics import roc_auc_score
        labels = [p["actual"] for p in predictions]
        probs = [p["gnn_prob"] for p in predictions]
        auc = roc_auc_score(labels, probs)
        active_probs = [p["gnn_prob"] for p in predictions if p["actual"]]
        decoy_probs = [p["gnn_prob"] for p in predictions if not p["actual"]]
        print(f"\n{'=' * 55}")
        print("  CL-GNN Benchmark Results (5-HT1A)")
        print(f"{'=' * 55}")
        print(f"  ROC-AUC: {auc:.4f}")
        print(f"  Active mean prob: {sum(active_probs)/len(active_probs):.4f}" if active_probs else "")
        print(f"  Decoy mean prob:  {sum(decoy_probs)/len(decoy_probs):.4f}" if decoy_probs else "")
        print(f"  N: {len(predictions)}")
        print(f"  Time: {elapsed:.0f}s ({elapsed/len(predictions):.1f}s/mol)")
    else:
        print("  Not enough predictions to evaluate.")


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CL-GNN: Contrastive Learning for GNN-v2")
    parser.add_argument("--pretrain", action="store_true", help="Contrastive pretraining")
    parser.add_argument("--finetune", action="store_true", help="Fine-tune on PDBbind")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate on 5-HT1A benchmark")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()

    if args.pretrain:
        pretrain(epochs=args.epochs, batch_size=args.batch_size, lr=args.lr)
    elif args.finetune:
        finetune(epochs=args.epochs, batch_size=args.batch_size, lr=args.lr)
    elif args.evaluate:
        evaluate()
    else:
        print("Use --pretrain, --finetune, or --evaluate")
        print("Recommended: --pretrain --epochs 200")
        print("Then:        --finetune --epochs 100")
        print("Then:        --evaluate")
