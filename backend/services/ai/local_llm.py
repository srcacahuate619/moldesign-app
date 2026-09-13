"""
services/ai/local_llm.py

Wrapper del motor LLM local de MolChat.

Migración v1.x — `llama-server.exe` subprocess (ver docs/33_MIGRATION_LLAMA_SERVER.md).

Anteriormente este módulo instanciaba `Llama(...)` de la librería
`llama-cpp-python` (binding Python sobre C++), que compilaba desde fuente
con CUDA en Windows y generaba el 80% de los issues de packaging de MolChat.

Ahora levanta el binario oficial `llama-server.exe` (release estable de
ggerganov/llama.cpp) como SUBPROCESO HTTP en puerto 8400, y habla con él
mediante `httpx.AsyncClient` usando protocolo OpenAI-compatible.

Superficie pública preservada (para no romper 11 callers en 7 archivos):

  - `get_local_llm() -> LocalLLM | None`
  - `is_local_llm_available() -> bool`
  - `MODEL_SEARCH_PATHS`
  - `LocalLLM.is_loaded` / `load_error` / `gpu_layers` / `gpu_name` /
    `gpu_vram_gb` / `using_gpu` / `max_context` / `unload()` / `set_model_file()`
  - `LocalLLM.load(retry: bool = False) -> bool`
  - `LocalLLM.generate_stream(...)` → `AsyncIterator[str]` (corregido del `Iterator[str]` bloqueante previo)

Errores históricos corregidos al reescribir (ver docs §3):
  - Bug #1: _load_with_gpu_fallback ahora nunca retorna None implícito.
  - Bug #2: generate_stream honra la temperatura del caller.
  - Bug #3: generate_stream es async y no bloquea el event loop.
  - D5: eliminado _DRAFT_MODEL_FILE y _resolve_draft_path (MTP archivado a experimental/chemistry_draft.py).
"""

from __future__ import annotations

import asyncio
import atexit
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import AsyncIterator, Optional

import httpx
from structlog import get_logger

from core.config import get_settings
from core.hardware import detect_hardware
from utils.procesos import BANDERAS_SIN_VENTANA

log = get_logger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────
#: Tope de espera ENTRE trozos del stream local. No es el tope de la respuesta
#: entera —eso lo cubre el timeout total de 300 s—: es lo que separa «el modelo
#: esta pensando» de «el motor dejo de hablar». Con 90 s, una GPU lenta cargando
#: contexto sigue dentro, y un servidor mudo no cuelga el turno para siempre.
STREAM_READ_TIMEOUT_S = 90.0

_DEFAULT_MODEL_REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
_DEFAULT_MODEL_FILE = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
_MODEL_TOTAL_LAYERS = 28
_GPU_KV_BUFFER_GB = 0.5

MODEL_SEARCH_PATHS = [
    Path(__file__).parent.parent.parent.parent / "models" / "llm",
    Path.home() / "MolDesign" / "models" / "llm",
    Path("models/llm"),
]

# Modo determinista heredado del backend (vina_seed=42 es la convención MolDesign).
_DEFAULT_N_CTX = int(os.environ.get("MOLCHAT_NCTX", "16384"))

# Tiempos y puertos (ver docs §4.D8)
_HEALTH_PROBE_TIMEOUT_S = 30.0
_HEALTH_PROBE_INITIAL_DELAY_S = 0.5
_HEALTH_PROBE_BACKOFF_FACTOR = 1.7
_HEALTH_PROBE_MAX_DELAY_S = 4.0

_PROCESS_TERMINATE_WAIT_S = 5.0


# ── Singleton thread-safe (mismo patrón que antes) ──────────────────────
_local_llm: Optional["LocalLLM"] = None
_lock = threading.Lock()


class LocalLLM:
    """
    Wrapper del subproceso `llama-server.exe` que respeta el contrato público
    esperado por `resource_manager.py`, `local_llm_provider.py`, etc.

    El modelo se carga bajo demanda (lazy load) — la instancia existe desde el
    arranque, pero `llama-server.exe` solo se lanza al primer `load()`.
    """

    def __init__(self, model_path: str | Path | None = None):
        self._model_path: Optional[str] = str(model_path) if model_path else None
        self._loaded: bool = False
        self._load_error: Optional[str] = None

        # Estado del subproceso (todos bajo self._lock).
        self._process: Optional[subprocess.Popen] = None
        self._port: Optional[int] = None
        self._gpu_layers: int = 0
        self._gpu_name: str = ""
        self._gpu_vram_gb: float = 0.0
        self._n_ctx: int = _DEFAULT_N_CTX

        # Drenaje de stdout del subproceso (ver _start_stdout_drain).
        self._stdout_file = None
        self._drain_thread: Optional[threading.Thread] = None

        # Cleanup robusto en salida limpia del proceso Python (Fase 1 MVP).
        # Fase 2 (próximo release): Windows Job Object via ctypes para cubrir
        # hard crashes (taskkill / Ctrl-C / segfault del backend). Ver docs §4.D2.
        atexit.register(self._cleanup_on_exit)

    # ── Propiedades (CONTRATO PÚBLICO — no cambiar firma) ─────────────────

    @property
    def is_loaded(self) -> bool:
        return (
            self._loaded
            and self._process is not None
            and self._process.poll() is None
        )

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    @property
    def gpu_layers(self) -> int:
        return self._gpu_layers

    @property
    def gpu_name(self) -> str:
        return self._gpu_name

    @property
    def gpu_vram_gb(self) -> float:
        return self._gpu_vram_gb

    @property
    def using_gpu(self) -> bool:
        return self._gpu_layers > 0 and self.is_loaded

    @property
    def max_context(self) -> int:
        """Contexto máximo del modelo cargado (n_ctx). 0 si no está cargado."""
        return self._n_ctx if self.is_loaded else 0

    # ── API pública ──────────────────────────────────────────────────────

    def clear_error(self) -> None:
        self._load_error = None

    def set_model_file(self, filename: str) -> bool:
        """Cambiar el modelo a usar en el próximo `load()`.

        Si el LLM ya está cargado con un modelo distinto, lo descarga primero
        para que el siguiente `load()` arranque el subproceso con el nuevo.
        """
        try:
            path = self._resolve_model_path(filename)
        except FileNotFoundError:
            self._load_error = f"Modelo no encontrado: {filename}"
            return False
        new_path = str(path)
        changed = new_path != self._model_path
        self._model_path = new_path
        # Solo descargar si el modelo CAMBIO — si es el mismo, no matar el server.
        # (Antes descargaba siempre que estuviera cargado, lo que rompía el flujo
        # tool-calling: el provider llama set_model_file() en cada chat, el server
        # moría después de ejecutar la tool, y el siguiente load() explotaba con
        # 'asyncio.run() cannot be called from a running event loop'.)
        if changed and self.is_loaded:
            self.unload()
        return True

    def load(self, retry: bool = False) -> bool:
        """Lanzar el subproceso `llama-server.exe` y esperar a que `/health` responda.

        Retorna True si el servidor está vivo y respondiendo; False si falló
        (con `self._load_error` descriptivo). Es seguro llamarla de nuevo.
        Idempotente: si ya está cargado, no relanza.
        """
        if self.is_loaded:
            return True

        self.clear_error()

        # WARMUP del ResourceManager: decide si hay RAM/VRAM para cargar.
        # Esta es la única razón por la que `load` sigue siendo síncrono — el
        # ResourceManager._ensure_idle_checker crea tareas async lazily llamado
        # desde aquí, y no desde el event loop externo. Respeta el contrato.
        try:
            from services.ai.resource_manager import get_resource_manager
            rm = get_resource_manager()
            can, reason = rm.can_load()
            if not can and not retry:
                self._load_error = reason or "ResourceManager no autoriza la carga"
                return False
        except ImportError:
            pass

        # Resolver binario + modelo
        try:
            server_bin = self._resolve_server_executable()
            model_path = self._resolve_model_path()
        except FileNotFoundError as e:
            self._load_error = str(e)
            return False

        # Determinar parámetros
        try:
            self._detect_gpu()
        except Exception as e:
            log.warning("local_llm_gpu_detect_failed", error=str(e)[:100])

        # Seleccionar puerto (Fase 1: fijo de config.py; sin retry con otros puertos)
        port = get_settings().llama_server_port
        args = self._build_server_args(server_bin, model_path, port)

        # Popen con CREATE_NO_WINDOW (patrón de resource_manager:32).
        # cwd=server_bin.parent es CRÍTICO: Windows resuelve las DLLs
        # (llama.dll, ggml.dll, etc.) desde el directorio del ejecutable,
        # NO automáticamente desde PATH. Sin esto → 0xC0000135 al arrancar.
        try:
            # Los argumentos van EN la llamada, no en un dict que se desempaqueta.
            # `test_subprocesos_sin_ventana.py` comprueba por AST que todo
            # lanzamiento declara `creationflags`; a través de un `**kwargs` esa
            # comprobación no puede ver nada, y un descuido futuro pasaría.
            self._process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(server_bin.parent),
                creationflags=BANDERAS_SIN_VENTANA,
            )
            self._port = port
            log.info(
                "llama_server_started",
                pid=self._process.pid,
                port=port,
                ngl=self._gpu_layers,
                n_ctx=self._n_ctx,
            )
            # Drenaje de stdout ANTES del health probe: el server escribe el
            # progreso de carga de pesos durante el arranque (miles de líneas
            # con n_ctx=16384). Sin drenaje, el pipe de 64KB se llena y el
            # server se bloquea — sintoma observado: "muerte silenciosa" tras
            # R003 en el run de regresión (sin log de unload, poll() vivo).
            self._start_stdout_drain()
        except FileNotFoundError:
            # El binario se movió o se corrompió entre el _resolve y el Popen
            self._load_error = (
                f"llama-server.exe no se pudo lanzar. ¿Está en tools/llama/? "
                f"Ruta: {server_bin}"
            )
            return False
        except Exception as e:
            self._load_error = f"Fallo al iniciar llama-server.exe: {e}"
            self._port = None
            return False

        # Esperar que /health responda (backoff exponencial, 30s timeout).
        # IMPORTANTE: usamos la version _SYNC del health probe porque load() es
        # llamado desde contextos async (el provider en prod invoca load dentro
        # del event loop de FastAPI). Antes esto hacia asyncio.run() que crashea
        # con 'cannot be called from a running event loop'. El polling sync con
        # time.sleep es seguro y no compite con el event loop externo.
        ready = self._wait_for_server_ready_sync()
        if not ready:
            self._load_error = (
                "llama-server.exe no respondió en /health dentro del timeout "
                f"({_HEALTH_PROBE_TIMEOUT_S:.0f}s). Posible problema de VRAM, "
                "permisos, o binario incompatible con el modelo."
            )
            # Capturar stderr del subproceso para diagnóstico y limpieza.
            self._drain_stderr_for_diagnostic()
            self._kill_and_reset()
            return False

        self._loaded = True
        self._load_error = None
        log.info(
            "local_llm_loaded",
            model=self._model_path,
            port=port,
            gpu=self._gpu_name or "CPU",
            gpu_layers=self._gpu_layers,
        )
        return True

    def unload(self) -> None:
        """Detener `llama-server.exe` y liberar VRAM/RAM."""
        self._kill_and_reset()
        log.info("local_llm_unloaded")

    # ── Inferencia: path síncrono (no-stream) ────────────────────────────

    def generate(
        self,
        messages: list[dict],
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> str:
        """Generar respuesta completa (sin stream). Útil para tests.

        Args:
            messages: lista OpenAI-style [{"role": "system"|"user"|"assistant", "content": "..."}].
                      Multi-turno nativo — se pasa directo a /v1/chat/completions.
        """
        if not self.is_loaded:
            return ""

        try:
            with httpx.Client(timeout=httpx.Timeout(300.0, connect=2.0)) as client:
                resp = client.post(
                    f"{self._http_url}/v1/chat/completions",
                    json={
                        "model": self._model_file_basename(),
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""
        except Exception as e:
            log.error("local_llm_generate_failed", error=str(e)[:200])
            return ""

    def generate_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> dict:
        """Llamar al LLM con herramientas nativas (OpenAI function calling).

        Devuelve {"content": str, "tool_calls": [{"name": str, "arguments": dict}]}.
        Si el modelo no llama herramientas: content tiene texto, tool_calls vacio.
        Si el modelo llama herramientas: content es "", tool_calls tiene las llamadas.

        Necesita --jinja en el arranque del server para template Hermes 2 Pro.
        """
        if not self.is_loaded:
            return {"content": "", "tool_calls": [], "error": "not_loaded"}

        import json as _json

        try:
            with httpx.Client(timeout=httpx.Timeout(300.0, connect=2.0)) as client:
                resp = client.post(
                    f"{self._http_url}/v1/chat/completions",
                    json={
                        "model": self._model_file_basename(),
                        "messages": messages,
                        "tools": tools,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "stream": False,
                    },
                )
                if resp.status_code != 200:
                    body = resp.text[:500]
                    log.error("llama_server_tool_error", status=resp.status_code, body=body)
                    resp.raise_for_status()
                data = resp.json()
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                content = message.get("content", "") or ""

                # Parsear tool_calls del formato OpenAI
                raw_tool_calls = message.get("tool_calls", [])
                tool_calls = []
                for tc in raw_tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    args_str = fn.get("arguments", "{}")
                    try:
                        args = _json.loads(args_str)
                    except _json.JSONDecodeError:
                        args = {"_raw": args_str}
                    tool_calls.append({"name": name, "arguments": args})

                return {"content": content, "tool_calls": tool_calls}
        except Exception as e:
            log.error("local_llm_tool_call_failed", error=str(e)[:200])
            return {"content": "", "tool_calls": [], "error": str(e)}

    # ── Inferencia: path streaming (corrige bugs #2 y #3) ─────────────────

    async def generate_stream(
        self,
        messages: list[dict],
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        """Yield tokens conforme el servidor los envía por SSE.

        Cambios vs versión `llama-cpp-python`:
          - AsyncIterator[str] (no más Iterator[str]) — corre sin bloquear el
            event loop de asyncio. Corrige bug #3 del plan.
          - Honra la `temperature` del caller. Corrige bug #2 (antes hardcodeada a 0.1).
          - SSE parser robusto: decodifica UTF-8 SOLO después de acumular un
            frame completo `data: ...\\n\\n`, evita trocear caracteres multibyte.
            Ver docs §4.D7.
          - **Multi-turno nativo**: recibe `messages` OpenAI-style, lo pasa directo
            al endpoint `/v1/chat/completions`. Elimina el aplanamiento de turnos
            que hacía el provider viejo (corrige bug #4: historial >> 1 turno
            aplanado rompía el multi-turno del chat).
        """
        if not self.is_loaded:
            yield ""
            return

        url = f"{self._http_url}/v1/chat/completions"
        payload = {
            "model": self._model_file_basename(),
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        buffer = b""
        try:
            # MOLCHAT-AUD-01 (higiene del §8): la lectura del stream no tenia
            # tope —esperaba indefinidamente entre trozos—. Un motor local que acepta la
            # conexion y deja de emitir colgaba el turno para siempre, y un tope
            # por peticion no es un tope si una de ellas puede no terminar nunca.
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    300.0, connect=2.0, read=STREAM_READ_TIMEOUT_S
                )
            ) as client:
                async with client.stream("POST", url, json=payload) as resp:
                    resp.raise_for_status()
                    async for raw_chunk in resp.aiter_bytes():
                        buffer += raw_chunk
                        # Ì Procesar frames completos (separados por \n\n)
                        while b"\n\n" in buffer:
                            frame, buffer = buffer.split(b"\n\n", 1)
                            # Cada frame contiene líneas `data: <json>` o `: \n\n` keepalives.
                            for line in frame.split(b"\n"):
                                # Bajar al siguiente line si no es una línea de datos
                                if not line.startswith(b"data:"):
                                    continue
                                data_part = line[len(b"data:"):].strip()
                                # Sentinel final
                                if data_part == b"[DONE]":
                                    return
                                try:
                                    # DECODIFICACIÓN AQUÍ (no antes): evita splitting UTF-8 multibyte
                                    text = data_part.decode("utf-8")
                                except UnicodeDecodeError:
                                    # Frame partido justo en medio de un char multibyte —
                                    # conservamos en el buffer y esperamos el siguiente chunk.
                                    buffer = line + b"\n\n" + buffer
                                    break
                                # Parse JSON del evento SSE
                                import json
                                try:
                                    evt = json.loads(text)
                                except json.JSONDecodeError:
                                    # JSON incompleto por streaming TCP split —
                                    # similar al split multibyte: re-bufferea.
                                    buffer = line + b"\n\n" + buffer
                                    break
                                choices = evt.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
        except httpx.HTTPStatusError as e:
            log.error("local_llm_stream_http_error", status=e.response.status_code, error=str(e)[:200])
        except httpx.ConnectError as e:
            log.error("local_llm_stream_connect_error", error=str(e)[:200])
        except Exception as e:
            log.error("local_llm_stream_failed", error=str(e)[:200])

    # ── Helpers internos ─────────────────────────────────────────────────

    @property
    def _http_url(self) -> str:
        # 127.0.0.1 evita DNS resolution de localhost en Windows,
        # que puede tardar ms extras o fallar por config de hosts.
        return f"http://127.0.0.1:{self._port}"

    def _model_file_basename(self) -> str:
        # openai-compatible: el "model" puede ser libre (no se valida en server-embebido)
        return Path(self._model_path).name if self._model_path else "default"

    def _cleanup_on_exit(self) -> None:
        """atexit hook — llama a unload si hay proceso vivo."""
        if self._process is not None and self._process.poll() is None:
            try:
                self._kill_and_reset()
            except Exception:
                pass  # No romper el shutdown del intérprete

    def _detect_gpu(self) -> bool:
        """Reusa core.hardware.detect_hardware — mismo patrón que el wrapper viejo."""
        hw = detect_hardware()
        if hw.gpu_cuda and hw.gpu_vram_gb > 0:
            self._gpu_name = hw.gpu_name
            self._gpu_vram_gb = hw.gpu_vram_gb
            self._gpu_layers = self._calculate_gpu_layers()
            return True
        self._gpu_layers = 0
        self._gpu_name = ""
        self._gpu_vram_gb = 0.0
        return False

    def _calculate_gpu_layers(self) -> int:
        """Decide cuántas capas del modelo cargar en GPU (-1 = todas).

        Heurística heredada del wrapper previo (docs §3 / report delegación):
          - Si VRAM >= modelo + buffer de KV → -1 (offload total)
          - Si no hay VRAM → 0
          - Caso intermedio → una fracción de las 28 capas
        """
        if self._gpu_vram_gb <= 0:
            return 0
        # Tamaño estimado del modelo Q4 para el buffering de GPU
        estimated_model_gb = 1.1  # _MODEL_SIZE_GB constante implícita
        available_for_kv = self._gpu_vram_gb - estimated_model_gb - _GPU_KV_BUFFER_GB
        if available_for_kv >= 0:
            return -1  # todas las capas
        # Cálculo de fracción
        fraction = max(0.0, available_for_kv + _GPU_KV_BUFFER_GB) / self._gpu_vram_gb
        n = max(1, int(_MODEL_TOTAL_LAYERS * fraction))
        return n

    def _resolve_model_path(self, filename: str | None = None) -> Path:
        """Buscar el archivo .gguf en MODEL_SEARCH_PATHS. Raises FileNotFoundError."""
        target_name = filename or self._model_path
        if target_name is None:
            target_name = os.path.basename(_DEFAULT_MODEL_FILE)
        target_path = Path(target_name)
        # Caso 1: ruta absoluta o relativa válida desde cwd
        if target_path.exists() and target_path.is_file():
            return target_path
        # Caso 2: solo filename → buscar en MODEL_SEARCH_PATHS
        if not target_path.is_absolute():
            for d in MODEL_SEARCH_PATHS:
                candidate = d / target_path.name
                if candidate.exists() and candidate.is_file():
                    return candidate
        raise FileNotFoundError(
            f"Modelo LLM no encontrado: {target_name}. "
            f"Directorios buscados: {[str(d) for d in MODEL_SEARCH_PATHS]}"
        )

    def _resolve_server_executable(self) -> Path:
        """Resolver la ruta al binario `llama-server.exe`. Raises FileNotFoundError."""
        return _resolve_server_executable_static()

    def _build_server_args(
        self, server_bin: Path, model_path: Path, port: int
    ) -> list[str]:
        """Argumentos CLI para `llama-server.exe` — adaptación del stress test 1000
        (doc 12) a la arquitectura sidecar.

        Confirmación experimental 2026-07-31:
          - `--parallel 1`               → N_KEYWORD_RES = 1. Confirmado en el
            log del server: "init: n_slots = 1, n_ctx_slot = 16384". Replica
            el comportamiento del in-process (stress test 1000 mensajes).
          - `--cache-type-k/v q8_0`      → lo intentamos, PROVOCÓ timeout en el
            primer request. La combinación `kv_unified=false` + `n_slots=1`
            + KV quantizada rompe algo en el binario CUDA b10199 (el primer
            request cuelga 300s). Rollback del KV type a default fp16.
            RAZÓN para no reintroducir: el in-process del stress test 1000
            usaba fp16 y surrvivió 207 min. Lo mismo debe alcanzar acá.

        Estrategia final probada: 1 slot + KV fp16 + n_ctx 16384. La KV fp16
        de 1 slot (~5.3 GB) + modelo Q1_0 (~1.16 GB) ≈ 6.5 GB — apenas pasa
        en 6 GB VRAM, parte va a RAM. llama.cpp maneja el reparto VRAM/RAM
        automáticamente (stable, rinde, no cuelga).
        """
        args = [
            str(server_bin),
            "-m", str(model_path),
            "--port", str(port),
            "-c", str(self._n_ctx),
            "-ngl", str(self._gpu_layers) if self._gpu_layers >= 0 else "99",
            "--parallel", "1",
            "--no-warmup",
            "--no-webui",
            "--cont-batching",
            "--jinja",  # Necesario para function calling nativo OpenAI-style
            # KV cache quantizada q8_0: KV de ~5.3GB (fp16) → ~2.65GB. La KV
            # cabe en 6GB VRAM junto al modelo (1.16GB) → VRAM libre 2.4GB.
            "--cache-type-k", "q8_0",
            "--cache-type-v", "q8_0",
            # Limitar la prompt cache del server a 256 MiB (default 8192 = 8GB).
            "--cache-ram", "256",
        ]
        return args

    def _build_messages(self, prompt: str, system_prompt: str) -> list[dict]:
        """DEPRECATED desde migración a llama-server (v1.0.0).
        Mantiene compatibilidad para tests legacy que aún pasan prompt+system.
        Será eliminado en v1.1.0. Nuevos callers deben pasar `messages` multi-turno.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    async def _wait_for_server_ready(self) -> bool:
        """Hacer polling a /health con backoff exponencial (timeout 30s).

        Patrón análogo a utils/file_handlers.py:120-137 (socket reachability).
        Versión ASYNC. Mantiene compat para callers que quieran usarla desde
        contexts async (raro; casi todos los callers van por load() sync).
        """
        deadline = time.monotonic() + _HEALTH_PROBE_TIMEOUT_S
        delay = _HEALTH_PROBE_INITIAL_DELAY_S
        url = f"{self._http_url}/health"

        while time.monotonic() < deadline:
            try:
                async with httpx.AsyncClient(timeout=1.0) as client:
                    resp = await client.get(url)
                if resp.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.ReadTimeout, ConnectionError):
                pass
            await asyncio.sleep(delay)
            delay = min(delay * _HEALTH_PROBE_BACKOFF_FACTOR, _HEALTH_PROBE_MAX_DELAY_S)
        return False

    def _wait_for_server_ready_sync(self) -> bool:
        """Versión síncrona del health probe. Usada por load().

        Idéntica lógica al backoff del async, pero con httpx.Client (sync)
        y time.sleep. Esto evita asyncio.run() y por lo tanto funciona
        cuando load() se llama desde dentro de un event loop activo
        (que es lo normal en producción: provider.chat() es async).
        """
        deadline = time.monotonic() + _HEALTH_PROBE_TIMEOUT_S
        delay = _HEALTH_PROBE_INITIAL_DELAY_S
        url = f"{self._http_url}/health"

        while time.monotonic() < deadline:
            try:
                with httpx.Client(timeout=1.0) as client:
                    resp = client.get(url)
                if resp.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.ReadTimeout, ConnectionError):
                pass
            time.sleep(delay)
            delay = min(delay * _HEALTH_PROBE_BACKOFF_FACTOR, _HEALTH_PROBE_MAX_DELAY_S)
        return False

    def _drain_stderr_for_diagnostic(self) -> None:
        """Lee el stderr/stdout del subproceso para loguearlo como last-resort de diagnóstico."""
        if self._process is None:
            return
        try:
            # Non-blocking read — el stdout está merged con stderr via STDOUT.
            import select
            if not select.select([self._process.stdout], [], [], 0.0)[0]:
                return
            output = self._process.stdout.read(2048)
            if output:
                log.warning("llama_server_stderr_during_load_fail", output=output.decode("utf-8", errors="replace"))
        except Exception:
            # select no disponible en algunos Win <3.6 + asyncio — silencioso.
            pass

    # ── Drenaje continuo de stdout (FIX interbloqueo de pipe) ──────────────

    # Patrones de línea del server que merecen llegada al log del backend.
    _SERVER_ERROR_PATTERNS = (
        "error", "CUDA error", "out of memory", "OOM", "abort",
        "failed", "failed to", "insufficient", "bad_alloc",
    )

    def _start_stdout_drain(self) -> None:
        """Thread daemon que drena el stdout del subproceso a `logs/llama-server.log`.

        CAUSA RAIZ CORREGIDA (diagnóstico 2026-07-31): `llama-server.exe` escribe
        logs de timings/requests al stdout. Con `stdout=subprocess.PIPE` y sin
        lector, el buffer del pipe (64KB en Windows) se llena después de 2-4
        requests con n_ctx=16384 → el `write()` del server bloquea → el server
        se congela silenciosamente (poll() vivo, /health sin responder). Eso
        era la "muerte tras R003" sin log de unload del ResourceManager.

        Además de desbloquear el pipe, el archivo `logs/llama-server.log` da
        observabilidad real del server (timings, errores CUDA) para diagnóstico
        de futuros incidentes. Las líneas con patrones de error se reenvían al
        log del backend como warning.
        """
        if self._process is None or self._process.stdout is None:
            return
        try:
            log_dir = Path(__file__).resolve().parents[3] / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            self._stdout_file = open(
                log_dir / "llama-server.log", "ab", buffering=0
            )
        except OSError as e:
            log.warning("llama_server_logfile_failed", error=str(e)[:120])
            self._stdout_file = None

        def _drain() -> None:
            proc = self._process
            if proc is None or proc.stdout is None:
                return
            try:
                while True:
                    line = proc.stdout.readline()
                    if line == b"":
                        # EOF: el subproceso cerró stdout (salió o crasheó).
                        if proc.poll() is not None:
                            log.warning(
                                "llama_server_process_exited",
                                pid=proc.pid,
                                returncode=proc.returncode,
                            )
                        break
                    if self._stdout_file is not None:
                        try:
                            self._stdout_file.write(line)
                        except OSError:
                            pass
                    text = line.decode("utf-8", errors="replace").strip()
                    if text and text.lower().startswith(self._SERVER_ERROR_PATTERNS):
                        log.warning("llama_server_output", line=text[:300])
            except Exception:
                # El pipe puede cerrarse de golpe si matamos el proceso.
                pass

        self._drain_thread = threading.Thread(
            target=_drain, name="llama-server-stdout-drain", daemon=True
        )
        self._drain_thread.start()

    def _kill_and_reset(self) -> None:
        """Terminar el subproceso terminando rápido o forzando kill si no muere."""
        if self._process is not None:
            try:
                self._process.terminate()
                # wait_for sincroniza no bloquea disco en Win
                try:
                    self._process.wait(timeout=_PROCESS_TERMINATE_WAIT_S)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=2.0)
            except Exception as e:
                log.warning("llama_server_kill_failed", error=str(e)[:100])
        self._process = None
        self._port = None
        self._loaded = False
        # Cerrar drenaje: el thread es daemon y termina solo en EOF del pipe,
        # pero cerramos el archivo y esperamos un join breve por prolijidad.
        thread = self._drain_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self._drain_thread = None
        if self._stdout_file is not None:
            try:
                self._stdout_file.close()
            except OSError:
                pass
            self._stdout_file = None


# ── Singleton accessor (preservar la firma vieja) ────────────────────────
def get_local_llm() -> Optional[LocalLLM]:
    """Thread-safe lazy singleton. False-y si `llama-server.exe` no está disponible."""
    global _local_llm
    if _local_llm is not None:
        return _local_llm
    with _lock:
        if _local_llm is None:
            if _can_instantiate():
                _local_llm = LocalLLM()
    return _local_llm


def is_local_llm_available() -> bool:
    """Chequeo triple (docs §4.D4): binario + modelo default + RAM suficiente."""
    return _can_instantiate()


def diagnosticar_llm_local() -> tuple[bool, str]:
    """Igual que `is_local_llm_available()`, pero diciendo CUÁL de las tres falla.

    LO QUE ARREGLA. `is_local_llm_available()` colapsa tres causas distintas en
    un booleano, y quien lo llamaba (el proveedor de MolChat) escribía SIEMPRE
    el mismo mensaje: «llama-server.exe no está disponible… verificá que el
    binario existe en tools/llama-cuda/ o tools/llama/».

    En una instalación limpia ese mensaje es FALSO. El instalador sí empaqueta
    `tools/llama/llama-server.exe`; lo que no empaqueta es ningún `.gguf` —los
    modelos se descargan desde Opciones ▸ Modelos— así que la comprobación que
    falla es la segunda y el usuario se queda buscando un binario que está
    donde debe. Encima el mensaje nombraba `tools/llama-cuda/`, que ni siquiera
    forma parte del paquete.

    Devuelve `(disponible, motivo)`. El motivo va escrito para quien usa la
    aplicación, no para quien la compila: dice qué hacer, no dónde mirar en el
    código.
    """
    try:
        try:
            _resolve_server_executable_static()
        except FileNotFoundError:
            return False, (
                "El motor de MolChat no está instalado en este equipo. "
                "Reinstala la aplicación para reponerlo: forma parte del paquete "
                "y no se descarga aparte."
            )

        try:
            _ = LocalLLM._resolve_model_path_static()
        except FileNotFoundError:
            return False, (
                "No hay ningún modelo de lenguaje descargado. MolChat necesita "
                "uno para responder. Descárgalo desde Opciones ▸ Modelos; el "
                "resto de la evaluación funciona sin él."
            )

        try:
            from services.ai.resource_manager import get_resource_manager, MIN_RAM_FREE_GB

            libre = get_resource_manager()._get_ram_free_gb()
            if libre < MIN_RAM_FREE_GB:
                return False, (
                    f"No hay memoria suficiente para cargar el modelo: quedan "
                    f"{libre:.1f} GB libres y hacen falta al menos "
                    f"{MIN_RAM_FREE_GB:.0f} GB. Cierra otras aplicaciones e "
                    f"inténtalo de nuevo."
                )
        except ImportError:
            # Sin ResourceManager (entorno de pruebas) no se bloquea nada.
            pass
    except Exception as exc:  # noqa: BLE001 — se reporta, no se traga
        return False, (
            f"No se pudo comprobar el estado de MolChat en este equipo "
            f"({type(exc).__name__})."
        )
    return True, "OK"


def _can_instantiate() -> bool:
    """Implementa el chequeo triple de D4 sin exponer internals a callers externos."""
    try:
        # 1. Binario existe (resolución robusta multi-candidate, ver _resolve_server_executable_static)
        try:
            _resolve_server_executable_static()
        except FileNotFoundError:
            return False
        # 2. Modelo default existe (en algún search path)
        try:
            _ = LocalLLM._resolve_model_path_static()
        except FileNotFoundError:
            return False
        # 3. RAM suficiente para cargar (≥ MIN_RAM_FREE_GB const del ResourceManager).
        #    ⚠️  NO usamos rm.get_status() aquí — generaría dependencia circular:
        #    _can_instantiate → get_status → get_local_llm → _can_instantiate → ∞.
        #    _get_ram_free_gb() consulta psutil directamente sin tocar el LLM.
        try:
            from services.ai.resource_manager import get_resource_manager, MIN_RAM_FREE_GB
            rm = get_resource_manager()
            if rm._get_ram_free_gb() < MIN_RAM_FREE_GB:
                return False
        except ImportError:
            pass  # ResourceManager opcional en tests — no bloquear su instantiation
    except Exception:
        return False
    return True


def _resolve_model_path_static() -> Path:
    """Resolver el modelo default sin instanciar la clase — helper de is_available."""
    instance = object.__new__(LocalLLM)
    instance._model_path = None
    return instance._resolve_model_path()
LocalLLM._resolve_model_path_static = staticmethod(_resolve_model_path_static)


def _resolve_server_executable_static() -> Path:
    """Resolver la ruta al binario `llama-server.exe` sin instanciar LocalLLM.

    Busca en este orden:
      1. Path absoluto tal cual (si viene absoluto desde config).
      2. Relativo al CWD del proceso (ej: backend corre desde la raíz del repo).
      3. Relativo al directorio PADRE del CWD (ej: backend corre desde backend/,
         la raíz del proyecto está un nivel arriba → tools/llama/ ahí).
      4. Relativo a la raíz del repo calculada desde __file__
         (backend/services/ai/local_llm.py → parents[3] = raíz del repo).
         Robusto frente a imports de tests u otros working dirs.
    """
    raw = get_settings().llama_server_executable_path
    path = Path(raw)
    candidates = []
    if path.is_absolute():
        candidates.append(path)
    else:
        cwd = Path.cwd()
        candidates.append(cwd / path)                       # CWD/tools/llama/...
        candidates.append(cwd.parent / path)                # ../tools/llama/...
        try:
            repo_root = Path(__file__).resolve().parents[3]
            candidates.append(repo_root / path)
        except IndexError:
            pass
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"llama-server.exe no encontrado. Buscado en: {candidates}. "
        "Empaquetado local esperado en tools/llama/. "
        "Ver docs/33_MIGRATION_LLAMA_SERVER.md §4.D3."
    )
LocalLLM._resolve_server_executable_static = staticmethod(_resolve_server_executable_static)
