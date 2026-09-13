---
titulo: "De 164 problemas a 54, en ocho segundos"
entradilla: "La ambigüedad tautomérica que bloqueaba la cartera H se reduce a un tercio cuando se mide su consecuencia en vez de su existencia. Y contar donadores y aceptores habría dado cero señal donde sí la hay."
---

`FEP-01` dejó el cuello identificado: **164 de 203 ligandos (81%) tienen más de un
tautómero enumerable y el pipeline no declara cuál usa**. Para docking apenas importa; para
energía libre es determinante, porque el tautómero decide qué átomos donan y cuáles aceptan
puentes de hidrógeno.

Pero ese número contaba **ambigüedad**, no **consecuencia**. Que existan varios tautómeros
posibles no significa que el que hay en el fichero sea distinto del que alguien elegiría.

Este experimento mide la diferencia.

## La medición que casi hago mal

La forma obvia de comparar dos tautómeros es contar donadores y aceptores de puente de
hidrógeno. Un sondeo previo sobre cinco ligandos la descartó:

| Ligando | ¿Canónico ≠ actual? | HBD | HBA |
|---|---|---|---|
| `10gs` | **Sí** | 5 → 5 | 5 → 5 |
| `1apv` | **Sí** | 6 → 6 | 6 → 6 |

Tautómero distinto, **totales idénticos**. El protón se mueve de un átomo a otro y la suma
no cambia.

Contar habría medido cero señal donde sí la hay. La comparación correcta es **átomo por
átomo**: cuántos hidrógenos lleva cada átomo pesado antes y después. Eso **localiza** el
protón, que es la cantidad físicamente relevante.

## Qué salió

Sobre los 203, con validez 203/203:

| | n | de 203 |
|---|---:|---:|
| SMILES canónico distinto del fichero | 84 | 41.4% |
| **El protón se mueve de átomo** | **54** | **26.6%** |
| Desacuerdo sin mover ningún protón | 30 | 14.8% |

Mediana de **2 átomos** afectados; máximo 4.

Esos 30 son instructivos: el canonicalizador reordena o kekuliza la molécula sin cambiar
dónde está el hidrógeno. Un SMILES distinto **no implica** un tautómero distinto en el
sentido que importa.

## La bandera de FEP-01 no tiene falsos negativos

De los 54 donde el protón se mueve, **los 54 estaban marcados** como ambiguos por
`FEP-01`. Cero complejos no marcados lo mueven.

La bandera es conservadora y sana. Su exceso —110 marcados sin desacuerdo— son casos donde
el fichero **ya coincide** con el canónico. Eso no prueba que sean correctos; prueba que no
hay conflicto de decisión.

## Consecuencia operativa

> Declarar tautómero para **54** complejos, no 164. Un tercio del trabajo, con la lista
> identificada por `pid`: 30 en `train`, 24 en `valtest`.

Ese es el desbloqueo concreto del primer punto de la cartera H.

## Un patrón que no buscaba

Los tres con más átomos afectados son `1m0n`, `1m0o` y `1m0q`: **4 átomos movidos cada uno,
con patrón N/N/O idéntico entre ellos**.

Son análogos de la misma serie química. El defecto es **de la serie, no del complejo** — lo
que cambia cómo se arregla: una decisión química para la serie entera, en vez de tres
decisiones independientes que podrían salir inconsistentes entre sí.

Es también, de paso, la clase de estructura que `FEP-03` echaba en falta: series
congenéricas de verdad dentro del conjunto.

## Lo que este experimento tiene prohibido concluir

Declarado en el gate antes de correr, y repetido en el sello:

> **El tautómero canónico no es «el correcto».** Es una heurística de puntuación, no una
> predicción de la población dominante a pH fisiológico.

Es la misma limitación que `FEP-01` declaró para su enumeración. Lo medido es
**desacuerdo** entre el fichero y un canonicalizador estándar, **no error**.

Queda expresamente prohibido concluir desde aquí que las poses dockeadas de esos 54 son
incorrectas. Lo que se concluye es más modesto y más útil: **en 54 complejos hay una
decisión química que nadie tomó explícitamente**, y para energía libre esa decisión hay que
tomarla y declararla.

## Incidencia registrada

RDKit emitió avisos de kekulización en unos pocos ligandos. Ninguno produjo error ni salió
del denominador, pero su canonicalización pudo estar degradada y **no se comprobó uno a
uno**. Queda anotado en lugar de silenciado.
