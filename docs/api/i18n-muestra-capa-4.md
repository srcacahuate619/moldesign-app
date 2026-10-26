# Muestra de revisión de la traducción · capa 4

Muestra aleatoria reproducible de 40 cadenas únicas traducidas en los diez ficheros de la capa 4. Semilla `20261004`; selección tomada de las cadenas que estaban pendientes en la línea base de la capa y ordenadas por texto fuente.

Revisión semántica completada por el agente: **0 errores de sentido en 40 cadenas**. Se comprobaron los límites de ejecución, la honestidad de los estados, las cautelas científicas, el glosario y la conservación de identificadores.

| # | Fichero | Línea | Español | English |
|---:|---|---:|---|---|
| 1 | `services/pipeline/runner.py` | 61 | El ensemble de {n1} conformaciones no se pudo generar ({n2}); la corrida sigue con una sola. | The ensemble of {n1} conformers could not be generated ({n2}); the run will continue with one. |
| 2 | `services/docking/preflight.py` | 1510 | Caja fuera de los límites de ejecución: lados entre {n1} y {n2} Å, centro finito entre -{n3} y {n4} Å. | Box is outside execution limits: sides must be between {n1} and {n2} Å, and the finite center between -{n3} and {n4} Å. |
| 3 | `api/routers/evaluation.py` | 827 | Suscribirse al flujo de eventos del pipeline (SSE) | Subscribe to the pipeline event stream (SSE) |
| 4 | `api/routers/evaluation.py` | 317 | Hay una etapa desconocida o no ejecutable | An unknown or non-executable stage is present |
| 5 | `chem/validator.py` | 359 | La molécula contiene {n1} fragmentos desconectados. En modo científico estricto se rechazan sales/mezclas para evitar ambigüedad en docking y scoring. | The molecule contains {n1} disconnected fragments. Strict scientific mode rejects salts/mixtures to avoid ambiguity in docking and scoring. |
| 6 | `services/docking/queue_handler.py` | 1664 | Evaluación interrumpida o cancelada | Evaluation interrupted or canceled |
| 7 | `services/docking/preflight.py` | 550 | No hay fuente en disco que comparar. Se calculará cuando la corrida la descargue. | No on-disk source is available for comparison. Its checksum will be calculated when the run downloads it. |
| 8 | `api/routers/evaluation.py` | 319 | El motor se declara en docking_engine, no en stage_params.docking.engine | The engine is specified in docking_engine, not in stage_params.docking.engine. |
| 9 | `services/docking/preflight.py` | 1506 | elegido por ti | selected by you |
| 10 | `services/docking/preflight.py` | 1535 | Sin el PDB de la ruta no se puede medir la relación geométrica entre la caja y el receptor; no se inventa. | Without the PDB used by this path, the geometric relationship between the box and receptor cannot be measured; no value is inferred. |
| 11 | `chem/validator.py` | 249 | Se detectaron {n1} doble(s) enlace(s) estereogenico(s) sin E/Z definida. El conformero 3D representara una geometria concreta; usa '/' y '\' en el SMILES para declarar el isomero deseado. | {n1} stereogenic double bond(s) have undefined E/Z configuration. The 3D conformer will represent one specific geometry; use '/' and '\' in SMILES to specify the desired isomer. |
| 12 | `services/docking/preflight.py` | 1273 | Ruta de docking comprobable | Docking path that can be checked |
| 13 | `api/routers/evaluation_dossier.py` | 61 | Dossier de caso | Case dossier |
| 14 | `services/docking/preflight.py` | 1852 | No evaluado: la ruta no conserva un mapa de huecos del receptor preparado. | Not evaluated: this path does not retain a gap map for the prepared receptor. |
| 15 | `services/docking/preflight.py` | 532 | El PDB de {n1} todavía no está en disco y no se pudo sellar su contenido. | The PDB for {n1} is not on disk yet, so its contents could not be hashed. |
| 16 | `api/routers/evaluation_cohort_runs.py` | 377 | Última corrida durable de una cohorte | Most recent durable run for a cohort |
| 17 | `services/docking/preflight.py` | 1346 | Open Babel {n1} presente con el hash declarado ({n2}, sha256 {n3}…). No se ejecutó para comprobarlo: esta comprobación previa no lanza procesos. | Open Babel {n1} is present with the declared hash ({n2}, SHA-256 {n3}…). It was not run for verification: this preflight does not launch processes. |
| 18 | `api/routers/evaluation.py` | 311 | La etapa openmm está retirada: sobrescribía poses y no ejecutaba OpenMM. | The openmm stage is retired: it overwrote poses and did not run OpenMM. |
| 19 | `services/docking/preflight.py` | 1663 | El protocolo que puede ejecutarse viaja en pipeline_config: las puertas de ejecución no llevan esos campos de nivel superior. Declararlos como efectivos firmaría una corrida que no ocurriría; para cambiar el protocolo hay que declararlo en stage_params. | The executable protocol is carried in pipeline_config; execution gates do not use those top-level fields. Declaring them as effective would attest to a run that would not occur. To change the protocol, declare it in stage_params. |
| 20 | `services/docking/preflight.py` | 782 | El receptor preparado carece del resumen de plantillas de Meeko. | The prepared receptor has no Meeko template summary. |
| 21 | `api/routers/evaluation_cohorts.py` | 226 | Comprobación previa de una cohorte (no ejecuta docking ni la persiste) | Preflight a cohort (does not run docking or persist it) |
| 22 | `services/pipeline/runner.py` | 846 | Error en stage | Error in stage |
| 23 | `services/docking/preflight.py` | 568 | El filtrado de la cadena falló, así que no hay preparado con el que comparar. | Chain filtering failed, so there is no prepared receptor to compare. |
| 24 | `services/docking/queue_handler.py` | 1650 | Evaluación cancelada o interrumpida | Evaluation canceled or interrupted |
| 25 | `chem/validator.py` | 168 | La molécula contiene {n1} — AutoDock Vina no tiene parámetros confiables para estos elementos. | The molecule contains {n1} — AutoDock Vina has no reliable parameters for these elements. |
| 26 | `api/routers/evaluation_cohort_runs.py` | 400 | Estado, progreso, configuración efectiva, procedencia y filas | Status, progress, effective configuration, provenance, and rows |
| 27 | `services/docking/queue_handler.py` | 1041 | Índice cuántico no evaluado: faltan descriptores xTB verificables. | Quantum index not evaluated: verifiable xTB descriptors are missing. |
| 28 | `chem/validator.py` | 110 | El SMILES no puede estar vacío | SMILES cannot be empty |
| 29 | `api/routers/evaluation.py` | 131 | QuickVina 2 no está habilitado para evaluaciones en esta versión. El backend rechaza la selección antes de encolar la corrida. | QuickVina 2 is not enabled for evaluations in this version. The backend rejects the selection before enqueueing the run. |
| 30 | `services/docking/preflight.py` | 1610 | services.docking.search_policy · tamaño efectivo de caja | services.docking.search_policy · effective box size |
| 31 | `services/docking/preflight.py` | 1774 | hotspots del catálogo · cadenas del receptor filtrado | Catalog hot spots · filtered receptor chains |
| 32 | `chem/validator.py` | 233 | Carga formal neta extrema ({n1}). Máximo permitido: ±{n2}. | Extreme net formal charge ({n1}). Maximum allowed: ±{n2}. |
| 33 | `services/docking/preflight.py` | 1208 | {n1} otros heteroátomos (ligandos, lípidos, aditivos) | {n1} other heteroatoms (ligands, lipids, additives) |
| 34 | `api/routers/evaluation.py` | 1019 | Leer SVG de atención GNN on-demand (UI-7, fuera del polling) | Read a GNN attention SVG on demand (UI-7, outside polling) |
| 35 | `api/routers/evaluation.py` | 368 | Lista de hotspots seleccionados por el usuario | List of user-selected hot spots |
| 36 | `services/docking/preflight.py` | 775 | El template elegido está registrado; el microestado experimental no está validado. | The selected template is recorded; the experimental microstate has not been validated. |
| 37 | `api/routers/evaluation.py` | 510 | La evaluación falló; consulta el estado de la tarea para más detalles. | The evaluation failed; check the task status for more details. |
| 38 | `services/docking/queue_handler.py` | 113 | Cancelado por el usuario | Canceled by the user |
| 39 | `services/docking/preflight.py` | 428 | Elementos sin parámetros fiables en Vina: {n1}. | Elements without reliable Vina parameters: {n1}. |
| 40 | `services/docking/preflight.py` | 718 | Existe un receptor preparado compatible con la cadena '{n1}' y {n2} átomos. | A prepared receptor with chain '{n1}' and {n2} atoms is available. |
