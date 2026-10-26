---
titulo: "Setenta y cinco, o diecinueve, y la diferencia no son defectos"
entradilla: "Cinco auditorías contaban piezas sueltas. Cruzarlas cuesta once milisegundos y da el número que ninguna tenía: cuántas parejas pasan a la vez los filtros de cribado. Es una cota, no cuántos cálculos de energía libre se pueden correr."
---

La cartera de preparación para energía libre tenía tres auditorías, y ninguna respondía la
pregunta que decide el trabajo.

`FEP-01` contaba ligandos con tautómero ambiguo. `FEP-02` contaba receptores con huecos.
`FEP-03` contaba parejas congenéricas. Cada una mira una pieza — pero **un cálculo de
energía libre relativa necesita las tres a la vez, y sobre los dos miembros de la pareja**.
Si un solo extremo tiene el tautómero sin decidir o un hueco en el bolsillo, la pareja no
se puede correr.

Este experimento no mide nada nuevo. Une lo ya sellado.

## Qué salió

De las 91 parejas que `FEP-03` declaró aptas:

| Estado | Parejas |
|---|---:|
| **EJECUTABLE HOY** | **75** |
| Bloqueada sólo por tautómero | 7 |
| Bloqueada por receptor | 9 |

Las 75 abarcan **45 complejos distintos**. Declarar los tautómeros de esos 7 sube la cifra
a **82**, y eso es una decisión química documentada, no modelado estructural.

## La segunda cifra, que va obligatoriamente junto a la primera

Bajo el criterio **completo** de `FEP-02` —que exige además cadenas, disulfuros, metales,
cofactores y aguas documentados en ambos extremos— quedan **19 parejas**.

Setenta y cinco contra diecinueve. Y lo que hay entre medias es lo importante:

> La distancia entre 75 y 19 **no son defectos**. Es documentación ausente.

Ninguna de esas 56 parejas está rota. Lo que les falta es que alguien declare qué hace con
las aguas del sitio, con los metales y con las cadenas. Nadie tiene que reparar nada: hay
que decidir y escribir.

Esa distinción decide cómo se planifica la cartera, porque **documentar y reparar cuestan
órdenes de magnitud distintos**.

## Por qué la vista por pareja sale mejor que la vista por complejo

`FEP-01` reportó 19% y `FEP-02` un 41% sobre los 203. Aquí sale 75 de 91. Parece
contradicción y no lo es:

Las 91 parejas aptas **ya son un subconjunto filtrado** por `FEP-03` —pocas dianas con
muchos análogos— y ese subconjunto está mejor preparado que la media del conjunto.

La lección de método es más general que este experimento:

> La unidad de inferencia de un cálculo de energía libre es **la pareja**, no el complejo. Y
> nadie había contado en esa unidad.

Contar en la unidad equivocada hizo que la cartera pareciera más bloqueada de lo que está.

## Lo que este número tiene prohibido

Declarado en el gate antes de correr: **«ejecutable hoy» significa sin los dos bloqueos
medidos, no «lista para producción»**. Los 75 son una **cota superior** y queda prohibido
citarlos como «parejas listas para FEP+».

El criterio completo se reportó aparte y deliberadamente **no se usó para clasificar**. Si
se hubiera usado, el experimento diría «19» y escondería que 56 de esas parejas están a una
decisión documental de distancia, no a una reparación. Las dos cifras describen cosas
distintas y las dos hacen falta.

## Coste

Once milisegundos. Cinco artefactos sellados, un cruce, y el número que ordena la cartera.

Es el argumento más claro que tengo a favor de mantener el registro: la información ya
estaba pagada. Sólo faltaba preguntarle lo correcto.

## Correcciones

**2026-10-20**, a raíz de la Fase B de la auditoría científica del producto. Ninguna cifra sellada cambia y no se repitió ningún cálculo; esto corrige lo que el texto afirmaba a partir de ellas. Detalle y procedencia en `docs/101_CORRIGENDA_SELLOS_AUDITORIA_20261020.md`.

- SCI-B-046. Las 19 parejas son las que pasan el filtro de FEP-02 —sin huecos de numeración y sin sitio entre cadenas—, no un criterio completo con cadenas, disulfuros, metales, cofactores y aguas. En esas 19 hay parejas con aguas de sitio, metales y disulfuros sin clasificar.

**2026-10-22**, a raíz de la Fase B de la auditoría científica (fase 1b del plan de arreglos,
`docs/102_FASE_1B_CORRECCIONES.md`). Ninguna cifra sellada cambia.

- SCI-B-049. Las 400 parejas «bloqueadas por el receptor» son las que el clasificador marca
  primero por receptor: 59 de ellas también tienen un tautómero ambiguo, así que reparar el
  receptor no las desbloquea. Que las otras 341 sean ejecutables tras la reparación no se midió.
  «Reparar receptores recupera 400 parejas» no se sostiene.

**2026-10-22.** La entradilla presentaba el cruce de flags como número de cálculos de energía libre disponibles, que SCI-B-046 y SCI-B-048 retiraron (hallazgo L2-SOL-007 de la revisión de papers de Sol).

## FEP-07-PDBBIND: el cruce de PDBBind aporta una cota de cribado por pareja

**GO descriptivo del cruce.** Amplía la población de parejas auditadas; no cuenta cálculos de energía libre ejecutados ni sistemas transferibles validados.

Sobre 3299 parejas candidatas del artefacto de series, los dos estados no cuantificados antes en este paper son:

| Etiqueta del clasificador | Parejas |
|---|---:|
| Sin los dos bloqueos medidos | 2243 |
| Prioridad de tautómero | 656 |

El primer grupo implica 1114 complejos. Las parejas comparten extremos; no son observaciones independientes de eficacia. **SCI-B-048** retira «ejecutables hoy» como readiness y **SCI-B-049**, detallada arriba, impide leer el estado prioritario como desbloqueos. Se mantiene SCI-B-046 sobre el supuesto filtro completo. No comprobado por mí: reconstruir cruces desde las fuentes moleculares originales. Fuente: `FEP-07-PDBBIND`.
