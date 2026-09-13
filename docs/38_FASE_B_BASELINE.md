# 38 — Baseline Fase A (modelo a vencer en Fase B)

**Fecha:** 2026-08-13
**Propósito:** Números EXACTOS del `model_a_universal` actual para comparar contra
el modelo reentrenado de Fase B. Este documento es la referencia de comparación
inmutable.

---

## Identidad del modelo actual (Fase A)

| Campo | Valor |
|---|---|
| Archivo | `rescoring/artifacts/model_a_universal.json` |
| SHA-256 | `d2041777857586065aa29dcc8b876a9c1e89394dacbf517e9c071e5cba27f0b2` |
| Features | 167 (A_EXT=8, B=4, C_EXT=3, D=96, E=56) — sin ProLIF |
| ProLIF | Excluido (SHAP<0.003; ablation ECIF-only 0.68 > ALL 0.60) |
| Delta-learning | Sí: `pKi = vina_pKi + delta`, `vina_pKi = -vina_best_score/1.36` |
| Seed | 42 |
| Dataset | PDBbind v2020 refined — 865 complejos cacheados |
| Pool entrenamiento | 537 (familia: soluble_enzyme 411, kinase 70, protease 29, gpcr 13, nr 11, pde 3) |
| Split | scaffold_disjoint_stratified; holdout congelado 328 (carved first, sin leakage) |
| Holdout nunca visto en training/CV | ✅ (verify_scaffold_disjoint) |
| Fecha entrenamiento | 2026-08-10 |

## Métricas baseline (LAS que Fase B debe superar)

### Modelo universal — validación (CV)

| Métrica | Valor |
|---|---|
| Spearman CV | **0.7731** |
| Pearson CV | **0.7418** |
| NDCG@10 | 0.4082 |
| RMSE (reference-only) | 1.3492 |
| n_train / n_val | 429 / 108 |

### Modelo universal — HOLDOUT honesto (328 complejos scaffold-disjoint)

| Métrica | Valor |
|---|---|
| Spearman holdout | **0.6094** (p<0.001) |
| CI95 Spearman | **[0.5282, 0.6791]** (bootstrap 10k) |
| Pearson holdout | **0.6048** (p<0.001) |
| CI95 Pearson | [0.5339, 0.6694] |
| RMSE | 1.9755 |
| MAE | 1.6749 |
| y_true range | [2.64, 11.22] |

### Por familia en holdout

| Familia | n | Spearman | p | Veredicto |
|---|---|---|---|---|
| soluble_enzyme | 267 | 0.6395 | <0.001 | transfiere bien |
| kinase | 26 | 0.6779 | 0.0001 | transfiere bien |
| protease | 22 | 0.2346 | 0.2933 | débil, no significativo |
| gpcr | 5 | -0.7000 | 0.1881 | n insuficiente |
| nuclear_receptor | 8 | -0.1429 | 0.7358 | ruido |

### Modelos familiares (quality gate: Spearman≥0.5 y p<0.05)

| Modelo | CV Spearman | p | Gate |
|---|---|---|---|
| kinase | 0.5868 | 0.0274 | ✅ PASS |
| soluble_enzyme | 0.6680 | <0.001 | ✅ PASS |
| protease | 0.5429 | 0.2657 | ⚠️ borderline (usa universal) |
| gpcr / nuclear_receptor | — | — | SKIPPED (n<15, usa universal) |

### Classifier binder (label: pKi ≥ 7.0, 160 features)

| Split | AUC | CI95 | F1 | Acc |
|---|---|---|---|---|
| holdout (328) | **0.8818** | [0.8422, 0.9178] | 0.8138 | 0.8354 |
| val 80/20 (108) | 0.8292 | [0.7475, 0.9017] | 0.7475 | 0.7685 |

### Importancia por grupo (shap_analysis.json)

| Grupo | Importancia |
|---|---|
| Shell (D) | 1.9632 |
| ECIF (E) | 0.9543 |
| Size-norm (C_EXT) | 0.1877 |
| Vina (B) | 0.0907 |
| 1D/2D (A_EXT) | 0.0 |

Gate Vina: share 2.8% < 10% → PASS (régimen train/inference documentado).

---

## Qué NO es válido citar

- ❌ **0.8732** — holdout inflado por leakage (split aleatorio). INVALIDADO. No citar.
- ❌ Comparaciones contra el modelo legacy 176 (incluía ProLIF, siempre 0/medias en inferencia).

## Métrica histórica de referencia (leakage, solo contexto)

- v2 universal CV: 0.7643 (split aleatorio, no scaffold) — NO comparable con el protocolo honesto.

---

## Protección del modelo actual

1. **Git**: commiteado en la rama `conexion_frontend_backend`; **tag `fase-a-baseline`**.
2. **Snapshot físico**: `rescoring/artifacts/backup_20260813_faseA/` (modelo + metadata + training_report + split_config + manifest + shap).
3. **Manifest**: `model-manifest.json` v3 registra el SHA-256.
4. **Regeneración**: `scripts/generate_model_manifest.py` recalcula hashes.

## Criterio de éxito de Fase B

El nuevo `model_a_universal` reentrenado con pool ampliado debe:
1. **Igualar o superar** Spearman holdout 0.6094 (CI95 que no se solape hacia abajo).
2. Mantener o ampliar la **cobertura de dominio** (menos moléculas fuera de Mahalanobis).
3. Mismo protocolo: scaffold-disjoint, holdout congelado NUEVO (sin reutilizar los 328 de Fase A como train), seed 42, 167 features sin ProLIF.
4. Actualizar manifest, gate Vina, training_report y este documento con la comparación.

## Registro de cambios

- 2026-08-13: baseline creado; tag `fase-a-baseline`; snapshot físico.
