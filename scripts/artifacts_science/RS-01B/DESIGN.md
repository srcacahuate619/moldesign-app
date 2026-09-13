# RS-01B — Cross-fitting OOF de clones v0.6 (DESIGN)

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** EJECUTADO (sin seal, sin finish — por instrucción del maintainer)
**Autorización:** maintainer, tras el cierre de RS-01A y el sello PARAGUAS de RS-01
**Preregistro:** `scripts/artifacts_science/RS-01/PREREGISTRO.md` §4.1-4.7 (protocolo sellado, aplicado literalmente)
**Script:** `scripts/run_rs01b_crossfit.py` (por composición; nada sellado se edita)

## 1. Veredicto del gate

**GATE PRIMARIO: FAIL**

| Criterio | Valor | Requisito | Cumple |
|---|---|---|---|
| Δ Top-1 OOF acumulado (dedup − original) | **−4** (43/116 vs 47/116) | ≥ +3 | NO |
| Mediana de diferencias pareadas de RMSD | **0.000 Å** | ≤ 0.1 Å | SÍ |

El gate exige AMBAS condiciones: la mediana pareada cumple, pero el Δ Top-1
acumulado es **negativo (−4)**, muy lejos del +3 requerido. Veredicto: **FAIL**.

Lectura honesta: la deduplicación con umbral anidado NO mejora el Top-1 OOF
del selector; sobre la métrica PRIMARIA de RMSD el resultado es: **sin
evidencia de degradación en la mediana pareada** (0.000 Å — la mediana
pareada NO establece compatibilidad ni equivalencia; solo ausencia de
degradación medible en esa estadística). Tampoco aporta aciertos: McNemar
exacto **p = 0.4807** (11 pérdidas vs 7 recuperaciones, n discordantes =
18; p CORREGIDO por el corrigendum estadístico — ver §7). El intervalo BCa
primario de hits [−8.80, 4.00] (38 componentes, 10 000 réplicas) NO excluye
el cero, y su extremo superior apenas toca el umbral operacional de +3.

**Secundarias (NO gate, reporte obligatorio):** diferencia de medianas
**−0.142 Å** (2.8885 − 3.0305); suma pareada **−33.269 Å**; media pareada
**−0.2868 Å**. Nota: la diferencia de medianas es NEGATIVA (el dedup reduce
la mediana global de RMSD del ganador), pero eso es un artefacto de mezcla
de complejos (la métrica de gate es la pareada, y ambas lecturas se reportan
sin ambigüedad).

## 2. Protocolo ejecutado (literal)

- **Folds EXACTOS del fold_plan sellado** (sha `9d97ad70…`, verificado):
  `[55, 16, 15, 15, 15]` complejos, 38 componentes combinadas
  scaffold+receptor. Verificado: 116 pids cubiertos 1:1, tamaños exactos,
  38 componentes.
- **Clones v0.6** (hiperparámetros CONGELADOS): XGBRanker
  `rank:pairwise`, n_estimators=**52** (best_iteration 51 + 1) SIN early
  stopping, sin eval_set, max_depth 6, lr 0.05, subsample 0.8, seed 42,
  n_jobs 4, eval_metric "auc" con fallback "rmse" (patrón histórico).
  Relevancia −rmsd, grupos por complejo, orden canónico
  `(pid, source, file_stem, model_idx)`. TODOS los datos outer-train.
- **Dos brazos por fold**: (a) ORIGINAL — U=None en fold-eval, features de
  conjunto congeladas; (b) DEDUP — umbral ANIDADO elegido dentro del
  outer-train con la regla EXACTA de MF-11-R1 (MAYOR U ∈
  {0.5, 0.75, 1.0, 1.5, 2.0} con 0 pérdidas de cobertura ≤2.0 Å +
  degradación mediana ≤0.1 Å + reducción ≥10%; separación de oráculo
  idéntica a `dedup_pose_union_medoid.py`). U elegido se aplica al
  fold-eval (entrenamiento Y evaluación del brazo dedup).
- **U anidado por fold**: `[2.0, 1.5, None, 1.5, 1.5]`.
  - Fold 2: **U=None** (contingencia B6-i cerrada ANTES de observar):
    ningún umbral cumplió (a)+(b)+(c) dentro de su outer-train; ambas
    variantes sin dedup, el fold participa igual en el pareado. Causa
    registrada en `metrics.json → por_fold[2].causa_U`.
  - Fold 0: 2.0 Å (reducción 26.28%, degradación 0.0, 0 pérdidas).
  - Folds 1/3/4: 1.5 Å (reducciones 11.95/11.39/12.84%, degradación 0.0,
    0 pérdidas).
- **Contrato de features A1**: variance/range POR CORRIDA congelados en
  ambos brazos; tras dedup SOLO se recalcula `cluster_density` (semántica
  histórica 2.0 Å, desde `records/{pid}.json` — hallazgo RS-01A) y, en
  consecuencia, la matriz z/pct por complejo sobre el conjunto resultante.
  Validación dura: recomputación sobre el conjunto original completo =
  **2739/2739 exactas**.
- **Gate PRIMARIO**: +3 Top-1 OOF acumulados Y mediana pareada ≤0.1 Å.
  PROHIBIDO usar diferencia de medianas o suma como gate (solo
  secundarias). Aplicado literalmente.
- **Incertidumbre**: bootstrap BCa primario por las **38 componentes**
  (10 000 réplicas exactas, seed 42) sobre Δ Top-1 y sobre la mediana
  pareada de RMSD; jackknife por componentes; regla C3d aplicada (la
  mediana pareada degeneró → fallback percentil [0.0, 0.0] registrado).
  Sensibilidad por complejo (percentil, 10k) reportada aparte; sin
  discordancias b/c. McNemar exacto bilateral. Por fold: descriptivos con
  denominador explícito (umbral ≥5 componentes para intervalo; fold 0 =
  1 componente → sin intervalo).
- **31 empates (B6-ii)**: recomputación determinista de medoids verificada
  contra el sidecar sellado (**2413/2413** representantes coinciden; 212
  no-singleton / 141 empates / 31 cross-source — coincide 1:1 con
  MF-11-R1). Contrafactual COMPLETO sobre los conjuntos OOF del brazo
  dedup: **144 clusters empatados** en fold-eval (23 cross-source), **144
  alternativas evaluadas** (swap → recálculo de cluster_density + z/pct
  del complejo → re-predicción → recomputo de métricas de fold y globales):
  15 alternativas cambian ganador, 5 cambian hit, 15 clusters con ≥1
  cambio; dirección dominante `flexible_redock→flexible_redock` (9).
  Cruce con los 31: **11 en alcance** (folds con U=1.5), 20 fuera
  (fold 0 eligió 2.0; fold 2 quedó U=None).
- **Abstención OOF (secundaria)**: umbral congelado 0.097663, sin
  recalibración. Original 0.5259; dedup 0.4569.
- **Cero val/test/CONFIRM**: auditoría de `builtins.open` con whitelist
  (patrón RS-01A): 151 archivos del repo abiertos, todos declarados;
  `poses_val.jsonl`, `poses_test.jsonl` y FND-05/D-RC-CONFIRM **nunca se
  abren** (0 referencias; verificado operacionalmente).

## 3. Runtime y carga del checkpoint

- Intérprete: `python-embed/python.exe` — Python **3.11.9**, xgboost
  **3.2.0**, numpy **2.4.4**, scipy **1.17.1** (verificado en ejecución).
- Checkpoint v0.6 (`pose_selector_v06.xgb`, sha `9827ddb9…`): cargado
  SOLO para validar el contrato de features congelado (52 árboles,
  best_iteration 51, meta asserts). Sus predicciones NO se usan: los 10
  clones se entrenan desde cero por fold/brazo.
- Duración por corrida completa: ~26 s (con reuso verificado de los 10
  clones; el entrenamiento completo era ~28 s).

## 4. Determinismo

Dos corridas completas consecutivas → sha256 byte-idénticos:
- `metrics.json` `52ED0198…98119D5`
- `per_complex.jsonl` `4868DBD0…D5CF71B`

Sin timestamps ni aleatoriedad no-seeded en las salidas (la duración solo
se imprime en consola). Los 10 clones guardados con su sha256 en
`fold_models/` (para fold 2 — U=None — ambos brazos comparten modelo y
sha, como exige la contingencia B6-i). `validate RS-01`, `validate
RS-01A` y `validate RS-01B` OK.

## 5. Salidas

| Archivo | Contenido |
|---|---|
| `metrics.json` | por_fold (U, outer-train, tabla de umbrales anidados, top-1, pareados), global (gate FAIL, primaria/secundarias), bootstrap BCa 38 componentes (hits y mediana pareada), sensibilidad por complejo, McNemar, abstención, empates contrafactual, modelos_fold con sha, auditoría de cuarentena |
| `per_complex.jsonl` (116) | fold, componente, U del fold, ganador original/dedup OOF con fuente/RMSD/hit/margen/abstención, Δ pareado, hit flags |
| `failures.jsonl` | vacío (0 fallos) |
| `fold_models/` (20 archivos) | 10 clones (.xgb, formato UBJSON) + 10 metas con sha256, parámetros congelados, nº filas/grupos y U del fold |
| `DESIGN.md` | este documento |

## 6. Estado

Ejecutado y validado; **sin seal y sin finish** (instrucción explícita del
maintainer para RS-01B). Sin commits, sin pip, sin red, sin cambios al
modelo ni a ningún artefacto sellado.

Conclusión del gate: la deduplicación con umbral anidado no sostiene el
gate operacional (+3 Top-1 OOF) — Δ acumulado −4. La mediana pareada de
RMSD (0.000 Å) implica **sin evidencia de degradación en la mediana
pareada** (no compatibilidad, no equivalencia), y no hay evidencia de
mejora OOF. La decisión posterior (proponer o no el uso de val una sola
vez) queda fuera de este preregistro.

## 7. Corrigendum estadístico (2026-08-16)

- **Bug formal**: `mcnemar_hits` multiplicaba por 2 el pvalue de
  `scipy.stats.binomtest(...)`, que YA es bilateral. Fix: factor 2
  eliminado; 0 pares discordantes → p = 1.0. Fix verificado por
  `scripts/test_mcnemar_fix.py` (casos (4,0)→0.125, (11,7)→0.480682,
  (7,11)→0.480682, (0,0)→1.0 → OK).
- **RS-01B reejecutado**: p de McNemar corregido **0.961365 → 0.480682**.
  Los números CIENTÍFICOS no cambian: Top-1 OOF 47→43 (Δ −4), mediana
  pareada 0.000 Å, BCa [−8.80, 4.00], per_complex.jsonl byte-idéntico al
  pre-corrigendum. Los 10 clones se REUSARON con verificación de sha256
  contra el metrics previo (modelos_fold.reusado=true); no se reentrenaron.
- **Narrativa**: cualquier lectura de la mediana pareada se expresa
  EXACTAMENTE como "sin evidencia de degradación en la mediana pareada"
  (0.000 Å no establece compatibilidad ni equivalencia).
- **Manifest**: `git_state.commit` = 97970ce (HEAD de contenido),
  `dependencies` = python 3.11.9 + xgboost 3.2.0 + numpy 2.4.4 +
  scipy 1.17.1 + rdkit 2025.09.6 (runtime real).
- Determinismo: 2 corridas consecutivas con reuso → `metrics.json`
  sha256 `9EA0393C…A52E00` y `per_complex.jsonl` `4868DBD0…5CF71B`
  byte-idénticos.
