---
titulo: "ProLIF no basta para ver si un ligando coordina el zinc"
entradilla: "Las interacciones de MolDesign no muestran la coordinación con metales. ProLIF trae dos detectores que podrían cubrirla. Con los iones pasados de forma explícita, reconocen 3 de 5 coordinaciones del cristal y se les escapan dos de zinc con sulfonamida, así que no entran en el producto."
---

**NO_GO técnico.** `MetalAcceptor` y `MetalDonor` de ProLIF 2.1.0 detectan 3 de 5 coordinaciones del cristal y no dan ningún falso
positivo en 9 controles negativos. El criterio exigía las cinco.

## Qué se midió

La huella de interacciones del producto no incluye la coordinación con metales. Es un límite declarado: un ligando que coordina el
zinc no lo enseña en su mapa de contactos. ProLIF, la biblioteca que la calcula, ofrece dos detectores para eso. Antes de añadirlos se
comprobó si ven lo que tienen que ver.

- **Positivos, en el cristal:** 1BN1 y 2AW1 (Zn–N), 4QA0 (Zn–S), 2JDI y 4WUD (Mg–O).
- **Negativos:** los mismos ligandos trasladados 30 Å, y 4PHL, cuyo ligando no tiene ningún donante cerca del Zn ni del Mg.
- **El ion se pasa a ProLIF de forma explícita,** con su posición del depósito y carga +2. Así un fallo no puede deberse a que la
  preparación lo retire.
- **Referencia:** la regla geométrica que usa Preparación (un N, O o S del ligando a 2,8 Å o menos del ion).
- **Descriptivo:** las 30 poses top-1 de MET-01-R1 con el ion conservado (semillas 42–46, Vina 1.2.7, exhaustividad 8).

## Qué pasó

- **Se le escapan 1BN1 y 2AW1,** dos zincs coordinados por el nitrógeno de una sulfonamida a 1,91 Å.
- **No hay falsos positivos:** 0 de 9 controles.
- **En las poses acopladas, la regla geométrica marca 20 de 35 pares ion–pose y ProLIF 15.** Las cinco diferencias son las cinco
  semillas de 1BN1.

## Qué dice y qué no dice

- **No se añade ProLIF como detector de coordinación:** se le escapan dos de los tres zincs del cristal.
- **El fallo no es de distancia:** el ion estaba presente y el donante a 1,91 Å. El límite está en el estado químico que declara el
  archivo del ligando y en los patrones SMARTS con los que ProLIF reconoce un donante.
- **La regla geométrica tampoco es una coordinación:** no mira ángulos, estado químico ni geometría multidentada.
- **Con cinco positivos no se estima ninguna tasa.** Es un piloto dirigido.
- **La recomendación de la investigación** es mantener las reglas de abstención y exigir un término de coordinación propio, evaluado
  antes de ampliar M5. Está en la [ficha D-05 de la investigación de 1.0.4](../auditorias/investigacion-1.0.4/D05.md).
