# E5 — enderezar cadenas y girar colas, como MolTalk: registro previo (2026-10-25)

Escrito y commiteado **antes** de medir. Resultados en `RESULTADOS.md`,
sección E5.

## Origen

`moltalk/conformer.py` (DomFico/moltalk, `44da199`, MIT) refina el conformador
elegido con dos pasos que no portamos:

- `_extend_chains`: pone a 180° (anti) las torsiones de las cadenas abiertas de
  carbonos sp3 (≥ 4 carbonos), relaja con MMFF (500 iteraciones) y conserva el
  resultado sólo si encaja mejor con el dibujo;
- `_swing_tail`: si una cola de ≥ 6 enlaces sale de un sistema de anillos, prueba
  60°, 180° y 300° en sus primeras 4 torsiones, descarta las combinaciones con
  átomos pesados a ≥ 4 enlaces y a < 2,5 Å, elige la que mejor encaja, relaja
  (300 iteraciones) y la conserva sólo si encaja mejor.

Se portan con la lógica de MolTalk y la puntuación de MolDesign (el desajuste de
`_ajuste` con los pesos del producto). MolTalk también exige que no empeore el
acuerdo con las cuñas; aquí no hace falta, porque girar enlaces sencillos no
cambia ninguna configuración (se comprueba: los centros R/S del refinado deben
ser los del SMILES).

## Regla que se mide

Los candidatos del producto (`26df919c`). En cada semilla, a su mejor candidato
se le aplica `_extend_chains` y después `_swing_tail` (como MolTalk: sólo al
elegido, no a todos). Abstención: la mediana de los tres mejores refinados, entre
la longitud media de enlace del dibujo, > 1. Se enseña el mejor refinado.

## Conjuntos y métricas

G37 y O167, como E1 y E4.

- abstención, producto frente a E5, en cada conjunto;
- cuántas moléculas tienen una cadena o una cola a la que se aplica algún paso,
  y en cuántas se conserva;
- ΔE MMFF del enseñado sobre el mínimo del conjunto **unido** (candidatos del
  producto ∪ refinados), para el producto y para E5 con la misma referencia;
- en G37, también ΔE xTB-ALPB con la misma regla;
- tiempo mediano por molécula, producto frente a E5;
- comprobación de estereoquímica: ningún centro R/S del refinado distinto del
  SMILES.

## Decisión

**GO** (vale la pena proponer el cambio) si se cumplen todas:

- G37: se abstienen ≤ 4/37 (el producto, 8/37);
- O167: no se abstienen más que con el producto (1/167);
- G37: la mediana de ΔE MMFF del enseñado no sube respecto del producto, con la
  misma referencia;
- tiempo mediano ≤ 1,5 veces el del producto;
- ningún centro estereogénico cambia.

Si no, **NO_GO**, con las cifras. Un GO no cambia el producto por sí solo: se
propone al propietario.
