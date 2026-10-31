# ADR 100 — MolChat vive fuera: sidecar GPL vendorizado, host mínimo y corte del interno

**Estado:** implementado en la rama `feat/molchat-plataforma-cr`; el código interno y el selector beta ya se retiraron en esa rama. El corte de código no demuestra todavía paridad, prueba del instalador ni preparación para publicar. El protocolo y su verificación están en [101_PROTOCOLO_MOLCHAT.md](101_PROTOCOLO_MOLCHAT.md).
**Fecha:** 2026-10-28. **Enlaza** el plan de extracción (repositorio `moldesign-molchat`, su `docs/PLAN_PUBLICO.md` cuando la Fase 7 lo publique) y los ADR 92/95 (patrón Molcy), cuyo mecanismo copia pieza a pieza.

## El problema, medido

El asistente vive horneado en la plataforma: unas 19.200 líneas en `backend/services/ai/` (66 ficheros) más la UI montada global en `frontend/app/layout.tsx`, con el router y el bootstrap registrados en `backend/api/main.py`. Consecuencias medidas, no opinadas:

- No se puede desarrollar, probar ni versionar el asistente sin la plataforma entera.
- No se puede ofrecer a terceros: importa `core.config`, `core.models`, RDKit y routers de evaluación.
- Cada cambio de plataforma arriesga al asistente y viceversa (un solo árbol, un solo despliegue).
- La lección del ADR 95 aplica entera: dejar el programa como «carpeta que el usuario configura» lo hizo inutilizable; incluirlo fijado lo hizo real.

## Decisión

El propietario decidió (2026-10-26, plan de extracción): **un solo MolChat, fuera**.

1. El asistente vive en su repositorio público, GPL-3.0-or-later: <https://github.com/srcacahuate619/moldesign-molchat> (rama `master`).
2. MolDesign lo vendoriza fijado por manifiesto en `tools/molchat/` y lo ejecuta como sidecar (proceso Python en loopback, puerto efímero), **opcional en runtime** (sin él, todo lo demás funciona) y **verificado antes de cada arranque**.
3. El MolChat interno se congela, alcanza paridad, y **se borra** en la release del corte. No se mantienen dos.
4. Lo que es plataforma (propuestas, STT, motores, identidad, casos) se queda; sólo cambia de sitio lo que cuelga de `services/ai/` por accidente histórico (§15.4 del plan).

### ¿Por qué GPL, y por qué no contagia a MolDesign?

Decisión del propietario, por simetría con Molcy y para que terceros lo adopten: quien reciba el sidecar lo recibe con derecho a usarlo, modificarlo y redistribuirlo también con fines comerciales. A diferencia del motor Molcy, aquí no hay presión de derivado por importar `bpy`: el sidecar y la plataforma no se importan en ningún sentido y se hablan por HTTP versionado, así que viajar juntos es mera agregación igual que Open Babel (ADR 79). MolDesign sigue bajo PolyForm Noncommercial.

> Esto es ingeniería y procedencia, **no asesoría jurídica**. Igual que los ADR 79/95, una revisión legal externa sigue siendo recomendable antes de vender licencias comerciales.

### La frontera

- MolDesign **no importa** `molchat_agent` y el sidecar **no importa** nada de MolDesign (`backend/tests/test_frontera_molchat.py`, espejo del de Molcy).
- MolDesign lo ejecuta por **subproceso** (`sys.executable -c` con un bootstrap que inserta el `src/` vendorizado en `sys.path`, `--ui-dist` absoluto de la copia verificada) y se comunican por HTTP (`moldesign.molchat/1`). Nada por `PATH`, nada relativo. El arranque no puede depender de `PYTHONPATH`: el intérprete empaquetado del escritorio es un Python aislado (`._pth`, `sys.flags.isolated=1`) que la ignora y cuyo `-m` nunca añade el cwd — medido en el runtime real, el sidecar no arrancaba con `-m` (corregido en `06eba932`).
- El lanzador exige manifiesto íntegro y contrato conocido **antes de cada arranque**; si no, se abstiene con motivo y la UI lo explica.

## Qué viaja

`tools/molchat/` (60 ficheros, ~0,6 MB): el paquete `molchat_agent` (sidecar), el build estático de su UI (`ui/dist/`), `LICENSE` (texto íntegro GPL-3.0-or-later), `NOTICE.md`, `pyproject.toml` (requisitos que el host debe dar al intérprete) y `molchat-manifest.json` (SHA-256 por fichero, versión, commit de origen, contrato y licencia).

**No viaja:** tests, `conformance/`, `examples/`, docs y scripts de desarrollo, el plan interno, claves ni pesos de modelos (se descargan como hoy).

### De dónde sale

Se vendoriza desde un **commit** con `scripts/stage_molchat.py --fuente <clon> --write`, que delega en `scripts/make_manifest.py` **del repositorio fuente** (una sola implementación de «qué viaja», allí) y después verifica con el verificador local (una sola implementación de «qué es íntegro», aquí: la que el lanzador usa). Los ficheros tracked se leen como *blobs* del commit; el build de la UI —artefacto git-ignorado por diseño— se toma del disco sólo si está fresco y sus fuentes commiteadas. El manifiesto registra rama, commit y URL pública sin credenciales. El repositorio marca `tools/molchat/**` como `-text` y lo exceptúa del `dist/` global de `.gitignore` (el build vendorizado SÍ viaja).

Para actualizar: se cambia **allí**, se commitea, y aquí se ejecuta el staging. Nunca al revés ni a mano.

## Decisiones de diseño cerradas en esta rama

El plan dejaba estos puntos abiertos; así quedaron, con su motivo:

- **Identidad de doble uso (diseño A).** El sidecar reenvía el Bearer que recibe y la plataforma lo acepta como identidad (`api/dependencies.py`, puerta por prefijo `mh1.`; los JWT normales ni pisan el código nuevo). Alternativa descartada: acuñar JWT cortos de plataforma por sesión (dos tokens por todas partes, más fontanería para el mismo riesgo). El secreto HMAC rota por proceso de escritorio, así que todo mh1 válido nació en este arranque — atadura más fuerte que la del JWT de invitado, que por eso no necesita chequeo separado.
- **Arranque bajo demanda.** El primer `POST /molchat-host/session` levanta el sidecar (~8 s, una vez); `GET /molchat-host/status` es público y no arranca nada. Un sidecar roto responde 503 con motivo, nunca tumba el arranque de MolDesign. Al cerrar el backend, el lifespan lo detiene (sin huérfanos).
- **Sesiones atadas a la cuenta.** `/session` exige cuenta y acuña mh1 (`sub` = su UUID, seis scopes de UI, TTL 3600 s por defecto, `MOLCHAT_TTL_S`). El sidecar fija el proceso a la primera cuenta (PD-04) y la plataforma impone la identidad por llamada.
- **UI embebida por handshake, no por URL.** La UI del sidecar anuncia `molchat-ui-ready` y el hueco responde `molchat-host-session` (postMessage, orígenes loopback en ambos sentidos). El token jamás va en la URL. Sin sandbox a propósito: el contenido es el nuestro, verificado por hash; el sandbox sólo rompería su sessionStorage.
- **Deep links con esquema cerrado.** Los cinco de §11.3, validados campo a campo; `open_molcy`→`/molcy`, evaluación/informe→`/history`, caso→`/moldex`, aprobación→aviso (no existe superficie de aprobación en el host: se resuelve en el propio panel). Navegación a listas reales, nunca a parámetros que las páginas no entienden.
- **Opcional de verdad.** Ni `HERRAMIENTAS_CRITICAS`, ni arranque acoplado, ni SBOM abortado: ausente se declara, presente se verifica. El modo externo (`MOLDESIGN_MOLCHAT_DIR` + `MOLCHAT_PERMITIR_EXTERNO=1`) es sólo para desarrollar el sidecar, sin vía en la aplicación.

## Cómo lo usa el backend

- `backend/services/molchat_host/manifest.py` (sólo biblioteca estándar): localizar y verificar, espejo de `services/molcy/motor.py`.
- `backend/services/molchat_host/sesion.py`: acuñado mh1 byte-compatible con `molchat_agent.server.auth` (clavado por vector dorado probado contra el verificador del sidecar) y secreto del proceso.
- `backend/services/molchat_host/launcher.py`: supervisión síncrona (puerto libre, entorno, drenaje de salida, espera de salud, parada con gracia), único por proceso.
- `backend/api/routers/molchat_host.py`: `GET /molchat-host/status` (público) y `POST /molchat-host/session` (con cuenta).
- `frontend/components/ai-host/MolChatHostMount.tsx`: hueco (iframe + puente), montado directamente por el layout. El selector beta y el panel clásico ya no están en la rama.

## Cómo se verifica en el build

- `stage_molchat.py --check`: copia exacta, forma del manifiesto, licencia real, sin rutas de máquina, indispensables del host.
- `test_frontera_molchat.py`: AST en ambos sentidos + lanzamiento sólo por subproceso absoluto.
- `verify_desktop_bundle.py`: `validate_molchat_sidecar` (presente ⇒ íntegro y localizable por el empaquetado; ausente ⇒ se declara, no se exige).
- SBOM: programa propio con manifiesto; `test_sbom_inventario.py` clava la tupla instalador↔SBOM y la opcionalidad.
- `test_molchat_host_lanzador.py::test_ciclo_de_vida_contra_la_copia_vendorizada` levanta la copia real (~8 s): salud, contrato, UI y parada limpia.

## Sombra y corte (§16)

La sombra previa exigía quality suite de 43 + sesiones reales del propietario, deterministas iguales o mejores, cero fugas adversariales y latencias no peores. La condición de salida §16.4 incluía además proveedores local y nube, 27 herramientas con estado final, manifiesto en instalación limpia y rollback ensayado. El código del asistente interno ya se retiró en la rama antes de que todas esas condiciones estuvieran verificadas: el registro histórico de [modo sombra](MODO_SOMBRA_MOLCHAT.md) describe las pruebas y lo pendiente en aquel momento. No debe leerse la retirada del código como un resultado de esas pruebas. El rollback de una release instalada sería instalar la release anterior; no se ha ensayado aquí.

## Lo que queda abierto

- Superficie de host mínima publicada en un MolDesign (`min_moldesign` del manifiesto se rellena entonces; hoy se omite con honestidad).
- Parámetros de deep link en las páginas destino (ítem exacto en vez de lista).
- Refresco de sesión sin reabrir el panel (hoy: expira ⇒ la UI re-pide sesión).
- Empaquetado del intérprete embebido: el sidecar necesita en él `httpx`, `starlette` y `uvicorn` (los tres ya viajan con el backend).

## Addendum (2026-10-28): la llave, la cerradura y la fijación

**Decisión del propietario.** MolChat es un proyecto independiente en su repositorio (`moldesign-molchat`, GPL-3.0-or-later). Ese proyecto es la **llave**. MolDesign conserva la **cerradura**: el código que verifica la llave, la arranca y la muestra. Tres decisiones lo fijan:

1. La llave viaja dentro del instalador, fijada por hash, como hasta hoy. No se pide al usuario que la instale aparte: la lección del ADR 95 es que una «carpeta que configura el usuario» deja la función inutilizable.
2. La fuente de la llave es un repositorio por commit: un clon local en desarrollo y el repositorio público para terceros.
3. Los documentos de MolChat que ya viven aquí se quedan en MolDesign. La documentación nueva vive en el repositorio de MolChat: `docs/LLAVE_Y_CERRADURA.md` y `docs/DESARROLLO_Y_VERSION_PROPIA.md`.

**Los dos objetivos.**

- *Trabajar en MolChat sin romper MolDesign.* La copia incluida y su fijación sólo cambian cuando se vendoriza a propósito y se confirma en un commit de MolDesign. Un cambio en el repositorio de MolChat no llega a MolDesign hasta entonces.
- *Que los usuarios modifiquen MolChat.* MolDesign acepta cualquier llave que cumpla `moldesign.molchat/1` y que esté fijada. Una llave que no sale del repositorio oficial queda como `oficial: false`, y el estado del sidecar lo muestra.

**La fijación.** `backend/data/molchat_fijacion.json` guarda el commit, el origen (`repositorio` y `oficial`) y el SHA-256 del manifiesto de la copia (`tools/molchat/molchat-manifest.json`). `GET /molchat-host/status` expone `oficial` y `repositorio`. El lanzador no arranca una copia incluida que no coincida con su fijación, y `verify_desktop_bundle` aplica la misma comprobación al backend empaquetado. Una copia externa (`MOLDESIGN_MOLCHAT_DIR` con `MOLCHAT_PERMITIR_EXTERNO=1`) no exige fijación: es para desarrollo, y la elige quien la usa.

**Vendorizar.** `scripts/stage_molchat.py --fuente <clon> --write` vendoriza el HEAD del clon y actualiza la fijación. `--destino <carpeta>` vendoriza a una carpeta de prueba sin tocar la copia incluida ni la fijación.

**Estado al cerrar la fusión (2026-10-28).**

- La llave es `master` de `moldesign-molchat` en `965ffe8d`, publicado en GitHub el 2026-10-28. Incluye el panel compacto de `ac8db615` y los commits de documentación de la llave. Clonar ese commit del repositorio público, construir su interfaz (`npm ci` y `npm run build`) y vendorizarlo produce una copia byte a byte igual a `tools/molchat/`, con el mismo manifiesto: la fijación se reproduce desde fuera.
- La fijación anterior apuntaba a `8899744`, publicado en `codex/protocolo-compatibilidad`. Respecto de ella, lo que cambia en la copia es la interfaz del panel compacto.
- La interfaz de la copia se reconstruyó desde las fuentes de `ac8db615` con `npm run build`: los ficheros de `ui/dist` coinciden byte a byte con los que viajan en la copia.

**Límites que quedan.**

- El SHA-256 prueba que la copia es la fijada, no quién la escribió. `oficial` describe el origen declarado; no lo certifica.
- `oficial` no impide construir un instalador con una llave propia. Si el instalador oficial debe exigir `oficial: true`, es una regla de publicación que aún no está implementada.
- Vendorizar renombra `tools/molchat/`. Si un proceso tiene ese directorio abierto (por ejemplo, un terminal con él como carpeta actual), Windows lo rechaza y el productor se detiene sin tocar la copia activa. Hay que cerrar ese proceso y repetir.
- El build oficial (Store) debe vendorizar desde un commit publicado en el repositorio oficial. `965ffe8d` lo está desde el 2026-10-28.

## Addendum (2026-10-28, 2): proveedores de IA por cuenta

**Decisiones del propietario.** OpenAI es la API genérica prioritaria; DeepSeek se usa sólo para DeepSeek. Las claves se guardan en MolDesign. Se implementa el flujo elegir proveedor → clave → autorizar, y se corrigen los defectos de la revisión.

**Dónde vive cada cosa.**

- **Catálogo** (`providers/catalogo.json`, en la llave): id, familia de protocolo, URL base, modelo por defecto y lo que sale de la máquina. Viaja en la llave, así que su hash está en el manifiesto. MolDesign lo lee de la copia verificada (`GET /molchat-host/proveedores`) sin arrancar el sidecar.
- **Claves y autorización** (MolDesign, `provider_config_store`): por cuenta y cifradas en reposo. «Guardar y autorizar envío a `<host>`» es un solo paso. El consentimiento es de la cuenta y de la huella `proveedor@host`. Si el host mostrado ya no es el del catálogo, la respuesta es 409 y no se guarda nada.
- **Entrega al sidecar** (`POST /molchat-host/credencial`): sólo con sesión mh1 y sólo si la cuenta tiene la clave, autorizó ese host y el host pedido es el del catálogo verificado. La clave no se devuelve a la interfaz ni se registra.
- **Modo alojado en MolChat** (`providers/alojado.py`): la clave vive en el registro de una sola llamada. El registro base nunca la guarda. El consentimiento global del fichero del sidecar no aplica en modo alojado.

**Valores por defecto.** Perfil `default`, que es el del producto. `hackathon` (sólo Meta remoto) hay que pedirlo. No hay proveedor activo hasta que la cuenta elige uno.

**Correcciones de esta fase.**

- La clave de cifrado se deriva una vez por secreto; antes se derivaba (480k iteraciones) en cada operación.
- Se retiró la promesa de «credenciales en LocalStorage» de los textos de IA: no era cierta.
- `docs/ARQUITECTURA.md` de MolChat ya no dice que las claves viven sólo en el entorno.

**Límites que quedan.**

- La llave `fa4a3e98` de MolChat todavía no está publicada en GitHub. Reproducirla desde fuera exige publicarla.
- Multi-cuenta en un mismo proceso de sidecar: sigue fijado a la primera cuenta (PD-04).
- La clave maestra del cifrado se deriva de `~/.moldesign/secret_key`, en claro en el perfil. DPAPI queda como mejora.
- Listado de modelos desde el proveedor (`/models`) y la API Responses para los modelos Codex: sin implementar. Los modelos se escriben a mano.
- La clave viaja al sidecar en cada llamada. Una versión propia de MolChat la recibe; por eso el estado `oficial` importa.

## Addendum (2026-10-31): la llave se consolida en el harness

**Qué pasó.** El trabajo del 28 y 29 de octubre se bifurcó en tres líneas. `master` público (`d459c08`) era un resumen de una etapa del harness, `codex/harness-base` (`0abb293`) era la más avanzada, y `tools/molchat/` salía de la línea experimental `94605d7`, sin publicar y fijada con `oficial: true`. La interfaz incluida no enviaba las acciones que el host ya recibía; el recorrido sólo funcionaba con una copia externa.

**Decisión.** La línea oficial es el harness. `master` avanza sin reescribir la historia hasta `eb39bb82`, y `tools/molchat/` se vendoriza desde un clon del repositorio público con la interfaz construida en ese clon. El paquete de interfaz resultante es el mismo que ya se probaba como copia externa. La línea experimental queda en la rama local `archivo/linea-experimental` del repositorio de MolChat. El mismo día, `master` llega a `e21a093c` con `get_evaluation_status`, y `tools/molchat/` se vuelve a vendorizar desde un clon público de ese commit: el host no cambia, porque la herramienta sólo lee `GET /evaluation/status/{task_id}` con la sesión de la cuenta.

**Cambio en el host.** PubChem lo consulta MolChat con su propio cliente; MolDesign sólo decide el permiso (`/ai/consent/red`). `POST /molchat-host/pubchem/search` y la capacidad `pubchem-lookup/1`, que nunca llegaron a un commit, no entran; se conservan en la rama local `archivo/host-antes-de-consolidar-2026-10-31`.

**Límites que quedan.**

- Las acciones de producto (caso, SMILES, receptor, evaluación y editor) viajan por mensajes entre el iframe y la ventana del host. No están declaradas en `moldesign.molchat/1` ni en el kit de conformidad, y se ofrecen al modelo sin comprobar que la cerradura las tenga.
- Las herramientas sólo se ofrecen con host y con un proveedor que admita llamadas a herramientas: fuera de MolDesign no hay ciclo de herramientas.
- La voz añade seis paquetes al runtime embebido (`faster-whisper`, `ctranslate2`, `onnxruntime`, `av`, `flatbuffers` y `protobuf`). El runtime base publicado, v1.1.2, es del 2026-10-11 y no se ha regenerado.
