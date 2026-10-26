---
titulo: "Metales del sitio con Vina: NO_GO en el redocking pareado"
entradilla: "MET-01-R1 repite MET-01 sobre un producto que sí conserva la whitelist y compara conservar y retirar el ion en 28 de 35 entradas coordinadas evaluables, con cinco semillas por brazo. Discordancias: 0 a favor de CON y 3 a favor de SIN; p bilateral = 0.25."
---

**NO_GO.** Mantener retirada y abstención. CON aporta una línea base para un futuro modelo de coordinación (M5).

El catálogo retira los metales que no declara. MET-01-R1 pregunta si conservarlos,
con el Vina que ejecuta MolDesign, mejora la reproducción de la pose de su propio
cristal. El ion no introduce por sí solo un modelo de coordinación: el protocolo
AutoDock4Zn descrito por los autores requiere parámetros, mapas y pseudoátomos
distintos. Aquí se usa Vina del producto. [Documentación de AutoDock](https://autodock-vina.readthedocs.io/en/latest/docking_zinc.html).

## Qué se fijó antes de acoplar

Producto `9ce8b10490fcdd1c21b5dc0cf1efa8f3eae76d70`, Meeko 0.7.1, Vina 1.2.7, PoseBusters 0.6.5 `dock` con
reconstrucción de H MF-33-H-COR. Exhaustividad 8, nueve poses solicitadas, un
conformador y semillas 42–46. El prerregistro es el commit `dfdc9a269343f7993a8d36bc25e361407cf01035`;
el piloto se conserva aparte y la entrada vuelve a medirse.

La población fija son 41 entradas, 52 iones: 35 entradas coordinadas
geométricamente y seis controles. Una entrada es el receptor y la instancia de
`site_ligand` más cercana a su caja. SIN y CON se crean por la API de variantes,
con caja y cadena heredadas. Dos procesos de preparación contrastan sus hashes,
y SIN se contrasta con el receptor del catálogo. Los SMILES estereoquímicos
proceden del CCD, con definición, URL, fecha y SHA-256 archivados; las coordenadas
del conformador no proceden del cristal. [Diccionario wwPDB](https://www.wwpdb.org/data/ccd).

Se reutilizan sin modificar `Backend.evaluar`, `_cristal`, `_neutro_sin_h` y
`_top1` de CAL-8HFI-01. El RMSD es simétrico de átomos pesados, sin alinear.
El gate exacto de CAL exige al menos tres RMSD ≤2 Å y validez de **todas** las
semillas cuyo RMSD cumple. El mejor de las poses devueltas es descriptivo.
Vina puede devolver menos de las nueve solicitadas.

## Potencia y exclusiones

La prueba de signos es exacta, bilateral, α=0,05. Seis discordantes 6:0 bastan
para p=0,03125: 17,1 puntos sobre 35 entradas. Ese límite de significación no es
un efecto detectable con 80 % de potencia. Se declaró como efecto mínimo una
diferencia de 40 puntos, bajo un modelo con 50 % de discordancias: potencia
94.76 % con 35, 82,02 % con 25 y 87.24 % con el n final.
Las diferencias detectables al 80 % con ese modelo son 33,7 puntos con 35 y
39,4 con 25. La tabla sellada incluye otros niveles de discordancia; estas
potencias dependen del modelo y no garantizan detectar efectos moderados.
La probabilidad exacta presupone signos discordantes independientes e
intercambiables bajo la nula. La unidad del encargo es una entrada PDB: varias
comparten diana/familia, lo que puede correlacionarlas. La p no se generaliza
a dianas independientes ni a metaloenzimas en conjunto.

Hubo 9 exclusiones fijadas antes de docking;
7 de las 35 principales quedan fuera al cierre.
Las causas por entrada están en el informe: receptor no preparable, brazo CON
no representable o referencia que el método de CAL no puede casar. No se
sustituye ninguna. Controles evaluables: 4 de 6.
Un n<25 o más del 30 % de exclusiones principales fuerza INCONCLUSIVE.
Antes de docking se cambió el requisito de los seis controles: dos no son
evaluables por preparación/referencia, lo que habría impedido cualquier GO.
Se exige no pérdida en todos los controles evaluables y al menos cuatro de seis
medidos. Con menos de cuatro, una señal favorable queda INCONCLUSIVE. El alcance
se restringe a las entradas evaluables; no se afirma ausencia de daño en las omitidas.

## Qué salió

| Medida | Resultado |
|---|---:|
| Entradas principales pareadas | 28/35 |
| Reproduce sólo CON | 0 |
| Reproduce sólo SIN | 3 |
| Diferencia pareada de tasas | -10.71 puntos |
| p bilateral exacta | 0.25 |
| Controles con pérdida demostrada | 0 |
| Corridas confirmatorias | 380 |
| Fallos de infraestructura | 0 |
| Rechazos del producto | 0 |

## El metal, PoseBusters y la histidina

Antes de Vina se pasó el cristal, con el microestado normal congelado, por
`evaluar_pose_fisica` del producto, con mapa de Meeko y cada receptor preparado.
En 33 entradas se pudo evaluar CON; en 0 falló
algún control de distancia o volumen frente a cofactores inorgánicos
(ninguna). Los restantes fallos del cristal
se conservan con su nombre: no se atribuyen automáticamente al ion.
La batería ofrece controles de cofactores inorgánicos, pero **el producto no
comprueba estos contactos con el metal**: Meeko escribe el ion como `ATOM`;
la máscara inorgánica lo excluye como proteína y la máscara de proteína lo
excluye por su elemento inorgánico. La inspección con las máscaras reales está
archivada (52 átomos metálicos cargados, 0 seleccionados
por la máscara inorgánica y 0 por la de proteína).
Por ello los PASA inorgánicos son vacuos en este caso, no una
validación de coordinación. No se alteró el validador. [API de PoseBusters](https://posebusters.readthedocs.io/en/latest/api.html).

Preparación avisó de His con H en el nitrógeno coordinante en 55/160
corridas CON normales. No se corrigió ninguna durante el experimento.

## Diagnóstico del ligando, fuera del gate

Se fijaron reglas químicas independientes para retirar un protón del N de una
sulfonamida, O de un hidroxamato o S de un tiol que queda a ≤2,8 Å de Zn.
Se conserva el microestado normal en los demás centros. Son hipótesis de anclaje,
no poblaciones de unión validadas. 6 entradas admitieron exactamente
esa forma mediante la opción pública de preparación a pH 7,4, 10 o 12, verificada
en dos procesos: 60 corridas diagnósticas en los dos brazos.
El pH que cambia se declara por entrada; no se interpreta como pH experimental
de unión. Las hipótesis que el producto reprotona o cambia en otros centros
quedan no representables y no se disfrazan de un diagnóstico ejecutado.

## Qué no dice

Este redocking usa la estructura de su propio cristal, un escenario favorable;
no demuestra cross-docking, actividad, afinidad, energía de coordinación,
calibración ni transferencia a FEP. Una distancia corta es geometría, no energía.
Los scores de SIN y CON describen receptores diferentes y no se comparan como
energías de unión. Una falta de significación tampoco prueba equivalencia.

## Consecuencia y reproducción

Mantener retirada y abstención. CON aporta una línea base para un futuro modelo de coordinación (M5). No se cambió el catálogo, M5 ni el producto.

El informe por receptor está en
`docs/auditorias/metales-con-y-sin-ion-R1-2026-10-21.md`. Protocolo, potencia,
CCD, preparados, salida cruda, filas y métricas están en
`scripts/artifacts_science/MET-01-R1-ION-DEL-SITIO/`.
`python scripts/medir_met01r1.py selftest` verifica controles sintéticos;
`python scripts/medir_met01r1.py analyze` reconstruye las métricas sin la sesión.
El MET-01 original (INCONCLUSIVE) está en `docs/papers/MET-01-ION-DEL-SITIO.md`.
El runtime no se distribuye por git y se declara en `sellos_no_distribuidos.json`.
