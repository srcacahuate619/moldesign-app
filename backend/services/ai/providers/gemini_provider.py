from __future__ import annotations

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

_GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(AIProvider):
    id = "gemini"
    name = "Gemini (Google)"
    description = "Google Gemini API. Requiere GEMINI_API_KEY. Tier gratuito: ~1500 req/día."

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        if not self._config.model:
            self._config.model = "gemini-2.5-flash"
        if not self._config.temperature:
            self._config.temperature = 0.5
        if not self._config.max_tokens:
            self._config.max_tokens = 4096

    def validate_config(self) -> tuple[bool, str]:
        if not self._config.api_key:
            return False, "GEMINI_API_KEY no configurada"
        return True, "OK"

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name=self.name,
            description=self.description,
            requires_api_key=True,
            requires_base_url=False,
            default_model="gemini-2.5-flash",
            configured=bool(self._config.api_key),
        )

    async def health_check(self) -> HealthCheckResult:
        ok, msg = self.validate_config()
        if not ok:
            return HealthCheckResult(status=HealthStatus.NO_API_KEY, message=msg)

        start = time.monotonic()
        url = f"{_GEMINI_API_BASE}/{self._config.model}:generateContent"
        headers = {"x-goog-api-key": self._config.api_key}
        payload = {
            "contents": [{"parts": [{"text": "hi"}]}],
            "generationConfig": {"maxOutputTokens": 1},
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
                if resp.status_code == 403:
                    return HealthCheckResult(
                        status=HealthStatus.NO_TOKENS,
                        message=f"API key sin permisos o bloqueada: {body}",
                        latency_ms=round(elapsed, 1),
                    )
                if resp.status_code == 429:
                    return HealthCheckResult(
                        status=HealthStatus.NO_TOKENS,
                        message="Quota excedida: HTTP 429",
                        latency_ms=round(elapsed, 1),
                    )
                return HealthCheckResult(
                    status=HealthStatus.CONNECTION_ERROR,
                    message=f"Error HTTP {resp.status_code}",
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
            yield "Error: GEMINI_API_KEY no configurada"
            return

        system_prompt = next((m["content"] for m in messages if m.get("role") == "system"), "")

        contents = []
        current_role = None
        current_parts = []

        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "system":
                continue
            if role != current_role and current_parts:
                contents.append({"role": _gemini_role(current_role), "parts": [{"text": "\n".join(current_parts)}]})
                current_parts = []
            current_role = role
            current_parts.append(content)

        if current_parts and current_role:
            contents.append({"role": _gemini_role(current_role), "parts": [{"text": "\n".join(current_parts)}]})

        if not contents:
            yield "Error: No hay mensajes para enviar"
            return

        url = f"{_GEMINI_API_BASE}/{self._config.model}:generateContent"
        headers = {"x-goog-api-key": self._config.api_key}
        payload = {
            "contents": contents,
            "system_instruction": {"parts": [{"text": system_prompt}]} if system_prompt else None,
            "generationConfig": {
                "temperature": self._config.temperature,
                "maxOutputTokens": self._config.max_tokens,
            },
        }

        if stream:
            url = f"{_GEMINI_API_BASE}/{self._config.model}:streamGenerateContent?alt=sse"
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream("POST", url, json=payload, headers=headers) as response:
                        if response.status_code != 200:
                            yield f"Error Gemini ({response.status_code})"
                            return
                        async for line in response.aiter_lines():
                            if not line or line.startswith(":"):
                                continue
                            if line.startswith("data: "):
                                try:
                                    import json as j
                                    data = j.loads(line[6:])
                                    candidates = data.get("candidates", [])
                                    if candidates:
                                        for p in candidates[0].get("content", {}).get("parts", []):
                                            yield p.get("text", "")
                                except Exception:
                                    pass
            except Exception as e:
                yield f"Error en streaming Gemini: {redactar_secretos(e)[:100]}"
        else:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code != 200:
                        yield f"Error Gemini ({resp.status_code})"
                        return
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text = "".join(p.get("text", "") for p in parts)
                        if text:
                            yield text
                            return
                    yield "Error: Gemini no generó respuesta."
            except Exception as e:
                yield f"Error en Gemini API: {redactar_secretos(e)[:100]}"

    async def list_models(self) -> list[str]:
        return ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash", "gemini-1.5-pro"]


def _gemini_role(role: str | None) -> str:
    if role == "assistant":
        return "model"
    return "user"
