---
titulo: "Cargas parciales con once criterios y ningún respaldo silencioso"
entradilla: "116 de 116 ligandos parametrizados, determinismo de 2.78e-17, y cero casos donde el sistema recurriera a un método peor sin decirlo. Sustituye un tipado heurístico escrito a mano."
---

Las cargas parciales —cuánta carga eléctrica lleva cada átomo— entran en casi todo cálculo
físico posterior: energías de interacción, solvatación, campos electrostáticos. Si están
mal, todo lo que se construya encima está mal de una forma que no produce errores, sólo
números incorrectos.

Hasta este experimento, el proyecto asignaba cargas con un tipado **heurístico escrito a
mano**. Funcionaba, en el sentido de que devolvía valores. Nadie había medido si eran
correctos.

## El modo de fallo que este experimento persigue

El peligro real de una tubería de parametrización no es que falle. Es que **funcione peor
sin avisar**: cuando el método bueno no puede tratar una molécula, muchas implementaciones
recurren silenciosamente a uno más simple y devuelven un resultado con el mismo aspecto.

El conjunto resultante queda entonces con una mezcla de cargas de dos calidades distintas,
sin ninguna marca que las separe, y cualquier análisis posterior promedia las dos sin
saberlo.

Por eso uno de los once criterios es explícitamente **cero respaldos silenciosos**.

## Qué pasó

Los once criterios se cumplen:

| Criterio | Exigido | Obtenido |
|---|---|---|
| Cobertura global | ≥95% | **100%** (116/116) |
| Cobertura por estrato | ≥90% en los 6 | **100%** en los 6 |
| Determinismo | ≤1e-6 | **2.78e-17** |
| Suma de cargas vs. carga formal | ≤1e-4 | **1e-15** máximo |
| Respaldos silenciosos | 0 | **0** |
| Energía finita y serializable | 100% | 100% |
| Mapeo biyectivo de átomos | Sí | Sí, con hash de orden |
| Trazabilidad del modelo | Registrada | Versión y SHA del modelo neuronal |
| Aislamiento de val, test y confirmatorio | Cero accesos | Cero |

El determinismo de **2.78e-17** es esencialmente el epsilon de la máquina: dos ejecuciones
producen bit por bit lo mismo. Y la suma de cargas coincide con la carga formal de la
molécula hasta 1e-15, que es la comprobación física básica — si esa suma no cuadra, las
cargas están mal por construcción.

## El detalle que hace esto reutilizable

Se registra el **SHA del modelo de producción** y su versión exacta, además de la versión
del campo de fuerza. Eso significa que cualquiera puede saber, dentro de dos años, con qué
se generaron estas cargas — y detectar si una actualización del modelo cambió los números
sin que nadie lo notara.

También se registra un **hash del orden de átomos** junto con el mapeo biyectivo. El orden
de átomos es una fuente clásica de errores silenciosos: dos representaciones de la misma
molécula con los átomos numerados distinto producen cargas correctas asignadas a los
átomos equivocados.

## Qué es y qué no es

Es un experimento de **capacidad**, no de rendimiento. No dice que las cargas nuevas mejoren
ningún resultado científico; dice que existen, que son correctas por las comprobaciones
físicas disponibles, que son reproducibles, y que sustituyen a un heurístico que nadie
había validado.

Sin este paso, cualquier experimento posterior de rescoring físico habría tenido una
variable de confusión imposible de separar del efecto que quisiera medir.
