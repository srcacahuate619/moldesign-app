"""
scripts/train_gnn_v31.py — GNN-v3.1 multi-task training

Trains GNNv31Classifier with:
  - Primary BCE loss on P(binder)
  - Secondary MSE loss on ΔpKi = pKi - Vina_score (delta-learning)
  - ECIF/Shell 152-dim fusion (when available)

Train set = PDBbind crystal (865 with pKi labels) + 7 benchmark decoys cached
            (cdk2, er_alpha, factor_xa, hiv_protease, glp1r, thrombin, ca2)
            — EXCLUDING 5HT1A (held-out eval)

5HT1A never seen during training → final eval benchmark.

Usage:
  python scripts/train_gnn_v31.py --epochs 200 --batch-size 16 --lr 1e-3 --lambda-delta 0.3
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
from torch.utils.data import DataLoader, Dataset
from torch_geometric.data import Batch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from gnn_v2.models import GNNv31Classifier, count_parameters
from gnn_v2.data import (
    ELEMENTS, ELEM_TO_IDX, PDBBIND_DIR, INDEX_PATH, REDOCK_DIR,
    build_complex_graph,
)

OUT_DIR = PROJECT_ROOT / "data" / "gnn_v31"
ARTIFACTS = PROJECT_ROOT / "rescoring" / "artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


def load_v31_dataset():
    """Load the unificated dataset built by build_gnn_v31_dataset.py."""
    path = OUT_DIR / "dataset_v31.npz"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run scripts/build_gnn_v31_dataset.py first.")
    d = np.load(path, allow_pickle=True)
    return {
        "X_ecif": d["X_ecif"],
        "y_binary": d["y_binary"],
        "y_pki": d["y_pki"],
        "vina_score": d["vina_score"],
        "source": d["source"],
        "target_id": d["target_id"],
        "smiles": d["smiles"],
        "protein_pdb_path": d["protein_pdb_path"],
        "feature_keys": list(d["feature_keys"]),
    }


# ═══════════════════════════════════════════════════════════════════════
# Graph construction: convert benchmark cached entries into graph dicts
# Same shape as build_complex_graph(pid) → reuse `_smiles_to_2d_sdf` from inference.py
# ═══════════════════════════════════════════════════════════════════════

def _smiles_to_2d_sdf(smiles: str, tmp_dir: Path) -> str | None:
    """Minimal SMILES → SDF for graph construction."""
    from rdkit import Chem, RDLogger
    from rdkit.Chem import AllChem
    RDLogger.DisableLog("rdApp.*")
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        mol = Chem.AddHs(mol)
        AllChem.Compute2DCoords(mol)
        mol = Chem.RemoveHs(mol)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        path = tmp_dir / f"{abs(hash(smiles))}.sdf"
        w = Chem.SDWriter(str(path))
        w.write(mol)
        w.close()
        return str(path)
    except Exception:
        return None


def benchmark_entry_to_graph(entry: dict, target_pdb_path: str, smiles: str, tmp_dir: Path):
    """Build a complex graph dict from a cached benchmark entry.

    Reuses _build_ligand_graph / _build_protein_graph / _build_cross_edges from data.py.
    Returns dict like build_complex_graph or None.
    """
    from gnn_v2.data import _build_ligand_graph, _build_protein_graph, _build_cross_edges
    import tempfile

    pose_pdbqt = entry.get("pose_pdbqt", "")
    if not pose_pdbqt or len(pose_pdbqt) < 100:
        return None

    # Write PDBQT to temp file
    fd, pdbqt_path = tempfile.mkstemp(suffix=".pdbqt")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(pose_pdbqt)
        sdf_path = _smiles_to_2d_sdf(smiles, tmp_dir)
        if sdf_path is None:
            return None
        lig_graph = _build_ligand_graph(sdf_path, pdbqt_path)
        if lig_graph is None:
            return None
        try:
            os.unlink(sdf_path)
        except OSError:
            pass

        lig_coords = lig_graph.pos.numpy()
        prot_graph = _build_protein_graph(target_pdb_path, lig_coords)
        if prot_graph is None:
            return None
        cross_edges = _build_cross_edges(lig_graph.pos, prot_graph.pos)
        # Label info
        is_active = int(bool(entry.get("is_active", False)))
        pki_real = entry.get("pki_real")
        try:
            pki = float(pki_real) if pki_real is not None else 0.0
        except (TypeError, ValueError):
            pki = 0.0
        vina = entry.get("vina_score")
        try:
            vina_score = float(vina) if vina is not None else 0.0
        except (TypeError, ValueError):
            vina_score = 0.0

        return {
            "protein": prot_graph,
            "ligand": lig_graph,
            "cross": cross_edges,
            "y_pki": pki,
            "y_binary": is_active,
            "vina_score": vina_score,
            "pdb_id": smiles,
        }
    finally:
        try:
            os.unlink(pdbqt_path)
        except OSError:
            pass


import os


def build_pdbbind_sample(pid: str):
    """Build a PDBbind crystal graph sample. Returns dict like above."""
    return build_complex_graph(pid)


# ═══════════════════════════════════════════════════════════════════════
# Dataset class
# ═══════════════════════════════════════════════════════════════════════

class V31Dataset(Dataset):
    """Builds complex graphs on first access and caches them in RAM.

    Two types of samples:
      - PDBbind crystal (source_id=0): build graph from PDB+SDF+redocked PDBQT
      - Benchmark cached (source_id>0): build graph from cached pose_pdbqt+target_pdb
    """

    def __init__(self, indices: list[int], dataset_meta: dict, tmp_dir: Path,
                 ecif_cache_path: Path | None = None, include_pdbbind: bool = True,
                 preloaded_ckpts: dict | None = None):
        self.dataset_meta = dataset_meta
        self.tmp_dir = tmp_dir
        self.indices = indices
        self.include_pdbbind = include_pdbbind
        self.preloaded_ckpts = preloaded_ckpts or {}

        # Load ECIF cache (z-scored) keyed by sample index in the FULL dataset
        self.ecif_cache = None
        if ecif_cache_path and ecif_cache_path.exists():
            self.ecif_cache = np.load(ecif_cache_path)

        # Lazily constructed graphs (cached per global index)
        self._graphs_cache: dict[int, dict | None] = {}

    def preload_all(self, name: str = ""):
        """Build all graphs in this dataset eagerly (one-time cost, O(0.3s * N)).

        Prints progress to stdout.
        """
        t0 = time.time()
        n_ok = n_fail = 0
        for i, idx in enumerate(self.indices):
            if idx in self._graphs_cache:
                continue
            g = self._get_graph(idx)
            if g is None:
                n_fail += 1
            else:
                n_ok += 1
            if (i + 1) % 200 == 0 or i == len(self.indices) - 1:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (len(self.indices) - i - 1) / rate if rate > 0 else 0
                print(f"    [{name}] preload {i+1}/{len(self.indices)} ok={n_ok} fail={n_fail} eta={eta:.0f}s")
        print(f"    [{name}] preload done in {time.time()-t0:.1f}s (ok={n_ok} fail={n_fail})")

    def __len__(self):
        return len(self.indices)

    def _get_graph(self, idx: int):
        if idx in self._graphs_cache:
            return self._graphs_cache[idx]
        meta = self.dataset_meta
        source = int(meta["source"][idx])
        if source == 0:
            # PDBbind crystal
            pid = meta["smiles"][idx]  # for source=0, smiles holds pid
            graph = build_pdbbind_sample(pid)
        else:
            # Need to load benchmark entry — load entire checkpoint again
            # This is suboptimal; speed up via passsing pre-loaded results
            target_name = self._target_name_for_source(source)
            ckpt_path = OUT_DIR / "checkpoints" / f"benchmark_checkpoint_{target_name}.json"
            with open(ckpt_path) as f:
                r = json.load(f)
            results = r["results"]
            # Find idx-th entry for this source in global idx array
            # We stored idx relative to global dataset
            # Filter results by source match
            sm = meta["smiles"][idx]
            target_pdb = meta["protein_pdb_path"][idx]
            # Find entry with this smiles position
            # We use the smiles for ID — but it might collide
            # Build from any cache reasonable
            entry = None
            for ent in results:
                if ent.get("smiles") == sm:
                    entry = ent
                    break
            if entry is None:
                # fallback to first result
                entry = results[0]
            graph = benchmark_entry_to_graph(entry, target_pdb, sm, self.tmp_dir)
        self._graphs_cache[idx] = graph
        return graph

    def _target_name_for_source(self, source: int) -> str:
        m = {
            1: "cdk2", 2: "er_alpha", 3: "factor_xa", 4: "hiv_protease",
            5: "glp1r", 6: "thrombin", 7: "ca2", 8: "5ht1a"
        }
        return m.get(source, "?")

    def __getitem__(self, position: int):
        idx = self.indices[position]
        graph = self._get_graph(idx)
        if graph is None:
            return None  # collate filters out
        ecif_vec = None
        if self.ecif_cache is not None:
            try:
                ecif_vec = self.ecif_cache["X"][idx]
            except Exception:
                ecif_vec = None
        return {
            **graph,
            "ecif": ecif_vec,
            "_source": int(self.dataset_meta["source"][idx]),
            "_target_id": int(self.dataset_meta["target_id"][idx]),
            "_global_idx": idx,
        }


# ═══════════════════════════════════════════════════════════════════════
# Collate
# ═══════════════════════════════════════════════════════════════════════

def collate_v31(batch: list) -> dict | None:
    batch = [b for b in batch if b is not None]
    if not batch:
        return None
    proteins = [item["protein"] for item in batch]
    ligands = [item["ligand"] for item in batch]
    prot_batch = Batch.from_data_list(proteins)
    lig_batch = Batch.from_data_list(ligands)

    cross_edges = []
    prot_offset, lig_offset = 0, 0
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
        torch.cat(cross_edges, dim=1) if cross_edges
        else torch.empty((2, 0), dtype=torch.long)
    )

    y_binary = torch.tensor([item["y_binary"] for item in batch], dtype=torch.float32)
    y_pki = torch.tensor([item.get("y_pki", 0.0) for item in batch], dtype=torch.float32)
    vina_score = torch.tensor([item.get("vina_score", 0.0) for item in batch], dtype=torch.float32)
    # ΔpKi target: only defined when both pKi and Vina are present
    y_delta = y_pki - vina_score
    has_delta = ((y_pki > 0) & (vina_score != 0)).float()

    ecifs = []
    for item in batch:
        e = item.get("ecif")
        if e is None:
            ecifs.append(np.zeros(152, dtype=np.float32))
        else:
            ecifs.append(np.asarray(e, dtype=np.float32))
    ecif_tensor = torch.from_numpy(np.stack(ecifs))

    return {
        "prot_x": prot_batch.x,
        "prot_edge_index": prot_batch.edge_index,
        "prot_batch": prot_batch.batch,
        "lig_x": lig_batch.x,
        "lig_edge_index": lig_batch.edge_index,
        "lig_batch": lig_batch.batch,
        "cross_edge_index": cross_batch,
        "y_binary": y_binary,
        "y_pki": y_pki,
        "y_delta": y_delta,
        "has_delta": has_delta,
        "vina_score": vina_score,
        "ecif": ecif_tensor,
    }


# ═══════════════════════════════════════════════════════════════════════
# Train / val loop
# ═══════════════════════════════════════════════════════════════════════

def to_device(batch, device):
    return {k: v.to(device) if torch.is_tensor(v) else v for k, v in batch.items()}


def train_epoch(model, loader, optimizer, device, lambda_delta):
    model.train()
    total, ok, bce_acc, delta_acc, correct = 0, 0, 0.0, 0.0, 0
    for batch in loader:
        if batch is None:
            continue
        batch = to_device(batch, device)
        out = model(
            batch["prot_x"], batch["prot_edge_index"],
            batch["lig_x"], batch["lig_edge_index"],
            batch["cross_edge_index"],
            lig_batch=batch["lig_batch"], prot_batch=batch["prot_batch"],
            ecif=batch["ecif"],
        )
        prob_logit, delta_pred = out
        bce = F.binary_cross_entropy_with_logits(prob_logit, batch["y_binary"])
        # delta only where both pKi and vina are known
        if lambda_delta > 0 and batch["has_delta"].sum() > 0:
            mask = batch["has_delta"].bool()
            mse = F.mse_loss(delta_pred[mask], batch["y_delta"][mask])
            loss = bce + lambda_delta * mse
            delta_acc += float(mse.item())
        else:
            loss = bce
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        total += len(batch["y_binary"])
        ok += 1
        bce_acc += float(bce.item())
        pred = (torch.sigmoid(prob_logit) > 0.5).float()
        correct += int((pred == batch["y_binary"]).sum().item())
    n = max(ok, 1)
    return bce_acc / n, (delta_acc / n if lambda_delta > 0 else 0.0), correct / max(total, 1)


@torch.no_grad()
def eval_model(model, loader, device):
    model.eval()
    ys, ps = [], []
    for batch in loader:
        if batch is None:
            continue
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
    return {
        "roc_auc": float(roc_auc_score(ys, ps)),
        "pr_auc": float(average_precision_score(ys, ps)),
    }


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
    p.add_argument("--max-pdbbind", type=int, default=0, help="0=all, >0 subsample")
    args = p.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = (args.device if args.device != "auto"
              else ("cuda" if torch.cuda.is_available() else "cpu"))
    print(f"Device: {device}")

    print("\n=== Loading dataset v3.1 ===")
    meta = load_v31_dataset()
    print(f"  Total: {len(meta['X_ecif'])}")
    print(f"  Train candidates (excl 5ht1a): "
          f"{int((meta['source'] != 8).sum())}")
    print(f"  5HT1A held-out: {int((meta['source'] == 8).sum())}")

    # Build training index list (exclude 5HT1A = source 8)
    train_indices_all = [i for i, s in enumerate(meta["source"]) if s != 8]

    # Subsample PDBbind if requested
    if args.max_pdbbind > 0:
        non_pp = [i for i in train_indices_all if meta["source"][i] != 0]
        pp_ids = [i for i in train_indices_all if meta["source"][i] == 0]
        random.shuffle(pp_ids)
        pp_ids = pp_ids[:args.max_pdbbind]
        train_indices_all = pp_ids + non_pp

    # Stratify seed-based split: 80/10/10
    random.shuffle(train_indices_all)
    n = len(train_indices_all)
    n_val = max(1, n // 10)
    n_test = max(1, n // 10)
    n_train = n - n_val - n_test
    train_idx = train_indices_all[:n_train]
    val_idx = train_indices_all[n_train:n_train + n_val]
    test_idx = train_indices_all[n_train + n_val:]
    print(f"  Split: train={len(train_idx)} val={len(val_idx)} test={len(test_idx)}")

    # ECIF cache with z-score normalization (PDBbind stats) — fallback to no norm
    ecif_norm_path = OUT_DIR / "ecif_norm_stats.npz"
    # ECIF dataset: pre-build one large npz with z-scored features so the Dataset can index by global idx
    ecif_cache = OUT_DIR / "ecif_all_zscored.npz"
    if not ecif_cache.exists():
        print("  (Note: ecif_all_zscored.npz not present — falling back to dataset_v31 Npz for ECIF)")
        # We'll feed raw from meta directly
        # Build on-the-fly cache: write z-scored ECIF keyed by ALL indices (including held-out)
        X = meta["X_ecif"]
        # Use PDBbind-only indices (source==0) for computing mean/std, more representative of "data distribution"
        src = meta["source"]
        pp_mask = (src == 0)
        if pp_mask.sum() == 0:
            print("  WARN: no PDBbind samples — using ALL samples for z-score stats")
            usage = X
        else:
            usage = X[pp_mask]
        mean = usage.mean(axis=0, keepdims=True)
        std = usage.std(axis=0, keepdims=True) + 1e-8
        X_z = (X - mean) / std
        # Replace NaNs (from missing features)
        X_z = np.nan_to_num(X_z, nan=0.0, posinf=0.0, neginf=0.0)
        np.savez_compressed(ecif_cache, X=X_z.astype(np.float32),
                            mean=mean, std=std)
        print(f"  Wrote {ecif_cache.name} (X z-scored on PDBbind stats)")
    else:
        print(f"  {ecif_cache.name} exists")

    # Pre-load checkpoint into memory to avoid re-parsing (massive speedup)
    preloaded = {}
    for src_name in ["cdk2", "er_alpha", "factor_xa", "hiv_protease",
                     "glp1r", "thrombin", "ca2"]:
        ck = OUT_DIR / "checkpoints" / f"benchmark_checkpoint_{src_name}.json"
        if ck.exists():
            with open(ck) as f:
                preloaded[src_name] = {r.get("smiles"): r for r in json.load(f)["results"]}
    print(f"  Preloaded checkpoint dicts: {list(preloaded.keys())}")

    # Patch Dataset to use preloaded lookup via attribute
    def fast_get_graph(self, idx):
        if idx in self._graphs_cache:
            return self._graphs_cache[idx]
        meta = self.dataset_meta
        src = int(meta["source"][idx])
        if src == 0:
            pid = meta["smiles"][idx]
            graph = build_pdbbind_sample(pid)
        else:
            name = self._target_name_for_source(src)
            sm = meta["smiles"][idx]
            target_pdb = meta["protein_pdb_path"][idx]
            entry = self.preloaded_ckpts.get(name, {}).get(sm)
            if entry is None:
                entry = {"smiles": sm, "pose_pdbqt": "", "is_active": 0, "vina_score": 0,
                         "pki_real": None}
            graph = benchmark_entry_to_graph(entry, target_pdb, sm, self.tmp_dir)
        self._graphs_cache[idx] = graph
        return graph

    V31Dataset._get_graph = fast_get_graph

    tmp_dir = PROJECT_ROOT / "tmp" / "gnn_v31"
    train_ds = V31Dataset(train_idx, meta, tmp_dir, ecif_cache_path=None,
                          include_pdbbind=True, preloaded_ckpts=preloaded)
    val_ds = V31Dataset(val_idx, meta, tmp_dir, include_pdbbind=True,
                        preloaded_ckpts=preloaded)
    test_ds = V31Dataset(test_idx, meta, tmp_dir, include_pdbbind=True,
                         preloaded_ckpts=preloaded)

    # Pre-build all graphs eagerly (one-time cost ~30-50 min for 15K samples)
    print(f"\n=== Pre-building graphs (this may take 30-50 min) ===")
    train_ds.preload_all("train")
    val_ds.preload_all("val")
    test_ds.preload_all("test")
    print(f"  Done. Train={len(train_ds._graphs_cache)}, val={len(val_ds._graphs_cache)}, "
          f"test={len(test_ds._graphs_cache)} cached")

    # Workers = 0 on Windows typically
    loaders = {
        "train": DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                            collate_fn=collate_v31, num_workers=0),
        "val": DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                          collate_fn=collate_v31, num_workers=0),
        "test": DataLoader(test_ds, batch_size=args.batch_size, shuffle=False,
                           collate_fn=collate_v31, num_workers=0),
    }

    model = GNNv31Classifier(
        hidden_dim=args.hidden_dim,
        dropout=args.dropout,
        ecif_in=152,
        use_delta_head=(args.lambda_delta > 0),
    ).to(device)
    n_params = count_parameters(model)
    print(f"\nModel parameters: {n_params:,}")

    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-6)

    best_val_auc = 0.0
    best_epoch = -1
    patience_left = args.patience
    out_pt = ARTIFACTS / "gnn_v31_best.pt"

    print(f"\n=== Training {args.epochs} epochs (batch={args.batch_size}) ===")
    t_start = time.time()
    history = []
    for epoch in range(1, args.epochs + 1):
        bce_loss, delta_loss, train_acc = train_epoch(
            model, loaders["train"], optimizer, device, args.lambda_delta)
        val_metrics = eval_model(model, loaders["val"], device)
        scheduler.step()
        msg = (f"Epoch {epoch:3d} | BCE {bce_loss:.4f} | Δ {delta_loss:.4f} | "
               f"train_acc {train_acc:.3f} | val_AUC {val_metrics['roc_auc']:.4f}")
        history.append({
            "epoch": epoch, "bce": bce_loss, "delta": delta_loss,
            "train_acc": train_acc, "val_auc": val_metrics["roc_auc"],
            "val_pr": val_metrics["pr_auc"],
        })

        if val_metrics["roc_auc"] > best_val_auc:
            best_val_auc = val_metrics["roc_auc"]
            best_epoch = epoch
            patience_left = args.patience
            torch.save(model.state_dict(), out_pt)
            msg += "  ★ (saved)"
        else:
            patience_left -= 1
            msg += f"  (patience {patience_left})"

        elapsed = time.time() - t_start
        print(f"  {msg}  [{elapsed:.0f}s]")

        if patience_left <= 0:
            print(f"Early stopping at epoch {epoch}")
            break

    # Final test
    print("\n=== Test set evaluation ===")
    # Load best weights
    model.load_state_dict(torch.load(out_pt, weights_only=False))
    test_metrics = eval_model(model, loaders["test"], device)
    print(f"Test ROC-AUC: {test_metrics['roc_auc']:.4f}")
    print(f"Test PR-AUC:  {test_metrics['pr_auc']:.4f}")

    results = {
        "best_val_auc": best_val_auc,
        "best_epoch": best_epoch,
        "n_params": n_params,
        "n_train": len(train_idx), "n_val": len(val_idx), "n_test": len(test_idx),
        "test_metrics": test_metrics,
        "config": vars(args),
        "device": device,
        "total_time_s": round(time.time() - t_start, 1),
        "history": history,
    }
    out_json = ARTIFACTS / "gnn_v31_results.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Done. Artifacts:")
    print(f"  {out_pt}  ({out_pt.stat().st_size/1024:.0f} KB)")
    print(f"  {out_json}")
    print(f"\n=== Next step: run scripts/eval_gnn_v31_5ht1a.py ===")


if __name__ == "__main__":
    main()
