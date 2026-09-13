---
titulo: "El 2.64% medía nuestra reconstrucción de hidrógenos, no la física de la pose"
entradilla: "Con los átomos pesados idénticos —desplazamiento máximo 0.0 Å— y los hidrógenos regenerados desde la geometría dockeada, la validez física pasa de 2.64% a 99.48%. Y la cifra nueva no se cita nunca sin esa condición."
---

Durante meses el programa reportó que **el 2.64% de las poses retenidas pasa PoseBusters**, y
que el 97.3% de los fallos venían de `internal_energy`. De ahí salieron tres conclusiones que
parecían sólidas: *la validez física es deficiente*, *el ensemble no la arregla*, y *una
minimización post-docking atacaría el problema*.

Las tres están invalidadas. Ninguna medía la pose.

## El defecto

Un PDBQT es una representación de **átomo unido**: los hidrógenos no polares no están. Para
pasar una pose por PoseBusters hay que reconstruirlos, y la capa que lo hacía los tomaba de
una fuente incompatible con la geometría dockeada. El resultado es un ligando cuyos átomos
pesados están donde el motor los puso y cuyos hidrógenos están donde no toca — una molécula
con tensión interna fabricada por la propia tubería de medición.

`internal_energy` detecta esa tensión perfectamente. Lo que no puede hacer es distinguir si
viene del docking o del instrumento.

## El diseño: mover hidrógenos y nada más

Sin cómputo de docking. Se reevalúan poses **ya retenidas**, regenerando los hidrógenos desde
la geometría de átomos pesados dockeada y relajándolos con **los pesados completamente
fijos**.

Dos ámbitos, declarados en `MF-33-H-COR-PRE` antes de correr:

| Ámbito | Qué es | Poses |
|---|---|---:|
| **A** | brazo flexible retenido por `MF-33-B-RET-R2`, 48 complejos | 8,224 |
| **B** | top-1 de los dos brazos del protocolo rígido, 116 complejos | 232 |

Y **cinco invariantes por pose**, que son la condición de validez del artefacto en lugar de
un umbral de tasa: desplazamiento pesado máximo dentro de 1e-6 Å, SMILES canónico idéntico,
carga formal idéntica, número de enlaces idéntico y cero hidrógenos heredados del cristal.
Una pose que viole cualquiera de ellas no entra en la tasa y se cuenta aparte.

## Qué salió

| Ámbito A — 8,224 poses | Histórica | **Corregida** |
|---|---:|---:|
| Válidas | 217 | **8,181** |
| Tasa | 2.64% | **99.48%** |
| IC95 Wilson | 2.31 – 3.01% | 99.30 – 99.61% |

| Ámbito B — 232 poses top-1 | Histórica | **Corregida** |
|---|---:|---:|
| Válidas | 28 | **216** |
| Tasa | 12.07% | **93.10%** |

Y el desglose por control, que es donde se ve el mecanismo:

| Control que falla | Histórica (A) | Corregida (A) |
|---|---:|---:|
| `internal_energy` | **8,006** | **7** |
| `double_bond_flatness` | **598** | **0** |
| `internal_steric_clash` | 23 | 23 |
| `minimum_distance_to_protein` | 13 | 13 |
| `bond_angles` / `bond_lengths` | 7 / 7 | 7 / 7 |

Los controles **geométricos** no se mueven ni una unidad. Se mueven exactamente los dos que
dependen de dónde están los hidrógenos.

**Y eso corrige una afirmación nuestra.** El prerregistro y el commit de este corrigendum
dijeron que el defecto afectaba a la energía interna. También contaminaba la **planaridad de
dobles enlaces**, que depende de los sustituyentes de hidrógeno: 598 → 0. La afirmación
previa de que sólo estaba afectada la energía era incompleta, y queda corregida aquí.

## Por qué la corrección es creíble, y no sólo favorable

Un corrigendum que multiplica por 38 la cifra que le conviene tiene que llegar con más
respaldo del habitual. Tres piezas:

**Las cinco invariantes se cumplen en las 8,456 poses**, verificadas por un consolidador
independiente y no por el contador del runner: desplazamiento pesado máximo **0.0 Å**, SMILES
canónico idéntico, carga formal idéntica, número de enlaces idéntico, **cero** hidrógenos
heredados del cristal, **cero** violaciones. La molécula corregida es la misma molécula.

**La reproducción de lo histórico es exacta, complejo a complejo y no en agregado.** La rama
histórica de esta tubería reproduce el top-1 `pb_valid` de `MF-33-PB` en los 48 complejos del
ámbito A y el `pb_valid_fisica` de `MF-33-TOP1` en los 116 del ámbito B, con **cero
discordancias**. Sin esa reproducción, un cambio de tasa podría ser un cambio de tubería; con
ella, la única variable que cambia es la reconstrucción de hidrógenos.

**Los 331 archivos se bajaron del servidor con SHA-256 contrastado**: 331 coinciden, 0
difieren, 0 faltan.

## No es ciego, y no lo finge

Los 12 complejos del piloto diagnóstico **fueron inspeccionados antes** de diseñar la
corrección, y la prueba técnica previa al sellado miró además `10gs` del ámbito B.

Ese piloto **demuestra el defecto y diseña la corrección**; no estima la tasa nueva, que es
lo que mide este artefacto sobre las cohortes completas. Un corrigendum de implementación no
se aprueba ni se rechaza: se ejecuta y se reporta, con la reconstrucción histórica al lado
para que la diferencia sea auditable. Por eso **no tiene gate de aceptación**, y es
deliberado.

La decisión `GO` es la única etiqueta compatible con el esquema del registro y significa
**aquí** «la corrección queda establecida y reemplaza a la medición anterior», no «el sistema
pasa un umbral».

## Una cifra que no es la corrección de la otra

El ámbito A corre sobre `MF-33-B-RET-R2`: 8,224 poses, no las 8,215 que selló `MF-33-PB`. La
única diferencia de cohorte es `1afl`, que aporta 267 poses en R2 frente a 258 en R1, y
**estaba predicha** en los límites declarados de `MF-33-PB`.

En consecuencia, el 8,006 de este artefacto **no es** el 7,997 de `MF-33-PB`: aquél contaba
`internal_energy` sobre 8,215 poses de R1 y éste sobre 8,224 de R2. No es una corrección de
la cifra vieja sino otra cohorte, y la caída que este corrigendum mide es **8,006 → 7 dentro
de la misma cohorte R2**.

## El residuo, que es lo que queda vivo

Las 43 poses del ámbito A que siguen inválidas —43 únicas frente a una suma de 57 recuentos
por control, porque una pose puede fallar varios a la vez— **se concentran en siete
complejos**: 21 de ellas en `1nm6` y 9 en `1mmq`. Sus fallos son geométricos:
`internal_steric_clash` 23, `minimum_distance_to_protein` 13, y un bloque de 7 poses que
fallan `bond_angles`, `bond_lengths` e `internal_energy` **siempre juntos**.

No es tensión generalizada del ligando. Es un subconjunto pequeño y localizado que merece
caracterización posterior. En el ámbito B pasa lo mismo: 14 de las 16 inválidas son contacto
con la proteína.

## Sin evidencia interpretable de diferencia entre brazos

Con la tasa cerca del techo, este diseño ya no distingue:

| | Ambos | Sólo ensemble | Sólo single | Ninguno | McNemar | MDE |
|---|---:|---:|---:|---:|---:|---:|
| Ámbito A (48) | 47 | 0 | 1 | 0 | p = 1.0 | 5.41 pp |
| Ámbito B (116) | 104 | 6 | 2 | 4 | p = 0.289 | 6.61 pp |

**No** se afirma que gane el single, **ni** que gane el ensemble, **ni** que sean
equivalentes. Lo último exigiría una prueba de no-inferioridad con margen preregistrado, que
aquí no existe.

## Qué se invalida y qué no

**Se invalidan y se reemplazan:** el 217/8215 = 2.64%; el 97.3% de fallos por
`internal_energy`; el 8/48 contra 10/48 de `MF-33-PB`; el 8.62% contra 15.52% de
`MF-33-TOP1`; y las tres conclusiones que colgaban de ellos —«la validez física es
deficiente», «el ensemble no la arregla» y «una minimización post-docking atacaría el
problema»—.

**No se ven afectados:** RMSD, cobertura del oráculo, top-1, top-5 y la cascada de conversión
de ningún artefacto. Los hidrógenos no entran en ninguna de esas métricas.

**`MF-33-PB` y `MF-33-TOP1` no se tocan.** Quedan sellados e inmutables con sus cifras
originales, etiquetados, y con este corrigendum nombrado al lado. Un registro que sólo publica
lo que funcionó no permite juzgar lo que funcionó; uno que corrige en silencio, tampoco.

## La condición que viaja con la cifra nueva

> El 99.48% es válido **después de una reconstrucción canónica de hidrógenos**. Sin esa
> cláusula la frase es incorrecta.

Y no demuestra exactitud de pose, ni unión, ni ventaja de ningún brazo. Este corrigendum no
toca el protocolo de docking: sólo dice que lo que se estaba midiendo no era lo que se creía
medir.
