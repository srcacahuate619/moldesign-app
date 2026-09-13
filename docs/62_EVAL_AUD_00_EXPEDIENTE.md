# EVAL-AUD-00 — Expediente de auditoría de la pestaña Evaluación

**Fecha:** 2026-08-29
**Plan de referencia:** [61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md](61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md)
**Paso del método:** 1 (AUD, sólo lectura) y primeros paquetes de escritura.
**Prioridad del mandato:** validez científica → calidad → eficiencia.

Este expediente registra lo encontrado con evidencia reproducible, lo corregido
en esta sesión y lo que queda abierto. No declara verde ninguna pestaña: el
Gate de Evaluación exige una corrida real con el motor empaquetado, reinicio de
backend y dos cuentas en la misma máquina, y esa parte sigue pendiente (§6).

---

## 1. Mapa real del flujo (lectura)

```
cuenta ─▶ caso (CaseWorkspace) ─▶ inputs (receptor + ligando + caja)
   │                                   │
   │                                   ▼
   │                          POST /evaluation/preflight
   │                          (build_preflight, sin docking)
   │                                   │  input_fingerprint
   │                                   ▼
   └────────────────▶ POST /evaluation/submit ──▶ submit_evaluation_job
                        (recalcula la huella)      (dispatcher desktop, 1 proceso)
                                                        │
                              ┌─────────────────────────┴─────────────┐
                              │ pipeline_config presente              │ ausente
                              ▼                                       ▼
                     services/pipeline/runner.py            queue_handler (rama heredada)
                              │                                       │
                              └──────────────┬────────────────────────┘
                                             ▼
                          SQLite (molecules, evaluation_results, runs)
                                             │
      GET /evaluation/status/{task_id} (polling 2 s) ◀───┤
      GET /evaluation/stream/{task_id} (SSE, orbs)   ◀───┤
      GET /evaluation/result/{molecule_id}           ◀───┤
      GET /evaluation/files/{poses,protein,complex}  ◀───┤
      GET /evaluation/dossier/...                    ◀───┘
```

Hechos del mapa que condicionan todo lo demás:

- **Un solo proceso.** Los workers viven dentro del backend; si el proceso
  muere, ninguna tarea sobrevive. Lo que quede «en marcha» en SQLite tras un
  arranque pertenece por definición a una corrida muerta.
- **Dos motores, no uno.** `pipeline_config` decide entre `runner.py` (camino
  PRO, el que usa la pestaña) y la rama heredada de `queue_handler`. La rama
  heredada sigue publicada y alcanzable desde `/evaluation/evaluate` y
  `/evaluation/batch`.
- **La autoridad del estado terminal es el polling**, no el SSE. El SSE sólo
  alimenta los orbs del timeline (`lib/pipelineStream.ts`).
- **La identidad durable de una corrida es `task_id` + `molecule_id`**, y el
  caso guarda ambos en su manifiesto. `localStorage` no es la fuente de verdad
  en escritorio (`tauriCaseRepository`), y en navegador las claves ya están
  particionadas por cuenta (`lib/userStorage.ts`, `caseKey(ownerUserId, id)`).

## 2. Hallazgos

Prioridad según §4 del plan. Estado: **corregido** (con prueba), **abierto**,
o **aceptado con limitación**.

| ID | P | Eje | Dónde | Estado |
|---|---|---|---|---|
| EVAL-SCI-001 | P0 | Ciencia | `services/pipeline/runner.py:234`, `services/docking/queue_handler.py:297`, `services/docking/peptide_docking.py:45`, `db/repository.py:544` | corregido |
| EVAL-SCI-002 | P0 | Ciencia | `services/docking/queue_handler.py:366-386` | corregido |
| EVAL-BE-003 | P0 | Backend | `api/routers/evaluation_files.py:30-90` | corregido |
| EVAL-BE-004 | P1 | Backend | `api/main.py:193-211` | corregido |
| EVAL-BE-005 | P1 | Backend | `api/routers/evaluation.py:145` | corregido |
| EVAL-BE-007 | P2 | Backend | `services/docking/queue_handler.py` (código muerto) | corregido |
| BATCH-SCI-001 | P0 | Ciencia | `api/routers/batch.py:497-520, 600-640` | corregido |
| EVAL-INT-006 | P2 | Intersección | `api/routers/evaluation.py` (`_enforce_submission_gates`) | corregido |
| EVAL-INT-008 | P2 | Intersección | `lib/types.ts` vs `EvaluationResultRead` | corregido |
| EVAL-FE-009 | P2 | Frontend | `context/EvaluationContext.tsx`, `components/interfaces/pro/ProResults.tsx` | corregido |
| EVAL-EFF-010 | P2 | Eficiencia | `api/routers/evaluation.py` (`poseData` en el polling) | corregido |
| BATCH-BE-002 | P1 | Backend | `api/routers/batch.py` (`GET /batch/{id}`, `/export`, `/csv`) | corregido |
| MOLCHAT-INT-001 | P1 | Intersección | `services/ai/tools/docking_tools.py:59` | abierto |
| TRANS-NET-001 | P1 | Transversal | `evaluation_files.py`, `ingestion_manager` | abierto |
| EVAL-SCI-012 | P0 | Ciencia/intersección | `api/routers/sar.py`, `components/interfaces/pro/ProSarTab.tsx` | corregido |
| EVAL-UX-013 | P1 | UX | `components/interfaces/pro/TargetSelectorModal.tsx` | corregido |

---

### EVAL-SCI-001 · P0 · El receptor de una corrida se sustituía en silencio

**Evidencia.** Los tres caminos de ejecución terminaban igual cuando el
receptor pedido no estaba en el catálogo y la auto-ingesta fallaba:

```python
# services/pipeline/runner.py (antes)
if target is None:
    target = await repository.ensure_default_target()   # ← 7E2Y, 5-HT1A
```

`ensure_default_target()` devuelve **7E2Y (receptor 5-HT1A de serotonina)** con
su propia caja de docking. La corrida continuaba, persistía y devolvía
`SUCCESS`. `db/repository.py::create_or_get_molecule` hacía lo mismo un nivel
más abajo, de modo que incluso la fila de la molécula quedaba archivada contra
otro receptor.

**Impacto científico.** El resultado describe una proteína que el investigador
no eligió, con coordenadas de caja que pertenecen a otra estructura. No hay
manera de distinguirlo de un resultado bueno: no hay advertencia, no hay
estado, y el dossier hereda la sustitución. Es la definición de invalidez
científica del plan (§4, P0).

**Alcanzabilidad.** El producto es local y offline por diseño. Basta un PDB ID
que no esté en el catálogo curado (entrada manual, receptor borrado del disco,
herramienta de MolChat) más la ausencia de red para que la ingesta falle.

**Causa raíz.** `ensure_default_target()` cumple dos funciones incompatibles:
sembrar el receptor base en una instalación nueva y actuar de comodín cuando
falta cualquier otro.

**Corrección.** `services/targets/resolution.py::resolve_execution_target`
concentra la regla: devolver el receptor pedido, incorporarlo si se puede,
sembrar el base **sólo si el base es lo pedido**, y en cualquier otro caso
levantar `TargetUnavailableError` con un mensaje que el usuario puede accionar.
`create_or_get_molecule` rechaza un `target_pdb_id` explícito inexistente. El
docking peptídico registra la molécula con `target_pdb_id=target.pdb_id` en vez
de dejar que caiga al base.

**Prueba.** `backend/tests/test_target_substitution.py` (11 casos): fallo de
ingesta, excepción de ingesta, siembra legítima del base, receptor conocido,
ingesta exitosa, rechazo en persistencia, y tres guardas de código que impiden
reintroducir la caída por copia.

---

### EVAL-SCI-002 · P0 · Una heurística de vecindad cancelaba la corrida y se presentaba como fallo técnico

**Evidencia.** La rama heredada consultaba `predict_early_exit` (media de los
scores de los vecinos con Tanimoto ≥ 0.6 en el grafo químico local) y, si
predecía inactividad, devolvía sin acoplar:

```python
return {"task_id": ..., "molecule_id": ..., "skipped": True, "reason": ...}
```

**Cadena de consecuencias, medida en el código:**

1. `_run_serialized_wrapper` marcaba el job `SUCCESS` con ese diccionario;
2. `get_desktop_job_status` buscaba el resultado persistido, no lo encontraba
   —nunca se escribió— y devolvía `FAILURE` con *«no fue posible recuperar su
   resultado persistido. Revisa los logs del backend y reintenta»*;
3. la molécula quedaba en `validated`, estado que el historial no lista.

**Impacto científico.** Una **predicción** sustituía a la **observación**
pedida, sin declararlo, y el usuario recibía un fallo técnico inventado en
lugar de su docking o de una abstención honesta. Contradice el mandato de
separar «docking, rescoring, predicción, heurística y evidencia observada»
(§5, EVAL-SCI) y la decisión de `docs/60` de mantener ML/GNN fuera del camino
crítico del MVP.

**Corrección.** El pre-filtro sale del camino de ejecución. El grafo químico
sigue disponible para MolChat y para análisis; lo que no puede hacer es decidir
si se calcula lo que se pidió.

**Prueba.** `backend/tests/test_early_exit_no_sustituye_la_corrida.py`.

---

### EVAL-BE-003 · P0 · `GET /evaluation/files/protein/{molecule_id}` no comprobaba propiedad

**Evidencia.** El propio código lo declaraba:

```python
# ``current_user`` se mantiene en la firma para conservar el contrato de
# dependencia del endpoint. La política de autorización de targets se
# consolidará junto con los demás archivos en el siguiente corte C-09.
_ = current_user
```

Sus dos hermanos (`/files/poses`, `/files/complex`) sí llaman a
`require_owned_molecule`. Con el id de una molécula ajena, éste devolvía 200 y
el PDB del receptor.

**Impacto.** Rompe literalmente el Gate de Evaluación —«segunda cuenta no puede
listar, leer, descargar, cancelar ni **inferir** la corrida»—: un 200 confirma
que la corrida existe y revela contra qué proteína se ejecutó. Si el receptor
era una estructura privada subida por otra cuenta (`USR_*`), lo que se
descargaba eran sus bytes.

Además, al no encontrar el archivo local salía a RCSB **sin consentimiento** y
con el identificador interno en la URL. La prueba en rojo lo demostró
literalmente: `GET https://files.rcsb.org/download/USR_ALICE.pdb`.

**Corrección.** Se aplica `require_owned_molecule` y
`require_target_object_access` —la misma política que el resto de la
superficie— y se rechaza la descarga externa de identificadores que no son PDB
públicos. La lectura del receptor se hace con `repository.get_molecule`, que
trae la relación con `selectinload`: la instancia de la política no la tiene
cargada y tocarla dispararía una carga perezosa dentro de una sesión asíncrona.

**Prueba.** `backend/tests/test_evaluation_protein_file_access.py` (4 casos,
incluida la comprobación de que no se toca el disco ni la red antes de
autorizar).

---

### EVAL-BE-004 · P1 · Reconciliación incompleta tras un reinicio

**Evidencia.** El arranque sólo reconciliaba `pending`
(`api/main.py`), pero el pipeline escribe y commitea `validated`
(propiedades hechas) y `docking` (acoplamiento en curso).

**Impacto.** Una corrida interrumpida —cerrar la aplicación, apagón, crash—
quedaba atrapada en un estado intermedio para siempre: invisible en el
historial (que lista `evaluated` y `failed`) y en contradicción con
`get_desktop_job_status`, que sí concluye que la tarea ya no existe.

**Corrección.** `services/docking/recovery.py::reconcile_interrupted_evaluations`
cierra los tres estados no terminales y escribe el motivo —se interrumpió— en
`error_message`, sin inventar resultado y sin tocar lo terminal. Es idempotente.

**Prueba.** `backend/tests/test_reconciliacion_evaluaciones.py` (4 casos).

---

### EVAL-BE-005 · P1 · `/evaluation/evaluate` era una puerta trasera del submit

**Evidencia.** El endpoint síncrono ejecuta el mismo pipeline y acepta el mismo
modelo de petición —incluido `preflight_fingerprint`—, pero no comprobaba la
huella, no aplicaba la cuota anónima ni el limitador, y no registraba el dueño
del `task_id` del que dependen `status`, `stream` y `cancel`.

**Corrección.** Las comprobaciones del submit se extraen a
`_enforce_submission_gates` y las usan los dos endpoints. El dueño se registra
antes de ejecutar nada.

**Prueba.** `backend/tests/test_evaluacion_sincrona_comparte_gates.py`.

**Nota de alcance.** No se retira el endpoint: ningún cliente del repositorio
lo usa, pero eliminarlo es un cambio de contrato y corresponde al propietario.

---

### EVAL-BE-007 · P2 · Borrado automático de resultados (código muerto)

`_schedule_cleanup` programaba, una hora después de evaluar, el borrado de toda
molécula no guardada con `total_score < 50`. **Nadie lo llamaba** —quedó
desconectado al cambiar la política de historial—, pero seguía en el módulo
listo para reconectarse. Retirado, con guarda en la prueba.

---

### BATCH-SCI-001 · P0 · El batch heredado fabricaba cifras y miraba las etiquetas

Dos defectos que viajaban juntos en `POST /evaluation/batch`
(`early_exit` con **valor por defecto `True`**):

1. **Cifras fabricadas.** La molécula saltada entraba en la tabla de
   resultados con `"total_score": 0, "affinity_kcal": 0`. Nadie la acopló: ese
   cero no es una medida débil, es una medida inexistente, y así viajaba al
   Excel exportado.
2. **Filtro dependiente de la etiqueta.** El pre-filtro sólo se aplicaba a las
   moléculas **no marcadas como activas**
   (`if early_exit and not mol.get("is_active")`). En un conjunto etiquetado
   eso descarta señuelos usando la verdad que EF y ROC-AUC pretenden medir, y
   `_compute_ef_metrics` calcula después sobre lo que quedó.

**Corrección.** El pre-filtro sale del batch por la misma razón que de la
evaluación. El parámetro `early_exit` se conserva en el contrato, marcado como
deprecado, y la respuesta declara `early_exit_enabled: false`, de modo que el
cliente puede **ver** que no se aplicó.

**Prueba.** `backend/tests/test_batch_legacy_no_fabrica_resultados.py`.

**Nota de alcance.** Esto no abre el cierre profundo de Batch (pestaña 2). Se
corrigió aquí porque es un P0 de afirmación engañosa en una superficie
publicada, del mismo linaje que EVAL-SCI-002.

---

### BATCH-BE-002 · P1 · El batch heredado no tenía dueño

`GET /evaluation/batch/{batch_id}`, `/export` y `/csv` no comprobaban ninguna
identidad: el estado vive en un diccionario en memoria (`_batches`) que no
guardaba `user_id`. Conocer el identificador —que viaja en enlaces, capturas y
paquetes de soporte— bastaba para leer o exportar el cribado completo de otra
cuenta en la misma máquina.

**Corrección.** El registro guarda `owner_id` (la cuenta, o `demo` para el
espacio anónimo) y las tres lecturas exigen coincidencia. Se responde **404**,
no 403, para no confirmar la existencia de un cribado ajeno; el 400 histórico
de «aún en progreso» se conserva sólo para el dueño.

**Prueba.** `backend/tests/test_batch_legacy_aislamiento.py` (3 casos, incluida
la no herencia de un cribado anónimo por la siguiente cuenta que inicie sesión).

---

### Hallazgos abiertos

**EVAL-INT-006 · P2 · Corregido · `submit` recalculaba el preflight sin `chain`.**
`chain` ya forma parte de `EvaluationSubmitRequest`, del payload TypeScript y
del `PreflightRequest` que el backend recalcula antes de ejecutar. La cadena se
trata como identidad esperada del receptor registrado —la versión actual no
promete selección multi-chain por corrida—: si cambió respecto del target, el
submit responde 409 y obliga a seleccionar/comprobar de nuevo. Lo cubren una
prueba backend de propagación, otra de discrepancia y contratos frontend de
runner y cuerpo HTTP. El OpenAPI versionado incluye el campo aditivo.

**EVAL-INT-008 · P2 · Corregido · Procedencia reproducible visible.**
`receptor_sha256`, `receptor_path` y `docking_protocol` forman parte del tipo
TypeScript. La vista activa muestra el hash completo y el protocolo ejecutado,
incluidas conformaciones, motor, exhaustividad, poses, semilla y advertencias.
La ruta local se conserva para trazabilidad interna, pero nunca se renderiza:
una prueba usa deliberadamente una ruta privada de Windows para vigilarlo.

**EVAL-FE-009 · P2 · Corregido · Estado y superficie muertos retirados.**
Se eliminaron `context/EvaluationContext.tsx` y
`components/interfaces/pro/ProResults.tsx`, que no tenían consumidores, y los
campos fantasma de `EvaluationResult` asociados. La superficie activa queda
como única máquina de estados de la evaluación y usa el PDB ID del target
seleccionado, no una propiedad inexistente del resultado.

**EVAL-EFF-010 · P2 · Corregido · Polling sin SDF.**
`GET /evaluation/status/{task_id}` ya no abre ni serializa el archivo de poses.
El cliente lo solicita a `/evaluation/files/poses/{id}` sólo cuando necesita la
vista 3D. Se retiró `poseData` del modelo de respuesta y una regresión impide
que el polling vuelva a leer el archivo.

**MOLCHAT-INT-001 · P1 · La herramienta de docking de MolChat no puede funcionar.**
`services/ai/tools/docking_tools.py:59` importa
`from services.docking.queue_handler import run_single_evaluation`, y esa
función **no existe** en el módulo. El `ImportError` se captura y la
herramienta devuelve siempre *«Pipeline de docking no disponible en este
modo»*, pese a que `chat_service` fuerza esta herramienta por intención. La
corrección pertenece al cierre de MolChat (pestaña 4): necesita identidad de
usuario, persistencia y contrato propios.

**TRANS-NET-001 · P1 · Red implícita sin consentimiento.**
No existe todavía una puerta de consentimiento por cuenta para RCSB/UniProt. El
caso más agudo de esta auditoría se cerró (EVAL-BE-003), pero la política
transversal del §10 del plan sigue abierta.

**EVAL-SCI-012 · P0 · Corregido · SAR fabricaba ceros e identidad.**
La tabla SAR convertía scores y afinidades ausentes en `0`, calculaba deltas
contra esos ceros y declaraba similitud `1.0` cuando RDKit no podía calcularla.
Además, el frontend mostraba seis análogos ficticios sin una evaluación activa.
Ahora las métricas y similitudes no calculables viajan como `null`, los deltas
sólo existen si ambas corridas conservan la métrica, el cero real sigue siendo
válido y la vista no contiene datos demo. El texto declara correctamente
Tanimoto sobre el fingerprint topológico RDKit, no Morgan.

**EVAL-UX-013 · P1 · Corregido · Compartir receptor bloqueaba la aplicación.**
El selector usaba `alert()` para éxito y error, no daba feedback si el callback
de refresco no existía y permitía envíos repetidos. El resultado se anuncia
ahora dentro del modal mediante `status`/`alert` accesibles; el botón muestra
progreso y permanece deshabilitado mientras la solicitud está en curso.

---

## 3. Matriz de trazabilidad (campos científicos de la corrida)

`entrada UI → payload → esquema backend → cálculo → DB → respuesta → tipo TS → vista → export → reapertura`

| Campo | UI | payload | backend | DB | respuesta | TS | vista | dossier | reapertura |
|---|---|---|---|---|---|---|---|---|---|
| SMILES introducido | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| SMILES canónico | ✓ (preflight) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Receptor (PDB ID) | ✓ | ✓ | ✓ | ✓ | `target_name` | parcial | ✓ | ✓ | ✓ (caso) |
| Cadena | ✓ (preflight) | ✓ | ✓ | ✓ | — | ✓ | ✓ (caso) | ✓ | ✓ |
| Caja (centro/tamaño) | ✓ | ✓ | ✓ | ✓ (caso) | — | ✓ | ✓ | ✓ | ✓ |
| Hotspots | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Motor / exhaustividad / poses | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Semilla | preflight | ✓ | ✓ | `vina_random_seed` | ✓ | ✓ | ✓ | ✓ | ✓ |
| Versión del motor | — | — | ✓ | `vina_version` | ✓ | ✓ | ✓ | ✓ | ✓ |
| Conformaciones (K) | ✓ | ✓ | ✓ | `docking_protocol` | ✓ | ✓ | ✓ | ✓ | ✓ |
| Hash del receptor preparado | — | — | ✓ | `receptor_sha256` | ✓ | ✓ | ✓ | ✓ | ✓ |
| Afinidad y poses | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Evidencia estructural | — | — | ✓ | `structural_evidence` | ✓ | ✓ | ✓ | ✓ | ✓ |
| Selección de pose | — | — | ✓ | `pose_selection` | ✓ | ✓ | ✓ | ✓ | ✓ |
| Advertencias científicas | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Huella del preflight | ✓ | ✓ | ✓ | ✓ (caso) | — | ✓ | ✓ | ✓ | ✓ |

La cadena y la procedencia reproducible ya recorren todos los eslabones que les
corresponden. Las celdas `—` son datos no introducidos o no mostrados en esa
etapa, no pérdidas de contrato.

## 4. Qué se ejecutó

| Suite | Antes | Después |
|---|---|---|
| Backend (`pytest`) | 870 passed, 3 skipped | 927 passed, 3 skipped (+57 nuevas) |
| Frontend (`vitest run`) | 531 passed | 546 passed (+15 nuevas) |
| `tsc --noEmit` | limpio | limpio |
| `generate_openapi_contract.py --check` | **desactualizado** | vigente |
| `--diff` (incompatibilidades) | — | ninguna |

El snapshot OpenAPI estaba desfasado respecto del árbol de trabajo antes de
esta sesión; se regeneró con el script (no a mano) y ahora `--check` pasa.

## 5. Paquetes de escritura de esta sesión

| Paquete | Hallazgos | Archivos de producto |
|---|---|---|
| EVAL-P0-01 | EVAL-SCI-001 | `services/targets/resolution.py` (nuevo), `services/pipeline/runner.py`, `services/docking/queue_handler.py`, `services/docking/peptide_docking.py`, `db/repository.py` |
| EVAL-P0-02 | EVAL-SCI-002 | `services/docking/queue_handler.py` |
| EVAL-P0-03 | EVAL-BE-003 | `api/routers/evaluation_files.py` |
| EVAL-P1-04 | EVAL-BE-004 | `services/docking/recovery.py` (nuevo), `api/main.py` |
| BATCH-P0-05 | BATCH-SCI-001 | `api/routers/batch.py` |
| BATCH-P1-09 | BATCH-BE-002 | `api/routers/batch.py` |
| EVAL-P1-06 | EVAL-BE-005 | `api/routers/evaluation.py` |
| EVAL-P2-07 | EVAL-BE-007 | `services/docking/queue_handler.py` |
| EVAL-INT-08 | EVAL-INT-008 (vigilancia) | `frontend/lib/types.ts` (sólo anotaciones) |
| EVAL-INT-11 | EVAL-INT-006 | `api/routers/evaluation.py`, `frontend/lib/api.ts`, `frontend/components/evaluation/CaseEvaluationRunner.tsx` |
| EVAL-INT-12 | EVAL-INT-008 | `frontend/lib/types.ts`, `frontend/components/interfaces/pro/EvaluationEvidencePanel.tsx` |
| EVAL-FE-13 | EVAL-FE-009 | retiro de `frontend/context/EvaluationContext.tsx` y `frontend/components/interfaces/pro/ProResults.tsx`; `frontend/components/interfaces/pro/ProEvaluation.tsx` |
| EVAL-EFF-14 | EVAL-EFF-010 | `backend/api/routers/evaluation.py`, `backend/core/models.py` |
| EVAL-SCI-15 | EVAL-SCI-012 | `backend/api/routers/sar.py`, `frontend/components/interfaces/pro/ProSarTab.tsx` |
| EVAL-UX-16 | EVAL-UX-013 | `frontend/components/interfaces/pro/TargetSelectorModal.tsx` |

Ningún paquete cambia la semántica científica de un resultado válido: todos
retiran caminos que producían resultados inválidos, los sustituyen por un fallo
explícito, o cierran una superficie sin autorización.

## 6. Lo que falta para el Gate de Evaluación

Del gate del plan (§5), lo que **no** se puede declarar con esta sesión:

- [ ] **Corrida real** pequeña, offline y determinista con el motor
      empaquetado. No se ejecutó: requiere el entorno de escritorio, no la
      suite.
- [ ] **Persistencia comprobada** cerrando la app y reiniciando el backend
      contra una corrida real (la reconciliación está probada en unitario, no
      en el recorrido completo).
- [ ] **Dos cuentas en la misma máquina** ejercitadas en navegador sobre la
      corrida real (existe cobertura de contrato y un E2E de sesiones).
- [ ] **Resultado vivo = reabierto = dossier exportado** comparado campo a
      campo sobre una corrida real.
Los hallazgos automatizables de Evaluación registrados en este expediente
quedan cerrados, cada uno con una prueba que fallaba antes y pasa después. El
Gate sigue pendiente exclusivamente por las cuatro comprobaciones runtime
anteriores; no se declara verde hasta ejecutarlas.

## 7. Riesgos y trabajo no verificado

- **Cambio de comportamiento deliberado.** Una corrida contra un receptor que
  no se puede resolver ahora **falla** donde antes devolvía un resultado. Es la
  corrección, no un efecto secundario: el resultado anterior describía otra
  proteína. Un usuario sin red que dependiera sin saberlo de esa sustitución
  verá ahora un fallo explicable en vez de un número falso.
- **No se ejecutó el motor real.** Ninguna de las pruebas nuevas acopla con
  Vina. Las que tocan el pipeline sustituyen el cálculo pesado, como ya hacía
  la suite. El Gate de Evaluación sigue exigiendo una corrida real (§6).
- **`predict_early_exit` queda sin consumidores en el camino de ejecución.** La
  función y su grafo siguen existiendo para MolChat y análisis. Si alguien la
  reconecta, las guardas de código de
  `tests/test_early_exit_no_sustituye_la_corrida.py` fallarán.
- **`/evaluation/evaluate` y `/evaluation/batch` siguen publicados.** Se les
  cerraron los agujeros, pero ningún cliente del repositorio los usa. Retirarlos
  es un cambio de contrato y corresponde al propietario decidirlo.
- **El snapshot OpenAPI se regeneró** con `--write` porque ya estaba desfasado
  respecto del árbol de trabajo antes de esta sesión. `--diff` no detectó
  incompatibilidades.
- **Sin commit.** Todo queda en el árbol de trabajo, junto a los cambios
  previos del usuario, que se conservaron intactos.
