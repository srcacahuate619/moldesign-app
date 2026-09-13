# RS-08 — Preregistro formal: router de decidibilidad ACCIONABLE (solved / rescoring_actionable@2 / sampling_needed)

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** PREREGISTRO (nada ejecutado; sin seal, sin finish)
**Referencia:** `CAMPANA-2-PLAN` sellado (`41b7f09`, IT1/DECISIONS **QA-3** — router de riesgo presupuestario dentro de los 5 folds sellados de RS-01B). Insumos: RS-01B sellado (folds `[55,16,15,15,15]` sobre 38 componentes combinadas; 5 modelos `brazo_original`), RS-04-OOF sellado NO_GO (`a8c9523`).

---

## 1. Objetivo (reformulación accionable de la decidibilidad)

**El router NO predice "v0.6 falla".** Predice qué **ACCIÓN** puede resolver el fallo del Top-1 de v0.6. Las tres clases de salida, definidas por el maintainer:

| Clase | Significado | Acción |
|---|---|---|
| `solved` | v0.6 ya seleccionó una pose ≤ 2 Å (Top-1 correcto) | Ninguna (no escalar) |
| `rescoring_actionable@2` | Top-1 falla, PERO existe una pose ≤ 2 Å entre las **top-2** | Escalar a RS-03 (la top-2 recibirá MM/GBSA-like) |
| `sampling_needed` | NO existe pose recuperable (ni top-2 ni top-3 contienen una pose ≤ 2 Å) | **Nueva generación de poses**; NO MM/GBSA-like (el rescoring no puede recuperar lo que no existe) |

- **Primaria**: `rescoring_actionable@2`.
- **Secundaria**: `@3` (top-3) — reportada como sensibilidad, nunca como gate primario.

El strain MMFF94s queda **FUERA del camino primario** (RS-04-OOF NO_GO, `a8c9523`; no se reintroduce como feature del router).

---

## 2. Requisitos de ejecución (obligatorios)

1. **Cross-fitting ANIDADO (obligatorio)**:
   - Dentro de cada outer fold, las features y las etiquetas de error del router proceden de predicciones **inner-OOF** del **outer-train** (cross-fitting interno sobre los complejos del outer-train).
   - **PROHIBIDO** reutilizar el OOF global si sus modelos vieron el outer-test: un modelo entrenado sobre un fold global que incluya el outer-test de este fold contamina la etiqueta de error del router.
2. **Umbral**: percentil **70** del riesgo inner-OOF del outer-train (equivalente a "30% de mayor riesgo" de QA-3, derivado DENTRO del outer-train, nunca fuera).
3. **Aplicación FIJA al outer-test**: el percentil 70 se congela sobre el outer-train y se aplica tal cual al outer-test. **NO** seleccionar el 30% mirando la distribución del outer-test (prohibido re-fit tras observar).
4. **Drift real de presupuesto**: reportar el porcentaje de complejos del outer-test realmente escalados (el percentil 70 del outer-train puede no traducirse en 30% exacto en el outer-test). **Gate de operación aceptable: 25–35%.** Fuera de ese rango → el fold se reporta como desviación de presupuesto (con causa), no se re-umbraliza.

---

## 3. Comparadores obligatorios

| Comparador | Rol | Definición |
|---|---|---|
| **Margen v0.6 a igual presupuesto** | **RIVAL PRINCIPAL** | Escalar los complejos de menor margen top1−top2 de v0.6, con el MISMO presupuesto (mismo 30% / mismo número de escalamientos) |
| **Selección aleatoria** | **CONTROL INFERIOR** | Escalar una muestra aleatoria de igual presupuesto (semilla 42) — cota mínima de cualquier política |

El gate se compara contra **margin-only** (rival principal). La selección aleatoria es solo control de sanidad.

---

## 4. Métricas y gate de desarrollo

### 4.1 Métrica primaria

- **Fallos recuperables@2 capturados**: complejos donde (a) v0.6 Top-1 falla (ganador > 2 Å), (b) existe pose ≤ 2 Å entre las top-2, y (c) el router los escaló (los puso dentro del presupuesto). Comparación pareada por complejo sobre los 116 OOF, por outer fold.

### 4.2 Gate de desarrollo

1. **Capturar ≥ +3 fallos recuperables@2** frente a margin-only al MISMO coste (mismo número de complejos escalados, pareado por fold).
2. **NO aumentar los falsos escalamientos de casos ya resueltos** frente a margin-only: los complejos `solved` escalados por el router no pueden exceder a los escalados por margin-only (protección: el router no debe gastar presupuesto en complejos que v0.6 ya resuelve). El incremento de falsos escalamientos (Δ `solved` escalados) debe ser **≤ 0** respecto a margin-only; si es > 0, el gate falla aunque se cumpla el +3.
3. **Bootstrap por las 38 componentes** (réplicas sobre componentes combinadas, seed 42, BCa con fallback percentil) sobre la diferencia pareada de fallos recuperables@2.
4. **Sensibilidad presupuestaria**: reportar 10% / 20% / 40% (QA-3) además del 30% primario — descriptiva, sin gate.
5. **Estratos separados**: hard y control reportados por separado (el estrato hard debe absorber la ganancia o, al menos, no degradar por debajo de margin-only).
6. **val40 y D-RC-CONFIRM intactas**: cero acceso (misma prohibición que RS-01B/RS-04; cohorte consumida para recalibración — IT1/QA-3a).

---

## 5. Limitación de claim (regla estricta del maintainer)

- RS-08 solo puede recibir **GO como router** (decisibilidad accionable).
- RS-08 **NO puede reclamar mejora de Top-1** por sí solo: el rescoring solo es útil si RS-03 (MM/GBSA-like, previa RS-03-PARAM) convierte los complejos escalados en aciertos. El claim de mejora de Top-1 solo existe tras la **cascada integrada v0.6 → RS-08 → RS-03 (MM/GBSA-like)**.
- El strain MMFF94s queda **FUERA del camino primario** de la cascada.

---

## 6. Insumos y prohibiciones

- Folds sellados de RS-01B (`fold_plan.json` sha `9d97ad70...` — 38 componentes, `[55,16,15,15,15]`): esquema de cross-fitting EXACTO del router.
- Predicciones y features: scores v0.6 + features congeladas sobre la unión original; el checkpoint v0.6 NO se toca (reutilización sin reentrenar — QA-3).
- Prohibiciones vigentes: NO entrenamiento, NO inferencia, NO pip, NO red, NO commits, NO seal/finish en esta fase (solo registro del diseño).

---

## 7. Determinismo

Salidas sin timestamps, seed 42, dos corridas byte-idénticas (patrón del programa). El umbral percentil 70 se materializa como valor numérico por outer fold y se registra (auditable).

---

## 8. Archivos de RS-08

- `manifest.json` — registro init del prerregistro (sin sellar, sin finish).
- `PREREGISTRO.md` — este documento (contrato formal).
- `README.md` — resumen breve (3 líneas).
- Skeletons vacíos (`metrics.json`, `per_complex.jsonl`, `failures.jsonl`) — sin datos (nada ejecutado).