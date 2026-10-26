---
titulo: "VMAT2 (8T69) sin el compuesto 4-67: el criterio se cumple, pero se enmendó tras ver los scores"
entradilla: "Reanálisis de CAL-D-01-R4 sin el compuesto que el producto no calculó. Con 88 padres, ρ = 0,39 (IC 95 % 0,22–0,54) y ρ de peor caso = 0,32 (IC 95 % 0,14–0,47): el criterio enmendado se cumple, pero la enmienda se redactó después de ver los scores y no confirma nada."
---

**INCONCLUSIVE por construcción.** El criterio enmendado se cumple; eso no basta, porque se enmendó después de ver los datos.
No acopla nada y no promociona 8T69.

## Qué es

`CAL-D-01-R4-VMAT2-8T69` terminó NO_GO formal porque su registro exigía cero fallos persistentes y el compuesto
4-67 (biciclo[1.1.1]pentano) no completó el pipeline del producto (1200 s, dos intentos). Los 88 scores, la puerta
de pose (5 de 5) y los números ya existían cuando se escribió esta enmienda. R4B los reanaliza con **una sola**
enmienda:

> Un fallo persistente **del producto** en un compuesto concreto, declarado con su identificador y su causa, no
> impide el criterio si quedan al menos 85 padres evaluados. El compuesto se publica como excluido.

Todo lo demás es el registro previo `0a1a4aed…` sin cambios.

## Resultado

| | Valor |
|---|---|
| Padres evaluados | 88 (excluido 4-67) |
| ρ de Spearman | 0,391, IC 95 % [0,219; 0,537] |
| ρ de peor caso (lotes) | 0,320, IC 95 % [0,139; 0,473] |
| Concordancia de pares con cociente de Ki > F | 0,637, IC 95 % [0,576; 0,694] |
| Criterio enmendado | cumplido (los dos límites inferiores > 0) |

Los números coinciden exactamente con los de R4: el reanálisis lo comprueba antes de escribirlos.

## Por qué no es un GO

Una regla que se cambia después de ver el resultado y luego lo cumple no demuestra nada que la regla original no
hubiera mostrado. Esto es el quinto paso de la misma decisión (1IAS, 8WRE, 8T69, regla nueva R4, R4B), con un solo
resultado computacional, y por eso la decisión registrada es INCONCLUSIVE aunque el criterio se cumpla.
Cambiarla a GO no promocionaría nada: el catálogo exige un protocolo sellado antes de acoplar.

## Qué haría falta para promocionar 8T69

Un protocolo confirmatorio nuevo, escrito antes de acoplar, que ya contemple los compuestos que el producto no
calcula (4-67 y su biciclopentano); que el catálogo, el dossier y Preparación puedan llevar la ρ de peor caso y la
condición de lote; y, idealmente, los Ki por compuesto con su lote o una prueba de comparabilidad.

## Qué no dice

Lo mismo que R4: no hay comparabilidad entre lotes, afinidad absoluta ni generalización, y se desconoce qué habría
dado 4-67.

Datos y reproducción en `scripts/artifacts_science/CAL-D-01-R4B-VMAT2-8T69/` y `scripts/cal_d01r4/reanalisis_r4b.py`.
