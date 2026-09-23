---
titulo: "El radio de Bondi empeora la hidratación del bromo y del yodo"
entradilla: "Contra 37 moléculas de FreeSolv, cambiar el radio GB de Br e I por el de Bondi sube el error de 1,93 a 2,05 kcal/mol. El radio se queda en 1,5 Å, y el análisis posterior apunta a otro sitio: el flúor y la dispersión."
---

En GBn2, el bromo y el yodo reciben un radio de 1,5 Å: no porque alguien lo
eligiera para ellos, sino porque es el valor por defecto para elementos sin
parámetro. La hipótesis era que un radio físico, el de Bondi (1,85 y 1,98 Å),
acertaría mejor la energía libre de hidratación.

## Qué se midió

Las 642 moléculas neutras de FreeSolv v0.52 (Mobley y Guthrie, 2014; datos CC
BY 4.0), con un solo confórmero y sin minimizar: una estimación estática, no una
energía libre con muestreo. Polar: GBn2 con las correcciones de Amber de
`MMGBSA-H13`. No polar: γ·SASA + b, ajustado **sólo con las 467 moléculas sin
halógeno**, para que ningún radio de Br o I pudiera compensar un sesgo del
término no polar. Nada se ajusta en Br ni en I.

## Qué salió

**NO_GO. El radio de Bondi empeora el acierto.**

| | 1,5 Å | Bondi |
|---|---:|---:|
| Br e I (37) | 1,93 | 2,05 kcal/mol |
| Br (21) | 1,67 | 1,80 |
| I (12) | 1,13 | 1,27 |

El intervalo bootstrap de la diferencia es [−0,01; +0,25] y Bondi mejora 8 de
37 moléculas. Con 1,5 Å el bromo ya sale **infrasolvatado** —sesgo +1,57
kcal/mol—, y un radio mayor lo empeora. Repetido con PB en lugar de GB, Bondi
tampoco mejora: el resultado no es un artefacto de la aproximación GB.

## La medida que hubo que repetir

La primera corrida perdió justo las 37 moléculas que decidían: `pbsa` corta los
nombres de archivo a 80 caracteres y la ruta del brazo de Bondi medía 81. Se
corrigió, se declaró antes de repetir y se repitió sólo la medida: las 605
moléculas que ya habían salido dan valores idénticos bit a bit.

## Lo que apareció después, sin decidir nada

El análisis posterior al gate —exploratorio y declarado como tal— encontró dos
patrones más grandes que el del radio:

- **GBn2 sobresolvata los grupos polifluorados** frente a PB con los mismos
  radios: con uno o dos F coinciden; con un CF₃, −2,3 kcal/mol de media; con
  cuatro o más F, −7,7.
- **Las moléculas con cuatro o más cloros** quedan +5,9 kcal/mol por encima del
  experimento sin que PB lo explique, lo que apunta a un término no polar sin
  dispersión atractiva.

Son hipótesis nuevas. Ninguna se ha prerregistrado todavía, y ninguna se
arregla con un número de la literatura: la bibliografía revisada no ofrece un
radio ni un apantallamiento de flúor validados para GBn2.
