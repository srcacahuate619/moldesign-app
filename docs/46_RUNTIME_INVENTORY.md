# 46 — Inventario runtime actual (generado)

**Estado:** 🟢 Inventario vigente derivado de los artefactos que el repositorio distribuye.

No contiene una afirmación nueva de validez científica. Las métricas se transcriben desde el manifiesto v4 y conservan sus estados/notas.

## Catálogo de receptores

- Entradas en `curated_targets.json`: **380**
- PDB IDs únicos: **380**
- IDs con estructura distribuida en el repositorio (`.pdb.gz` de nombre exacto): **380 / 380**
- Archivos `.pdb.gz` versionados (incluye variantes de cadena y duplicados): **407**
- SHA-256 del catálogo: `7c653ab5875537321a7dbd99435166638a54708311f4346e3d0a6f99ecd71f1c`

### Familias estructurales

| Familia | Targets |
|---|---:|
| `atp_synthase` | 1 |
| `chaperone` | 1 |
| `cytochrome_p450` | 4 |
| `gpcr` | 30 |
| `growth_factor` | 9 |
| `hydrolase` | 26 |
| `ion_channel` | 30 |
| `isomerase` | 1 |
| `kinase` | 29 |
| `ligase` | 2 |
| `lyase` | 1 |
| `metalloenzyme` | 3 |
| `methyltransferase` | 2 |
| `nuclear_receptor` | 29 |
| `nuclease` | 10 |
| `oxidoreductase` | 20 |
| `phosphodiesterase` | 18 |
| `polymerase` | 18 |
| `protease` | 62 |
| `proteasome` | 18 |
| `protein_interaction` | 23 |
| `topoisomerase` | 18 |
| `transcription_factor` | 1 |
| `transferase` | 5 |
| `transporter` | 18 |
| `ubiquitin_ligase` | 1 |

## Modelos declarados por el manifest v4

- Manifest: `rescoring/artifacts/model-manifest.json` (schema v4)
- SHA-256 del manifest: `84c843c86935fc96d0db5cee125185bc90ca2c7a175352e1a56691089bdb5be0`

### `classifier_binder`

- Archivo: `classifier_binder.json`
- SHA-256: `b83a936564036b196b53919c707250c441d49fbd1b9427b15f7ebe48850ea636`
- Estado científico declarado: `HOLDOUT_SCAFFOLD_DISJOINT__COHORTE_PEQUENA`
- Fecha de entrenamiento: `2026-08-10T02:10:00`
- Feature schema: Shell(96)+ECIF(56)+1D2D(8)=160
- Nota del manifest: Produce `xgb_score`. Es el componente de mayor peso del stacking (0.60 por defecto, 0.40 en GPCR). El umbral de binder es pKi>=7.0: la etiqueta es una DICOTOMIZACION de una afinidad continua, no una medida experimental de union. Cohorte pequena -108 de validacion y 328 de holdout- asi que los intervalos son anchos y el AUC no debe citarse sin ellos.

| Métrica declarada | Valor |
|---|---:|
| `holdout` | {'accuracy': 0.8354, 'auc': 0.8818, 'auc_ci95': [0.8422, 0.9178], 'f1': 0.8138, 'n': 328, 'neg': 177, 'pos': 151} |
| `validacion` | {'accuracy': 0.7685, 'auc': 0.8292, 'auc_ci95': [0.7475, 0.9017], 'f1': 0.7475, 'n': 108, 'neg': 54, 'pos': 54} |

### `gnn_v2_cl`

- Archivo: `gnn_v2_cl_best.pt`
- SHA-256: `f714dd8208f491258dcb4671bc1e29f308712c1c27f629409f2e33993186bb4f`
- Estado científico declarado: `HELD_OUT_MULTITARGET__TRANSFERENCIA_DEPENDE_DE_LA_FAMILIA`
- Fecha de entrenamiento: `2026-07-26`
- Feature schema: Grafo heterogeneo: ligando (38-dim por atomo) + proteina (Ca de residuos de bolsillo) + cross-edges ligando-Ca a <8 A. ContrastiveGNN (GAT+GIN+Set2Set+Cross-Attention) -> GNNv2Classifier, 751448 parametros, hidden_dim=128.
- Nota del manifest: LA TRANSFERENCIA DEPENDE DE LA FAMILIA Y NO SE PUEDE CITAR UN AUC GLOBAL. Funciona en familias bien representadas en PDBbind: HIV proteasa 0.949, 5-HT1A 0.850. Queda en el azar donde no lo estan: CDK2 0.594, ER-alfa 0.658, CA2 0.588 -- el grafo no modela el metal como nodo, asi que los contactos Zn-ligando no se ven. Trombina falla al 100% (error tecnico del PDB 1e66, sin resolver). Por eso los pesos de stacking de metaloenzima que ponian clgnn=1.0 se rechazan en scoring/engine.py. Ver docs/CL_GNN_MULTITARGET_RESULTS.md.

| Métrica declarada | Valor |
|---|---:|
| `auc_held_out_por_familia` | {'gpcr_5HT1A_7E2Y': 0.8496, 'kinase_CDK2_3PP0': 0.5942, 'metalloenzyme_CA2_3dc3': 0.5883, 'nuclear_receptor_ERalpha_3ERT': 0.6581, 'protease_HIV_1HSG': 0.9491, 'protease_factorXa_3CYX': 0.7394, 'protease_thrombin_1e66': None} |
| `fallos_silenciosos_pct` | {'gpcr_5HT1A_7E2Y': 0.16, 'metalloenzyme_CA2_3dc3': 5.09, 'protease_HIV_1HSG': 0.16, 'protease_factorXa_3CYX': 3.32, 'protease_thrombin_1e66': 100.0} |
| `finetuning` | BCE, 100 epocas, lr=5e-4 |
| `pretraining` | NT-Xent, ruido gaussiano std=0.2, 200 epocas, lr=1e-3 |
| `val_auc_pdbbind_docked` | 0.6433 |

### `model_a_universal`

- Archivo: `model_a_universal.json`
- SHA-256: `d2041777857586065aa29dcc8b876a9c1e89394dacbf517e9c071e5cba27f0b2`
- Estado científico declarado: `HONEST_HOLDOUT`
- Fecha de entrenamiento: `2026-08-10`
- Feature schema: 167 features (A_EXT=8, B=4, C_EXT=3, D=96, E=56)
- Nota del manifest: Historical 0.8732 INVALIDATED (leakage). Do not cite.

| Métrica declarada | Valor |
|---|---:|
| `pearson_holdout` | 0.6048 |
| `spearman_cv` | 0.7731 |
| `spearman_holdout` | 0.6094 |
| `spearman_holdout_ci95` | [0.5282, 0.6791] |

### `pose_selector_v06`

- Archivo: `pose_selector_v06.xgb`
- SHA-256: `9827ddb94c5ded5b2ef1dda1250606d73f73163becc310641d5bd493196e5d31`
- Estado científico declarado: `HONEST_FROZEN_HOLDOUT_BELOW_PREREGISTERED_0.70_TARGET`
- Fecha de entrenamiento: `2026-08-14`
- Feature schema: 233 features (224 raw relativizadas por complejo + 9 percentiles)
- Nota del manifest: Top-1 0.660 supera Vina, pero no alcanza el objetivo preregistrado final >=0.70. El 0.852 es condicional a 43% de abstencion y no debe citarse como rendimiento global.

| Métrica declarada | Valor |
|---|---:|
| `abstention_rate` | 0.43 |
| `accepted_top1_crystal_like` | 0.852 |
| `selector_median_rmsd_angstrom` | 1.428 |
| `selector_top1_crystal_like` | 0.66 |
| `vina_top1_crystal_like` | 0.532 |

## Mantenimiento

- Regenerar: `python scripts/generate_runtime_inventory.py --write`.
- Verificar: `python scripts/generate_runtime_inventory.py --check`.
- Los targets y modelos experimentales no declarados en el manifest no se presentan como runtime de producción.
