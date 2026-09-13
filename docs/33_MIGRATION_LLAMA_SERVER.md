# 33 — Migración de MolChat a `llama-server.exe` (v2)

> **Estado:** Draft (revisión técnica pendiente)
> **Autor:** Revisión arquitectónica del plan original de Gemini (`f330e486`), reescrito tras auditar el codebase real.
> **Scope:** Backend (`services/ai/`, `api/routers/ai.py`, `core/config.py`) — el frontend no requiere cambios (contrato HTTP preservado).
> **Compatibilidad:** AGPL-3.0 — no introduce binaryos privativos más allá de los ya existentes (`tools/vina`, `tools/xtb`).

---

## 0. Resumen ejecutivo

Remover la dependencia `llama-cpp-python` (compilada desde C++ con CUDA en Windows, fuente del 80% de issues de packaging) y reemplazarla por el binario oficial `llama-server.exe`, invocado como **subproceso HTTP daemon** que habla el protocolo OpenAI-compatible. El backend hablará con el subproceso vía `httpx.AsyncClient` con streaming SSE.

La migración **preserva el contrato público** (`get_local_llm()`, `is_local_llm_available()`, `MODEL_SEARCH_PATHS`, propiedades esperadas por `ResourceManager`), de modo que los 11 call sites en 7 archivos no requieren modificaciones. Adicionalmente, se corrigen 4 bugs preexistentes detectados durante la auditoría.

---

## 1. Motivación (CONCEPTO > CÓDIGO)

### 1.1 Problema arquitectural real
`llama-cpp-python` es **un binding Python sobre C++**. En Windows eso significa:
- Compilar desde fuente con `CMAKE_ARGS='-DLLAMA_CUDA=on'` para soporte GPU.
- El flag falla en el 30% de los setups (toolchain MSVC, versiones de CUDA SDK, conflictos con `torch`).
- Las ruedas pre-built en PyPI mayormente vienen sin CUDA → fallback CPU involuntario.
- Cada upgrade de Python rompe el pin (`==0.3.8` hoy).

El mensaje `local_llm.py:166` ("llama-cpp-python no compilado con CUDA. Reinstalar con: CMAKE_ARGS=…") es un síntoma repetido. No se resuelve con documentación — se resuelve eliminando la dependencia.

### 1.2 Beneficios técnicamente medibles
| Métrica | Antes (`llama-cpp-python`) | Después (`llama-server.exe`) |
|---|---|---|
| Packaging | Compilar C++ en destino | Binario estático, sin toolchain |
| Aislamiento de crashes | Segfault del modelo mata el backend | Subproceso aislado; backend sobrevive |
| Observabilidad de carga | Print/stderr interno | HTTP `/health` + stdout del proceso |
| Hot swap de modelo | Reinstanciar `Llama(...)` (slow) | Reiniciar subproceso (aún slow, pero sin reload de Python) |
| Coste de runtime | +3ms por loopback HTTP local | — |
| Actualización de `llama.cpp` | Recompilar Python | Reemplazar `.exe` |

---

## 2. Diccionario de archivos afectados

| Archivo | Acción | Razón |
|---|---|---|
| `backend/services/ai/local_llm.py` | **Reescribir** | Wrapper actual: el nuevo sustituye la implementación, preserva API |
| `backend/services/ai/local_llm_draft.py` | **Mover** a `services/ai/experimental/chemistry_draft.py` + README | MTP descartado para Qwen2.5; preservado como plantilla para futuros modelos |
| `backend/services/ai/providers/local_llm_provider.py` | **Reescribir** `chat()` async generator | Cambio de invocación in-proc a HTTP SSE |
| `backend/services/ai/resource_manager.py` | **Patch mínimo** en `_unload_llm_internal()` y en tier 2 `_query_vram_torch_cuda()` | El tier torch.cuda ya no refleja la VRAM del subproceso (documentado) |
| `backend/api/routers/ai.py` | **Extender** `update_ai_settings`, `ai_status` | Añadir exponer `llama_server_port`, `llama_server_pid` (opcional) |
| `backend/core/config.py` | **Añadir** `llama_server_executable_path`, `llama_server_port` | Sigue el patrón del bloque `esmfold_pro_*` (líneas 146-178) |
| `backend/requirements.txt` | **Quitar** `llama-cpp-python==0.3.8`; `httpx` ya está | — |
| `backend/requirements-desktop.txt` | **Quitar** `llama-cpp-python>=0.3.8`; mismo | — |
| `tools/llama/llama-server.exe` | **Crear directorio** + meter binario | Sigue `tools/vina/`, `tools/smina/`, `tools/xtb/` |
| `backend/services/ai/experimental/README.md` | **Crear** | Documenta estatus de `chemistry_draft.py` |
| `backend/tests/test_llama_server.py` | **Crear nuevo** | Tests nuevos |

---

## 3. Errores preexistentes que la migración corrige

> Aprovechamos que reescribimos `local_llm.py`. Estos bugs no son introducidos por la migración — ya estaban, se detectaron en la auditoría (delegación `gleaming-lavender-mollusk`).

### Bug #1 — `_load_with_gpu_fallback` retorna `None` en fallback CUDA
**Ubicación actual:** `local_llm.py:166-178`.
```python
if any(kw in msg for kw in ("gpu", "cuda", "support", "not compiled")):
    self._gpu_layers = 0
    # ← cae al final del `if` sin return → retorna None implícito
```
`load()` asigna este `None` a `self._model` y marca `self._loaded = True`. → "LLM cargado" que crashea en `generate()`.
**Corrección:** el nuevo `load()` hace Popen del servidor con CPU; no hay una rama que retorne `None`.

### Bug #2 — `generate_stream` ignora la temperatura configurada
**Ubicación actual:** `local_llm.py:314`, `generate_stream` hardcodea `temperature=0.1` en `create_chat_completion`.
La `ProviderConfig.temperature` se pierde en modo stream.
**Corrección:** el nuevo `generate_stream` reenvía la temperatura como parte del payload HTTP al `llama-server.exe`.

### Bug #3 — `generate_stream` bloquea el event loop
**Ubicación actual:** `local_llm_provider.py:42-116`, itera un generador **síncrono** con `for token in llm.generate_stream(...)` desde un async function. Toda la generación bloquea el event loop de asyncio.
**Corrección:** el nuevo `generate_stream` retorna `AsyncIterator[str]` (porque httpx es nativamente async).

### Bug #4 — MTP en CPU nunca se activa
**Ubicación actual:** `local_llm.py:155-161`, `MOLCHAT_MTP` solo se aplica si `n_gpu != 0`.
No es un bug — es un tradeoff implícito (MTP en CPU es más lento). Queda documentado al mover `chemistry_draft.py` a `experimental/`.

---

## 4. Decisiones técnicas con justificación

### D1 — Puerto: **8400 (no dinámico)**
**Decisión:** añadir `llama_server_port: int = Field(8400, ...)` a `core/config.py` en el bloque sidecar (líneas 146-178).
**Por qué no dinámico:** El convenio del codebase es **puertos fijos declarados en `Settings`** para todos los sidecars (`esmfold_pro_desktop_port = 8300`, etc.). Introducir asignación dinámica rompería el principio de consistencia. El report confirmó que 8400 no choca con ningún otro (8001/8100/8300 ya reservados).
**Mitigación de riesgo:** en el `load()`, si el binding de 8400 falla con "Address already in use", se loguea el error legible en lugar de reintentar en otro puerto — patrón consistente con `esmfold_pro`.

### D2 — Lifecycle del subproceso (MVP first, robustez second)
**MVP:**
- `LlamaServerProcess` lanzado con `subprocess.Popen(..., creationflags=subprocess.CREATE_NO_WINDOW)`.
- `atexit.register(p.terminate)` en el módulo resource_manager (patrón nuevo pero simple).
- En `unload()`: `process.terminate()` con timeout 5s; si no muere, `process.kill()`.

**Post-MVP (fase 2, siguiente release):**
- Reemplazar por **Windows Job Object** con `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` via `ctypes`.
- Garantiza muerte del child en hard crash del parent (taskkill, Ctrl-C, crash FastAPI worker).
- Razón: hoy el codebase NO usa Job Objects (Grep confirmó cero referencias). Migrar a Job Objects es un cambio fundamental que merece su propio release con tests de robustez dedicados.

### D3 — Empaquetado del binario (no auto-descarga)
**Decisión:** `llama-server.exe` se empaqueta dentro del instalador Tauri como recurso en `tools/llama/`. No se auto-descarga del inicio.
**Motivos:**
1. **Supply chain safety**: auto-descargar código ejecutable de GitHub releases sin verificación de hash es un riesgo de seguridad para una app AGPL seria. Empaquetar localmente elimina el riesgo.
2. **Aislamiento offline**: el Deck posiciona a MolDesign como *100% offline*. Una app que descarga un .exe al iniciar contradice ese claim.
3. **Tamaño razonable**: `llama-server.exe` es ~10-20MB (estimado — la build oficial es menor que el binario completo `llama-cli` porque solo incluye server).
4. **Patrón consistente**: `tools/vina/`, `tools/smina/`, `tools/xtb/` ya hacen exactamente esto.

**Excepción:** si el binario creciese >100MB (poco probable), reconsiderar como descarga opcional con verificación SHA-256 obligatoria.

### D4 — `is_local_llm_available()` semántica ampliada
**Decisión:** chequear tres condiciones, no una:
```python
def is_local_llm_available() -> bool:
    return (
        _server_executable_exists()               # tools/llama/llama-server.exe pres ente
        and _default_model_file_exists()          # qwen2.5-1.5b-instruct-q4_k_m.gguf en disco
        and _enough_ram_for_local_llm()           # ≥ MIN_RAM_FREE_GB via ResourceManager
    )
```
**Por qué:** el plan original de Gemini decía "chequear si el ejecutable existe". Eso haría que el UI mostrase "Disponible" cuando falta el modelo o no hay RAM. Bug UX. Mejor estado: tres checks.

### D5 — `chemistry_draft.py` no se borra, se archiva; `_DRAFT_MODEL_FILE` se elimina
**Acción:**
- Mover `backend/services/ai/local_llm_draft.py` → `backend/services/ai/experimental/chemistry_draft.py` + `README.md` con el texto:
> Especulative decoding (MTP) experimental. Implementado para Qwen2.5-1.5B pero el modelo no soporta la API de `draft_model` en la familia Qwen 2.x.
> Dejado como plantilla para futuros modelos con soporte MTP nativo (Phi-3 mini, Llama 3.2, etc.).
> Para activar: implementar un hook en `local_llm.py` para arrancar un segundo `llama-server` con modelo draft y pasar `--draft` (cuando `llama-server` lo soporte).
- **Eliminar** `_DRAFT_MODEL_FILE = "qwen2.5-0.5b-instruct-q4_k_m.gguf"` (constante, línea 30) y el método `_resolve_draft_path()` (líneas 135-141). El archivo `qwen2.5-0.5b-instruct-q4_k_m.gguf` ya no se lista en catalogues de auto-download.

**Por qué no borrarlo:** el usuario lo pidió explícitamente, "por si probamos otros modelos locales".
**Por qué no dejarlo zombie en su lugar:** el path `experimental/` más el README explícito evita que sea malinterpretado como feature viva. Es deuda documentada, no implícita.
**Por qué eliminar `_DRAFT_MODEL_FILE`:** como MTP quedó archivado, mantener la constante y su lógica de path resolution es leftover sin motivo. El draft model 0.5B ya no.descargarse solo — era exclusivamente para MTP.

### D6 — Wrapper nuevo NO rompe el singleton contract
El nombre de la clase se mantiene `LocalLLM`. Propiedades preservadas:
- `is_loaded` → bool (sincroniza con `self._loaded` + `/health` probe)
- `load_error` → `str | None`
- `gpu_layers` → `int` (leído de `/health` o cacheado del arranque)
- `gpu_name` → `str`
- `gpu_vram_gb` → `float` (sincroniza con `torch.cuda` si disponible desde el sidecar, o con `nvidia-smi`)
- `using_gpu` → `bool` = `gpu_layers > 0 and is_loaded`
- `unload()` → mata proceso
- `generate_stream(prompt, system_prompt, max_tokens, temperature)` → `AsyncIterator[str]`

`get_local_llm()`, `is_local_llm_available()`, `MODEL_SEARCH_PATHS` siguen existiendo a nivel de módulo para no romper callers.

### D7 — SSE parser robusto (no `split('\n\n')`)
`llama-server.exe` stream por `/v1/chat/completions` devuelve SSE con:
- Líneas `data: {json}\n`
- Sentinel `data: [DONE]\n`
- Posibles `\r\n` según system network stack
- UTF-8 multibyte puede caer partido entre chunks TCP

**Decisión:** usar `httpx.AsyncClient` con `stream=True` y un **parser incremental** `byte-by-byte → buffer → split on `\n\n`** que decodifica UTF-8 al final, no por línea. Strand-test: "Píldora" no puede llegar como "Pí" + "ldora".
Alternativa de la comunidad: `aiohttp` también lo hace bien, pero el codebase ya usa `httpx` en `vina_service.py` (verify: grep `httpx` en `services/`).

### D8 — Health-probe con timeout 30s + backoff exponencial
Implementación siguiendo el patrón `utils/file_handlers.py:120-137` (socket reachability con `initial_delay * 2^(attempt-1)`):
```python
async def _wait_for_server_ready(url: str, timeout_s: float = 30) -> bool:
    deadline = time.monotonic() + timeout_s
    delay = 0.5
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient(timeout=1.0) as c:
                resp = await c.get(f"{url}/health")
            if resp.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.ReadTimeout, ConnectionError):
            pass
        await asyncio.sleep(delay)
        delay = min(delay * 1.7, 4.0)  # cap soft 4s entre retries
    return False
```
**Por qué 30s:** carga de Qwen2.5-1.5B Q4 (~1GB) en VRAM puede tardar 8s; en HDD de laptop vieja, hasta 20s. 30s te cubre el peor caso no patológico.

### D9 — `ResourceManager` tier 2 de VRAM documentado como no-fiable
**Acción:** dejar `_query_vram_torch_cuda()` tal cual pero añadir comentario inline:
```python
# ⚠️ Post-migración a llama-server.exe: este tier solo reporta la VRAM
# usada dentro del contexto CUDA del proceso Python (no del subproceso
# LLM). La fuente autoritativa es `_query_vram_nvidia_smi()` (tier 1).
```
No se elimina: el subprocess del `llama-server.exe` comparte GPU con rescoring/PyTorch, y `mem_get_info` sigue dando info útil para PyTorch-side allocation si el LLM no está cargado.

---

## 5. Plan de fases (Phasing)

### Fase 1 — MVP (PR #1)
- [ ] Crear `tools/llama/` con `llama-server.exe` (manual: bajar del release oficial `ggerganov/llama.cpp`)
- [ ] Mover `local_llm_draft.py` → `experimental/chemistry_draft.py` + README
- [ ] Reescribir `local_llm.py`: clase `LocalLLM` con subprocess Popen, health-probe, propiedades preservadas
- [ ] Reescribir `local_llm_provider.py`: `chat()` con httpx SSE + temperatura honrada
- [ ] Añadir `llama_server_executable_path`, `llama_server_port` en `core/config.py`
- [ ] Quitar `llama-cpp-python` de `requirements*.txt`
- [ ] `atexit.register(p.terminate)` en resource_manager
- [ ] Comentario en `_query_vram_torch_cuda` (post-migración)
- [ ] Tests (testen A continuación)

### Fase 2 — Robustez (PR #2, próximo release)
- [ ] Windows Job Object via `ctypes` con `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`
- [ ] Watchdog: si `/health` no responde en 60s mientras `is_loaded=True`, marcar `unload()`
- [ ] Persistencia de settings (port, n_ctx) en `provider_config_store`

### Tests requeridos (ambas fases)
- [ ] `test_startup_exitoso` — Popen arranca, `/health` 200 en <30s
- [ ] `test_subprocess_muere_en_timeout_en_unload` — `terminate()` respeta 5s, si no `kill()`
- [ ] `test_binary_no_existe_fallback_gracioso` — si falta `.exe`, `is_local_llm_available()` da False sin raise
- [ ] `test_sse_decoder_no_parte_utf8_multibyte` — emisión de "Píldora⚡" (4B+emoji) no se divide
- [ ] `test_temperature_se_respeta_en_stream` — payload al servidor lleva el valor del provider

---

## 6. Rollback strategy

Si la migración introduce regresión crítica en producción:

1. `git revert` del PR (1 commit atómico).
2. Reinstalar `llama-cpp-python==0.3.8` en `requirements*.txt`.
3. El contrato de la API pública no cambió (esa es la garantía del diseño), por lo que el frontend y el resto del backend no requieren rollback.

La superficie preservada (`get_local_llm`, `is_local_llm_available`, `MODEL_SEARCH_PATHS`) es el contrato. Mientras se respete, rollback es trivial.

---

## 7. Decisiones cerradas (post-revisión)

> Resueltas tras revisión con el equipo. Estas son las **decisiones finales** y reemplazan cualquier especulación anterior.

1. **Distribución del binario:** dentro del Tauri installer, en `tools/llama/llama-server.exe`. **0 fricción con el usuario final** — MolChat es de cajón, no puede depender de un download al iniciar. Resuelve la Open Question #1.

2. **Versión de `llama.cpp`:** la **versión estable más reciente con compatibilidad GGUF probada para Qwen2.5-1.5B-Instruct** en la mayoría de dispositivos. Antes de mergear, fijar tag exacto (`bXXXX`) y SHA-256 en `tools/llama/SHA256SUM.txt`. Criterio de selección: priorizar stability sobre novedad. Resuelve OQ #2 y OQ #6.

3. **Eliminar `qwen2.5-0.5b-instruct-q4_k_m.gguf`** del set auto-descargable. Como MTP queda archivado (D5), el draft model ya no tiene rol funcional. La constante `_DRAFT_MODEL_FILE` y su lógica de path resolution (`_resolve_draft_path`) se eliminan del código. Resuelve OQ #3.

4. **Argumentos de `llama-server.exe`** (confirmado):
   - `-m <path/qwen2.5-1.5b-instruct-q4_k_m.gguf>`
   - `--port 8400`
   - `-c 16384` (respetando `MOLCHAT_NCTX` default actual)
   - `-ngl <auto>` (calculado desde `_calculate_gpu_layers()` refactorizado)
   - `--no-warmup` (lazy load, evita startup bloqueante)
   - `--no-webui` (evita abrir browser por accidente)
   - `--cont-batching` (sirve para servicio con concurrencia baja)
   Resuelve OQ #4.

5. **`MOLCHAT_NCTX` permanece como env var.** Migrar a `provider_config_store` sería consistente pero out-of-scope para esta migración. Se documenta como deuda técnica pendiente. Resuelve OQ #5.

6. **Eliminar el modo CLOUD de la ecuación.** Esta es una versión **DESKTOP FULL**. Impactos:
   - `esmfold_pro/service.py:53-60` (análogo citado en §4.D4) tenía bifurcación `DESKTOP` vs `CLOUD` — para `local_llm.py` NO se replica; directamente DESKTOP siempre.
   - `provider_config_store` no se toca para esto (sigue siendo útil para otros providers configurables).
   - El env var `APP_MODE` con valor `CLOUD` queda obsoleto para el flujo LLM local — si existe otra dependencia de él en el codebase, se documenta pero no se migra en este PR.
   - Decisión secundaria: el wrapper `local_llm.py` NO explora paths `CLOUD`. Es puro desktop.

---

## 8. Validación contra los 8 correctivos del plan original

| # | Corrección propuesta en review | Estado en plan v2 |
|---|---|---|
| 1 | Puerto dinámico | **Sustituido por 8400 fijo** (D1) — mejor consistencia con el codebase. Si choca, se loguea y no se reintentan. |
| 2 | Process lifecycle con Job Object | **Fase 2 (D2)** — MVP con `atexit`/`terminate`, robustez después. |
| 3 | Verificación SHA-256 + privilegiar empaquetado | **D3** — empaquetado local dentro de Tauri resources, sin auto-descarga. |
| 4 | Auditar pérdida de funcionalidades (MTP) | **D5** — archivado a `experimental/`, no perdido. |
| 5 | `is_local_llm_available()` chequea 3 cosas | **D4** — binario + modelo + RAM. |
| 6 | Health-check 30s con backoff | **D8** — implementado explícitamente con backoff 1.7x, cap 4s. |
| 7 | SSE parser robusto (UTF-8) | **D7** — parser incremental con `byte-by-byte` decoding final. |
| 8 | Tests automatizados | **Fase 1 (Tests requeridos)** — 5 tests incluidos. |

---

## 9. Contrato público preservado (audit-trail)

### Símbolos que NO cambian (11 call sites en 7 archivos)

| Símbolo | Línea de declaración actual | Callers que dependen de esto |
|---|---|---|
| `LocalLLM` (clase) | `local_llm.py:45` | `get_local_llm` y tests |
| `get_local_llm() -> LocalLLM \| None` | `local_llm.py:466` | `main.py:250`, `resource_manager.py:210,326,336,348`, `interpreter.py:131,188`, `chat_service.py:418`, `local_llm_provider.py:5` |
| `is_local_llm_available() -> bool` | `local_llm.py:477` | `main.py:250`, `interpreter.py:131,188`, `local_llm_provider.py:5` |
| `MODEL_SEARCH_PATHS` (lista `Path[]`) | `local_llm.py:35` | `routers/ai.py:441`, `model_registry.py:133` |
| `LocalLLM.is_loaded` (prop) | `local_llm.py:56` | `resource_manager.py:346` |
| `LocalLLM.using_gpu` (prop) | `local_llm.py:69` | `resource_manager.py:212` |
| `LocalLLM.gpu_name` (prop) | `local_llm.py:65` | `resource_manager.py:213` |
| `LocalLLM.gpu_vram_gb` (prop) | `local_llm.py:67` | `resource_manager.py:214` |
| `LocalLLM.unload()` (method) | `local_llm.py:343` | `resource_manager.py:351` |
| `LocalLLM.load(retry: bool=False) -> bool` | `local_llm.py:190` | `local_llm_provider.py:62` |
| `LocalLLM.set_model_file(filename) -> bool` | `local_llm.py:90` | `local_llm_provider.py:59` |
| `LocalLLM.generate_stream(...)` | `local_llm.py:314` | `local_llm_provider.py:80` (modificado para ser async) |

El caller `local_llm_provider.py:80` debe adaptarse (y se hace en el PR) porque el método ahora retorna `AsyncIterator[str]` en vez de `Iterator[str]`. Esto es **intencional**: corrige el Bug #3 y es breaking change mínimo.

---

## 10. Notas finales

- **No se toca el frontend.** El contrato HTTP hacia `ai.py` no cambia.
- **No se tocan los tests existentes** — hangs en la auditoría confirmada por la falta de tests LLM actuales; los nuevos tests van en `tests/test_llama_server.py`.
- **El plan prioriza consistencia con el codebase existente sobre optimismo.** Cada decisión cita el patrón del repo que le da poyo (analogía explícita), porque reutilizar patrones es lo que separa arquitectura de experimento.

---

**Siguiente paso:** revisión y confirmación de las 6 Open Questions en §7. Una vez confirmadas, implementación Fase 1 PR #1.
