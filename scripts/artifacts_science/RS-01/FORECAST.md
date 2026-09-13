# RS-01 — FORECAST (costos estimados, solo planificación — nada ejecutado)

**Fecha:** 2026-08-16
**Bases de estimación (evidencia histórica medida):**

| Evidencia | Valor | Fuente |
|---|---|---|
| Extracción completa de features ricas (4300 registros + tipado RDKit de receptores, primer paso, 1 núcleo) | ~93 s (≈22 ms/pose) | `scripts/artifacts_ruta_c_fase1_5.json` → `features.nota_tiempos` |
| Entrenamiento v0.5 (2 modelos, cache caliente) | ~2 min | ídem |
| Pipeline Fase 1.6 completo (modelos A+B, cache caliente) | 5.3 s | `scripts/artifacts_ruta_c_fase1_6.json` → `duracion_total_s` |
| Build del dataset (pasada A features baratas + pasada B cluster_density + emisión; 4300 registros / 156 complejos) | 17.5 s | `data/pose_selector_dataset/manifest.json` → `duracion_total_s` |
| Checkpoint v0.6 (tamaño) | 199,127 bytes | `pose_selector_v06.xgb` |

---

## 1. RS-01A — auditoría del checkpoint congelado

**Carga:** **2739 poses ÚNICAS** (el conjunto deduplicado de 2413 es un
subconjunto de las mismas poses: la dedup solo descarta poses ya existentes en
la unión, NO crea extracciones nuevas. Sin extracción duplicada).

| Componente | Estimación | Base |
|---|---|---|
| Features por pose (ruta PRIMARIA: **vista train-only** `cache_train_only_view.jsonl` (2739 registros, B4) + las 8 baratas que NO están en la unión desde `poses_train.jsonl` (`vina_score` sí viene de la unión), validación por sha y por identidad posicional) | 1-2 min (I/O + armado) | sin extracción geométrica |
| cluster_density post-dedup (pares pose-pose RMSD por complejo: ~32k pares original + ~25k dedup, ~116 complejos) | segundos (paralelizable por pid) | pasada B completa de train+val+test entró en los 17.5 s del build del dataset |
| variance/range de conjunto + z/pct por complejo + `Booster.predict` (52 árboles) | segundos | inferencia ms-escala |
| Contingencia SOLO si la vista invalidara (re-extracción geométrica con `feature_extractor.py`) | **2739 × 22 ms ≈ 60 s** en 1 núcleo; ~15-30 s con 4 workers | 93 s / 4300 registros |
| Análisis de los 31 empates cross-source (recomputación determinista de sumas de medoid por cluster) | minutos | dmat por pid + sidecar |

**Wall RS-01A:** P50 ≈ **3-6 min**, P90 ≈ **15-20 min** (dominado por I/O, verificaciones byte-idénticas y la auditoría de empates). 4/6 workers aplican en contingencia y en la recomputación de cluster_density por complejo.

**Almacenamiento RS-01A:** resultados JSONL (scores, márgenes, abstenciones, ganadores por complejo) ≈ **5-10 MB**. Sin poses nuevas (se lee la unión sellada).

---

## 2. RS-01B — cross-fitting OOF (K=5, 2 variantes)

**Carga:** 5 folds × 2 variantes = 10 clones XGBoost. Per-pose features
COMPARTIDAS entre variantes (solo cambian las dependientes del conjunto).
**Outer-train reales según fold_plan**: fold 0 tiene 55 complejos → outer-train
de **61**; folds 1-4 tienen 16/15/15/15 → outer-train de **100/101/101/101**.

| Componente | Estimación | Base |
|---|---|---|
| Tipado RDKit de receptores + secuencias por cadena (one-time, 116 receptores) + componentes scaffold/receptor (union-find k-meros K=8, umbral 0.90) | 2-4 min one-time | tipado RDKit incluido en los 93 s históricos; clustering de cadenas segundos |
| Armado de matrices por fold desde la vista train-only del cache | segundos por fold | I/O |
| Anidación del umbral de dedup (por fold sobre el outer-train REAL: 61 complejos ≈ 1.4k poses ≈ 17k pares en fold 0; 100/101/101/101 complejos ≈ 2.4k poses ≈ 28k pares en folds 1-4; clustering greedy ×5 umbrales) | 1-3 min por fold → 5-15 min total (paralelizable) | escala de `dedup_pose_union_medoid.py` sobre train completo |
| Entrenamiento de clones: 10 × (2-10 s) | 20-100 s total | Fase 1.6 completa en 5.3 s (cache caliente); v0.5 ~2 min con cache caliente |
| Inferencia sobre folds de evaluación + bootstrap pareado (**10 000 réplicas exactas**, BCa primario por las 38 componentes) | segundos-minutos | ms-escala |

**Wall RS-01B:** P50 ≈ **10-20 min**, P90 ≈ **45-90 min** (dominado por la anidación del umbral por fold y verificaciones byte-idénticas). 4/6 workers: folds y variantes son independientes (features por pose compartidas); la anidación del umbral es por fold.

**Almacenamiento RS-01B:** 10 clones × ~199 KB ≈ **2 MB** + resultados OOF/pareados/bootstrap ≈ **5-10 MB**.

---

## 3. Totales RS-01 (A + B)

- **Wall:** P50 ≈ **20-30 min**, P90 ≈ **1.5-2 h** con 4/6 workers (la extracción de features NO es el cuello de botella: se reutiliza la vista train-only del cache del dataset).
- **Almacenamiento:** < **35 MB** total (resultados JSONL + 10 checkpoints de clones). Cero docking, cero poses nuevas.
- **Riesgos de costo identificados:**
  1. Vista del cache invalidada → re-extracción geométrica de **2739 poses únicas** (~1 min 1 núcleo, ~30 s 4 workers) — acotado y solo para RS-01A.
  2. Anidación del umbral más lenta de lo esperado por fold (clustering greedy en 5 umbrales) — acotado a minutos por fold, paralelizable.
  3. Diferencia de versión xgboost (3.2.0 en los interpretes del programa vs pin 2.1.4 del microservicio) — no cambia costo, solo implica registrar la versión usada y tratar RS-01A como auditoría de compatibilidad (ya declarado en PREREGISTRO.md §3.5).
