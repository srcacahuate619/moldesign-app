---
titulo: "Donde el paisaje coopera, Vina es casi determinista; donde no, tira los dados"
entradilla: "La desviación por semilla es 0.011 Å en los complejos fáciles y 0.283 Å en los difíciles. Los efectos agregados del programa sobreviven al ruido; las afirmaciones por complejo no."
---

Todo el programa mide efectos de entre 0.5 y 1 ángstrom. Ninguno de esos efectos significa
nada si el propio motor de docking, ejecutado dos veces con semillas distintas sobre el
mismo complejo, ya varía en ese orden.

Este experimento era prioridad máxima desde el primer día y estuvo sin ejecutar durante
meses. Fue una **auditoría adversarial contra el propio programa** la que lo identificó
como el hueco más grave: nada de lo publicado estaba controlado contra el ruido de la
semilla.

## Qué pasó

| Estrato | Desviación típica mediana |
|---|---:|
| Control (complejos fáciles) | **0.011 Å** |
| Colocación (complejos difíciles) | **0.283 Å** |

Veinticinco veces más ruido en el estrato difícil. Ese contraste es, por sí solo, el
hallazgo más interesante del experimento:

> Donde el paisaje de puntuación coopera, Vina es casi determinista. Donde no coopera,
> tira los dados.

## Los efectos del programa sobreviven

El error estándar de la mediana sobre 33 complejos es **0.049 Å**. Los efectos que el
programa ha medido:

| Experimento | Efecto | Veces el error estándar |
|---|---:|---:|
| Geometría de la caja | −0.82 Å | 16.7× |
| Reinicios de búsqueda | −0.79 Å | 16.1× |
| Presupuesto de búsqueda | −0.784 Å | 16.0× |

Todos alrededor de **16 veces** el ruido. A nivel agregado, sobreviven al control con
holgura. Nada de lo publicado se cae por esto.

## Pero la distribución es muy asimétrica, y ahí está el problema

La mediana de 0.283 Å oculta una cola larga:

| | Valor |
|---|---:|
| Percentil 75 | 0.962 Å |
| Percentil 90 | **1.422 Å** |
| Rango máximo | **4.022 Å** |
| Complejos con sd > 0.5 Å | 14 de 33 |

Cuatro ángstroms de rango en un mismo complejo, sólo por cambiar la semilla. Eso es más que
el umbral de éxito entero.

## Dos consecuencias de signo opuesto

**(a) Las conclusiones binarias son estables.** Ningún complejo cambia su veredicto de
acierto o fallo entre semillas. Afirmaciones como «3 de 33» o «cero conversiones» no son
artefactos de la semilla 42 — son reproducibles.

**(b) Las afirmaciones por complejo individual no son fiables.** Con rangos de hasta 4 Å,
decir algo sobre un complejo concreto a partir de una sola corrida es decir algo sobre esa
corrida, no sobre el complejo.

Esa segunda consecuencia tiene una implicación directa de producto: la confianza por
complejo que mide `FEP-04` está calculada sobre una sola ejecución. Para ser honesta,
**tendría que incorporar repeticiones**. Es una tarea abierta, y está anotada como tal en
el propio registro de `FEP-04`.

## Por qué importa que lo pidiera un ataque

Este experimento existe porque un ejercicio deliberado de buscarle los fallos al programa
encontró que su resultado más básico —«el baseline es estable»— nunca se había medido.

Es la diferencia entre un programa que se audita a sí mismo y uno que confía en que sus
cimientos están bien porque nadie ha mirado.
