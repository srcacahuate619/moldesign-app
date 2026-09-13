from __future__ import annotations

import json
import time
from typing import AsyncIterator

import httpx

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


class OpenAIProvider(AIProvider):
    id = "openai"
    name = "Cloud (OpenAI/Groq)"
    description = (
        "Compatible con OpenAI, Groq (gratis, 500+ tok/s), DeepSeek, Together, vLLM, etc. "
        "Configurá base_url + api_key + model."
    )

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        if not self._config.base_url:
            self._config.base_url = "https://api.groq.com/openai/v1"
        if not self._config.model:
            self._config.model = "llama-3.1-8b-instant"
        if not self._config.temperature:
            self._config.temperature = 0.5
        if not self._config.max_tokens:
            self._config.max_tokens = 4096

    def validate_config(self) -> tuple[bool, str]:
        if not self._config.api_key:
            return False, "API key no configurada"
        return True, "OK"

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name=self.name,
            description=self.description,
            requires_api_key=True,
            requires_base_url=True,
            default_base_url="https://api.openai.com/v1",
            default_model="gpt-4o-mini",
            configured=bool(self._config.api_key),
        )

    async def health_check(self) -> HealthCheckResult:
        ok, msg = self.validate_config()
        if not ok:
            return HealthCheckResult(status=HealthStatus.NO_API_KEY, message=msg)

        start = time.monotonic()
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._config.model,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload, headers=headers)
                elapsed = (time.monotonic() - start) * 1000
                if resp.status_code == 200:
                    return HealthCheckResult(
                        status=HealthStatus.OK,
                        message="API key válida y con saldo disponible",
                        latency_ms=round(elapsed, 1),
                    )
                body = resp.text[:200]
                if resp.status_code == 401:
                    return HealthCheckResult(
                        status=HealthStatus.NO_TOKENS,
                        message=f"API key inválida o revocada: {body}",
                        latency_ms=round(elapsed, 1),
                    )
                if resp.status_code in (402, 429):
                    return HealthCheckResult(
                        status=HealthStatus.NO_TOKENS,
                        message=f"Sin saldo disponible o quota excedida: HTTP {resp.status_code}",
                        latency_ms=round(elapsed, 1),
                    )
                return HealthCheckResult(
                    status=HealthStatus.CONNECTION_ERROR,
                    message=f"Error inesperado HTTP {resp.status_code}: {body}",
                    latency_ms=round(elapsed, 1),
                )
        except httpx.TimeoutException:
            elapsed = (time.monotonic() - start) * 1000
            return HealthCheckResult(
                status=HealthStatus.CONNECTION_ERROR,
                message=f"Timeout conectando a {redactar_secretos(self._config.base_url)}",
                latency_ms=round(elapsed, 1),
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return HealthCheckResult(
                status=HealthStatus.CONNECTION_ERROR,
                message=f"Error de conexión: {redactar_secretos(e)[:120]}",
                latency_ms=round(elapsed, 1),
            )

    async def chat(
        self,
        messages: list[dict[str, str]],
        stream: bool = False,
    ) -> AsyncIterator[str]:
        if not self._config.api_key:
            yield "Error: API key no configurada"
            return

        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._config.model,
            "messages": messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "stream": stream,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                if stream:
                    async with client.stream("POST", url, json=payload, headers=headers) as response:
                        if response.status_code != 200:
                            body = await response.aread()
                            yield f"Error API ({response.status_code}): {body[:200].decode()}"
                            return
                        async for line in response.aiter_lines():
                            if not line or line.startswith(":") or line == "data: [DONE]":
                                continue
                            if line.startswith("data: "):
                                try:
                                    data = json.loads(line[6:])
                                    choices = data.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            yield content
                                except json.JSONDecodeError:
                                    pass
                else:
                    payload["stream"] = False
                    resp = await client.post(url, json=payload, headers=headers, timeout=120.0)
                    if resp.status_code != 200:
                        yield f"Error API ({resp.status_code}): {resp.text[:200]}"
                        return
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        if content:
                            yield content
                            return
                    yield "Error: El proveedor no generó respuesta."
        except Exception as e:
            yield (
                f"Error conectando con {redactar_secretos(self._config.base_url)}: "
                f"{redactar_secretos(e)[:100]}"
            )

    async def list_models(self) -> list[str]:
        if not self._config.api_key or not self._config.base_url:
            return [self._config.model]
        try:
            url = f"{self._config.base_url.rstrip('/')}/models"
            headers = {"Authorization": f"Bearer {self._config.api_key}"}
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return [m["id"] for m in resp.json().get("data", [])]
        except Exception:
            pass
        return [self._config.model]
