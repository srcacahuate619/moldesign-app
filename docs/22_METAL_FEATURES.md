# Option C — Metalloenzyme Features (Zn Coordination)

Branch: `molchamb-loto-experiment`
Date: 2026-07-26

## Goal

Improve the weak target ca2 (metalloenzyme, carbonic anhydrase) by adding
metal-coordination-aware features to the Metastack scoring pipeline. ca2 was
the outlier in the 7-target LOTO evaluation: Metastack4 LOTO AUC = 0.7144
(vs mean 0.9374).

## Strategy: Family-Gated 5th Scorer Activation

**Rule**: For family == `metaloenzyme`, add a Zn-specific scorer to Metastack.
For all other 7 families, keep Metastack4 unchanged.

This guarantees ZERO regression on non-metal targets.

## Files Added (Branch Only)

| File | Purpose |
|------|---------|
| scripts/molchamb_populate_checkpoints.py | Populate 8 checkpoints with `molchamb_score` |
| scripts/metastack5_loto_eval.py | First (naive) Metastack5 everywhere eval |
| scripts/metastack_family_gated.py | Family-gated gating (M5 on metal only) |
| scripts/zn_coordination_features.py | Zn-specific geometric+SMILES features for ca2 |
| scripts/metastack_metal_comparison.py | Compare 4 strategies (M4, M5-MC, M5-Zn, M6) |
| data/molchamb_loto/checkpoints/*.json | Copies of checkpoints with `molchamb_score` field |
| data/molchamb_loto/zn_features_ca2.json | Zn features computed for ~1934 ca2 mols |
| data/molchamb_loto/metastack_family_gated_report.json | Family-gated eval results |
| data/molchamb_loto/metal_strategy_comparison.json | 4-strategy comparison |
| data/gnn_v31/checkpoints_PRE_MOLCHAMB/ | Backup of original checkpoints |

## Individual Zn Features (ca2)

Per-molecule Zn-aware features, computed from the pose_pdbqt field of each
molecule and the Zn ion coordinates in 3dc3.pdb:

- `zn_nearest_dist` — min distance (A) from ligand atoms to Zn
- `zn_donors_count` — N/O/S atoms within 3.5 A of Zn (coordination sphere)
- `zn_closest_atom` — element of the closest ligand atom
- `zn_has_sulfonamide` — SMILES regex for SO2NH (warhead)
- `zn_in_box` — 1 if any ligand atom within 8 A of Zn (active site)
- `zn_coord_score` — heuristic blend (0.5*dist_score + 0.3*donor_score + 0.2*sulf)

### Individual AUC on ca2 (biased, per-molecule)

| Feature | AUC |
|---------|-----|
| **zn_coord_score** (heuristic) | **0.9498** |
| zn_has_sulfonamide (SMILES flag) | 0.9030 |
| zn_nearest_dist | 0.8969 |
| molchamb_score (quantum, ref) | 0.8934 |
| zn_donors_count | 0.6796 |
| 0.5*MolChamb + 0.5*ZnCoord blend | 0.9592 |

The simple `zn_has_sulfonamide` flag alone (AUC 0.903) outperforms MolChamb
electronic features (0.893). This confirms that for carbonic anhydrase, the
"warhead recognition" problem (sulfonamide present) is more discriminating than
generic electronic features.

## Strategy Comparison (7-target mean, biased exact per-molecule)

| Strategy | Mean AUC | Δ vs M4 |
|----------|----------|---------|
| M4 baseline (vina + xgb + clgnn_a + gnn_d) | 0.9455 | — |
| M5+MolChamb (gated, metalloenzyme only) | 0.9502 | +0.0047 |
| **M5+ZnCoord (gated)** | **0.9544** | **+0.0089** |
| **M6 full (MolChamb+ZnCoord gated)** | **0.9577** | **+0.0122** |

### ca2 specifically

| Strategy | ca2 AUC | Δ |
|----------|---------|---|
| M4 baseline | 0.7992 | — |
| M5 + MolChamb | 0.8322 | +0.0330 |
| **M5 + ZnCoord** | **0.8617** | **+0.0625** |
| **M6 full (MC + Zn)** | **0.8846** | **+0.0854** |

The combined M6 strategy lifts ca2 from 0.799 (worst target) to 0.885
(roughly thrombin's level).

### Per-target Δ (M6 full gated)

| Target | Family | M4 | M6 | Δ | Note |
|--------|--------|----|----|----|------|
| 5ht1a | gpcr | 0.9890 | 0.9890 | 0 | Not metallo -- untouched |
| **ca2** | **metaloenzyme** | **0.7992** | **0.8846** | **+0.0854** | **Key gain** |
| cdk2 | kinase | 0.9950 | 0.9950 | 0 | Not metallo -- untouched |
| er_alpha | nuclear_receptor | 0.9893 | 0.9893 | 0 | Not metallo -- untouched |
| factor_xa | soluble_enzyme | 0.9881 | 0.9881 | 0 | Not metallo -- untouched |
| hiv_protease | protease | 0.9994 | 0.9994 | 0 | Not metallo -- untouched |
| thrombin | soluble_enzyme | 0.8583 | 0.8583 | 0 | Not metallo -- untouched |

## LOTO Honest Evaluation (TBD)

The biased results above use the full GNN-D model (saw ca2 actives in
training). For an honest LOTO estimate, we need to:

1. Load each of the 7 GNN-D LOTO models (`rescoring/artifacts/gnn_d_loto_{target}.pt`)
2. Re-score the held-out target with the LOTO model (replaces `gnn_d_prob`)
3. Combine with the (already populated) `molchamb_score` and `zn_coord_score`
4. Compute Metastack5 / Metastack6 AUC per LOTO fold

**IMPORTANT**: ZnCoord is heuristic (not trained). Its AUC on ca2 LOTO should
remain ~0.95 — the only thing that changes is GNN-D's per-molecule
probabilities, which in LOTO for ca2 drop to AUC ~0.582. This means in LOTO:
- M4 LOTO ca2 = 0.7144 (GNN-D near-random)
- M5+ZnCoord LOTO ca2 = ? (ZnCoord provides strong signal independently)

A rough estimate: even with weak GNN-D, Metastack5+ZnCoord should reach
~0.78-0.82 on ca2 LOTO. Full re-scoring pass takes ~2-3h GPU.

## Plan for Further Improvement

If the LOTO result confirms the gain, next steps:

1. **Generalize Zn features to other metalloenzymes**:
   - For MMP targets (MMP-8/MMP-9): use Zn from 1gkc/5TY1, same dist+donor features
   - For ECMEND (Mn): replace Zn detector with Mn detector, same framework
   - Add a `metal_coord_score` per-target computed at benchmark time

2. **Tune the heuristic**:
   - Current `zn_coord_score` is 0.5*dist + 0.3*donor + 0.2*sulf (fixed)
   - Try learning the weights per metalloenzyme target (small dataset ok)
   - Add tautomer state (deprotonated sulfonamide = active coordinator)

3. **Train a metal-aware XGBoost**:
   - Use Zn + ECIF + molchamb features on a held-out metalloenzyme set
   - More accurate than the fixed heuristic
   - Predicts "probability of Zn coordination" directly

4. **Add metal-coordination to feature_extractor.py**:
   - Current `metal_coordination` field (PROLIF-MetalAcceptor) is dead code
   - Replace with: distance to nearest Zn in PDB + donor counting
   - This requires reading the Zn at feature extraction time

## Clean Re-Scoring Plan (for honest LOTO M5/M6)

```bash
# For each LOTO fold
for tgt in 5ht1a ca2 cdk2 er_alpha factor_xa hiv_protease thrombin:
    python scripts/rescore_loto_with_molchamb.py --held_out $tgt
    # Loads gnn_d_loto_$tgt.pt
    # Re-scores the $tgt checkpoint molecules with that LOTO model
    # Writes data/molchamb_loto/loto_$tgt.json with gnn_d_prob_loto + molchamb + zn_coord
# Then evaluate Metastack6 LOTO across 7 targets
```

Estimated time: ~7 folds × 15-20 min per fold (rescoring 2000 mols on GPU) = 2-2.5h total.

## Conclusion (so far on branch molchamb-loto-experiment)

- **Family-gated activation works**: zero regression on non-metal targets
- **ZnCoord beats MolChamb alone** on ca2 (+0.063 vs +0.033)
- **M6 full** (MolChamb + ZnCoord gated) = best strategy (+0.012 mean, +0.085 ca2)
- LOTO confirmation pending (~2-3h investment)
- The "warhead detection" insight (sulfonamide flag AUC 0.903) suggests a wider
  principle: target-family-specific pharmacophore flags > generic electronic features
