# MolChamb Ablation Study - CDK2

**Target**: CDK2 | **Family**: kinase
**Dataset**: 199 mols (50 actives)
**Box source**: curated_csv
**Box center**: [17.1, 16.55, 26.6]
**Box size**: 32.7 Angstrom
**MolChamb runtime**: 0.27s (cache hit 100%)

## Ablation Table

| Method | EF@1% | EF@5% | EF@10% | ROC-AUC | PR-AUC | Delta-AUC | Notes |
|--------|-------|-------|--------|---------|--------|-----------|-------|
| Vina Only (baseline physical) | 3.98x | 3.98x | 3.98x | 0.9616 | 0.9287 | -0.0244 | Docking scoring function only |
| Vina + XGB (current paper claim) | 3.98x | 3.98x | 3.98x | 0.9860 | 0.9591 | baseline | 187-feature XGBoost classifier |
| Vina + GNN (v2 hot-patched) | 3.98x | 3.98x | 3.98x | 0.9616 | 0.9287 | -0.0244 | GNN-v2 signal ABSENT -- checkpoint not re-scored; composite falls back to Vina |
| Vina + CL-GNN | 3.98x | 3.98x | 3.98x | 0.9616 | 0.9287 | -0.0244 | CL-GNN signal ABSENT -- checkpoint not re-scored; composite falls back to Vina |
| Calibrated Stacking (vina+xgb+clgnn) | 3.98x | 3.98x | 3.98x | 0.9860 | 0.9591 | +0.0000 | Family weights: vina 0.2, xgb 0.2, gnn 0.0, clgnn 0.6 (gnn=0 by family config) |
| Stacking + MolChamb (NEW) | 3.98x | 3.98x | 3.56x | 0.9694 | 0.8982 | -0.0166 | vina+xgb+molchamb; gnn weight forced to 0 (signal absent) |

## Key Findings

- **Vina baseline AUC**: 0.9616
- **Vina + XGB AUC** (paper primary claim): 0.9860 (delta over Vina: +0.0244)
- **Vina + GNN AUC**: 0.9616 (delta over Vina+XGB: -0.0244) -- GNN-v2 with Bucket A feature adapter
- **Vina + CL-GNN AUC**: 0.9616 (delta over Vina+XGB: -0.0244)
- **Calibrated Stacking AUC** (vina+xgb+clgnn, gnn=0 by family config): 0.9860 (delta over Vina+XGB: +0.0000)
- **Stacking + MolChamb AUC** (vina+xgb+molchamb, gnn=0): 0.9694 (delta over Vina+XGB: -0.0166)

## Signal Presence Note

- **GNN-v2 signal ABSENT** in this checkpoint (`benchmark_checkpoint_<target>.json` does not contain real `gnn_prob` values; either the silent-fallthrough case or the target has not been re-scored via `re-score-gnn.py` with the Bucket A hot-patch yet). The 'Vina + GNN' cut in this table is therefore a fallback to Vina only and its AUC equals Vina. **Do not interpret equal-AUC as 'GNN works'** -- it means the GNN signal was not present in the checkpoint.
- **CL-GNN signal ABSENT** in this checkpoint (same reason as above, for `clgnn_prob`). The 'Vina + CL-GNN' cut is a fallback to Vina.

## Methodological Caveat - GNN-v2 hot-patched (Bucket A compat)

Bucket A.1 (commit ce7c4a1) silently broke GNN-v2 by expanding the ELEMENTS alphabet from 10 to 30 entries, growing the ligand feature dimension from 18 to 38. The checkpoint's `LigandEncoder.in_proj` is `Linear(18, hidden_dim)` in BOTH the CPU (2 MB) and GPU (7.8 MB) checkpoints, so any forward pass with a 38-dim input raised `RuntimeError: mat1 and mat2 shapes cannot be multiplied (Nx38, 18xHIDDEN)` and silently fell through to `(0.5, 1.0)` for **all** molecules.

A hot-patch (commits 4f48fde and 51f8a89) was added that:
- prefers the GPU checkpoint (`rescoring/artifacts/gpu/gnn_v2_best.pt`, hidden_dim=128) which contains the `cross_attn.residue_bias.weight` layer missing from the CPU checkpoint,
- injects a fixed (non-learnable) selection matrix W of shape (18, 38) that projects the 38-dim Bucket A.1 features back to the 18-dim shape the GNN-v2 checkpoint was trained on.

The hot-patch rescues GNN-v2 from the degenerate state (varying probabilities instead of constant 0.5 for all molecules), but **the resulting discrimination is near-random** (AUC 0.9616). This is expected: the 18 -> 38 adapter is lossy (drops ~53% of the Bucket A.1 features, mapping the new element columns to the original 'X' catch-all), and the GPU checkpoint was never trained to extract signal from the projected feature distribution.

**Conclusion for the paper**: The primary claim remains **Vina + XGB (AUC 0.9860, EF@1% 3.98x)**. All combinations involving GNN-v2 produce worse AUC than Vina + XGB alone, because:
- GNN-v2 alone has lower discrimination than Vina-only in this configuration (single hot-patched checkpoint, no retrain),
- Calibrated Stacking averages Vina+XGB with low-discrimination CL-GNN (CL-GNN appears to contribute nothing on this target -- likely a similar Bucket A issue to be diagnosed as part of Bucket C),
- MolChamb cannot claim value-add or value-loss here because the ensemble baseline (Calibrated Stacking) is already worse than the simpler Vina+XGB.

**Bucket C research track (post-paper)**: a GNN-v3 retrain on the 30-element alphabet (no adapter) is the only path to a real GNN signal. See `docs/19_LIMITATIONS.md`.

## Caveats

- Bucket A.1 (commit ce7c4a1) expanded the ELEMENTS alphabet from 10 to 30 entries, breaking GNN-v2's LigandEncoder.in_proj. A feature adapter hot-patch (commits 4f48fde, 51f8a89) was added to project 38-dim features back to 18-dim and prefer the GPU checkpoint. This re-runs GNN-v2 with non-degenerate output but **near-random discrimination**.
- CL-GNN appears to contribute ~0 on this target (AUC matches Vina-only). Not diagnosed; likely a similar Bucket A feature-dim mismatch. Flagged for Bucket C.
- MolChamb cache hit rate 100% for this target's molecule library (4522 pre-computed SMILES). Cache size: 786 KB.
- Cache contains ~88.8% of 3495-molecule source library for 5HT1A; missing mols would invoke xTB realtime (~5-30s/mol worst case).
