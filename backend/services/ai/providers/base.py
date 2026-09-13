from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator


class HealthStatus(Enum):
    OK = "ok"
    NO_API_KEY = "no_api_key"
    NO_TOKENS = "no_tokens"
    CONNECTION_ERROR = "connection_error"
    NOT_AVAILABLE = "not_available"
    #: No se preguntó. El `health_check` de un proveedor cloud es una llamada
    #: real a su API, así que sondear un destino sin autorizar es exactamente lo
    #: que el consentimiento impide. Es un estado y no un fallo: no se sabe si
    #: funciona, y decir otra cosa sería inventarlo.
    SIN_CONSENTIMIENTO = "sin_consentimiento"


@dataclass
class HealthCheckResult:
    status: HealthStatus = HealthStatus.NOT_AVAILABLE
    message: str = ""
    latency_ms: float = 0.0


class StartupMode(Enum):
    AUTO_START = "auto_start"
    NOTIFY_FALLBACK = "notify_fallback"
    MANUAL_ONLY = "manual_only"


@dataclass
class ProviderInfo:
    id: str
    name: str
    description: str
    requires_api_key: bool
    requires_base_url: bool
    default_base_url: str = ""
    default_model: str = ""
    available_models: list[str] = field(default_factory=list)
    env_key: str = ""
    env_url: str = ""
    configured: bool = False


@dataclass
class ProviderConfig:
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.5
    max_tokens: int = 4096
    extra: dict[str, Any] = field(default_factory=dict)


class AIProvider(ABC):
    id: str = ""
    name: str = ""
    description: str = ""

    def __init__(self, config: ProviderConfig | None = None):
        self._config = config or ProviderConfig()

    @property
    def config(self) -> ProviderConfig:
        return self._config

    @config.setter
    def config(self, value: ProviderConfig):
        self._config = value

    @abstractmethod
    def validate_config(self) -> tuple[bool, str]:
        pass

    @abstractmethod
    def get_info(self) -> ProviderInfo:
        pass

    async def health_check(self) -> HealthCheckResult:
        """
        Verifica si el provider realmente funciona (API key válida, tokens disponibles).
        Por defecto delega a validate_config. Providers cloud sobreescriben para
        hacer una llamada real (ej: list_models con 1 token).
        """
        ok, msg = self.validate_config()
        if not ok:
            return HealthCheckResult(
                status=HealthStatus.NO_API_KEY,
                message=msg,
            )
        return HealthCheckResult(
            status=HealthStatus.OK,
            message="Configuración válida",
        )

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        stream: bool = False,
    ) -> AsyncIterator[str]:
        yield ""

    @abstractmethod
    async def list_models(self) -> list[str]:
        return []
