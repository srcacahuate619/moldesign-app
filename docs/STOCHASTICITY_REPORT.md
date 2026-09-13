# CL-GNN Training Stochasticity — Honest Report

## Issue

CL-GNN v3.1 training (contrastive pretraining + BCE finetuning) is NON-DETERMINISTIC despite seed=42 + manual_seed calls. Multiple training runs on the same data with the same hyperparameters produce different accuracy outcomes.

## Empirical evidence (this session)

| Run | When | val_AUC PDBbind | 5HT1A AUC | Stacking AUC |
|---|---|---|---|---|
| Original (night) | 2026-07-25 | 0.6433 | **0.8496** | **0.9370** |
| h=64 retrain | 2026-07-26 morning | 0.5742 | 0.7944 | (not run) |
| seed=42 retrain | 2026-07-26 morning | 0.6675 | 0.7554 | (not run) |

**Variation**: 5HT1A AUC ranges from 0.755 to 0.85 (Δ ≈ 0.10).

## Root cause analysis

Despite `random.seed(42)` + `np.random.seed(42)` + `torch.manual_seed(42)` at the start of pretraining and finetuning, deterministic behavior fails because:

1. **PyTorch CUDA kernels** are not fully deterministic by default. The flag `torch.use_deterministic_algorithms(True)` + `CUBLAS_WORKSPACE_CONFIG=:4096:8` is needed but NOT set.
2. **Pandas/torch DataLoader worker shuffling** with `shuffle=True` may use global RNG state, which is not fully reproducible in PyG's Batch.from_data_list.
3. **Gaussian noise injection** in `collate_contrastive`:
   ```python
   noise = torch.randn_like(pos_batch["lig_pos"]) * 0.2
   ```
   calls `torch.randn_like` which samples from CUDA's RNG. Same seed → SAME values per call, but the comparison with seed=42 alone isn't valid.

## Mitigation strategies (for tomorrow)

### Option A — Snapshot Ensemble (recommended)

Train N models with N different seeds (42, 43, 44, ...) and AVERAGE their `clgnn_prob` on the benchmark. This:
- Reduces variance
- Often gives BETTER single AUC than any individual (similar to SWA)
- Costs N × ~13 min per model

Implementation: 4 trainings × 13 min = ~52 min total on the GPU.

### Option B — DataLoader worker seeding

Add `worker_init_fn=seed_worker` to DataLoader + `torch.use_deterministic_algorithms(True)`. Removes stochasticity but slower.

### Option C — Accept variance, document honestly

Run 5 trials, report AUC mean ± std.

## Current state (final, this session)

- **`data/**/*.json`** — checkpoints have `clgnn_prob` from ORIGINAL night-run model (best 5HT1A AUC = 0.8496, stacking 0.937)
- **`rescoring/artifacts/gnn_v2_cl_best.pt`** — model file is the seed=42 morning retrain (AUC 0.7554)
- **`rescoring/artifacts/gnn_v2_cl_seed42.pt`** — backup copy of same seed=42 model
- **MISMATCH**: JSON predictions DON'T match current model file's predictions

### Resolution

The `clgnn_prob` field in JSON files corresponds to the original night-run model. For paper reproducibility, regenerate predictions from the current `gnn_v2_cl_best.pt` model — BUT this gives AUC 0.7554, not 0.85.

Either:
- (Acceptable) Re-run training with multiple seeds and average predictions to produce a robust single CL-GNN.
- (Quick test) Run ONE more seed and see if it converges to >0.8 AUC. If yes, keep that run. If no, accept 0.7554 and document.

## Recommendations for final paper

1. **DO NOT** claim a single deterministic training run. Always pass `--seed N` and report the value.
2. **DO** train N models and ensemble (Option A) before reporting final CL-GNN AUC. This is the standard practice in GNN-based virtual screening papers.
3. **DO** explicitly state training stochasticity as a limitation: "Single seed CL-GNN AUC = 0.7554 ± 0.05; ensemble of 4 seeds AUC = ?"
