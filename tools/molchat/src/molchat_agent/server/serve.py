"""Standalone wiring: config -> state -> app -> uvicorn (loopback only).

``molchat-agent serve`` runs the sidecar against a local MolDesign without
touching its frontend (PLAN 4.4, the hackathon demo mode). Bind is loopback
only, always: a non-loopback ``--host`` is refused loudly, never silently
reinterpreted.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..bridge import MolDesignBridge
from ..config import MolChatConfig, load_config
from ..conversation.memory import MemoryStore
from ..conversation.tools import PlatformBackend
from ..orchestration.store import ExecutionStore
from ..providers import build_registry
from ..voice.local_whisper import ChainSTT, LocalWhisperSTT, faster_whisper_available
from ..voice.moldesign_whisper import MolDesignWhisper
from ..voice.cloud_stt import CloudSTT
from .app import create_app
from .auth import mint, standalone_secret
from .executions import ExecutionManager
from .state import ServerState

DEFAULT_PORT = 8771
LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass
class ServedSidecar:
    app: Any
    state: ServerState
    bridge: MolDesignBridge
    secret: bytes
    token: str | None  # standalone token (printed once); None in hosted mode
    ui_dist: Path | None


def validate_bind_host(host: str) -> str:
    if (host or "").lower() not in LOOPBACK:
        raise ValueError(f"el sidecar solo escucha en loopback, no en {host!r}")
    return host


def find_ui_dist(explicit: str = "") -> Path | None:
    """Locate the built UI: explicit flag/env, then ./ui/dist, else None."""
    candidates = [Path(explicit)] if explicit else []
    candidates.append(Path.cwd() / "ui" / "dist")
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate
    return None


def _build_stt(config: MolChatConfig, bridge: MolDesignBridge):  # type: ignore[no-untyped-def]
    """STT chain: cloud when explicitly enabled, else platform/local chain.

Cloud is EXCLUSIVE when enabled (explicit opt-in wins; failures are loud,
never a silent substitution). Without it, the platform endpoint comes first
and the sidecar's own local model is the fallback. No backend -> None (503).
"""
    if config.cloud_stt_enabled and config.cloud_stt_base_url \
            and config.cloud_stt_api_key and config.cloud_stt_model:
        return CloudSTT(base_url=config.cloud_stt_base_url,
                        api_key=config.cloud_stt_api_key,
                        model=config.cloud_stt_model)
    backends: list = []
    if config.moldesign_token and not config.host_secret:
        backends.append(MolDesignWhisper(
            bridge.client, config.moldesign_token,
            ensure_contract=lambda: bridge.ensure_contract('platform-actions/1')))
    if faster_whisper_available():
        backends.append(LocalWhisperSTT(config.whisper_model))
    if not backends:
        return None
    return backends[0] if len(backends) == 1 else ChainSTT(backends)


def build_server(config: MolChatConfig | None = None,
                 *, ui_dist: str = "") -> ServedSidecar:
    """Wire every sidecar dependency from config (no sockets opened)."""
    config = config or load_config()
    if config.host_secret:
        secret = config.host_secret.encode("utf-8")
        token: str | None = None  # hosted mode: the host mints sessions
    else:
        secret = standalone_secret()
        token = mint(secret, "operador-local",
                     {"read", "chat", "plan", "approve", "cancel", "transcribe"},
                     config.session_ttl_s)
    registry = build_registry(config)
    bridge = MolDesignBridge(
        base_url=config.moldesign_base_url,
        token=None if config.host_secret else config.moldesign_token,
        allow_remote=config.moldesign_allow_remote, require_contract=True)
    store = ExecutionStore(config.exec_store)
    state = ServerState(
        secret=secret, registry=registry,
        memory=MemoryStore(config.memory_file),
        backend=PlatformBackend(bridge),
        allowed_origins=config.allowed_origins,
        provider_id=config.provider,
        executions=ExecutionManager(bridge, store),
        stt=_build_stt(config, bridge),
        hosted=bool(config.host_secret),
        bridge=bridge,
    )
    found = find_ui_dist(ui_dist or config.ui_dist)
    app = create_app(state, ui_dist=found)
    return ServedSidecar(app=app, state=state, bridge=bridge, secret=secret,
                         token=token, ui_dist=found)


def run(host: str = "127.0.0.1", port: int = DEFAULT_PORT,
        *, ui_dist: str = "") -> int:
    """Serve forever (sync entry; fails loudly inside a running loop)."""
    return asyncio.run(serve_async(host, port, ui_dist=ui_dist))


async def serve_async(host: str = "127.0.0.1", port: int = DEFAULT_PORT,
                      *, ui_dist: str = "") -> int:
    """Serve forever. Prints the URL (and the standalone token) once."""
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit(
            "falta el extra 'server': pip install 'moldesign-molchat[server]'") from exc
    validate_bind_host(host)
    if not 0 <= port <= 65535:
        raise ValueError(f"puerto no válido: {port}")
    served = build_server(ui_dist=ui_dist)
    print(f"MolChat sidecar en http://{host}:{port or '(efímero)'} "
          f"({'con UI' if served.ui_dist else 'solo API; construye ui/ para la interfaz'})",
          flush=True)
    if served.token is not None:
        print("Sesión standalone (se muestra una sola vez; no la registres):", flush=True)
        print(f"  {served.token}", flush=True)
    else:
        print("Modo host: las sesiones las acuña MolDesign (MOLCHAT_HOST_SECRET).",
              flush=True)
    server = uvicorn.Server(uvicorn.Config(
        served.app, host=host, port=port or 0, log_level="warning"))
    try:
        await server.serve()
    finally:
        await served.bridge.__aexit__(None, None, None)
    return 0
