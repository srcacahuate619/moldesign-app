# MF-10-PRE — Prerregistro: relajación in situ con un force field parametrizado

**Fecha:** 2026-08-18
**Estado:** PREREGISTRO (solo el sondeo de capacidad ejecutado, declarado en §5)
**Refina:** `MF-10` de la cartera C (doc. 49 §8) — «el relax local actual no aporta; un FF bien parametrizado podría».
**Entradas selladas:** `MF-08`, `MF-02F`, `MF-09`, `RS-03-PARAM-A`.
**Entorno:** contenedor `moldesign-lab` del servidor (Vina 1.2.7, RDKit 2026.03.1, OpenFF 0.18, OpenMM 8.5.2, openmmforcefields, PDBFixer).

---

## 1. Por qué esta palanca y por qué ahora

De la hipótesis original del maintainer —tensión in situ, multi-modo, flexibilidad de receptor— la **micro-relajación in situ** es la única que sigue sin probarse. Las otras dos están cerradas: el multi-modo ya estaba saturado (`num_modes=9`) y la flexibilidad de receptor apuntaba a complejos cuyo fallo es conformacional.

Y las dos palancas geométricas se agotaron sobre la misma cohorte: `MF-08` (caja adaptativa) y `MF-02F` (reinicios K90) convirtieron **3 de 33 cada una**, moviendo la mediana ~0.8 Å. Las poses se quedan en ~3 Å y necesitan bajar de 2.0.

**Este experimento no puede correr en la máquina local.** `molflex.py` tiene una fase 3 de relax que degrada a `vina --local_only` porque Python 3.14 bloquea `openff-toolkit` — diagnóstico documentado en `moldesign-app/docs/SESSION_SUMMARY_v1.6.md`, lección 7. El contenedor tiene Python 3.11 y `RS-03-PARAM-A` ya validó que Sage 2.2.1 + NAGL parametriza 116/116 ligandos ahí.

## 2. Por qué sus datos no se degradan con RS-14

`RS-14` pregunta si un **selector** supera al baseline. `MF-10` mide qué le hace un **campo de fuerza** a una pose dentro del bolsillo. Son magnitudes físicas —RMSD antes/después y energías— que no dependen de qué modelo estadístico gane: si RS-14 da GO, estas poses relajadas son candidatas mejores para el mismo selector; si da NO_GO, siguen siendo la medición de si el FF acerca la pose. En ninguno de los dos casos hay que recomputarlas.

## 3. Diseño

**Cohorte**: los mismos **33 dominados por colocación + 15 de control** de `MF-08`/`MF-02F`, para que toda la línea sea comparable.

**Poses de entrada**: las **20 mejores por score de Vina** de cada complejo, de la unión del material de `MF-02D` y `MF-02F` (**878 poses**). Se eligen por score y **nunca por RMSD**: elegirlas por cercanía al cristal sería mirar la respuesta.

**Procedimiento por pose**: sistema proteína + ligando en vacío con `amber14-all` para la proteína y **Sage 2.2.1 vía SMIRNOFF** para el ligando, cargas **NAGL `openff-gnn-am1bcc-1.0.0`** (las validadas en `RS-03-PARAM-A`); proteína restringida con `k = 100 kcal/mol/Å²` sobre átomos pesados; ligando libre; minimización local de hasta 500 iteraciones.

**Preparación de la proteína**: filtro de `preparer.py` (solo ATOM, sin aguas ni HETATM, altloc mayoritario) y **PDBFixer** para átomos pesados que falten e hidrógenos. **`missingResidues` se vacía a propósito**: no se reconstruyen loops ausentes, porque inventar estructura lejos del bolsillo añadiría ruido sin informar la pregunta. Los cortes de cadena quedan como términos y la proteína va restringida de todos modos.

**Métrica**: `rmsd_pose_pocket` (sin alinear) **antes y después** de minimizar, sobre los mismos átomos pesados. Éxito = cruzar ≤2.0 Å.

## 4. Predicción declarada

De las 878 poses, **67 caen en la banda 2.0–3.0 Å**: son las que una minimización local puede plausiblemente cruzar. Una minimización mueve átomos décimas de Å, no ángstroms, así que **fuera de esa banda no se espera conversión**. Contarla como fracaso del método sería injusto, y contarla como éxito si ocurriera sería igual de injusto: la banda se declara aquí y no se redefine después.

## 5. Sondeo de capacidad, ya ejecutado y declarado

El gate G1 es el sondeo, y **ya corrió**: sobre `10gs` el sistema se construye y da energía **−8212.81 kcal/mol** con 33 átomos de ligando, en 8.2 s.

Se declara aquí porque descubrió tres dependencias ausentes del contenedor —`openmmforcefields`, `pdbfixer`, `lxml`— que se añadieron a la imagen antes de preregistrar. Si el sondeo hubiera fallado, **ése habría sido el resultado de MF-10** y así se habría registrado: la pregunta «¿un FF bien parametrizado podría?» se responde con un no rotundo si el FF no se puede parametrizar.

## 6. Gates

| ID | Gate | Criterio |
|---|---|---|
| G1 | **Capacidad** | el stack parametriza proteína + ligando con Sage 2.2.1 (ya PASS, §5) |
| G2 | **Validez** | ≥95% de las poses se minimizan con energía finita |
| G3 | **Mejora** | la mediana de Δ RMSD es **negativa**: la relajación acerca la pose al cristal |
| G4 | **Conversión** | al menos **5** poses de la banda 2–3 Å cruzan el umbral de 2.0 Å |

**GO** = los cuatro pasan. **NO_GO** = falla G3 o G4.

G3 y G4 son distintos a propósito: un FF puede acercar sistemáticamente sin convertir a nadie (efecto real, inútil) o convertir a unos pocos por azar sin tendencia (ruido). Se exigen ambos.

## 7. Advertencia declarada

Minimizar optimiza hacia **el mínimo del campo de fuerza**, no hacia el cristal. Puede alejar poses tanto como acercarlas, y por eso se reporta explícitamente cuántas empeoran. Un Δ mediano negativo con muchas poses empeorando sería un resultado ambiguo y se registraría como tal.

## 8. Prohibiciones

- Prohibido elegir las poses de entrada por RMSD: se eligen por score.
- Prohibido redefinir la banda 2–3 Å después de ver resultados.
- Prohibido leer un GO como cambio del protocolo de producción: `molflex.py` seguiría necesitando el stack de Python 3.11, que la máquina local no tiene.
- No se toca val, test ni `D-RC-CONFIRM`: la cohorte es de train.
