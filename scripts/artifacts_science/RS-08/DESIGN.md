# RS-08 — Router de decidibilidad accionable (DESIGN)

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** EJECUTADO (sin seal, sin finish — por instrucción del maintainer)
**Preregistro:** `scripts/artifacts_science/RS-08/PREREGISTRO.md` (sello b4204bd, contrato literal)
**Plan:** `CAMPANA-2-PLAN` sellado (41b7f09) IT1/DECISIONS QA-3
**Script:** `scripts/run_rs08_router.py` (por composición; nada sellado se edita)

## 1. Veredicto del gate de desarrollo

**GATE: FAIL**

| Criterio | Valor | Requisito | Cumple |
|---|---|---|---|
| Δ fallos recuperables@2 vs margin-only | **-2** | ≥ +3 | NO |
| Δ falsos escalamientos vs margin-only | **-1** | ≤ 0 | SÍ |

Fallos recuperables@2 capturados: router **3**, margin-only **5**, aleatorio **5** (116 OOF, mismo coste real por fold).

Falsos escalamientos (complejos `solved` escalados): router **14**, margin-only **15**, aleatorio **19**.

Bootstrap BCa por las 38 componentes (10 000 réplicas, seed 42): Δ fallos recuperables@2 [-6.0, 0.0] (excluye cero: False); Δ falsos escalamientos [-10.0, 5.0] (excluye cero: False).

Drift real de presupuesto (fracción escalada en outer-test): **38.79%** global (fold 0: 40.0%, fold 1: 18.75%, fold 2: 66.67%, fold 3: 40.0%, fold 4: 26.67%); gate de operación 25–35%.

## 2. Protocolo ejecutado (literal)

- **Outer**: 5 folds EXACTOS del fold_plan sellado (sha `9d97ad70…`), `[55,16,15,15,15]`, 38 componentes. Clon v0.6 outer = el sellado (RS-01B `brazo_original` / RS-04-OOF `baseline`), sha verificados por fold (`6e872ba2/2541609f/9584f7d9/8eab79bf/fabc39ec`) + meta de hiperparámetros congelados: NO se reentrena.
- **Inner (cross-fitting ANIDADO, obligatorio)**: dentro de cada outer-train, 5 sub-folds por componentes reutilizando las asignaciones del fold_plan restringidas al outer-train donde aplique (grupos `g != f`); el quinto sub-fold parte el grupo más grande (por componentes si tiene >1; por pids ordenados si es un componente único — fold 0 con 55 pids). Para cada sub-fold se entrena un clon v0.6 inner (MISMO XGBoost congelado: rank:pairwise, 52 trees, depth 6, lr 0.05, subsample 0.8, seed 42, sin early stopping, 233 features A1 SIN strain) sobre el inner-train y se evalúa sobre el sub-fold. Features y etiquetas del router sobre el outer-train proceden de estas predicciones **inner-OOF** (el clon que predice un complejo NUNCA lo vio). PROHIBIDO el OOF global cuyos modelos vieron el outer-test.
- **Etiqueta por complejo del outer-train**: error del clon inner-OOF (top-1 rmsd > 2 Å? clase accionable@2).
- **Features del router** (13): `score_top1`, `margen_top1_top2`, `n_poses`, `abstenido` y los 9 percentiles del ganador sobre las columnas PCT_RAW de A1 (`pct_vina_score`, `pct_n_contacts_4`, `pct_n_contacts_6`, `pct_contacts_per_ha_4`, `pct_n_clashes`, `pct_pose_score_variance`, `pct_pose_score_range`, `pct_cluster_density`, `pct_n_heavy`). El margen v0.6 es FEATURE del riesgo, no el selector (QA-3g).
- **Modelo del router**: regresión logística (lbfgs, C=1.0, random_state 42; arquitectura de referencia Fase 3.5/QA-3) con estandarización ajustada DENTRO del outer-train; riesgo = P(rescoring_actionable@2).
- **Umbral**: percentil 70 del riesgo inner-OOF del outer-train (equivalente al 30% de mayor riesgo de QA-3), congelado y aplicado FIJO al outer-test (prohibido re-seleccionar mirando la distribución del outer-test). Sensibilidad 10/20/40% (percentiles 90/80/60 del outer-train) descriptiva, sin gate.
- **Drift real de presupuesto**: fracción escalada en el outer-test; gate de operación 25–35%; fuera de rango → desviación con causa, NO se re-umbraliza.
- **Comparadores al MISMO coste** (mismo número de escalamientos por fold = presupuesto real del router, pareado): (1) margin-only v0.6 — k complejos de menor margen top1−top2 del clon outer (RIVAL PRINCIPAL); (2) selección aleatoria seed 42 (CONTROL INFERIOR).
- **Estratos** hard/control (D-MF-HARD congelado) reportados por separado; McNemar exacto opcional.
- **Cero val/test/CONFIRM**: auditoría de `builtins.open` con whitelist (patrón RS-01B/RS-04-OOF); `poses_val.jsonl`, `poses_test.jsonl` y FND-05/D-RC-CONFIRM nunca se abren.

## 3. Limitación de claim

- RS-08 solo puede recibir GO **como router** (decisibilidad accionable).
- PROHIBIDO reclamar mejora de Top-1 por sí solo: el rescoring solo es útil si RS-03 (MM/GBSA-like, previa RS-03-PARAM) convierte los complejos escalados en aciertos (cascada integrada v0.6 → RS-08 → RS-03).
- El strain MMFF94s queda FUERA del camino primario de la cascada y del router (RS-04-OOF NO_GO a8c9523).

## 4. Determinismo y salidas

- Salidas sin timestamps ni aleatoriedad no-seeded; dos corridas producen `metrics.json`, `per_complex.jsonl`, `failures.jsonl` e `inner_models/meta.jsonl` byte-idénticos (verificación con sha256 en la sección de determinismo del reporte).
- `inner_models/` guarda SOLO el meta jsonl con el sha256 de los 25 clones inner (los binarios `.xgb` no se conservan); los 5 clones outer sellados se reutilizan verificados por sha.
- `validate RS-08` OK (el manifest sellado no se modifica).

## 5.1 Anclaje de integridad de los assets de resultado

El manifest de RS-08 fue sellado en el MOMENTO DEL PREREGISTRO (sello `b4204bd`, 3 assets: PREREGISTRO.md, experiment_manifest.py, manifest.schema.json). FND-05 impide re-sellar, por lo que los assets de resultado NO están registrados en el manifest sellado. Su integridad queda anclada por:

1. **Git**: commit `fa9cf70` contiene exactamente estos archivos (y `run_rs08_router.py`).
2. **SHA256 documentados aquí** (verificados tras la ejecución final):

| Asset de resultado | SHA256 |
|---|---|
| `scripts/artifacts_science/RS-08/DESIGN.md` | `55189367e2c72c78896f1a9a80940569924dcf5280024ee883b7e83444de4dff` |
| `scripts/artifacts_science/RS-08/metrics.json` | `9d8c36de5411ddd43729f31d54dc61a267d25f764492c61c6266cb1e41688747` |
| `scripts/artifacts_science/RS-08/per_complex.jsonl` | `98176f43232b3a085e73ce99b701ff400ac2c423f6be2d033e73189a285b6100` |
| `scripts/artifacts_science/RS-08/failures.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (vacío) |
| `scripts/run_rs08_router.py` | `4a937f48dda16ac181c5e36d5619dc96036a52224876cd51e2dea93e34dd69b5` |
| `scripts/artifacts_science/RS-08/inner_models/meta.jsonl` | `225500fe3fb050f3dc8d180b35028941937aca6b54222d8418bdc6f583041ba7` |

Nota de gobernanza: el sello de prerregistro antes de ejecución es la causa de esta brecha. Para los próximos experimentos con prerregistro sellado previo (RS-03-PARAM, RS-03), el seal de resultados deberá incluir los assets de resultado mediante el flujo completo (init → ejecución → seal con TODOS los assets → finish), o bien separar prerregistro y ejecución en dos experimentos. Decisión del maintainer pendiente.

## 5. Evidencia de determinismo (sha256 de dos corridas consecutivas)

| Archivo | Corrida A | Corrida B | Verdict |
|---|---|---|---|
| `metrics.json` | `9d8c36de5411ddd43729f31d54dc61a267d25f764492c61c6266cb1e41688747` | `9d8c36de5411ddd43729f31d54dc61a267d25f764492c61c6266cb1e41688747` | byte-idéntico |
| `per_complex.jsonl` | `98176f43232b3a085e73ce99b701ff400ac2c423f6be2d033e73189a285b6100` | `98176f43232b3a085e73ce99b701ff400ac2c423f6be2d033e73189a285b6100` | byte-idéntico |
| `failures.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | byte-idéntico |
| `inner_models/meta.jsonl` | `225500fe3fb050f3dc8d180b35028941937aca6b54222d8418bdc6f583041ba7` | `225500fe3fb050f3dc8d180b35028941937aca6b54222d8418bdc6f583041ba7` | byte-idéntico |
| `DESIGN.md` | `b02e02ebf5be544f65ad9c36d15f53a25714a4556051c28201e6d9197b935d4f` | `b02e02ebf5be544f65ad9c36d15f53a25714a4556051c28201e6d9197b935d4f` | byte-idéntico |

Tres corridas consecutivas (la A y la B aquí documentadas más la primera) produjeron los mismos resultados y hashes; sin timestamps en las salidas.
