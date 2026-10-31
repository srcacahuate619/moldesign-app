"""Centralized environment configuration.

This is the only module that reads ``os.environ`` (PLAN Fase 1, tarea 1.6).
Every other module receives explicit parameters or a :class:`MolChatConfig`.
Secrets live in memory only; they are never written to disk by this package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Mapping

HACKATHON_PROFILE = "hackathon"
DEFAULT_PROFILE = "default"
PROFILES = (HACKATHON_PROFILE, DEFAULT_PROFILE)


def _default_consents_file() -> Path:
    return Path.home() / ".molchat" / "consents.json"


@dataclass(frozen=True)
class MolChatConfig:
    """All settings, from environment with safe defaults."""

    moldesign_base_url: str = "http://127.0.0.1:8000"
    moldesign_token: str | None = None
    moldesign_allow_remote: bool = False
    profile: str = DEFAULT_PROFILE
    provider: str | None = None  # active provider override (else profile default)
    model_api_key: str | None = None  # Meta Model API
    meta_model: str = "muse-spark-1.3"
    meta_reasoning_effort: str = "medium"
    openai_compat_base_url: str = ""
    openai_compat_api_key: str | None = None
    openai_compat_model: str = ""
    openai_compat_json_mode: str = "schema"
    openai_compat_disable_thinking: bool = False
    llama_server_url: str = "http://127.0.0.1:8400/v1"
    llama_server_model: str = ""
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    anthropic_api_key: str | None = None
    claude_model: str = "claude-haiku-4-5-20251001"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    #: Claves de los proveedores del catálogo. En modo alojado no se usan: llegan
    #: por petición desde MolDesign, donde están guardadas por cuenta.
    openai_api_key: str | None = None
    deepseek_api_key: str | None = None
    nvidia_api_key: str | None = None
    cloud_stt_enabled: bool = False
    cloud_stt_base_url: str = ""
    cloud_stt_api_key: str | None = None
    cloud_stt_model: str = ""
    consents_file: Path = field(default_factory=_default_consents_file)
    offline: bool = False
    host_secret: str | None = None  # shared HMAC secret with the MolDesign host
    allowed_origins: tuple[str, ...] = ()  # extra UI origins besides loopback
    session_ttl_s: int = 3600  # standalone session lifetime
    memory_file: Path = field(default_factory=lambda: Path.home() / ".molchat" / "sidecar_memory.db")
    exec_store: Path = field(default_factory=lambda: Path.home() / ".molchat" / "sidecar_exec.db")
    ui_dist: str = ""  # built UI directory (else ./ui/dist, else API-only)
    whisper_model: str = "tiny"  # local faster-whisper fallback model

    def redacted(self) -> dict[str, str]:
        """Config summary safe to print: secrets become set/unset, never values."""
        def secret(value: str | None) -> str:
            return "set" if value else "unset"

        return {
            "moldesign_base_url": self.moldesign_base_url,
            "moldesign_token": secret(self.moldesign_token),
            "moldesign_allow_remote": str(self.moldesign_allow_remote),
            "profile": self.profile,
            "provider": self.provider or "(profile default)",
            "model_api_key": secret(self.model_api_key),
            "meta_model": self.meta_model,
            "meta_reasoning_effort": self.meta_reasoning_effort,
            "openai_compat_base_url": self.openai_compat_base_url or "(unset)",
            "openai_compat_api_key": secret(self.openai_compat_api_key),
            "openai_compat_model": self.openai_compat_model or "(unset)",
            "openai_compat_json_mode": self.openai_compat_json_mode,
            "openai_compat_disable_thinking": str(self.openai_compat_disable_thinking),
            "llama_server_url": self.llama_server_url,
            "llama_server_model": self.llama_server_model or "(unset)",
            "ollama_url": self.ollama_url,
            "ollama_model": self.ollama_model or "(unset)",
            "anthropic_api_key": secret(self.anthropic_api_key),
            "claude_model": self.claude_model,
            "gemini_api_key": secret(self.gemini_api_key),
            "gemini_model": self.gemini_model,
            "openai_api_key": secret(self.openai_api_key),
            "deepseek_api_key": secret(self.deepseek_api_key),
            "nvidia_api_key": secret(self.nvidia_api_key),
            "cloud_stt_enabled": str(self.cloud_stt_enabled),
            "cloud_stt_base_url": self.cloud_stt_base_url or "(unset)",
            "cloud_stt_api_key": secret(self.cloud_stt_api_key),
            "cloud_stt_model": self.cloud_stt_model or "(unset)",
            "consents_file": str(self.consents_file),
            "offline": str(self.offline),
            "host_secret": secret(self.host_secret),
            "allowed_origins": ",".join(self.allowed_origins) or "(loopback only)",
            "session_ttl_s": str(self.session_ttl_s),
            "memory_file": str(self.memory_file),
            "exec_store": str(self.exec_store),
            "ui_dist": self.ui_dist or "(auto)",
            "whisper_model": self.whisper_model,
        }


def load_config(env: Mapping[str, str] | None = None) -> MolChatConfig:
    """Build config from ``env`` (defaults to ``os.environ``)."""
    source = env if env is not None else os.environ

    def text(name: str, default: str = "") -> str:
        return (source.get(name, default) or "").strip()

    def secret(name: str) -> str | None:
        return text(name) or None

    def flag(name: str) -> bool:
        return text(name) == "1"

    # Producto: `default`. El perfil `hackathon` (sólo Meta remoto) es una política de
    # concurso y debe pedirse a mano con MOLCHAT_PROFILE=hackathon.
    profile = text("MOLCHAT_PROFILE", DEFAULT_PROFILE)
    if profile not in PROFILES:
        raise ValueError(f"MOLCHAT_PROFILE debe ser uno de {list(PROFILES)}: {profile!r}")

    consents = text("MOLCHAT_CONSENTS_FILE")
    memory_file = text("MOLCHAT_MEMORY_FILE")
    exec_store = text("MOLCHAT_EXEC_STORE")
    origins = tuple(o for o in
                    (part.strip() for part in text("MOLCHAT_ALLOWED_ORIGINS").split(","))
                    if o)
    try:
        session_ttl = int(text("MOLCHAT_SESSION_TTL_S", "3600"))
    except ValueError as exc:
        raise ValueError("MOLCHAT_SESSION_TTL_S debe ser un entero") from exc
    if session_ttl <= 0:
        raise ValueError("MOLCHAT_SESSION_TTL_S debe ser positivo")
    return MolChatConfig(
        moldesign_base_url=text("MOLDESIGN_BASE_URL", "http://127.0.0.1:8000"),
        moldesign_token=secret("MOLDESIGN_TOKEN"),
        moldesign_allow_remote=flag("MOLDESIGN_ALLOW_REMOTE"),
        profile=profile,
        provider=text("MOLCHAT_PROVIDER") or None,
        model_api_key=secret("MODEL_API_KEY"),
        meta_model=text("META_MODEL", "muse-spark-1.3"),
        meta_reasoning_effort=text("META_REASONING_EFFORT", "medium"),
        openai_compat_base_url=text("OPENAI_COMPAT_BASE_URL"),
        openai_compat_api_key=secret("OPENAI_COMPAT_API_KEY"),
        openai_compat_model=text("OPENAI_COMPAT_MODEL"),
        openai_compat_json_mode=text("OPENAI_COMPAT_JSON_MODE", "schema"),
        openai_compat_disable_thinking=flag("OPENAI_COMPAT_DISABLE_THINKING"),
        llama_server_url=text("LLAMA_SERVER_URL", "http://127.0.0.1:8400/v1"),
        llama_server_model=text("LLAMA_SERVER_MODEL"),
        ollama_url=text("OLLAMA_URL", "http://127.0.0.1:11434"),
        ollama_model=text("OLLAMA_MODEL"),
        anthropic_api_key=secret("ANTHROPIC_API_KEY"),
        claude_model=text("CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
        gemini_api_key=secret("GEMINI_API_KEY"),
        gemini_model=text("GEMINI_MODEL", "gemini-2.5-flash"),
        openai_api_key=secret("OPENAI_API_KEY"),
        deepseek_api_key=secret("DEEPSEEK_API_KEY"),
        nvidia_api_key=secret("NVIDIA_API_KEY"),
        cloud_stt_enabled=flag("MOLCHAT_CLOUD_STT"),
        cloud_stt_base_url=text("MOLCHAT_CLOUD_STT_URL"),
        cloud_stt_api_key=secret("MOLCHAT_CLOUD_STT_KEY"),
        cloud_stt_model=text("MOLCHAT_CLOUD_STT_MODEL"),
        consents_file=Path(consents) if consents else _default_consents_file(),
        offline=flag("MOLCHAT_OFFLINE"),
        host_secret=secret("MOLCHAT_HOST_SECRET"),
        allowed_origins=origins,
        session_ttl_s=session_ttl,
        memory_file=Path(memory_file) if memory_file else Path.home() / ".molchat" / "sidecar_memory.db",
        exec_store=Path(exec_store) if exec_store else Path.home() / ".molchat" / "sidecar_exec.db",
        ui_dist=text("MOLCHAT_UI_DIST"),
        whisper_model=text("MOLCHAT_WHISPER_MODEL", "tiny"),
    )
