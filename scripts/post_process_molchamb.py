#!/usr/bin/env python3
"""
scripts/post_process_molchamb.py
Post-process MolChamb quantum scores onto a GNN-rescored checkpoint
and generate ablation comparison report (with vs without MolChamb).

Usage:
    python post_process_molchamb.py --target 5ht1a [--checkpoint-dir DIR]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Ensure imports from moldesign-build
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score

# Import MolDesign stacking utilities
from stacking_ef import (
    composite_stacking_molchamb,
    compute_molchamb_scores,
    composite_vina_xgb,
    composite_stacking,
)
import benchmark_ef_vina as bm


def enrichment_factor(scores, labels, pct):
    """Compute EF@pct%."""
    n = len(scores)
    n_act = sum(labels)
    if n_act == 0:
        return 0.0
    top_k = max(1, int(n * pct / 100))
    order = np.argsort(scores)[::-1]
    top_labels = [labels[i] for i in order[:top_k]]
    found = sum(top_labels)
    expected = n_act * top_k / n
    return round(found / expected, 2) if expected > 0 else 0.0


def report_metrics(name, scores, labels):
    """Return metrics dict for a score set."""
    auc = roc_auc_score(labels, scores) if len(set(labels)) > 1 else 0.0
    pr = average_precision_score(labels, scores) if len(set(labels)) > 1 else 0.0
    ef1 = enrichment_factor(scores, labels, 1)
    ef5 = enrichment_factor(scores, labels, 5)
    ef10 = enrichment_factor(scores, labels, 10)
    return {
        "ef1": ef1, "ef5": ef5, "ef10": ef10,
        "auc": round(auc, 4), "pr": round(pr, 4),
        "n_total": len(scores), "n_active": sum(labels)
    }


def compute_all_cuts(results, family, stacking_weights):
    """
    Compute all 6 score cuts for ablation:
    1. vina_only
    2. vina_plus_xgb
    3. vina_plus_gnn (no CL-GNN, no XGB)
    4. vina_plus_clgnn (no GNN, no XGB)
    5. calibrated_stacking (Vina+XGB+GNN+CL-GNN, no MolChamb)
    6. stacking_with_molchamb (Vina+XGB+GNN+CL-GNN+MolChamb)
    """
    valid = [r for r in results if r.get("vina_score") is not None]
    if not valid:
        return {}

    labels = [r["is_active"] for r in valid]

    # 1. vina_only
    vina_scores = [abs(r["vina_score"]) for r in valid]
    vina_m = report_metrics("Vina Only", vina_scores, labels)

    # 2. vina_plus_xgb
    comp_scores = [composite_vina_xgb(r) for r in valid]
    comp_m = report_metrics("Vina + XGB", comp_scores, labels)

    # 3. vina_plus_gnn (GNN without CL-GNN, no XGB)
    def _vina_plus_second(r, key, w_second=0.70):
        vina = abs(r.get("vina_score") or -5.0)
        vina_norm = min(1.0, vina / 12.0)
        second = r.get(key)
        if second is None or second < 0.01:
            return round(vina_norm, 4)
        return round(vina_norm * (1.0 - w_second) + float(second) * w_second, 4)

    gnn_scores = [_vina_plus_second(r, "gnn_prob") for r in valid]
    gnn_m = report_metrics("Vina + GNN", gnn_scores, labels)

    # 4. vina_plus_clgnn
    clgnn_scores = [_vina_plus_second(r, "clgnn_prob") for r in valid]
    clgnn_m = report_metrics("Vina + CL-GNN", clgnn_scores, labels)

    # 5. calibrated_stacking (no MolChamb)
    weights = stacking_weights.get(family, stacking_weights["default"])
    cal_scores = bm.calibrated_stacking(valid, family)
    cal_m = report_metrics("Calibrated Stacking (no MolChamb)", cal_scores, labels)

    # 6. stacking_with_molchamb
    # Compute MolChamb scores first
    compute_molchamb_scores(valid)
    molchamb_w = {
        "w_vina": weights["vina"],
        "w_xgb": weights["prob"],
        "w_gnn": weights["gnn"],
        "w_molchamb": 0.15,
    }
    molchamb_scores = [composite_stacking_molchamb(r, **molchamb_w) for r in valid]
    molchamb_m = report_metrics("Stacking + MolChamb", molchamb_scores, labels)

    return {
        "vina_only": vina_m,
        "vina_plus_xgb": comp_m,
        "vina_plus_gnn": gnn_m,
        "vina_plus_clgnn": clgnn_m,
        "calibrated_stacking": cal_m,
        "stacking_with_molchamb": molchamb_m,
    }


def generate_markdown_report(target_name, family, all_cuts, box_info, n_total, n_active):
    """Generate markdown ablation report for the paper."""
    md = []
    md.append(f"# MolChamb Ablation Study — {target_name.upper()}")
    md.append(f"")
    md.append(f"**Target**: {target_name} | **Family**: {family}")
    md.append(f"**Dataset size**: {n_total} mols ({n_active} actives, {n_total - n_active} decoys)")
    md.append(f"**Box source**: {box_info.get('box_source', 'unknown')}")
    md.append(f"**Box center**: {box_info.get('box_center', 'N/A')}")
    md.append(f"**Box size**: {box_info.get('box_size', 'N/A')} Å")
    md.append(f"")
    md.append(f"## Ablation Table — 6 Cut Comparison")
    md.append(f"")
    md.append(f"| Method | EF@1% | EF@5% | EF@10% | ROC-AUC | PR-AUC | Δ vs Calibrated |")
    md.append(f"|--------|-------|-------|--------|---------|--------|-----------------|")

    baseline_auc = all_cuts.get("calibrated_stacking", {}).get("auc", 0.0)

    cut_order = [
        ("Vina Only", "vina_only"),
        ("Vina + XGB", "vina_plus_xgb"),
        ("Vina + GNN", "vina_plus_gnn"),
        ("Vina + CL-GNN", "vina_plus_clgnn"),
        ("Calibrated Stacking (no MolChamb)", "calibrated_stacking"),
        ("Stacking + MolChamb", "stacking_with_molchamb"),
    ]

    for label, key in cut_order:
        m = all_cuts.get(key, {})
        if not m:
            continue
        delta_auc = m.get("auc", 0.0) - baseline_auc
        delta_str = f"{delta_auc:+.4f}" if key != "calibrated_stacking" else "— (baseline)"
        md.append(f"| {label} | {m['ef1']:.2f}x | {m['ef5']:.2f}x | {m['ef10']:.2f}x | {m['auc']:.4f} | {m['pr']:.4f} | {delta_str} |")

    md.append(f"")
    md.append(f"## Key Findings")
    md.append(f"")

    vina_auc = all_cuts.get("vina_only", {}).get("auc", 0.0)
    cal_auc = all_cuts.get("calibrated_stacking", {}).get("auc", 0.0)
    molchamb_auc = all_cuts.get("stacking_with_molchamb", {}).get("auc", 0.0)

    md.append(f"- **Vina baseline AUC**: {vina_auc:.4f}")
    md.append(f"- **Calibrated Stacking (GNN+CL-GNN+XGB) AUC**: {cal_auc:.4f} (Δ = {cal_auc - vina_auc:+.4f})")
    md.append(f"- **Stacking + MolChamb AUC**: {molchamb_auc:.4f} (Δ vs calibrated = {molchamb_auc - cal_auc:+.4f})")

    if molchamb_auc > cal_auc:
        md.append(f"- **MolChamb adds value**: AUC improved by {molchamb_auc - cal_auc:+.4f} ({(molchamb_auc - cal_auc) * 100:.1f}% relative)")
    elif molchamb_auc < cal_auc:
        md.append(f"- **MolChamb degrades**: AUC decreased by {cal_auc - molchamb_auc:.4f} — MolChamb signal may be orthogonal or noisy for this target")
    else:
        md.append(f"- **MolChamb neutral**: No measurable AUC change vs calibrated stacking")

    md.append(f"")
    md.append(f"## Box Provenance")
    md.append(f"")
    md.append(f"- Box source: `{box_info.get('box_source', 'unknown')}`")
    md.append(f"- Box center: {box_info.get('box_center', 'N/A')}")
    md.append(f"- Box size: {box_info.get('box_size', 'N/A')} Å")
    md.append(f"")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(
        description="Post-process MolChamb scores onto GNN-rescored checkpoint and generate ablation report"
    )
    parser.add_argument("--target", required=True, help="Target dataset name (e.g., 5ht1a)")
    parser.add_argument("--checkpoint-dir", default="data/gnn_fixed",
                        help="Directory containing benchmark_checkpoint_<target>.json")
    parser.add_argument("--output-dir", default="data/gnn_fixed",
                        help="Directory for output reports")
    parser.add_argument("--docs-dir", default="docs",
                        help="Directory for markdown report")
    args = parser.parse_args()

    target = args.target
    checkpoint_dir = Path(args.checkpoint_dir)
    output_dir = Path(args.output_dir)
    docs_dir = Path(args.docs_dir)

    ckpt_path = checkpoint_dir / f"benchmark_checkpoint_{target}.json"
    if not ckpt_path.exists():
        # Try data/gnn_fixed first, then data/ fallback
        alt = Path("data") / f"benchmark_checkpoint_{target}.json"
        if alt.exists():
            ckpt_path = alt
        else:
            print(f"[ERROR] Checkpoint not found: {ckpt_path}")
            sys.exit(1)

    print(f"Loading checkpoint: {ckpt_path}")
    with open(ckpt_path, encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", [])
    print(f"Loaded {len(results)} molecules from {ckpt_path.name}")

    # Validate we have GNN+CL-GNN scores (from re-score-gnn.py)
    has_gnn = sum(1 for r in results if r.get("gnn_prob") is not None)
    has_clgnn = sum(1 for r in results if r.get("clgnn_prob") is not None)
    print(f"GNN scores present: {has_gnn}/{len(results)}")
    print(f"CL-GNN scores present: {has_clgnn}/{len(results)}")

    if has_gnn == 0 or has_clgnn == 0:
        print("[WARN] Missing GNN/CL-GNN scores — run re-score-gnn.py first for full ablation")
        # Still proceed with whatever we have

    # Get family from checkpoint metadata or infer
    family = data.get("family", "gpcr")  # 5ht1a is GPCR
    if not family or family == "unknown":
        # Try to infer from target name
        if "5ht1" in target:
            family = "gpcr"
        elif "cdk" in target:
            family = "kinase"
        elif "hiv" in target or "protease" in target:
            family = "protease"
        elif "er_alpha" in target or "nr" in target:
            family = "nuclear_receptor"
        elif "factor_xa" in target or "soluble" in target:
            family = "soluble_enzyme"
        else:
            family = "default"

    print(f"Family: {family}")

    # Get box info from benchmark report if available
    box_info = {"box_source": "unknown", "box_center": [0, 0, 0], "box_size": 0}
    report_path = Path("data") / f"ef_report_{target}.json"
    if report_path.exists():
        with open(report_path, encoding="utf-8") as f:
            rep = json.load(f)
            box_info["box_source"] = rep.get("box_source", "unknown")
            box_info["box_center"] = rep.get("box_center", [0, 0, 0])
            box_info["box_size"] = rep.get("box_size", 0)
    elif "box_source" in data:
        box_info["box_source"] = data.get("box_source", "unknown")
        box_info["box_center"] = data.get("box_center", [0, 0, 0])
        box_info["box_size"] = data.get("box_size", 0)

    # Stacking weights from module
    from stacking_ef import STACKING_WEIGHTS
    stacking_weights = STACKING_WEIGHTS

    print(f"Computing ablation cuts (6 methods)...")
    t0 = time.time()
    all_cuts = compute_all_cuts(data.get("results", []), family, STACKING_WEIGHTS)
    print(f"Computed in {time.time() - t0:.1f}s")

    # Generate JSON report
    n_total = len([r for r in data.get("results", []) if r.get("vina_score") is not None])
    n_active = sum(r.get("is_active", 0) for r in data.get("results", []) if r.get("vina_score") is not None)

    target_name = data.get("target_name", target.upper())
    box_center_str = str(box_info.get("box_center", [0, 0, 0]))

    report = {
        "target": target,
        "family": family,
        "n_total": n_total,
        "n_active": n_active,
        "box_source": box_info.get("box_source", "unknown"),
        "box_center": box_info.get("box_center", [0, 0, 0]),
        "box_size": box_info.get("box_size", 0),
        "cuts": all_cuts,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Save JSON report
    out_path = Path(args.output_dir) / f"ef_report_{target}_molchamb_gs.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"JSON report saved: {out_path}")

    # Generate markdown report
    md = generate_markdown_report(
        target_name=target.upper(),
        family=target,
        all_cuts=all_cuts,
        box_info=box_info,
        n_total=n_total,
        n_active=sum(r.get("is_active", 0) for r in data.get("results", []) if r.get("vina_score") is not None)
    )

    md_path = Path(args.docs_dir) / f"21_ABLATION_MOLCHAMB_{target.upper()}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Markdown report saved: {md_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("ABLATION SUMMARY")
    print("=" * 60)
    for key in ["vina_only", "calibrated_stacking", "stacking_with_molchamb"]:
        if key in all_cuts:
            m = all_cuts[key]
            print(f"  {key:30s} EF@1%={m['ef1']:.2f}x  AUC={m['auc']:.4f}")

    if "calibrated_stacking" in all_cuts and "stacking_with_molchamb" in all_cuts:
        delta = all_cuts["stacking_with_molchamb"]["auc"] - all_cuts["calibrated_stacking"]["auc"]
        print(f"\nMolChamb delta vs calibrated: {delta:+.4f} AUC")
        if delta > 0:
            print("  -> MolChamb ADDS value")
        elif delta < 0:
            print("  -> MolChamb DEGRADES")
        else:
            print("  -> MolChamb NEUTRAL")


if __name__ == "__main__":
    main()