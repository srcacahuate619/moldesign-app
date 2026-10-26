---
titulo: "VMAT2 (8T69): Vina ordena los Ki publicados, pero el intento es NO_GO por un compuesto que el producto no calculó"
entradilla: "Con 8T69, la pose de la tetrabenazina se reproduce en 5 de 5 semillas y el top-1 de Vina correlaciona con 88 Ki publicados de una patente (ρ = 0,39, IC 95 % 0,22–0,54), también en la peor asignación de lotes (ρ = 0,32, IC 95 % 0,14–0,47). La regla registrada exigía los 89 compuestos y uno, con un biciclopentano, no terminó: NO_GO formal."
---

**NO_GO formal. La señal es positiva; el fallo es del cálculo de un compuesto.** 8T69 sigue en Demostración.

Este es el cuarto intento de decidir CAL-D-01 (1IAS, 8WRE y 8T69 antes de esta regla), no una réplica
independiente ni un holdout. La regla se escribió después de leer los Ki y el resultado de la ronda anterior,
y antes de ver ningún score de Vina de este panel ni de este receptor.

## Qué se preguntó

Si, con el receptor 8T69 del catálogo (VMAT2 humano con tetrabenazina, cadena A, receta 7), Vina 1.2.7 y
Q = −E(top-1), (1) se reproduce la pose del ligando del cristal y (2) el orden de Q coincide con el de los Ki
publicados de las tablas 15A/15B de la patente US11718618B2 (ejemplo 11, plaquetas humanas, [³H]DTBZ).

El problema de ese panel es que los Ki se normalizaron con una Kd del radioligando que cambia por lote
(2,5 o 4,06 nM) y la patente no dice qué lote corresponde a cada compuesto. Por eso el criterio no es sólo ρ:
se calcula también **ρ de peor caso**, el mínimo de Spearman sobre todas las asignaciones binarias de lote con
F = 1015/703, y el éxito exige que el límite inferior del IC 95 % de las dos sea mayor que cero.

## Qué se fijó antes de acoplar

Registro previo `0a1a4aed…` (6948 bytes) y panel de 89 padres `ff5e0c69…`, con el producto en `6f3ff1b5`.
Exhaustividad 8, nueve poses, un conformador, 4 CPU por proceso, semilla 42 en el panel y 42–46 en el
redocking. Microestados congelados en dos procesos distintos; receptor preparado `8fc027ca…` reproducible y
comprobado en cada cápsula. IC por bootstrap percentil pareado por padre, 10 000 réplicas, semilla 20261021.
La ρ de peor caso se calcula de forma exacta (programación dinámica) y se validó contra la enumeración de todas
las asignaciones en 80 casos pequeños, con empates, copias de bootstrap y valores junto al umbral.

## Qué se midió

| | Resultado |
|---|---|
| Pose del cristal (tetrabenazina) | 5 de 5 semillas, RMSD 0,67–0,71 Å, todas válidas en PoseBusters |
| Compuestos acoplados | 88 de 89 |
| ρ de Spearman (Q frente a pKi) | **0,391**, IC 95 % [0,219; 0,537] |
| ρ de peor caso (peor asignación de lotes) | **0,320**, IC 95 % [0,139; 0,473] |
| Concordancia de pares con cociente de Ki > F | 0,637 (3505 pares), IC 95 % [0,576; 0,694] |
| Sensibilidad con 4-31, con 4-118 o con la mediana de ambos | ρ 0,37–0,39 y ρ de peor caso 0,30–0,32 |

## Por qué es NO_GO

El compuesto **4-67** lleva un biciclo[1.1.1]pentano. Su docking termina (ocho poses), pero el análisis posterior del
pipeline no acaba y el producto lo corta a los 1200 s, en los dos intentos. La regla registrada decía GO sólo
con cero fallos persistentes. Es una decisión formal por un fallo del producto, no un resultado en contra de la
correlación. Quedan 88 padres evaluados, por encima del mínimo de 85.

Durante la campaña ocurrieron tres cosas que no cambiaron ningún umbral ni entrada y están en
`DESVIACIONES.md`: un intento de 4-67 interrumpido a mano, los hilos de los intentos agotados que siguieron
calculando y frenaron los compuestos siguientes (se reinició ese proceso), y un error del análisis, corregido
después de congelar, que calculaba el RMSD de los compuestos del panel contra el cristal.

## Qué no dice

Ordenar los Ki publicados de esta tabla no demuestra comparabilidad entre lotes, afinidad absoluta ni
generalización a otra serie o diana. La sensibilidad a F no cubre el resto de la variabilidad experimental (el
duplicado 4-31/4-118 difiere unas ocho veces). Los 88 padres comparten el núcleo de benzo[a]quinolizidina de la tetrabenazina: la ρ describe cómo ordena análogos de esa serie, no ligandos de estructura diversa. La estructura es
un cryo-EM de 2,89 Å del estado ocluido por tetrabenazina, no del conjunto de la población de membranas de
plaqueta. Se desconoce el score de 4-67.

## Consecuencia y reproducción

Ningún receptor cambia. Se publica como intento, igual que CAL-8HFI-01. El reanálisis sin 4-67, escrito después
de ver estos números, es `CAL-D-01-R4B-VMAT2-8T69` y no es confirmatorio.

Registro, protocolo, panel, crudos, métricas y desviaciones están en
`scripts/artifacts_science/CAL-D-01-R4-VMAT2-8T69/`; el estadístico y el arnés, en `scripts/cal_d01r4/`. La
prueba del estadístico es `backend/tests/test_cal_d01r4_rho_peor.py`.
