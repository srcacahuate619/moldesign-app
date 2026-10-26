---
titulo: "El LCPO del cloro no sirve para el yodo"
entradilla: "Con los coeficientes publicados para el Cl y el radio de Bondi, el área del yodo sale sistemáticamente corta, y más cuanto mayor es el radio. El bromo roza el aprobado; el yodo no se acerca."
---

El término no polar de MM-GBSA necesita el área accesible al disolvente de cada
átomo. OpenMM la aproxima con LCPO, una fórmula analítica con cuatro
coeficientes por tipo de átomo, y **no trae coeficientes para Br ni para I**. La
salida más barata era usar los del cloro (Weiser, Shenkin y Still, 1999) con el
radio de Bondi de cada halógeno, sin ajustar nada.

## Qué se midió

Error por átomo frente a la SASA numéricamente exacta, en 121 ligandos de
PDBBind con Br o I repartidos por scaffold (60/20/20, sellado antes de medir).
Por elemento y partición: mediana ≤ 2,81 Å², p90 ≤ 7,25 Å², un intervalo
bootstrap del sesgo dentro de ±2,81 Å², y que los átomos vecinos no empeoren
respecto del respaldo que usa Amber.

## Qué salió

**Los cuatro casos fallan.**

| | mediana | p90 | IC95 del sesgo |
|---|---:|---:|---|
| Br, validación | 0,70 | 6,90 | [−3,14; −0,40] |
| Br, prueba | 3,40 | 9,44 | [−3,03; +3,35] |
| I, validación | 4,71 | 6,49 | [−5,82; −1,32] |
| I, prueba | 4,57 | 5,36 | [−4,81; −1,33] |

En el yodo el error es **sistemático, negativo y crece con el radio**: con un
radio de 1,8 Å el error baja en las tres particiones. Es la refutación que el
documento de hipótesis anticipaba: la forma funcional del cloro no escala con
el tamaño del átomo.

Lo que sí pasa: los átomos vecinos mejoran entre 0,20 y 0,23 Å² respecto del
respaldo de Amber, que usa para Cl, Br e I los coeficientes de un carbono y
falla por 24-31 Å².

## Lo que apareció de paso

4 de 121 ligandos no se pudieron medir, y ninguno por el halógeno. Tres
contienen un **=CH₂ vinílico terminal**, para el que OpenMM 8.5.2 no tiene
parámetro LCPO: el MM-GBSA candidato tampoco puntuaría un alqueno terminal. El
cuarto es un alquino terminal al que el SDF de PDBBind le quitó el hidrógeno.

## MMGBSA-PARTICIONES-BRI-V1: la asignación del material precede al ensayo de áreas

**GO de asignación de material.** Documenta la población de partida; no cambia los casos medidos de H1 ni valida parámetros físicos.

Se separaron grupos de scaffold; para acíclicos se usó InChIKey. Se ordenó por hash de semilla y grupo y se asignó por déficit relativo de partición, distinguiendo Br e I. La semilla fue 20260923, bajo RDKit 2025.09.6.

| Partición de material | Ligandos | Grupos |
|---|---:|---:|
| Entrenamiento | 72 | 46 |
| Validación | 24 | 18 |
| Prueba | 26 | 19 |

La lista marca `5mlj` por geometría imposible: asignación y universo finalmente medido por H1 no son el mismo denominador. Tampoco es la cohorte de paridad de H5. La reproducibilidad declarada del reparto no mide calidad de LCPO ni independencia química más allá de la agrupación usada. No comprobado por mí: reproducir curación o asignación desde SDF originales. Fuente: `MMGBSA-PARTICIONES-BRI-V1`.
