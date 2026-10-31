"""Deterministic provider for tests and keyless demos.

No network, no randomness: the same goal always yields the same plan, and
every step is read-only. Anything needing an id the user did not give
(task ids, proposal ids) degrades to a listing step instead of inventing one.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from ..tools import PlanValidationError
from ..plan import Plan
from .base import (
    CatalogEntry,
    ChatEvent,
    HealthCheckResult,
    HealthStatus,
    ProviderConfig,
    ProviderInfo,
    TurnContext,
    plan_from_content,
)

# Fixed public demo molecule/target. Constants, not inventions: the fake
# provider never derives identifiers from the goal text.
DEMO_SMILES = "CCO"
DEMO_TARGET = "1HSG"


class FakeProvider:
    id = "fake"
    locality = "local"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self.config = config or ProviderConfig()

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name="Fake (determinista)",
            description="Planes fijos sin red, para tests y demos sin claves.",
            requires_api_key=False,
            requires_base_url=False,
        )

    async def health(self) -> HealthCheckResult:
        return HealthCheckResult(
            status=HealthStatus.OK,
            message="Proveedor determinista; no usa red.",
        )

    def _route(self, goal: str) -> list[dict[str, Any]]:
        text = goal.lower()
        if any(w in text for w in ("historial", "history", "evaluaciones",
                                   "evaluations", "estado", "status")):
            return [{"capability": "list_evaluations", "arguments": {},
                     "rationale": "Demo determinista: listar evaluaciones primero"}]
        if any(w in text for w in ("preflight", "evaluar", "evaluate", "docking")):
            return [{"capability": "check_preflight",
                     "arguments": {"smiles": DEMO_SMILES, "target_pdb_id": DEMO_TARGET},
                     "rationale": "Demo determinista con molécula pública fija"}]
        return [{"capability": "list_targets", "arguments": {},
                 "rationale": "Demo determinista: listar receptores primero"}]

    async def plan(self, goal: str, catalog: list[CatalogEntry] | None = None) -> Plan:
        if not isinstance(goal, str) or not 0 < len(goal) <= 4000:
            raise PlanValidationError("Objetivo no válido")
        _ = catalog  # the fake provider only emits fixed read-only steps
        return plan_from_content(
            json.dumps({"steps": self._route(goal)}),
            goal, "fake:deterministic")

    async def chat(self, turn: TurnContext) -> AsyncIterator[ChatEvent]:
        """Canned conceptual answer. No digits: nothing to verify, nothing to fake."""
        yield ChatEvent(type="token", text=(
            "Respuesta conceptual de demostración, sin valores numéricos: "
            "los datos factuales siempre vienen de herramientas verificadas."))
        yield ChatEvent(type="done", done=True)
