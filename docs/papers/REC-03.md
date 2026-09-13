---
titulo: "Reparar el catálogo rompió dos objetivos sanos"
entradilla: "El grid por predicción de pocket repara 6 de los objetivos accionables. En el control pierde dos que funcionaban, y no los pierde por poco: de 1.338 Å a 61.07 Å."
---

La auditoría del catálogo había encontrado 57 objetivos con la caja de búsqueda mal
colocada. La pregunta natural es si se pueden reparar automáticamente: sustituir el grid
del catálogo por uno derivado de predicción de pocket, que no necesita conocer el ligando.

Si funcionara, sería un arreglo de una sola pasada para un problema de curación manual que
de otro modo se hace objetivo por objetivo.

## Qué pasó

**El criterio de reparación pasa.** El grid por predicción repara **6** de los objetivos
accionables. El techo geométrico declarado antes era de 9 sobre los 19 evaluables, así que
alcanza el **67% de lo que la geometría permitía**.

Y repara donde tenía sentido: 5 de las 6 reparaciones son de casos donde la caja del
catálogo contenía **parcialmente** el ligando. Donde la caja estaba completamente fuera, no
repara nada. El mecanismo se comporta como se esperaba.

**El criterio de no regresión falla, y falla mal.** En el grupo de control, el grid nuevo
conserva **4 de los 6** objetivos que el catálogo tenía bien, por debajo de los 5 exigidos.

Las dos pérdidas no son marginales:

| Objetivo | Con el catálogo | Con el grid nuevo |
|---|---:|---:|
| `2H02` | 1.338 Å | **61.07 Å** |
| `7JVU` | 1.976 Å | **13.09 Å** |

Sesenta y un ángstroms. No es una degradación: es colocar el ligando en otra parte de la
proteína.

Esa asimetría es la que decide. Un arreglo automático que repara 6 y destruye 2 de forma
catastrófica no es un arreglo — es cambiar un conjunto conocido de fallos por uno
desconocido.

## El fallo de validez, y por qué no se interpretó

La validez salió en **87.1%** (324 de 372), por debajo del 98% exigido. Pero no falló de
forma difusa, que sería lo preocupante: falló **entera y exclusivamente en 4 objetivos**
que perdieron sus 12 corridas cada uno, mientras los otros 27 dieron 324 de 324 válidas.

Las causas están diagnosticadas una a una:

- `3MG0` lleva **boro**, y Vina no tiene tipo de átomo para B. Es un límite del motor, no
  del experimento.
- `6MWA` (37 torsiones), `7E2Y` (43) y `4CA8` (20 torsiones, 56 átomos) **agotaron el
  tiempo límite** de 1800 s.

Como los 4 caen igual en los cuatro brazos, no distorsionan la comparación. Aun así el
prerregistro es explícito: **un fallo de validez obliga a repetir, no a interpretar**. Así
que no se emite ningún claim positivo sobre el criterio de reparación, aunque haya pasado.

Es la clase de regla que cuesta respetar cuando el resultado que se pierde es favorable.

## Una calibración que nadie buscaba

Como control se dockeó con la caja **exacta** del catálogo, centrada a 0.00 Å del ligando —
la mejor caja posible por construcción. El re-docking acierta en **6 de 8** objetivos sanos.

Un 75% con información perfecta sobre dónde está el ligando. **Ese techo es del motor, no
del catálogo.** Ninguna mejora de grids puede superarlo, y conviene tenerlo presente antes
de atribuir a la caja fallos que son del docking.

## Conclusión registrada

La reparación automática global del catálogo por predicción de pocket **no es viable con
este motor**. Los objetivos accionables siguen siendo deuda de curación manual, uno a uno.

Es coherente con `REC-07`, que había llegado a lo mismo desde el otro lado: la geometría
del grid no es buen predictor de la calidad del docking, ni para condenar un grid ni para
reemplazarlo.
