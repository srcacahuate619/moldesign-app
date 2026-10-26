---
titulo: "INCONCLUSIVE: quitar todas las aguas no demuestra una diferencia en el oráculo"
entradilla: "CON cubre 94 y SIN 96 de 116 complejos; McNemar bilateral p = 0,814529. La intervención conserva INCONCLUSIVE. REC-11-CRUCES queda GO descriptivo post-hoc y no cambia esa salida."
---

**INCONCLUSIVE en REC-11. GO descriptivo post-hoc en REC-11-CRUCES.** La intervención no confirma equivalencia ni una política óptima. El cruce no habilita un cambio de producto.

## Por qué se hizo

REC-09 puntúa una pose conocida. Para docking de novo no se conoce esa pose y no puede usarse para decidir qué agua estorba. Aquí se comparó conservar todas las aguas con retirarlas todas, manteniendo fijo el ligando de entrada.

## Qué se midió

Se usó `conf0.flex.pdbqt` en ambos brazos, caja de 25 Å, exhaustividad 8, hasta 9 modos por corrida y semillas [42, 1, 2, 3, 4]. CON conserva el receptor experimental; SIN retira los registros de agua. El primario es cobertura del oráculo entre las poses de esas corridas, con RMSD de bolsillo sin alinear ≤ 2 Å. No es la cobertura alcanzable con todos los confórmeros.

La regla compara discordancias por McNemar exacto bilateral. Una p ≥ 0,05 conduce a SIN_DIFERENCIA_DETECTABLE. El manifiesto no fija las versiones del helper y los paquetes del contenedor ni el binario; no se atribuye a ellos el entorno actual.

## Qué pasó

Todos los conteos siguientes corresponden a la intervención sobre los 116 complejos evaluados:

| Cantidad | Resultado |
|---|---:|
| Cobertura CON, oráculo | 94; fracción 0,8103 |
| Cobertura SIN, oráculo | 96; fracción 0,8276 |
| SIN cubre y CON no | 10 |
| CON cubre y SIN no | 8 |
| McNemar exacto bilateral, primario | 0,814529 |
| Discordancia observada | 0,1552 |
| MDE calculado con esa discordancia | 9,92 puntos porcentuales |

El MDE es planificación bajo supuestos de significación y potencia del productor. No es una resolución absoluta ni un intervalo del efecto observado. El agregado conservado no ofrece un intervalo del efecto pareado; aquí no se calcula uno nuevo.

El secundario top-1 elige la pose de mejor score entre las semillas: cubre 59 con aguas y 50 sin ellas, con p archivada 0,162756. Es descriptivo y no rescata ni cambia el primario.

## REC-11-CRUCES: GO descriptivo, después de ver la tabla

La tabla se inspeccionó antes de escribir el registro. Este cruce reutiliza las mismas mediciones y no es una réplica independiente.

| Grupo del criterio de REC-09 | Gana SIN en REC-11 | Miembros |
|---|---:|---:|
| Con algún registro bloqueante | 5 | 26 |
| Sin registros bloqueantes | 5 | 90 |

Entre los 10 casos que gana SIN, 5 no tenían bloqueantes según el criterio cristalográfico. Esto acota el alcance de ese criterio en las unidades observadas y motiva otra hipótesis. No demuestra cuál es la política correcta. Los p-valores del cruce no se usan aquí como argumento confirmatorio, tal como prohíbe su registro.

## Qué dice y qué no dice

La intervención no detecta una diferencia con esta configuración y este tamaño. No demuestra equivalencia, ausencia de efecto ni que conservar todas sea correcto. Retirar todas tampoco es la única alternativa: no se evaluaron políticas intermedias. Se mantiene la decisión operativa histórica, sin confundirla con las rutas actuales del producto.

## Correcciones

**Vigentes al 2026-10-22.**

- **SCI-B-154:** se retiran «no resoluble» y «límite de resolución medido». Un efecto menor que el MDE puede dar un resultado significativo sin alcanzar la potencia objetivo. El valor archivado no convierte este INCONCLUSIVE en equivalencia.

Detalle: `docs/102_FASE_1B_CORRECCIONES.md`; estado en `docs/100_CORRECCIONES_AUDITORIA_CIENCIA_20261015.md`. No comprobado por mí: reconstrucción física de los brazos ni recálculo de McNemar, MDE o Fisher. Se leyeron las tablas conservadas y sus productores, sin ejecutar los experimentos.
