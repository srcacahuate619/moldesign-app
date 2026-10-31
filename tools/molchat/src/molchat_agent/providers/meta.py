"""Meta Muse Spark planner. Produces proposals, never executes tools.

Hackathon policy (PLAN §6.1.1): the default and demonstrable model is
``muse-spark-1.3`` Standard. The ``contributor`` tier trains on the data sent
to it, so selecting it with scientific data is forbidden and rejected here.
Reasoning defaults to ``medium``; raising it needs quality-suite evidence.
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator

import httpx

from ..tools import PlanValidationError
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

META_URL = "https://api.meta.ai/v1/chat/completions"
META_API_BASE = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.3"
DEFAULT_REASONING_EFFORT = "medium"
REASONING_LEVELS = ("medium", "high", "xhigh", "max")


class MetaProvider:
    """Muse Spark planner behind the LLMProvider port (remote)."""

    id = "meta"
    locality = "remote"

    def __init__(self, *, api_key: str | None = None, model: str | None = None,
                 reasoning_effort: str = DEFAULT_REASONING_EFFORT,
                 client: httpx.AsyncClient | None = None) -> None:
        config = load_config()
        if reasoning_effort not in REASONING_LEVELS:
            raise ValueError(
                f"reasoning_effort debe ser uno de {list(REASONING_LEVELS)}: "
                f"{reasoning_effort!r}")
        resolved_model = model or config.meta_model
        if "contributor" in resolved_model.lower():
            raise ValueError(
                f"Modelo {resolved_model!r} prohibido: el nivel contributor usa "
                "los datos para mejorar productos de Meta (PLAN §6.1.1).")
        self.config = ProviderConfig(
            api_key=api_key or config.model_api_key or "",
            base_url=META_API_BASE,
            model=resolved_model,
        )
        self.reasoning_effort = reasoning_effort
        self._client = client
        self._owns_client = client is None

    @property
    def _http(self) -> httpx.AsyncClient:
        """Transport, created on first use (fast builds, no leaks)."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0, trust_env=False)
        return self._client

    async def __aenter__(self) -> "MetaProvider":
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name="Meta Muse Spark",
            description="Planificador remoto por defecto del perfil hackathon.",
            requires_api_key=True,
            requires_base_url=False,
            default_base_url=META_API_BASE,
            default_model=DEFAULT_MODEL,
        )

    async def health(self) -> HealthCheckResult:
        if not self.config.api_key:
            return HealthCheckResult(
                status=HealthStatus.NO_API_KEY,
                message="Falta MODEL_API_KEY; no se enviará nada a Meta.")
        start = time.monotonic()
        try:
            response = await self._http.post(
                META_URL,
                json={"model": self.config.model,
                      "messages": [{"role": "user", "content": "hi"}],
                      "max_tokens": 1},
                headers={"Authorization": f"Bearer {self.config.api_key}",
                         "Content-Type": "application/json"},
            )
        except (httpx.RequestError, ValueError) as exc:
            return HealthCheckResult(
                status=HealthStatus.CONNECTION_ERROR,
                message=f"No se pudo contactar a Meta: {exc}",
                latency_ms=(time.monotonic() - start) * 1000)
        elapsed_ms = (time.monotonic() - start) * 1000
        if response.status_code == 200:
            return HealthCheckResult(
                status=HealthStatus.OK, message="Meta responde.",
                latency_ms=round(elapsed_ms, 1))
        if response.status_code in (401, 403):
            return HealthCheckResult(
                status=HealthStatus.NO_API_KEY,
                message=f"Meta rechazó la clave (HTTP {response.status_code}).",
                latency_ms=round(elapsed_ms, 1))
        if response.status_code in (402, 429):
            return HealthCheckResult(
                status=HealthStatus.NO_TOKENS,
                message=f"Sin saldo o cuota excedida (HTTP {response.status_code}).",
                latency_ms=round(elapsed_ms, 1))
        return HealthCheckResult(
            status=HealthStatus.CONNECTION_ERROR,
            message=f"Meta devolvió HTTP {response.status_code}.",
            latency_ms=round(elapsed_ms, 1))

    def _payload(self, goal: str, catalog: list[CatalogEntry] | None) -> dict[str, Any]:
        safe_tools = read_only_catalog(catalog)
        schema = readonly_plan_schema(safe_tools)
        return {
            "model": self.config.model,
            "reasoning_effort": self.reasoning_effort,
            "messages": [
                {"role": "developer", "content": (
                    "Eres un planificador de química computacional. Propón SOLO una secuencia "
                    "de herramientas enumeradas en el catálogo. Nunca inventes IDs, SMILES, "
                    "datos de receptores ni resultados. Si faltan datos, usa solamente "
                    "list_targets u otra consulta válida. No realices diagnóstico clínico. "
                    "No hay ejecución en esta llamada. El protocolo científico lo decide MolDesign. "
                    "Devuelve el plan como JSON con la estructura indicada."
                )},
                {"role": "user", "content": json.dumps(
                    {"goal": goal, "capabilities": safe_tools}, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "molchat_readonly_plan", "strict": False, "schema": schema,
            }},
        }

    async def plan(self, goal: str, catalog: list[CatalogEntry] | None = None) -> Plan:
        if not self.config.api_key:
            raise ValueError("Falta MODEL_API_KEY; no se enviará el objetivo a Meta")
        if not isinstance(goal, str) or not 0 < len(goal) <= 4000:
            raise PlanValidationError("Objetivo no válido")
        try:
            response = await self._http.post(
                META_URL, json=self._payload(goal, catalog),
                headers={"Authorization": f"Bearer {self.config.api_key}",
                         "Content-Type": "application/json"},
            )
            if response.status_code >= 400 or response.is_redirect:
                raise RuntimeError(f"Meta Model API devolvió HTTP {response.status_code}")
            content = response.json()["choices"][0]["message"]["content"]
            allowed = [t["name"] for t in read_only_catalog(catalog)]
            return plan_from_content(content, goal, f"meta:{self.config.model}",
                                     allowed)
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("Meta no entregó un plan válido; no se ejecutó nada") from exc
        except ProviderError as exc:
            raise RuntimeError("Meta no entregó un plan válido; no se ejecutó nada") from exc

    async def chat(self, turn: TurnContext) -> AsyncIterator[ChatEvent]:
        if not self.config.api_key:
            raise ValueError("Falta MODEL_API_KEY; no se enviará nada a Meta")
        messages = turn.messages or [{"role": "user", "content": turn.text}]
        try:
            response = await self._http.post(
                META_URL,
                json={"model": self.config.model, "messages": messages,
                      "max_tokens": self.config.max_tokens},
                headers={"Authorization": f"Bearer {self.config.api_key}",
                         "Content-Type": "application/json"},
            )
            if response.status_code >= 400 or response.is_redirect:
                raise ProviderError(f"Meta Model API devolvió HTTP {response.status_code}")
            content = response.json()["choices"][0]["message"]["content"]
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("Meta no entregó respuesta de chat.") from exc
        yield ChatEvent(type="token", text=content)
        yield ChatEvent(type="done", done=True)

    async def chat_with_tools(self, messages: list[dict[str, Any]],
                              tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Forward the native Chat Completions tool protocol to Meta."""
        from .openai_compatible import OpenAICompatibleProvider

        adapter = OpenAICompatibleProvider(api_key=self.config.api_key, base_url=META_API_BASE,
                                           model=self.config.model, client=self._http,
                                           provider_id=self.id)
        return await adapter.chat_with_tools(messages, tools)


#: Backward-compatible alias: the class lived in ``molchat_agent.meta``.
MetaPlanner = MetaProvider
