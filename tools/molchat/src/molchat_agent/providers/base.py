"""The LLMProvider port: one interface for local and cloud planners.

Reimplemented from the design of MolDesign's ``providers/base.py``
(``AIProvider``, health states) without importing it and without its
per-user coupling. Every provider only ever sees read-only capabilities:
filtering happens here, not in each provider.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Literal, Protocol

from ..tools import PlanValidationError, catalog as get_catalog
from ..plan import MAX_STEPS, Plan

CatalogEntry = dict[str, Any]

# Identifiers supplied to an untrusted planner have only one current source:
# the goal text. Do not infer them from a model's general knowledge. This is
# deliberately narrower than a semantic verifier and can reject valid plans.
_EXPLICIT_IDENTIFIERS = frozenset({
    "task_id", "proposal_id", "molecule_id", "batch_id", "case_id",
    "target_pdb_id", "idempotency_key", "smiles",
})


def _check_explicit_identifiers(plan: Plan, goal: str) -> None:
    for step in plan.steps:
        for key, value in step.arguments.items():
            if key not in _EXPLICIT_IDENTIFIERS or not isinstance(value, str):
                continue
            # SMILES is case-sensitive. Identifiers must occur as complete
            # tokens; only PDB identifiers are compared case-insensitively.
            flags = re.IGNORECASE if key == "target_pdb_id" else 0
            pattern = r"(?<![\w-])" + re.escape(value) + r"(?![\w-])"
            if re.search(pattern, goal, flags) is None:
                raise ProviderError(
                    f"{key}: el identificador no aparece explícitamente en el objetivo")


class HealthStatus(Enum):
    OK = "ok"
    NO_API_KEY = "no_api_key"
    NOT_CONFIGURED = "not_configured"
    CONNECTION_ERROR = "connection_error"
    NO_TOKENS = "no_tokens"
    NOT_AVAILABLE = "not_available"
    # Unknown by rule, not by failure: probing a non-consented remote
    # destination would send the very bytes consent exists to prevent.
    NO_CONSENT = "no_consent"


@dataclass
class HealthCheckResult:
    status: HealthStatus = HealthStatus.NOT_AVAILABLE
    message: str = ""
    latency_ms: float = 0.0


@dataclass
class ProviderConfig:
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.5
    max_tokens: int = 4096
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderInfo:
    id: str
    name: str
    description: str
    requires_api_key: bool
    requires_base_url: bool
    default_base_url: str = ""
    default_model: str = ""


@dataclass
class TurnContext:
    """Minimal turn for streaming chat.

    ``messages`` carries full history when the caller has it (engine
    conceptual path); otherwise providers synthesize ``[user: text]``.
    """

    text: str
    catalog: list[CatalogEntry] | None = None
    messages: list[dict[str, str]] | None = None


@dataclass
class ChatEvent:
    type: str  # "token" | "warning" | "done"
    text: str = ""
    done: bool = False


class ProviderError(RuntimeError):
    """A provider failed without producing a usable plan."""


class ProviderDisabled(RuntimeError):
    """The active profile does not allow this provider."""


def read_only_catalog(catalog: list[CatalogEntry] | None) -> list[CatalogEntry]:
    """Catalog entries a planner may see: explicit ``read`` risk only.

    ``None`` means the full local catalog. Entries without an explicit
    ``"read"`` risk are excluded (fail closed).
    """
    entries = (catalog if catalog is not None
               else [c.as_catalog_entry() for c in get_catalog().values()])
    return [e for e in entries if e.get("risk") == "read"]


def readonly_plan_schema(safe_tools: list[CatalogEntry]) -> dict[str, Any]:
    """JSON schema for planner output: steps only, tools from an enum."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["steps"],
        "properties": {
            "steps": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_STEPS,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["capability", "arguments", "rationale"],
                    "properties": {
                        "capability": {
                            "type": "string",
                            "enum": [t["name"] for t in safe_tools],
                        },
                        "arguments": {"type": "object"},
                        "rationale": {"type": "string"},
                    },
                },
            },
        },
    }


def plan_from_content(content: str, goal: str, planner: str,
                      allowed: list[str] | None = None) -> Plan:
    """Parse ``{"steps": [...]}`` model output into a validated plan.

    Step ids (s1, s2, …) are assigned locally and every step is validated
    against the capability contract; unknown tools or bad arguments raise
    instead of producing a plan. When ``allowed`` carries the exact tool
    names sent to the provider, anything outside that set is rejected even
    if the general catalog knows it (MP-02: the read-only offer is the
    ceiling, not the catalog). ``None`` is for trusted, code-generated
    content only (fake provider).
    """
    try:
        decoded = json.loads(content)
        raw_steps = decoded["steps"]
        steps = [dict(id=f"s{n}", **item)
                 for n, item in enumerate(raw_steps, 1)]
        if allowed is not None:
            names = set(allowed)
            for step in steps:
                if step.get("capability") not in names:
                    raise ProviderError(
                        f"La respuesta usa {step.get('capability')!r}, fuera "
                        f"del catálogo enviado: {sorted(names)}")
        plan = Plan.from_dict({"goal": goal, "steps": steps, "planner": planner})
        if allowed is not None:
            _check_explicit_identifiers(plan, goal)
        return plan
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ProviderError(f"El proveedor no entregó un plan válido: {exc}") from exc
    except PlanValidationError as exc:
        raise ProviderError(f"El proveedor propuso pasos fuera de contrato: {exc}") from exc


class LLMProvider(Protocol):
    id: str
    locality: Literal["local", "remote"]
    config: ProviderConfig

    async def health(self) -> HealthCheckResult: ...
    async def plan(self, goal: str, catalog: list[CatalogEntry] | None = None) -> Plan: ...
    async def chat(self, turn: TurnContext) -> AsyncIterator[ChatEvent]: ...
