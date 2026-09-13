---
titulo: "La cobertura sube 26.7 puntos y al top-1 llegan 11.2"
entradilla: "De los 31 complejos ganados a nivel de oráculo sobreviven 18 al top-5 y 13 al top-1. La fracción de lo cubierto que se realiza en top-1 baja del 62.9% al 53.0%: el siguiente cuello es la selección."
---

> ## ⚠ Defecto detectado después de sellar, corregido en otro registro
>
> **Las tasas de validez física de este artefacto —8.62% en single y 15.52% en ensemble—
> están invalidadas y reemplazadas.** No medían tensión del ligando dockeado: medían un
> defecto de la capa que **reconstruía los hidrógenos** antes de pasar la pose a PoseBusters.
>
> [`MF-33-H-COR`](#) lo midió con los átomos pesados idénticos —desplazamiento máximo 0.0 Å,
> mismo SMILES canónico, misma carga, mismos enlaces— y las 232 poses top-1 de este
> experimento pasan de **12.07% a 93.10%**: 91.38% en single y 94.83% en ensemble.
>
> **Todo lo demás de esta ficha sigue en pie sin reservas**: RMSD, cobertura del oráculo,
> top-1, top-5 y la cascada de conversión no dependen de los hidrógenos. Este artefacto queda
> sellado e inmutable con sus cifras originales, y el corrigendum que las reemplaza queda
> nombrado al lado.

`MF-33` midió que el ensemble de confórmeros sube la **cobertura del oráculo**. El oráculo es
el mejor RMSD entre las poses que el brazo conserva: dice qué hay disponible, no qué se
entrega.

Lo que el investigador recibe es el **top-1 por score**. Y `MF-09` había medido, en el
estrato difícil, que el top-1 acierta 0 de 33 y el top-20 llega a 2. Con esa distancia entre
lo disponible y lo entregado, subir el techo podría no mover nada.

Este experimento mide si el mecanismo llega hasta abajo. Sin cómputo de docking: los
`conf<i>.out.pdbqt` del protocolo congelado están en disco para los 116 de entrenamiento, con
sus scores y sus nueve modelos por corrida. Dos brazos pareados: **SINGLE** con las 9 poses
de `conf0.out`, **ENSEMBLE** con las K×9 de todos.

## Qué salió

McNemar exacto pareado sobre «acierta ≤2 Å», por separado en las tres métricas:

| Sobre los 116 | Single | Ensemble | Δ | b / c | p |
|---|---:|---:|---:|---:|---:|
| **Oráculo** | 35 | **66** | +26.72 pp | 31 / 0 | 0.0 |
| **Top-5** | 35 | **53** | +15.52 pp | 20 / 2 | 0.000121 |
| **Top-1** | 22 | **35** | +11.21 pp | 13 / 0 | 0.000244 |

Las tres mejoran con significación. Y las tres mejoran **cada vez menos**.

De los **+31** complejos ganados a nivel de oráculo, sobreviven **18** al top-5 —el 58% de la
ganancia— y **13** al top-1 —el 42%—.

## La atenuación es el resultado

El gate preregistrado da la etiqueta `LA_VENTAJA_LLEGA_AL_USUARIO`, y esa etiqueta se
conserva porque se escribió antes de mirar. **Pero no debe usarse como titular**: como
afirmación científica sobrepasa lo medido.

La formulación publicable es ésta, y es la que hay que usar:

> Aunque el muestreo por ensemble aumentó la cobertura del oráculo, la fracción de complejos
> cubiertos que se realiza en top-1 bajó del **62.9%** al **53.0%**, ampliando el hueco
> oráculo-a-top-1 de **13** a **31** complejos.

Los cuatro números son el hecho observado. Están **relacionados matemáticamente** y la
causalidad **no** está demostrada. La interpretación va aparte y en condicional: *aumentar la
cobertura de candidatos parece imponer una carga mayor sobre la selección de pose*.

**Una sutileza que un revisor señalaría, y hay que anticipar.** Ese 53.0% **no** significa
que el selector sea peor. El selector del brazo ensemble se enfrenta a un **problema
distinto** —un espacio de candidatos mucho mayor y potencialmente con más cuencas
competitivas—, así que la caída de 62.9% a 53.0% no demuestra por sí sola que el algoritmo de
ranking se haya degradado intrínsecamente.

Lo que sí demuestra, y basta para identificar la selección como el siguiente cuello:

> La capacidad del pipeline de convertir cobertura disponible en top-1 **no escala
> proporcionalmente** con el aumento de cobertura.

*(Enmienda del 2026-08-21: la versión anterior de esta lectura decía que mejorar la
generación agrava el cuello de selección **porque** el oráculo sube más rápido que la
capacidad de elegir. Eso afirmaba una causalidad que estos datos no establecen, y se
retiró.)*

## En el estrato difícil no hay señal, y era previsible

| COLOCACION (n=33) | Single | Ensemble |
|---|---:|---:|
| Top-1, top-5 y oráculo | 0 | 0 |

Cero en los tres campos para los dos brazos. No es un resultado nulo interesante: el
protocolo **rígido** tiene techo de 1 de 33 en el estrato difícil, según el brazo C de
`MF-33`. Aquí no hay nada que atenuar porque no hay nada que propagar.

## La limitación central, declarada en el gate

**Estas poses son del protocolo rígido.** Las flexibles del brazo B de `MF-33` no existen: el
runner las escribió en un `TemporaryDirectory`.

Así que esto **no mide el brazo del paper**. Mide si el **mecanismo** llega al selector en el
único protocolo cuyas poses sobrevivieron. Contestar la misma pregunta sobre el brazo
flexible exigió volver a dockear, y para eso se selló `MF-33-B-RET`.

Otros límites: se ordena por score de Vina **sin rescoring** —la cartera RS mide eso aparte—;
SINGLE usa `conf0` por índice y no por calidad, como el brazo A de `MF-33`; y el ensemble
selecciona sobre un pool K veces mayor, que **es el fenómeno** y no un confundido.

## Qué cierra y qué deja expuesto

**Cierra** la amenaza T1 del paper a nivel de mecanismo: el efecto no vive exclusivamente en
una métrica de oráculo, llega a lo que se entrega.

**Deja expuestos** dos cuellos posteriores que estaban ocultos detrás del de generación:

1. **Selección** — 31 complejos que contienen una solución correcta y no la entregan en
   top-1, nominalmente identificados en `per_complex.jsonl`.
2. **Validez física** — que aquí se midió mal y se corrigió después. Con las tasas
   corregidas de `MF-33-H-COR` el cuello no es el que este artefacto creyó ver, y el residuo
   real está caracterizado allí.

La razón por la que la validez física entró en este diseño sigue siendo buena aunque su
medición fallara: **un selector que pase de 35 a 55 entregando poses inválidas no habría
mejorado el producto.** Optimizar una métrica intermedia sin mirar la física es la forma
estándar de mejorar un número y empeorar el resultado.
