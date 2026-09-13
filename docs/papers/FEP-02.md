---
titulo: "Los nueve que fallaron tienen huecos de cadena, nueve de nueve"
entradilla: "41% de los receptores quedarían documentados. Y de paso la auditoría verificó un diagnóstico que llevaba meses siendo una conjetura razonable: p ≈ 0.0004."
---

La mitad de un complejo proteína-ligando es la proteína, y sus defectos son menos visibles
que los del ligando. Una cadena con residuos ausentes, un sitio de unión repartido entre
dos cadenas, un metal sin coordinar, una decena de aguas cuyo papel nadie decidió: todo eso
se procesa sin error y sale con aspecto normal.

Esta auditoría cuenta cuántos de los 203 receptores tendrían documentado lo necesario para
un cálculo de energía libre.

## Qué salió

**83 de 203 (41%)** quedarían documentados. Y el desglose de lo que falta:

| Defecto | Complejos |
|---|---:|
| Huecos de numeración en la cadena | **86 (42%)** |
| Sitio repartido entre más de una cadena | **43 (21%)** |
| Metales en el sitio | 52 |
| Aguas en el sitio (mediana) | **10**, ninguna clasificada |

Ese 21% con el sitio repartido entre cadenas es un modo de fallo que el propio documento de
limitaciones del proyecto marcaba como conocido — y que **nadie había contado**. Estaba en
la lista de cosas sabidas, sin número al lado, que es una forma cómoda de no saber.

Las aguas merecen mención aparte: mediana de 10 por sitio, **ninguna documentada** como
estructural (parte del sitio, hay que conservarla) o desplazable (el ligando la echa al
unirse). Esa decisión cambia el resultado de un cálculo de energía libre, y hoy la toma por
omisión quien escribió el preparador.

## La verificación que no se buscaba

Meses antes, un experimento de campo de fuerza había fallado la parametrización en 9
complejos, todos con el mismo error de plantilla. El diagnóstico propuesto entonces fue que
tenían **cortes de cadena** dejados como extremos sin capar. Era una explicación plausible y
nadie podía comprobarla.

Esta auditoría, que se hacía por otro motivo, la comprueba:

> Los 9 complejos que fallaron tienen huecos de cadena. **9 de 9.**
>
> Tasa base en el conjunto: **42.4%**. Probabilidad de que salga así por azar: 0.424⁹ ≈
> **0.0004**.

El diagnóstico queda confirmado, y con él la decisión que dependía de él: **no volver a
correr aquel experimento** para recuperar esos 9 complejos, porque su fallo no informaba
sobre el campo de fuerza sino sobre la preparación del receptor.

Es un buen ejemplo de por qué vale la pena registrar los diagnósticos aunque no se puedan
comprobar en su momento: escrito con precisión, un diagnóstico se puede verificar después
por un experimento que no existía cuando se formuló.

## La limitación, declarada

Un salto en la numeración de residuos **no siempre es un hueco físico**: hay convenciones de
numeración no consecutiva, sobre todo en estructuras alineadas a una referencia.

Así que los 86 son **candidatos, no defectos confirmados**. Cada uno exige mirar la
estructura.

Los 9 del caso anterior sí lo eran, lo cual da alguna confianza en el criterio pero no lo
valida en general. La cifra honesta es «86 estructuras a revisar», no «86 estructuras
rotas».
