#!/usr/bin/env python3
"""Check which checkpoints have molchamb_score and what GPU work remains."""
import json
import subprocess
import sys
from pathlib import Path

ckpt_dir = Path("data/molchamb_loto/checkpoints")

# Check GPU availability
try:
    import torch
    has_cuda = torch.cuda.is_available()
    if has_cuda:
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_mem / 1024**3
        print(f"GPU: {gpu_name} ({gpu_mem:.1f} GB)")
    else:
        print("GPU: NOT AVAILABLE (CUDA)")
except ImportError:
    print("GPU: PyTorch not available")
    has_cuda = False

print()

for ckpt_path in sorted(ckpt_dir.glob("*.json")):
    target = ckpt_path.stem.replace("benchmark_checkpoint_", "")
    text = ckpt_path.read_text()

    # Find results array and parse first entry
    results_idx = text.index('"results"')
    chunk = text[results_idx+10:results_idx+5000]

    depth = 0
    for i, c in enumerate(chunk):
        if c == "{": depth += 1
        if c == "}": depth -= 1
        if depth == 0:
            first_result = json.loads(chunk[:i+1])
            break
    else:
        print(f"{target}: Could not parse first result")
        continue

    r = first_result
    has_pose = bool(r.get("pose_pdbqt", ""))
    has_mc = "molchamb_score" in r
    has_ums = "universal_metal_score" in r
    has_gnn = "gnn_d_prob" in r
    n = len(json.loads(ckpt_path.read_bytes()[:200].decode())) if False else "?"
    size_mb = ckpt_path.stat().st_size / (1024*1024)

    # Quick count: count '"pose_pdbqt"' occurrences (each mol has one)
    n_mols = text.count('"is_active"')
    if n_mols == 0:
        n_mols = text.count('"smiles"')
    n_mols = max(1, n_mols - 1)

    flags = ""
    if has_mc: flags += " MC"
    if has_ums: flags += " UMS"
    if has_gnn: flags += " GNN"
    if not has_pose: flags += " NO-POSE"

    print(f"{target:15s}| {n_mols:5d} mols |{flags:20s} | {size_mb:5.0f}MB")

# What GPU work is available NOW?
print()
print("=" * 60)
print("GPU-ACCELERATED WORK AVAILABLE NOW:")
print("=" * 60)

# Check if MolChamb populated = can run MolChamb on GPU
print()
print("[1] MolChamb quantum scores (GPU with PyTorch):")
print("    - Already populated: 5ht1a, ca2, cdk2, er_alpha, factor_xa, hiv_protease, thrombin")
print("    - Needs checkpoint first: mmp9, ace, pde5a (waiting for Vina docking)")

print()
print("[2] GNN-D inference (GPU, ~0.3s/mol):")
print("    - Already computed: 7 LOTO models (gnn_d_loto_*.pt)")
print("    - Available for GPU re-scoring: ALL 7 targets")

print()
print("[3] Train metal-aware GNN-D with UMS as feature:")
print("    - USES GPU: train loop + inference")
print("    - Could start NOW with 8 existing checkpoints + UMS scores")
print("    - This is the most impactful GPU work available")

print()
if has_cuda:
    print(f"RECOMMENDATION: Use GPU to train a metal-aware GNN-D model")
    print(f"that takes Universal Metal Score as an input feature,")
    print(f"while CPU processes finish Vina docking overnight.")
else:
    print("No GPU detected. Work remains CPU-bound.")
