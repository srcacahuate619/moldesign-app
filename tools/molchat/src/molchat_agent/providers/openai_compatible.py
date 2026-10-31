"""Generic OpenAI-compatible planner (remote or loopback-local).

Design reimplemented from MolDesign's ``openai_provider.py`` without copying
it. Differences are deliberate and safer: no third-party defaults (no
surprise calls to Groq/OpenAI), remote requires HTTPS, and locality is
computed from the URL host — a loopback ``base_url`` is local even though
the provider id is cloud-shaped.
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator
from urllib.parse import urlsplit

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
    readonly_plan_schema,
)

LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def is_loopback_url(url: str) -> bool:
    try:
        return (urlsplit(url).hostname or "").lower() in LOOPBACK_HOSTS
    except ValueError:
        return False


class OpenAICompatibleProvider:
    """Chat-completions planner against any OpenAI-compatible endpoint."""

    id = "openai-compatible"

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None, temperature: float = 0.1,
                 json_mode: str | None = None, disable_thinking: bool | None = None,
                 client: httpx.AsyncClient | None = None,
                 provider_id: str | None = None) -> None:
        # Un proveedor del catálogo (openai, deepseek, nvidia...) es una instancia
        # con su id; sin id queda el genérico de siempre.
        self.id = provider_id or type(self).id
        config = load_config()
        self.json_mode = json_mode if json_mode is not None else config.openai_compat_json_mode
        if self.json_mode not in ("schema", "object"):
            raise ValueError("OPENAI_COMPAT_JSON_MODE debe ser schema u object.")
        self.disable_thinking = (disable_thinking if disable_thinking is not None
                                 else config.openai_compat_disable_thinking)
        resolved_base = (base_url if base_url is not None
                         else config.openai_compat_base_url).strip().rstrip("/")
        if resolved_base:
            scheme = (urlsplit(resolved_base).scheme or "").lower()
            if is_loopback_url(resolved_base):
                self.locality: str = "local"
            else:
                if scheme != "https":
                    raise ValueError(
                        "Un endpoint remoto exige HTTPS; loopback para local.")
                self.locality = "remote"
        else:
            # Unknown destination: fail closed until configured.
            self.locality = "remote"
        self.config = ProviderConfig(
            api_key=api_key if api_key is not None else (config.openai_compat_api_key or ""),
            base_url=resolved_base,
            model=model if model is not None else config.openai_compat_model,
            temperature=temperature,
        )
        self._client = client
        self._owns_client = client is None

    @property
    def _http(self) -> httpx.AsyncClient:
        """Transport, created on first use (fast builds, no leaks)."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0, trust_env=False)
        return self._client

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name="OpenAI-compatible",
            description="Cualquier endpoint estilo OpenAI (nube o loopback local).",
            requires_api_key=self.locality == "remote",
            requires_base_url=True,
        )

    async def __aenter__(self) -> "OpenAICompatibleProvider":
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    async def health(self) -> HealthCheckResult:
        if not self.config.base_url:
            return HealthCheckResult(
                status=HealthStatus.NOT_CONFIGURED,
                message="Falta OPENAI_COMPAT_BASE_URL.")
        if self.locality == "remote" and not self.config.api_key:
            return HealthCheckResult(
                status=HealthStatus.NO_API_KEY,
                message="Falta OPENAI_COMPAT_API_KEY para el endpoint remoto.")
        start = time.monotonic()
        try:
            response = await self._http.get(
                f"{self.config.base_url}/models", headers=self._headers(),
                timeout=httpx.Timeout(5.0, connect=1.0))
        except (httpx.RequestError, ValueError) as exc:
            return HealthCheckResult(
                status=HealthStatus.CONNECTION_ERROR,
                message=f"No responde en {self.config.base_url}: {exc}",
                latency_ms=(time.monotonic() - start) * 1000)
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        if response.status_code == 200:
            return HealthCheckResult(
                status=HealthStatus.OK,
                message=f"Responde en {self.config.base_url}.", latency_ms=elapsed_ms)
        if response.status_code in (401, 403):
            return HealthCheckResult(
                status=HealthStatus.NO_API_KEY,
                message=f"El endpoint rechazó la clave (HTTP {response.status_code}).",
                latency_ms=elapsed_ms)
        return HealthCheckResult(
            status=HealthStatus.CONNECTION_ERROR,
            message=f"El endpoint devolvió HTTP {response.status_code}.",
            latency_ms=elapsed_ms)

    def _payload(self, goal: str, catalog: list[CatalogEntry] | None) -> dict[str, Any]:
        safe_tools = read_only_catalog(catalog)
        user_data: dict[str, Any] = {"goal": goal, "capabilities": safe_tools}
        instruction = (
            "Eres un planificador de química computacional. Propón SOLO una secuencia "
            "de herramientas enumeradas en el catálogo. Nunca inventes IDs, SMILES, "
            "datos de receptores ni resultados. Devuelve el plan como JSON con la "
            "estructura indicada."
        )
        if self.json_mode == "object":
            instruction += (
                ' Responde exclusivamente con un objeto de la forma '
                '{"steps":[{"capability":"nombre de herramienta",'
                '"arguments":{},"rationale":"motivo"}]}. '
                "No copies el objetivo ni el catálogo en la respuesta. Incluye solo "
                "argumentos válidos y omite los opcionales no indicados; no uses null "
                "ni texto vacío. Si falta un identificador necesario, no lo inventes."
            )
        payload: dict[str, Any] = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": min(self.config.max_tokens, 2048),
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": json.dumps(
                    user_data, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "molchat_readonly_plan", "strict": False,
                "schema": readonly_plan_schema(safe_tools),
            }},
        }
        if self.json_mode == "object":
            payload["response_format"] = {"type": "json_object"}
        if self.disable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        return payload

    async def plan(self, goal: str, catalog: list[CatalogEntry] | None = None) -> Plan:
        if not self.config.base_url:
            raise ValueError("Falta OPENAI_COMPAT_BASE_URL; nada que contactar.")
        if self.locality == "remote" and not self.config.api_key:
            raise ValueError("Falta OPENAI_COMPAT_API_KEY para el endpoint remoto.")
        if not self.config.model:
            raise ValueError("Falta OPENAI_COMPAT_MODEL; el endpoint no sabe qué servir.")
        try:
            response = await self._http.post(
                f"{self.config.base_url}/chat/completions",
                json=self._payload(goal, catalog), headers=self._headers())
            if response.status_code >= 400 or response.is_redirect:
                raise ProviderError(
                    f"El endpoint devolvió HTTP {response.status_code}.")
            content = response.json()["choices"][0]["message"]["content"]
            allowed = [t["name"] for t in read_only_catalog(catalog)]
            return plan_from_content(content, goal, f"openai-compatible:{self.config.model}",
                                     allowed)
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("El proveedor no entregó un plan válido.") from exc

    async def chat(self, turn: TurnContext) -> AsyncIterator[ChatEvent]:
        if not self.config.base_url:
            raise ValueError("Falta OPENAI_COMPAT_BASE_URL; nada que contactar.")
        if self.locality == "remote" and not self.config.api_key:
            raise ValueError("Falta OPENAI_COMPAT_API_KEY para el endpoint remoto.")
        if not self.config.model:
            raise ValueError("Falta OPENAI_COMPAT_MODEL; el endpoint no sabe qué servir.")
        messages = turn.messages or [{"role": "user", "content": turn.text}]
        try:
            payload = {"model": self.config.model, "messages": messages,
                       "temperature": self.config.temperature,
                       "max_tokens": self.config.max_tokens}
            if self.disable_thinking:
                payload["chat_template_kwargs"] = {"enable_thinking": False}
            response = await self._http.post(
                f"{self.config.base_url}/chat/completions",
                json=payload,
                headers=self._headers())
            if response.status_code >= 400 or response.is_redirect:
                raise ProviderError(
                    f"El endpoint devolvió HTTP {response.status_code}.")
            content = response.json()["choices"][0]["message"]["content"]
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("El proveedor no entregó respuesta de chat.") from exc
        yield ChatEvent(type="token", text=content)
        yield ChatEvent(type="done", done=True)

    async def chat_with_tools(self, messages: list[dict[str, Any]],
                              tools: list[dict[str, Any]]) -> dict[str, Any]:
        """One model step; the harness owns execution and continuation."""
        if not self.config.base_url or not self.config.model:
            raise ProviderError("Falta configurar el endpoint o el modelo.")
        if self.locality == "remote" and not self.config.api_key:
            raise ProviderError("Falta la clave del proveedor.")
        payload: dict[str, Any] = {"model": self.config.model, "messages": messages,
                                  "temperature": self.config.temperature,
                                  "max_tokens": self.config.max_tokens}
        if tools:
            payload.update({"tools": tools, "tool_choice": "auto"})
        if self.disable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        try:
            response = await self._http.post(f"{self.config.base_url}/chat/completions",
                                             json=payload, headers=self._headers())
            if response.status_code >= 400 or response.is_redirect:
                raise ProviderError(f"El proveedor rechazó las herramientas (HTTP {response.status_code}).")
            message = response.json()["choices"][0]["message"]
            if not isinstance(message, dict):
                raise ProviderError("Respuesta del proveedor no válida.")
            return message
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("El proveedor no entregó una respuesta válida de herramientas.") from exc
