# Justificación de `runFullTrust` para Partner Center

Estado: **borrador para revisión del responsable del producto** (2026-09-12).
No es un dictamen jurídico; es el texto técnico que sustenta la capacidad
restringida ante la revisión de Microsoft.

Dónde va: en Partner Center, campo *Restricted capabilities justification*
al declarar `<rescap:Capability Name="runFullTrust" />`. El paquete ya la
declara y los autotests (`msix/tests/test_msix_contrato.py`) comprueban que está
marcada como restringida. Los hechos técnicos que la sustentan viven en
`msix/msix-config.json → nivel_de_confianza`.

---

## Texto a pegar en Partner Center (inglés)

> MolDesign AI is a local-first desktop application for reproducible structural
> docking evidence in early-stage drug research. It must run with **runFullTrust**
> because its scientific pipeline is executed by child processes and native
> binaries that a sandboxed AppContainer cannot launch:
>
> 1. **Embedded Python runtime** — the backend is a self-contained CPython
>    interpreter (`python/python.exe`) started as a child process that serves a
>    local HTTP API over a loopback socket (`127.0.0.1`), used only by the app's
>    own webview. No remote listening.
> 2. **AutoDock Vina** (`tools/vina/vina.exe`) — an external scientific engine
>    invoked as a subprocess that reads/writes temporary files.
> 3. **Open Babel** (`tools/openbabel/bin/obabel.exe`) — invoked as an
>    independent command-line program to honor its GPL-2.0-only license boundary;
>    it cannot be embedded or hosted in an AppContainer.
> 4. **Local persistence** — the app writes SQLite, docking poses and logs to the
>    user's profile (outside the package), which requires normal file-system
>    access.
>
> The application does **not** use full trust to reach the network: there is no
> server component and no remote code is loaded for the core docking workflow.
> Normal evaluations run entirely offline. `runFullTrust` is requested solely to
> execute the same local scientific toolchain that the MSI/NSIS desktop build
> already runs, so the Store channel is functionally identical to a normal
> Win32 install.

## Versión en español (para revisión interna)

> MolDesign AI es una aplicación de escritorio local-first para evidencia de
> docking estructural reproducible en etapas tempranas de investigación. Necesita
> **runFullTrust** porque su pipeline científico se ejecuta mediante procesos y
> binarios nativos que un AppContainer no puede lanzar:
>
> 1. **Intérprete Python embebido** — el backend es un CPython autocontenido
>    lanzado como proceso hijo que sirve una API HTTP local sobre `127.0.0.1`,
>    solo para el webview de la propia app. No escucha de forma remota.
> 2. **AutoDock Vina** — motor científico externo invocado como subproceso que
>    lee/escribe temporales.
> 3. **Open Babel** — invocado como programa independiente para respetar la
>    frontera de su licencia GPL-2.0-only; no puede ir embebido ni en un
>    AppContainer.
> 4. **Persistencia local** — escribe SQLite, poses y logs en el perfil del
>    usuario (fuera del paquete), algo que exige acceso normal al sistema de
>    archivos.
>
> La aplicación **no** usa plena confianza para llegar a la red: no hay servidor
> y no se carga código remoto en el flujo de docking. Las evaluaciones normales
> corren sin red. `runFullTrust` se pide solo para ejecutar las mismas
> herramientas científicas locales que ya ejecuta la compilación de escritorio
> MSI/NSIS, de modo que el canal Store es funcionalmente idéntico a una
> instalación Win32 normal.

---

## Notas de riesgo (para la revisión humana)

- **No** afirmar afiliación, certificación ni aprobación de Microsoft, Schrödinger,
  AutoDock, RCSB PDB, PDBbind, Meta, Prior Labs ni otros terceros.
- **No** afirmar validación clínica, predicción de éxito farmacológico ni
  funcionalidad *drug discovery* end-to-end. El contrato del producto es
  preparación/auditoría estructural, no predicción de actividad.
- El texto debe mencionar que el menú avanzado nombra varios motores pero sólo
  ejecuta lo que declara `GET /evaluation/engines`; no prometer motores futuros.