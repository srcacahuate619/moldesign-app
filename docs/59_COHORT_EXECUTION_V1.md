# 59 — Ejecución durable de una cohorte, v1

**Estado:** 🟢 Vigente desde Sprint 5C. Una cohorte congelada se ejecuta, el
progreso sobrevive al reinicio y una corrida interrumpida se reanuda. **No hay
ranking, ni métricas de enriquecimiento, ni dossier de cohorte** (Sprint 5D).

**Superficie:** `POST /evaluation/cohorts/{cohort_id}/runs` ·
`GET /evaluation/cohort-runs/{run_id}` · `.../resume` · `.../cancel`

**Prerrequisitos:** [57 — Comprobación previa](57_COHORT_PREFLIGHT_V1.md) ·
[58 — Cohortes congeladas](58_COHORT_PERSISTENCE_V1.md).

---

## 1. La regla que gobierna este sprint

> **El archivo original no se vuelve a leer. Nunca.**

Todo lo científico sale del snapshot congelado en 5B:

- la configuración, de `normalized_study_json`;
- las moléculas, de las filas `eligible` de `preflight_snapshot_json`;
- las estructuras, de sus `canonical_smiles` **congelados**.

Recanonicalizar con el RDKit de hoy ejecutaría una cohorte distinta de la que
alguien aceptó —posiblemente con más filas, posiblemente con menos— y el
`cohort_fingerprint` dejaría de identificar lo que de verdad corrió.

`source_bytes` no aparece en ninguna parte del camino de ejecución. Sigue
guardado para poder auditar, mucho después, que la interpretación fue fiel; no
para volver a interpretarla.

**La cohorte congelada no se toca.** Ningún estado de ejecución escribe en
`cohorts`: si lo hiciera, una cohorte no podría ejecutarse dos veces sin borrar
la historia de la primera.

---

## 2. Qué se congela al ABRIR la corrida

La cohorte identifica **qué** se ejecuta. La corrida congela **cómo**:

| Congelado | Por qué |
|---|---|
| `effective_config_json` | caja, motor, exhaustividad, poses y semilla, resueltos **una vez** |
| `receptor_provenance_json` + `receptor_prepared_bytes` | identidad y copia exacta del PDBQT preparado |
| `run_fingerprint` | la identidad de este cómo |
| Las filas de trabajo | con su molécula congelada, desde el primer instante |

### 2.1 La caja se resuelve una sola vez

Si la cohorte omitió `grid_center`/`grid_size`, se resuelven del **catálogo**
(`TargetORM`) al abrir la corrida y se congelan, con `grid_origin: "catalogo"`
para que el lector sepa de dónde salieron. Resolverla por fila permitiría que
dos moléculas de la misma cohorte se acoplaran en cajas distintas.

Si la cohorte no la declaró y el catálogo tampoco la tiene → **409**
`CAJA_NO_RESOLUBLE`. No se acopla en una región que nadie ha declarado.

### 2.2 El receptor se congela por su contenido, no por su ruta

El `.pdbqt` preparado vive en un directorio **mutable**: repreparar el receptor
lo reescribe con el mismo nombre. La corrida guarda tanto su **SHA-256** como
los bytes exactos, y el docking consume esa copia, no la ruta del catálogo:

```jsonc
{ "pdb_id": "7E2Y", "chain": "A",
  "prepared_sha256": "sha256:…", "prepared_size_bytes": 41231,
  "prepared_object": "targets/7E2Y/prepared.pdbqt",   // nombre lógico, no una ruta de disco
  "source_sha256": "sha256:…", "catalog_target_id": "…" }
```

Dos corridas con el mismo hash usaron el mismo receptor; con hashes distintos,
no, por mucho que la ruta coincida.

**Si no hay preparación verificable → 409 `RECEPTOR_PREPARADO_AUSENTE`, antes de
crear nada.** No se prepara al vuelo: eso convertiría un `POST` en un trabajo
largo de resultado incierto y dejaría al usuario sin saber si la corrida quedó
abierta.

### 2.3 `run_fingerprint`

`sha256:` sobre este documento canónico
(`sort_keys`, `separators=(",",":")`, `allow_nan=False`):

```jsonc
{ "contract": "cohort_execution/v1",
  "cohort_fingerprint": "sha256:…",
  "config": { "grid_center": [x,y,z], "grid_size": [x,y,z],
              "docking_engine": "vina", "engine_version": "AutoDock Vina 1.2.5",
              "exhaustiveness": 8, "num_poses": 5, "seed": 42 },
  "receptor": { "pdb_id": "7E2Y", "chain": "A", "prepared_sha256": "sha256:…" },
  "stages": ["validation","properties","sa_filter","conformer","docking"] }
```

**No entra:** `workers`, timestamps, usuario, estado, contadores. El paralelismo
cambia cuánto tarda, no qué se calcula; si entrara, la misma corrida en dos
máquinas parecería dos corridas distintas.

---

## 3. Esquema durable

```
cohort_runs
├── id · cohort_id → cohorts · user_id → users
├── status  queued|running|completed|completed_with_exceptions|failed|interrupted|cancelled
├── cohort_fingerprint · run_fingerprint
├── effective_config_json · receptor_provenance_json
├── total_rows        ← del ARCHIVO (denominador honesto)
├── eligible_rows     ← del TRABAJO
├── completed_rows · failed_rows · not_evaluated_rows   ← derivados de las filas
├── cancel_requested  ← intención, no estado
└── created_at · started_at · finished_at · last_error

cohort_run_rows          unique(run_id, source_row_index)
├── id · run_id → cohort_runs
├── source_row_index     ← índice en el ARCHIVO, vínculo con el snapshot
├── canonical_smiles     ← CONGELADO; nunca se recanonicaliza
├── source_name · control_role · active_label · duplicate_of_row
├── status  pending|running|completed|failed|not_evaluated|duplicate_reused|interrupted|cancelled
├── molecule_id · result_id
├── reused_from_row      ← linaje de EJECUCIÓN (≠ duplicate_of_row)
└── error_code · error_detail · started_at · finished_at
```

`SCHEMA_VERSION` 4 → **5**. Puramente aditiva: dos tablas nuevas; `cohorts` no
cambia, y no puede cambiar.

### 3.1 Las filas `invalid_input` NO se insertan

No son trabajo científico pendiente: son entradas que nunca van a ejecutarse.
Insertarlas como `not_evaluated` las mezclaría con las moléculas que sí entraron
y el motor no pudo evaluar, que es un hecho completamente distinto.

Sus cantidades no desaparecen: `total_rows` (archivo) frente a `eligible_rows`
(trabajo) sigue diciendo cuántas quedaron fuera, y el detalle publica los dos.

---

## 4. `eligible`, `failed` y `not_evaluated`

La distinción es el corazón de este contrato.

| | Qué dice | Qué NO dice |
|---|---|---|
| `eligible` | la fila puede entrar en la corrida común | nada sobre la molécula |
| `completed` | el docking terminó y hay resultado | **nada sobre actividad** |
| `not_evaluated` | el motor declaró que no evaluó esta molécula | nada sobre la molécula |
| `failed` | no se obtuvo resultado utilizable | nada sobre la molécula |
| `duplicate_reused` | otra fila acopló esta misma molécula | — |

**Un fallo de infraestructura no es evidencia negativa.** Que el motor se cayera
acoplando una molécula no dice que esa molécula no se una. Por eso `failed` y
`not_evaluated` son estados distintos, llevan `error_code` estable, y ninguno se
presenta jamás como un resultado científico.

Códigos: `SIN_RESULTADO` · `PIPELINE_FALLO` · `NO_EVALUADA` · `CANCELADA`.

---

## 5. Duplicados

Cada `canonical_smiles` único se acopla **una vez**. La primera fila elegible que
lo trae ejecuta; las siguientes quedan en `duplicate_reused`, con
`reused_from_row` apuntando a la que sí corrió, y heredan su `molecule_id`.

Conservan **su propio** `active_label` y **su propio** `control_role`: son filas
distintas del archivo aunque compartan molécula.

Dos campos, dos preguntas distintas:

- `duplicate_of_row` — **procedencia del archivo**, del snapshot: mira todas las
  filas con canónico, incluidas las que el validador rechazó.
- `reused_from_row` — **linaje de ejecución**: cuál acopló de verdad, entre las
  elegibles.

**No se elimina nada del denominador declarado.** `eligible_rows` sigue contando
los duplicados. La política estadística —si los duplicados pesan uno o ninguno en
una métrica— es de 5D; decidirla aquí, en silencio, cambiaría el denominador de
todo lo que venga después.

Si la fila que ejecuta no produce resultado, la duplicada **no se reintenta por
la puerta de atrás**: se declara `failed` con `SIN_RESULTADO` apuntando a ella.

---

## 6. El pipeline es el del producto

Se llama a `services/pipeline/runner.py::run_pipeline`, el mismo motor del modo
PRO. No hay una versión científica paralela de nada.

Se entra por la rama de `pipeline_config` y **no** por la heredada de
`_run_full_evaluation_async`, por una razón concreta: la heredada llama a
`predict_early_exit` (MolGraph) antes de acoplar y puede saltarse moléculas. Una
cohorte con moléculas silenciosamente omitidas no es una cohorte.

```
etapas pedidas   validation · properties · sa_filter · conformer · docking
excluidas        clgnn (GNN) · openmm · selectivity
ADMET-AI         desactivado por stage_params
Early Exit       no se ejecuta en esta rama
```

### 6.1 XGBoost fuera de la corrida de cohorte

El contrato de etapas requeridas puede acotarse por llamada. Evaluación y PRO
conservan su configuración histórica, pero cohortes requieren únicamente
`validation`, `properties`, `sa_filter`, `conformer` y `docking`. Por tanto XGBoost
no corre y no puede sustituir la afinidad de Vina. Ningún endpoint de corrida
devuelve `total_score`.

---

## 7. Máquina de estados

### 7.1 Corrida

```
                 ┌──────────────► cancelled ◄──────────┐
                 │                                     │
  queued ──► running ──┬──► completed                  │ (cancel_requested
     │           │     ├──► completed_with_exceptions  │  y sin trabajo activo)
     │           │     └──► failed                     │
     │           └──► interrupted ──(resume)──► queued ┘
     └──(cancel antes de empezar)──► cancelled
```

- `completed` — todas las moléculas únicas evaluables terminaron bien.
- `completed_with_exceptions` — hay al menos una `failed` o `not_evaluated`.
- `failed` — **no se obtuvo ningún resultado utilizable**. Una cohorte de 300 con
  299 acopladas y una caída **no** es una cohorte fallida; decirlo así tiraría
  299 resultados buenos.
- `interrupted` — la aplicación se cerró mientras corría. Dice lo único cierto:
  no sabemos cómo acabó.
- `cancelled` — se pidió cancelar y no queda trabajo activo.

La decisión vive en **un solo sitio**: `execution.decide_run_status`.

### 7.2 Fila

`pending → running → {completed | failed | not_evaluated}` ·
`pending → duplicate_reused` · `* → interrupted` (arranque) · `pending → cancelled`.

---

## 8. Durabilidad y reinicio

**`running` se escribe y se confirma ANTES de llamar al pipeline.** Si el proceso
muere durante el docking, queda una fila `running` en disco. Escribirlo después
dejaría una fila `pending` indistinguible de una que nunca empezó, y la
reanudación repetiría trabajo o lo daría por hecho.

Al arrancar la aplicación (`api/main.py`, lifespan):

1. Toda corrida `queued` o `running` en disco pertenece a un proceso que ya no
   existe → **`interrupted`**. Ninguna corrida puede fingir que sigue.
2. Sus filas `running` → **`interrupted`**.
3. Los contadores se **recalculan desde las filas**. Un contador que sobrevive a
   un corte sin que las filas lo respalden es un contador que miente.
4. Lo `completed` se conserva intacto.

### 8.1 Orden de escritura y encolado

    1. se persisten la corrida y TODAS sus filas, en una transacción;
    2. se hace `commit` — explícito, es la frontera del contrato;
    3. sólo entonces se encola la ejecución.

`BackgroundTasks` **no sirve** para esto: en la versión de FastAPI de este
repositorio las tareas de fondo corren *antes* de que se cierren las dependencias
con `yield`, es decir, antes del commit. Se comprobó, no se supuso. El ejecutor
abre su propia sesión y no encontraría la corrida.

Si algo falla después del commit, queda una corrida `queued` que el arranque
reconcilia a `interrupted` y se puede reanudar. Es el fallo barato; el caro sería
ejecutar sobre algo que no está guardado.

---

## 9. Endpoints

| | |
|---|---|
| `POST /evaluation/cohorts/{cohort_id}/runs?workers=N` | **202** con `run_id`, `status`, `run_fingerprint`, `eligible_rows`, `workers` |
| `GET /evaluation/cohort-runs/{run_id}` | estado, progreso, configuración efectiva, procedencia del receptor y filas |
| `POST /evaluation/cohort-runs/{run_id}/resume` | **202**. Sólo `interrupted` o `completed_with_exceptions` |
| `POST /evaluation/cohort-runs/{run_id}/cancel` | **200** con la corrida; marca la intención |

**202 y no 200**: abrir una corrida no la termina. Se aceptó el trabajo, está
persistido, y el resultado se consulta después.

### 9.1 Conflictos (409)

`CORRIDA_ACTIVA` (dos corridas simultáneas de la misma cohorte competirían por el
mismo motor local y ninguna sería reproducible) · `RECEPTOR_PREPARADO_AUSENTE` ·
`RECEPTOR_PREPARADO_ILEGIBLE` · `CAJA_NO_RESOLUBLE` · `COHORTE_NO_LISTA` ·
`SIN_FILAS_ELEGIBLES`.

Una corrida ajena y una inexistente devuelven **lo mismo: 404**. Un 403
confirmaría que ese identificador existe en esta máquina.

### 9.2 `resume` no reinterpreta nada

Las filas ya están en la base desde que se abrió la corrida, con su molécula
congelada. Reanudar es volver a recorrer las `pending` e `interrupted`, nada más.
**No repite las `completed`.** Las `failed` tampoco se reintentan en silencio:
eso convertiría un fallo declarado en un resultado nuevo sin que nadie lo
pidiera.

### 9.3 `cancel` marca intención, no mata

El ejecutor consulta la bandera antes de empezar cada fila: no se inician filas
nuevas, y las que ya terminaron **se conservan con su resultado**. Interrumpir un
docking en curso no ahorraría nada y dejaría una fila cuyo estado nadie puede
afirmar.

---

## 10. Concurrencia

`workers` es operacional: máximo explícito **4**, por defecto 2. Una excepción en
una fila **no cancela la cohorte** — cada fila va envuelta y sus hermanas siguen.
El paralelismo no entra en ningún fingerprint.

---

## 11. Lo que esto NO demuestra

- **Completar un docking no demuestra actividad.** `completed` significa que el
  cálculo terminó, nada más.
- **No hay ranking.** Ninguna respuesta ordena moléculas por mérito.
- **No hay `total_score`** ni ninguna puntuación 0-100 en la superficie de
  corridas.
- **No hay métricas de enriquecimiento** (EF, ROC-AUC). Hay etiquetas `active`
  congeladas y no se usan: son para 5D, después de ejecutar.
- **No hay dossier de cohorte.**

---

## 12. Dónde vive

```
backend/core/models.py                          CohortRunORM · CohortRunRowORM
backend/core/database.py                        SCHEMA_VERSION = 5
backend/services/cohort/execution.py            plan, fingerprint, pipeline, estados
backend/services/cohort/runs.py                 persistencia, bucle, reconciliación
backend/api/routers/evaluation_cohort_runs.py   las cuatro rutas
backend/api/main.py                             reconciliación en el arranque
```

---

## 13. Reservado para 5D

- Métricas de cribado (EF, ROC-AUC) sobre una corrida terminada, con su política
  de duplicados explícita.
- Dossier de cohorte y su paquete reproducible.
- Interfaz Batch migrada a cohortes; retirada de las rutas históricas.
- Reintento explícito de filas `failed`, a petición.
- Ejecución con receptor auto-preparado, si se decide que abrir una corrida puede
  disparar una preparación.
