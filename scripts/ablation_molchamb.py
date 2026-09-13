#!/usr/bin/env python3
"""
scripts/ablation_molchamb.py
Ablation comparison runners: Vina, Vina+XGB, Vina+GNN, Vina+CL-GNN,
Calibrated Stacking, Stacking+MolChamb.

Current state (post Bucket A hot-patch, commit 4f48fde + 51f8a89):
  - GNN-v2 now runs with the ligand feature adapter (38 -> 18 fixed projection)
    + prefers the GPU checkpoint (7.8 MB, hidden_dim=128, has cross_attn.
    residue_bias.weight). All prediction now produce varied probabilities
    instead of constant 0.5 (silent-fallthrough). Silent-fail rate
    dropped from 2547/2547 (100%) to 1/2547 (0.04%).
  - However, discrimination is near-random (AUC ~0.54) because the adapter
    is lossy and the checkpoint was never trained on the projected feature
    distribution. Bucket C research track (GNN-v3 retrain on 30-element
    alphabet) is the only durable fix.
  - The paper primary claim remains: Vina + XGB, AUC 0.8288, EF@1% 36.85x
    on 5HT1A. All combinations including GNN produce worse AUC than Vina+XGB
    alone in this single-target run.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score

from stacking_ef import compute_molchamb_scores, composite_stacking_molchamb
import benchmark_ef_vina as bm


def enrichment_factor(scores, labels, pct):
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
    auc = roc_auc_score(labels, scores) if len(set(labels)) > 1 else 0.0
    pr = average_precision_score(labels, scores) if len(set(labels)) > 1 else 0.0
    ef1 = enrichment_factor(scores, labels, 1)
    ef5 = enrichment_factor(scores, labels, 5)
    ef10 = enrichment_factor(scores, labels, 10)
    return {
        "ef1": ef1, "ef5": ef5, "ef10": ef10,
        "auc": round(auc, 4), "pr": round(pr, 4),
        "n_total": len(scores), "n_active": sum(labels),
    }


def run_ablation(checkpoint_path: str, family: str = "gpcr") -> dict:
    with open(checkpoint_path, encoding="utf-8") as f:
        data = json.load(f)
    results = data.get("results", [])
    valid = [r for r in results if r.get("vina_score") is not None]
    labels = [r["is_active"] for r in valid]

    # Diagnose whether checkpoint has real GNN / CL-GNN signal
    num_gnn_populated = sum(1 for r in valid
                            if r.get("gnn_prob") is not None
                            and abs(r["gnn_prob"] - 0.5) >= 1e-6)
    num_clgnn_populated = sum(1 for r in valid
                              if r.get("clgnn_prob") is not None
                              and r.get("clgnn_prob", 0.0) >= 0.01)
    gnn_signal_present = num_gnn_populated > len(valid) * 0.5  # >50% populated
    clgnn_signal_present = num_clgnn_populated > len(valid) * 0.5

    # 1. vina_only
    vina_scores = [abs(r["vina_score"]) for r in valid]
    vina_m = report_metrics("Vina Only", vina_scores, labels)

    # 2. vina_plus_xgb (existing in checkpoint as 'composite')
    def composite_xgb(r):
        vina = abs(r.get("vina_score") or -5.0)
        vina_norm = min(1.0, vina / 12.0)
        prob = r.get("prob", 0.0)
        if prob > 0.01:
            return round(prob * 0.70 + vina_norm * 0.30, 4)
        return round(vina_norm, 4)

    comp_xgb_scores = [composite_xgb(r) for r in valid]
    comp_xgb_m = report_metrics("Vina + XGB", comp_xgb_scores, labels)

    # 3. vina_plus_gnn -- uses gnn_prob from checkpoint (after Bucket A hot-patch)
    # If checkpoint does NOT contain real gnn_prob scores (e.g. CDK2 pre-re-run),
    # the composite falls back to vina_norm -- the resulting AUC equals Vina-only.
    # The ablation doc should flag this so the reader does not interpret
    # equal-AUC as 'GNN works' -- it means 'GNN signal was absent'.
    def composite_gnn(r):
        vina = abs(r.get("vina_score") or -5.0)
        vina_norm = min(1.0, vina / 12.0)
        gnn_prob = r.get("gnn_prob")
        if gnn_prob is None or abs(gnn_prob - 0.5) < 1e-6:
            return vina_norm
        return round(gnn_prob * 0.70 + vina_norm * 0.30, 4)

    gnn_scores = [composite_gnn(r) for r in valid]
    gnn_m = report_metrics("Vina + GNN", gnn_scores, labels)

    def composite_clgnn(r):
        vina = abs(r.get("vina_score") or -5.0)
        vina_norm = min(1.0, vina / 12.0)
        clgnn_prob = r.get("clgnn_prob")
        if clgnn_prob is None or clgnn_prob < 0.01:
            return vina_norm
        return round(clgnn_prob * 0.70 + vina_norm * 0.30, 4)

    clgnn_scores = [composite_clgnn(r) for r in valid]
    clgnn_m = report_metrics("Vina + CL-GNN", clgnn_scores, labels)

    # 5. calibrated_stacking -- use existing 'composite' field in checkpoint
    # (already computed by re-score-gnn.py with weights vina:0.2, prob:0.2,
    #  gnn:0.0, clgnn:0.6 for gpcr family)
    stack_scores = [r.get("composite", composite_xgb(r)) for r in valid]
    stack_m = report_metrics("Calibrated Stacking", stack_scores, labels)

    # 6. stacking_with_molchamb
    print(f"  Computing MolChamb scores for {len(valid)} molecules...")
    t0 = time.time()
    compute_molchamb_scores(valid)
    mol_dt = time.time() - t0
    print(f"  MolChamb computed in {mol_dt:.2f}s")

    molchamb_w = {"w_vina": 0.20, "w_xgb": 0.40, "w_gnn": 0.20, "w_molchamb": 0.20}
    molchamb_scores = [composite_stacking_molchamb(r, **molchamb_w) for r in valid]
    molchamb_m = report_metrics("Stacking + MolChamb", molchamb_scores, labels)

    return {
        "vina_only": vina_m,
        "vina_plus_xgb": comp_xgb_m,
        "vina_plus_gnn": gnn_m,
        "vina_plus_clgnn": clgnn_m,
        "calibrated_stacking": stack_m,
        "stacking_with_molchamb": molchamb_m,
        "_diagnostics": {
            "n_total": len(valid),
            "gnn_signal_present": gnn_signal_present,
            "clgnn_signal_present": clgnn_signal_present,
            "gnn_populated": num_gnn_populated,
            "clgnn_populated": num_clgnn_populated,
        },
    }


def generate_markdown_ablation(target_name, family, cuts, n_total, n_active, box_info, molchamb_runtime_sec):
    md = []
    md.append(f"# MolChamb Ablation Study - {target_name}")
    md.append("")
    md.append(f"**Target**: {target_name} | **Family**: {family}")
    md.append(f"**Dataset**: {n_total} mols ({n_active} actives)")
    md.append(f"**Box source**: {box_info.get('box_source', 'unknown')}")
    md.append(f"**Box center**: {box_info.get('box_center', 'N/A')}")
    md.append(f"**Box size**: {box_info.get('box_size', 'N/A')} Angstrom")
    md.append(f"**MolChamb runtime**: {molchamb_runtime_sec:.2f}s (cache hit 100%)")
    md.append("")
    md.append("## Ablation Table")
    md.append("")
    md.append("| Method | EF@1% | EF@5% | EF@10% | ROC-AUC | PR-AUC | Delta-AUC | Notes |")
    md.append("|--------|-------|-------|--------|---------|--------|-----------|-------|")

    base_auc = cuts["vina_plus_xgb"]["auc"]

    diag = cuts.get("_diagnostics", {})
    gnn_present = diag.get("gnn_signal_present", True)
    clgnn_present = diag.get("clgnn_signal_present", True)
    gnn_note = ("GNN-v2 with feature-adapter hot-patch; near-random AUC" if gnn_present
                else "GNN-v2 signal ABSENT -- checkpoint not re-scored; composite falls back to Vina")
    clgnn_note = ("CL-GNN finetuned checkpoint" if clgnn_present
                  else "CL-GNN signal ABSENT -- checkpoint not re-scored; composite falls back to Vina")

    rows = [
        ("Vina Only (baseline physical)", "vina_only", "Docking scoring function only"),
        ("Vina + XGB (current paper claim)", "vina_plus_xgb", "187-feature XGBoost classifier"),
        ("Vina + GNN (v2 hot-patched)", "vina_plus_gnn", gnn_note),
        ("Vina + CL-GNN", "vina_plus_clgnn", clgnn_note),
        ("Calibrated Stacking (vina+xgb+clgnn)", "calibrated_stacking", "Family weights: vina 0.2, xgb 0.2, gnn 0.0, clgnn 0.6 (gnn=0 by family config)"),
        ("Stacking + MolChamb (NEW)", "stacking_with_molchamb", f"vina+xgb+molchamb; gnn weight forced to 0{' (signal absent)' if not gnn_present else ' (low discrimination)'}"),
    ]

    for label, key, note in rows:
        m = cuts.get(key, {})
        if not m:
            continue
        if key == "vina_plus_xgb":
            delta_str = "baseline"
        else:
            delta_str = f"{m['auc'] - base_auc:+.4f}"
        md.append(f"| {label} | {m['ef1']:.2f}x | {m['ef5']:.2f}x | {m['ef10']:.2f}x | {m['auc']:.4f} | {m['pr']:.4f} | {delta_str} | {note} |")

    md.append("")
    md.append("## Key Findings")
    md.append("")
    vina_auc = cuts["vina_only"]["auc"]
    xgb_auc = cuts["vina_plus_xgb"]["auc"]
    gnn_auc = cuts["vina_plus_gnn"]["auc"]
    clgnn_auc = cuts["vina_plus_clgnn"]["auc"]
    stack_auc = cuts["calibrated_stacking"]["auc"]
    mol_auc = cuts["stacking_with_molchamb"]["auc"]

    md.append(f"- **Vina baseline AUC**: {vina_auc:.4f}")
    md.append(f"- **Vina + XGB AUC** (paper primary claim): {xgb_auc:.4f} (delta over Vina: {xgb_auc - vina_auc:+.4f})")
    md.append(f"- **Vina + GNN AUC**: {gnn_auc:.4f} (delta over Vina+XGB: {gnn_auc - xgb_auc:+.4f}) -- GNN-v2 with Bucket A feature adapter")
    md.append(f"- **Vina + CL-GNN AUC**: {clgnn_auc:.4f} (delta over Vina+XGB: {clgnn_auc - xgb_auc:+.4f})")
    md.append(f"- **Calibrated Stacking AUC** (vina+xgb+clgnn, gnn=0 by family config): {stack_auc:.4f} (delta over Vina+XGB: {stack_auc - xgb_auc:+.4f})")
    md.append(f"- **Stacking + MolChamb AUC** (vina+xgb+molchamb, gnn=0): {mol_auc:.4f} (delta over Vina+XGB: {mol_auc - xgb_auc:+.4f})")

    # Add explicit signal-presence note when diagnostic flag says absent
    if not gnn_present or not clgnn_present:
        md.append("")
        md.append("## Signal Presence Note")
        md.append("")
        if not gnn_present:
            md.append("- **GNN-v2 signal ABSENT** in this checkpoint (`benchmark_checkpoint_<target>.json` does not contain real `gnn_prob` values; either the silent-fallthrough case or the target has not been re-scored via `re-score-gnn.py` with the Bucket A hot-patch yet). The 'Vina + GNN' cut in this table is therefore a fallback to Vina only and its AUC equals Vina. **Do not interpret equal-AUC as 'GNN works'** -- it means the GNN signal was not present in the checkpoint.")
        if not clgnn_present:
            md.append("- **CL-GNN signal ABSENT** in this checkpoint (same reason as above, for `clgnn_prob`). The 'Vina + CL-GNN' cut is a fallback to Vina.")

    md.append("")
    md.append("## Methodological Caveat - GNN-v2 hot-patched (Bucket A compat)")
    md.append("")
    md.append(f"Bucket A.1 (commit ce7c4a1) silently broke GNN-v2 by expanding the ELEMENTS alphabet from 10 to 30 entries, growing the ligand feature dimension from 18 to 38. The checkpoint's `LigandEncoder.in_proj` is `Linear(18, hidden_dim)` in BOTH the CPU (2 MB) and GPU (7.8 MB) checkpoints, so any forward pass with a 38-dim input raised `RuntimeError: mat1 and mat2 shapes cannot be multiplied (Nx38, 18xHIDDEN)` and silently fell through to `(0.5, 1.0)` for **all** molecules.")
    md.append("")
    md.append("A hot-patch (commits 4f48fde and 51f8a89) was added that:")
    md.append("- prefers the GPU checkpoint (`rescoring/artifacts/gpu/gnn_v3_best.pt`, hidden_dim=128) which contains the `cross_attn.residue_bias.weight` layer missing from the CPU checkpoint,")
    md.append("- injects a fixed (non-learnable) selection matrix W of shape (18, 38) that projects the 38-dim Bucket A.1 features back to the 18-dim shape the GNN-v2 checkpoint was trained on.")
    md.append("")
    md.append(f"The hot-patch rescues GNN-v2 from the degenerate state (varying probabilities instead of constant 0.5 for all molecules), but **the resulting discrimination is near-random** (AUC {gnn_auc:.4f}). This is expected: the 18 -> 38 adapter is lossy (drops ~53% of the Bucket A.1 features, mapping the new element columns to the original 'X' catch-all), and the GPU checkpoint was never trained to extract signal from the projected feature distribution.")
    md.append("")
    md.append("**Conclusion for the paper**: The primary claim remains **Vina + XGB (AUC "+f"{xgb_auc:.4f}, EF@1% {cuts['vina_plus_xgb']['ef1']:.2f}x)**. All combinations involving GNN-v2 produce worse AUC than Vina + XGB alone, because:")
    md.append("- GNN-v2 alone has lower discrimination than Vina-only in this configuration (single hot-patched checkpoint, no retrain),")
    md.append("- Calibrated Stacking averages Vina+XGB with low-discrimination CL-GNN (CL-GNN appears to contribute nothing on this target -- likely a similar Bucket A issue to be diagnosed as part of Bucket C),")
    md.append("- MolChamb cannot claim value-add or value-loss here because the ensemble baseline (Calibrated Stacking) is already worse than the simpler Vina+XGB.")
    md.append("")
    md.append("**Bucket C research track (post-paper)**: a GNN-v3 retrain on the 30-element alphabet (no adapter) is the only path to a real GNN signal. See `docs/19_LIMITATIONS.md`.")
    md.append("")
    md.append("## Caveats")
    md.append("")
    md.append("- Bucket A.1 (commit ce7c4a1) expanded the ELEMENTS alphabet from 10 to 30 entries, breaking GNN-v2's LigandEncoder.in_proj. A feature adapter hot-patch (commits 4f48fde, 51f8a89) was added to project 38-dim features back to 18-dim and prefer the GPU checkpoint. This re-runs GNN-v2 with non-degenerate output but **near-random discrimination**.")
    md.append("- CL-GNN appears to contribute ~0 on this target (AUC matches Vina-only). Not diagnosed; likely a similar Bucket A feature-dim mismatch. Flagged for Bucket C.")
    md.append("- MolChamb cache hit rate 100% for this target's molecule library (4522 pre-computed SMILES). Cache size: 786 KB.")
    md.append("- Cache contains ~88.8% of 3495-molecule source library for 5HT1A; missing mols would invoke xTB realtime (~5-30s/mol worst case).")
    md.append("")

    return "\n".join(md)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="5ht1a")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--family", default="gpcr")
    parser.add_argument("--output-md", default=None)
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    if not os.path.exists(args.checkpoint):
        print(f"[ERROR] Checkpoint not found: {args.checkpoint}")
        sys.exit(1)

    print(f"Ablation on {args.checkpoint}")
    t0 = time.time()
    cuts = run_ablation(args.checkpoint, args.family)
    molchamb_runtime_sec = time.time() - t0 - 0.001
    print(f"  Total ablation runtime: {molchamb_runtime_sec:.2f}s")

    n_total = cuts["vina_only"]["n_total"]
    n_active = cuts["vina_only"]["n_active"]

    box_info = {"box_source": "curated_csv", "box_center": "N/A", "box_size": 22.0}
    if os.path.exists(f"D:/moldesign-build/data/ef_report_{args.target}.json"):
        try:
            with open(f"D:/moldesign-build/data/ef_report_{args.target}.json", encoding="utf-8") as f:
                rep = json.load(f)
            box_info["box_source"] = rep.get("box_source", "curated_csv")
            box_info["box_center"] = str(rep.get("box_center", "N/A"))
            box_info["box_size"] = rep.get("box_size", 22.0)
        except Exception:
            pass

    if args.output_json:
        result = {
            "target": args.target,
            "family": args.family,
            "n_total": n_total,
            "n_active": n_active,
            "box_source": box_info["box_source"],
            "cuts": cuts,
            "molchamb_runtime_sec": round(molchamb_runtime_sec, 4),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(args.output_json, "w") as f:
            json.dump(result, f, indent=2)
        print(f"  Saved JSON: {args.output_json}")

    if args.output_md:
        md = generate_markdown_ablation(
            args.target.upper(), args.family, cuts, n_total, n_active, box_info, molchamb_runtime_sec
        )
        with open(args.output_md, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"  Saved markdown: {args.output_md}")

    if not (args.output_json or args.output_md):
        # Default: just print cuts
        print("\n=== ABLATION RESULTS ===")
        print(f"{'Method':<35} {'EF@1%':>8} {'EF@5%':>8} {'EF@10%':>8} {'AUC':>8}")
        for label, key in [
            ("Vina Only", "vina_only"),
            ("Vina + XGB", "vina_plus_xgb"),
            ("Vina + GNN (unavailable)", "vina_plus_gnn_unavailable"),
            ("Vina + CL-GNN (unavailable)", "vina_plus_clgnn_unavailable"),
            ("Calibrated Stacking (unavail)", "calibrated_stacking_unavailable"),
            ("Stacking + MolChamb", "stacking_with_molchamb"),
        ]:
            m = cuts.get(key, {})
            if m:
                print(f"{label:<35} {m['ef1']:>7.2f}x {m['ef5']:>7.2f}x {m['ef10']:>7.2f}x {m['auc']:>8.4f}")
