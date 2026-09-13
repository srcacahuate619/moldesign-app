# RS-14-PRE — Reapertura de la cartera D: ¿hay selector una vez corregido el denominador?

**Fecha:** 2026-08-18
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** PREREGISTRO (nada ejecutado bajo este registro)
**Autorización:** reapertura de la cartera D concedida explícitamente por el maintainer.
**Entradas selladas:** `RC-F0-V2` (conjunto v2), `MF-09` (margen de selección medido a nivel de pose), `MF-02B-R1` (cobertura corregida).

---

## 1. Qué cambió en el denominador

La §19.1 suspendió la cartera D y exige, para reabrirla, **un prerregistro que declare qué cambió en el denominador**. Cambió esto:

| | v1 | v2 |
|---|---:|---:|
| Complejos con MolFlex aplicado | 13 de 116 | **116 de 116** |
| Cobertura del oráculo (train) | 67.2% | **79.3%** |
| Poses por complejo (mediana) | ~9 | **~162** |
| Poses de train | 2,739 | **18,812** |

No es «más de lo mismo»: en 38 complejos de v1 **no existía pose que seleccionar**, y los experimentos que fallaron —`RS-01`, `RS-04-OOF`, `RS-08`— midieron Top-1 global sobre ese universo. `MF-02B-R1` lo documentó.

## 2. Por qué esperar señal, y cuánta

`MF-09` midió el margen a nivel de pose sobre los complejos **cubiertos**: los 15 del control tienen pose buena disponible, el top-1 por score de Vina acierta en **7** y el top-5 en **14**. Es decir, **8 de 15 complejos tienen la pose correcta disponible y el score no la pone primera, pero sí entre las cinco primeras**. El Spearman score–RMSD es 0.483 donde hay señal.

Eso acota la expectativa por arriba y por abajo: hay margen real, y está en los cubiertos. Este experimento pregunta si un selector lo captura.

## 3. Diseño

**Datos**: v2 **solo train** (18,812 poses, 116 complejos). Val y test **no se tocan** — se reservan para una confirmación posterior si este experimento da GO. `D-RC-CONFIRM` intacto.

**Features**: las 224 raw del extractor v0.5, transformadas con el contrato exacto de v0.6 — z-score por columna **dentro de cada complejo** (std 0 → z 0), más rangos percentiles 0–100 sobre las 9 features de `PCT_RAW`, NaN → 0 tras transformar. Total 233.

**Modelo**: `XGBRanker` `rank:pairwise` con los hiperparámetros documentados de v0.6 (500 árboles, `max_depth` 6, `lr` 0.05, `subsample` 0.8, early stopping 50). Relevancia = −RMSD, grupos por complejo.

**Evaluación**: **leave-one-complex-out (LOCO)** — 116 ajustes por semilla, semillas 42/43/44. El complejo evaluado nunca aporta poses al entrenamiento. Early stopping sobre una partición interna agrupada por complejo (80/20, semilla fija) del propio fold de entrenamiento.

**Baseline**: ranking por `vina_score` crudo.

## 4. Métricas — la descomposición obligatoria de la §9

Se reportan **los tres números por separado** y **el gate se evalúa sobre la precisión condicional**:

- **cobertura del oráculo** = complejos con alguna pose ≤2.0 Å. Fija por los datos: **79.3%** (92 de 116). Es covariable, no resultado.
- **precisión condicional** = Top-1 acertado / complejos cubiertos.
- **Top-1 global** = precisión condicional × cobertura. Se reporta como resultado ITT obligatorio.

Umbral de acierto: RMSD `rmsd_pose_pocket` ≤ 2.0 Å, sin alinear.

## 5. Control de nulo, y por qué es imprescindible

Con 233 features y 116 complejos como unidad de inferencia, el régimen es **p > n**: un modelo puede aparentar señal por sobreajuste al ruido. Por eso el gate primario no basta.

**Nulo por permutación**: 200 permutaciones que barajan las etiquetas de RMSD **dentro de cada complejo**, preservando la estructura de grupos y el número de poses. Cada permutación se evalúa con 5-fold agrupado. La precisión condicional observada debe superar el **percentil 95** de esa distribución nula.

Permutar dentro del complejo —y no globalmente— destruye la relación pose↔calidad conservando todo lo demás, que es exactamente la hipótesis nula que importa.

## 6. Gates

| ID | Gate | Criterio |
|---|---|---|
| G1 | **Validez** | los 348 ajustes LOCO completan sin error |
| G2 | **Superioridad** (primario) | precisión condicional del selector > baseline de Vina, con el CI95 BCa de la diferencia **pareada por complejo** excluyendo el cero |
| G3 | **Nulo** | la precisión condicional observada supera el percentil 95 de la distribución nula por permutación |
| G4 | **Determinismo** | misma semilla reproduce el mismo resultado |

**GO** = los cuatro pasan. **NO_GO** = falla G2 o G3.

Un GO **no promueve nada a producción**: habilita una confirmación sobre val, que exige su propio prerregistro.

## 7. Prohibiciones

- **Prohibido comparar cifras con v1**: v0.6 se entrenó sobre v1 y la tarea cambió de ~9 a ~162 candidatos. Cualquier comparación cruzada mezcla cambio de datos con cambio de tarea.
- Prohibido tocar val, test o `D-RC-CONFIRM` en este experimento.
- Prohibido ajustar hiperparámetros mirando el resultado: son los de v0.6, congelados aquí.
- Prohibido reportar Top-1 global como si fuera el gate: el gate es la precisión condicional (§9).
- Prohibido leer un NO_GO como «el selector no sirve» sin mirar antes la cobertura: si la señal no aparece con 79.3% de cobertura, el límite puede seguir siendo el generador.
