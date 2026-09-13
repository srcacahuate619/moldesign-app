# MF-13-PRE — Prerregistro: ¿la función de Vina prefiere la pose nativa?

**Fecha:** 2026-08-18
**Estado:** PREREGISTRO escrito antes de ejecutar (doc. 49 §2).
**Entorno:** contenedor `moldesign-lab` (Vina 1.2.7, Meeko 0.7.1, RDKit 2026.03.1).
**Entradas selladas o registradas:** `MF-09`, `MF-02F`, `RC-F0-V2`, `MF-09-SYM`.

---

## 1. La pregunta que quedó abierta, y por qué importa tanto

`MF-09` estableció que en **30 de 33** complejos difíciles no existe pose ≤2 Å entre
~751 candidatas, y concluyó «es muestreo, no puntuación». Esa conclusión es correcta
sobre lo que midió —el material **producido** por el buscador— pero deja sin
responder la mitad complementaria: **¿reconocería la función de puntuación la pose
nativa si se la entregaran?**

Son dos fallos distintos con consecuencias opuestas:

| | Mecanismo | Palanca |
|---|---|---|
| **(A) Fallo de búsqueda** | la función prefiere la nativa, el optimizador no la encuentra | muestreo: mejor optimizador, mejor inicialización |
| **(B) Fallo de puntuación** | el mínimo global de Vina **no está** en la nativa | ninguna palanca de muestreo sirve; hace falta otra función |

Si es **(B)**, explica de una sola vez `MF-08` (caja), `MF-02F` (reinicios), `MF-09`
(cobertura) y `MF-10` (campo de fuerza): las cuatro fallaron porque buscaban mejor un
óptimo que está en el sitio equivocado. Y reorientaría la cartera C por completo.

Nadie lo ha medido. Se responde con material ya en disco y dos llamadas a Vina por
complejo.

## 2. Diseño

Cohorte: los **116 complejos de train**, cada uno en **su propio receptor y su propia
caja** — los mismos `rec.pdbqt` y `center.json` que usó el docking que produjo el
conjunto v2. Estratificados por las etiquetas de `MF-02F`: 33 COLOCACION, 15 CONTROL,
68 RESTO.

Por complejo:

1. La **pose cristalográfica** se prepara como PDBQT con el mismo tipado de Meeko que
   molflex aplica a los confórmeros.
2. `vina --score_only` sobre ella → `score_cristal`.
3. `vina --local_only` desde ella, y re-puntuación de la pose resultante →
   `score_cristal_local` y `rmsd_deriva_local`, que mide **cuánto se aleja el cristal
   al dejar que Vina lo optimice localmente**. Si el optimizador local lo empuja
   lejos, el cristal ni siquiera es un mínimo local de la función.
4. Comparación con el **mejor score entre todas las poses dockeadas** del complejo
   (`score_top1_dock`) y **percentil** del score del cristal dentro de la distribución
   de scores dockeados.

## 3. Por qué la comparación es conservadora con la hipótesis (B)

El cristal se puntúa **tal cual sale del PDB**, sin optimizar, mientras las poses
dockeadas ya vienen optimizadas por Vina. Eso juega **en contra** de que el cristal
gane. Por eso se reporta también `score_cristal_local`, que es la comparación justa —
y es la que decide el gate.

Si aun con la comparación cruda el cristal gana, la conclusión de «fallo de búsqueda»
queda sobredeterminada.

## 4. Métrica principal y regla de lectura, declaradas antes de ver los datos

**Métrica**: fracción de complejos **COLOCACION** en los que
`score_cristal_local < score_top1_dock`, es decir, en los que la función de Vina
prefiere la pose nativa optimizada localmente sobre lo mejor que su propia búsqueda
encontró.

| Fracción | Diagnóstico | Consecuencia |
|---|---|---|
| **≥ 0.70** | **BÚSQUEDA** | la función es correcta; el optimizador no llega. La palanca es el muestreo/inicialización |
| **≤ 0.30** | **PUNTUACIÓN** | el mínimo de Vina no está en la nativa; ninguna palanca de muestreo puede funcionar |
| 0.30–0.70 | **MIXTO** | se reporta la distribución completa, sin forzar una lectura |

Los umbrales se fijan **aquí** y no se redefinen después.

## 5. Predicción declarada

Se predice **BÚSQUEDA** (fracción ≥ 0.70). Razón: Vina es una función entrenada para
reproducir poses cristalográficas, y sería sorprendente que su mínimo estuviera
sistemáticamente lejos de la nativa en complejos que no tienen nada patológico. El
sondeo sobre `10gs` —declarado en §7— apunta en esa dirección.

Se predice además que el **CONTROL se comportará al revés**: allí el docking ya
encuentra la pose correcta, así que la pose dockeada está optimizada y puntuará
similar o mejor que el cristal crudo. Esa inversión esperada entre estratos es una
comprobación de cordura del diseño: si CONTROL y COLOCACION dieran lo mismo,
sospecharía del montaje antes que del resultado.

## 6. Lo que este experimento NO puede decir

- **No mide si Vina puede encontrar la pose**, sólo si la reconoce cuando se la dan.
  Un diagnóstico de BÚSQUEDA **no** implica que exista un buscador práctico que la
  encuentre: `MF-02F` ya mostró que triplicar reinicios no basta.
- **No compara funciones de puntuación.** Si sale PUNTUACIÓN, la elección de una
  alternativa exige su propio experimento.
- **No toca val, test ni `D-RC-CONFIRM`.**

## 7. Sondeo ya ejecutado y declarado

Sobre 3 complejos, para verificar el montaje antes de preregistrar:

| Complejo | Estrato | `score_cristal` | `score_cristal_local` | `score_top1_dock` | Deriva local |
|---|---|---:|---:|---:|---:|
| `10gs` | COLOCACION | −13.747 | **−14.280** | −8.955 | 0.222 Å |
| `184l` | RESTO | −7.450 | −7.731 | −7.572 | 0.317 Å |
| `186l` | RESTO | −7.171 | −7.535 | −7.891 | 0.241 Å |

Se declara porque **descubrió y corrigió un defecto del montaje**: `--local_only` no
escribe `REMARK VINA RESULT`, así que el score de la pose relajada devolvía nulo y
había que re-puntuarla — el mismo patrón que ya usa `molflex`. Sin ese arreglo, el
gate se habría evaluado sobre la comparación cruda en vez de la justa.

El dato de `10gs` es llamativo —el cristal puntúa 5.3 kcal/mol mejor que las 261
poses dockeadas, percentil 0.0— pero **n=1 y no se usa como resultado**: se declara
para que no parezca hallazgo posterior.

## 8. Prohibiciones

- Prohibido redefinir los umbrales de 0.70 / 0.30 después de ver la fracción.
- Prohibido leer un diagnóstico de BÚSQUEDA como permiso para reabrir `MF-03`,
  `MF-04`, `MF-05`, `MF-07` o `MF-12`: esos experimentos ajustan **parámetros** del
  mismo buscador, y la §8 del doc. 49 ya los declara agotados. Un BÚSQUEDA justifica
  un **buscador distinto**, no más parámetros del mismo.
- Prohibido usar el cristal como pose candidata en ningún experimento de selección:
  aquí es sonda de la función, no material de entrenamiento.

## 9. Presupuesto

~4 s por complejo medidos en el sondeo (preparación Meeko + `score_only` +
`local_only` + re-puntuación). 116 complejos → **8–12 min** de reloj en el contenedor,
un proceso, sin GPU.

## 10. Artefactos previstos

`scripts/artifacts_science/MF-13/` con `metrics.json` (resumen por estrato, fracciones,
ventajas medianas, percentiles, deriva local y el diagnóstico) y `per_complex.jsonl`
(116). Runner: `scripts/run_mf13_score_nativo.py`.
