# 39 — Runbook Fase B: Expansión de dataset y reentrenamiento honesto

**Fecha:** 2026-08-13
**Estado:** LISTO PARA EJECUTAR (piloto). Nada se ha ejecutado aún.
**Script orquestador:** `scripts/fase_b_expand_dataset.py`
**Documento de referencia:** `docs/38_FASE_B_BASELINE.md` (baseline a vencer)

---

## 1. Objetivo

Ampliar el pool de entrenamiento del modelo de rescoring desde **865 complejos
cacheados (537 train / 328 holdout)** hacia varios miles, reentrenar con el
**mismo protocolo honesto** (scaffold-disjoint, holdout congelado, seed 42,
167 features sin ProLIF, delta-learning) y demostrar que el modelo nuevo
**iguala o supera** el baseline de Fase A.

## 2. Baseline a vencer (números EXACTOS de doc 38)

| Métrica | Valor |
|---|---|
| Spearman holdout (328, scaffold-disjoint) | **0.6094** (p<0.001) |
| CI95 Spearman (bootstrap 10k) | **[0.5282, 0.6791]** |
| Pearson holdout | 0.6048 |
| RMSE / MAE | 1.9755 / 1.6749 |
| Pool entrenamiento Fase A | 537 (865 cacheados, 328 holdout) |

Protección del modelo actual: tag `fase-a-baseline`,
snapshot `rescoring/artifacts/backup_20260813_faseA/`, doc 38.

## 3. Situación de datos verificada (2026-08-13)

- `data/pdbbind/` → **5316 directorios de complejos** (refined set Zenodo);
  **3887** tienen `{pdb}_protein.pdb` + `{pdb}_ligand.sdf`.
- `INDEX_refined_data.2020` → solo **865 etiquetas** (reconstruidas).
- `feature_cache_v4/` → **865** JSONs v4; **746** con features Vina enriquecidas.
- `vina_redock_cache/` → 540; `redocked_v2/` → 2220 poses dockeadas.
- **Candidatos nuevos con estructura local pero sin etiqueta: 3022.**
- No hay general set local; la vía de expansión principal es BindingDB sobre
  las estructuras ya descargadas (alternativa: Zenodo general set, doc 40
  potencial futuro).

## 4. Cadena real de entrenamiento (contrato de datos)

Un complejo nuevo entra al pool SOLO si tiene, en este orden:

1. **Directorio** `data/pdbbind/{pdb_id}/` con `{pdb_id}_protein.pdb` y
   `{pdb_id}_ligand.sdf` (o `.mol2`) — para extracción 3D, SMILES 1D/2D y
   clasificación de familia.
2. **Etiqueta pKi** en `INDEX_refined_data.2020`
   (`PDB_ID  res  year  Ki=...  //  pKi`) — leída por
   `train_families.parse_index` (toma `parts[-1]`).
3. **Entry de feature cache** `feature_cache_v4/{pdb_id}.json` =
   `{"version": 4, "features": {...}}` (CACHE_VERSION=4) — producida por
   `feature_extractor.extract_single_complex` (mismo path que
   `train_orchestrator._extract_features_for_all`).
4. **Features Vina (Grupo B)** en el cache (merge desde `vina_redock_cache`):
   sin ellas, `build_feature_matrix` imputa por media (permitido <25% faltantes).
5. **family_map.json** (opcional): sin entrada → familia "other" (solo aporta
   al modelo universal).
6. **Exclusión del holdout**: `split_config.json → frozen_test_set`; todo ID
   ahí se quita del pool de train (`train_families` paso 3.5).

## 5. Tabla de etapas

| # | Etapa | Comando | Tiempo est. | Disco est. | Output clave |
|---|-------|---------|-------------|------------|--------------|
| 1 | Etiquetas BindingDB | `python scripts/fase_b_expand_dataset.py --stage 1 --limit 300` | 15-45 min (descarga 525 MB + scan 2.6M filas + RCSB metadata) | ~1 GB | INDEX por etapas + `faseb_selection_manifest.json` |
| 2 | Redock Vina | `python scripts/fase_b_expand_dataset.py --stage 2 --max-workers 6 --vina-path C:\...\vina.exe` | ~5 min/complejo → 300 con 6 workers ≈ **4-5 h** | ~10 MB | `vina_redock_cache/{pdb}.json` |
| 3 | Features v4 | `python scripts/fase_b_expand_dataset.py --stage 3 --max-workers 6` | 20s-2min/complejo → 300 con 6 workers ≈ **15-60 min** | ~50 KB/complejo | `feature_cache_v4/{pdb}.json` (v4 + Vina) |
| 4 | Split NUEVO scaffold-disjoint | `python scripts/fase_b_expand_dataset.py --stage 4 --test-size 500 --seed 42` | 10-40 min (parser + curación + VIP audit + clasificación) | ~1 MB | `artifacts/split_config_faseb.json` + `family_map_faseb.json` |
| 5 | Entrenar | `python scripts/fase_b_expand_dataset.py --stage 5` | 5-30 min (XGBoost CPU, pool 537+N) | ~10 MB | `model_a_*_faseb.joblib` (Fase A restaurada) |
| 6 | Evaluar + comparar | `python scripts/fase_b_expand_dataset.py --stage 6` | 5-15 min (2× bootstrap 10k) | ~1 MB | `faseb_comparison_report.json` |
| — | Promover (SOLO tras GO) | `python scripts/fase_b_expand_dataset.py --promote` | <2 min | ~10 MB | modelos activos actualizados + backup |

**Todo el piloto (300):** ~6-8 h, dominado por redock. Pre-verificación:
`--dry-run` (imprime todo sin ejecutar nada, <5 s).

## 6. Comandos exactos

```powershell
# 0. Verificación previa (no ejecuta nada)
cd D:\moldesign-build
python scripts/fase_b_expand_dataset.py --dry-run

# 1. Etiquetas (requiere internet; httpx instalado)
python scripts/fase_b_expand_dataset.py --stage 1 --limit 300

# 2. Redock (requiere AutoDock Vina + OpenBabel en PATH o --vina-path)
python scripts/fase_b_expand_dataset.py --stage 2 --max-workers 6

# 3. Features
python scripts/fase_b_expand_dataset.py --stage 3 --max-workers 6

# 4. Split nuevo (invariante: 328 de Fase A NUNCA a train)
python scripts/fase_b_expand_dataset.py --stage 4 --test-size 500 --seed 42

# 5. Entrenar (backup + swap temporal + restore automáticos)
python scripts/fase_b_expand_dataset.py --stage 5

# 6. Evaluar (GO / WARN / NO-GO + reporte JSON)
python scripts/fase_b_expand_dataset.py --stage 6

# 7. PROMOVER — SOLO si veredicto GO y decisión humana explícita
python scripts/fase_b_expand_dataset.py --promote
```

Notas operativas:
- `--force` re-ejecuta una etapa ya completada (respaldando lo previo).
- Si Etapa 2/3 se interrumpe, re-ejecutar retoma solo los pendientes (idempotente).
- Rollback de Etapa 1: copiar `INDEX_refined_data.2020.faseA_<ts>` sobre
  `INDEX_refined_data.2020` y borrar `faseb_selection_manifest.json`.

## 7. Invariantes de seguridad (NO negociables)

1. **Holdout nunca en train**: los 328 IDs del holdout Fase A se fuerzan dentro
   del NUEVO holdout (Etapa 4); `verify_scaffold_disjoint` debe dar **0
   violaciones** antes de guardar; la Etapa 4 aborta si el invariante falla.
2. **El modelo actual queda intacto** durante las etapas 1-6:
   `model_a_universal.json` nunca se sobreescribe; Etapa 5 hace backup, swap
   temporal, entrena, renombra a `*_faseb` y **restaura** los Fase A.
   Solo `--promote` (flag explícito) hace el swap, con backup previo.
3. **Hashes por etapa**: cada etapa registra SHA-256 de INDEX, split configs,
   family maps, manifest y modelos nuevos en
   `data/pdbbind/faseb_logs/faseb_pipeline_log.json` (reproducibilidad).
4. **Protocolo idéntico a Fase A**: scaffold-disjoint estratificado, seed 42,
   167 features sin ProLIF, delta-learning `pKi = -vina/1.36 + delta`,
   calidad de etiquetas filtrada por `data_curator` (rechaza IC50/EC50 y
   precisión no exacta).

## 8. Criterios Go/No-Go (Etapa 6)

| Veredicto | Condición |
|---|---|
| **GO** | Spearman Fase B ≥ **0.6094** Y CI95_lo ≥ **0.5282** (no se solapa hacia abajo con el baseline) |
| **WARN** | Spearman ≥ 0.6094 pero CI95_lo < 0.5282 (mejora con solape: revisar con más datos o más bootstrap) |
| **NO-GO** | Spearman < 0.6094 → NO promover; mantener Fase A activa |

Además, en el reporte se comparan **Fase A vs Fase B sobre el MISMO holdout
nuevo** (comparación justa, mismo denominador) y se desglosa:
- Δ FaseB vs baseline histórico (doc 38).
- Δ FaseB vs FaseA en el holdout nuevo.
- n válidos (missing features/labels se reportan y se excluyen, nunca se fabrican).

Requisitos posteriores al GO: actualizar `training_report.json`, regenerar
`model-manifest.json` (`rescoring/scripts/generate_model_manifest.py`), gate
Vina (`check_vina_importance_gate.py`) y actualizar doc 38 con la comparación.

## 9. Riesgos conocidos (documentados, no bloqueantes)

1. **Redock requiere OpenBabel + Vina** (`redock_pdbbind.py` usa `obabel` para
   preparar PDBQT). Si obabel falta, Etapa 2 falla por complejo → imputación
   por media en Grupo B. Verificar con `obabel --version` antes.
2. **Etiquetas BindingDB mixtas**: Ki/Kd se prefieren, pero IC50/EC50 solo se
   filtran en Etapa 4 (data_curator). El rendimiento real del piloto puede ser
   < 300 tras curación + VIP audit + gap de features (contrato A2 excluye
   complejos con >25% de features faltantes).
3. **Train/inference mismatch del Grupo B**: redock usa exhaustiveness 8
   (producción usa 8 por defecto) — consistente; la Etapa 3 marca
   `vina_exhaustiveness: 8` en el cache.
4. **El holdout nuevo es más grande que 500** por diseño (cuota por familia +
   cierre scaffold + 328 heredados) — es el precio de la atomicidad scaffold.
5. **No se reutilizan los 328 como train** — esta es la mayor diferencia vs un
   split ingenuo: el pool de Fase B pierde esos 328 para entrenar, garantizando
   que la comparación longitudinal contra 0.6094 siga siendo honesta.

## 10. Registro de cambios

- 2026-08-13: runbook creado; orquestador `scripts/fase_b_expand_dataset.py`
  verificado con `py_compile` y `--dry-run` (<5 s, sin ejecución pesada).
