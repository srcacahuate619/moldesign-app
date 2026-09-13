# Scripts Deprecados — Métricas Fabricadas / Inválidas

> **Fecha de aislamiento:** 2026-07-23
> **Motivo:** Estos 4 scripts fueron identificados en la auditoría científica como fabricando métricas circulares, correlacionando contra índices posicionales, o usando mocks que contienen el ground truth. **NO son benchmarks válidos** y confundían la evaluación del modelo.
>
> El reemplazo canónico es `rescoring/evaluate_test_set.py` (PDBbind holdout 327 complejos, delta-learning reconstruction, Spearman + Pearson + RMSE + MAE con bootstrap CI) y `rescoring/valid_spearman.py` (wrapper CV liviano).

---

## 1. `spearman_test.py` — Mock Circular

**Qué hacía mal (líneas 65, 73, 83):**
```python
mock_vina = -(exp_val * 1.36) + np.random.normal(0, 1.5)  # pred = -exp*1.36 + noise
pred_val = -mock_vina / 1.36                               # pred = exp - noise/1.36
coef, p_value = spearmanr(experimental, predictions)       # spearmanr(exp, exp + noise)
```

**Por qué es inválido:** La "predicción" es `experimental + ruido gaussiano`. El Spearman mide correlación entre `exp` y `exp + noise` ≈ 0.8-0.9 siempre. **No evalúa el modelo, evalúa cuánto ruido le agregaste.**

**Evidencia en el propio código:** Comentario línea 58-59: *"En un Spearman real, tendríamos que correr el docking completo... aquí haremos una validación de la lógica de correlación."* — Admite que no es real.

---

## 2. `real_spearman.py` — Correlación contra Índice Posicional

**Qué hacía mal (línea 82):**
```python
coef, p_val = spearmanr(range(len(results)), results)  # range(len) = 0,1,2,3...
```

**Por qué es inválido:** Correlaciona los scores predichos contra `0, 1, 2, 3... N` (el orden en que se procesaron las moléculas). **No usa afinidad experimental en ningún lado.**

**El script lo admite en su docstring (líneas 1-10):**
> *"DEPRECATED — Este script tiene un bug metodologico critico. La linea 71 correlaciona contra range(len(results)) — el INDICE posicional, no contra datos experimentales reales. El Spearman reportado es invalido."*

**Pero seguía en el repo y `valid_spearman.py` lo referenciaba como "reemplazo correcto".**

---

## 3. `blind_spearman_2024.py` — Mismo Bug + Docstring Mentirosa

**Qué hacía mal (línea 67):**
```python
coef, p = spearmanr(range(len(scores)), scores)  # Igual que real_spearman.py
```

**Docstring miente (líneas 13-14):**
> *"NOTA: Estos SMILES corresponden a fármacos aprobados post-2022. El modelo PDBbind 2020 JAMÁS los ha visto."*

**Realidad (líneas 16-18):**
```python
"CC1=C(C=C(C=C1)C(=O)NC2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5", # Imatinib (2001)
"CC1=CC=C(C=C1)C2=CC(=NN2C3=CC=C(C=C3)S(=O)(=O)N)C(F)(F)F", # Celecoxib (1999)
"CNC(=O)C1=CC=CC=C1SC2=CC=C(C=C2)C=C3C4=C(C=NN4)C=C3", # Axitinib (2012)
```
**Solo 5/9 son post-2020.** Imatinib, Celecoxib, Axitinib son pre-2020. El modelo PDBbind 2020 **SÍ los pudo haber visto**.

---

## 4. `ablation_test.py` — Mock de "Ablación"

**Qué hacía mal (línea 22):**
```python
predictions = [val + np.random.normal(0, val * 0.3) for val in experimental]
```

**Por qué es inválido:** Igual que `spearman_test.py`: `pred = exp + noise(30%)`. Spearman(`exp`, `exp+noise`) ≈ 0.84 siempre. La conclusión "el cerebro es real" si ρ>0.5 es **tautológica** — siempre se cumple por construcción.

---

## 5. Artefactos del modelo Extended — RETIRADOS (2026-08-13)

**Archivos movidos aquí (preservados solo para historia, NO usar):**
- `model_a_extended.json`
- `model_a_extended.metadata.json`
- `applicability_domain_extended.json`
- `gpu_model_a_extended.joblib` (antes en `artifacts/gpu/`)

**Por qué se retiraron:**
1. `model_a_extended.json` era **byte-idéntico** (SHA-256 `23b0f312b11dadf007ddde88f1771c91f54ed08924295be46907ca10c7105d3c`) a `model_a_legacy_176.json` — el huérfano legacy de **176 features** (167 del contrato A2 + 9 ProLIF) que el contrato rechaza en carga.
2. El runtime puntuaba moléculas FUERA DE DOMINIO con este modelo con peso de hasta **100%** (`w_extended = 1.0` cuando la distancia de Mahalanobis ≥ umbral extended) e **imputaba las 9 features ProLIF faltantes con medias de entrenamiento** — es decir, la zona de menor confianza se evaluaba con un modelo retirado y valores fabricados.
3. Contradecía el principio A2/A3: jamás imputar lo que el contrato no puede proveer, jamás puntuar con un modelo fuera de contrato.

**Decisión (aprobada por el usuario):** eliminación total del modelo extended.
- Moléculas fuera de dominio → score del modelo **CORE** (universal, o de familia si pasa el quality gate) + advertencia honesta "XGBOOST FUERA DEL DOMINIO DE APLICABILIDAD… fines de auditoría".
- Sin interpolación, sin umbral extended, sin imputación de medias ProLIF.
- Los scripts de entrenamiento (`train_orchestrator.py`, `train_pipeline.py`, `train_pipeline_gpu.py`) todavía contienen código que ENTRENA este modelo — queda como deuda pendiente de limpieza; el runtime ya no lo consume.

---

## Reemplazos Válidos (Canónicos)

| Script | Qué hace | Estado |
|--------|----------|--------|
| `rescoring/evaluate_test_set.py` | **Benchmark principal.** Carga `split_config.json["frozen_test_set"]` (328 complejos PDBbind v2020 holdout, scaffold-disjoint desde Fase A), hace delta-learning reconstruction (`pKi = vina_pKi + delta`), reporta Spearman + Pearson + RMSE + MAE. **Evaluado (Fase A 2026-08-10): Spearman 0.6094 [CI95 0.528–0.679] en 328 complejos. El 0.8732 histórico está INVALIDADO por leakage — no citar.** | ✅ Canónico |
| `rescoring/valid_spearman.py` | Wrapper CV liviano sobre `feature_cache_v4/` (split=test). **Defectos conocidos:** cap `entries[:200]` arbitrario, sin bootstrap CI, clasificación binaria EXCELENTE/BUENO/... | ⚠️ Requiere refactor (quitar cap, añadir bootstrap CI, reportar effect size) |

---

## Cómo Ejecutar el Benchmark Real

```powershell
cd D:\moldesign-build\rescoring
python evaluate_test_set.py
```

**Salida esperada (post Fase A retrain 2026-08-10, holdout scaffold-disjoint):**
```
============================================================
  EVALUACION DEL TEST SET HOLDOUT
  Modelo: model_a_universal (167 features, delta-learning)
============================================================

[1/6] Cargando test set IDs...
  Test set IDs: 328
[2/6] Cargando pKi labels...
  pKi labels loaded: 4123
[3/6] Cargando features 3D del cache...
  3D features loaded: 865 complexes
[4/6] Enriqueciendo con features 1D/2D desde SMILES...
[5/6] Cargando modelo...
  Features del modelo: 167
  Delta-learning: True
[6/6] Construyendo matriz y prediciendo...

============================================================
  RESULTADOS -- TEST SET HOLDOUT (328 complejos)
============================================================
  Spearman rho: 0.6094  (p=0.000000, CI95 [0.5282, 0.6791])
  Pearson r:    0.6048
  RMSE:         1.9755
  MAE:          1.6749
  y_true range: [2.64, 11.22]
  y_pred range: [2.36, 10.63]

  --- COMPARACION CV vs TEST SET ---
  CV (validation):    Spearman 0.7731 (Fase A)
  Test set (holdout): Spearman 0.6094 (scaffold-disjoint)
  Veredicto: WARN -- Generalizacion moderada, overfit parcial.
  (El 0.8732 historico estaba contaminado por leakage y queda INVALIDADO.)
```

---

## Referencias de la Decisión

- **Auditoría científica 2026-07-23:** 3 subagentes paralelos (eficiencia, calidad, validez científica). Hallazgos consolidados en `docs/README.md` (Punto 1 de remediación).
- **Documentación histórica en `moldesign-app/docs/`:**
  - `07_SPEARMAN_BENCHMARK_LOG.md` — Bitácora de 9 experimentos iterativos.
  - `08_SCIENTIFIC_VALIDATION.md` — Validación ProLIF, ablation, SHAP, discrepancias.
  - `16_AUDIT_FIXES.md` — 3 auditorías, 24 hallazgos, todos mitigados.
  - `datos_para_paper.md` — Datos para publicación (EF@1% 29.24× promedio 3 familias, DUD-E bias tests 3 barreras).

---

## Para Futuros Desarrolladores

**Si encontrás estos archivos en `deprecated/` y te tentás a "arreglarlos": NO LO HAGAS.**

El problema no es un bug de código — es **diseño metodológico fundamentalmente erróneo**. Cualquier "fix" que mantenga la estructura de mock circular o correlación contra índice seguirá siendo inválido.

**El camino correcto:** Usá `evaluate_test_set.py` como base. Si necesitás un benchmark nuevo, extendé ese script (añadí bootstrap CI, reporte per-family, etc.) — no resucités estos patrones.

---

*Este directorio se mantiene en git history para trazabilidad. No se eliminan los archivos — se aíslan con este README para que nadie los ejecute por accidente.*