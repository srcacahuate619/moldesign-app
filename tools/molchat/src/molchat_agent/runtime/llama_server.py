"""llama-server subprocess lifecycle (port of the internal wrapper idea).

Lessons kept from ``local_llm.py`` (compass, not a copy): cwd at the binary
directory (Windows DLL resolution), no-window creation flags declared
literally, a stdout drain thread before health-probing (64 KB pipe fills or
the server stalls), sync health polling (safe inside any event loop), and an
atexit hook that never breaks interpreter shutdown. Dropped couplings:
ResourceManager, core.config/hardware, structlog.

GPU offload is operator-chosen (``gpu_layers``) with an nvidia-smi best
effort when set to ``"auto"``; anything unknown means CPU (0), loudly told.
"""

from __future__ import annotations

import atexit
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .models import ModelError, resolve_model

DEFAULT_PORT = 8400
DEFAULT_CTX = 16384
HEALTH_TIMEOUT_S = 60.0
STOP_TIMEOUT_S = 10.0
CREATE_NO_WINDOW = 0x08000000


class LlamaServerError(RuntimeError):
    """The local server could not start, answer, or stop cleanly."""


def default_binary_dirs() -> list[Path]:
    return [Path.home() / ".molchat" / "bin", Path("tools") / "llama"]


def resolve_binary(name_or_path: str | Path | None = None) -> Path:
    """Find llama-server. Raises LlamaServerError (never returns a guess)."""
    names = [str(name_or_path)] if name_or_path else []
    names += ["llama-server.exe", "llama-server"]
    for name in names:
        candidate = Path(name)
        if candidate.is_file():
            return candidate
        if not candidate.is_absolute() and len(candidate.parts) == 1:
            for directory in default_binary_dirs():
                found = directory / name
                if found.is_file():
                    return found
            which = shutil.which(name)
            if which:
                return Path(which)
    raise LlamaServerError(
        f"llama-server no encontrado ({name_or_path or 'búsqueda por defecto'}); "
        f"buscado en {[str(d) for d in default_binary_dirs()]} y PATH")


def detect_vram_gb(run: Any = subprocess.run) -> float:
    """Best-effort VRAM via nvidia-smi; 0.0 when unknown (CPU fallback)."""
    try:
        completed = run(["nvidia-smi", "--query-gpu=memory.total",
                         "--format=csv,noheader,nounits"],
                        capture_output=True, text=True, timeout=10)
    except (OSError, ValueError):
        return 0.0
    if completed.returncode != 0:
        return 0.0
    try:
        mib = float(completed.stdout.split()[0])
    except (IndexError, ValueError):
        return 0.0
    return mib / 1024


def gpu_layers_for(vram_gb: float, *, model_gb: float = 1.1) -> int:
    """-1 (all layers) when the model + KV buffer fit; else 0 (CPU).

    Simplified from the internal fraction heuristic: partial offload is an
    operator choice via ``gpu_layers=N``, not a guess.
    """
    if vram_gb - model_gb - 0.5 >= 0:
        return -1
    return 0


class LlamaServer:
    def __init__(self, *, binary: str | Path | None = None,
                 model: str | Path | None = None,
                 port: int = DEFAULT_PORT, n_ctx: int = DEFAULT_CTX,
                 gpu_layers: int | str = "auto",
                 argv_builder: Callable[[Path, Path, int], list[str]] | None = None,
                 health_timeout_s: float = HEALTH_TIMEOUT_S) -> None:
        self._binary_arg = binary
        self._model_arg = model
        self._port = port
        self._n_ctx = n_ctx
        self._gpu_layers = gpu_layers
        self._argv_builder = argv_builder or self._llama_argv
        self._health_timeout_s = health_timeout_s
        self._process: subprocess.Popen | None = None
        self._drain: threading.Thread | None = None
        self._registered_exit = False

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._port}"

    @property
    def port(self) -> int:
        return self._port

    def alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def healthy(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.url}/health", timeout=3) as response:
                return response.status < 400
        except (OSError, ValueError):
            return False

    def start(self) -> str:
        """Start the server and wait for /health. Idempotent. Returns a note."""
        if self.alive() and self.healthy():
            return "already running"
        if self.alive():
            self.stop()
        binary = resolve_binary(self._binary_arg)
        if self._model_arg is None:
            raise LlamaServerError("falta el modelo (.gguf): pásalo con --model")
        try:
            model = resolve_model(self._model_arg)
        except ModelError as exc:
            raise LlamaServerError(str(exc)) from exc
        self._resolve_layers()  # fail fast on bad gpu_layers, before spawning
        argv = self._argv_builder(binary, model, self._port)
        try:
            self._process = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(binary.parent),
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except OSError as exc:
            raise LlamaServerError(f"no se pudo lanzar {binary}: {exc}") from exc
        self._start_drain()
        if not self._registered_exit:
            atexit.register(self._cleanup_on_exit)
            self._registered_exit = True
        if not self._wait_ready():
            diagnostic = self._diagnostic()
            self._kill()
            raise LlamaServerError(
                f"llama-server no respondió /health en {self._health_timeout_s:.0f}s"
                + (f": {diagnostic}" if diagnostic else ""))
        return f"listening on {self.url}"

    def stop(self) -> str:
        """Terminate the server; kill after a grace period. Idempotent."""
        process, self._process = self._process, None
        if process is None or process.poll() is not None:
            return "not running"
        process.terminate()
        try:
            process.wait(timeout=STOP_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=STOP_TIMEOUT_S)
        return "stopped"

    def _llama_argv(self, binary: Path, model: Path, port: int) -> list[str]:
        layers = self._resolve_layers()
        return [str(binary), "-m", str(model), "--port", str(port),
                "-c", str(self._n_ctx),
                "-ngl", str(layers) if layers >= 0 else "99",
                "--parallel", "1", "--no-warmup", "--no-webui",
                "--cont-batching", "--jinja"]

    def _resolve_layers(self) -> int:
        if isinstance(self._gpu_layers, int):
            return self._gpu_layers
        if self._gpu_layers != "auto":
            raise LlamaServerError(f"gpu_layers no válido: {self._gpu_layers!r}")
        return gpu_layers_for(detect_vram_gb())

    def _wait_ready(self) -> bool:
        deadline = time.monotonic() + self._health_timeout_s
        delay = 0.2
        while time.monotonic() < deadline:
            if not self.alive():
                return False
            if self.healthy():
                return True
            time.sleep(delay)
            delay = min(delay * 1.5, 2.0)
        return self.alive() and self.healthy()

    def _start_drain(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        stream = self._process.stdout

        def _drain() -> None:
            try:
                for _line in stream:
                    pass
            except (OSError, ValueError):
                pass

        self._drain = threading.Thread(target=_drain, daemon=True)
        self._drain.start()

    def _diagnostic(self) -> str:
        return ""  # the drain consumed stdout; keep the hook for a ring buffer

    def _kill(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        try:
            process.kill()
            process.wait(timeout=STOP_TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _cleanup_on_exit(self) -> None:
        try:
            self._kill()
        except Exception:  # noqa: BLE001 - never break interpreter shutdown
            pass
