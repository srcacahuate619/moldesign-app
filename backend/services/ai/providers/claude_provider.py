from __future__ import annotations

import time
from typing import AsyncIterator

from services.ai.providers.base import (
    AIProvider,
    HealthCheckResult,
    HealthStatus,
    ProviderConfig,
    ProviderInfo,
)
from services.ai.redaccion import redactar_secretos
from utils.logger import get_logger

log = get_logger(__name__)


class ClaudeProvider(AIProvider):
    id = "claude"
    name = "Claude (Anthropic)"
    description = "Anthropic Claude API. Requiere ANTHROPIC_API_KEY. Modelo default: claude-haiku-4-5."

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        if not self._config.model:
            self._config.model = "claude-haiku-4-5-20251001"
        if not self._config.temperature:
            self._config.temperature = 0.5
        if not self._config.max_tokens:
            self._config.max_tokens = 4096

    def validate_config(self) -> tuple[bool, str]:
        if not self._config.api_key:
            return False, "ANTHROPIC_API_KEY no configurada"
        return True, "OK"

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name=self.name,
            description=self.description,
            requires_api_key=True,
            requires_base_url=False,
            default_model="claude-haiku-4-5-20251001",
            configured=bool(self._config.api_key),
        )

    async def health_check(self) -> HealthCheckResult:
        ok, msg = self.validate_config()
        if not ok:
            return HealthCheckResult(status=HealthStatus.NO_API_KEY, message=msg)

        import anthropic
        start = time.monotonic()
        try:
            client = anthropic.AsyncAnthropic(api_key=self._config.api_key)
            response = await client.messages.create(
                model=self._config.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            elapsed = (time.monotonic() - start) * 1000
            return HealthCheckResult(
                status=HealthStatus.OK,
                message="API key válida y con saldo disponible",
                latency_ms=round(elapsed, 1),
            )
        except anthropic.AuthenticationError as e:
            elapsed = (time.monotonic() - start) * 1000
            return HealthCheckResult(
                status=HealthStatus.NO_TOKENS,
                message=f"API key inválida: {redactar_secretos(e)[:120]}",
                latency_ms=round(elapsed, 1),
            )
        except anthropic.RateLimitError as e:
            elapsed = (time.monotonic() - start) * 1000
            return HealthCheckResult(
                status=HealthStatus.NO_TOKENS,
                message=f"Límite de velocidad o saldo insuficiente: {redactar_secretos(e)[:120]}",
                latency_ms=round(elapsed, 1),
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return HealthCheckResult(
                status=HealthStatus.CONNECTION_ERROR,
                message=f"Error conectando con Anthropic: {redactar_secretos(e)[:120]}",
                latency_ms=round(elapsed, 1),
            )

    async def chat(
        self,
        messages: list[dict[str, str]],
        stream: bool = False,
    ) -> AsyncIterator[str]:
        import anthropic

        if not self._config.api_key:
            yield "Error: ANTHROPIC_API_KEY no configurada"
            return

        try:
            client = anthropic.AsyncAnthropic(api_key=self._config.api_key)
            response = await client.messages.create(
                model=self._config.model,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
                messages=[m for m in messages if m.get("role") != "system"],
                system=next((m["content"] for m in messages if m.get("role") == "system"), None),
            )
            content = response.content[0].text.strip() if response.content else ""
            if content:
                yield content
            else:
                yield "Error: Claude no generó respuesta."
        except Exception as e:
            log.warning("claude_chat_failed", error=redactar_secretos(e))
            yield f"Error en Claude API: {redactar_secretos(e)[:120]}"

    async def list_models(self) -> list[str]:
        return [
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-5-20251001",
            "claude-3-5-haiku-20241022",
            "claude-3-5-sonnet-20241022",
        ]
