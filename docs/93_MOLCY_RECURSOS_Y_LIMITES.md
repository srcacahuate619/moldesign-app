# Molcy 1.0.2 — recursos y casos límite (actualizado 2026-09-29)

## Recorrido real de esta iteración — medido

Windows, **AMD Ryzen 5 5500 (12 procesadores lógicos), NVIDIA GeForce GTX 1660 SUPER**, Blender 5.2.2 y Molecular Nodes 520.2.0. Blender se descargó de Blender Foundation a la carpeta interna de una instalación QA; el addon se instaló en un perfil nuevo, sin usar la instalación personal. El ZIP oficial mide 404.453.484 bytes y su SHA-256 es `3849d17a682cba006075aaa3f3597ecb5c9c30ec31035b2e092c53e40679b535`. La instalación de la extensión y la primera comprobación de dispositivos tardaron 48,67 s; esta cifra no es el tiempo de descargar Blender.

La evaluación real de aspirina contra el receptor preparado 1AJ6 terminó con Vina 1.2.7, semilla 42, exhaustividad 1 y una pose. El score de −5,573 kcal/mol está condicionado a esa corrida, caja y preparación; no es actividad biológica. Se guardó la molécula en la base QA para que apareciera en Moldex. La evaluación se lanzó por API y el indicador de guardado se persistió en SQLite; no se ensayó en esta iteración el clic de guardado de la pestaña Evaluación. Molcy sí seleccionó la corrida, generó y descargó desde la página en Edge.

| Modo | Construcción | Render molecular (90 cuadros, 720×720, 48 muestras) | Tiempo del trabajo completo observado por QA | Duración final | Bytes |
|---|---:|---:|---:|---:|---:|
| GPU, EEVEE | 2,6 s | 48,4 s | 65,288 s | 3,0 s | 1.082.530 |
| CPU, Cycles, 11 hilos, denoising | 2,6 s | 476,3 s | 1.044,767 s | 6,6 s (3 + 3,6) | 1.876.575 |

El tiempo del trabajo incluye lanzamiento, fotogramas, codificación y comprobaciones; se observó con sondeo de cinco segundos y excluye el sondeo inicial de disponibilidad. CPU generó además por primera vez 108 cuadros del outro, con 64 muestras, unos nueve minutos adicionales, y dejó el cierre en caché. **No se midió un segundo video CPU con caché caliente**; no se presenta como medido el ahorro esperado. El tramo molecular CPU fue 9,84 veces el de EEVEE en este caso. La apariencia y el cálculo de iluminación son distintos: el cociente no demuestra equivalencia visual.

Hashes de los MP4 descargados desde la UI:

- GPU: `d2bd0a9f632234865167602c1f8e109d1b76bf382d77dd39af2d0456b2920760`.
- CPU: `2bea4a79ff14946b0c60e005ab0ed8ac0e490a394de92b4fbd8b8846a793fd51`.

Videos, actas, procedencia, capturas y resultados de reproducción: `D:\moldesign-build\dist\molcy-maduracion-20260929` (ahora en F:\Backups\moldesign-evidencia\2026-10-10-limpieza-D\dist\molcy-maduracion-20260929). Los nombres son `molcy-moldex-gpu.mp4`, `molcy-moldex-cpu.mp4`, `procedencia-<modo>.json` y `reproduccion-resultados.json`. Edge comprobó metadatos 720×720, avance y búsqueda de ambos MP4. No hubo error del elemento video ni bloqueo de `media-src`. Se observó además un aviso de hidratación del layout global de Next; no se cuenta como corregido por esta iteración. El backend reducido de QA no incluye `/ai/providers`, `/ai/startup` ni `/ai/consent`; sus 404 de consola no corresponden a Molcy. Las rutas Molcy sí se ejecutaron con autenticación real.

## Presupuestos actuales y guardas de disco

La cota cuenta dos secuencias completas de PNG RGBA de ocho bits (escena y título), cierre, 0,5 GiB de codificación y 1 GiB de reserva. CPU acorta la escena a 90 cuadros y la previsualización CPU incorpora también el outro. No son tamaños esperados de videos ni una predicción del consumo típico:

| Formato del motor | Reserva GPU | Reserva CPU |
|---|---:|---:|
| previsualizacion | 1.86 GiB | 2.07 GiB |
| social_vertical | 7.95 GiB | 3.74 GiB |
| biblioteca | 13.13 GiB | 3.93 GiB |

La API comprueba el presupuesto antes de exportar y el trabajador lo repite antes del proceso. El motor verifica la reserva antes de cada PNG y de la codificación; los temporales de Blender se ubican en el trabajo, en esa unidad. Caer por debajo de la reserva produce un trabajo fallido con motivo; no se intenta seguir llenando la unidad. Se prueban umbrales y agotamiento durante el render con espacio simulado, sin llenar físicamente el disco.

Instalar Blender requiere el ZIP, hasta 3 GiB de extracción y 1 GiB de reserva (~4,4 GiB conservadores) en la unidad de instalación; la unidad de descarga requiere ZIP + reserva. El ZIP se valida por tamaño/hash y estructura, y se vuelve a verificar en el proceso elevado. Molecular Nodes exige 1 GiB libre en su perfil. No hay descargas automáticas al abrir Molcy.

## Escenarios y cobertura actual

| Caso | Mitigación implementada | Evidencia o límite |
|---|---|---|
| Sin Blender | Descarga explícita o ruta absoluta a Blender existente; sin render hasta sondeo válido | Descarga e instalación real en carpeta QA escribible |
| Blender sin Molecular Nodes | Botón con motivo/tamaño; gestor oficial; fases y error | Instalación real en perfil administrado nuevo |
| Disco insuficiente antes/durante render | Presupuesto por formato/dispositivo, reserva por PNG y antes de MP4; limpieza tras terminar | Pruebas de umbral y fallo simulado |
| Disco insuficiente al instalar | Comprobación de ambas unidades antes de red y repetida durante descarga/antes de extracción | Pruebas sin llenar la unidad |
| ZIP corrupto, ruta maliciosa o descarga incompleta | Tamaño, SHA-256, rutas internas y límite de extracción; no promoción | Pruebas negativas; hash oficial verificado en descarga real |
| Carpeta protegida o rechazo UAC | Elevación sólo de extracción oficial, backend/render sin privilegios; mensaje de fallo | Ruta de rechazo simulada; UAC real en Program Files pendiente |
| Descarga cancelada | Cancela antes de aplicar y limpia su carpeta temporal; no afirma éxito | Prueba de cancelación; aplicación/elevación ya iniciada no es cancelable |
| GPU ausente/no compatible | Cycles CPU habilitado sólo si supera sondeo; GPU deshabilitada si EEVEE falla | Simulación de fallo GPU y render CPU real; PC físicamente sin hardware gráfico pendiente |
| CPU con gráficos integrados | Puede ofrecer CPU y GPU si ambos sondeos funcionan; recomienda GPU con caveat de rendimiento | No se dispone de equipo integrado ensayado; una prueba pequeña no acredita toda escena |
| CPU/GPU con memoria insuficiente | Un trabajo activo, CPU limita sus hilos a N−1 (mínimo uno), error del proceso recuperable, opción CPU manual | Pico RAM/VRAM y receptores grandes aún sin medir; no hay fallback silencioso |
| Doble clic o abrir otro video mientras se renderiza | Reserva antes de exportación, envío bloqueado e historial identifica activo | Pruebas backend/UI |
| Cambiar instalación durante render/addon | Rechazo 409 y controles bloqueados | Pruebas de concurrencia |
| Cancelar render | Cancela el árbol propio de procesos y limpia PNG/temporales | Prueba con un descendiente Python real en Windows; no un Blender completo cancelado |
| Cierre abrupto | Job Object; estado interrumpido al volver; borrar archivos desde historial | Semántica de Windows y prueba de reinicio de estado; cierre forzado real de app pendiente |
| Estado JSON dañado | Trabajo fallido, sin excepción ni video presentado como válido | Prueba con null/lista/identidad incorrecta |
| Video corrupto o de otro usuario | SHA-256 antes de servir, propiedad al emitir acceso, historial por usuario | Pruebas de dueño, hash, expiración y Range |
| Acceso de video caducado | Reintentar renueva el acceso; descarga directa sigue disponible | Pruebas API/UI |
| Video grande en WebView | Streaming y descarga directa; no Blob completo del MP4 | Descarga real por botón y reproducción con búsqueda |
| Cambiar de cuenta | Reinicia la vista y evita restauración tardía de otra cuenta | Prueba UI |
| Corte de red al descargar | Se informa fallo y limpia la descarga propia; volver a iniciar es explícito | Ramas de error; redes/proxies variados pendientes |
| Otra versión de Blender/addon | Sondeo local y motivo si falla; Blender administrado 5.2.2 recomendado | Sólo la combinación 5.2.2/520.2.0 pasó estos MP4; compatibilidad de otras versiones requiere prueba propia |
| Fuente borrada/corrupta o sin poses verificables | Hashes y requisitos vuelven a validarse al crear el trabajo; error y abstención | Pruebas de snapshot/hash manipulado; no se reconstruyen datos ficticios |
| Archivo externo de receptor inválido | Se reutilizan validación y preparación del catálogo; render sólo con estructura local disponible | Formulario/selección verificados; MP4 específico de un receptor subido sigue pendiente |
| Actualizar/desinstalar app, antivirus o instalación administrada dañada | Falla el sondeo y puede elegirse un Blender compatible existente | Reparación automática, migración y limpieza del instalador aún sin verificar |
| Motor ausente/incompatible | Se abstiene; ruta configurable y prueba de contrato/formato | Configuración local real; paquete complementario aún pendiente |
| Varias instancias | Tauri ya usa single-instance y el backend reserva un trabajo | Backends manuales simultáneos no se coordinan globalmente |
| Formatos finales 16:9/9:16 | Contrato de duración CPU y presupuesto calculado por formato | Pruebas del motor; falta MP4 completo de cada formato |
| Batería, suspensión, térmicas | CPU limita sus hilos a N−1 (mínimo uno); cancelación/error disponibles | No se han medido laptops, suspensión ni límites térmicos |

## Puertas ejecutadas sin build

Backend completo: **2.946 passed, 47 skipped**, 237,54 s, Python embebido 3.11.9 y `LOCAL_DATA_DIR` de pruebas. Frontend: **1.112/1.112**, 122 archivos, 68,45 s. Rescoring: **313 passed, 12 skipped**. Motor: **54 passed, 2 skipped**. TypeScript sin errores; ESLint completo sin errores y 39 advertencias existentes fuera de Molcy. El guardián CSP pasó con sus autotests. `smoke:prod` no pudo continuar: falta `frontend/out`. No se hizo build, staging, merge ni push. Después del último mensaje CPU se repitieron las 30 pruebas de Molcy/idiomas afectadas, TypeScript y ESLint de archivos modificados, sin errores. No se declara verificado el instalador ni WebView2. Los servidores, cuenta, datos de ejecución e instalación QA se retiraron; se conservan MP4, actas, capturas, logs y `escena-verificada` sin credenciales.

## Antecedentes medidos el 2026-09-28

Las siguientes pruebas históricas preceden el límite y el outro CPU de esta iteración. Se conservan con sus condiciones; sus duraciones no describen el video CPU actual.

## Medición CPU

**Medido:** Blender 5.2.2 LTS en Windows, AMD Ryzen 5 5500 (12 procesadores lógicos), escena real `1M17_previsualizacion_ui_20260922_0958.blend` ya construida por Molcy. Se cambió únicamente el motor de render a Cycles, dispositivo `CPU`, 48 muestras sin denoising, 720×720, PNG, cuadros 1–90. Los 90 PNG terminaron en **259,94 s** (2,89 s/cuadro en promedio) y ocuparon **50.927.810 bytes**. Los cuadros 1, 45 y 90 se inspeccionaron; la estructura es visible. El codificador de Molcy produjo después un MP4 de **1.116.418 bytes**, 90 cuadros verificados, en **3,16 s**; SHA-256 `f4dbb8eba22c9ce1984ffc04f2a24114ff70cf3e756b90aea247e009ab95d517`. El tramo render CPU → MP4 tomó unos **263,1 s**, excluidos los pocos segundos de lanzamiento y copia para la prueba. La prueba se hizo en sandbox: Blender no pudo cargar el addon del perfil del usuario, pero la geometría ya estaba guardada en el `.blend`. Por ello esta medida cubre **el render y la codificación de una escena construida**, no la construcción desde una corrida en una PC físicamente sin GPU.

**Referencia separada:** dos previsualizaciones completas con EEVEE en esta misma máquina tardaron 46,4 y 46,8 s para 90 cuadros de 720×720, según el informe de integración. Cambiar EEVEE por Cycles altera iluminación y materiales; la comparación de tiempos no demuestra equivalencia visual. No extrapolamos 90 cuadros a los formatos horizontal y vertical: resolución, muestras, título y cierre cambian. La versión 1.0.2 ofrece ahora Cycles CPU como opción; la medida anterior sigue siendo sólo un ensayo desde un `.blend` ya construido.

## Prueba nueva del motor completo, CPU frente a GPU

**Medido el 2026-09-28:** se entregó al motor externo el mismo paquete local verificado de receptor `1AJ6` y se ejecutó `correr_caso.ps1` desde escena hasta MP4 en ambos modos, uno después del otro. Blender 5.2.2 y Molecular Nodes 520.2.0; previsualización 1:1 de 90 cuadros a 720×720 y 48 muestras. En CPU, Cycles usó 11 de los 12 procesadores lógicos del Ryzen 5 5500 y denoising. EEVEE usó la GPU de la estación.

| Modo | Construcción | Render principal | MP4 sellado | SHA-256 |
|---|---:|---:|---:|---|
| EEVEE GPU | 3,0 s | 46,4 s | 1.104.892 bytes | `6ae4dfd86529926a79521ad42da791aca9f7158b4ff2f27d02d600bc8b469a29` |
| Cycles CPU | 1,8 s | 476,8 s | 1.023.567 bytes | `db04160593725f8114fb571b2f353970533b0a66ef827d33fd5b87e830f956a3` |

El render principal CPU tardó **10,3 veces** lo que EEVEE GPU en esta comparación. Ambos MP4 pasaron codificación de 90 cuadros, sello SHA-256 y postcheck de nitidez. Se conservaron en `D:\moldesign-build\dist\molcy-cpu-gpu-qa-20260928\salida_<modo>` (ahora en F:\Backups\moldesign-evidencia\2026-10-10-limpieza-D\dist\molcy-cpu-gpu-qa-20260928). Se inspeccionó un PNG CPU de la escena; el receptor era visible. Además, el cierre de marca en modo CPU construyó y rindió un cuadro de prueba del formato horizontal al 5 % de resolución. Esta prueba cubre el **motor desde el paquete hasta el MP4**, no una sesión de la interfaz o el instalador; tampoco prueba Windows sin ningún hardware gráfico. La previsualización no lleva cierre ni pasada de título. Faltan vídeos completos 16:9 y 9:16 para comparar calidad y costes de cierre.


## Iteración DevOps: selección CPU, 2026-09-29

Se añadió la elección de hilos lógicos de CPU y estimación previa por historial
local comparable, sin inventar valores si falta una medición. El motor `adb6a4f`
aplica el valor a escena y outro; el acta lo acredita. La proyección sólo cubre
el tramo molecular y no garantiza aceleración proporcional. Se verificaron los
valores 1 y 4 en Cycles real con sondeos 8×8 y en la configuración del outro;
no se generaron videos completos adicionales. Las siete puertas locales pasaron
(69 backend Molcy, 36 frontend/guardianes, 61 motor con dos omitidas).
El procedimiento y sus límites están en [operación CPU](MOLCY_DEVOPS_CPU.md).

## Cierre obligatorio y autodetección de Blender — medido el 2026-10-04

Máquina: Windows 11, AMD Ryzen 5 5500 (12 hilos lógicos), cápsula 3 de QA con Blender 5.2.2 administrado, Molecular Nodes 520.2.0 y el motor
incluido (`tools/molcy`, commit del manifiesto `757979ce`). Receptor 1AJ6, vista previa 1:1.

### El cierre de MolDesign en todo video

| Prueba | Resultado |
|---|---|
| «Prueba» en GPU (EEVEE) | completa en 176 s la primera vez (incluye generar la caché del cierre `previsualizacion_gpu`); MP4 de 198 fotogramas, **6,6 s** según el átomo `mvhd` que lee el backend; acta: `formato.cierre_s = 3,6`, `cierre.fotogramas = 108`, `duracion_s = 3,0` |
| «Prueba» en CPU (Cycles, 4 hilos) | completa en 1079 s; MP4 de **6,6 s**; mismo acta de cierre (108 fotogramas, 3,6 s) |
| Fotogramas del MP4 de GPU, sacados con el propio Blender | a 1,5 s la escena; a 4,6 s el emblema entrando; a 6,4 s el cierre completo (emblema, «MolDesign», «EVIDENCIA ESTRUCTURAL REPRODUCIBLE» y la dirección web) |

Qué no se midió con Blender real: `social_vertical` y `biblioteca` (los tres formatos pasan `cierre.verificar` en pruebas, pero sólo se renderizó la
vista previa) y la reanudación tras un fallo a mitad del cierre. El motivo del rechazo de un video sin cierre se ejercita con MP4 sintéticos
(`backend/tests/test_molcy_cierre_obligatorio.py`), no con uno real recortado.

### Dónde busca Blender la autodetección

Antes sólo miraba `%ProgramFiles%\Blender Foundation\Blender *`. En esta máquina esa carpeta no existe: Blender 5.2.2 se instaló con el MSI oficial
eligiendo la raíz del disco E (`InstallLocation = E:\`), y la aplicación decía «No se encontró Blender» con uno apto instalado. Ahora, sin ejecutar
nada y sin PowerShell (registro con `winreg`, 88 ms medidos):

| Pista | Qué lee | Verificado |
|---|---|---|
| Instalador oficial | `Uninstall\*` (nombre «Blender», editor «Blender Foundation», `InstallLocation`, `DisplayVersion`), `App Paths`, `Program Files` de cada disco fijo, instalación por usuario | **sí, con datos reales** (halló `E:\blender.exe` 5.2.2) |
| Archivos `.blend` | el programa asociado; si es `blender-launcher.exe` se toma el `blender.exe` de al lado | **sí, con datos reales** (`blender.5.2` → lanzador en `E:\`) |
| Raíz de un disco fijo, carpeta `Blender*`, ZIP en Descargas/Escritorio/Documentos | `blender.exe` y la carpeta de versión `X.Y` de al lado | **sí, con datos reales** |
| Steam | `SteamPath` del registro, `libraryfolders.vdf` (bibliotecas en otros discos), `appmanifest_365670.acf` | el analizador del `.vdf` con el archivo real de esta máquina (tres bibliotecas); **no hay un Blender de Steam instalado aquí**, el resto es con archivos de mentira |
| Microsoft Store | `Repository\Packages` del registro (la carpeta real del paquete, también en otra unidad) y el `Executable` de su `AppxManifest.xml` | `WindowsApps` no se puede listar (medido: `PermissionError`), pero el manifiesto de un paquete conocido sí se lee: el lector se probó con el manifiesto **real** del Bloc de notas de esta máquina. **No hay Blender de la Tienda aquí** |
| Scoop, Chocolatey, winget, `PATH` | rutas conocidas y las carpetas absolutas del `PATH` (sin la carpeta actual, que `shutil.which` mira primero) | sólo con archivos de mentira |

**Lo que NO está verificado:** que un `blender.exe` lanzado directamente desde `WindowsApps` (Tienda) o desde una biblioteca de Steam arranque y pase el
sondeo de Molcy; ni dónde guarda Molecular Nodes ese Blender. La autodetección sólo dice dónde está; quien decide si sirve es el sondeo (versión mínima
5.2, Molecular Nodes, Cycles y EEVEE).

La versión sale de la carpeta `X.Y` que Blender trae junto al ejecutable, del nombre del paquete de la Tienda o del registro; si no se sabe, se
muestra como desconocida y se puede elegir. Un Blender anterior a 5.2 se muestra pero no se puede elegir, y si es el único, el Blender de MolDesign
queda como opción predeterminada. Sólo se recorren discos fijos: un disco de red o una unidad óptica puede tardar segundos en contestar.
