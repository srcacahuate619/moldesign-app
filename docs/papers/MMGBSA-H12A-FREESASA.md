---
titulo: "FreeSASA falla su gate por medio ångström cuadrado"
entradilla: "La SASA numérica que ya viaja dentro de la RDKit acierta por átomo con una mediana de 0,14 Å², veinte veces mejor que LCPO. Pero su p95 sale 0,55 con el tope en 0,5, y se sella NO_GO sin reformular el criterio."
---

LCPO no representa bien los anillos polibromados (`MMGBSA-H2`). La alternativa
obvia es calcular el área con un método numérico en lugar de una fórmula
analítica. La RDKit que ya viaja en el instalador trae FreeSASA (algoritmo de
Lee-Richards), así que la pregunta era si es lo bastante exacta y rápida.

## Qué se midió

Área por átomo de FreeSASA frente a una SASA numéricamente exacta (Shrake-Rupley
con 50 000 puntos), con los mismos radios y la misma sonda, en los 121
ligandos de PDBBind con Br o I: 3088 átomos pesados. Tope por átomo: p95 ≤ 0,5
Å² y máximo ≤ 1,0 Å², en el conjunto y por elemento, y ≤ 50 ms por ligando.

## Qué salió

**NO_GO por la letra.**

| | mediana | p95 | máximo |
|---|---:|---:|---:|
| Todos | 0,144 | **0,553** | **1,221** |
| Br | 0,261 | 0,643 | 1,177 |
| I | 0,163 | 0,547 | 0,664 |

Tarda 0,55 ms por ligando. El techo lo pone la resolución por defecto de
Lee-Richards, que la RDKit no deja cambiar.

## Por qué no se reformula

Con estos números delante sería fácil escribir un criterio energético que
pasara: 1,22 Å² por la tensión superficial habitual son menos de 0,009 kcal/mol.
Pero un criterio diseñado después de ver los datos pasa por construcción. El
gate se fijó antes y se sella como dice.

## Lo que sí queda establecido

Como caracterización, el error de FreeSASA es unas **veinte veces menor** que el
de LCPO, cuya mediana de fondo es 2,81 Å² y que en Br e I llega a p90 de 9,8.
Para decidir el término no polar del producto pesa esa comparación, no sólo el
veredicto.
