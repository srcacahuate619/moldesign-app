"""Google Gemini planner over HTTP (same transport as the internal one).

Reimplemented from the behavior of MolDesign's ``gemini_provider.py``
(defaults, health semantics, role mapping with consecutive merging, header
auth) without its MolDesign couplings. One deliberate delta: ``plan()``
asks for ``responseMimeType: application/json`` (documented Gemini parameter)
so the read-only plan parses reliably. Remote-only; disabled in the
hackathon profile (§6.1.1).
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

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.5-flash"

_PLANNER_SYSTEM = (
    "Eres un planificador de química computacional. Propón SOLO una secuencia "
    "de herramientas enumeradas en el catálogo. Nunca inventes IDs, SMILES, "
    "datos de receptores ni resultados. Devuelve el plan como JSON con la "
    "estructura indicada."
)


def _gemini_role(role: str | None) -> str:
    return "model" if role == "assistant" else "user"


def _to_contents(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, Any]]]:
    """System prompt aside; consecutive same-role turns merged (internal rule)."""
    system = next((m["content"] for m in messages if m.get("role") == "system"), "")
    contents: list[dict[str, Any]] = []
    current_role: str | None = None
    current_parts: list[str] = []
    for message in messages:
        role = message.get("role", "")
        if role == "system":
            continue
        if role != current_role and current_parts:
            contents.append({"role": _gemini_role(current_role),
                             "parts": [{"text": "\n".join(current_parts)}]})
            current_parts = []
        current_role = role
        current_parts.append(message.get("content", ""))
    if current_parts and current_role:
        contents.append({"role": _gemini_role(current_role),
                         "parts": [{"text": "\n".join(current_parts)}]})
    return system, contents


class GeminiProvider:
    """Gemini planner behind the LLMProvider port (remote)."""

    id = "gemini"
    locality = "remote"

    def __init__(self, *, api_key: str | None = None, model: str | None = None,
                 client: httpx.AsyncClient | None = None) -> None:
        config = load_config()
        self.config = ProviderConfig(
            api_key=api_key if api_key is not None else (config.gemini_api_key or ""),
            base_url=GEMINI_API_BASE,
            model=model or config.gemini_model or DEFAULT_MODEL,
        )
        self._client = client
        self._owns_client = client is None

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0, trust_env=False)
        return self._client

    async def __aenter__(self) -> "GeminiProvider":
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name="Gemini (Google)",
            description="Planificador remoto opcional (perfil default).",
            requires_api_key=True,
            requires_base_url=False,
            default_base_url=GEMINI_API_BASE,
            default_model=DEFAULT_MODEL,
        )

    def _url(self) -> str:
        return f"{GEMINI_API_BASE}/{self.config.model}:generateContent"

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self.config.api_key,
                "Content-Type": "application/json"}

    async def health(self) -> HealthCheckResult:
        if not self.config.api_key:
            return HealthCheckResult(
                status=HealthStatus.NO_API_KEY,
                message="Falta GEMINI_API_KEY; no se enviará nada a Google.")
        start = time.monotonic()
        try:
            response = await self._http.post(
                self._url(),
                json={"contents": [{"parts": [{"text": "hi"}]}],
                      "generationConfig": {"maxOutputTokens": 1}},
                headers=self._headers())
        except (httpx.RequestError, ValueError) as exc:
            return HealthCheckResult(
                status=HealthStatus.CONNECTION_ERROR,
                message=f"No se pudo contactar a Google: {exc}",
                latency_ms=(time.monotonic() - start) * 1000)
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        if response.status_code == 200:
            return HealthCheckResult(
                status=HealthStatus.OK, message="Google responde.",
                latency_ms=elapsed_ms)
        if response.status_code == 403:
            return HealthCheckResult(
                status=HealthStatus.NO_TOKENS,
                message="Clave sin permisos o bloqueada (HTTP 403).",
                latency_ms=elapsed_ms)
        if response.status_code == 429:
            return HealthCheckResult(
                status=HealthStatus.NO_TOKENS,
                message="Cuota excedida (HTTP 429).", latency_ms=elapsed_ms)
        return HealthCheckResult(
            status=HealthStatus.CONNECTION_ERROR,
            message=f"Google devolvió HTTP {response.status_code}.",
            latency_ms=elapsed_ms)

    @staticmethod
    def _text_of(payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates", [])
        parts = (candidates[0].get("content", {}).get("parts", [])
                 if candidates else [])
        combined = "".join(p.get("text", "") for p in parts).strip()
        if not combined:
            raise ProviderError("Gemini no devolvió texto.")
        return combined

    def _payload(self, goal: str, catalog: list[CatalogEntry] | None) -> dict[str, Any]:
        safe_tools = read_only_catalog(catalog)
        return {
            "contents": [{"role": "user", "parts": [{"text": json.dumps(
                {"goal": goal, "capabilities": safe_tools}, ensure_ascii=False)}]}],
            "system_instruction": {"parts": [{"text": _PLANNER_SYSTEM}]},
            "generationConfig": {"temperature": self.config.temperature,
                                 "maxOutputTokens": self.config.max_tokens,
                                 "responseMimeType": "application/json"},
        }

    async def plan(self, goal: str, catalog: list[CatalogEntry] | None = None) -> Plan:
        if not self.config.api_key:
            raise ValueError("Falta GEMINI_API_KEY; no se enviará el objetivo")
        try:
            response = await self._http.post(
                self._url(), json=self._payload(goal, catalog),
                headers=self._headers())
            if response.status_code >= 400 or response.is_redirect:
                raise ProviderError(f"Google devolvió HTTP {response.status_code}.")
            content = self._text_of(response.json())
            allowed = [t["name"] for t in read_only_catalog(catalog)]
            return plan_from_content(content, goal, f"gemini:{self.config.model}",
                                      allowed)
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("Gemini no entregó un plan válido.") from exc

    async def chat(self, turn: TurnContext) -> AsyncIterator[ChatEvent]:
        if not self.config.api_key:
            raise ValueError("Falta GEMINI_API_KEY; no se enviará nada")
        messages = turn.messages or [{"role": "user", "content": turn.text}]
        system, contents = _to_contents(messages)
        if not contents:
            raise ProviderError("Gemini necesita al menos un mensaje no-system.")
        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": self.config.temperature,
                                 "maxOutputTokens": self.config.max_tokens},
        }
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}
        try:
            response = await self._http.post(self._url(), json=body,
                                             headers=self._headers())
            if response.status_code >= 400 or response.is_redirect:
                raise ProviderError(f"Google devolvió HTTP {response.status_code}.")
            content = self._text_of(response.json())
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("Gemini no entregó respuesta de chat.") from exc
        yield ChatEvent(type="token", text=content)
        yield ChatEvent(type="done", done=True)
