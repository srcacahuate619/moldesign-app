# SUP-03-VALIDADOR-LIGANDO — acta de cierre

**Decisión: GO.** Ninguna de las cuatro reglas bloqueantes del validador del ligando rechaza ninguna de las 640 moléculas con
actividad medida de las tres dianas disponibles:
- R1 · carga neta mayor que 2 en valor absoluto;
- R2 · carga de un átomo mayor que 2 en valor absoluto;
- R3 · radicales;
- R4 · varios fragmentos tras quitar sales.

Criterio en `entrada/REGISTRO_PREVIO.md` (`bbef7ffe`), commiteado antes de pasar ninguna molécula.

| Conjunto | n | Aceptadas | R1 | R2 | R3 | R4 | Otra |
|---|---:|---:|---:|---:|---:|---:|---:|
| A · VMAT2 (Ki, patente) | 89 | 89 | 0 | 0 | 0 | 0 | 0 |
| B · NET (Ki, ChEMBL) | 57 | 57 | 0 | 0 | 0 | 0 | 0 |
| C · 5-HT1A (ChEMBL) | 494 | 494 | 0 | 0 | 0 | 0 | 0 |
| D · señuelos DUD-E de 5-HT1A | 3000 | 3000 | 0 | 0 | 0 | 0 | 0 |
| E · conjuntos de benchmark, sin duplicados | 6898 | 6824 | 0 | 0 | 0 | 6 | 68 |

## Lo que sí rechaza, en los conjuntos descriptivos

- **R4, 6 moléculas:** solvatos escritos con el disolvente como segundo fragmento (p. ej. `….CC(C)=O`, acetona), que `SaltRemover`
  no reconoce. La molécula es válida; el usuario tiene que borrar el disolvente a mano. El validador ya tiene el camino de
  «avisar y quedarse con el fragmento mayor», pero el modo estricto lo apaga. Es una observación, no decide.
- **Otra, 68:**
  - 19 llevan boro. Vina no tiene parámetros para B, y eso es una limitación real del motor.
  - 49 son péptidos de más de 1000 Da o más de 70 átomos pesados, fuera del alcance declarado; ESMFold es el camino de los
    péptidos.

## Qué significa

Con estos datos, las cuatro reglas no bloquean química con actividad medida: el supuesto se sostiene. Los únicos rechazos de R4 son
de formato. Con la preferencia del propietario (avisar, no bloquear), convertir R4 en aviso con el fragmento mayor sería coherente,
pero este experimento no lo exige.

## Límites y desviaciones

- **Entradas copiadas antes de sellar.** C, D y E no están versionados en `data/` (C, por `.gitignore`; los checkpoints suman
  729 MB). Se copiaron a `entrada/` antes de sellar: C y D tal cual, y E como la lista de `completed_smiles` de los diez
  checkpoints, sin duplicados. `entrada/fuentes.json` guarda el SHA-256 de cada original, y el resultado se repitió desde las copias
  con métricas idénticas byte a byte.
- **Sólo los SMILES de entrada.** La protonación posterior puede subir la carga, y este experimento no mira esa etapa.
- **640 moléculas de tres dianas no son el espacio de los fármacos.** Un GO dice que las reglas no muerden aquí, no que nunca
  muerdan. Los aniones múltiples (fosfatos, nucleótidos) no están representados.
