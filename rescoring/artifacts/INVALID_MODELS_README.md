# ⚠️ INVALID MODELS — DO NOT USE

## Reason
These models were trained with a methodology flaw discovered on 2026-07-29.

The `GNNv2Classifier` backbone was loaded from `gnn_d_best.pt`, which was trained on **ALL 865 PDBbind v2020 complexes** (including all 7 targets: 5ht1a, ca2, cdk2, er_alpha, factor_xa, hiv_protease, thrombin). The subsequent "LOTO" fine-tuning excluded one target from training but the backbone had already memorized representations of that target's molecules.

**Result**: AUCs of 0.99-1.00 at epoch 1 → classic data leakage via pretrained backbone.

## Correct approach (future work)
Train 7 GNN-D models from scratch with true LOTO:
- Each model trained on 6 targets, never seeing the 7th
- No pretrained backbone from `gnn_d_best.pt`
- ~3-5h GPU per 7 models

## Files affected
- metal_aware_loto_5ht1a.pt → renamed to *.INVALID_DUE_TO_DATA_LEAKAGE
- metal_aware_loto_ca2.pt
- metal_aware_loto_cdk2.pt
- metal_aware_loto_er_alpha.pt
- metal_aware_loto_factor_xa.pt
- metal_aware_loto_hiv_protease.pt
- metal_aware_loto_thrombin.pt

## Valid models (unaffected)
- gnn_d_loto_*.pt — true LOTO, trained correctly
- gnn_d_best.pt — general model, not LOTO, valid for non-LOTO use
- gnn_v2_cl_seed*.pt — CL-GNN ensemble seeds, correct methodology
