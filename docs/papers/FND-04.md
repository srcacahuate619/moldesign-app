---
titulo: "Los intervalos de confianza, verificados con código que no los escribió"
entradilla: "Cinco experimentos calculaban su propia estadística. Una implementación independiente los recomputó: coinciden al cuarto decimal. Y reveló que uno de ellos nunca pudo detectar lo que buscaba."
---

Este experimento estaba marcado como prioridad máxima desde el inicio del programa y se
quedó sin hacer mientras cinco experimentos —incluidos los dos que decidieron el destino
de una cartera entera— calculaban cada uno su propio intervalo de confianza, con su
propio código.

Eso es un modo de fallo silencioso y conocido. Un error en un bootstrap no lanza una
excepción: devuelve un intervalo con aspecto perfectamente razonable.

## Dos trabajos en uno

**Primero, una biblioteca común**: bootstrap pareado, intervalos de Wilson, McNemar,
DeLong y corrección por multiplicidad, con 12 pruebas de cordura sobre casos de respuesta
conocida. Las 12 pasan.

Una falló en la primera pasada, y la causa merece contarse porque es exactamente el tipo
de cosa que este experimento existe para atrapar: la prueba comparaba un número decimal
con `== 1.0`, cuando el borde superior de Wilson para 10 aciertos de 10 vale 1.0 sólo
*analíticamente*, no en aritmética de punto flotante. **El defecto estaba en la prueba, no
en la biblioteca.** Se corrigió con una tolerancia.

**Segundo, y es lo que da valor a lo anterior**: recomputar con esta implementación
independiente los intervalos que ya estaban sellados.

## Qué pasó

| Experimento | Sellado originalmente | Recomputado aquí |
|---|---|---|
| `RS-14` | −0.0471 · CI [−0.1522, +0.0617] | −0.0471 · CI [−0.1594, +0.0616] |
| `RS-14-R1` | −0.0942 · CI [−0.2138, +0.0217] | −0.0942 · CI [−0.2101, +0.0217] |

Los puntos coinciden **al cuarto decimal**. Los intervalos difieren dentro del ruido
esperable del remuestreo.

Es la primera vez en el programa que un intervalo de confianza se verifica con una
implementación distinta de la que lo produjo. Los dos resultados que cerraron una línea
de investigación completa quedaron confirmados por código que no los escribió.

## El hallazgo incómodo

A la biblioteca se le añadieron dos funciones que el programa no tenía: **efecto mínimo
detectable** y **n necesario**. Aplicarlas retrospectivamente produjo lo más útil de todo
este experimento.

`RS-14` se había interpretado como evidencia de que el selector no supera al baseline por
un margen pequeño. Pero:

| | Se creía | Es |
|---|---:|---:|
| Efecto que `RS-14` podía detectar | ~10 pp | **22.3 pp** |
| Complejos necesarios para resolver 5 pp | ~370 | **1,972** |

Con 92 complejos cubiertos, ese diseño **nunca pudo** distinguir una diferencia menor a
22.3 puntos porcentuales. Cualquier lectura de que "el selector se acerca" era una lectura
de ruido.

Y no fue el único: `MF-19` y `MF-08` también resultan **formalmente indetectables por
diseño** — se ejecutaron sin potencia suficiente para lo que preguntaban.

## Por qué esto cambió la forma de trabajar

De aquí salió la regla que el programa aplica desde entonces: **el efecto mínimo
detectable se declara antes de correr**. Si el diseño no puede resolver el efecto que se
busca, eso se sabe cuando todavía se puede cambiar el diseño, y no después de gastar el
cómputo.

`MF-12` fue el primer experimento en aplicarla, con un MDE de 0.136 declarado por
adelantado y un efecto observado de 0.218 que lo supera.

Es un resultado que hace más pequeño al programa que lo produjo. Tres experimentos ya
ejecutados pasaron a estar formalmente sin potencia, y dos de ellos ya se habían citado.
Publicarlo era la única salida honesta.
