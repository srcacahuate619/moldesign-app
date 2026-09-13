"""
scripts/extract_ecif_pdbbind.py — Fase 1 GNN-v3.1
Extrae features ECIF/Shell (155 dim) para ~3887 PDBbind crystal complexes.
Output: data/gnn_v31/ecif_pdbbind_crystal.npz con:
  - X: (N, 155) float32
  - pid: PDB ids
  - y_pki: experimental pKi values
  - y_binary: 1 if pKi > 7 else 0

No extrae Morgan/RDKit descriptores (no usaremos para GNN). Solo interactions.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from feature_extractor import ALL_3D_FEATURES, InteractionFeatureExtractor

# Filtered to ONLY shell_ + ecif_ features (Características 3D estructurales)
ECIF_SHELL_KEYS = [k for k in ALL_3D_FEATURES if k.startswith("shell_") or k.startswith("ecif_")]
print(f"Using {len(ECIF_SHELL_KEYS)} ECIF/Shell features (96 shell + 56 ecif = {96+56})")

OUT_DIR = PROJECT_ROOT / "data" / "gnn_v31"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PDBBIND_DIR = PROJECT_ROOT / "data" / "pdbbind"
INDEX_PATH = PDBBIND_DIR / "INDEX_refined_data.2020"


def load_pki_labels():
    """Parse pKi values for refined set from INDEX."""
    labels = {}
    if not INDEX_PATH.exists():
        # try general index
        gen = PDBBIND_DIR / "INDEX_general_data.2020"
        if gen.exists():
            paths = [gen, INDEX_PATH]
        else:
            paths = [INDEX_PATH]
    else:
        paths = [INDEX_PATH]

    for p in paths:
        if not p.exists():
            continue
        with open(p) as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.strip().split()
                if len(parts) >= 6 and parts[4] == "//":
                    try:
                        pid = parts[0]
                        pki = float(parts[5])
                        labels[pid] = pki
                    except (ValueError, IndexError):
                        pass
    print(f"Loaded {len(labels)} pKi labels from INDEX")
    return labels


def main(range_start=None, range_end=None):
    os.chdir(PROJECT_ROOT / "rescoring")
    print(f"cwd={os.getcwd()}, PYTHONPATH={os.environ.get('PYTHONPATH','')}")
    print(f"OUT_DIR: {OUT_DIR}")
    ext = InteractionFeatureExtractor()
    print(f"ProLIF available: {ext.is_available}")

    pki_map = load_pki_labels()
    dirs = sorted([d for d in PDBBIND_DIR.iterdir()
                   if d.is_dir() and (d / f"{d.name}_protein.pdb").exists()
                   and (d / f"{d.name}_ligand.sdf").exists()])

    if range_start is not None and range_end is not None:
        original_total = len(dirs)
        dirs = dirs[range_start:range_end]
        suffix = f"_chunk_{range_start}_{range_end}"
        print(f"Sliced dirs from [{range_start}:{range_end}]: {len(dirs)} of {original_total}")
    else:
        suffix = ""
        out_path = OUT_DIR / "ecif_pdbbind_crystal.npz"
        if out_path.exists():
            print(f"SKIP (already exists): {out_path.name}")
            return

    out_path = OUT_DIR / f"ecif_pdbbind{suffix}.npz"
    if out_path.exists():
        print(f"SKIP (already exists): {out_path.name}")
        return

    print(f"Processing {len(dirs)} PDBbind dirs with protein.pdb + ligand.sdf")

    n_feat = len(ECIF_SHELL_KEYS)
    X = np.zeros((len(dirs), n_feat), dtype=np.float32)
    pids = [None] * len(dirs)
    pki_vals = np.zeros(len(dirs), dtype=np.float32)
    t0 = time.time()
    n_ok, n_zero, n_with_label = 0, 0, 0
    for i, d in enumerate(dirs):
        pid = d.name
        pdb = str(d / f"{pid}_protein.pdb")
        sdf = str(d / f"{pid}_ligand.sdf")
        try:
            feats = ext.extract_from_files(pdb, sdf)
        except Exception:
            feats = {}
        v = np.zeros(n_feat, dtype=np.float32)
        if feats:
            for j, k in enumerate(ECIF_SHELL_KEYS):
                val = feats.get(k)
                if val is not None:
                    try:
                        v[j] = float(val)
                    except (TypeError, ValueError):
                        pass
        nx = int((v != 0).sum())
        if nx > 0:
            X[i] = v
            n_ok += 1
        else:
            n_zero += 1
        pids[i] = pid
        if pid in pki_map:
            pki_vals[i] = pki_map[pid]
            n_with_label += 1
        else:
            pki_vals[i] = 0.0
        if (i + 1) % 100 == 0 or i == len(dirs) - 1:
            elapsed = time.time() - t0
            rate = (i + 1) / max(elapsed, 0.001)
            eta = (len(dirs) - i - 1) / max(rate, 0.001)
            print(f"  [{i+1}/{len(dirs)}] ok={n_ok} zero={n_zero} labeled={n_with_label}"
                  f" rate={rate:.1f}/s eta={eta:.0f}s")

    y_binary = (pki_vals > 7.0).astype(np.int8)
    np.savez_compressed(
        out_path,
        X=X,
        pid=np.array(pids, dtype=object),
        y_pki=pki_vals.astype(np.float32),
        y_binary=y_binary,
        feature_keys=np.array(ECIF_SHELL_KEYS, dtype=object),
    )
    elapsed = time.time() - t0
    print(f"\n=== CHUNK DONE ===")
    print(f"Range: {range_start}-{range_end} | Total time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"n_ok={n_ok} | n_zero={n_zero} | n_with_label={n_with_label}")
    print(f"X shape: {X.shape}")
    pki_pos = pki_vals[pki_vals > 0]
    if len(pki_pos) > 0:
        print(f"pKi stats: mean={pki_pos.mean():.2f}, median={np.median(pki_pos):.2f}, "
              f"min={pki_pos.min():.2f}, max={pki_pos.max():.2f}")
    print(f"y_binary: strong={y_binary.sum()}, weak={(pki_vals>0).sum()-y_binary.sum()}, "
          f"no_label={len(dirs)-n_with_label}")
    print(f"Saved → {out_path} ({out_path.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--range", nargs=2, type=int, default=None,
                        help="Process only dirs in range [START END] (zero-indexed)")
    args = parser.parse_args()
    if args.range:
        main(range_start=args.range[0], range_end=args.range[1])
    else:
        main()
