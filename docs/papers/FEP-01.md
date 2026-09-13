---
titulo: "El cuello es el tautómero, y nadie lo había contado"
entradilla: "Sólo 39 de 203 complejos pasan la auditoría química. Pero el estéreo está impecable —0 sin asignar— y el cuello real es que 164 ligandos tienen tautómero ambiguo y el pipeline no declara cuál usa."
---

Los métodos de energía libre son el patrón de oro para predecir afinidad, y son
implacables con la calidad de la entrada: si el ligando entra con la química mal
especificada, el cálculo produce un número preciso y equivocado.

Esta auditoría cuenta cuántos de los 203 complejos del programa tendrían **declarada** su
química: estereoquímica, tautómero, protonación, carga y correspondencia de átomos. No si
son correctos —eso exige juicio experto caso por caso— sino si están **declarados** en vez
de dejados al azar de la implementación.

## El resultado global

**39 de 203 (19%)** pasan hoy los cuatro campos.

Es un número bajo, y la parte interesante es cómo se reparte.

## Dos sospechas de partida que resultaron infundadas

**La estereoquímica está limpia.** 138 ligandos tienen centros quirales y **cero** están sin
asignar.

Eso contradice directamente lo que sugería el código: el pipeline llama a la función de
conversión con la opción de *permitir estéreo indefinido* activada. Esa bandera hace saltar
la alarma de cualquiera que la lea, porque permite pasar moléculas cuya quiralidad no está
determinada — y la quiralidad decide si una molécula se une o no.

La bandera permite algo que en la práctica **no ocurre nunca**. El riesgo estaba, la
realización no. Sin contar, la conclusión razonable habría sido la contraria.

**La correspondencia de átomos es biyectiva** y cubre los átomos pesados en los 203
complejos. Eso importa más allá de esta auditoría: es la base sobre la que se calculan
**todos los RMSD del programa**, y hasta aquí nunca se había verificado. Si esa
correspondencia estuviera rota en algún complejo, sus distancias medidas compararían átomos
distintos.

## El cuello real

**164 de 203 (81%)** tienen más de un tautómero enumerable, y **48** alcanzan el tope de 10
que se permitió a la enumeración.

El pipeline **no declara cuál usa**.

Para docking con Vina eso apenas importa: la función de puntuación es lo bastante tosca
como para que la diferencia se pierda en el ruido. Para energía libre es **determinante**,
porque el tautómero define exactamente qué átomos donan puentes de hidrógeno y cuáles los
aceptan — que es la interacción que domina el reconocimiento molecular.

Es un problema silencioso: nunca produce un error, sólo un resultado calculado sobre una
molécula que puede no ser la que existe en solución.

## La limitación, declarada

La enumeración usada es una heurística de transformaciones químicas, no un cálculo de
poblaciones. Que un ligando tenga más de un tautómero enumerable **no significa que esté
mal**: significa que hay una **ambigüedad no declarada**.

La distinción importa porque marca qué trabajo hay que hacer. No es corregir 164 moléculas
— es declarar, para cada una, cuál se usa y por qué.

## Por qué esta auditoría era la que faltaba

El proyecto llevaba tiempo asumiendo que estar listo para energía libre era cuestión de
formato de exportación. Esta auditoría dice que el formato es lo de menos: el trabajo real
está en decidir y documentar química que hoy se decide sola, dentro de una biblioteca, sin
que nadie registre qué eligió.

Es el elemento con más apalancamiento de la cartera: declarar tautómeros sube este 19% por
encima del 80% de un solo golpe.
