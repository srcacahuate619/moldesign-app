"""Quick smoke test — verify train_gnn_v31.py plumbing works on sample subset.

Tests:
1. Load dataset_v31.npz
2. Random sample 30 entries
3. Build graph for each (10 PDBbind + 10 benchmark)
4. Pass through collate_fn
5. Forward through GNNv31Classifier
6. Compute BCE loss + delta loss
"""
import sys, json, time, os, tempfile
from pathlib import Path
import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from gnn_v2.models import GNNv31Classifier
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from train_gnn_v31 import (
    load_v31_dataset, V31Dataset, collate_v31, build_pdbbind_sample,
    benchmark_entry_to_graph,
)

print("Loading dataset...")
meta = load_v31_dataset()
print(f"Total: {len(meta['X_ecif'])}, Train candidates (excl 5ht1a): {int((meta['source'] != 8).sum())}")

# Sample 10 random (NOT 5ht1a) + 10 PDBbind if available
random_idx = list(np.random.RandomState(42).choice(
    [i for i, s in enumerate(meta['source']) if s != 8], size=20, replace=False))

print(f"\nBuilding {len(random_idx)} graphs...")
tmp_dir = PROJECT_ROOT / "tmp" / "gnn_v31"
tmp_dir.mkdir(parents=True, exist_ok=True)

# Pre-build dict
pid_set = set()
from collections import defaultdict
smi_lookup_per_target = defaultdict(dict)
from train_gnn_v31 import V31Dataset as V31
ds = V31(random_idx, meta, tmp_dir, ecif_cache_path=None, include_pdbbind=True)

import json as json_mod
# Pre-load checkpoints
for src_id, src_name in [(1, "cdk2"), (2, "er_alpha"), (3, "factor_xa"),
                         (4, "hiv_protease"), (5, "glp1r"), (6, "thrombin"), (7, "ca2")]:
    ck = PROJECT_ROOT / "data" / "gnn_v31" / "checkpoints" / f"benchmark_checkpoint_{src_name}.json"
    if ck.exists():
        with open(ck) as f:
            for r in json_mod.load(f)["results"]:
                smi_lookup_per_target[src_name][r.get("smiles")] = r

# Patch dataset
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
        entry = smi_lookup_per_target.get(name, {}).get(sm)
        if entry is None:
            entry = {"smiles": sm, "pose_pdbqt": "", "is_active": 0, "vina_score": 0, "pki_real": None}
        graph = benchmark_entry_to_graph(entry, target_pdb, sm, self.tmp_dir)
    self._graphs_cache[idx] = graph
    return graph

V31Dataset._get_graph = fast_get_graph

# Time to load each
t0 = time.time()
ok = 0
fail = 0
times = []
for i, p in enumerate(random_idx):
    st = time.time()
    g = ds._get_graph(p)
    el = time.time() - st
    times.append(el)
    if g is not None:
        ok += 1
    else:
        fail += 1
    if i < 5 or g is None:
        src = int(meta["source"][p])
        nm = ds._target_name_for_source(src) if src > 0 else "pdbbind"
        print(f"  [{i+1}] src={src}({nm}) graph={'OK' if g else 'NONE'} time={el:.1f}s")
print(f"\nOK: {ok}, FAIL: {fail}, mean_time: {np.mean(times):.2f}s, total: {time.time()-t0:.1f}s")

# Build batch via collate
print("\n=== Building batch of 8 ===")
batch_items = [ds[i] for i in range(8)]
batch = collate_v31(batch_items)
if batch is None:
    print("Batch is empty!")
else:
    print(f"Batch prot_x shape: {batch['prot_x'].shape}")
    print(f"Batch lig_x shape: {batch['lig_x'].shape}")
    print(f"Batch y_binary: {batch['y_binary']}")
    print(f"Batch y_delta: {batch['y_delta']}")
    print(f"Batch has_delta: {batch['has_delta']}")
    print(f"Batch vina_score: {batch['vina_score']}")
    print(f"Batch ecif shape: {batch['ecif'].shape}")

print("\n=== Forward through GNNv31Classifier ===")
device = "cpu"
model = GNNv31Classifier(hidden_dim=64, ecif_in=152, use_delta_head=True).to(device)
print(f"Params: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")
batch_t = {k: v.to(device) if torch.is_tensor(v) else v for k, v in batch.items()}
prob_logit, delta_pred = model(
    batch_t["prot_x"], batch_t["prot_edge_index"],
    batch_t["lig_x"], batch_t["lig_edge_index"],
    batch_t["cross_edge_index"],
    lig_batch=batch_t["lig_batch"], prot_batch=batch_t["prot_batch"],
    ecif=batch_t["ecif"],
)
print(f"prob_logit: {prob_logit.shape}")
print(f"delta_pred: {delta_pred.shape}")

# Compute loss
import torch.nn.functional as F
bce = F.binary_cross_entropy_with_logits(prob_logit, batch_t["y_binary"])
mask = batch_t["has_delta"].bool()
if mask.sum() > 0:
    mse = F.mse_loss(delta_pred[mask], batch_t["y_delta"][mask])
    total = bce + 0.3 * mse
    print(f"BCE: {bce.item():.4f}, MSE(Δ): {mse.item():.4f}, Total: {total.item():.4f}")
else:
    print(f"BCE only: {bce.item():.4f} (no delta samples in batch)")
print("\n=== Smoke test OK ===")
