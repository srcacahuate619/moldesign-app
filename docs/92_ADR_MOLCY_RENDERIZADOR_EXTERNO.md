# ADR 92 — Molcy como renderizador externo en 1.0.2

> **Actualizado el 2026-10-04.** Tres cosas de este documento ya no son ciertas: (1) el motor Molcy **sí** viaja en el instalador, como programa
> independiente GPL-3.0-or-later (ADR 95); (2) el Blender administrado se instala en la carpeta de datos del usuario, no junto al programa (apartado
> «Corrección del 2026-10-04»); (3) el detector exige **Blender 5.2 o superior**, no 4.2 (el motor sólo funciona en 5.2.x: probado con 4.2.23 y 4.5.14).

**Estado:** integrado localmente en `codex/release-hygiene`, con export y runtime staged verificados; pendiente de build de instalador y verificación en WebView2. **Fecha:** 2026-09-28; ampliado el 2026-09-29; integración verificada el 2026-10-03.

## Decisión

MolDesign prepara un paquete local verificable y ejecuta Molcy como programa independiente en Blender. La versión 1.0.2 detecta una instalación local de Blender 4.2+ con Molecular Nodes y una ruta local del motor Molcy. También admite `MOLCY_BLENDER_PATH` y `MOLCY_ENGINE_DIR`. No incluye Blender ni el motor Molcy en el instalador base. Si sólo falta Molecular Nodes, el investigador puede pedir su instalación desde la pestaña: Blender sincroniza su repositorio oficial, descarga la extensión y la habilita en su propio perfil. No hay descarga al abrir la pestaña ni importación del complemento en MolDesign. El usuario elige GPU con EEVEE o CPU con Cycles. La prueba de ambos dispositivos es local; GPU sólo aparece habilitada cuando EEVEE rinde un cuadro de prueba. Una GPU integrada puede superar esa prueba.

La frontera sigue este orden: `EvaluationRunORM.snapshot_json` de una corrida exitosa y guardada en Moldex, o un receptor accesible del catálogo → verificación de archivos y SHA-256 → `scene.json`, geometría PDB derivada del PDBQT preparado, `docking.json` si hay poses, y `MANIFEST.sha256` → `powershell.exe` de ruta absoluta que invoca `correr_caso.ps1` → Blender de ruta absoluta que ejecuta `maestro.py` → MP4 y acta con SHA-256. El backend jamás importa `bpy`, Molecular Nodes ni módulos del motor. El trabajo vive en `LOCAL_DATA_DIR/molcy/<usuario>/<trabajo>`; no hay tablas nuevas. Un render interrumpido al cerrar el proceso se marca fallido al consultarlo, sin presentar un MP4 incompleto como terminado.

## Archivos del caso (cambio del 2026-10-06)

Los renders nuevos de una corrida asociada a un caso se guardan en
`<carpeta del caso>/molcy/NNN_<receptor>_<PDB>_<task_id>/`. El consecutivo
permite varios vídeos de la misma corrida; `task_id` es su UUID de Moldex.
`salida/` contiene el MP4 y el acta; el paquete de entrada, estado y log
permanecen en el mismo trabajo. El nombre del receptor se normaliza para el
sistema de archivos y se limita a 40 caracteres.

Rust entrega al backend `MOLDESIGN_CASE_REGISTRY`, apuntando a su registro de
carpetas autorizadas. El backend comprueba el ID y el propietario de `case.json`
y busca la corrida en `runs` (o `activeRun` en manifiestos anteriores). No recibe
una ruta de escritura desde la webview. Una corrida asociada a varios casos se
bloquea. Un índice en `LOCAL_DATA_DIR/molcy/<usuario>/<trabajo>/ubicacion.json`
conserva sólo el ID del caso y el nombre relativo del trabajo: al reubicar el
caso desde Casos, Molcy resuelve su nueva ubicación.

Los trabajos anteriores conservan sus archivos originales. Las corridas sin
caso disponible y los vídeos generados directamente desde el catálogo de
receptores conservan el almacenamiento local anterior; la selección de Moldex
indica cuándo no se encontró un caso disponible. La caché del cierre sigue
compartida en `LOCAL_DATA_DIR/molcy/cache/cierre`. Se comprueba el espacio en la
unidad del trabajo y en la caché, y se vigila la reserva durante el render.

El historial muestra el caso y omite el bloque «Ubicación exacta». En Windows,
«Mostrar MP4 en Explorador» verifica el SHA-256 y usa
`SHOpenFolderAndSelectItems` con el identificador absoluto del archivo para
abrir su carpeta y seleccionarlo, sin argumentos `/select` que puedan
interpretarse mal con espacios. El reproductor emergente sigue siendo
independiente del vídeo central. Este cambio requiere reconstruir frontend,
backend empaquetado y contenedor Rust; no modifica el motor Molcy.

### Regresión de rutas extendidas corregida el 2026-10-06

Dos intentos de la escena Ensamble de 5TBO fallaron a los 1,04 y 0,62 s,
antes de lanzar Blender. El registro autorizado de Rust conservaba la ruta
canónica `\\?\F:\...`; `Join-Path` de Windows PowerShell 5.1 fallaba con
«drive es NULL» y `Out-File` tampoco podía crear los logs. Fue una regresión
de la integración con las carpetas del caso, no una abstención científica.

El adaptador conserva las rutas canónicas para autorización y comprobaciones
de contención. Al serializar argumentos y directorios del proceso externo,
convierte rutas extendidas de unidad y UNC a su escritura habitual. Incluye
entrada, salida, temporales, caché, plantilla, ejecutables y perfil de Blender.
La selección de MP4 en el Explorador comparte esta conversión. Otros namespaces
extendidos se rechazan sin transformarlos en rutas relativas.

La reproducción aislada con PowerShell 5.1 falla con el prefijo original y
funciona con la conversión, incluso con espacios y acentos. Con una copia del
paquete fallido, Blender 5.2.2 y el motor incluido produjeron `CONSTRUIDO_OK`
para `ensamble_conformacional`, formato `social_vertical`, dispositivo GPU,
sin `QC_ABORTADO`. Se usó `-SoloConstruir` para comprobar construcción y QC;
no demuestra todavía el render, título, cierre y codificación del MP4 completo.
Los hashes de todos los archivos del trabajo original permanecieron iguales.
Evidencia local: `dist/molcy-diagnostico-20261006/resultado.json` (ahora en F:\Backups\moldesign-evidencia\2026-10-10-limpieza-D\dist\molcy-diagnostico-20261006) y logs anexos.
Los tres archivos Python corregidos se copiaron al runtime ya preparado y se
precompilaron con Python embebido 3.11.9; sus hashes coinciden con el código
fuente. El motor incluido conserva sus 54 archivos íntegros. `smoke:prod`
aprobó 28/28 comprobaciones sobre ese runtime y el export existente. No se
construyó un nuevo instalador.

## Contrato científico

Para Moldex se identifica `task_id` de la corrida, se lee su snapshot inmutable y se verifica el receptor preparado y la colección SDF de poses con los hashes persistidos. La caja se toma de `docking_protocol.execution_provenance`; el SDF top-1 se convierte a PDB visual conservando sus coordenadas. `docking.json` conserva motor, versión, semilla, caja, afinidad y hashes. El PDB visual del receptor conserva coordenadas y numeración del PDBQT; se detectan saltos entre Cα y se declaran en `scene.json`. El motor debe cortar la cinta en esos huecos. El paquete prohíbe dibujar una trayectoria de unión o búsqueda no registrada. La escena `resultado` muestra la primera pose de Vina. `busqueda` exige una traza interna verificable de la misma corrida; `ensamble` exige evidencia recuperable de las conformaciones, corridas y poses. Ambas requieren un motor incluido que contenga sus guiones y se abstienen si no pueden recuperar y verificar sus archivos.

Para un receptor interno o añadido por el usuario, la escena `receptor` sólo muestra la estructura preparada y el encuadre. Si no existe un preparado pero existe la fuente local, la preparación oficial del producto se ejecuta bajo demanda. No se atribuyen poses, contactos, afinidad ni actividad. Si faltan geometría, hashes, caja, Blender, addon o motor, se informa el motivo y se abstiene.

El paquete y el MP4 son artefactos locales. `GET /molcy/fuentes` enumera corridas de moléculas guardadas y receptores accesibles; `POST /molcy/trabajos` vuelve a comprobar propiedad, hashes, capacidad y espacio libre antes de iniciar. Las rutas de estado y descarga usan el UUID del usuario autenticado. El MP4 se verifica contra el acta antes de declararlo completo y antes de servirlo. `GET/POST /molcy/addon` expone el estado de una instalación solicitada por el usuario; sólo se admite cuando el detector identifica la ausencia de la extensión, con `blender_org` apuntando al repositorio oficial de Blender.

## Distribución y licencias

MolDesign mantiene PolyForm Noncommercial 1.0.0. Molcy permanece en su repositorio independiente bajo GPL-3.0 y usa `bpy` y Molecular Nodes dentro de Blender. La integración adopta la frontera de programa independiente y mera agregación prevista por el propietario, siguiendo el patrón técnico del ADR 79 para Open Babel. Esto documenta la arquitectura adoptada; no equivale a un dictamen jurídico sobre una distribución futura. Blender y el motor se obtienen/configuran aparte por el investigador; el addon puede instalarse explícitamente desde MolDesign por medio del gestor oficial de Blender.

## Recursos y abstención

La disponibilidad exige una prueba Cycles CPU de 8×8; una prueba EEVEE independiente determina la opción GPU. No se afirma que una GPU sin memoria suficiente pueda completar una escena grande ni que Blender arranque en Windows físicamente sin hardware gráfico compatible. Los presupuestos de disco usan los tamaños y fotogramas de los tres formatos del motor, RGBA de 8 bits sin compresión, una pasada de título conservadora, cierre de marca, espacio para MP4 y 1 GiB de reserva. Una verificación del código de formatos impide usar presupuestos obsoletos. La API y la interfaz bloquean el inicio cuando la unidad de salida no llega al presupuesto; el motor vuelve a comprobar el espacio antes de cada PNG y antes de codificar. El cierre de marca se guarda en `LOCAL_DATA_DIR/molcy/cache/cierre`, separado por formato y dispositivo, para no escribir dentro de un motor instalado en una carpeta de sólo lectura. La página calcula el tiempo restante del render principal usando los últimos cinco PNG del trabajo; no presenta un tiempo antes de medirlos ni incluye título, cierre y codificación en esa cifra. Véase [la medición y los límites](93_MOLCY_RECURSOS_Y_LIMITES.md).

## Ampliación autorizada del 2026-09-29

CPU limita la escena molecular a **tres segundos**, conserva la resolución del formato y añade su outro MolDesign. La previsualización CPU entrega 6,6 s (3 + 3,6); la horizontal conserva su outro de 4,4 s. GPU conserva sus duraciones. El backend exige que el acta acredite Cycles CPU, duración y cierre; no sustituye un render solicitado por otro dispositivo en silencio.

`MOLDESIGN_INSTALL_DIR`, resuelto por el contenedor Rust desde el ejecutable instalado, define `tools/blender/blender-5.2.2-windows-x64/blender.exe`. La descarga explícita usa el ZIP oficial de Blender Foundation (404.453.484 bytes), tamaño y SHA-256 fijados, valida su estructura y reserva espacio tanto en la unidad de descarga como en la de instalación. Si la carpeta está protegida, sólo la extracción verificada pide elevación de Windows; el backend y los renders no se elevan. El hash se verifica también dentro del proceso elevado. Un ZIP inválido, UAC rechazado, falta de red o falta de espacio no se presenta como instalación terminada.

El Blender administrado usa un perfil de extensiones y preferencias aislado en `LOCAL_DATA_DIR/molcy/perfil_blender/5.2.2`. La alternativa de Blender existente conserva su ejecutable y su perfil al renderizar; si el usuario solicita instalar Molecular Nodes en él, su gestor oficial instala la extensión en ese perfil. El modo administrado es el recomendado. La instalación y configuración del motor independiente siguen separadas de la descarga de Blender.

Una reserva limita a un trabajo activo por backend, incluida la exportación. Tauri ya usa `tauri-plugin-single-instance`; dos backends lanzados manualmente siguen siendo un entorno no cubierto por esa garantía. Configuración, instalación del addon, descarga de Blender y render no pueden pisarse. Los renders usan un Job Object de Windows para terminar descendientes al cancelar/cerrar el backend, y una ruta temporal por trabajo en la misma unidad presupuestada. El historial conserva estados; permite seleccionar trabajos y eliminar sus archivos sin borrar la evaluación. Tras fallo o cancelación normal se retiran PNG parciales; tras cierre abrupto el historial informa interrupción y permite limpiar el trabajo.

Con autorización explícita del propietario, `media-src` permite sólo el origen propio y los servidores locales `127.0.0.1`/`localhost` en las CSP de Tauri y Next. El acceso de reproducción lo emite el propietario autenticado del trabajo, caduca a la hora y admite Range; no lleva el JWT en la URL. Reproducción y descarga MP4 son transferencias directas, sin cargar el video completo en un Blob del WebView. La procedencia se descarga como JSON separado. Hay reintento para renovar el acceso; al cambiar de cuenta se reinicia la vista. El guardián CSP tiene muestras positivas y negativas.

## Corrección del 2026-10-04: el Blender administrado se instala en la carpeta de datos

La ampliación del 2026-09-29 puso el Blender administrado en `<instalación>/tools/blender/` y pedía elevación de Windows si
esa carpeta estaba protegida. Eso no funciona en la build de la Microsoft Store: `C:\Program Files\WindowsApps\...` es de sólo
lectura para la app y también para un proceso elevado (la regla está en `msix/README.md` y en el doc 86), así que «Descargar
Blender» habría bajado 404 MB, pedido UAC y fallado. En una instalación por máquina exigía además un PowerShell elevado.

Ahora vive en `LOCAL_DATA_DIR/molcy/blender/blender-5.2.2-windows-x64/` —donde MolDesign ya escribe sus datos— y se instala sin
elevación: descarga con tamaño y SHA-256 fijados, validación del ZIP (rutas, enlaces simbólicos, tamaño), nueva comprobación del
hash dentro de `_promote`, extracción en una carpeta temporal hermana y renombrado. No se lanza PowerShell ni existe
`-Verb RunAs`. `MOLDESIGN_INSTALL_DIR` sigue existiendo (Rust lo entrega) pero Molcy ya no lo lee. El perfil aislado de Blender
y el modo «Usar mi Blender» no cambian. Las pruebas de `test_molcy_maduracion.py` fijan que el instalador no tiene camino de
elevación; el smoke de producción comprueba que la ruta cuelga de la carpeta de datos.

## Verificado y pendiente

- Dos videos reales de la misma corrida Vina guardada para Moldex terminaron por GPU y CPU con el Blender administrado descargado e instalación nueva de Molecular Nodes. La UI descargó ambos y sus hashes coinciden con sus actas. Edge reprodujo 3 s GPU y 6,6 s CPU, avanzó y buscó dentro de ambos sin bloqueo de medios. Condiciones, tiempos y límites en [recursos y pruebas](93_MOLCY_RECURSOS_Y_LIMITES.md).
- CPU se ensayó en una estación que también tiene GPU, forzando Cycles CPU con 11 hilos. No demuestra compatibilidad de Windows físicamente sin hardware gráfico ni rendimiento de gráficos integrados o de otra CPU.
- Los formatos completos 16:9 y 9:16, UAC real dentro de Program Files, instalación en otra máquina y WebView2 siguen pendientes. Se respetó el máximo de dos renders completos de esta iteración.
- `smoke:prod` se intentó y terminó en su precondición: falta `frontend/out`. No se construyó ni staged nada para solventarlo, por instrucción del propietario. La ruta Rust se formateó; no se compiló.
- Edge/Next dev mostró un aviso de hidratación en el `head` del layout global (script 3Dmol/JSON-LD), fuera de los archivos Molcy modificados. Se registra para la revisión del frontend y del artefacto; reproducir videos no demuestra que ese aviso esté resuelto.
- La distribución del motor GPL independiente requiere preparar y verificar su paquete complementario. Configurar una carpeta local está probado; una descarga de Blender por sí sola no aporta el motor Molcy.
- No hay cola persistente ni reanudación automática de un render interrumpido. El usuario puede eliminarlo e iniciar uno nuevo. La prueba pequeña del dispositivo no garantiza RAM/VRAM suficiente para cualquier receptor.

## Integración con Sol/Luna — 2026-10-03

Fusión local con `--no-ff` de Molcy (`27fea69`) sobre el cierre Sol/Luna
(`ea01cc6`), con ancestro común `2bfda5e`. Los únicos conflictos de contenido
fueron el mapa API y el total del registro de pruebas. Se regeneraron con los
scripts del contrato y del conteo, usando Python embebido 3.11.9; también se
sincronizó el JSON OpenAPI que Git había fusionado automáticamente.

La comparación con ambos padres conserva los cambios de código de las dos
ramas, todas sus rutas y los esquemas actualizados por Sol/Luna. El export
incluye `/molcy` y `/preparacion`; no se retiraron funciones para resolver la
fusión. El contrato combinado tiene 132 rutas y 142 operaciones HTTP.

| Verificación | Resultado y condición |
|---|---|
| Backend completo | Python embebido 3.11.9: 3224 aprobadas, 17 omitidas; 3239 ítems recolectados. Dos de las omisiones son módulos sin `pypdf`, que pytest cuenta fuera de esos ítems. |
| Integración seleccionada | 211 aprobadas: Molcy, Preparación, propuestas de MolChat, OpenAPI, frontera Open Babel y corridas doradas. |
| Frontend completo | 1280 aprobadas en 137 archivos, con cuatro workers; TypeScript y lint Molcy correctos. |
| Rust | `cargo fmt --check` y `cargo check --locked --offline` correctos. |
| Contrato, SBOM y goldens | OpenAPI vigente, cobertura de licencias completa y ocho corridas doradas verificadas. |
| Runtime staged | 35248 archivos, 1826,3 MiB; backend actualizado, dependencias nativas, modelos ligeros, Vina y `/health` verificados, sin mutar el runtime. |
| Frontera Open Babel | 17 comprobaciones aprobadas sobre repositorio y bundle. |
| Export de producción | Build limpio aprobado; 252 archivos sin backend horneado y 18 CSS/HTML sin recursos remotos. |
| Smoke de producción | 18/18, con Chrome, export real, CSP de producción, Python empaquetado y datos temporales aislados. |

El smoke ahora comunica `MOLDESIGN_INSTALL_DIR`, como Rust, y comprueba con
autenticación que `/molcy/blender` existe en el bundle y resuelve la raíz
instalada. Las primeras ejecuciones encontraron aislamiento de temporales y
permisos del sandbox; el build posterior encontró una caché incompleta. Las
pruebas se repitieron fuera del sandbox y el export se construyó desde caché
limpia, sin cambios funcionales para hacerlas pasar.

Logs y comparación de preservación: `dist/qa-merge-molcy-20261003`. Son
artefactos QA de la fusión, generados antes del commit, no un release sellado.
Esta verificación no ejecutó nuevos renders ni construyó un instalador; el
smoke usa un puente Tauri simulado en Chrome. Siguen pendientes los ensayos
del instalador/WebView2 y del render real descritos arriba.
