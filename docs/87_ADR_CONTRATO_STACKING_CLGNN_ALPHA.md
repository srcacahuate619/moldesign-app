# ADR 87 - Release contract for M4 stacking and CL-GNN

Status: accepted for the first public alpha (2026-09-10).

## Decision

The canonical release contract is `backend/artifacts/sci_config_registry.json` (`M4_STACKING_ALPHA_V1`). Every generic M4 family resolves to:

| component | release weight |
|---|---:|
| AutoDock Vina | 0.25 |
| XGBoost | 0.75 |
| legacy GNN / RTMScore | 0.00 |
| CL-GNN | 0.00 |

`rescoring/artifacts/stacking_weights.json` is a compatibility mirror, not an independent authority. `frontend/lib/pipelineDefinitions.ts` only describes the same contract. `scripts/check_stacking_weights_ui.py` blocks a build when registry, mirror, effective backend resolution, UI, model manifest, or checkpoint hash disagree.

## Why CL-GNN is included but has zero release weight

The installer includes `gnn_v2_cl_best.pt`, production loads it, scores the docked pose, persists the probability, and the UI may display it as an experimental signal. Inclusion and scientific authority are separate claims.

The distributed checkpoint SHA-256 is:

`f714dd8208f491258dcb4671bc1e29f308712c1c27f629409f2e33993186bb4f`

The external AUC values in historical reports belong to different checkpoint bytes. The current `model-manifest.json` therefore records `external_metrics_for_exact_sha256: null`. Reusing those AUCs to assign a nonzero weight would be false provenance. The legacy GNN is deprecated and likewise cannot influence ranking.

This does not call CL-GNN invalid. It says exactly what is known today: the current artifact can produce a signal, but its contribution to ranking has not been qualified.

## Promotion rule

A nonzero CL-GNN weight requires all of the following in one change:

1. preregistered external controls that exclude training and model-selection targets;
2. metrics attributable to the exact distributed SHA-256;
3. a frozen calibration method and uncertainty intervals;
4. evidence that the proposed stack improves over Vina + XGBoost on an untouched set;
5. updated model manifest, registry hash, compatibility mirror, UI, goldens, and embedded-runtime controls.

The gate deliberately fails if the manifest still says validation is pending while any family gives CL-GNN a positive weight.

## M5-Zn boundary

No generic metalloenzyme entry exists in the M4 mirror. M5-Zn is calculated and persisted by its target-specific protocol, with its own abstention and review states. Both spellings (`metaloenzyme` and `metalloenzyme`) fall back to the conservative M4 contract only for the generic M4 result; neither activates or substitutes an M5 profile.

## Failure behavior

The registry path is anchored to the backend source tree, not the process working directory, so development and the embedded backend load the same bytes. The registry validates its own `config_hash` and rejects unsealed edits. If the artifact is absent or corrupt at runtime, the engine uses an identical conservative fallback and logs the degradation; the release gate prevents such a bundle from being produced.