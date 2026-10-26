# Cápsulas de QA

Una **cápsula** es un backend + un frontend + datos propios, con un puerto y una
carpeta por agente. Existe para que dos auditores (humanos o agentes) usen la
aplicación **a la vez, como usuarios**, sin pisarse los datos ni los puertos, y
sin tocar el perfil real de quien lanza.

No es la aplicación instalada. Este documento dice qué replica, qué no, y cómo
saberlo en cada sesión: el manifiesto de la cápsula lo repite.

## Uso

Desde el **worktree** del agente (no desde el árbol principal, ver «Límites»):

```bash
node scripts/qa_sandbox/sandbox-up.mjs --agente 2            # levanta; construye frontend/out si hace falta
node scripts/qa_sandbox/sandbox-up.mjs --agente 2 --estado   # qué está vivo, qué commit sirve
node scripts/qa_sandbox/sandbox-up.mjs --agente 2 --reset    # apaga y vuelve a «primer uso»
node scripts/qa_sandbox/sandbox-up.mjs --agente 2 --down     # apaga (--limpiar retira las junctions)
```

Abre **`http://localhost:<puerto frontend>`**, nunca `127.0.0.1`: el origen es lo
que lleva CORS y `localStorage`. `127.0.0.1` se redirige solo a `localhost`.

| Agente | Backend | Frontend | LLM (llama) | Carpeta |
|---:|---:|---:|---:|---|
| 1 | 18011 | 13011 | 18111 | `..\.sandbox\agente1\` |
| 2 | 18012 | 13012 | 18112 | `..\.sandbox\agente2\` |
| 9 | 18019 | 13019 | 18119 | (temporal; lo usa el autotest) |

Los puertos quedan fuera de 8000-8019 (el rango que Rust reserva para el backend
de la app instalada), de 3000/3001 y de los fijos de los sidecars. `..` es la
carpeta que contiene el worktree.

Opciones: `--rebuild`, `--no-build`, `--out DIR` (sirve un export ya hecho; el
manifiesto lo marca «externo»), `--capsula DIR`, `--vina-cpu N` (4 por defecto),
`--primer-plano`.

### Qué hay en la carpeta de la cápsula

| Carpeta | Contenido | `--reset` |
|---|---|---|
| `data/` | `LOCAL_DATA_DIR`: SQLite, poses, PDFs | la borra |
| `home/` | perfil de usuario redirigido (`USERPROFILE`, `APPDATA`, `LOCALAPPDATA`) | la borra |
| `casos/`, `registro-casos/` | carpetas de casos y su registro de autorizaciones (emulan app data de Rust) | las borra |
| `tmp/`, `install/` | temporales; raíz de instalación que ve Molcy | las borra |
| `logs/` | un log de backend, de frontend y de build **por arranque** | **no**: es evidencia |
| `manifest.json` | commit, árbol limpio, export, puertos, desviaciones | se reescribe al levantar |

`--reset` sólo borra carpetas que lleven la marca `.capsula-moldesign` y que no
sean ni contengan el repositorio, el runtime compartido ni el perfil real.

## Qué replica de la aplicación instalada

- **El entorno del backend** de `src-tauri/src/backend.rs`: `APP_MODE`,
  `ENVIRONMENT=production`, `PYTHONUTF8`, `VINA_EXECUTABLE_PATH`,
  `MOLDESIGN_OPENBABEL_DIR`, token de arranque, mismo `--app-dir`.
- **El frontend es el export estático** (`npm run build:desktop`), servido con la
  **CSP de producción**, no `next dev`. `next dev` no prueba la CSP (restricción 4
  del AGENTS.md) y la app real no lo usa.
- **Un solo build sirve para cualquier puerto**: el puerto lo da el shim, como lo
  da Rust. La puerta `check:exported-api-url` se ejecuta tras el build.
- **Usuario nuevo**: el perfil está redirigido, así que el backend crea su
  `secret_key` y sus almacenes como en un primer arranque real.
- **Aislamiento verificado**: el autotest fotografía `~\.moldesign`, `~\MolDesign`
  y `~\.cache\huggingface` antes y después y exige que no cambien.

## Qué NO replica (leer antes de dar nada por auditado)

1. **Tauri está simulado.** El shim de `window.__TAURI__` contesta
   `ensure_backend`, `backend_launch_token`, `backend_status`; el servidor emula:
   - los 13 comandos `case_*` de `cases.rs` (`casos.mjs`), con sus códigos de error
     y la lectura con recuperación desde `.case.json.bak`. **No** emula
     `ensure_within` contra symlinks, la escritura atómica con `sync_all` ni el
     Explorador de Windows (`case_reveal` no abre nada);
   - `get_resource_dir` (devuelve el árbol principal), `file_exists` y
     `verify_model`. Este último sólo comprueba **existencia**, no el SHA-256:
     hashear los 8,4 GB de ESMFold en cada carga de página distorsionaría lo que
     se audita.
   
   **No se emulan** `download_model`, `cancel_download` ni `extract_archive`: el
   servidor contesta 501 y el shim anota el comando en
   `window.__SANDBOX_NO_SIMULADO__` (y el servidor en `logs/no-emulados.log`).
   Cualquier cosa que dependa de ellos queda **sin auditar**.
2. **El selector nativo de carpetas** se sustituye por la carpeta fija `casos/`.
   Para probar «Abrir carpeta existente», «Reubicar» o «Inicializar», escribe la
   ruta en `siguiente-carpeta.txt` (dentro de la carpeta de la cápsula): se
   consume en el siguiente diálogo y vale para uno solo.
3. **El origen es `http://localhost:<puerto>`**, no `http://tauri.localhost`: el
   CORS de producción para el origen de Tauri no se ejerce.
4. **WebView2 no es Chrome.** El navegador de la prueba es otro motor de render.
5. **El backend corre desde el árbol**, con el `python-embed` del árbol principal
   y el `backend/` del worktree, no desde el runtime *staged* del instalador, y
   **con `python -B`**, para no escribir bytecode en el runtime compartido. El
   primer arranque desde fuentes puede tardar más que el bundle precompilado. Lo que se verifica aquí es el
   código, no el artefacto: antes de dar algo por entregable hace falta
   `npm run smoke:prod` (restricción 1 del AGENTS.md).
6. **El instalador, NSIS, la firma y una máquina limpia no se ejercitan.**

## Límites que conviene conocer

- **Sidecars con puerto fijo.** ESMFold (8100) y ESMFold-Pro (8300) no tienen
  override: sólo **una** cápsula a la vez puede usarlos. El backend sí respeta
  `LLAMA_SERVER_PORT`, que la cápsula fija por agente.
- **Recursos compartidos de sólo lectura.** El worktree no trae lo que git ignora.
  La cápsula usa `python-embed/`, `tools/vina`, `tools/openbabel` y los pesos del
  árbol principal (`MOLDESIGN_RUNTIME_ROOT` lo cambia), copia
  `data/molgraph_seed.db` y enlaza con *junctions* `frontend/node_modules` y
  `models/`. Todo lo que crea queda en `enlaces.json`. **Las descargas de modelos
  están vetadas**: caerían en el árbol principal a través de esas junctions.
- **Se retiran con `--down --limpiar`** (que usa `rmdir` no recursivo). Nunca con
  `rm -rf` sobre una junction.
- **`backend/.env` y `.env.desktop`.** Existen en el árbol principal y el backend
  los carga (`SECRET_KEY`, `SOLANA_PRIVATE_KEY`…); el instalador los excluye. En
  un worktree no existen. El lanzador avisa si los encuentra y lo anota en el
  manifiesto.
- **CPU.** Vina va limitado a 4 núcleos por cápsula. Con dos cápsulas docando a la
  vez los tiempos medidos no son los de una instalación.
- **El export se reconstruye** cuando cambia la huella (commit + cambios sin
  commitear + archivos nuevos de `frontend/`). Con `--no-build` o `--out` el
  manifiesto avisa si no corresponde al código actual.

## Pruebas

```bash
node --test scripts/qa_sandbox/sandbox.test.mjs   # 22 pruebas, sin red ni procesos
node scripts/qa_sandbox/autotest.mjs              # levanta una cápsula real (agente 9) y la ejerce
```

El autotest termina cada comprobación en **OK**, **FALLA** o **NO EJECUTADO**; lo
último no es verde y con `--estricto` cuenta como fallo. Incluye muestras que
deben fallar (origen ajeno, secreto erróneo, `..%2f`, `Sec-Fetch-Site:
cross-site`) y crea un caso **por la interfaz** para que el manifiesto emulado no
pueda desviarse en silencio de lo que acepta el frontend.

## Un candidato a defecto que la cápsula reproduce

`case_list_authorized` (`cases.rs`) llama a `read_manifest_with_recovery`, que
**restaura `case.json` en disco** y descarta el indicador de recuperación. Como
`listCases` llama a `case_read` después, la fila nunca llega con
`recoveredFromBackup`: un caso salvado del backup no se dice. No está verificado
contra el binario real; la cápsula lo reproduce porque emula el mismo orden
(prueba `casos: escribir deja copia…`). Si se corrige en Rust, hay que corregir
`casos.mjs` y esa prueba.
