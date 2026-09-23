---
titulo: "OpenMM y sander coinciden con Br e I; con azufre, no"
entradilla: "23 de 24 topologías con bromo o yodo reproducen a sander en GBn2 hasta la sexta cifra. La que falla trae un hidrógeno imposible en el SDF, y de paso apareció un desacuerdo de hasta 11 kcal/mol en cualquier Met o Cys."
---

Antes de ajustar un solo parámetro de bromo o de yodo en MM-GBSA hay que saber
que el programa calcula lo que dice. Si OpenMM y sander (Amber) dieran energías
distintas con la misma topología y las mismas coordenadas, cualquier error
posterior se podría deber a la implementación y no a la física.

## Qué se midió

24 topologías de PDBBind con Br o I, y 31 de control con F o Cl, evaluadas con
OpenMM 8.5.2 (plataforma Reference, doble precisión) y con sander, en vacío y en
GBn2 sin término de superficie. Tope: residuo de energía < 0,001 kcal/mol y
error de fuerza < 0,001 kcal/mol/Å tras convertir constantes.

## Qué salió

**NO_GO por la letra del gate: 23 de 24.**

- **19 pasan directamente**, con residuos ≤ 2·10⁻⁶ kcal/mol.
- **4 llevan azufre** y fallan sólo en GBn2. Las cuatro recuperan la paridad
  cuando el S se trata como elemento genérico en los dos programas: el
  desacuerdo es del azufre, no del halógeno.
- **5mlj falla ya en vacío** (3,88 kcal/mol), y no por el bromo: el SDF de
  PDBBind pone un hidrógeno a 0,26 Å de un carbono, con un ángulo de 1,2°. El
  gate no preveía esa excepción y no se cambió después de medir; se repitió
  como réplica con un filtro declarado antes (`MMGBSA-H5-R1`, GO 23/23).

El OpenMM del Python que se entrega en Windows reproduce al de Linux en 110 de
110 comparaciones (8,5·10⁻¹⁴ kcal/mol).

## El hallazgo que no se buscaba

El desacuerdo del azufre en GBn2 llega a **11,24 kcal/mol** (2weg) y a 4,87 con
dos azufres (5eij). No es un problema de los ligandos: afecta a cualquier
metionina o cisteína del receptor. Se resolvió después en `MMGBSA-H13-AZUFRE-AMBER`.

## Lo que no demuestra

Que los parámetros sean buenos. Coincidir con sander prueba que los dos
programas hacen la misma cuenta, no que la cuenta acierte.
