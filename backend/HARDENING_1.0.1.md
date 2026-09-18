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
