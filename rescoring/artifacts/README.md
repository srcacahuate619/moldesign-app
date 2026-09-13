# Model Artifacts — MolDesign Rescoring

> **Estado**: v1.3 (Julio 2026) — Modelos re-entrenados con 167 features (sin ProLIF), quality gate activo.

---

## Modelos Disponibles

| Archivo | Descripción | Features | Uso |
|---------|-------------|----------|-----|
| `model_a_universal.json` + `.joblib` | **Modelo canónico producción** | 167 (A_EXT 8 + B 4 + C_EXT 3 + D 96 + E 56) | Default en ModelManager |
| `model_a_gpcr.json` + `.joblib` | Familia GPCR (14 muestras) | 167 | Quality gate: ρ≥0.5 & p<0.05 → fallback a universal |
| `model_a_kinase.json` + `.joblib` | Familia Kinase (76 muestras) | 167 | Quality gate: ρ≥0.5 & p<0.05 → fallback a universal |
| `model_a_protease.json` + `.joblib` | Familia Protease (40 muestras) | 167 | Quality gate: ρ≥0.5 & p<0.05 → **PASA** (ρ=0.736) |
| `model_a_soluble_enzyme.json` + `.joblib` | Familia Soluble Enzyme (542 muestras) | 167 | Quality gate: **PASA** (ρ=0.703) |
| `model_a_nuclear_receptor.json` + `.joblib` | Familia Nuclear Receptor (15 muestras) | 167 | Quality gate → fallback a universal |
| `classifier_binder.json` + `.joblib` | Clasificador binario pKi>7 | 160 (D+E+A_EXT) | ROC AUC 0.858, integrado en /rescore |
| `model_null.joblib` | Ablación: solo features A_EXT (8) | 8 | Baseline para ablation studies |
| `morgan_rescore_v1.joblib` | Morgan fingerprint baseline | 2048 | Comparativa legacy |

> **NOTA**: `model_a.json` (176 features, incluye ProLIF) **NO debe usarse** — es el modelo legacy v1.2. Ver sección "Feature Count Mismatch" abajo.

> **RETIRADO (2026-08-13)**: la interpolación de dominio extendido fue eliminada. `model_a_extended.json` era byte-idéntico al huérfano legacy de 176 features (`model_a_legacy_176.json`, SHA-256 `23b0f3…5d3c`) y puntuaba la zona de peor confianza con peso de hasta 100% imputando las 9 features ProLIF. Las moléculas fuera de dominio ahora se puntúan con el modelo CORE (universal, o de familia si pasa el quality gate) y reciben la advertencia honesta de baja confianza con fines de auditoría. Los artefactos se movieron a `rescoring/deprecated/`.

---

## Decisiones Metodológicas Clave (para revisores)

### 1. FEATURE_GROUP_B (Vina) = 0 en Training — **DECISIÓN INTENCIONAL**

**Contexto**: `FEATURE_GROUP_B` = 4 features de Vina (`vina_best_score`, `pose_score_variance`, `pose_score_range`, `poses_passing_ratio`). En el docstring de `feature_extractor.py:11` se declara: *"Features de Vina (4 features, del docking — 0 en training)"*.

**Evidencia empírica (Experimento 1, `07_SPEARMAN_BENCHMARK_LOG.md:50-68`):**
- Se re-dockearon **540/890 complejos PDBbind** con AutoDock Vina (exhaustiveness=8, meeko receptor prep).
- Se enriqueció el feature cache con scores Vina reales (no cero).
- **Resultado**: Spearman NO mejoró. *"Agregar 4 features Vina con 61% de coverage no mueve la aguja. El problema es más profundo que 'faltan features'."*
- El modelo XGBoost ya tenía 172 features útiles (Shell+ECIF+1D/2D). Vina real no aportó señal incremental.

**Decisión**: Mantener Vina = 0 en training. En inferencia, las 4 features llegan con valores reales pero el modelo les asigna peso ~0 (porque nunca las vio ≠0). **Esto es distribution shift conocido y aceptado** — el modelo universal se diseñó para features geométricas (Shell/ECIF) que SÍ transfieren entre proteínas.

**Implicación**: El pipeline de producción usa Vina solo como **ranker primario** (EF@1% 14.92×) + XGBoost/CL-GNN como **rescorer post-docking**. No se espera que XGBoost use Vina como feature predictiva.

---

### 2. ProLIF / Interaction Features EXCLUIDAS — **3 EVIDENCIAS CONVERGENTES**

Las 9 features ProLIF (`hbond_donor_count`, `hbond_acceptor_count`, `hydrophobic_contacts`, `salt_bridges`, `pi_stacking`, `pi_cation`, `metal_coordination`, `close_contacts_4A`, `close_contacts_6A`) fueron removidas de `ALL_3D_FEATURES` en `feature_extractor.py:160-168` (Fix #3).

**Evidencia 1 — 5-HT1A benchmark (N=99 ChEMBL):**
> Interaction score (suma lineal) ρ = **-0.035** vs pKi. No correlaciona. Vina solo ρ = +0.286. XGBoost ECIF-only ρ = +0.228. (`08_SCIENTIFIC_VALIDATION.md:41-48`)

**Evidencia 2 — SHAP importance global (172 features, v1.2):**
| Feature | Tipo | SHAP | Rank |
|---------|------|------|------|
| `shell_C_C_8_12` | Geométrica | 0.0120 | #1 |
| `heavy_atom_count` | Size-norm | 0.0105 | #2 |
| `hydrophobic_contacts` | ProLIF | 0.0026 | #56 |
| `salt_bridges` | ProLIF | 0.0000 | #172 (último) |

Top-5 son **todas geométricas** (Shell, close contacts, size). ProLIF 10-100× menor. (`08_SCIENTIFIC_VALIDATION.md:138-159`)

**Evidencia 3 — Ablation v1.2 (865 complejos, CV):**
| Config | Features | Spearman CV |
|--------|----------|-------------|
| **ECIF-only** | 56 | **0.6798** (mejor individual) |
| A_ext+E (1D+ECIF) | 64 | 0.6329 |
| ALL_v4 (con ProLIF) | 172 | 0.5999 |
| ProLIF-only | 9 | 0.0 (trivial) |

ECIF-only **supera** al modelo completo con ProLIF. ProLIF introduce ruido (depende de protonación/aromaticidad correctas que PDBQT no preserva). (`08_SCIENTIFIC_VALIDATION.md:63-76`)

**Decisión**: Remover ProLIF del training (167 features). ProLIF **SÍ se calcula en inferencia** (`skip_prolif=False` en `/rescore`) y se expone en `features_used` para visualización Molstar 3D — solo no entra al XGBoost.

---

### 3. NDCG@10 Reportado Como TRIVIAL — **NO USAR COMO QUALITY GATE**

`train_pipeline.py:798-811` reporta `NDCG@10` con `groups = [1] * N` (cada complejo su propio grupo). Esto hace que NDCG sea **ranking global trivial**, no intra-target.

```python
# train_pipeline.py:366
ordered_ids = sorted(pdb_ids)
groups = [1] * len(ordered_ids)  # Cada complejo = grupo de tamaño 1
```

**El criterio `scaffold_split_ndcg_positive` (línea 801) ES VACUO**. No mide capacidad de ranking intra-target.

**Acción**: En `training_report.json` y logs, NDCG se marca como `TRIVIAL/WARN`. Métricas canónicas: **Spearman + Pearson + RMSE + MAE + Bootstrap CI** (ver `evaluate_test_set.py`). NDCG se mantiene solo por compatibilidad histórica, no para decisiones de quality gate.

---

### 4. `reg:squarederror` vs `rank:pairwise` — **DESCARTADO EMPÍRICAMENTE**

`07_SPEARMAN_BENCHMARK_LOG.md:5` (Error #5): *"Usar `reg:squarederror` en vez de `rank:pairwise` | El original también usaba regresión — no era el problema"*.

Se probó `rank:pairwise` con groups reales (requiere mapping UniProt→PDBbind) y no mejoró sobre regresión con features Shell+ECIF. La clasificación binaria (`classifier_binder`, AUC 0.858) **sí fue superior** para virtual screening (EF@1%). El pipeline actual usa regresión XGBoost + clasificador binario + stacking.

---

### 5. Feature Count Mismatch — **RESUELTO PARCIALMENTE (model_a_universal OK, model_a.json legacy)**

| Fuente | Feature Count | Estado |
|--------|---------------|--------|
| `train_pipeline.py:ALL_FEATURES` | 167 | ✅ Canónico |
| `model_a_universal.metadata.json` | 167 | ✅ Coherente |
| `model_a.metadata.json` (default ModelManager) | 176 | ⚠️ **LEGACY v1.2** — incluye 9 ProLIF |
| `training_report.json` (v1.2) | 172 | Histórico |

**En inferencia** (`model_manager.py:438-456`), `skip_prolif=True` hace que las 9 ProLIF sean **siempre 0.0** → mismatch: pesos entrenados para features que no llegan.

**Fix pendiente**: Reemplazar `model_a.json` por `model_a_universal.json` en ModelManager default, o re-entrenar `model_a` con 167 features.

---

## Métricas de Validación (Holdout Test Set — 327 complejos)

> ⛔ **INVALIDADO por leakage (P0-SCI, 2026-08-09).** Las cifras de abajo fueron
> computadas sobre `model_a_universal.json`, entrenado por `train_families.py`
> **sin excluir el frozen test set** (`split_config.json["frozen_test_set"]`, 327 IDs).
> El modelo vio esos complejos durante el entrenamiento, por lo que el "holdout"
> NO fue independiente y **0.8732 está contaminado**. NO citar como generalización.
>
> **Fix aplicado:** `train_families.py` ahora excluye el frozen test set del pool de
> entrenamiento (paso 3.5). **Acción requerida:** re-entrenar `model_a_universal` con el
> protocolo corregido y re-ejecutar `evaluate_test_set.py` para obtener una métrica
> holdout limpia. Hasta entonces, estas cifras quedan congeladas como NO válidas.

Ejecutar (solo tras re-entrenar con el fix): `cd rescoring && python evaluate_test_set.py`

| Métrica | Valor | 95% CI (Bootstrap 10k) | Estado |
|---------|-------|------------------------|--------|
| Spearman ρ | ~~0.8732~~ | [0.842, 0.901] | ⛔ INVALIDADO (leakage) |
| Pearson r | ~~0.8541~~ | [0.818, 0.886] | ⛔ INVALIDADO (leakage) |
| RMSE | ~~1.123 pKi~~ | — | ⛔ INVALIDADO (leakage) |
| MAE | ~~0.877 pKi~~ | — | ⛔ INVALIDADO (leakage) |

> ~~CV (validation): Spearman 0.7643 → Test holdout: 0.8732. "Buena transferencia".~~
> **Retractado:** el gap CV→holdout no es interpretable porque el holdout no fue disjoint.
> El 0.7643 de `training_report.json` proviene de un split aleatorio 80/20 (no scaffold).

---

## Reproducibilidad

- Semillas fijas: `random.seed(42)`, `np.random.seed(42)`, `xgb.set_config(verbosity=0)`
- PDBbind v2020 refined set (865 complejos) documentado en `training_report.json`
- Scaffold split estratificado (Bemis-Murcko) → `split_config.json["frozen_test_set"]` (327 IDs)
- ⚠️ **Nota de protocolo (P0-SCI):** el `model_a_universal.json` de producción fue
  entrenado por `train_families.py` con split aleatorio 80/20 y SIN excluir el frozen
  test set. El scaffold-split CV canónico vive en `train_orchestrator.py` (produce
  `model_a.joblib`, no `model_a_universal.json`). Ver sección "Métricas de Validación".
- Hardware: 6 cores, 32 GB RAM, GTX 1660 SUPER (opcional para GNN)
- `cudnn.deterministic = True` en `RTMScore/model/utils.py` + `train_pipeline_gpu.py` + `gnn_v2/train.py` (verificar descomentado)

---

## Próximos Pasos (Gap Analysis)

Ver `docs/datos_para_paper.md §11` — Gap analysis completo:

1. **Multi-target ≥10** (actual 3: GPCR, Kinase, Protease) → 7 targets adicionales listados.
2. **Baselines reales** (OnionNet, RF-Score-VS, GNNSeq) sobre mismos targets/decoys.
3. **MM-GBSA full validation** (MolChamb v2, AUC 0.739, ortogonal a Vina r=-0.075).
4. **Scaffold split + Sequence similarity split** (ya implementado en `evaluate_test_set.py`).
5. **Publicar pesos** vs IP strategy (§9 datos_para_paper.md).

---

## Referencias Cruzadas

- `docs/07_SPEARMAN_BENCHMARK_LOG.md` — Bitácora 8 experimentos + lecciones.
- `docs/08_SCIENTIFIC_VALIDATION.md` — Validación ProLIF, ablation, SHAP, discrepancies.
- `docs/16_AUDIT_FIXES.md` — 3 auditorías, 24 hallazgos mitigados.
- `docs/datos_para_paper.md` — Datos compilados para whitepaper, IP strategy, roadmap.
- `rescoring/deprecated/README.md` — Scripts que fabricaban métricas (aislados).

---

*Generado como parte de remediación post-auditoría 2026-07-23. Para preguntas técnicas, ver session summary en Engram (observation #84).*