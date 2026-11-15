---
titulo: "El UMS no reconoce los aniones que coordinan un metal, y la réplica lo reproduce byte a byte"
entradilla: "La señal UMS busca con patrones químicos los grupos que suelen coordinar un metal. En seis pares neutro/anión ve las seis formas neutras y ninguna aniónica. Añadir tres patrones las cubre todas sin activar ningún negativo. Este registro es la réplica del control, con el código fijado en Git."
---

**GO.** La réplica reproduce exactamente el resultado del control original. Ese control dice que los patrones actuales reconocen 6 de
12 positivos y que, con los candidatos, reconocen los 12 sin activar ninguno de los 12 negativos.

## Qué se midió

UMS es la señal que dice si un ligando tiene un grupo capaz de coordinar un metal (sulfonamida, hidroxamato, tiol…). La busca con
patrones SMARTS sobre el SMILES de entrada. Si el usuario escribe el grupo ya desprotonado, como queda al coordinar, puede pasar
inadvertido y la señal sale en cero.

- **Positivos:** seis moléculas en sus dos formas, neutra y aniónica: metanosulfonamida, bencenosulfonamida, acetohidroxamato,
  benzohidroxamato, etanotiol y tiofenol.
- **Negativos:** doce grupos parecidos que no deben activar estas familias: acetamida, acetato, sulfona, sulfóxido, tioéter,
  disulfuro, tioacetato, fenolato, entre otros.
- **Dos brazos sobre el mismo SMILES:** los patrones del producto y tres patrones candidatos para las formas aniónicas, cargados sólo
  en memoria. El producto no cambia.

## Qué pasó

| Familia | Patrones actuales | Con candidatos | Negativos sin activar |
|---|---:|---:|---:|
| Sulfonamida primaria | 2/4 | 4/4 | 12/12 |
| Hidroxamato | 2/4 | 4/4 | 12/12 |
| Tiol | 2/4 | 4/4 | 12/12 |

- **Los seis aniones se pierden con los patrones actuales;** las seis formas neutras se reconocen.
- **En M4 no cambia el orden:** la fórmula del score no depende de esta señal. En un perfil M5 que la pondere, sí podría cambiar.

## Por qué es una réplica

El sello original del control se apartó íntegro cuando el verificador vio que tres de sus ficheros podían cambiar de bytes al pasar
por git, porque no tenían protegido el final de línea. Esta réplica fija los blobs del código por su hash de Git, vuelve a correr la
sonda y obtiene el mismo resultado. Sólo prueba que el control se reproduce; no lo amplía.

## Qué dice y qué no dice

- **Dice que un cero de UMS no significa «no hay grupo»:** puede ser un anión que los patrones no cubren.
- **No mide coordinación real ni rendimiento:** son doce positivos elegidos a mano, sin potencia para estimar una tasa.
- **No se cambian los patrones:** ampliarlos exige versionar la señal y probar más familias negativas.
- **Lo que cambió en el producto** es sólo un texto: desde `7190fe00`, un cero de UMS en el dossier dice que estos aniones también dan
  cero. La evidencia completa está en la [ficha D-08 de la investigación de 1.0.4](../auditorias/investigacion-1.0.4/D08.md).
