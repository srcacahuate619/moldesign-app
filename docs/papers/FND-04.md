---
titulo: "Los intervalos de confianza, verificados con código que no los escribió"
entradilla: "Cinco experimentos calculaban su propia estadística. Una implementación independiente los recomputó: coinciden al cuarto decimal. Y reveló que uno de ellos tenía muy poca potencia para lo que buscaba."
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

Con 92 complejos cubiertos, el efecto que ese diseño detectaba con un 80 % de potencia y
α = 5 % era de 22.3 puntos porcentuales, bajo la aproximación normal y la discordancia que
supone el cálculo. Una diferencia menor no era imposible de ver: se habría visto con una
probabilidad baja. Leer en ese resultado que "el selector se acerca" no tenía soporte.

Y no fue el único: `MF-19` y `MF-08` también se ejecutaron **sin potencia suficiente**
para lo que preguntaban.

## Por qué esto cambió la forma de trabajar

De aquí salió la regla que el programa aplica desde entonces: **el efecto mínimo
detectable se declara antes de correr**. Si el diseño no puede resolver el efecto que se
busca, eso se sabe cuando todavía se puede cambiar el diseño, y no después de gastar el
cómputo.

`MF-12` fue el primer experimento en aplicarla, con un MDE de 0.136 declarado por
adelantado y un efecto observado de 0.218 que lo supera.

Es un resultado que hace más pequeño al programa que lo produjo. Tres experimentos ya
ejecutados resultaron tener potencia insuficiente, y dos de ellos ya se habían citado.
Publicarlo era la única salida honesta.

## Correcciones

**2026-10-20**, a raíz de la auditoría científica del producto (SCI-A-071). La versión
anterior decía que `RS-14` «nunca pudo» distinguir una diferencia menor de 22.3 pp y que
tres experimentos eran «formalmente indetectables por diseño». Un efecto mínimo detectable
depende de la potencia elegida (aquí 80 %, con α = 5 %): por debajo de él la detección es
improbable, no imposible. Además, la auditoría señala que el modelo de potencia de este
cálculo (respuesta por par, ±1) no corresponde a la respuesta fraccionaria de `RS-14`
(SCI-B-002), así que el propio 22.3 pp está en revisión. Ninguna cifra sellada cambia.

**2026-10-22**, a raíz de la Fase B de la auditoría científica (fase 1b del plan de arreglos,
`docs/102_FASE_1B_CORRECCIONES.md`). Ninguna cifra sellada cambia.

- SCI-B-018. El modelo del MDE toma la diferencia por complejo en {−1, 0, +1} con discordancia
  d, así que ningún efecto puede pasar de d. Con d = 3/33 = 0.091, el MDE publicado de `MF-19` y
  `MF-08` (0.132) es **imposible bajo su propio modelo**: con esa discordancia, ningún efecto
  alcanzable llega al 80 % de potencia. Esas dos filas no se citan como MDE. Las otras tres caen
  dentro del dominio.
- SCI-B-002. En `RS-14` y `RS-14-R1` la respuesta del selector es la media de tres semillas: 43
  y 36 de las 92 diferencias son fraccionarias, y el modelo ±1 sobrestima su dispersión
  (desviación típica observada 0.53 y 0.58 frente a 0.79 del modelo). Con la varianza observada
  el MDE al 80 % es **0.156** y **0.169**, no 0.223. Sigue siendo una aproximación normal.
  Productor: `scripts/analisis_fnd04_potencia_dominio.py`.
