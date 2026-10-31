"""Anthropic Claude planner over HTTP (no SDK dependency).

Reimplemented from the behavior of MolDesign's ``claude_provider.py``
(defaults, health semantics, system-prompt handling) without its
``anthropic`` SDK: plain ``httpx`` against the public Messages API, in the
house provider shape. Remote-only; the hackathon profile keeps it disabled
(§6.1.1: future compatibility, never the presented build).
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator

import httpx

from ..config import load_config
from ..plan import Plan
from .base import (
    CatalogEntry,
    ChatEvent,
    HealthCheckResult,
    HealthStatus,
    ProviderConfig,
    ProviderError,
    ProviderInfo,
    TurnContext,
    plan_from_content,
    read_only_catalog,
)

CLAUDE_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_API_BASE = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_PLANNER_SYSTEM = (
    "Eres un planificador de química computacional. Propón SOLO una secuencia "
    "de herramientas enumeradas en el catálogo. Nunca inventes IDs, SMILES, "
    "datos de receptores ni resultados. Devuelve el plan como JSON con la "
    "estructura indicada."
)


class ClaudeProvider:
    """Claude planner behind the LLMProvider port (remote)."""

    id = "claude"
    locality = "remote"

    def __init__(self, *, api_key: str | None = None, model: str | None = None,
                 client: httpx.AsyncClient | None = None) -> None:
        config = load_config()
        self.config = ProviderConfig(
            api_key=api_key if api_key is not None else (config.anthropic_api_key or ""),
            base_url=CLAUDE_API_BASE,
            model=model or config.claude_model or DEFAULT_MODEL,
        )
        self._client = client
        self._owns_client = client is None

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0, trust_env=False)
        return self._client

    async def __aenter__(self) -> "ClaudeProvider":
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name="Claude (Anthropic)",
            description="Planificador remoto opcional (perfil default).",
            requires_api_key=True,
            requires_base_url=False,
            default_base_url=CLAUDE_API_BASE,
            default_model=DEFAULT_MODEL,
        )

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.config.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json"}

    async def health(self) -> HealthCheckResult:
        if not self.config.api_key:
            return HealthCheckResult(
                status=HealthStatus.NO_API_KEY,
                message="Falta ANTHROPIC_API_KEY; no se enviará nada a Anthropic.")
        start = time.monotonic()
        try:
            response = await self._http.post(
                CLAUDE_URL,
                json={"model": self.config.model, "max_tokens": 1,
                      "messages": [{"role": "user", "content": "hi"}]},
                headers=self._headers())
        except (httpx.RequestError, ValueError) as exc:
            return HealthCheckResult(
                status=HealthStatus.CONNECTION_ERROR,
                message=f"No se pudo contactar a Anthropic: {exc}",
                latency_ms=(time.monotonic() - start) * 1000)
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        if response.status_code == 200:
            return HealthCheckResult(
                status=HealthStatus.OK, message="Anthropic responde.",
                latency_ms=elapsed_ms)
        if response.status_code == 401:
            return HealthCheckResult(
                status=HealthStatus.NO_API_KEY,
                message="Anthropic rechazó la clave (HTTP 401).",
                latency_ms=elapsed_ms)
        if response.status_code == 429:
            return HealthCheckResult(
                status=HealthStatus.NO_TOKENS,
                message="Cuota excedida (HTTP 429).", latency_ms=elapsed_ms)
        return HealthCheckResult(
            status=HealthStatus.CONNECTION_ERROR,
            message=f"Anthropic devolvió HTTP {response.status_code}.",
            latency_ms=elapsed_ms)

    def _payload(self, goal: str, catalog: list[CatalogEntry] | None) -> dict[str, Any]:
        safe_tools = read_only_catalog(catalog)
        return {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "system": _PLANNER_SYSTEM,
            "messages": [{"role": "user", "content": json.dumps(
                {"goal": goal, "capabilities": safe_tools}, ensure_ascii=False)}],
        }

    @staticmethod
    def _text_of(payload: dict[str, Any]) -> str:
        blocks = payload.get("content") or []
        texts = [b.get("text", "") for b in blocks if isinstance(b, dict)]
        combined = "".join(texts).strip()
        if not combined:
            raise ProviderError("Claude no devolvió texto.")
        return combined

    async def plan(self, goal: str, catalog: list[CatalogEntry] | None = None) -> Plan:
        if not self.config.api_key:
            raise ValueError("Falta ANTHROPIC_API_KEY; no se enviará el objetivo")
        try:
            response = await self._http.post(
                CLAUDE_URL, json=self._payload(goal, catalog),
                headers=self._headers())
            if response.status_code >= 400 or response.is_redirect:
                raise ProviderError(f"Anthropic devolvió HTTP {response.status_code}.")
            content = self._text_of(response.json())
            allowed = [t["name"] for t in read_only_catalog(catalog)]
            return plan_from_content(content, goal, f"claude:{self.config.model}",
                                      allowed)
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("Claude no entregó un plan válido.") from exc

    async def chat(self, turn: TurnContext) -> AsyncIterator[ChatEvent]:
        if not self.config.api_key:
            raise ValueError("Falta ANTHROPIC_API_KEY; no se enviará nada")
        messages = turn.messages or [{"role": "user", "content": turn.text}]
        system = next((m["content"] for m in messages if m.get("role") == "system"), None)
        exchange = [{"role": m["role"], "content": m["content"]} for m in messages
                    if m.get("role") in ("user", "assistant")]
        if not exchange:
            raise ProviderError("Claude necesita al menos un turno user/assistant.")
        body: dict[str, Any] = {"model": self.config.model,
                                "max_tokens": self.config.max_tokens,
                                "temperature": self.config.temperature,
                                "messages": exchange}
        if system:
            body["system"] = system
        try:
            response = await self._http.post(CLAUDE_URL, json=body,
                                             headers=self._headers())
            if response.status_code >= 400 or response.is_redirect:
                raise ProviderError(f"Anthropic devolvió HTTP {response.status_code}.")
            content = self._text_of(response.json())
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("Claude no entregó respuesta de chat.") from exc
        yield ChatEvent(type="token", text=content)
        yield ChatEvent(type="done", done=True)
