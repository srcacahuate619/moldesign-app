"""Immutable plans: their SHA-256 digest binds explicit human approvals.

Immutability is enforced by copying: ``from_dict`` deep-copies caller data
and ``as_dict`` deep-copies on export, so no reference the caller keeps can
mutate a plan (or be mutated through it) while a step is awaited (MP-01).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

from .tools import capability, PlanValidationError

MAX_STEPS = 8
MAX_STEPS_2 = 25
SCHEMA_1 = "/1"
SCHEMA_2 = "/2"

_BINDING_RE = re.compile(r"^s([1-9]\d*)\.([A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+)*)$")


class BindingError(PlanValidationError):
    """A step binding is malformed, unresolvable, or mistyped."""


def is_binding(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == {"$from"} and isinstance(value["$from"], str)


class _Missing:
    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<missing>"


_MISSING = _Missing()


def resolve_binding(reference: str, results: dict[str, Any]) -> Any:
    """Walk ``sN.path.to.value`` over prior step results (dicts + list indices)."""
    match = _BINDING_RE.fullmatch(reference)
    if match is None:
        raise BindingError(f"Referencia malformada: {reference!r}")
    current: Any = results.get(f"s{match.group(1)}", _MISSING)
    if current is _MISSING:
        raise BindingError(f"Referencia a paso no ejecutado: {reference!r}")
    for segment in match.group(2).split("."):
        if isinstance(current, list):
            if not segment.isdigit() or int(segment) >= len(current):
                raise BindingError(f"Ruta sin dato: {reference!r}")
            current = current[int(segment)]
        elif isinstance(current, dict):
            if segment not in current:
                raise BindingError(f"Ruta sin dato: {reference!r}")
            current = current[segment]
        else:
            raise BindingError(f"Ruta sin dato: {reference!r}")
    return current


@dataclass(frozen=True)
class Step:
    id: str
    capability: str
    arguments: dict[str, Any]
    rationale: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "capability": self.capability,
                "arguments": copy.deepcopy(self.arguments),
                "rationale": self.rationale}


@dataclass(frozen=True)
class Plan:
    goal: str
    steps: tuple[Step, ...]
    planner: str = "manual"
    schema: str = SCHEMA_1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        if not isinstance(data, dict):
            raise PlanValidationError("El plan debe ser un objeto")
        keys = set(data)
        if keys - {"goal", "steps", "planner", "schema"} or not {"goal", "steps", "planner"} <= keys:
            raise PlanValidationError("El plan debe contener goal, steps y planner")
        schema = data.get("schema", SCHEMA_1)
        if schema not in (SCHEMA_1, SCHEMA_2):
            raise PlanValidationError("Esquema de plan desconocido")
        if not isinstance(data["goal"], str) or not 0 < len(data["goal"]) <= 4000:
            raise PlanValidationError("Objetivo vacío o demasiado largo")
        if not isinstance(data["planner"], str) or len(data["planner"]) > 100:
            raise PlanValidationError("Origen del plan no válido")
        raw_steps = data["steps"]
        limit = MAX_STEPS_2 if schema == SCHEMA_2 else MAX_STEPS
        if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= limit:
            raise PlanValidationError(f"Un plan requiere entre 1 y {limit} pasos")
        steps: list[Step] = []
        for index, raw in enumerate(raw_steps):
            if not isinstance(raw, dict) or set(raw) != {"id", "capability", "arguments", "rationale"}:
                raise PlanValidationError(f"Paso {index}: campos inesperados")
            if not isinstance(raw["id"], str) or raw["id"] != f"s{index + 1}":
                raise PlanValidationError("Los pasos se identifican s1, s2, ...")
            if not isinstance(raw["capability"], str):
                raise PlanValidationError("Nombre de herramienta no válido")
            if not isinstance(raw["rationale"], str) or len(raw["rationale"]) > 600:
                raise PlanValidationError("Justificación demasiado larga")
            arguments = raw["arguments"]
            if not isinstance(arguments, dict):
                raise PlanValidationError(f"{raw['capability']}: argumentos no son objeto")
            tool = capability(raw["capability"])
            fields = tool.required | tool.optional
            extra = set(arguments) - set(fields)
            missing = set(tool.required) - set(arguments)
            if extra or missing:
                raise PlanValidationError(
                    f"{tool.name}: parámetros sobrantes {sorted(extra)} o faltantes {sorted(missing)}"
                )
            bindings = {k for k, v in arguments.items() if is_binding(v)}
            if bindings and schema != SCHEMA_2:
                raise PlanValidationError("Los bindings exigen esquema /2")
            for key, value in arguments.items():
                if key in bindings:
                    cls._check_binding(value["$from"], index, raw_steps)
                else:
                    fields[key].validate(key, value)
            steps.append(Step(id=raw["id"], capability=raw["capability"],
                              arguments=copy.deepcopy(arguments),
                              rationale=raw["rationale"]))
        return cls(goal=data["goal"], steps=tuple(steps), planner=data["planner"],
                   schema=schema)

    @staticmethod
    def _check_binding(reference: str, index: int, raw_steps: list[Any]) -> None:
        """Static binding checks: shape, earlier step, declared head route."""
        match = _BINDING_RE.fullmatch(reference)
        if match is None:
            raise BindingError(f"Referencia malformada: {reference!r}")
        source = int(match.group(1))
        if source < 1 or source > index:
            raise BindingError(f"Referencia fuera de orden: {reference!r}")
        head = match.group(2).split(".")[0]
        producer = capability(raw_steps[source - 1]["capability"])
        if head not in producer.outputs:
            raise BindingError(f"Ruta no declarada por {producer.name}: {head!r}")

    def as_dict(self) -> dict[str, Any]:
        return {"goal": self.goal, "steps": [s.as_dict() for s in self.steps],
                "planner": self.planner, "schema": self.schema}

    @property
    def digest(self) -> str:
        normalized = json.dumps(self.as_dict(), sort_keys=True, ensure_ascii=False,
                                separators=(",", ":"))
        return "sha256:" + sha256(normalized.encode("utf-8")).hexdigest()

