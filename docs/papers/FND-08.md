---
titulo: "Le pedimos al registro que se sostuviera solo, y en diez sitios no lo hacía"
entradilla: "Auditoría de solo lectura sobre los 94 artefactos sellados. Fallan tres de los cuatro criterios, y el hallazgo principal no era ninguno de ellos: diez artefactos guardan sus datos bajo un nombre que el contrato no declara."
---

El programa promete algo concreto: que cualquiera pueda reconstruir sus resultados sin
memoria de sesión. El experimento que debería probarlo —un tercero reconstruyendo el
paquete de transferencia— depende de un export que todavía no existe.

Pero hay una pregunta anterior que **no depende de nada**, y que tiene que responderse
antes de que ningún tercero mire nada:

> ¿El registro se sostiene por sí solo?

Esta auditoría lo comprueba mecánicamente. Cuesta segundos y no escribe nada: sólo lee.

## Los cuatro criterios y el resultado

| Gate | Qué exige | Resultado |
|---|---|---|
| **G1** | Todo artefacto sellado valida sus hashes | **93 / 94** |
| **G2** | El `n` declarado coincide con las filas de su registro | **23 / 23** |
| **G3** | Todo artefacto con resultados tiene dato crudo no vacío | **60 / 64** |
| **G4** | El script que produjo el resultado está hasheado | **63 / 64** |

Tres de cuatro fallan. **NO_GO**, y ese es el resultado útil: una auditoría que pasa a la
primera normalmente significa que no miró lo suficiente.

## El hallazgo principal no era ninguno de los gates

**Diez artefactos guardan su dato crudo bajo un nombre distinto del canónico:**

| Artefacto | Dónde vive realmente el dato |
|---|---|
| `D-MF-HARD` | `cohort.jsonl` |
| `FEP-03` | `parejas.jsonl` |
| `MF-01-UNION` | `union_candidates_*.jsonl`, `union_labels_*.jsonl` |
| `MF-02E` | `corridas.jsonl`, `pocket_frame.jsonl` |
| `MF-08` | `corridas.jsonl` |
| `MF-10-CAL` | `brazo_a.jsonl`, `brazo_b.jsonl` |
| `MF-11-R2` | `per_complex_{train,val,test}.jsonl` |
| `MF-15`, `MF-20` | `per_complex_train.jsonl` |
| `RS-01` | `cache_train_only_view.jsonl` |

El contrato declara `per_complex.jsonl`, y en los diez casos **ese fichero sigue en el
directorio, vacío, junto al que sí tiene los datos**.

A un tercero se le dice que busque un archivo que está vacío. No hay pérdida de
información —los datos están ahí— pero es incumplimiento de contrato, y es exactamente la
fricción que hace fracasar una transferencia: el que llega mira donde se le dijo, ve cero
filas, y concluye que el artefacto está vacío.

**La corrección no es renombrar.** Renombrar rompería hashes sellados. Se resuelve con un
índice aditivo —`scripts/artifacts_science/_datos_crudos.json`— que dice para cada
artefacto dónde vive su dato realmente.

## Los fallos, uno a uno

**`FND-01-SMOKE` no valida, y no es reparable.** Selló `experiment_manifest.py` como
**dataset**. Cuando la herramienta se amplió con el subcomando `maintain`, el hash dejó de
coincidir — y `maintain` rechaza tocar `dataset_hashes` por diseño, porque los datasets
son inmutables.

La causa raíz es una mala clasificación: **código sellado como dato**. Es un artefacto
cuya hipótesis literal dice «smoke test» y no sostiene ninguna cifra del programa, pero el
fallo es real y queda declarado en lugar de silenciado.

**Cuatro artefactos declaran resultados sin ningún fichero de datos por unidad**:
`FND-04`, `MF-26`, `REC-03-PRE` y `RS-01A-R1`. Los cuatro son re-análisis o corrigenda
sobre material ya sellado, y sus scripts **sí** están hasheados. De modo que:

> Son reproducibles por **re-ejecución**. No son verificables por **lectura**.

Esa distinción existía de facto y no estaba declarada en ningún sitio. Ahora sí.

**`FND-02` declara resultados sin ningún script hasheado.** No se corrige a posteriori:
añadir hashes a un sello es reescribir lo que se garantizó en su momento. Se documenta.

**Cero hashes apuntan a ficheros ausentes.** Eso sí salió limpio, y es el chequeo que más
me preocupaba.

## Nota de método: la auditoría se equivocó dos veces antes de sellar

Vale la pena contarlo porque es la parte instructiva.

**Primera versión.** Buscaba el dato crudo en una lista fija de nombres de fichero.
Reportó **8 fallos de G3, cinco de ellos falsos**: el dato existía, sólo que bajo un nombre
que la lista no contemplaba.

**Segunda versión.** Comparó el `n` declarado contra el `.jsonl` más largo del directorio.
Produjo **6 falsos positivos en G2**, porque varios artefactos llevan ficheros auxiliares
—cohortes, parejas, brazos— con más filas que complejos tiene la cohorte.

Ambos criterios se corrigieron **antes** de sellar. Si se hubiera publicado la primera
versión, habría enviado a arreglar cinco cosas que estaban bien.

> Una auditoría mal calibrada es peor que ninguna: gasta credibilidad en defectos que no
> existen.

Es el mismo error que la auditoría persigue —afirmar algo que el dato no sostiene— cometido
por el instrumento que iba a detectarlo.

## Qué habilita esto

Ninguno de estos defectos invalida un resultado científico. Todos son de **contrato**: el
registro promete una estructura y en algunos sitios entrega otra.

Pero son justo los que un evaluador externo encuentra en los primeros diez minutos, y son
baratos de arreglar ahora y caros de descubrir cuando los encuentre otro. Arreglarlos es la
precondición de que `FEP-06` —el dry-run con un tercero de verdad— tenga alguna
probabilidad de salir bien.
