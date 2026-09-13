"""
scripts/build_gnn_v31_dataset.py — Fase 2 GNN-v3.1
Unifica todos los benchmarks cached (con features inline) + PDBbind ECIF extraído,
en un unico dataset en memoria (npz) listo para training.

Output:
  data/gnn_v31/dataset_v31.npz con keys:
    - X_ecif: (N_total, 152) float32 ECIF/Shell features
    - y_binary: (N_total,) int8 (1 si binder, 0 si decoy)
    - y_pki: (N_total,) float32 (pKi real si disponible, 0 sino)
    - vina_score: (N_total,) float32 (Vina score; 0 si training PDBbind crystal)
    - source: (N_total,) int8 (0=pdbbind, 1=cdk2, 2=er_alpha, 3=factor_xa, 4=hivp, 5=glp1r, 6=thrombin, 7=ca2, 8=5ht1a_heldout)
    - smiles: (N_total,) object
    - target_id: (N_total,) int8 (target index)
    - protein_pdb_path: (N_total,) object (path al PDB target, "" si PDBbind crystal propio)

5HT1A marcado como held-out (source=8) y NO entra al training split.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "data" / "gnn_v31"

# Target map: name → (target_pdb, source_id, family, is_heldout)
TARGET_MAP = {
    "cdk2":         ("3PP0.pdb", 1, "kinase", False),
    "er_alpha":     ("3ERT.pdb", 2, "nuclear_receptor", False),
    "factor_xa":   ("3CYX.pdb", 3, "protease", False),
    "hiv_protease": ("1HSG.pdb", 4, "protease", False),
    "glp1r":        ("6X1A.pdb", 5, "gpcr", False),
    "thrombin":     ("1e66.pdb", 6, "protease", False),
    "ca2":          ("3dc3.pdb", 7, "metaloenzyme", False),
    "5ht1a":        ("7E2Y.pdb", 8, "gpcr", True),  # HELD-OUT
}

# Feature keys comunes (definidos en feature_extractor.py como SHELL_FEATURES + ECIF_FEATURES)
ECIF_SHELL_PREFIXES = ("shell_", "ecif_")


def load_benchmark(name: str):
    """Load benchmark checkpoints returning dict with raw data."""
    path = OUT_DIR / "checkpoints" / f"benchmark_checkpoint_{name}.json"
    if not path.exists():
        print(f"  WARN: {name} checkpoint missing: {path}")
        return None
    with open(path) as f:
        r = json.load(f)
    return r["results"]


def feats_to_vec(feats: dict, keys_in_order: list[str]) -> np.ndarray:
    """Extract 152-dim ECIF/Shell vector."""
    v = np.zeros(len(keys_in_order), dtype=np.float32)
    if not feats or not isinstance(feats, dict):
        return v
    for i, k in enumerate(keys_in_order):
        try:
            v[i] = float(feats.get(k, 0.0))
        except (TypeError, ValueError):
            pass
    return v


def collect_benchmark_features(results: list, name: str):
    """Extract X_ecif (N, 152) and labels for a benchmark."""
    feats_keys = sorted([k for k in results[0].get("features", {})
                         if any(k.startswith(p) for p in ECIF_SHELL_PREFIXES)])
    print(f"  {name}: {len(results)} mols, {len(feats_keys)} ECIF/Shell features")

    X = np.zeros((len(results), len(feats_keys)), dtype=np.float32)
    y_binary = np.zeros(len(results), dtype=np.int8)
    y_pki = np.zeros(len(results), dtype=np.float32)
    vina_score = np.zeros(len(results), dtype=np.float32)
    smiles = [None] * len(results)

    n_with_pose = 0
    for i, ent in enumerate(results):
        smi = ent.get("smiles")
        smiles[i] = smi
        feats = ent.get("features", {})
        v = feats_to_vec(feats, feats_keys)
        nx = int((v != 0).sum())
        if nx > 0:
            X[i] = v
            n_with_pose += 1
        y_binary[i] = int(bool(ent.get("is_active", False)))
        try:
            y_pki[i] = float(ent.get("pki_real") or 0.0)
        except (TypeError, ValueError):
            y_pki[i] = 0.0
        try:
            vina_score[i] = float(ent.get("vina_score", 0.0))
        except (TypeError, ValueError):
            vina_score[i] = 0.0
    print(f"    {n_with_pose} mols with non-zero ECIF vector")
    return X, y_binary, y_pki, vina_score, smiles, feats_keys


def main():
    print(f"OUT_DIR: {OUT_DIR}")

    # First, collect all benchmarks
    all_X = []
    all_yb = []
    all_yp = []
    all_vina = []
    all_smi = []
    all_src = []
    all_target_id = []
    all_target_pdb = []

    # Validate feature keys equal across all benchmarks
    base_keys = None
    for name in TARGET_MAP:
        results = load_benchmark(name)
        if not results:
            continue
        # Get key set
        feats_keys = sorted([k for k in results[0].get("features", {})
                             if any(k.startswith(p) for p in ECIF_SHELL_PREFIXES)])
        if base_keys is None:
            base_keys = feats_keys
            print(f"Base features ({len(base_keys)}): {base_keys[:3]}...{base_keys[-2:]}")
        elif feats_keys != base_keys:
            print(f"  DIFF! {name} has different feature set. {len(feats_keys)} vs {len(base_keys)}")
            print(f"   keys diff: {set(feats_keys).symmetric_difference(set(base_keys))}")

    target_id_map = {n: i+1 for i, n in enumerate(sorted(TARGET_MAP.keys()))}
    if base_keys is None:
        print("No benchmark data found.")
        return

    # Re-iterate collecting
    for name, (pdb_path, src_id, family, is_heldout) in TARGET_MAP.items():
        results = load_benchmark(name)
        if not results:
            continue
        X, yb, yp, vs, smi, _ = collect_benchmark_features(results, name)
        all_X.append(X)
        all_yb.append(yb)
        all_yp.append(yp)
        all_vina.append(vs)
        all_smi.extend(smi)
        all_src.append(np.full(len(X), src_id, dtype=np.int8))
        all_target_id.append(np.full(len(X), target_id_map[name], dtype=np.int8))
        all_target_pdb.extend([str(PROJECT_ROOT / "data" / "targets" / pdb_path)] * len(X))

    # Now add PDBbind ECIF (from intensive extraction)
    pdbbind_npz = OUT_DIR / "ecif_pdbbind_crystal.npz"
    if not pdbbind_npz.exists():
        print(f"\nWARN: PDBbind ECIF missing ({pdbbind_npz.name}). Proceeding without it.")
        n_pp = 0
    else:
        pp = np.load(pdbbind_npz, allow_pickle=True)
        X_pp = pp["X"]
        pid_pp = list(pp["pid"])
        y_pki_pp = pp["y_pki"]
        y_binary_pp = pp["y_binary"]
        # Sanity check feature alignment with base_keys (152 expected)
        X_pp_keys = list(pp["feature_keys"])
        if X_pp_keys != base_keys:
            print(f"\nWARNING: PDBbind ECIF feature keys differ from benchmarks!")
            print(f"  PDBbind ({len(X_pp_keys)}): {X_pp_keys[:3]}...")
            print(f"  Benchmark ({len(base_keys)}): {base_keys[:3]}...")
            # Pad/align to be safe
            aligned = np.zeros((X_pp.shape[0], len(base_keys)), dtype=np.float32)
            for i, k in enumerate(base_keys):
                if k in X_pp_keys:
                    j = X_pp_keys.index(k)
                    aligned[:, i] = X_pp[:, j]
            X_pp = aligned
        all_X.append(X_pp)
        all_yb.append(y_binary_pp)
        all_yp.append(y_pki_pp)
        # PDBbind crystal: no Vina score (crystal pose)
        all_vina.append(np.zeros(len(X_pp), dtype=np.float32))
        all_smi.extend(pid_pp)  # use pid as identifier
        all_src.append(np.zeros(len(X_pp), dtype=np.int8))  # source_id=0 for PDBbind
        all_target_id.append(np.zeros(len(X_pp), dtype=np.int8))
        all_target_pdb.extend([""] * len(X_pp))  # no external target
        n_pp = len(X_pp)
        print(f"\nAdded {n_pp} PDBbind crystal complexes")

    # Concat all
    X_all = np.concatenate(all_X, axis=0)
    y_binary_all = np.concatenate(all_yb)
    y_pki_all = np.concatenate(all_yp)
    vina_all = np.concatenate(all_vina)
    source_all = np.concatenate(all_src)
    target_id_all = np.concatenate(all_target_id)
    smiles_all = np.array(all_smi, dtype=object)
    pdb_all = np.array(all_target_pdb, dtype=object)

    print(f"\n=== FINAL DATASET ===")
    print(f"X_ecif shape: {X_all.shape}")
    print(f"PDBbind crystal: {int((source_all == 0).sum())}")
    for nt in TARGET_MAP:
        cnt = int((source_all == TARGET_MAP[nt][1]).sum())
        acts = int(((source_all == TARGET_MAP[nt][1]) & (y_binary_all == 1)).sum())
        held = " [HELD-OUT]" if TARGET_MAP[nt][3] else ""
        print(f"  {nt:15}: {cnt:5d} (actives={acts}){held}")
    # Total
    print(f"\nTotal actives: {int((y_binary_all == 1).sum())}")
    print(f"Total decoys:  {int((y_binary_all == 0).sum())}")
    print(f"Total mols:    {len(X_all)}")
    print(f"Train candidates (excl 5ht1a): {int((source_all != 8).sum())}")
    held_out = int((source_all == 8).sum())
    print(f"Held-out (5ht1a):               {held_out}")

    out_path = OUT_DIR / "dataset_v31.npz"
    np.savez_compressed(
        out_path,
        X_ecif=X_all,
        y_binary=y_binary_all,
        y_pki=y_pki_all,
        vina_score=vina_all,
        source=source_all,
        target_id=target_id_all,
        smiles=smiles_all,
        protein_pdb_path=pdb_all,
        feature_keys=np.array(base_keys, dtype=object),
        target_names=np.array(list(TARGET_MAP.keys()) + ["pdbbind_crystal"], dtype=object),
    )
    print(f"\nSaved to {out_path} ({out_path.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
