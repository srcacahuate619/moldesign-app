"""
services/ai/resource_manager.py

Gestor de recursos para el LLM local.

Reglas de oro:
  1. El LLM NUNCA se carga al iniciar la app. Solo on-demand.
  2. Si el pipeline está ejecutándose (Vina, MM-GBSA) → LLM descargado.
  3. Si RAM libre < 4 GB → LLM no se carga (prioridad al pipeline).
  4. Si VRAM libre < 3 GB en GPU → LLM no se carga.
  5. Si el LLM no se usa por 5 min → auto-descarga.
  6. Si RAM o VRAM caen por debajo del mínimo estando cargado → descargar.
  7. Si el usuario activa "keep_loaded" manualmente → no descargar en pipeline.

Umbrales de RAM/VRAM:
  - RAM: psutil.virtual_memory().available (RAM realmente libre de TODO el sistema)
  - VRAM: nvidia-smi --query-gpu=memory.free (VRAM libre de apps de terceros)
    fallback → torch.cuda.mem_get_info() (solo PyTorch, parcial)

Arquitectura:
  ResourceManager (singleton, thread-safe)
    ├── PipelineState: idle | busy
    ├── LLMState: unloaded | loaded
    ├── RAM tracking (psutil, cache 3s)
    ├── VRAM tracking (nvidia-smi, cache 10s)
    └── Auto-unload timer loop (asyncio background task, cada 60s)
"""

from __future__ import annotations

import asyncio
import subprocess
import threading
import time
from enum import Enum
from utils.procesos import BANDERAS_SIN_VENTANA


class PipelineState(Enum):
    IDLE = "idle"
    BUSY = "busy"


class LLMState(Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"


# ── Thresholds ──────────────────────────────────────────────────────
# Estos umbrales aplican sobre la RAM/VRAM REALMENTE libre
# (descontando lo que usan Chrome, juegos, VS Code, etc.)

MIN_RAM_FREE_GB = 4.0       # Windows idle ya come ~2-3 GB
KEEP_LLM_RAM_GB = 2.5       # Si RAM baja de esto con LLM cargado → descargar
COMFORTABLE_RAM_GB = 6.0    # Si > esto, mantener cargado

MIN_VRAM_FREE_GB = 2.0      # Qwen2.5-1.5B Q4 (~1.0) + KV (~0.5) + buffer
LOW_VRAM_FREE_GB = 1.0      # Si cae de esto → descargar YA
COMFORTABLE_VRAM_FREE_GB = 4.0  # Si > esto y keep_loaded, mantener

IDLE_TIMEOUT_S = 300         # 5 min sin uso → descargar
IDLE_CHECK_INTERVAL_S = 60   # cada 60s
RAM_CACHE_S = 3.0            # Cache psutil
VRAM_CACHE_S = 10.0          # nvidia-smi es pesado, no spamear


class ResourceManager:
    """Singleton thread-safe que decide CUANDO cargar/descargar el LLM."""

    def __init__(self):
        self._pipeline_state = PipelineState.IDLE
        self._llm_state = LLMState.UNLOADED
        self._lock = threading.Lock()
        self._last_used: float = 0.0
        self._last_ram_check: float = 0.0
        self._cached_ram_free_gb: float = 0.0
        self._last_vram_check: float = 0.0
        self._cached_vram_free_gb: float = -1.0  # -1 = no detectada
        self._cached_vram_total_gb: float = 0.0
        self._keep_loaded = False
        self._idle_task: asyncio.Task | None = None

    @property
    def keep_loaded(self) -> bool:
        return self._keep_loaded

    def set_keep_loaded(self, flag: bool):
        with self._lock:
            self._keep_loaded = flag

    # ── Pipeline lifecycle ──────────────────────────────────────────

    def on_pipeline_start(self):
        with self._lock:
            self._pipeline_state = PipelineState.BUSY
            if self._keep_loaded:
                return
            if self._llm_state == LLMState.LOADED:
                if self._vram_has_headroom():
                    return
                self._unload_llm_internal()

    def on_pipeline_end(self):
        with self._lock:
            self._pipeline_state = PipelineState.IDLE

    def is_pipeline_busy(self) -> bool:
        return self._pipeline_state == PipelineState.BUSY

    # ── LLM lifecycle ───────────────────────────────────────────────

    def on_llm_loaded(self):
        with self._lock:
            self._llm_state = LLMState.LOADED
            self._last_used = time.monotonic()
        self._ensure_idle_checker()

    def on_llm_unloaded(self):
        with self._lock:
            self._llm_state = LLMState.UNLOADED

    def on_llm_loading(self):
        with self._lock:
            self._llm_state = LLMState.LOADING

    def touch(self):
        """El usuario usó el LLM — resetear timer de inactividad."""
        with self._lock:
            self._last_used = time.monotonic()

    # ── Decision logic ──────────────────────────────────────────────

    def can_load(self) -> tuple[bool, str]:
        with self._lock:
            if self._pipeline_state == PipelineState.BUSY:
                return False, (
                    "Pipeline ocupado. Esperá a que termine la evaluación."
                )

            if self._llm_state == LLMState.LOADED:
                return True, "LLM ya cargado."

            if self._llm_state == LLMState.LOADING:
                return False, "LLM cargándose. Esperá unos segundos."

        ram_free = self._get_ram_free_gb()
        if ram_free < MIN_RAM_FREE_GB:
            return False, (
                f"RAM insuficiente: {ram_free:.1f} GB libres "
                f"(se necesita ≥{MIN_RAM_FREE_GB:.0f} GB). "
                "Windows ya consume 2-3 GB. Cerrá otras aplicaciones "
                "o configurá un proveedor cloud en Opciones > Intérprete IA."
            )

        vram_free = self._get_vram_free_gb()
        if vram_free >= 0 and vram_free < MIN_VRAM_FREE_GB:
            return False, (
                f"VRAM insuficiente: {vram_free:.1f} GB libres en GPU "
                f"(se necesita ≥{MIN_VRAM_FREE_GB:.0f} GB para Qwen2.5-1.5B "
                f"de ~1.1 GB + KV-cache). Cerrá juegos o apps gráficas "
                "o configurá un proveedor cloud."
            )

        return True, "OK"

    def should_unload(self) -> tuple[bool, str]:
        with self._lock:
            if self._llm_state != LLMState.LOADED:
                return False, "LLM no cargado."

            idle_time = time.monotonic() - self._last_used
            if idle_time > IDLE_TIMEOUT_S:
                return True, f"Inactivo por {idle_time:.0f}s (>{IDLE_TIMEOUT_S}s)."

        ram_free = self._get_ram_free_gb()
        if ram_free < KEEP_LLM_RAM_GB:
            return True, (
                f"RAM crítica: {ram_free:.1f} GB libres con LLM cargado. "
                "Descargando para liberar recursos. Posible causa: otra app "
                "consumió RAM."
            )

        vram_free = self._get_vram_free_gb()
        if vram_free >= 0 and vram_free < LOW_VRAM_FREE_GB:
            return True, (
                f"VRAM crítica: {vram_free:.1f} GB libres en GPU. "
                "Descargando para liberar VRAM. Posible causa: abriste un "
                "juego o app de diseño."
            )

        return False, "OK"

    def should_keep_loaded(self) -> bool:
        if self._keep_loaded:
            return True
        ram_free = self._get_ram_free_gb()
        return ram_free >= COMFORTABLE_RAM_GB

    # ── Status ──────────────────────────────────────────────────────

    def get_status(self) -> dict:
        idle_s = 0.0
        if self._llm_state == LLMState.LOADED and self._last_used > 0:
            idle_s = round(time.monotonic() - self._last_used, 1)

        gpu_name = ""
        gpu_vram_total = 0.0
        using_gpu = False
        try:
            from services.ai.local_llm import get_local_llm
            llm = get_local_llm()
            if llm:
                using_gpu = llm.using_gpu
                gpu_name = llm.gpu_name
                gpu_vram_total = llm.gpu_vram_gb
        except ImportError:
            pass

        vram_free = self._get_vram_free_gb()

        return {
            "pipeline_state": self._pipeline_state.value,
            "llm_state": self._llm_state.value,
            "ram_free_gb": round(self._get_ram_free_gb(), 1),
            "ram_total_gb": round(self._get_ram_total_gb(), 1),
            "min_ram_for_llm_gb": MIN_RAM_FREE_GB,
            "keep_llm_ram_gb": KEEP_LLM_RAM_GB,
            "idle_timeout_s": IDLE_TIMEOUT_S,
            "idle_seconds": idle_s,
            "keep_loaded": self._keep_loaded,
            "using_gpu": using_gpu,
            "gpu_name": gpu_name,
            "gpu_vram_total_gb": gpu_vram_total,
            "vram_free_gb": round(vram_free, 1) if vram_free >= 0 else -1,
        }

    # ── Background idle checker ─────────────────────────────────────

    def _ensure_idle_checker(self):
        if self._idle_task is None or self._idle_task.done():
            try:
                self._idle_task = asyncio.create_task(self._idle_loop())
            except RuntimeError:
                pass

    async def _idle_loop(self):
        while True:
            await asyncio.sleep(IDLE_CHECK_INTERVAL_S)
            should, reason = self.should_unload()
            if should:
                self._unload_llm_internal()
                break
            if self._llm_state != LLMState.LOADED:
                break

    # ── RAM tracking ────────────────────────────────────────────────

    def _get_ram_free_gb(self) -> float:
        now = time.monotonic()
        if now - self._last_ram_check > RAM_CACHE_S:
            try:
                import psutil
                self._cached_ram_free_gb = psutil.virtual_memory().available / (1024 ** 3)
                self._last_ram_check = now
            except Exception:
                return 8.0
        return self._cached_ram_free_gb

    def _get_ram_total_gb(self) -> float:
        try:
            import psutil
            return psutil.virtual_memory().total / (1024 ** 3)
        except Exception:
            return 0.0

    # ── VRAM tracking ──────────────────────────────────────────────

    def _get_vram_free_gb(self) -> float:
        """VRAM realmente libre (todas las apps, no solo PyTorch)."""
        now = time.monotonic()
        if now - self._last_vram_check <= VRAM_CACHE_S and self._cached_vram_free_gb >= 0:
            return self._cached_vram_free_gb

        free = self._query_vram_nvidia_smi()
        if free < 0:
            free = self._query_vram_torch_cuda()
        if free < 0:
            free = self._query_vram_from_llm()

        self._cached_vram_free_gb = free
        self._last_vram_check = now
        return free

    def _query_vram_nvidia_smi(self) -> float:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.free,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=4,
                creationflags=BANDERAS_SIN_VENTANA,
            )
            if result.returncode == 0 and result.stdout.strip():
                row = result.stdout.strip().split("\n")[0]
                parts = [p.strip() for p in row.split(",")]
                free_mb = float(parts[0])
                total_mb = float(parts[1])
                self._cached_vram_total_gb = round(total_mb / 1024, 1)
                return round(free_mb / 1024, 1)
        except Exception:
            pass
        return -1.0

    def _query_vram_torch_cuda(self) -> float:
        # ⚠️ POST-MIGRACIÓN llama-server.exe (ver docs/33_MIGRATION_LLAMA_SERVER.md §4.D9):
        # Este tier solo reporta la VRAM usada dentro del contexto CUDA del proceso
        # Python (rescoring, TabPFN, etc.). El LLM vive ahora en un subproceso
        # independiente (llama-server.exe) con su propio contexto CUDA, por lo que
        # su consumo de VRAM no se refleja aquí.
        # → La fuente autoritativa para VRAM libre total es _query_vram_nvidia_smi()
        #   (tier 1), que ve la GPU completa desde fuera del proceso Python.
        # Este tier se conserva para el caso "LLM no cargado" (rescoring + PyTorch solos).
        try:
            import torch
            if torch.cuda.is_available():
                free_bytes, total_bytes = torch.cuda.mem_get_info()
                self._cached_vram_total_gb = round(total_bytes / (1024**3), 1)
                return round(free_bytes / (1024**3), 1)
        except Exception:
            pass
        return -1.0

    def _query_vram_from_llm(self) -> float:
        try:
            from services.ai.local_llm import get_local_llm
            llm = get_local_llm()
            if llm and llm.gpu_vram_gb > 0:
                self._cached_vram_total_gb = llm.gpu_vram_gb
        except Exception:
            pass
        return -1.0

    def _vram_has_headroom(self) -> bool:
        try:
            from services.ai.local_llm import get_local_llm
            llm = get_local_llm()
            if llm and llm.using_gpu:
                vram_free = self._get_vram_free_gb()
                if vram_free >= COMFORTABLE_VRAM_FREE_GB:
                    return True
        except ImportError:
            pass
        return False

    def _unload_llm_internal(self):
        try:
            from services.ai.local_llm import get_local_llm
            llm = get_local_llm()
            if llm and llm.is_loaded:
                llm.unload()
        except Exception:
            pass
        self._llm_state = LLMState.UNLOADED


_resource_manager: ResourceManager | None = None
_rm_lock = threading.Lock()


def get_resource_manager() -> ResourceManager:
    global _resource_manager
    if _resource_manager is None:
        with _rm_lock:
            if _resource_manager is None:
                _resource_manager = ResourceManager()
    return _resource_manager
