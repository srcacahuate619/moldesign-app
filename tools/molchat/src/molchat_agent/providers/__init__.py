"""LLM providers: local and cloud planners behind one port."""

from .base import (
    CatalogEntry,
    ChatEvent,
    HealthCheckResult,
    HealthStatus,
    LLMProvider,
    ProviderConfig,
    ProviderDisabled,
    ProviderError,
    ProviderInfo,
    TurnContext,
    plan_from_content,
    read_only_catalog,
    readonly_plan_schema,
)
from .claude import ClaudeProvider
from .fake import FakeProvider
from .gemini import GeminiProvider
from .local_http import LlamaServerProvider, OllamaProvider
from .meta import MetaProvider
from .openai_compatible import OpenAICompatibleProvider
from .registry import (
    CONTENT_SCOPE,
    HACKATHON_REMOTE_ALLOWLIST,
    ConsentDenied,
    ConsentStore,
    Destination,
    ProviderRegistry,
    ProviderStatus,
    UnknownProviderError,
    build_registry,
    resolve_destination,
)

__all__ = [
    "CONTENT_SCOPE",
    "CatalogEntry", "ChatEvent", "ClaudeProvider", "ConsentDenied", "ConsentStore", "Destination",
    "FakeProvider", "GeminiProvider", "HACKATHON_REMOTE_ALLOWLIST",
    "HealthCheckResult",
    "HealthStatus", "LLMProvider", "LlamaServerProvider", "MetaProvider",
    "OllamaProvider", "OpenAICompatibleProvider", "ProviderConfig", "ProviderDisabled",
    "ProviderError", "ProviderInfo", "ProviderRegistry", "ProviderStatus", "TurnContext",
    "UnknownProviderError", "build_registry", "plan_from_content",
    "read_only_catalog", "readonly_plan_schema", "resolve_destination",
]
