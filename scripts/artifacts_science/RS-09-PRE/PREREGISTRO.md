# RS-09-PRE — Sub-prerregistro: robustez metamórfica del selector v0.6 (invarianza, orden, perturbación) sobre la cohorte completa

**Fecha:** 2026-08-17
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** PREREGISTRO (nada ejecutado bajo este registro; sin seal, sin finish)
**Tipo:** experimento de robustez (Cartera D, doc 49 §9 fila RS-09) — preregistrado y sellado separadamente de la ejecución (política del laboratorio).

---

## 1. Hipótesis (doc 49:310)

> Un selector debe ser robusto a rotación, orden y perturbación.

El selector de producción **v0.6** (`rescoring/artifacts/pose_selector_v06.xgb`, SHA-256 `9827DDB94C5DED5B2EF1DDA1250606D73F73163BECC310641D5BD493196E5D31`, XGBRanker rank:pairwise con 52 árboles, features 233) debe:

1. **Invariante a transformaciones rígidas** (rotación + traslación) de poses y receptor: el ranking Top-1 no cambia (tolerancia estricta 1e-6 en features, selección idéntica).
2. **Invariante al orden de poses** de entrada: permutar el orden de las poses de un complejo no cambia el Top-1 seleccionado.
3. **Sensibilidad localizada a perturbación débil** (σ = 0.1 Å): cambios de selección solo en complejos de margen bajo (concentrados en el tercil inferior de margen), sin flips `ok→mal` por encima de un umbral acordado.

## 2. Relación con R-RC5 (evidencia previa, NO duplicación)

R-RC5 (Fase 3.5, `scripts/artifacts_ruta_c_fase3_5.json`) ya probó en 10 complejos de TEST la invarianza rígida (`max_dif_224: 0.0`, OK) y en 47 complejos de TEST la perturbación σ=0.1 Å con `n_flips_ok_mal: 0`.

**RS-09 extiende lo que R-RC5 NO cubrió:**
- **Test de ORDEN de poses** (permutación) — no existe en R-RC5.
- **Cobertura completa**: los **116 complejos train sellados** (no solo 10/47 de test).
- **Muestra exhaustiva** (no 10 complejos de muestra para invarianza).
- Reporte estratificado por margen con terciles (sobre la cohorte completa, no solo test).

## 3. Alcance y no-alcance

**Alcance:**
- Re-extracción de las 224 features + 9 transformaciones (233 totales) sobre coordenadas **transformadas** (rotadas/trasladadas/permutadas/perturbadas) de los complejos train.
- Scoring con el **checkpoint congelado** de producción v0.6 (`pose_selector_v06.xgb`).
- Comparación de Top-1 (identidad de selección) entre canónico y transformado.

**No alcance:**
- NO entrena ni re-entrena ningún modelo.
- NO toca `pose_selector_v06.xgb`, `v06_production_meta.json` ni el dataset congelado.
- NO toca `backend/`, ni receptores, ni grids, ni `docs/49` (salvo el sello al final).
- NO usa val40/test/D-RC-CONFIRM para decisión: la cohorte es train (la cascada que v0.6 sirve opera sobre train).

## 4. Cohorte y datos

- **116 complejos train** (`data/pose_selector_dataset/poses_train.jsonl`, 2739 poses).
- **Fuentes de poses**: S1 (vina_redock_work), S2 (.work_molflex_v3), S3 (tmp/ruta_a) — la misma lógica de `build_pose_selector_dataset.py` que R-RC5.
- Features de referencia: cache v0.5 congelado (`features_v05_progress.jsonl`) + meta de producción.
- Receptor: PDB por fuente (`v05.obtener_receptor`).
- Ligando cristalino: `meta_cristal(pid)`.
- Cero acceso a val40/test/D-RC-CONFIRM para entrenamiento o ajuste de umbrales.

## 5. Métodos

### 5.1 Invarianza rígida (A)
- R rotación propia (QR de gaussiana, seed 1000+i) + t uniforme en [-50,50]^3 sobre coords de **todas las poses y del receptor** (mismo marco), por complejo i.
- Re-extracción 224 features + scoring v0.6.
- Criterio: `max_dif_224 <= 1e-6` y selección Top-1 idéntica al canónico (100% de los 116).

### 5.2 Orden de poses (B) — NUEVO
- Permutación determinista del orden de poses del complejo (seed 2000+i, permutación aleatoria fija).
- Re-scoring con el MISMO feature vector (no re-extracción: el orden no altera features per-pose; lo que se prueba es que el pipeline de inferencia `z-score intra-complejo + percentil` no dependa del orden).
- Criterio: Top-1 idéntico (100% de los 116). Si algún complejo cambia → bug de orden (dependencia del orden en el ranking).

### 5.3 Perturbación débil (C)
- σ = 0.1 Å gaussiano (seed 42+i) sobre átomos pesados de las poses; receptor fijo.
- Re-extracción 224 + scoring.
- Criterios:
  - Fracción de cambios de selección **concentrada en el tercil inferior de margen**: ≥ 60% de los cambios en terciles 1-2 (no en el tercil superior).
  - Flips `ok→mal` (Top-1 canónico ≤ 2 Å que deja de serlo) **≤ 2** en los 116.
  - Sin drift de re-extracción limpia vs canónico (control de calidad del extractor): `n_mismatch = 0`.

## 6. Gates

| Gate | Criterio | Tipo |
|---|---|---|
| G1 | Invarianza rígida: `max_dif_224 ≤ 1e-6` y Top-1 idéntico en 116/116 | PASS/FAIL |
| G2 | Orden: Top-1 idéntico en 116/116 | PASS/FAIL |
| G3 | Perturbación: flips ok→mal ≤ 2 | PASS/FAIL |
| G4 | Perturbación: ≥ 60% de cambios en terciles 1-2 de margen | PASS/FAIL |
| G5 | Drift re-extracción limpia = 0 (control extractor) | PASS/FAIL |
| G6 | Aislamiento: checkpoint v0.6 + dataset + cache intactos (SHA-256 verificados) | PASS/FAIL |

**Lectura:** GO = el selector v0.6 es robusto en la cohorte completa (invarianza, orden, sensibilidad localizada). NO_GO = algún gate falla; se reporta el bug con evidencia.

## 7. Artefactos

- `scripts/artifacts_science/RS-09/metrics.json` — gates, resúmenes por test.
- `scripts/artifacts_science/RS-09/per_complex.jsonl` — detalle por complejo (A/B/C).
- `scripts/artifacts_science/RS-09/failures.jsonl` — fallos de re-extracción/lectura.
- `scripts/artifacts_science/RS-09/DESIGN.md` — decisión final.
- Runner: `scripts/run_rs09_robustez.py` (en el repo, sellado con la ejecución).

## 8. Cero claims de mejora

RS-09 NO reclama mejora de Top-1 ni de cobertura. Solo caracteriza la robustez del selector v0.6 (requisito del gate confirmatorio D-RC-CONFIRM del doc 49:321: "no degradar sustancialmente mediana RMSD, robustez o tasa de fallo").
