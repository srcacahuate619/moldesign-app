"""Local HTTP planners: llama-server and Ollama on loopback.

Design reimplemented from MolDesign's ``local_llm_provider.py``,
``ollama_provider.py`` and ``local_llm.py`` (ports, endpoints, timeouts)
without copying them and without the process lifecycle — Fase 1 talks to
already-running servers; managing ``llama-server.exe`` is Fase 5 work.
Both providers refuse non-loopback URLs at construction: local means local.
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
PROBE_TIMEOUT = httpx.Timeout(5.0, connect=1.0)


def _require_loopback(url: str, variable: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    if host not in LOOPBACK_HOSTS:
        raise ValueError(
            f"{variable} debe ser loopback (se recibió {url!r}); "
            "un servidor remoto no es un proveedor local.")
    return url.rstrip("/")


class LlamaServerProvider:
    """Planner against a running llama-server (OpenAI-compatible /v1)."""

    id = "llama-server"
    locality = "local"

    def __init__(self, *, base_url: str | None = None, model: str | None = None,
                 temperature: float = 0.1,
                 client: httpx.AsyncClient | None = None) -> None:
        config = load_config()
        resolved_base = (base_url if base_url is not None else config.llama_server_url)
        self.config = ProviderConfig(
            base_url=_require_loopback(resolved_base.strip(), "LLAMA_SERVER_URL"),
            model=model if model is not None else config.llama_server_model,
            temperature=temperature,
        )
        self._client = client
        self._owns_client = client is None

    @property
    def _http(self) -> httpx.AsyncClient:
        """Transport, created on first use (fast builds, no leaks)."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0, trust_env=False)
        return self._client

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name="llama-server (local)",
            description="Servidor llama-server en ejecución, puerto 8400 por defecto.",
            requires_api_key=False,
            requires_base_url=False,
            default_base_url="http://127.0.0.1:8400/v1",
        )

    async def __aenter__(self) -> "LlamaServerProvider":
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def health(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            response = await self._http.get(
                f"{self.config.base_url}/models", timeout=PROBE_TIMEOUT)
        except (httpx.RequestError, ValueError) as exc:
            return HealthCheckResult(
                status=HealthStatus.CONNECTION_ERROR,
                message=f"llama-server no responde en {self.config.base_url}: {exc}",
                latency_ms=(time.monotonic() - start) * 1000)
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        if response.status_code != 200:
            return HealthCheckResult(
                status=HealthStatus.CONNECTION_ERROR,
                message=f"llama-server devolvió HTTP {response.status_code}.",
                latency_ms=elapsed_ms)
        try:
            models = [m["id"] for m in response.json().get("data", [])]
        except (ValueError, AttributeError, KeyError, TypeError):
            models = []
        detail = f"Modelos: {', '.join(models[:4])}" if models else "Sin modelos listados."
        return HealthCheckResult(
            status=HealthStatus.OK,
            message=f"Responde en {self.config.base_url}. {detail}",
            latency_ms=elapsed_ms)

    def _payload(self, goal: str, catalog: list[CatalogEntry] | None) -> dict[str, Any]:
        safe_tools = read_only_catalog(catalog)
        return {
            "model": self.config.model,
            "temperature": self.config.temperature,
            # Bound generation: a plan is short JSON. Without a cap, a
            # thinking model on CPU spends the whole client timeout
            # reasoning instead of answering (seen live, Fase 1 closure).
            "max_tokens": self.config.max_tokens,
            "messages": [
                {"role": "system", "content": (
                    "Eres un planificador de química computacional. Propón SOLO una secuencia "
                    "de herramientas enumeradas en el catálogo. Nunca inventes IDs, SMILES, "
                    "datos de receptores ni resultados. Devuelve el plan como JSON con la "
                    "estructura indicada."
                )},
                {"role": "user", "content": json.dumps(
                    {"goal": goal, "capabilities": safe_tools}, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "molchat_readonly_plan", "strict": False,
                "schema": readonly_plan_schema(safe_tools),
            }},
        }

    async def plan(self, goal: str, catalog: list[CatalogEntry] | None = None) -> Plan:
        if not self.config.model:
            raise ValueError("Falta LLAMA_SERVER_MODEL; el servidor no sabe qué servir.")
        try:
            response = await self._http.post(
                f"{self.config.base_url}/chat/completions",
                json=self._payload(goal, catalog))
            if response.status_code >= 400:
                raise ProviderError(
                    f"llama-server devolvió HTTP {response.status_code}.")
            content = response.json()["choices"][0]["message"]["content"]
            allowed = [t["name"] for t in read_only_catalog(catalog)]
            return plan_from_content(content, goal, f"llama-server:{self.config.model}",
                                     allowed)
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("llama-server no entregó un plan válido.") from exc

    async def chat(self, turn: TurnContext) -> AsyncIterator[ChatEvent]:
        if not self.config.model:
            raise ValueError("Falta LLAMA_SERVER_MODEL; el servidor no sabe qué servir.")
        messages = turn.messages or [{"role": "user", "content": turn.text}]
        try:
            response = await self._http.post(
                f"{self.config.base_url}/chat/completions",
                json={"model": self.config.model, "messages": messages,
                      "temperature": self.config.temperature,
                      "max_tokens": self.config.max_tokens})
            if response.status_code >= 400:
                raise ProviderError(
                    f"llama-server devolvió HTTP {response.status_code}.")
            content = response.json()["choices"][0]["message"]["content"]
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("llama-server no entregó respuesta de chat.") from exc
        yield ChatEvent(type="token", text=content)
        yield ChatEvent(type="done", done=True)

    async def chat_with_tools(self, messages: list[dict[str, Any]],
                              tools: list[dict[str, Any]]) -> dict[str, Any]:
        """llama-server exposes the same structured Chat Completions contract."""
        from .openai_compatible import OpenAICompatibleProvider

        adapter = OpenAICompatibleProvider(base_url=self.config.base_url, model=self.config.model,
                                           temperature=self.config.temperature, client=self._http,
                                           provider_id=self.id)
        return await adapter.chat_with_tools(messages, tools)


class OllamaProvider:
    """Planner against a running Ollama server (native /api/*)."""

    id = "ollama"
    locality = "local"

    def __init__(self, *, base_url: str | None = None, model: str | None = None,
                 temperature: float = 0.1,
                 client: httpx.AsyncClient | None = None) -> None:
        config = load_config()
        resolved_base = base_url if base_url is not None else config.ollama_url
        self.config = ProviderConfig(
            base_url=_require_loopback(resolved_base.strip(), "OLLAMA_URL"),
            model=(model if model is not None else config.ollama_model).strip(),
            temperature=temperature,
        )
        self._client = client
        self._owns_client = client is None

    @property
    def _http(self) -> httpx.AsyncClient:
        """Transport, created on first use (fast builds, no leaks)."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0, trust_env=False)
        return self._client

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name="Ollama (local)",
            description="Servidor Ollama en ejecución, puerto 11434 por defecto.",
            requires_api_key=False,
            requires_base_url=False,
            default_base_url="http://127.0.0.1:11434",
        )

    async def __aenter__(self) -> "OllamaProvider":
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _tags(self) -> list[str]:
        response = await self._http.get(
            f"{self.config.base_url}/api/tags", timeout=PROBE_TIMEOUT)
        if response.status_code != 200:
            raise ProviderError(f"Ollama devolvió HTTP {response.status_code}.")
        try:
            return [m["name"] for m in response.json().get("models", [])]
        except (ValueError, AttributeError, KeyError, TypeError):
            return []

    @staticmethod
    def _installed(model: str, installed: list[str]) -> str | None:
        """How Ollama lists ``model`` (bare names resolve to ``:latest``)."""
        model = model.strip()
        if not model:
            return None
        candidates = {model} if ":" in model else {model, f"{model}:latest"}
        return next((m for m in installed if m in candidates), None)

    async def health(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            installed = await self._tags()
        except (httpx.RequestError, ValueError, ProviderError) as exc:
            return HealthCheckResult(
                status=HealthStatus.CONNECTION_ERROR,
                message=f"Ollama no responde en {self.config.base_url}: {exc}",
                latency_ms=(time.monotonic() - start) * 1000)
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        if not installed:
            return HealthCheckResult(
                status=HealthStatus.NOT_AVAILABLE,
                message=(f"Ollama responde en {self.config.base_url} pero no "
                         "tiene modelos. Descarga uno con `ollama pull <modelo>`."),
                latency_ms=elapsed_ms)
        if not self.config.model:
            return HealthCheckResult(
                status=HealthStatus.NOT_CONFIGURED,
                message=(f"Falta OLLAMA_MODEL. Instalados: {', '.join(installed[:6])}."),
                latency_ms=elapsed_ms)
        resolved = self._installed(self.config.model, installed)
        if resolved is None:
            return HealthCheckResult(
                status=HealthStatus.NOT_AVAILABLE,
                message=(f"Ollama no tiene {self.config.model!r}. Instalados: "
                         f"{', '.join(installed[:6])} (o `ollama pull "
                         f"{self.config.model}`)."),
                latency_ms=elapsed_ms)
        return HealthCheckResult(
            status=HealthStatus.OK,
            message=(f"Responde en {self.config.base_url} con {resolved}."),
            latency_ms=elapsed_ms)

    async def plan(self, goal: str, catalog: list[CatalogEntry] | None = None) -> Plan:
        if not self.config.model:
            raise ValueError("Falta OLLAMA_MODEL; nada que pedirle a Ollama.")
        safe_tools = read_only_catalog(catalog)
        try:
            installed = await self._tags()
        except (httpx.RequestError, ValueError) as exc:
            raise ProviderError(f"Ollama no responde en {self.config.base_url}.") from exc
        if self._installed(self.config.model, installed) is None:
            raise ProviderError(
                f"Ollama no tiene {self.config.model!r}; descárgalo con "
                f"`ollama pull {self.config.model}`.")
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": (
                    "Eres un planificador de química computacional. Propón SOLO una secuencia "
                    "de herramientas enumeradas en el catálogo. Nunca inventes IDs, SMILES, "
                    "datos de receptores ni resultados. Devuelve el plan como JSON con la "
                    "estructura indicada."
                )},
                {"role": "user", "content": json.dumps(
                    {"goal": goal, "capabilities": safe_tools}, ensure_ascii=False)},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": self.config.temperature,
                        "num_predict": self.config.max_tokens},
        }
        try:
            response = await self._http.post(
                f"{self.config.base_url}/api/chat", json=payload)
            if response.status_code != 200:
                raise ProviderError(f"Ollama devolvió HTTP {response.status_code}.")
            content = response.json()["message"]["content"]
            allowed = [t["name"] for t in read_only_catalog(catalog)]
            return plan_from_content(content, goal, f"ollama:{self.config.model}",
                                     allowed)
        except (httpx.RequestError, KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Ollama no entregó un plan válido.") from exc

    async def chat(self, turn: TurnContext) -> AsyncIterator[ChatEvent]:
        if not self.config.model:
            raise ValueError("Falta OLLAMA_MODEL; nada que pedirle a Ollama.")
        messages = turn.messages or [{"role": "user", "content": turn.text}]
        try:
            response = await self._http.post(
                f"{self.config.base_url}/api/chat",
                json={"model": self.config.model, "messages": messages,
                      "stream": False,
                      "options": {"temperature": self.config.temperature,
                                  "num_predict": self.config.max_tokens}})
            if response.status_code != 200:
                raise ProviderError(f"Ollama devolvió HTTP {response.status_code}.")
            content = response.json()["message"]["content"]
        except (httpx.RequestError, KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Ollama no entregó respuesta de chat.") from exc
        yield ChatEvent(type="token", text=content)
        yield ChatEvent(type="done", done=True)
