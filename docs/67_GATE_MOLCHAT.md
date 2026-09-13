# Gate de MolChat — APROBADO con dos hallazgos abiertos declarados

**Fecha:** 2026-08-31
**Estado:** 🟢 aprobado para el alcance de cierre vertical, con dos exclusiones nombradas
**Suite adversarial:** `backend/tests/test_gate_molchat_adversarial.py`
**Expediente:** [66_MOLCHAT_AUD_00_EXPEDIENTE.md](66_MOLCHAT_AUD_00_EXPEDIENTE.md)

## Qué exige el gate y qué se comprobó

El §8 del [plan de cierre](61_PLAN_CIERRE_APP_ORQUESTACION_CLAUDE.md) fija cuatro
criterios. Ninguno se da por bueno por lectura: cada uno tiene su prueba, y cada
prueba se escribió **en rojo** contra el código anterior.

### 1. Suite adversarial

| Frente | Qué se intenta | Desenlace exigido |
|---|---|---|
| Prompt injection | Que el texto del turno —incluido el que llega de PubChem, ChEMBL o RCSB— consiga una llamada a herramienta con la identidad de otra cuenta | La identidad la impone el servidor; la que venga en los argumentos se descarta siempre |
| Fuga entre usuarios | Leer conversación, índice FTS, catálogo de evaluaciones o configuración de proveedor de otra cuenta | Nada de otra cuenta, y borrar lo ajeno no borra nada |
| Tool calls inválidos | Herramienta inexistente, argumento que no existe, SMILES alucinado | El turno sobrevive y **no produce número**: abstención |
| Alucinación | Afirmar un valor químico sin herramienta que lo respalde | Se marca; un valor que sí calculó una herramienta, no |

**18 pruebas, todas verdes.** El frente de prompt injection encontró un fallo
real, descrito abajo.

### 2. Conversación y configuración reaparecen sólo para su propietario

Cubierto por `test_conversaciones_por_cuenta.py`, `test_proveedor_por_cuenta.py`,
`test_memoria_ia_por_cuenta.py` y la sección de fuga del gate. Se comprobó en
las cinco superficies que guardan estado de cuenta: conversaciones, índice FTS de
mensajes, catálogo `ai_catalog`/`ai_details`, almacén cifrado de proveedor y
consentimientos de destino.

### 3. Cero llamadas remotas sin consentimiento verificable

MOLCHAT-NET-005 ya exigía consentimiento por cuenta y por destino para el turno.
**El gate encontró la excepción:** `pubchem_autolookup` salía a PubChem en cada
turno cuyo mensaje nombrara un fármaco conocido, sin mirar `allow_web` y sin
pasar por el consentimiento. Corregido: depende del mismo interruptor que el
resto de las herramientas de red, y el camino offline vuelve a ser inequívoco,
que es lo que el §8 pide.

Queda declarado como **no cubierto**: el consentimiento sigue siendo por destino
del proveedor de chat, no por destino de cada herramienta. `allow_web` es un
interruptor, no un permiso por host. Es la misma política transversal que
TRANS-NET-001 dejó abierta para RCSB/UniProt.

### 4. Toda afirmación específica enlaza a datos persistidos o se etiqueta

Cubierto por `test_clasificacion_epistemica_de_respuestas.py`. Cada herramienta
declara en su contrato qué clase de respuesta produce —cálculo, dato persistido,
inferencia, recuperación externa, explicación— y su procedencia; el bloque que se
inyecta en el turno lo imprime; el prompt permanente obliga a conservar la
distinción; y la interfaz separa la evidencia de la prosa del modelo con la clase
y la fuente a la vista. Una herramienta sin clase declarada rompe la suite.

## Fallos descubiertos y corregidos por el gate

1. **Prompt injection podía elegir de quién era el historial.**
   `execute_tool_step` ejecutaba los argumentos tal como venían en la respuesta
   del modelo, y varias herramientas aceptan `user_id`. El turno de MolChat lleva
   dentro texto de terceros, así que bastaba con que ese texto consiguiera una
   línea `🛠️ query_evaluation_details | user_id=<otra cuenta>` para leer el
   historial ajeno: la fuga que MOLCHAT-BE-004 cerró, reabierta por la puerta del
   modelo. La identidad se borra siempre de los argumentos y la repone el
   servidor; sin sesión se pasa vacía, que las herramientas ya tratan como «no
   leo el historial de nadie» (D-05).
2. **Una llamada remota sin autorizar en cada turno** (criterio 3, arriba).
3. **Dos negativos fabricados.** `check_druglikeness` contestaba «Sin alertas
   PAINS» cuando el catálogo PAINS no había podido cargarse, y
   `explain_fragments` reportaba «Fragmentos BRICS: 0» cuando la fragmentación
   había fallado. Fabricar un negativo está tan prohibido como fabricar un
   positivo, y es peor de detectar: nadie sospecha de una buena noticia.
4. **El turno que fallaba no dejaba rastro.** `sendMessage` hacía
   `if (!res.ok) return;`: los motivos accionables que esta pestaña añadió al
   backend —403 sin consentimiento, 503 si el historial local no acepta
   escribir— morían ahí, y el borrador se perdía. Ahora el motivo se muestra, el
   borrador vuelve y hay reintento con el mismo snapshot, que es lo que lo hace
   idempotente.

## Hallazgos abiertos que el gate declara y no cierra

**MOLCHAT-BE-009 · P1 · `molgraph.db` no tiene dimensión de cuenta.** La tarea 3
nombraba tres almacenes —`ai_catalog`, `ai_details` y el índice FTS— y los tres
quedaron cerrados. Auditándolos apareció un cuarto: `services/ai/molgraph.py`
registra cada evaluación de cualquier cuenta (`add_evaluation_node`, llamado
desde `queue_handler`) en un grafo de máquina sin `user_id`, y siete herramientas
de MolChat lo leen. **No se ha medio arreglado a propósito.** El identificador
de nodo es `mol_<smiles>`, compartido entre cuentas, y `add_evaluation_node`
sobrescribe `properties_json` con la última evaluación: filtrar sólo la lectura
dejaría a una cuenta pisando el score de otra y además ocultándolo, que es peor
que el estado actual. Cerrarlo exige rediseñar la identidad de nodo, y eso abre
una decisión del propietario.

**D-10 · ¿Qué es MolGraph: corpus compartido o memoria por cuenta?** El producto
distribuye `molgraph_seed.db`, un corpus público de referencia que la aplicación
copia en el primer arranque. Las filas existentes sin dueño son una mezcla
indistinguible de ese corpus y de evaluaciones que hizo quien ya usó la máquina.
No se les puede asignar propietario por suposición —mismo criterio que D-07 y
que MOLDEX-SCI-001—, y borrarlas destruiría la referencia de la que depende
`suggest_smiles`. Las opciones son: (a) marcar el seed al copiarlo y tratar lo no
marcado como privado sin dueño; (b) declarar todo el grafo corpus compartido y
dejar de escribir en él las evaluaciones de las cuentas; (c) partirlo en dos
bases. Ninguna es un arreglo de una línea.

## Trabajo no verificado

- **El gate es de suite, no de runtime.** Evaluación y Batch pasaron su gate
  ejecutando Vina/Meeko reales ([63](63_GATE_RUNTIME_EVALUACION.md),
  [64](64_GATE_RUNTIME_BATCH.md)). Aquí no se ejecutó una conversación real
  contra un modelo cargado: MolChat depende de un modelo local descargado o de
  una clave de proveedor, y ninguna de las dos cosas está en este entorno. Lo
  que se comprueba es el contrato y las defensas, no la calidad de las
  respuestas de un modelo concreto.
- **La evaluación en segundo plano de D-08 no se corrió de extremo a extremo.**
  `run_docking` entra por `registrar_corrida`, la misma puerta que
  `/evaluation/submit`, y eso está cubierto por prueba; lo que falta es lanzar
  una desde el chat con el motor real y leerla después con
  `check_docking_status`. Se cubre al ejecutar el gate runtime de la pestaña.
- **El reintento idempotente se prueba por estructura, no por render.**
  `AIContextTurnoFallido.test.ts` fija que `retryLastTurn` reejecuta el mismo
  snapshot y que ni él ni `ejecutarTurno` añaden el mensaje del investigador —lo
  que hace idempotente al reintento—, y `motivoDeTurno.test.ts` prueba de verdad
  el mensaje accionable. Es la convención que ya seguían `AIContextAuth` y
  `AIContextConsentimiento`: montar `AIProvider` entero en vitest exige backend,
  sesión y `getApiUrl`, y en este entorno cuelga la recolección del runner. Falta
  una prueba de render que ejercite el clic de «Reintentar».
- **El snapshot OpenAPI no se regeneró.** Ya estaba desactualizado antes de este
  trabajo, y su única incompatibilidad —`GET /evaluation/limit-status`, retirado
  por TRANS-ANON-002— exige `--write --allow-breaking`, que es una decisión del
  propietario y de un paquete anterior. Lo que este trabajo añade al contrato es
  aditivo: `maxLength` en `ChatMessage.content` y `maxItems` en
  `AIChatRequest.messages`.

## Verificación automatizada

- suite adversarial del gate: **`18 passed`**;
- suites propias de MolChat (`ai_endpoints`, conversaciones, proveedor,
  consentimiento, paridad, docking desde el chat, persistencia, memoria por
  cuenta, clasificación epistémica, higiene): verdes;
- backend completo: **`1253 passed`** con el intérprete de desarrollo y
  **`1215 passed, 3 skipped`** con `python-embed`, el que se distribuye. La
  diferencia eran 36 pruebas del contrato del dossier que se saltaban por falta
  de `pypdf`; ver [68](68_GATE_RUNTIME_MOLDEX_Y_MOLCHAT.md) y
  `docs/api/test-counts.json`, que ahora se genera;
- frontend completo: **`638 passed`** en 66 archivos;
- TypeScript: `tsc --noEmit`, limpio;
- `py_compile`: limpio.
