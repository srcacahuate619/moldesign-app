# 57 — Comprobación previa de cohortes, v1

**Estado:** 🟢 Vigente desde Sprint 5A. Contrato de ingesta y comprobación
implementado. La persistencia de cohortes llegó en Sprint 5B — ver
[58 — Cohortes congeladas](58_COHORT_PERSISTENCE_V1.md). La interfaz Batch
**todavía no lo usa**, la ejecución no existe (Sprint 5C) y el dossier de
cohorte tampoco.

**Superficie:** `POST /evaluation/cohorts/preflight`

---

## 1. Qué cambia respecto al Batch actual

El Batch histórico se presenta así:

> «Sube cientos de moléculas y te entregamos un ranking de candidatos.»

Eso afirma tres cosas que el producto no puede sostener: que hay candidatos, que
están ordenados por mérito, y que el orden significa algo. La cohorte se
presenta al revés:

> «Define una cohorte comparable, comprueba sus entradas y controles, ejecútala
> bajo una configuración común y declara cobertura, excepciones y evidencia por
> molécula.»

Los problemas concretos del Batch vigente, y qué hace este contrato con cada uno:

| Batch histórico | Cohorte v1 |
|---|---|
| Estado en memoria; se pierde al reiniciar | Este endpoint no guarda nada; la cohorte se congela con [`POST /evaluation/cohorts`](58_COHORT_PERSISTENCE_V1.md) |
| `total_score` 0-100 como ranking principal | **No existe ningún score**, ni aquí ni en la respuesta |
| Admite `ALL` y varios receptores | Un receptor y sólo uno; `ALL` se rechaza con 422 |
| Early Exit activado por defecto, cambia qué llega a docking | No hay Early Exit; nada filtra la cohorte en silencio |
| Filas inválidas contadas como un entero suelto | Taxonomía por fila, con código estable y fila conservada |
| No hay comprobación congelable antes de ejecutar | `cohort_fingerprint`: identidad reproducible de la cohorte |

Las rutas históricas (`POST /evaluation/batch`, `GET /evaluation/batch/{id}`,
`/export`, `/csv`) **siguen publicadas, sin cambios y funcionando** — se
ejercitan en `backend/tests/test_batch_legacy_contract.py`. La migración de la
interfaz es posterior; hasta entonces conviven.

---

## 2. Límites de lo que esta comprobación afirma

Es la sección que hay que leer antes que ninguna otra.

- **Superar el preflight no predice unión.** No se ha calculado ninguna energía,
  ninguna pose, ninguna interacción.
- **No predice calidad farmacológica.** Que una molécula sea `eligible` no dice
  nada sobre su ADME, su toxicidad ni su viabilidad sintética.
- **No se ha ejecutado ningún cálculo científico.** Sin docking, sin ML, sin
  GNN, sin MolGraph, sin PoseBusters, sin servicios externos, sin tareas de
  fondo.
- **No se calcula enriquecimiento.** Hay etiquetas `active` y no se usan para
  EF, ROC-AUC ni nada parecido: un enriquecimiento calculado antes de ejecutar
  mide el archivo, no el cribado.
- **`decision: ready` no significa «buena cohorte».** Significa que estas
  entradas se pueden leer y que esta configuración se puede aplicar a todas por
  igual. Es la condición mínima para empezar a producir evidencia, no evidencia.

---

## 3. Entrada

`multipart/form-data` con dos partes:

| Parte | Contenido |
|---|---|
| `file` | El archivo de moléculas: `.csv`, `.xlsx`/`.xls`, `.sdf`, `.smi`/`.txt` |
| `study` | `CohortStudy` v1 serializado como JSON |

### 3.1 `CohortStudy` v1

```json
{
  "schema_version": 1,
  "name": "Serie de anilinas · lote 3",
  "receptor": { "pdb_id": "7E2Y", "chain": "A" },
  "config": {
    "docking_engine": "vina",
    "exhaustiveness": 8,
    "num_poses": 5,
    "grid_center": [10.0, 11.0, 12.0],
    "grid_size": [22.0, 22.0, 22.0],
    "seed": 42
  }
}
```

| Campo | Obligatorio | Notas |
|---|---|---|
| `schema_version` | sí | Debe ser `1` |
| `name` | sí | 1-300 caracteres. Descriptivo: **no entra en el fingerprint** |
| `receptor.pdb_id` | sí | 4-10 caracteres `[A-Z0-9_-]`. Se normaliza a mayúsculas |
| `receptor.chain` | no | Máx. 4 caracteres, a mayúsculas |
| `config.docking_engine` | **sí** | `vina` o `qvina2` |
| `config.exhaustiveness` | **sí** | 1-128 |
| `config.num_poses` | **sí** | 1-20 |
| `config.grid_center` | no | Tres flotantes finitos, \|v\| ≤ 1000 |
| `config.grid_size` | no | Tres lados finitos, `0 < lado ≤ 100` |
| `config.seed` | no | Entero ≥ 0 |

**Por qué la configuración es obligatoria.** El producto tiene sus valores por
defecto (`vina_exhaustiveness=8`, `vina_num_poses=5`), pero una cohorte cuyo
fingerprint incluye un valor que nadie declaró cambiaría de identidad el día que
cambie ese ajuste. Aquí se declara o no se ejecuta.

**Por qué no hay `num_workers`.** El número de trabajadores es operacional:
cambia cuánto tarda, no qué se calcula. Meterlo en la identidad científica haría
que la misma cohorte, corrida en un portátil y en una estación, pareciera dos.

**La caja se omite, no se pone a cero.** Para que la caja se derive del receptor,
omite `grid_size`. El centinela `(0,0,0)` se rechaza: un lado de cero no es una
caja, y aceptarlo dejaría el fingerprint identificando una caja inexistente.

### 3.2 Columnas reconocidas

Insensibles a mayúsculas; gana la primera coincidencia.

| Papel | Nombres aceptados |
|---|---|
| estructura | `smiles`, `canonical_smiles`, `structure` |
| nombre | `name`, `id`, `identifier`, `molecule_name` |
| etiqueta | `active` |
| control | `control_role` |

`.smi`/`.txt` son posicionales: `smiles [nombre] [active] [control_role]`,
separados por espacios; `#` inicia comentario. En `.sdf` se leen del bloque
`_Name`, `active` y `control_role`.

`active` acepta `1/0`, `true/false`, `yes/no`, `si/no`, `active/inactive`
(y sus equivalentes en minúsculas). Cualquier otra cosa deja la etiqueta ausente
con el aviso `ETIQUETA_ACTIVE_INVALIDA`: no se adivina.

`control_role` acepta **exactamente** `reference`, `positive`, `negative`,
`none`. Un valor fuera de esa lista cae a `none` con
`ROL_CONTROL_INVALIDO` — `reference_compound` no se aproxima a `reference`,
porque suponerlo convertiría una errata en un control que nadie declaró.

**Ningún control se infiere.** Ni de un nombre que empiece por «ref», ni de una
etiqueta `active=1`, ni de la posición en el archivo. El día que se calcule
enriquecimiento, un control inventado decidiría el veredicto.

### 3.3 Qué se rechaza en la puerta (HTTP 422)

Se rechaza lo que impide siquiera *formular* la cohorte. No hay resultado
parcial, porque un resultado parcial de algo que no es una cohorte parecería una
cohorte.

- `study` que no es JSON válido.
- `pdb_id = ALL`, o una lista de receptores (`"7E2Y,3PP0"`).
- Campos desconocidos en cualquier nivel (`extra="forbid"`) — incluidos
  `num_workers` y `early_exit`.
- `NaN`, `Infinity`, `-Infinity`, y valores que se desbordan a infinito (`1e400`).
- Parámetros fuera de los límites del producto (exhaustividad, poses, motor,
  lado de caja, coordenada).
- Más de **500** filas, o un archivo de más de **8 MB**. El límite de filas es el
  que ya aplica el Batch histórico; no se inventa una capacidad que el producto
  no ha demostrado, y no se recorta la cohorte en silencio.

Lo demás **se declara en el resultado**, con 200: un archivo ilegible, una
columna ausente o cero moléculas elegibles sí son una cohorte —una que no se
puede ejecutar— y el cliente necesita verla entera para poder arreglarla.

---

## 4. Salida: `CohortPreflightResult` v1

```jsonc
{
  "schema_version": 1,
  "generated_at": "2026-08-24T21:52:23.610001+00:00",
  "cohort_fingerprint": "sha256:fd96e7c9c3f035ca…",
  "normalized_study": { /* el study tal como se firmó */ },
  "decision": "ready",            // "ready" | "blocked"
  "blockers": [],
  "warnings": ["FILAS_INVALIDAS", "DUPLICADOS_CANONICOS"],
  "summary": {
    "total_rows": 5,
    "eligible_rows": 3,
    "invalid_rows": 2,
    "unique_canonical_ligands": 2,
    "duplicate_rows": 1,
    "explicit_reference_controls": 1,
    "explicit_positive_controls": 0,
    "explicit_negative_controls": 0,
    "input_coverage": 0.6,
    "input_coverage_denominator": 5
  },
  "rows": [ /* una entrada por fila del archivo */ ]
}
```

### 4.1 Qué significa `eligible`

**Que la fila puede entrar en la corrida común de esta cohorte**: la estructura
se lee con RDKit y el validador del producto —el mismo que usa
`/evaluation/submit`— la acepta para evaluación.

Nada más. No significa que la molécula se una al receptor, ni que sea buena, ni
que la cohorte vaya a producir un resultado interpretable.

Las dos formas de **no** ser elegible se mantienen separadas a propósito:

- `SMILES_ILEGIBLE` — RDKit no puede leer la estructura. **Arregla el texto.**
- `SMILES_NO_ADMISIBLE` — se lee perfectamente, y la política química del
  producto la rechaza para evaluación (p. ej. menos átomos pesados del mínimo).
  **La molécula está bien escrita; este producto no la evalúa.**

Colapsarlas en «inválida» mandaría a alguien a revisar una sintaxis correcta.
Para las `NO_ADMISIBLE` se devuelve igualmente `canonical_smiles`, para que se
vea de qué molécula se habla.

### 4.2 Cobertura y su denominador

```
input_coverage = eligible_rows / total_rows
input_coverage_denominator = total_rows
```

`total_rows` es el número de filas de datos del archivo, **conservadas todas**:
un SMILES vacío, uno ilegible, un duplicado y una etiqueta rota siguen siendo
filas. Ése es el punto: un parser que descarta filas reduce el denominador y
convierte una cohorte del 60 % en una del 100 %.

**Sin filas no hay cobertura.** Con `total_rows == 0`, `input_coverage` es
`null` y `decision` es `blocked`. No es `0.0` —eso afirmaría un 0 % medido sobre
nada— y nunca es `NaN` ni `±Infinity`, que ni siquiera serían JSON válido.

Excepciones declaradas del recuento de filas, ambas por convención del formato:

- `.smi`/`.txt`: las líneas en blanco y los comentarios `#` son separadores, no
  registros; nadie declaró una molécula ahí.
- Excel: se recortan **sólo** las filas completamente vacías del final, que
  openpyxl fabrica a partir de la dimensión declarada de la hoja. Una fila vacía
  intercalada sí se conserva.

### 4.3 Duplicados

Dos filas con el mismo **SMILES canónico** son la misma molécula aunque el texto
difiera (`CC(=O)Oc1ccccc1C(=O)O` y `OC(=O)c1ccccc1OC(C)=O`). La repetición se
marca con `duplicate_of_row` apuntando a la primera fila equivalente y el aviso
`SMILES_DUPLICADO`.

**No se excluye.** Qué peso llevan los duplicados en las métricas es una decisión
de 5B; tomarla aquí, en silencio, cambiaría el denominador de todo lo que venga
después.

`unique_canonical_ligands` cuenta canónicos distintos **entre filas elegibles**:
cuántas moléculas distintas entrarían de verdad en la corrida.

Los recuentos de control cuentan roles declarados **en filas elegibles**: un
control que no puede ejecutarse no es un control disponible, y contarlo haría
creer que la cohorte tiene una referencia que nunca va a correr.

---

## 5. Fingerprint

`cohort_fingerprint` responde a una pregunta: *¿es ésta la misma cohorte
científica que aquélla?*

### 5.1 Canonicalización exacta

Se construye este documento, se serializa con
`json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False,
allow_nan=False)`, y el fingerprint es `"sha256:" + sha256(utf8(documento))`:

```jsonc
{
  "contract": "cohort_preflight/v1",
  "receptor": { "pdb_id": "<MAYÚSCULAS>", "chain": "<MAYÚSCULAS|null>" },
  "config": {
    "grid_center": [x, y, z] | null,     // redondeado a 3 decimales
    "grid_size":   [x, y, z] | null,     // redondeado a 3 decimales
    "docking_engine": "<minúsculas>",
    "exhaustiveness": <int>,
    "num_poses": <int>,
    "seed": <int|null>
  },
  "rows": [ ["<molécula>", <active|null>, "<control_role>"], … ]
}
```

`<molécula>` es el **SMILES canónico** cuando la estructura se pudo leer, y el
texto de entrada recortado cuando no: una fila ilegible sigue formando parte de
la cohorte declarada, y omitirla haría parecer iguales dos cohortes distintas.

Las filas van **en el orden del archivo**. Reordenar el archivo cambia el
fingerprint: en v1 la cohorte es el conjunto tal como se declaró. Ordenar por
canónico haría indistinguible «reordené» de «cambié una molécula».

Los flotantes se redondean a 3 decimales antes de serializar, igual que en
`services/docking/preflight.py`: sin eso, `22.5` y `22.500000000000004` —que
producen la misma caja— darían identidades distintas.

### 5.2 Qué identifica, y qué NO entra

| Entra | No entra |
|---|---|
| Versión del contrato | `generated_at` |
| Receptor normalizado (pdb_id, cadena) | `name` del estudio (descriptivo) |
| Configuración científica normalizada | `source_name` de cada fila |
| Filas normalizadas, en orden estable | Nombre del archivo y cualquier ruta local |
| Etiquetas `active` y roles de control | Número de workers |
| | Usuario o sesión |
| | Elegibilidad, razones y avisos |

Las tres últimas exclusiones merecen razón explícita:

- **`generated_at`**: si entrara, la misma cohorte tendría una identidad distinta
  cada vez que se comprueba, y el fingerprint no podría demostrar nada.
- **Workers, usuario y rutas**: la misma cohorte es la misma la ejecute quien la
  ejecute y donde la ejecute.
- **El veredicto (elegibilidad, razones, avisos)**: es una opinión *sobre* la
  entrada, no la entrada. Incluirlo ataría la identidad a la versión del
  validador, y la cohorte «cambiaría» al actualizar RDKit sin que nadie tocara
  una molécula.

Reescribir una molécula de otra forma (`CCO` → `OCC`) **no** cambia el
fingerprint: se firma el canónico.

---

## 6. Taxonomía de códigos

Son identificadores estables. La lógica —de la interfaz, del dossier de cohorte,
de cualquier análisis— depende del código, nunca del texto en castellano. Un
código no se renombra ni se reutiliza; añadir uno nuevo es aditivo.

### 6.1 Estado de fila (`eligibility`)

`eligible` · `invalid_input`

### 6.2 Razones de fila (`reasons`) — invalidan

| Código | Significado |
|---|---|
| `SMILES_AUSENTE` | La celda de estructura está vacía, o la fila entera lo está |
| `SMILES_ILEGIBLE` | RDKit no puede leer la estructura |
| `SMILES_NO_ADMISIBLE` | Se lee, y la política química del producto la rechaza |
| `REGISTRO_ILEGIBLE` | El registro del archivo no es una molécula (bloque SDF corrupto) |

### 6.3 Avisos de fila (`warnings`) — no invalidan

| Código | Significado |
|---|---|
| `SMILES_DUPLICADO` | Repite el canónico de una fila anterior (ver `duplicate_of_row`) |
| `ETIQUETA_ACTIVE_INVALIDA` | Había etiqueta y no se entiende; queda ausente |
| `ROL_CONTROL_INVALIDO` | Rol fuera del vocabulario; queda en `none` |
| `FILA_COLUMNAS_INCONSISTENTES` | La fila tiene más o menos celdas que la cabecera |
| `MOLECULA_CON_AVISOS_QUIMICOS` | El validador la aceptó dejando avisos |
| `NOMBRE_AUSENTE` | La fila no declara nombre; no se fabrica uno |

### 6.4 Bloqueantes de cohorte (`blockers`) — `decision: blocked`

| Código | Significado |
|---|---|
| `ARCHIVO_ILEGIBLE` | No se pudo decodificar (no es UTF-8) o recorrer |
| `FORMATO_NO_SOPORTADO` | La extensión no corresponde a ningún formato leído |
| `LECTOR_NO_DISPONIBLE` | El runtime no trae el lector de ese formato (openpyxl, RDKit) |
| `COLUMNA_SMILES_AUSENTE` | El archivo no declara columna de estructura |
| `COHORTE_VACIA` | No hay ninguna fila de datos |
| `SIN_MOLECULAS_ELEGIBLES` | Hay filas y ninguna puede entrar en la corrida |
| `VALIDADOR_NO_DISPONIBLE` | RDKit no está disponible; no hay veredicto que dar |

`LECTOR_NO_DISPONIBLE` y `VALIDADOR_NO_DISPONIBLE` no son `ARCHIVO_ILEGIBLE` a
propósito: el archivo puede estar perfectamente, y culparlo mandaría a la
persona a rehacer algo que no tiene nada malo.

### 6.5 Avisos de cohorte (`warnings`) — **ninguno bloquea**

| Código | Significado |
|---|---|
| `FILAS_INVALIDAS` | Hay filas que no entran en la corrida (la cobertura lo cuantifica) |
| `DUPLICADOS_CANONICOS` | Hay SMILES repetidos canónicamente |
| `SIN_CONTROLES_DECLARADOS` | Ninguna fila declara papel de control |
| `SIN_ETIQUETAS_ACTIVE` | Ninguna fila declara etiqueta `active` |
| `CAJA_NO_DECLARADA` | La configuración no fija caja; se derivará al ejecutar |
| `SEMILLA_NO_DECLARADA` | Sin semilla, dos corridas pueden diferir por ruido |

Un aviso que bloqueara sería un bloqueante mal nombrado. La ausencia de controles
avisa y no inventa ninguno; la ausencia de etiquetas `active` avisa y no bloquea
—una cohorte prospectiva no tiene por qué conocer la respuesta.

---

## 7. Determinismo

Con la misma entrada, la misma salida. Lo único que depende del reloj es
`generated_at`, y por eso está fuera del fingerprint.

---

## 8. Dónde vive

```
backend/services/cohort/
    taxonomy.py     códigos estables
    schemas.py      CohortStudy v1 · CohortPreflightResult v1
    parser.py       ingesta que NO descarta filas
    fingerprint.py  documento canónico y SHA-256
    preflight.py    orquestación pura
backend/api/routers/evaluation_cohorts.py
```

`api/routers/batch.py` **no se ha tocado**. Sus extractores son con pérdida por
contrato (filtran, saltan filas, indexan etiquetas por nombre); los de cohorte
conservan todas las filas. No son la misma función con otro llamador, así que
fundirlos habría obligado a cambiar uno de los dos comportamientos. Cuando 5B
retire el Batch histórico, aquella ingesta desaparece: no se unifica.

---

## 9. Reservado para 5B / 5C

- ~~Persistencia de la cohorte comprobada~~ — hecha en 5B, ver
  [doc 58](58_COHORT_PERSISTENCE_V1.md).
- Ejecución de la cohorte bajo la configuración común.
- Interfaz Batch migrada a cohortes; retirada de las rutas históricas.
- Decisión sobre cómo pesan los duplicados en las métricas.
- Verificación del receptor contra el catálogo (hoy sólo se valida la **forma**
  del `pdb_id`, no que exista y esté preparado).
- Métricas de cribado (EF, ROC-AUC) **después** de ejecutar, nunca antes.
- Dossier de cohorte y su paquete reproducible.
