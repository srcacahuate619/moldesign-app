---
titulo: "¿Basta la exhaustividad 8? En 8T69, subirla a 32 no cambia la pose y mueve el orden menos de lo que se pudo resolver"
entradilla: "MolDesign acopla con la exhaustividad 8 que trae Vina por defecto, y un texto la llamaba «sweet spot validado» sin medida. Con la serie de 89 Ki de VMAT2, 32 no reproduce mejor la pose y ordena +0,04 mejor, un cambio del tamaño del que produce la semilla."
---

**INCONCLUSIVE.** No se demostró que la exhaustividad 8 ordene peor que la 32, ni que ordene igual.

## Qué se midió

Se acopló la misma serie de 8T69 (VMAT2) con la que el receptor entró en Verificados: 89 padres con Ki de la patente US11718618B2.
Hubo cuatro brazos con el arnés sellado de CAL-D-01-R4:
- exhaustividad 8, 16 y 32 con la semilla 42;
- exhaustividad 8 con la semilla 43, para medir el ruido de la semilla.

Además, cinco redockings de la tetrabenazina del cristal en los tres primeros. El registro previo se commiteó antes de acoplar.
- **GO** si el IC 95 % de Δρ(32 − 8) cabía entero en ±0,10.
- **NO_GO** si excluía el cero por encima, o si 8 reproducía peor la pose.

## Qué pasó

| Exhaustividad | Semilla | ρ (89 padres) | Redocking a ≤ 2 Å | CPU-core-h |
|---:|---:|---:|---:|---:|
| 8 | 42 | 0,392 | 5/5 | 3,70 |
| 8 | 43 | 0,367 | — | 3,42 |
| 16 | 42 | 0,428 | 5/5 | 5,56 |
| 32 | 42 | 0,435 | 5/5 | 9,78 |

- **Δρ(32 − 8) = +0,043**, IC 95 % −0,006 a +0,116. Cruza el cero y sale del margen por 0,016.
- Cambiar sólo la semilla mueve ρ −0,025, IC 95 % −0,135 a +0,078.
- La energía top-1 apenas cambia: 85 de 89 padres quedan a menos de 0,1 kcal/mol. La ρ entre las energías a 8 y a 32 es 0,968.
- La pose del cristal sale igual con las tres exhaustividades: RMSD de 0,67 a 0,72 Å.
- **Control:** el brazo a 8 repite las 89 energías del sello de 8T69 sin ninguna diferencia.

## Qué dice y qué no dice

- **La búsqueda a 8 ya converge en esta serie.** La ρ se mueve por reordenaciones pequeñas entre análogos de energía casi igual.
  Una semilla distinta produce cambios del mismo orden.
- **El sello de 8T69 no cambia.** Describe corridas a exhaustividad 8 con semilla 42, y aquí se repite exacto.
- **No valida el «sweet spot»**, que ya se había retirado del producto. El valor por defecto sigue siendo el de Vina, con esta
  medida como condición.
- **Un receptor, una serie y una caja de 30 Å.** No dice nada de cajas mayores, donde el producto ya sube a 32, ni de otros
  receptores o ligandos más flexibles.
- **Una sola semilla por brazo.** Saber si +0,04 es efecto o ruido pide varias semillas por brazo, y eso ya no sería ciego.
