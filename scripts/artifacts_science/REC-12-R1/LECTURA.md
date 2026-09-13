# REC-12-R1 — La fuente sí servía, y quince receptores pierden algo del sitio

## Diagnóstico: `HAY_RECEPTORES_INCOMPLETOS` — decisión `GO`

`REC-12` no pudo leer su inventario: su G1 de validez de la fuente dio **0.0208**, porque
`data/pdbbind/<pid>/<pid>_protein.pdb` viene limpiado por PDBBind y elimina todo
heteroátomo que no sea agua o metal. El cero de cofactores era **del archivo**. Este R1
cambia una sola variable —la estructura original pasa a ser la entrada de RCSB— e importa
el módulo sellado de `REC-12` sin reescribirlo, como exige el §17.

| Instrumento | Criterio preregistrado | Resultado | Estado |
|---|---|---|---|
| **G1 validez de la fuente** | ≥5% de complejos con algún HETATM que no sea agua ni metal | **115/116 = 0.9914** | **Pasa** (REC-12: 0.0208) |
| **Lectura** | tres ramas escritas antes | 15 complejos con cofactor no aditivo **perdido** | **Rama (2)** |
| Secundario `1d7i`/`1ew9` | descriptivo, sin gate | **ninguno tiene cofactor en el sitio** | Negativo limpio |

Las 116 entradas se descargaron sin una sola ausencia. **Eso solo ya cierra lo que `REC-12`
dejó abierto: la pregunta era contestable y el instrumento estaba ciego, no vacío el objeto.**

## Los quince, y por qué quince es una cota superior

En 15 de 116 hay al menos un `HETATM` que no es agua, ni metal, ni figura en la lista
`ADITIVOS` congelada antes de correr, que cae a ≤8.0 Å del ligando cristalográfico y que
**no sobrevive en el `rec.pdbqt`** que consume todo el programa.

**El 15 no es un recuento de cofactores funcionales.** El prerregistro prohíbe mover la
lista después de ver el resultado, así que la cifra se reporta como salió y se desglosa:

| Grupo | n | Complejos | Qué son |
|---|---:|---|---|
| **Núcleo robusto** | **2** | `1gwv` (UDP), `1lbk` (GSH) | Cofactores funcionales de verdad — glutatión y UDP |
| Ligando o inhibidor | 11 | `1bty` `1c5o` `1c5p` (BEN), `1hpx` (KNI, 41 átomos), `1alw` `1d7j` `1f4g` `1fd0` `1igb` `1jao` `1jaq` | Descartarlos en la preparación **puede ser lo correcto** si son segundas copias del propio ligando. Este análisis no lo distingue |
| Hueco de mis listas | 2 | `1apv` (DMF, disolvente), `1dgm` (CL, cloruro) | `CL` no está en el conjunto `METALES` del módulo sellado; `DMF` no estaba en `ADITIVOS` |

**La lectura de existencia se sostiene aunque se retiren los dos últimos grupos:** UDP y
GSH bastan para que la rama (2) sea la correcta. Lo que no se sostiene es el titular
«quince receptores incompletos».

De aditivos propiamente dichos había 119 átomos en los sitios, dominados por `SO4` (13
complejos), `PO4` (4), `ACY` (3) y `GOL` (3) — justo lo que el archivo limpiado de PDBBind
había hecho invisible.

## Lo que NO establece

- **Que el sitio necesite esas especies.** Establece que el receptor preparado no las
  tiene. Es la prohibición explícita del prerregistro.
- **Que haya que cambiar algún receptor.** No cambia ni re-sella nada. Lo que autoriza es
  **diseñar `REC-05`** —ablación por familia—, que estaba bloqueado precisamente porque los
  cofactores eran invisibles.
- **Nada sobre la assembly biológica.** La entrada de RCSB es la unidad asimétrica
  depositada; esa cuestión la gobierna `REC-08`.

## El secundario cierra una puerta

`REC-09` dejó dos cristales absurdos sin explicar: **`1d7i` y `1ew9` puntúan absurdamente
mal con cero aguas bloqueantes.** Ninguno de los dos tiene cofactor en el sitio. **Esta vía
no los explica**, y la pregunta abierta de `REC-09` sigue abierta.

## Procedencia

Ejecutado en el contenedor `moldesign-lab` del servidor. Artefactos descargados con SHA-256
verificado contra el remoto. Los dos scripts —el nuevo y el módulo sellado de `REC-12` que
importa— coinciden byte a byte con lo sellado en `REC-12-R1-PRE`, en local y en el servidor.
