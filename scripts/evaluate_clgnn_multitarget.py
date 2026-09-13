"""
scripts/evaluate_clgnn_multitarget.py
Evaluate the trained CL-GNN model (gnn_v2_cl_best.pt) on ALL benchmark targets.
Adds 'clgnn_prob' to each checkpoint, computes AUC/EF per target.

Usage:
  python scripts/evaluate_clgnn_multitarget.py
  python scripts/evaluate_clgnn_multitarget.py --target cdk2
  python scripts/evaluate_clgnn_multitarget.py --skip-existing
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import shutil
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from gnn_v2.models import GNNv2Classifier

ARTIFACTS = PROJECT_ROOT / "rescoring" / "artifacts"
CKPT_PATH = ARTIFACTS / "gnn_v2_cl_best.pt"

# Mapping (verified via build_gnn_v31_dataset.py)
TARGETS = {
    "5ht1a":        {"pdb": "7E2Y.pdb", "family": "gpcr",              "checkpoint_dir": "gnn_v31/checkpoints"},
    "cdk2":         {"pdb": "3PP0.pdb", "family": "kinase",           "checkpoint_dir": "gnn_v31/checkpoints"},
    "hiv_protease": {"pdb": "1HSG.pdb", "family": "protease",          "checkpoint_dir": "gnn_v31/checkpoints"},
    "er_alpha":     {"pdb": "3ERT.pdb", "family": "nuclear_receptor", "checkpoint_dir": "gnn_v31/checkpoints"},
    "factor_xa":    {"pdb": "3CYX.pdb", "family": "protease",          "checkpoint_dir": "gnn_v31/checkpoints"},
    "thrombin":     {"pdb": "1c4u.pdb", "family": "protease",          "checkpoint_dir": "gnn_v31/checkpoints"},
    "ca2":          {"pdb": "3dc3.pdb", "family": "metaloenzyme",      "checkpoint_dir": "gnn_v31/checkpoints"},
    # glp1r has 0 actives - skipped
}

TARGETS_DIR = PROJECT_ROOT / "data" / "targets"


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


def build_graph_from_pose(pose_pdbqt, target_pdb, smiles):
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


def evaluate_target(target_name, model, device, hidden_dim=128):
    cfg = TARGETS[target_name]
    target_pdb = TARGETS_DIR / cfg["pdb"]
    if not target_pdb.exists():
        print(f"  [SKIP] {target_name}: missing PDB {target_pdb}")
        return None

    ck_path = PROJECT_ROOT / "data" / cfg["checkpoint_dir"] / f"benchmark_checkpoint_{target_name}.json"
    if not ck_path.exists():
        print(f"  [SKIP] {target_name}: missing checkpoint {ck_path}")
        return None

    with open(ck_path) as f:
        ck = json.load(f)
    results = ck["results"]
    n = len(results)
    n_act = sum(1 for x in results if x.get("is_active"))
    print(f"\n=== {target_name} ({cfg['family']}) | N={n} actives={n_act} ===")

    labels = np.array([int(bool(r.get("is_active", False))) for r in results])
    preds = np.zeros(n, dtype=np.float32)
    silent = 0
    t0 = time.time()

    from torch_geometric.data import Batch

    for i, ent in enumerate(results):
        smi = ent.get("smiles", "")
        pose = ent.get("pose_pdbqt", "")
        try:
            graph = build_graph_from_pose(pose, str(target_pdb), smi)
            if graph is None:
                preds[i] = 0.5
                silent += 1
                continue
            prot_b = Batch.from_data_list([graph["protein"]]).to(device)
            lig_b = Batch.from_data_list([graph["ligand"]]).to(device)
            with torch.no_grad():
                logits = model(
                    prot_b.x, prot_b.edge_index,
                    lig_b.x, lig_b.edge_index,
                    graph["cross"].to(device),
                    lig_batch=lig_b.batch, prot_batch=prot_b.batch,
                )
                preds[i] = float(torch.sigmoid(logits).item())
        except Exception:
            preds[i] = 0.5
            silent += 1

        if (i + 1) % 200 == 0 or i == n - 1:
            print(f"  [{i+1}/{n}] silent={silent} rate={(i+1)/(time.time()-t0):.1f}/s")

    valid = np.where(preds != 0.5)[0]
    if len(valid) == 0:
        print("  ERROR: no valid predictions")
        return None
    y, p = labels[valid], preds[valid]
    auc = float(roc_auc_score(y, p))
    pr = float(average_precision_score(y, p))
    ef1 = float(compute_ef(p, y, 1))
    ef5 = float(compute_ef(p, y, 5))
    ef10 = float(compute_ef(p, y, 10))
    t_elapsed = time.time() - t0

    print(f"  ROC-AUC={auc:.4f}  PR={pr:.4f}  EF@1%={ef1:.2f}x  EF@5%={ef5:.2f}x  EF@10%={ef10:.2f}x")
    print(f"  Mean P(active)={p[y==1].mean():.4f}  P(decoy)={p[y==0].mean():.4f}")
    print(f"  Silent={silent}  Time={t_elapsed:.0f}s ({t_elapsed/n:.2f}s/mol)")

    # Add clgnn_prob to checkpoint
    for i, v in enumerate(preds):
        results[i]["clgnn_prob"] = round(float(v), 6)

    # Save updated checkpoint (backup first)
    if not Path(str(ck_path) + ".bak").exists():
        shutil.copy(ck_path, str(ck_path) + ".bak")
    with open(ck_path, "w") as f:
        json.dump(ck, f, indent=2)
    print(f"  Saved clgnn_prob to {ck_path}")

    return {
        "target": target_name,
        "family": cfg["family"],
        "n_total": n,
        "n_actives": n_act,
        "n_valid": int(len(valid)),
        "n_silent": silent,
        "auc": auc, "pr": pr,
        "ef1": ef1, "ef5": ef5, "ef10": ef10,
        "mean_act": float(p[y == 1].mean()),
        "mean_dec": float(p[y == 0].mean()),
        "time_s": round(t_elapsed, 1),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=str, default=None, help="Evaluate single target")
    parser.add_argument("--skip-existing", action="store_true", help="Skip if clgnn_prob already exists")
    parser.add_argument("--hidden-dim", type=int, default=128)
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    model = GNNv2Classifier(hidden_dim=args.hidden_dim).to(device)
    state = torch.load(CKPT_PATH, map_location=device, weights_only=False)
    sd = state.get("model_state_dict", state)
    model.load_state_dict(sd, strict=False)
    model.to(device).eval()
    print(f"Model loaded: {CKPT_PATH.name}")

    targets_to_eval = [args.target] if args.target else list(TARGETS.keys())

    all_results = []
    for tname in targets_to_eval:
        if tname not in TARGETS:
            print(f"Unknown target: {tname}")
            continue

        # Check if already evaluated
        if args.skip_existing:
            ck_path = PROJECT_ROOT / "data" / TARGETS[tname]["checkpoint_dir"] / f"benchmark_checkpoint_{tname}.json"
            if ck_path.exists():
                ck = json.load(open(ck_path))
                if ck["results"] and ck["results"][0].get("clgnn_prob") is not None:
                    print(f"  [SKIP-EXISTING] {tname} already has clgnn_prob")
                    continue

        r = evaluate_target(tname, model, device, hidden_dim=args.hidden_dim)
        if r:
            all_results.append(r)

    # Summary
    if all_results:
        print("\n" + "=" * 80)
        print("  CL-GNN MULTI-TARGET EVALUATION SUMMARY")
        print("=" * 80)
        print(f"  {'Target':15s} {'Family':20s} {'N':>5s} {'Act':>4s} {'AUC':>7s} {'PR':>7s} {'EF@1%':>7s} {'EF@5%':>7s} {'EF@10%':>7s}")
        for r in all_results:
            print(f"  {r['target']:15s} {r['family']:20s} {r['n_total']:5d} {r['n_actives']:4d} {r['auc']:7.4f} {r['pr']:7.4f} {r['ef1']:7.2f} {r['ef5']:7.2f} {r['ef10']:7.2f}")

        # Save summary
        out_path = PROJECT_ROOT / "data" / "gnn_fixed" / "clgnn_multitarget_summary.json"
        with open(out_path, "w") as f:
            json.dump({
                "version": "CL-GNN (38-dim, contrastive pretrained)",
                "model_path": str(CKPT_PATH),
                "results": all_results,
            }, f, indent=2)
        print(f"\nSummary saved: {out_path}")


if __name__ == "__main__":
    main()
