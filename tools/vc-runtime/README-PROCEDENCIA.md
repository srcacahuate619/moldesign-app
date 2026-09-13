# Microsoft Visual C++ Runtime x64 — procedencia

Este directorio conserva el conjunto **app-local** mínimo que necesitan los binarios nativos del instalador de MolDesign en una máquina Windows limpia. No es código de MolDesign y no se publica bajo AGPL.

- Componente: Microsoft Visual C++ Redistributable, x64.
- Versión de archivos: 14.50.35719.0.
- Origen de la copia: `Microsoft.VC145.CRT` del redist de Visual Studio 18 usado por el build auditado del 2026-09-04.
- Instalador oficial contrastado: `https://aka.ms/vs/18/release/14.50.35719/VC_redist.x64.exe`.
- Firma Authenticode comprobada: Microsoft Corporation, válida.
- Hashes y tamaño: `vc-runtime-manifest.json`.

Se versionan porque el instalador usa despliegue app-local y debe ser reconstruible sin depender de que la máquina de build conserve una instalación concreta de Visual Studio. `scripts/vc_runtime_source.py` verifica los bytes antes de que `bundle_helper.py` o `stage_openbabel_tool.py` puedan copiarlos. No se copian desde `System32`.

La autorización para redistribuir estos archivos depende de los términos de licencia de Microsoft Visual Studio aplicables al mantenedor que construye y distribuye el producto. Este registro de procedencia no sustituye esa licencia ni una revisión jurídica.