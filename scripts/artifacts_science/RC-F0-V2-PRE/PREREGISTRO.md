# RC-F0-V2-PRE — Prerregistro: reconstrucción del conjunto de poses (Ruta C, Fase 0, v2)

**Fecha:** 2026-08-17
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** PREREGISTRO (nada ejecutado bajo este registro)
**Entradas selladas:** `MF-02D` (material, 17,596 poses de train), `MF-02B-R1` (cobertura corregida 79.3%), `MF-02A` (techo conformacional).
**Contrato original que se reconstruye:** `scripts/build_pose_selector_dataset.py` (Ruta C Fase 0, docs/42) + `scripts/ruta_c_fase1_5_v05.py` (224 features raw).

---

## 1. Por qué se reconstruye

`MF-02B-R1` dejó medido que **MolFlex se había aplicado a 13 de los 116 complejos de train**. En los otros 103 el conjunto de poses es el que produjo `flexible_redock`, y en 38 complejos **no existe ninguna pose a ≤2 Å del cristal**: no hay nada que seleccionar. Aplicar el generador sube la cobertura del oráculo de 67.2% a **79.3%**.

El conjunto actual no es, por tanto, un conjunto homogéneo al que le falten poses: es un conjunto **construido con distinta política de generación según el complejo**. Cualquier evaluación de selector sobre él confunde «el selector no eligió bien» con «al selector no le dieron material», que es exactamente lo que la §9 del doc. 49 prohíbe desde el 2026-08-17.

## 2. Gate de reproducción, ya superado y declarado aquí

Antes de añadir una sola pose se verificó que el contrato original se reproduce **exactamente** a partir de los registros intermedios (`data/pose_selector_dataset/records/`, que conservan coordenadas por pose), sin re-ejecutar docking:

| Split | Líneas | Resultado |
|---|---:|---|
| `poses_train.jsonl` | 2,739 | **idéntico** |
| `poses_val.jsonl` | 730 | **idéntico** |
| `poses_test.jsonl` | 831 | **idéntico** |

Se reprodujeron las tres etapas finales —densidad de clúster intra-complejo (pares < 2.0 Å en marco de pocket), división por grupo de scaffold Murcko con semilla 42 (116/40/47) y emisión en el orden canónico— y el resultado coincide línea a línea.

**Sin este gate la reconstrucción sería indefendible**: ante cualquier diferencia posterior no se podría distinguir si viene de las poses nuevas o de haber entendido mal el contrato. Artefacto: `scripts/verificar_reproduccion_dataset.py`.

También se verificó la integridad del caché de features ricas (`features_v05_progress.jsonl`, 4,300 poses × 215 features): sus SHA-256 de los tres splits **coinciden** con los archivos sellados actuales.

## 3. La decisión de diseño más delicada: los tres splits o ninguno

Añadir ~170 poses por complejo **solo a train** produciría un conjunto en el que train y val/test viven en regímenes distintos: distinto número de candidatos por complejo, distinta distribución de `cluster_density` (que cuenta vecinos < 2 Å dentro del complejo y **no es invariante de escala**), y distinta dificultad de la tarea de ranking. Un selector entrenado ahí y evaluado en val/test mediría el cambio de régimen, no su propia capacidad.

Por eso se preregistra: **se regenera con el mismo protocolo congelado en los tres splits** — train (116, ya hecho en MF-02D), val (40) y test (47).

Generar poses en val y test **no es fuga**: no se ajusta ningún parámetro ni se mira ninguna etiqueta para tomar decisiones; es la misma política de generación aplicada uniformemente. `D-RC-CONFIRM` **no se toca**.

## 4. Segunda decisión: qué poses entran

**Entran todas las poses dockeadas** (`conf*.out.pdbqt`, todos los MODEL de todos los conformeros), que es el contrato que ya tenía la fuente S2 del constructor original — no el top-K entregado.

Consecuencia declarada: **la tarea cambia**. Se pasa de rankear ~9 candidatos por complejo a rankear ~180. El conjunto v2 **no es una versión ampliada del v1**: es una tarea distinta, y más parecida a la de producción. Cualquier comparación de cifras de v0.6 entre v1 y v2 es apples-to-oranges y queda prohibida sin re-entrenar bajo el mismo protocolo.

Nota: el conjunto v1 **ya era heterogéneo** (13 complejos con ~123 poses y 103 con ~9). La reconstrucción lo vuelve homogéneo; no introduce la heterogeneidad, la elimina.

## 5. Tercera decisión: la fuente `molflex` se regenera entera

Los 13 complejos de train que ya tenían poses `molflex` las tenían calculadas con un receptor (`scripts/.work_molflex_v3/<pid>/rec.pdbqt`) que **ya no existe en disco**. Mezclar poses viejas y nuevas de la misma fuente con preparaciones de receptor distintas metería una firma de procedencia dentro de una misma fuente.

Por eso: para la fuente `molflex`, **el conjunto v2 usa exclusivamente el material de MF-02D/MF-02E**, descartando las poses `molflex` de v1. Las fuentes `flexible_redock` y `ruta_a` se conservan tal cual, con sus features del caché verificado.

**Limitación declarada**: dentro de un mismo complejo, poses de fuentes distintas se calculan sobre preparaciones de receptor distintas — cierto también en v1. El campo `source` se conserva por pose para que la procedencia pueda **auditar**; por RS-02 tiene prohibido **decidir**.

## 6. Procedimiento

1. **Generación** (`MF-02E`): MolFlex congelado sobre val (40) y test (47), `--keep`. Protocolo idéntico a MF-02D.
2. **Etiquetado**: `rmsd_pose_pocket` (sin alinear) y las 9 features baratas, por el mismo camino de código del constructor original (`procesar_trabajo`), con su guardia de mapeo completo — una pose con algún átomo pesado sin mapear se **excluye**, no se etiqueta parcialmente.
3. **Features ricas**: las 215 (shells 96 + ECIF-lite 56 + per-residuo 63) con el extractor v0.5 sobre las poses nuevas; las de v1 se toman del caché verificado.
4. **Recálculo intra-complejo**: `cluster_density` sobre la **unión** de cada complejo. No es un append: añadir poses cambia el valor de las viejas.
5. **Emisión**: mismo orden canónico y mismas claves. **La división por scaffold NO se recalcula**: se reutiliza la sellada (116/40/47), porque los complejos son los mismos y recalcularla admitiría que un cambio de poses moviera un complejo de split.

## 7. Gates

| ID | Gate | Criterio |
|---|---|---|
| G1 | **Reproducción** | reproducir `poses_{train,val,test}.jsonl` v1 línea a línea desde los registros (ya PASS, §2) |
| G2 | **Integridad del caché** | los SHA-256 de los splits registrados en el caché de features coinciden con los archivos sellados (ya PASS, §2) |
| G3 | **Conservación de split** | ningún complejo cambia de split entre v1 y v2 |
| G4 | **Conservación de poses v1** | toda pose de v1 de fuente `flexible_redock` o `ruta_a` aparece en v2 con la **misma etiqueta RMSD** y las mismas 9 features base; solo pueden cambiar `cluster_density` y las normalizadas |
| G5 | **Cobertura** | la cobertura del oráculo de v2 en train es ≥ 79.3% (lo medido por MF-02B-R1) y ≥ la de v1 en cada split |
| G6 | **Completitud de features** | cero poses sin sus 224 features; cero NaN |

**GO** = los seis pasan. **NO_GO** = falla G3, G4 o G6 (integridad del conjunto). Si falla G5 se registra y se investiga, pero no invalida el conjunto.

## 8. Fuera de alcance

- **No se entrena ni se evalúa ningún selector.** La reapertura de la cartera D y la medición de precisión condicional van en su propio prerregistro, que deberá declarar el cambio de denominador con la cifra correcta (79.3%) y aplicar protocolo OOF.
- **Prohibido** comparar cifras de v0.6 entre v1 y v2 sin re-entrenar bajo el mismo protocolo: v0.6 fue entrenado sobre v1 y evaluarlo sobre v2 mezclaría cambio de tarea con cambio de datos.
- No se toca `D-RC-CONFIRM`.
- No se re-divide por scaffold.
