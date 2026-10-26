# Justificación de `runFullTrust` para Partner Center

Estado: **borrador para revisión del propietario**, 2026-10-04. Molcy entra como **Beta**.
Texto técnico basado en el código; no acredita aprobación de la Store ni es un dictamen jurídico.
Dónde va: campo Restricted capabilities justification de Partner Center. El manifiesto ya declara
runFullTrust; no se cambió msix/msix-config.json ni se construyó un MSIX para esta revisión.

## Texto a pegar en Partner Center (inglés)

> MolDesign is a desktop application that produces local structural docking evidence for early research.
> It requests **runFullTrust** to launch its embedded Python backend and native scientific child processes
> and to keep SQLite records, poses, logs and videos in the user's writable data directory.
>
> 1. **Embedded CPython** (`python/python.exe`) is launched from the resolved package layout. It serves
>    an HTTP API bound to `127.0.0.1`; the desktop webview connects to the port selected by the launcher.
> 2. **AutoDock Vina** (`tools/vina/vina.exe`) performs docking. The desktop launcher passes its resolved
>    absolute path through VINA_EXECUTABLE_PATH. **xTB**, when requested for quantum descriptors, is
>    looked up at `tools/xtb/xtb-6.7.1/bin/xtb.exe` relative to the installed runtime tree.
> 3. **Open Babel** (`tools/openbabel/bin/obabel.exe`) runs as an independent GPL-2.0-only command-line
>    program. Its adapter verifies the packaged manifest and executable hash and never searches PATH.
> 4. **Molcy (Beta)** creates local molecular videos using **Blender** and **Molecular Nodes**. The backend
>    invokes PowerShell at `%SystemRoot%/System32/WindowsPowerShell/v1.0/powershell.exe`, with the
>    bundled script, resolved absolute Blender path and the current embedded Python executable passed
>    explicitly. Child processes are hidden; render cancellation terminates the owned process tree.
> 5. Blender and Molecular Nodes are **not bundled**. Only an **explicit** user installation request starts
>    a download. Managed Blender is the official portable 5.2.2 Windows ZIP from `download.blender.org`,
>    pinned to **404453484 bytes** and SHA-256
>    `3849d17a682cba006075aaa3f3597ecb5c9c30ec31035b2e092c53e40679b535`.
>    It is verified and extracted into the user's data folder, without administrator elevation.
>    Blender installs `blender_org.molecularnodes` through its official Extensions repository on a separate
>    explicit request. Managed Blender uses a dedicated user profile; an existing Blender chosen by the
>    user uses its own extension profile. The app does not import the GPL extension into its backend.
> 6. The bundled Molcy engine is **GPL-3.0-or-later**, executed as a separate program inside Blender.
>    Its source and license are offered at `https://github.com/srcacahuate619/moldesign-molcy`;
>    `tools/molcy/molcy-manifest.json` identifies the bundled source commit and file hashes.
>
> Normal docking evaluations run offline with locally available inputs and models. Optional installation
> downloads require a network connection and explicit user action. This request does not claim that
> Microsoft's policy for downloading and executing third-party programs has been verified; the publisher
> must obtain that review before submitting Molcy. The engine menu only enables engines that this
> installation reports as executable through GET /evaluation/engines.

## Versión en español (para revisión interna)

> MolDesign produce evidencia estructural de docking local. Requiere **runFullTrust** para lanzar Python
> embebido y programas científicos nativos, y conservar SQLite, poses, registros y vídeos en datos del usuario.
> Python sirve HTTP sólo en `127.0.0.1`; Rust entrega al webview el puerto elegido y pasa a Vina su ruta absoluta.
> xTB se busca en `tools/xtb/xtb-6.7.1/bin/xtb.exe` del runtime. Open Babel se ejecuta como programa independiente,
> con hash/manifiesto verificados y sin búsqueda por PATH.
>
> **Molcy (Beta)** ejecuta PowerShell mediante la ruta absoluta de `%SystemRoot%`, el script incluido,
> Blender seleccionado con ruta absoluta y el Python embebido. Los procesos son ocultos y la cancelación
> termina el árbol propio. El motor GPL-3.0-or-later se ejecuta dentro de Blender; su fuente y licencia se ofrecen
> en `https://github.com/srcacahuate619/moldesign-molcy`, con commit y hashes en el manifiesto incluido.
>
> Blender y Molecular Nodes no viajan en el instalador. Sólo una **solicitud explícita** inicia cada instalación.
> El ZIP oficial de Blender 5.2.2 proviene de download.blender.org, con tamaño 404453484 y SHA-256 fijados
> indicados arriba. Se valida y extrae en datos del usuario sin elevación. Blender instala Molecular Nodes
> desde el repositorio oficial Extensions; el perfil administrado es independiente. Si el usuario elige un
> Blender existente, sus extensiones se instalan en el perfil de ese Blender. El backend no importa la extensión.
>
> El docking normal funciona sin red con entradas y modelos locales; las descargas opcionales sí usan red.
> El menú sólo habilita los motores ejecutables declarados por GET /evaluation/engines.

## Evidencia técnica y límites de la revisión

- `frontend/src-tauri/src/backend.rs`: RuntimeLayout, resolución del Python/Vina, --host 127.0.0.1,
  VINA_EXECUTABLE_PATH, MOLDESIGN_OPENBABEL_DIR y MOLDESIGN_MOLCY_DIR.
- `backend/services/molcy/renderer.py`: Blender absoluto, PowerShell de SystemRoot, parámetros
  -Blender/-Python, rutas de trabajo y caché; `process.py`: Windows Job y taskkill absoluto para el árbol propio.
- `installation.py`: origen, tamaño/hash, validación del ZIP y perfil administrado; `addon.py`:
  comprobación del repositorio oficial y instalación por Blender. `api/routers/molcy.py`:
  POST /molcy/blender y /molcy/addon; la pantalla los llama tras la acción del usuario.
- `utils/procesos.py`: CREATE_NO_WINDOW/CREATE_NEW_PROCESS_GROUP en Windows.
- `services/external_tools/open_babel.py`: ruta y hash sin PATH.
- **La afirmación global «nunca se resuelve nada por PATH» no está demostrada y sería falsa sobre todo el árbol.**
  `vina_service.py`/`preparer.py` tienen `shutil.which` heredado, y `scripts/compute_quantum_features.py`
  recurre a `shutil.which("xtb")` si falta su candidato empaquetado. La ruta normal de Vina de escritorio es
  absoluta; el adaptador de Open Babel y el flujo Molcy revisado no buscan esos programas por PATH.
  Esta revisión no modifica los resolutores ni prueba una instalación con binarios ausentes.

## Notas de riesgo (para la revisión humana)

- La política de la Store sobre descargar y ejecutar programas de terceros **no está verificada**.
  La decisión de enviar corresponde al **propietario**. No se hicieron WACK, MSIX, revisión de Microsoft
  ni una instalación en VM. Si Microsoft exige cambios en msix/msix-config.json, deben proponerse y revisarse
  por separado antes de construir; esta revisión no modifica msix/.
- La fuente del motor identifica un commit concreto (`fuente.commit` de `tools/molcy/molcy-manifest.json`): ese commit tiene
  que existir en el repositorio público antes de distribuir un instalador con ese manifiesto, o la oferta de código fuente de
  la GPL no se cumple. Que el repositorio sea público no demuestra que un commit nuevo ya esté publicado.
- No afirmar afiliación, certificación ni aprobación de Microsoft, Schrödinger, AutoDock o terceros.
- Molcy visualiza estructuras; un vídeo no valida ciencia ni predice actividad o éxito farmacológico.
- La justificación describe procesos y rutas observados en código, no una certificación jurídica de las fronteras GPL.
