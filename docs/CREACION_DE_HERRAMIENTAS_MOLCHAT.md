# Creación de herramientas: MolDesign y MolChat

## Principio

MolDesign posee los datos, la identidad y las operaciones de la aplicación.
MolChat interpreta solicitudes y puede proponer el uso de capacidades del host.
Una propuesta del modelo no es un resultado; la confirmación solo puede
aparecer cuando la operación concreta de MolDesign la comunica.

Este documento describe la integración existente de creación de casos y sirve
de guía para diseñar nuevas capacidades. No declara que el chat ya tenga un
enrutador universal ni acceso a todas las funciones de MolDesign.

## Flujo implementado: crear un caso

1. Con un proveedor que admite herramientas, el modelo decide llamar a
   `create_case` y sus argumentos se validan contra un esquema cerrado. Sin
   herramientas, el clasificador reconoce la petición y el modelo elige el
   nombre en un JSON cerrado, que debe aparecer literalmente en el turno. Un
   nombre inventado o una respuesta inválida no producen acción.
2. El servidor verifica proveedor, autorización y sesión. Genera un
   `request_id` aleatorio, envía un evento `case_create` y espera un resultado
   asociado a ese ID y a la cuenta del turno.
3. La UI del sidecar transmite `molchat-host-message` con `kind: create_case`,
   `request_id` y `name`. El host acepta mensajes solo de la ventana del iframe
   y su origen exacto, comprueba la forma, la cuenta y los IDs ya recibidos.
4. El host entrega la solicitud al espacio de casos. Si no está montado, abre
   Evaluación y espera brevemente a que se monte. El receptor comprueba la
   cuenta, evita operaciones simultáneas desde el chat y consulta los casos de
   esa cuenta para detectar un nombre existente, normalizado para comparación.
   La creación se realiza con `CaseContext.createCase`, que conserva sus
   comprobaciones, escritura, selección y actualización de la lista. En Tauri
   usa el directorio predeterminado autorizado y la frontera de Rust.
5. El host devuelve `created`, `exists`, `failed` o `unknown`. `exists` incluye
   el caso existente y una colisión de carpeta reportada por el repositorio;
   no abre ni modifica el caso. Otros errores después de intentar la escritura
   pueden ser ambiguos y se informan como `unknown`.
6. La UI devuelve el estado al sidecar por su sesión en
   `/v1/case-requests/{request_id}/result`. Solo `created` permite responder que
   se creó el caso. Ante `unknown` se pide revisar la lista antes de reintentar.

La deduplicación actual del host es por ID de solicitud y vive en memoria. No
garantiza idempotencia durable entre reinicios ni resuelve todos los casos de
peticiones concurrentes originadas fuera del chat. El rechazo de nombres
coincidentes es una política del puente del chat, no una regla general para
todas las operaciones de casos de la aplicación.

## Consulta informativa de PubChem

La consulta la hace MolChat con la herramienta `pubchem_lookup`, no el host.
MolDesign solo decide el permiso: antes de cada petición, el sidecar lo
comprueba con la sesión de la cuenta en `GET /ai/consent/red`, que también
refleja el modo sin red. El cliente HTTP de MolChat no usa proxies del entorno
ni sigue redirecciones. Los resultados contienen nombre, identificador,
propiedades disponibles y enlace a PubChem; se limitan a diez y se declara la
truncación. La selección de una referencia se guarda por conversación y cuenta,
sin cambiar Ketcher ni el campo SMILES.

El permiso puede otorgarse y retirarse explícitamente desde Ajustes de MolChat.
Se envía el nombre consultado a PubChem. Una fuente que no responde no equivale
a una búsqueda sin resultados. La consulta es informativa: cargar un SMILES es
una operación aparte, que pide confirmación al host.

## Responsabilidades al añadir una herramienta

**MolDesign** define y ejecuta la operación de producto; conserva su validación,
propiedad, estado de guardado y autorización. Debe poder distinguir un fallo
seguro de una operación cuyo resultado no se conoce. El frontend no debe
duplicar ni saltarse las comprobaciones de su contexto o repositorio.

**MolChat** ofrece al modelo únicamente las capacidades acordadas, valida la
selección y sus argumentos como entrada no confiable y conserva la cuenta y el
destino autorizados. No convierte texto del modelo en una confirmación de
escritura. Hoy las herramientas solo se ofrecen con un host y con un proveedor
que admite llamadas a herramientas.

**El contrato** documenta forma, versión, identidad, límite de tamaño,
autorización, respuesta, deduplicación, errores y recuperación. Las operaciones
de efecto deben definir cuándo pedir confirmación y cómo conciliar una
respuesta perdida; ninguna política de creación de caso se aplica
automáticamente a todas las operaciones futuras. Las acciones de producto de
este documento viajan por mensajes entre el iframe y la ventana del host: aún no
están declaradas en `moldesign.molchat/1` ni en el kit de conformidad de MolChat.

## Acciones sobre un caso

### Asignación de receptor desde MolChat

MolChat ofrece `search_receptors` y `assign_case_receptor`: identifica el caso
y el PDB, y exige un identificador explícito o una búsqueda inequívoca. Envía
`case_receptor` por el canal de eventos; la UI lo transmite al host mediante
`assign_case_receptor`. El host comprueba cuenta, origen, ventana, forma y
repetición de solicitud, y el espacio de casos resuelve el nombre en la cuenta.
El runner valida el catálogo y utiliza la misma selección que la interfaz,
incluida la actualización de la caja y la protección del sistema estructural.
La confirmación requiere que el receptor esté visible y que el registro del
caso persistido contenga ese identificador. Los errores de disponibilidad,
ambigüedad, bloqueo, guardado y resultado incierto se devuelven a MolChat;
no se inicia docking ni se reintenta una escritura automáticamente.

### Iniciar una evaluación desde MolChat

`evaluate_case` solicita evaluar un caso solo cuando el usuario lo pide. El
host valida la cuenta, resuelve un caso inequívoco y entra por el botón de
Evaluación, con los mismos controles, preparación y preflight del producto.
El ligando de ejemplo no se adopta automáticamente. La respuesta `started`
requiere un identificador aceptado y su registro en el caso; si se aceptó pero
falló el registro se devuelve `started_unregistered` con el identificador.
Los bloqueos, las tareas ya activas y el resultado incierto son explícitos;
una respuesta perdida no se reintenta automáticamente. Aceptar una tarea no
significa que haya terminado ni que existan resultados.

`get_evaluation_status` cierra ese turno y sólo lee: consulta
`GET /evaluation/status/{task_id}` con la sesión de la cuenta y no inicia,
cancela ni reintenta nada. Devuelve el estado y el progreso y, si la tarea acabó
con `SUCCESS`, la energía de Vina con la calibración del receptor, siempre con
el aviso de que no es una energía libre ni un Ki. Una tarea ajena o inexistente
se responde igual: `not_found`.

## Verificación antes de integrar

- Probar nombre válido, inexistente, existente y colisión de carpeta, cuenta
  ajena, argumentos desconocidos, fallo del repositorio y respuesta incierta.
- Probar origen y ventana del iframe, esquema cerrado, repetición de ID,
  recepción con Evaluación montada y navegación cuando aún no lo está.
- Comprobar que un error no declara éxito ni reintenta automáticamente una
  escritura incierta, y que el resultado se refleja en el historial y la UI.
- Probar por separado el intérprete de intención con un proveedor simulado y
  con el modelo real, y después el recorrido completo en Tauri. Las pruebas
  simuladas no prueban el hardware, permisos o proveedor del usuario.
- Ejecutar las pruebas y gates afectados de ambos repositorios. Construir la UI
  del sidecar, registrar su código fuente en un commit y usar el productor de
  manifiesto y `scripts/stage_molchat.py --write` y `--check`. La copia fijada
  debe ser reproducible; no modificarla a mano.

La guía del lado MolChat está en `docs/CREACION_DE_HERRAMIENTAS.md` de ese
repositorio. La decisión de arquitectura y las limitaciones de publicación del
sidecar están en `docs/100_ADR_MOLCHAT_EXTERNO.md` y `docs/101_PROTOCOLO_MOLCHAT.md`.
