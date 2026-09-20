# Auditoría de backend — 2026-09-17

Alcance: backend únicamente. Barrido AST de 236 módulos Python de producción
(90 160 líneas, incluidos scripts y sidecars) y 186 archivos de pruebas.
El barrido no equivale a una revisión manual línea por línea: se revisaron en
detalle las fronteras HTTP, almacenamiento, transacciones y ejecución de evaluaciones.
No es una certificación del instalador ni de Microsoft Store.

## Diagnóstico previo a cambios

| ID | Severidad | Hallazgo y condición |
|---|---|---|
| H01 | ALTO | `get_db`/`get_db_session`: rollback seguido de commit vacío puede ocultar pérdida de escrituras tras bloqueo SQLite; reintentar flush sobre sesión inválida tampoco recupera la operación. |
| H02 | ALTO | `local_storage.path_for` no confina las rutas; escritura directa trunca el archivo anterior si falla o se interrumpe. El escape requiere una ruta no confiable que llegue al almacén; no se afirma explotación HTTP universal. |
| H03 | ALTO | Meeko receptor/ligando, xTB y AD4 esperan `communicate` sin límite. Vina y conversores con timeout no limpian al cancelar la coroutine. |
| H04 | ALTO | Watchdog sólo cambia memoria; no cancela el cálculo ni libera capacidad. Cancelación del usuario tampoco detiene el pipeline principal. PRO propaga errores sin cerrar necesariamente el estado de la molécula. |
| H05 | ALTO | Se vuelve a leer el receptor mutable después de calcular su hash: otra preparación puede cambiar los bytes antes de Vina. |
| H06 | ALTO | Entradas de caja aceptan NaN/infinito y tamaños no positivos. Cohortes leen el upload entero antes de aplicar su límite. |
| H07 | ALTO | Corridas simultáneas de la misma molécula usan la misma proyección mutable; auxiliares post-hoc escriben por molecule_id sin verificar task_id. |
| H08 | MEDIO | Logs Vina imprimen exhaustiveness/num_modes por defecto, aunque se usaron overrides. |
| H09 | MEDIO | Operaciones nativas RDKit/PoseBusters/ML en hilos no tienen aislamiento terminable; cancelar asyncio no detiene un hilo nativo bloqueado. |
| H10 | MEDIO | Batch legacy y registro inicial del dispatcher viven en memoria; los snapshots durables aparecen después. Reinicio pierde configuración de trabajos que no llegaron a persistir. |
| H11 | MEDIO | Cirugía estructural convierte algunos errores en valores vacíos/caja por defecto. Corregirlo requiere revisar consumidores y contrato científico; se reserva. |
| H12 | MEDIO | Descargas opcionales dependen de reintentos/timeouts del SDK; procesos con PIPE acumulan salida en memoria. Falta prueba de corte abrupto de toda la aplicación y sus descendientes. |
| H13 | BAJO | Comentarios de serialización dicen una evaluación pero la constante permite cuatro; logging y contextos tienen inconsistencias de diagnóstico. |

No se ha demostrado un hallazgo CRÍTICO en la inspección inicial.

## Frontera científica

Se conservan scores, pesos, semillas, selección de poses, protonación,
tautomería, reconstrucción de hidrógenos, parámetros de PoseBusters ni protocolos.
Los límites de ejecución son operativos: una ejecución que antes podía esperar
indefinidamente ahora debe fallar. No se recortan moléculas ni se sustituyen
resultados científicos al alcanzar un límite. Tampoco se activan motores.

Excepciones autorizadas explícitamente por el usuario: MM-GBSA exige la pose
acoplada y se abstiene si falta/es inválida; también se abstiene si falla una
energía de subsistema. Se eliminan los fallbacks científicos defectuosos, no
se cambian fórmulas, cargas, force fields ni parámetros de minimización.
Resultados históricos obtenidos desde SMILES o con una energía sustituida
por cero no se consideran comparables ni se reescriben.

## Correcciones y evidencia

| Hallazgo | Corrección | Verificación |
|---|---|---|
| H01 | Los contextos SQLite propagan el fallo y revierten. `flush_with_retry`/`commit_with_retry` conservan sus nombres públicos, pero no repiten una transacción inválida. `_run_mini_tx` conserva el retry de operación completa en otra sesión. | Dos conexiones SQLite reales: una mantiene `BEGIN IMMEDIATE`; el commit de la otra falla, no anuncia éxito vacío. Después se escribe correctamente en una sesión nueva. Regresiones de migración y lifecycle. |
| H02 | `path_for` rechaza rutas absolutas, unidades Windows, traversal, NUL, streams NTFS y escapes resueltos. Escritura a temporal vecino, fsync y replace atómico; limpieza del temporal si falla. | Diez variantes iniciales y cinco adicionales de alias/dispositivos Windows; fallo inyectado en publicación conserva los bytes anteriores y no deja `.writing-*`; roundtrips existentes. No se afirma protección contra un atacante local que cambie junctions simultáneamente. |
| H03 | Helper común drena stdout/stderr, limita tiempo y limpia hijos y descendientes al cancelar/expirar. Meeko receptor/ligando, xTB y AD4 reciben límite de 600 s. Vina mantiene 600 s; export Meeko mantiene 60 s; Open Babel y auxiliares mantienen sus límites anteriores. Se añaden flags sin ventana donde faltaban. | Subprocesos Python reales: timeout, cancelación, nieto, salida por ambos pipes de 200 KB y exit 7 con stderr. Contratos Open Babel y suite existente. No es una prueba de todas las herramientas reales bloqueadas. |
| H04 | El dispatcher guarda la tarea asyncio y su molecule_id; cancelación y watchdog cancelan el cálculo, registran FAILURE, emiten pipeline_error y liberan el permiso. La espera del semáforo no deja un hilo capaz de adquirirlo después de cancelar. Fallos de memoria auxiliar no invalidan un éxito persistido. Snapshot y estado EVALUATED de PRO se confirman juntos. | Watchdog acelerado con pipeline bloqueado; cancelación esperando turno no roba capacidad; pruebas existentes de cancelación, snapshots y recuperación tras reinicio. Un caso adicional verifica el fallo temprano al reevaluar una molécula con proyección anterior, y que un fallo tardío no cierre al nuevo dueño. |
| H05 | Vina materializa siempre los bytes capturados antes del hash, sin volver a leer el receptor mutable. | Preparación simulada reemplaza el receptor después del hash; el ejecutor recibe los bytes originales y el hash coincide. |
| H06 | Submit y preflight rechazan cajas no finitas o no positivas, sin imponer nuevas dimensiones científicas. Handler de validación serializa NaN/Infinity del error como texto para devolver 422. Cohortes leen sólo límite+1; batch limita lectura a 20 MiB y devuelve 413. | Validación parametrizada de ambos modelos; error JSON no finito; lector de cohorte comprueba el tamaño solicitado; regresiones API y batch. El límite ASGI añadido después se describe en la segunda fase. |
| H07 (parcial) | Exclusión cross-loop por SMILES de entrada en los dos ejecutores principales. Auxiliares MM-GBSA/selectividad verifican task_id antes de escribir sobre la proyección. Cada ejecución Vina nueva guarda artefactos en una subcarpeta UUID bajo la huella existente; la clave de caché no cambia y las rutas antiguas siguen legibles. | Misma entrada se serializa, otro ligando avanza, cancelar un waiter limpia el lock. Dos redock conservan ambos artefactos. Persistencia/historial/snapshots existentes. La segunda fase impide dos backends sobre el mismo almacén; permanecen pendientes otros endpoints PRO independientes. |
| H08 | Log Vina registra exhaustiveness, num_modes y seed efectivos, incluidos overrides. | Revisión de los argumentos y el log; contratos de protocolo y corridas doradas. |
| H13 | Comentarios del dispatcher describen cuatro slots y un límite total, sin prometer un heartbeat que no se medía. Se elimina el helper de fallo fire-and-forget que ya no tenía llamadores. | Revisión del diff y compilación. |
| H16 (ALTO) | El endpoint de complejo aplica acceso al receptor y no intenta consultar RCSB con identificadores privados cuando falta el archivo local. | Receptor privado ausente devuelve 404 sin llamar a la función de descarga; regresiones de entrega de archivos. |

Los archivos de evidencia ya existentes no se migraron ni borraron. La segunda fase añade en schema v21 una tabla exclusivamente operativa
`evaluation_requests`: configuración solicitada, propietario, estado y error
antes de encolar. No se altera el esquema científico de resultados. La subcarpeta por ejecución distingue
identidad de configuración de identidad de artefacto; no altera sus coordenadas.
La serialización por ligando puede reducir throughput cuando se evalúa repetidamente
el mismo SMILES. No ofrece garantía FIFO.

## Hallazgos restantes

**ALTO — H07, endpoints PRO independientes.** Los ejecutores principales
ahora archivan toda la proyección antes de comenzar otra corrida, sin modificar
snapshots previos. MM-GBSA (también bajo demanda) y el auxiliar de selectividad
actualizan mediante `UPDATE ... WHERE task_id = ...`; otra instancia del backend
no puede iniciar sobre el mismo almacén. Todavía quedan escrituras independientes
de selectividad/ADMET y el guardado manual de selectividad desde el cliente que
no aportan una identidad de corrida al contrato. No se presenta este trabajo
como aislamiento completo de todas las superficies. El guardado tardío enviado
por un cliente requiere coordinar el contrato con el frontend, fuera del alcance
exclusivo de este cambio.

**MEDIO — H09.** RDKit, Dimorphite-DL, PoseBusters y ML/GNN ejecutan parte del
trabajo en proceso/hilos. El watchdog puede cerrar el estado asyncio, pero no
interrumpir un hilo nativo colgado. Separarlos en workers terminables exige
verificar transporte de objetos, versiones y paridad de resultados.

**MEDIO — H10.** La solicitud normal ya guarda configuración y propietario
antes de encolar, y registra fallos de aceptación y estados terminales. El polling
puede recuperar una solicitud interrumpida sin resultado. Batch legacy sigue
manteniendo el resumen y sus filas en memoria; su recuperación tras reinicio
no está resuelta. Cohortes sí tienen persistencia y reconciliación propias.

**MEDIO — H11.** `dynamic-box` ya devuelve 422 ante un ligando sin geometría
y 503/500 ante dependencia ausente/error; las coordenadas válidas mantienen
exactamente la misma fórmula. Los demás endpoints de cirugía todavía pueden
devolver defaults. En `/prepare`, un MolBlock generado desde SMILES se guarda
con extensión `.mol2` y entra en un parser MOL2; además, el receptor devuelto
puede apuntar al temporal que se elimina en `finally`. Revisar esta preparación
en conjunto, con evidencia estructural, antes de sustituir decisiones de caja
o cadena. No se cambió ese protocolo automáticamente.

**MEDIO — H12.** Se limitan stdout/stderr a 32 MiB por pipe; el exceso falla y
termina el proceso, no se acepta una salida truncada. HTTP limita 32 MiB antes
del parser, incluso sin Content-Length, con 30 s para recibir el cuerpo y spool
a disco desde 1 MiB. Excel limita expansión a 80 MiB, 2000 entradas ZIP,
10000 filas de datos y 256 columnas. Siguen pendientes cuota global de
artefactos, descargas opcionales dependientes del SDK y contención de hijos
ante muerte abrupta del backend (Windows Job Objects). El bloqueo de almacén
sí se ha probado tras muerte abrupta; eso no demuestra terminación de sus hijos.

**MEDIO — H15, fallo existente de suite fuera de alcance.**
`test_peptido_abstencion_negativa.py::test_la_interfaz_dice_lo_que_si_hace` exige
las cadenas literales `no soportada` y `plegamiento` en
`frontend/components/interfaces/pro/DockingEnginePanel.tsx`. Falló en la suite
completa; ambas cadenas también están ausentes en HEAD y el archivo coincide con HEAD; el frontend no se modificó. Se debe
revisar por separado si la explicación de producto o el test están desactualizados.

**BAJO.** Los diagnósticos tienen aún formatos heterogéneos. Conviene uniformar
identificador de corrida, etapa, motor, returncode y duración sin registrar
secretos ni archivos moleculares completos. Dos F841 existentes en api/main.py
quedan fuera de esta corrección; Ruff de los módulos nuevos y utilidades tocadas
no reporta errores.

## Cobertura de inspección

- FastAPI: routers, validación, errores globales, submit/preflight, polling/SSE,
  cancelación, uploads, acceso de cuentas y entregas de archivos.
- Herramientas: todos los lanzamientos async encontrados por AST; Vina, Meeko,
  Open Babel, MM-GBSA, selectividad, xTB, AD4; lectura del sidecar ESMFold y
  supervisores de motores/LLM. No se activaron motores dormidos.
- Química/ML: revisión de límites de ejecución y degradación de propiedades,
  conformeros, Dimorphite, evidencia estructural/PoseBusters, rescoring y CL-GNN;
  sin recalibración ni cambios en implementación científica.
- Persistencia: sesiones, retry, migración aditiva, deduplicación, proyecciones,
  snapshots, reconciliación de evaluaciones y cohortes.
- Offline: preflight sin red, estructuras cacheadas, inventario de modelos,
  descargas opcionales y tratamiento de dependencias ausentes. No se simuló
  una instalación limpia completa desconectada ni un fallo de todos los modelos.
- Seguridad: rutas de archivos, subprocesses con argv (no se encontró shell=True
  en el barrido de producción), límites de entrada y propiedad de receptores.
  No se afirma haber hecho fuzzing exhaustivo ni auditoría jurídica.

## Tests ejecutados

1. Suite enfocada inicial, Python 3.14 local: **94 passed**.
2. Suite completa backend con **python-embed/python.exe**: **2310 passed,
   10 skipped, 1 failed**, 270.95 s. El fallo es H15; no se ocultó ni se cambió
   el test para hacerlo pasar. Esta ejecución precedió a los últimos ajustes.
3. Regresión después de esos ajustes, runtime embebido: **208 passed**, 30.66 s.
   Incluye API, batch, archivos, SQLite, cancelación, Open Babel, protocolos y
   corridas doradas.
4. Archivo nuevo final `test_production_hardening.py`: **33 passed**, 4.65 s,
   runtime embebido. Incluye las dos últimas pruebas de receptor/artefactos y
   receptor privado sin red.
5. Último ajuste de ownership de fallos + regresiones del dispatcher y reconciliación: **56 passed**, 5.07 s, runtime embebido. El archivo nuevo contiene ahora **34 casos** (incluidos en esta ejecución).
6. `compileall`, `git diff --check` y Ruff focalizado. Sólo se editaron archivos
   bajo backend; `dossier_jelous.pdf` era un archivo no rastreado previo y no se tocó.

Logs locales (no versionados por las reglas existentes):
`backend/hardening-full-tests.log`, `backend/hardening-final-tests.log` y
`backend/hardening-new-tests.log` y `backend/hardening-lifecycle-final.log`. No se construyó ni publicó un instalador.
No se ejecutó smoke:prod: no se tocó empaquetado, CSP ni estilos.

## Segunda fase: cambios adicionales y verificación

| Problema / causa | Cambio | Verificación |
|---|---|---|
| ALTO H14: ruta lógica interpretada respecto al cwd; fallback desde SMILES | Ambos ejecutores resuelven con `path_for`; wrapper y motor se abstienen sin pose válida. JSON declara `not_evaluated`, valor nulo y motivo; logs separan error de resultado. | SDF real leído por RDKit; coordenadas y max_iter exactos entregados al motor doble; pose ausente/malformada; motor ausente; NaN/Inf; subprocess real sin pose. |
| ALTO H18: fallo de construcción del subsistema convertido en energía 0 | `_compute_isolated_fast` propaga el fallo; no se fabrica ΔG. Autorizado por el usuario. | Fallos inyectados de eliminación topológica y force field; ambos rechazan el resultado. No se validó el rendimiento científico de MM-GBSA. |
| MEDIO: MM-GBSA HTTP no era terminable; temporales sobrevivían a errores | Endpoint usa proceso con 300 s y limpieza del árbol; receptor temporal se elimina en finally, incluso si falla su preparación. | Proceso real; guardia del endpoint; fallo de preparación sin temporales restantes; regresiones de persistencia. |
| ALTO H07: None conserva scores opcionales de otra corrida | Inicio explícito archiva la proyección completa y reinicia sólo la proyección; conserva id/molecule_id y los archivos. Una reentrada con el mismo task_id conserva sus etapas. | SQLite real: snapshot con scores/sello/evidencia/ruta; rollback revierte archivo y reinicio; identidad e idempotencia preservadas. |
| ALTO H07: comprobación de task_id seguida de escritura vulnerable a carrera | UPDATE condicional para MM-GBSA HTTP/background y selectividad subprocess. | Dos sesiones SQLite, una con objeto viejo: no puede sobrescribir la corrida nueva; el dueño actual sí escribe. |
| ALTO: segunda instancia marca como interrumpidos trabajos vivos | Bloqueo de sistema operativo por almacén antes del lifespan/reconciliación. | Exclusión local y entre procesos; almacén distinto permitido; liberación tras matar el proceso propietario. No añade imports científicos al arranque. |
| MEDIO H10: configuración perdida antes del primer resultado | Tabla operativa evaluation_requests, commit antes del enqueue, recuperación de propietario/error y fallo de encolado durable. | Commit fallido no llama al dispatcher; rollback posterior no pierde aceptación; fallo de dispatcher permanece en SQLite; regresiones de migración/API/estado. |
| ALTO H17: batch no propaga propietario y acepta un retorno con error como éxito | Propietario pasa a cada evaluación; ALL filtra receptores accesibles; error explícito es fallo; la proyección debe corresponder al task_id. Límite por evaluación de 1200 s. | Batch con error+molecule_id nunca toma éxito previo y conserva owner; contratos batch y aislamiento de cuentas. |
| MEDIO H12: archivos malformados y expansión excesiva | CSV sin celdas no causa 500; columnas sobrantes/etiqueta inválida dan 400; Excel se recorre por filas, se cierra en finally y limita expansión. Límite HTTP antes de multipart. | ZIP de 81 MiB rechazado antes del parser; Excel válido/corrupto; CSV truncado/excedente; cuerpo chunked rechazado antes de la app; replay idéntico y timeout 408. |
| MEDIO H11: caja por defecto tras error de parseo | Error explícito sin cambiar la fórmula válida. | Ligando inválido da 422; SDF de coordenadas conocidas conserva centro (4,3,4), spans (6,2,2) y tamaño 14. |

Regresiones de esta fase (runtime embebido):
- MM-GBSA y contratos existentes: **36 passed**.
- Worker MM-GBSA, fallo de subsistemas y persistencia: **26 passed**.
- Batch, entradas y propiedad de escrituras: **38 passed**.
- Límites de procesos y exclusión del almacén: **37 passed**.
- Límite HTTP y compatibilidad API/batch: **20 passed**.
- Solicitudes durables, lifecycle, SQLite y API: **39 passed**.
- Caja estructural válida/inválida: **2 passed**.
- Última regresión de solicitudes, batch, MM-GBSA, proyección y dispatcher: **78 passed**.
- Topología SDF real y autorización legacy/durable: **23 passed**.
- Rutas Windows, almacenamiento y entrega de archivos: **57 passed**.
- Primera suite global de esta fase: **2334 passed, 10 skipped, 2 failed**.
  Uno es H15 (frontend preexistente). El otro era un doble de repositorio que
  no implementaba las operaciones nuevas; se amplió conservando la comprobación
  original de que la ruta llega a propiedades fuera del event loop.

Suite global verificada después de corregir los dobles de pruebas:
**2350 passed, 10 skipped, 1 failed**, 268.04 s, runtime embebido.
El único fallo es H15, que inspecciona texto del frontend preexistente; no se
modificó ni se omitió esa prueba. Los últimos casos adicionales de topología y
rutas Windows están cubiertos por las regresiones focalizadas de 23 y 57 pruebas.

Los conteos focalizados se solapan; no deben sumarse como pruebas distintas.
Logs: `hardening-mmgbsa.log`, `hardening-mmgbsa-worker.log`,
`hardening-round2.log`, `hardening-projection.log`,
`hardening-process-limits.log`, `hardening-http-limits.log`,
`hardening-durable.log`, `hardening-surgery.log`, `hardening-final-full.log`,
`hardening-last-regression.log`, `hardening-final-contracts.log`,
`hardening-windows-paths.log`, `hardening-verified-full.log`.
Ruff focalizado y compileall sin errores; `git diff --check` limpio.

## Recomendación para 1.0.1

1. Cerrar las escrituras PRO restantes y acordar identidad de corrida en los
   guardados tardíos del cliente. No anunciar aislamiento completo mientras H07
   siga abierto.
2. Aislar las etapas nativas en workers terminables con pruebas de paridad, y
   persistir el estado/resumen de batch legacy. Validar cierre forzado y descarga
   offline fallida con límites reales.
3. Revisar el contrato de cirugía estructural, especialmente `/prepare`, antes
   de usar defaults o ligandos regenerados para decisiones de caja/cadena.
4. Revisar resultados históricos afectados por los fallbacks MM-GBSA eliminados;
   no convertir resultados antiguos silenciosamente ni dar por validado el motor.
5. Cuando se autorice una release, verificar el artefacto instalado en Windows
   limpio (Vina real, offline, Unicode, disco lleno, cancelación y reapertura).
   No se hizo build, instalación ni publicación en esta tarea.

Los riesgos restantes están abiertos: esta auditoría no acredita ausencia total
de fallos ni da por cerrado todo el hardening de producción.


## Continuación: selectividad PRO y revisión de MM-GBSA (2026-09-17)

**1.0.1 permanece abierta.** No se hizo build ni se modificó frontend.
Prioridad acordada: ciencia > calidad > eficiencia. Las correcciones operativas
no acreditan equivalencia con Schrödinger ni validación científica del motor.

### Corregido en esta continuación

- ALTO: selectividad sustituía afinidad principal ausente por 0. Ahora intenta
  recuperar la afinidad del snapshot SUCCESS de la misma molécula y task_id.
  Si no existe una medida finita, devuelve 422; un cero realmente medido sigue
  siendo válido. Autorizado explícitamente por el usuario.
- ALTO: escrituras tardías ADMET y paneles PRO podían sobrescribir otra corrida.
  Usan UPDATE condicionado a molecule_id/task_id. El mapeo de propiedades se
  extrajo sin cambiar las conversiones y no cambia el carácter de control.
- ALTO: el guardado individual de anti-dianas perdía resultados de otro escritor.
  La fusión lee el JSON vigente desde SQL y usa comparación condicional antes de
  escribir. Una corrida distinta no recibe resultados viejos.
- ALTO: el endpoint HTTP MM-GBSA aún buscaba la ruta antigua compartida y generaba
  un conformador SMILES al faltar el archivo. Ahora lee poses_file_path de la
  evaluación o su snapshot SUCCESS. Rechaza la ausencia/corrupción y no filtra
  registros SDF inválidos antes de seleccionar el rango. Mantiene coordenadas y
  número de pasos. Esto completa otra ruta del cambio científico ya autorizado.

Contrato para la integración posterior de frontend: el guardado manual de
selectividad requiere task_id vigente; si falta o cambió devuelve 409. Las
respuestas PRO incluyen task_id. El cálculo ya persiste desde el backend;
no se debe asociar una respuesta tardía con la corrida que esté abierta entonces.

Verificación: 33 pruebas focalizadas PRO; luego **62 passed** con SDF real,
recuperación, rango corrupto, afinidad cero/no finita, persistencia y aislamiento.
Logs: hardening-pro-v3.log y hardening-pro-pose.log. Se solapan, no se suman.

### CRÍTICO C01: MM-GBSA construye un sistema con parámetros incompletos

Reproducción independiente: `backend/audits/mmgbsa_parameter_integrity.py`.
Evidencia: `backend/audits/mmgbsa_parameter_integrity.json`, OpenMM 8.5.2 del
runtime embebido. La herramienta sale con código 1 porque detecta defectos;
NO es un cálculo de energía ni una prueba científica superada.

1. El mapeo del ligando reutiliza tipos protein-* con reglas elementales.
   En etanol explícitamente hidrogenado hay 13 ángulos topológicos y sólo 10
   términos angulares; en benceno hay 18 y sólo 6. No es un conteo de enlaces
   que ignore restricciones de enlaces con hidrógeno.
2. La plantilla asigna carga cero. `_override_charges` modifica únicamente
   NonbondedForce; CustomGBForce y los productos de carga de excepciones 1-4
   conservan cero. La perturbación diagnóstica de 0.25 e demuestra la divergencia;
   ese valor es una sonda artificial, no una carga física calculada.
3. Un ligando con fósforo falla al crear el sistema, aunque P figure admitido.
4. La ruta de cargas procedentes de SMILES tampoco demuestra correspondencia
   atómica con la pose SDF. La reparación necesita un mapeo explícito, no asumir
   que ambos órdenes coinciden.

**No se corrigió este protocolo automáticamente.** El usuario prohibió cambiar
parámetros científicos sin autorización. Se solicitó autorización específica
para reparar la parametrización; las autorizaciones anteriores cubrían pose
real y abstención ante energías ausentes, no reemplazar el campo de fuerza.
El motor actual no debe considerarse científicamente validado por pasar los
controles operativos. Tampoco se reescribieron resultados históricos.

Propuesta verificable antes de activar un reemplazo:
- Parametrizador publicado para moléculas pequeñas, compatible con el modelo
  de proteína y solvente implícito; fijar versión y condiciones de licencia.
  GAFF/SMIRNOFF son candidatos a evaluar, no una elección ya validada.
- Conservar pose, estado químico y correspondencia atómica; parametrizar una vez
  y transferir de forma consistente a complejo y subsistemas.
- Validar cargas de todos los átomos, términos bonded, excepciones y GB; probar
  ligandos con heteroátomos, aromaticidad, halógenos, carga formal y fósforo.
- Comparar energías con un sistema de referencia construido independientemente,
  medir sensibilidad al protocolo y validar con complejos experimentales.
- Verificar operación offline. El runtime actual no trae openmmforcefields,
  openff.toolkit ni parmed; no se instaló ni descargó nada para ocultar esa falta.

Siguen abiertos los pendientes operativos previamente enumerados (persistencia
batch legacy, aislamiento de todas las etapas nativas, cirugía y descargas),
además de la revisión científica completa. Los tests no prueban ausencia de fallos.


Fuentes primarias consultadas para la propuesta (no sustituyen las mediciones
locales): [OpenMMForceFields: parametrizadores de moléculas pequeñas](https://github.com/openmm/openmmforcefields/blob/main/README.md)
y [OpenMM NonbondedForce: parámetros de partículas y excepciones](https://docs.openmm.org/latest/api-python/generated/openmm.openmm.NonbondedForce.html).
La documentación web corresponde a versiones publicadas actualmente; el
reproductor registra por separado la versión realmente instalada (8.5.2).

Observación adicional pendiente en la revisión estructural: el endpoint MM-GBSA
lee el receptor preparado del catálogo actual, aunque la evaluación conserva
receptor_path/receptor_sha256. Además prepare_protein elimina heterógenos y aguas.
Hay que definir y comprobar qué sistema molecular se conserva (especialmente
metales/cofactores) antes de declarar trazabilidad científica completa. No se
cambió esa preparación automáticamente en esta fase.


### Verificación final de esta continuación

- Suite global estable: **2370 passed, 10 skipped, 1 failed**, 245.28 s.
  Único fallo: H15, test_la_interfaz_dice_lo_que_si_hace, texto de frontend
  preexistente. Log: hardening-pro-verified.log.
- La primera corrida global de esta continuación registró dos fallos espurios
  de inspect.getsource porque el archivo cambió mientras el módulo anterior
  seguía cargado. Se repitió toda la suite sobre código estable; desaparecieron.
- Después se eliminó el fallback a cero también en el stage selectivity y su
  subprocess: datos inválidos/no finitos no lanzan el panel ni producen medidas.
  La fórmula para afinidades completas permanece igual.
- Regresión posterior de esos cambios: **85 passed**, 8.87 s, incluyendo contratos
  de pipeline, persistencia PRO, poses MM-GBSA y cinco entradas inválidas del
  subprocess. Log: hardening-selectivity-final.log. No sumar a la suite global.
- Ruff completo limpio en pro_features y los nuevos tests/reproductor; Ruff F
  limpio en runner/selectivity_subprocess. El lint de estilo general de esos
  dos módulos conserva avisos existentes (imports diferidos, JSON por stdout,
  entre otros); no se declara limpio todo el repositorio. compileall y
  git diff --check sin errores.

No se cerró 1.0.1 ni se creó un build. C01 sigue abierto y la sustitución de la
parametrización espera autorización científica específica. Continúan abiertos
los pendientes operativos y científicos descritos arriba.


## Continuación con commits y autorización científica

El usuario autorizó sustituir la parametrización MM-GBSA y descargar dependencias
científicas/referencias en un entorno aislado. Solicitó usar E: por espacio.
Esto sustituye el estado de autorización pendiente de la sección anterior;
no equivale a declarar validado ni activar ya un protocolo nuevo.

### H10 batch legacy: checkpoint durable y recuperación

- Tabla operativa batch_runs (schema 22, aditivo), con propietario, configuración,
  estado y resultados. Commit de aceptación antes de lanzar cualquier evaluación.
- Checkpoint tras cada fila y al finalizar métricas; el supervisor registra fallos
  y cancelaciones. Un fallo de persistencia no se disfraza de finalización correcta.
- Al consultar un batch que ya no tiene worker en memoria, se recupera de SQLite;
  si estaba running queda interrupted y conserva los resultados confirmados.
  El bloqueo de workspace garantiza una sola instancia propietaria del almacén.
  No hay repetición automática de cálculos tras un reinicio.
- Cada fila conserva task_id. La lectura usa primero el snapshot de esa corrida,
  por lo que una reevaluación posterior no cambia el resultado del batch.
- Se conserva el aislamiento de propietarios después de reiniciar. La API declara
  interrupted/failed y error; GET conserva resultados parciales. Export legacy
  sigue requiriendo completed, como antes.

Verificación: **41 passed**, SQLite temporal real y contratos API existentes;
commit fallido no lanza cálculos, aceptación duplicada no sobrescribe evidencia,
propietario incorrecto no actualiza, fallo del worker conserva evidencia parcial,
reinicio recupera configuración y una proyección posterior no altera el snapshot.
Log: hardening-batch-durable.log. Ruff F y git diff --check sin errores.

Límite: los batches anteriores a este cambio que sólo existieron en memoria no
pueden reconstruirse retroactivamente. La integración frontend de los estados
terminales nuevos sigue pendiente y está fuera de esta tarea.


### C01: contención y candidato científico medido

Ver [validación MM-GBSA](audits/MMGBSA_VALIDATION.md). La guardia de integridad
rechaza sistemas legacy incompletos antes de minimizar. Esto evita nuevos
números inválidos, pero puede reducir temporalmente la disponibilidad de MM-GBSA.
El reemplazo aún no está activado. C01 queda **contenido, no cerrado**.

El candidato GAFF2/AM1-BCC pasó 23/24 comparaciones con AmberTools en ocho
ligandos, incluyendo fuerzas y solvatación GBn2/LCPO. Se corrigieron discrepancias
reales de fósforo y tipado LCPO; el cloro sigue abierto. Las referencias se
reproducen offline en Windows. No se validaron todavía afinidades de unión ni
complejos completos. Se retiró una promesa no demostrada de ordenar poses.

Regresión global tras persistencia batch y contrato: 2381 passed, 10 skipped,
1 failed (H15 frontend), 285.67 s; log hardening-batch-science-full.log.
Pruebas focalizadas tras guardia y referencias científicas: 64 passed,
6 warnings GB documentados. No se suman los conteos solapados.


Verificación global final de este bloque: **2416 passed, 10 skipped, 1 failed**,
14 warnings, 337.09 s. Único fallo H15 (texto frontend preexistente). Log:
hardening-science-verified-full.log. No se modificó ni se omitió ese guardián.
Los avisos nuevos de radios GB se conservan y explican en el informe científico.
Ruff F, compileall focalizado y git diff --check sin errores.

Commits operativos de esta continuación: f474c19 (hardening acumulado) y
592975d (checkpoints batch). El bloque científico se registra por separado.
El entorno de referencia WSL quedó apagado, con sus archivos intactos en E:.
No hay build ni publicación; la 1.0.1 sigue abierta.


## Continuacion: ensamble y procedencia (2026-09-17)

Revision acotada documentada en `audits/ENSEMBLE_REVIEW.md`, con fuentes
experimentales, limites, pendientes y borrador ENS-PROD-01. La cobertura del
oraculo no se presenta como precision de recomendaciones biologicas.

ENS-01/ENS-02 (ALTOS): se impide agrupar receptores/protocolos incompatibles
y se preservan motor, exhaustiveness y numero de poses realmente ejecutados.
Antes, nueve pruebas reproducian perdida o mezcla de procedencia. No cambian
energias, pesos, conformaciones ni ranking de ejecuciones coherentes.

Verificacion: 113 passed, 1 skipped focalizados; suite completa con Python
embebido: **2427 passed, 10 skipped, 1 failed**, 14 warnings, 243.06 s.
Unico fallo: H15 preexistente,
`test_peptido_abstencion_negativa.py::test_la_interfaz_dice_lo_que_si_hace`.
Log local: `hardening-ensemble-full.log`. Ruff F (Python de desarrollo),
compileall focalizado y git diff --check correctos. No se instalo Ruff en el
runtime distribuido. No se repitieron benchmarks cientificos en este bloque.

Sin build, frontend ni activacion de MM-GBSA. La 1.0.1 sigue abierta.


## Continuacion: conversiones y correspondencia SDF (2026-09-17)

ENS-03 (MEDIO): las nuevas poses agrupadas conservan source_provenance con
rank original, archivo de origen, parser y conversor. El conjunto declara
mixed cuando hubo distintos parsers; no se atribuye al ultimo conversor.
Contrato aditivo de metadata opcional dentro del JSON existente, sin migracion
SQL ni cambio de formulas, pesos o coordenadas. Historicos conservan None.

ENS-06 (ALTO): SDF con registros sin afinidad se filtraba y renumeraba; la
asociacion posicional de Vina podia unir score y geometria de poses distintas.
Ahora se rechaza ese conjunto parcial de scores y se permite el respaldo
existente al PDBQT. El separador de registro tiene prioridad sobre campos sin
valor para no absorberlo ni desplazar la correspondencia. La ruta de datos
completos conserva valores y orden. No se activa recuperacion MM-GBSA basada
solo en rank/archivo: falta certificar hashes y correspondencia atomica.

Validacion: seis fallos iniciales reproducidos; 127 passed y 1 skipped tras
la primera correccion. Dos pruebas adicionales reprodujeron el caso de campos
truncados. Tras su correccion final: **129 passed, 1 skipped** en ocho suites
que cubren parser/conversion, ensemble, hardening, MM-GBSA, SQLite y reportes.
La regresion global iniciada antes de ese ultimo ajuste termino con
**2434 passed, 10 skipped, 1 failed**, 14 warnings, 239.96 s. Unico fallo H15
preexistente de texto frontend; log hardening-ensemble-provenance-full.log.
No se presenta esa corrida global como realizada despues del ultimo ajuste:
la version final del parser se verifico con las 129 pruebas focalizadas.
Ruff F sin errores en produccion y nuevas pruebas; aviso F841 preexistente en
test_sqlite_roundtrip.py:194 documentado en ENSEMBLE_REVIEW.md. Compileall y
git diff --check correctos. No se repitieron experimentos cientificos.

Sin build ni cambios frontend. MM-GBSA experimental no activado; 1.0.1 abierta.


## Continuacion: el ensemble acoplaba la misma geometria (2026-09-17, tarde)

Cierre de las auditorias abiertas de `audits/ENSEMBLE_REVIEW.md` y de la puerta 1
de `audits/MMGBSA_VALIDATION.md`. Sin build, sin frontend, sin activar MM-GBSA.

### ENS-05 (ALTO): confirmado, y el mecanismo era otro

Estaba anotado como «riesgo por verificar» con una hipotesis de concurrencia. Se
midio y el defecto era deterministico: `_prepare_ligand_pdbqt` sustituia el
conformero del hash derivado del ensemble (`<hash>__c07`) por el del hash
canonico, que es la conformacion 0 y existe siempre. **Las K corridas de Vina
partian de la misma geometria** y cada pose de la piscina declaraba una
conformacion de origen distinta: `conformer_index` era falso.

Reproducido en la suite con tres conformaciones reales de benceno y Meeko
instrumentado: los tres SDF pedidos eran distintos y los tres recibidos eran el
de la conformacion 0. Solo ocurria cuando el hash post-protonacion coincide con
el del validador -cualquier ligando neutro-, asi que colapsaba en silencio para
unas moleculas y no para otras.

Tres piezas, ninguna suficiente por si sola:

1. El rescate por SMILES solo actua si el hash pedido NO tiene geometria, y nunca
   para un hash derivado; si falta, se aborta en vez de sustituir o regenerar.
2. El `.pdbqt` preparado deja `vina_input.source.json` con el objeto y SHA-256
   del conformero de origen, el SHA-256 del propio PDBQT y quien lo preparo, y se
   comprueba antes de reutilizar la cache. Sin esto, las instalaciones que ya
   tengan un PDBQT construido desde la conformacion equivocada seguirian usandolo:
   es indistinguible de uno correcto.
3. La huella del cache de docking incluye la identidad del SDF de entrada. El
   cache es en memoria con TTL, asi que no hay migracion.

El registro comprueba tambien `prepared_by`: `quantum_ad4_service` escribe ese
mismo objeto con cargas GFN2-xTB y hoy no tiene llamante vivo. Colision latente
anotada en la auditoria, no corregida.

### ENS-05, segunda mitad: el bucle de eventos

El embebido de las K-1 conformaciones corria dentro de la corrutina. Latidos cada
10 ms, dipeptido, tres corridas por celda: K=8 paso de 5/44-45 a 29-30/45 y K=16
de 4/85-86 a 56-58/86-88, con la duracion total sin cambios (~452 y ~870 ms). Los
cuatro o cinco latidos de antes eran los del conformero 0: anadir conformaciones
no anadia un solo punto de suspension.

### ENS-07 (ALTO): la procedencia no cruzaba la persistencia

`Repository.cast_pose` enumera los campos a mano y `source_provenance` no estaba
en la lista. El contrato anadido para ENS-03 existia en memoria y se perdia al
guardar: la API devolvia None, el snapshot congelado tambien, y la recuperacion
de pose era imposible. Corregido de forma aditiva dentro del JSON existente, sin
migracion. Historicos siguen con None.

### ENS-04: cerrado con seis puertas

`services/docking/pose_recovery.py` recupera el registro SDF exacto de una pose
agrupada tras comprobar procedencia completa, hash del artefacto, hash de la
conformacion de entrada, existencia del rank, identidad quimica contra la entrada
y correspondencia coordenada a coordenada con el bloque PDBQT entregado. Se
abstiene con el motivo cuando algo falla. Nunca convierte desde SMILES.

Tolerancia 0.002 A, que es la precision de los formatos y no un margen de ajuste;
una prueba fija que 0.05 A se rechaza. Los pseudo-atomos de pegado de macrociclo
se descartan por su tipo AutoDock -la unica cosa que se lee de las columnas
77-78- para no declarar irrecuperable toda pose macrociclica.

El endpoint de MM-GBSA usa la recuperacion cuando no hay archivo unico de poses.
Eso NO activa nada: el protocolo sigue `EXPERIMENTAL_NOT_ENABLED` y la guardia de
integridad sigue rechazando sistemas incompletos.

Cada puerta se verifico desactivandola: G6 anulada tumba 4 pruebas, G1 cinco, G2
dos, y G3, G4 y G5 una cada una.

### MM-GBSA puerta 1: el cloro, completamente atribuido

Los 0.162782 kcal/mol del clorobenceno son exactamente la entrada LCPO `C_sp2_2`
-radio 1.7 A incluido- que Amber usa como respaldo de carbono para CL. Con ella,
energia y fuerzas concuerdan con sander en 1.3e-08 kcal/mol y 6.5e-05
kcal/mol/A. Ninguna otra entrada de la tabla lo consigue; la atribucion se
verifico por unicidad.

**El bloqueo se mantiene.** Copiar el respaldo daria paridad perfecta y eso es
razon para no hacerlo sin decision de dominio: seria elegir el parametro por el
resultado. Una prueba nueva falla si el adaptador empieza a manipular la tabla
LCPO. 23/24 sigue siendo 23/24.

### ENS-PROD-01: dimensionado cerrado, cohorte abierta

`audits/ens_prod_01_potencia.py` calcula potencia exacta de McNemar sobre la
discordancia sellada de MF-33-B-RET-R2. Contraste primario (top-1, TODOS):
potencia 0.150 con n=48, y hacen falta 248 complejos para 80% y 324 para 90%.
**R2 no podia demostrar mejora en top-1**, con 15% de potencia. Los contrastes
que si alcanzaron significacion estaban bien dimensionados (0.908 y 0.999).

La aritmetica se comprobo contra simulacion independiente (0.1501 frente a
0.1494; bajo la nula 0.0221 en ambas). El informe declara sus dos sesgos: cotas
inferiores por dimensionar con el efecto observado, y dependencia entre complejos
relacionados que McNemar no contempla. Cohorte, presupuesto y umbral siguen
abiertos; el experimento no se ha ejecutado.

### Verificacion

- Pruebas nuevas y reproducciones: 7 fallos reproducidos antes del arreglo de
  ENS-05 y 3 antes del de ENS-07, en pruebas escritas primero.
- Focalizadas tras los cambios: 20 de recuperacion de pose, 10 de identidad de
  conformacion, 3 de persistencia de procedencia, 19 de potencia, mas las suites
  de ensemble, procedencia, MM-GBSA, paridad Amber, SQLite y dossier.
- Subconjunto amplio (ensemble, pose, docking, procedencia, conformer, mmgbsa,
  sqlite, dossier): 531 passed, 2 skipped.
- Suite completa con el Python embebido, sobre el codigo final: **2495 passed,
  10 skipped, 1 failed**, 14 warnings, 336.21 s, de 2505 recolectadas. Unico
  fallo: H15 preexistente (texto de frontend), fuera de alcance y sin tocar.
  Log: `hardening-ensemble-identidad-full.log`.
- Ruff F limpio en los modulos tocados y en las pruebas nuevas; compileall
  focalizado y `git diff --check` correctos.

Sin build, sin cambios de frontend, sin activar MM-GBSA. La 1.0.1 sigue abierta.
Los pesos, energias, formulas y parametros cientificos no se han tocado.


## Continuacion: el SDF de Meeko no se parseaba nunca (2026-09-19, noche)

Defecto encontrado por `ENS-PILOT-01` al ejecutar el bloque 1 de
`audits/VALIDACION_EN_SERVIDOR.md`. Sin build, sin cambios de frontend, sin
activar MM-GBSA, sin tocar formulas, pesos, semillas ni parametros cientificos.

### SDF-01 (ALTO): un ancla de regex mandaba el 100% de las corridas al respaldo

`parse_vina_output_sdf` reconocia la cabecera de una propiedad con
`re.match(r"^>\s+<([^>]+)>\s*$", stripped)`. El `$` exigia que la linea acabara
justo tras el angulo de cierre. Meeko escribe `>  <meeko>  (1) `, con el indice
del registro detras, asi que ninguna de sus propiedades casaba y la funcion
devolvia `[]` para todo SDF de Meeko. `>  <REMARK>` de Open Babel no lleva
sufijo y si casaba: el ancla se ajusto al camino de respaldo mientras el
principal llevaba roto desde siempre, y el docstring ilustraba `> <meeko>`, una
cabecera que ningun programa emite.

Medido sobre ENS-PILOT-01: **172 acoplamientos lanzados, 171 por el respaldo de
Open Babel, cero por Meeko** (el 172 estaba en vuelo). Meeko no estaba roto:
`mk_export` devuelve rc=0 y un SDF de RDKit valido con su JSON `meeko` y
`free_energy`.

Consecuencias en el archivo entregado, mismo ligando y misma pose: Meeko 20
atomos `C8 H9 N1 O2`; Open Babel 13 atomos `C8 H2 N1 O2` -solo sobreviven los
hidrogenos polares del PDBQT-. En macrociclos, Open Babel no reconoce los tipos
de pegado de Meeko: escribe dos carbonos reales del anillo como pseudo-atomos
`*` y deja el ciclo abierto (exaltolida 17 atomos / 14 enlaces donde
corresponden 17 y 17). Las afinidades no cambiaban: salen de las mismas lineas
`REMARK VINA RESULT`.

**Viajo en 1.0.0.** Verificado sobre el artefacto y no sobre el codigo: cargado
`E:\rel\v1.0.0.0\layout\resources\backend\utils\file_handlers.py` y pasado un
SDF real de `mk_export`, devuelve `[]`. Ademas `services/docking/pose_recovery.py`
no existe en 1.0.0, asi que alli la puerta G5 no rechaza nada.

### SDF-02 (ALTO): arreglar el regex a secas habria entregado un RMSD falso

Meeko exporta la afinidad pero NO el RMSD contra la pose 1: esos dos numeros
solo existen en `REMARK VINA RESULT`. Con `poses` ya no vacio, el respaldo al
PDBQT de mas abajo no se ejecuta, asi que `rmsd_lb`/`rmsd_ub` quedaban en 0.0 y
`pdf_generator` habria impreso `RMSD 0.00` en todas las poses del dossier. No es
un dato ausente: afirma que todas son identicas a la pose 1.

Se anade `fusionar_rmsd_desde_pdbqt` en `utils/file_handlers.py`: emparejamiento
POSICIONAL, solo si ambos recuentos coinciden, y abstencion declarada si no
-desalinear pondria el RMSD de una pose sobre otra geometria, que es lo que el
invariante todo-o-nada de ENS-06 existe para impedir-. La afinidad no se
sobrescribe; se contrasta contra la del PDBQT y una divergencia se registra.

### Lo que NO cambia, comprobado antes de tocar nada

- `check:goldens` no se ve afectado: `scripts/generate_goldens.py` no importa
  nada de docking ni referencia `.sdf`/`.pdbqt`; alimenta diccionarios escritos
  a mano a la composicion del dossier y a los perfiles M4/M5-Zn.
- La validez fisica sellada no se invalida: `evaluar_pose_fisica` lee el PDBQT
  -`leer_pose_pdbqt_canonica`- y reconstruye los hidrogenos con
  `canonicalizar_hidrogenos`. El bloque PDBQT es identico. MF-33-H-COR y
  PROD-PV-H-01 intactos.
- La identidad MSIX no depende de esto: `msix/msix-config.json` declara el
  triple Name/Publisher/Arch como inmutable y la version como monotona con
  Revision 0. El codigo Python es contenido, no identidad.
- Frontend sin cambios: trata `parsing_source` como cadena opaca y sus pruebas
  ya usan `"sdf"`.
- El respaldo de Open Babel sigue existiendo y sigue etiquetandose
  `sdf_openbabel_cli`; pasa a ser un respaldo de verdad.

### Lo que el arreglo repara en la ciencia

Con las fixtures reales, la composicion del macrociclo vuelve identica a la de
su conformero de entrada -45 atomos, 45 enlaces, `C15 H28 O2`, anillo cerrado- y
las dos puertas de `pose_recovery` pasan: G5 3/3 y G6 3/3 con 17/17 coordenadas
a 0.0000 A de desplazamiento, con los 2 pseudo-atomos filtrados. En paracetamol,
G5 9/9 y G6 9/9. Los macrociclos pasan de irrecuperables a recuperables.

### Validacion

- Nuevo `tests/test_lector_de_sdf_de_meeko.py`: **24 pruebas**, con archivos
  producidos por Vina y `mk_export` en `tests/fixtures/meeko_export/` y no
  cabeceras escritas a mano -que es como el defecto sobrevivio a la bateria
  entera-. Incluye autotest del guardian: el regex con el defecto no casa con
  ninguna cabecera real de Meeko y si casa con las de Open Babel.
- Seis suites de mayor riesgo: **105 passed**.
- Suite completa SIN el archivo nuevo, con los cambios de codigo dentro:
  **2509 passed, 10 skipped, 0 failed** -identico al punto de partida del dia,
  es decir cero regresiones-.
- Suite completa sobre el codigo final: **2533 passed, 10 skipped, 0 failed**,
  16 warnings, 245.87 s. Recoleccion 2542 = 2518 + 24; `docs/api/test-counts.json`
  regenerado.
- `git diff --check` limpio, `compileall` correcto, sin saltos de linea mixtos.
  Ruff no esta en `python-embed`; ese chequeo queda para el interprete de
  desarrollo.

Documentacion corregida donde afirmaba lo contrario: `docs/79_ADR_FRONTERA_OPEN_BABEL.md`
punto 4 y la tabla del diagnostico, y dos comentarios de `vina_service.py` que
llamaban al camino de Open Babel «el caso normal» sin haberlo medido.

La 1.0.1 sigue abierta.
