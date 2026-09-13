---
titulo: "El orden real atenúa la desviación en vez de crearla"
entradilla: "conf0 es exactamente un confórmero medio: rango 0.503 contra 0.5 esperado. Y sólo el 2.3% de los órdenes aleatorios da un chi² tan pequeño como el real. La explicación que yo mismo había elevado a más plausible se cae con dos contrastes."
---

`MF-33-EXT-MOD` observó que la distribución del **primer acierto** —cuántos confórmeros hay
que dockear hasta encontrar uno que cubra— se desvía de una geométrica homogénea. Hay más
complejos de los esperados que aciertan al primer intento.

Una desviación así admite dos explicaciones muy distintas. Puede ser **heterogeneidad entre
complejos**: unos son fáciles y otros refractarios, y mezclar dos poblaciones rompe la
geométrica. O puede ser mucho más aburrido: que **el orden no sea intercambiable**, que
`conf0` sea el primero que ETKDG genera y resulte sistemáticamente mejor que sus hermanos.

En el registro de `MF-33-EXT-MOD` llegué a llamar a la segunda «la explicación más simple y
más probable del exceso en k=1». Este experimento existe para ponerla a prueba, y la
falsifica.

## Un re-análisis exacto, sin recomputar nada

Cada confórmero se dockeó independientemente con la misma semilla y su `rmsd_min` está
guardado por separado. Eso hace que **permutar el orden sea una re-lectura exacta**, no una
simulación: los mismos números, leídos en otro orden.

Tres contrastes, declarados en `MF-33-ORD-PRE` antes de correr.

## Contraste 1 — conf0 no es especial

| | |
|---|---:|
| Rango normalizado medio de `conf0` entre los K de su complejo (n=109) | **0.503** |
| Esperado bajo intercambiabilidad | 0.500 |
| z | 0.116 |
| p | **0.908** |

`conf0` es exactamente un confórmero medio. La idea de que el primero de ETKDG tuviera
ventaja intrínseca no tiene ningún apoyo.

## Contraste 2 — la desviación sobrevive al orden, y en la dirección contraria

Diez mil permutaciones del orden, recalculando el chi² con el procedimiento idéntico al de
`MF-33-EXT-MOD`:

| | |
|---|---:|
| chi² observado | **11.03** |
| Mediana de la nula por permutación | 25.14 |
| p95 de la nula | 39.33 |
| **p de permutación** | **0.9773** |

Sólo un **2.3%** de los órdenes aleatorios da un chi² tan pequeño o menor que el real.

Léase despacio: si el exceso en k=1 fuese artefacto de haber puesto primero un confórmero
privilegiado, randomizar debería *acercar* la distribución a la geométrica. Ocurre lo
contrario. **El orden real atenúa la desviación en vez de crearla.**

Eso permite retirar el efecto de posición con seriedad.

## Por qué esto NO establece la heterogeneidad

El prerregistro lo prohíbe expresamente, y la razón es estructural: **la permutación conserva
el multiconjunto de RMSDs de cada complejo**. La hipótesis nula ya incluye toda la
heterogeneidad entre complejos. Este contraste no la pone a prueba — sólo pone a prueba el
orden.

La formulación correcta es que la heterogeneidad entre complejos sigue siendo una explicación
**plausible** de la desviación, no la explicación en pie por descarte. Quedan sin separar la
dependencia entre confórmeros, la heterogeneidad en el **número** de confórmeros, la
geometría de los estados generados, las diferencias entre bolsillos, la interacción
confórmero-receptor y la estructura de orden posterior. Establecer un componente refractario
seguiría exigiendo modelos de mezcla, que aquí no se ajustan.

Y queda una **observación sin explicar**, declarada como tal: que el chi² observado sea menor
que el de casi todos los órdenes aleatorios sugiere alguna estructura en el orden que ETKDG
genera. No está caracterizada y no se usa para nada.

## Contraste 3 — y la medición que no se buscaba

El conjunto de los nueve nunca cubiertos es **invariante al orden**, verificado en 200
permutaciones. Es invariante por construcción —depende del conjunto completo de candidatos,
no de en qué orden se miren— y se verifica de todas formas, porque convierte una afirmación
teórica en un hecho comprobado.

Sobre los mismos datos apareció algo que no se buscaba, y que cambia cómo hay que pensar una
política de parada. Con `P(G1) = m/K`, donde `m` es cuántos confórmeros cubren:

| | Complejos |
|---|---:|
| `P(G1) ≥ 0.80` — casi siempre aciertan al primero | 64 |
| `0.20 < P(G1) < 0.80` — zona inestable | **36** |
| `P(G1) ≤ 0.20` | 7 |

> **De los 107 cubiertos, 43 —el 40.2%— pueden cambiar de clase G1↔G2 según el orden.**

G1 y G2 no son propiedades del complejo: son propiedades del **par complejo-orden**. G3 sí es
propiedad del complejo, porque depende del conjunto completo de candidatos generados.

La consecuencia para el diseño de una política de parada es directa, y no se buscaba: **una
política no debe intentar aprender que un complejo *es* G1**, porque no lo es. La pregunta
correcta es secuencial —dado lo observado hasta ahora, ¿cuál es la probabilidad de que más
inicializaciones aporten una cuenca útil nueva?— mientras que G3 plantea otra distinta: ¿hay
señales de que seguir muestreando ataque el mecanismo equivocado?

Son `STOP_SUCCESS` contra `CONTINUE` contra `ABSTAIN/REVIEW_INPUT`: las mismas primitivas a
las que llegó el análisis de coste por otra vía.

## Límites

- **No toca la cobertura de `MF-33-EXT`**, que tampoco depende del orden.
- **No ajusta modelos de mezcla.** Retira una explicación alternativa; no instala la otra.
- La permutación asume intercambiabilidad bajo la nula — que es la hipótesis contrastada, no
  un supuesto del método.
