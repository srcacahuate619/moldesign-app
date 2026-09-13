---
titulo: "El conjunto se armó para lo contrario de lo que hace falta"
entradilla: "91 parejas utilizables sobre 18 dianas, de 487 evaluadas. Y la razón no es un defecto: el conjunto se construyó para maximizar diversidad de dianas, que es justo lo opuesto a lo que necesita FEP+."
---

Los métodos de energía libre no calculan afinidades absolutas: calculan **diferencias**
entre moléculas parecidas. Necesitan **series congenéricas** — varios análogos de la misma
diana, que difieran en poco. Cuanto más pequeña la perturbación, más fiable el cálculo.

Esta auditoría cuenta cuántas parejas del material actual servirían.

## Qué salió

**91 parejas utilizables sobre 18 dianas**, de 487 evaluadas. Un **19%**.

Varias son de manual: tres pares con subestructura común de 26 a 33 átomos y **perturbación
cero**. Esas son exactamente el caso ideal.

Pero la estructura del conjunto es la equivocada, y esa es la conclusión real:

| | |
|---|---:|
| Dianas distintas | **104** |
| Complejos | 203 |
| Complejos que son la única entrada de su diana | **la mitad** |
| Cobertura de subestructura común (mediana) | 0.50 |
| Perturbación (mediana) | **27 átomos** |

Una perturbación mediana de 27 átomos no es una perturbación: es otra molécula.

## Por qué no es un defecto

Este es el punto que hace la auditoría útil en lugar de deprimente. El conjunto se armó
para **entrenar un selector de poses**, y para eso lo correcto es maximizar la diversidad de
dianas: cuantos más contextos distintos vea el modelo, mejor generaliza.

Energía libre quiere lo contrario: **pocas dianas con muchos análogos**.

No hay nada roto. Hay un conjunto optimizado para un objetivo, evaluado contra otro. La
implicación de diseño es que **demostrar la ruta completa exige cohortes construidas al
revés**, y esas existen: la base de datos de origen las tiene, y el grupo mayor disponible
aquí ya tiene 23 miembros.

Es una tarea de construcción de cohorte, no de investigación.

## Un error propio, encontrado y corregido

La primera pasada dio una cobertura de subestructura de **1.11** y una perturbación de
**−2**. Ambas son imposibles: la cobertura es una fracción y no puede pasar de 1, y una
perturbación no puede ser negativa.

La causa: la función que busca la subestructura común contaba un hidrógeno retenido que la
función de conteo de átomos pesados no contaba. Dos formas de contar átomos que no
coincidían.

Corregido, las parejas aptas bajaron de 96 a **91**.

Vale la pena señalar qué detectó el error: no una revisión de código, sino que **el
resultado era imposible**. Una fracción mayor que 1 no se puede explicar de ninguna manera.
Los valores fuera de rango físico son el detector de defectos más barato que existe, y
sólo funcionan si alguien mira los rangos.

## Por qué 91 es una cota superior

La agrupación de dianas se hizo por similitud de secuencia, y eso tiene dos sesgos, ambos
en la misma dirección:

- **no distingue mutantes puntuales**, que para energía libre **sí** serían dianas distintas;
- **puede unir isoformas** que tampoco son intercambiables.

Los dos inflan el conteo. Así que 91 es un techo, no una estimación central, y el número
real de parejas realmente utilizables es menor.

Declararlo así evita que la cifra se cite después como si fuera el suelo.
