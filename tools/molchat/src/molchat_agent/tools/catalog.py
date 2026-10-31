"""Capability registry: versioned contracts with risk and epistemics.

Every capability declares its HTTP contract, risk class, epistemic class,
provenance, and the output routes bindings may read. Tool-packs register
here (`moldesign` today, `molcy`/`reference` later); planners only ever
see read-only entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable
from urllib.parse import quote
import re


class PlanValidationError(ValueError):
    """An action fails the scientific capability contract."""


class EpistemicClass(str, Enum):
    CALCULATION = "calculation"
    PERSISTED = "persisted"
    INFERENCE = "inference"
    EXTERNAL = "external"
    EXPLANATION = "explanation"


RISKS = ("read", "write", "approval_required")
RESPONSE_KINDS = ("json", "bytes", "sse")


@dataclass(frozen=True)
class FieldSpec:
    kind: type
    max_length: int | None = None
    minimum: int | None = None
    maximum: int | None = None
    pattern: str | None = None
    location: str = "auto"  # auto | query | body (path comes from path_fields)

    def validate(self, key: str, value: Any) -> None:
        if self.kind is int:
            if type(value) is not int:
                raise PlanValidationError(f"{key}: se necesita un entero")
            if self.minimum is not None and value < self.minimum:
                raise PlanValidationError(f"{key}: fuera de rango")
            if self.maximum is not None and value > self.maximum:
                raise PlanValidationError(f"{key}: fuera de rango")
        elif self.kind is str:
            if not isinstance(value, str) or not value.strip():
                raise PlanValidationError(f"{key}: se necesita texto no vacío")
            if self.max_length is not None and len(value) > self.max_length:
                raise PlanValidationError(f"{key}: demasiado largo")
            if self.pattern and not re.fullmatch(self.pattern, value):
                raise PlanValidationError(f"{key}: formato no válido")
        else:
            raise TypeError("Tipo de contrato no soportado")

    def json_schema(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": "integer" if self.kind is int else "string"}
        if self.max_length is not None:
            result["maxLength"] = self.max_length
        if self.minimum is not None:
            result["minimum"] = self.minimum
        if self.maximum is not None:
            result["maximum"] = self.maximum
        if self.pattern is not None:
            result["pattern"] = self.pattern
        return result


@dataclass(frozen=True)
class Capability:
    name: str
    description: str
    method: str
    path: str
    required: dict[str, FieldSpec]
    optional: dict[str, FieldSpec]
    risk: str = "read"
    path_fields: tuple[str, ...] = ()
    version: str = "1"
    epistemic_class: EpistemicClass = EpistemicClass.PERSISTED
    provenance: str = ""
    # Declared output heads a binding may read ("s2.task_id" needs "task_id").
    outputs: tuple[str, ...] = ()
    # json (parsed body), bytes (raw artefact), sse (collected data events).
    response: str = "json"
    # Custom JSON body builder (dossier projection); None = remaining params.
    body_builder: Callable[[dict[str, Any]], dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if self.risk not in RISKS:
            raise ValueError(f"{self.name}: riesgo desconocido {self.risk!r}")
        if self.response not in RESPONSE_KINDS:
            raise ValueError(f"{self.name}: respuesta desconocida {self.response!r}")

    def validate(self, arguments: dict[str, Any]) -> None:
        if not isinstance(arguments, dict):
            raise PlanValidationError(f"{self.name}: argumentos no son objeto")
        fields = self.required | self.optional
        extra = set(arguments) - set(fields)
        missing = set(self.required) - set(arguments)
        if extra or missing:
            raise PlanValidationError(
                f"{self.name}: parámetros sobrantes {sorted(extra)} o faltantes {sorted(missing)}"
            )
        for key, value in arguments.items():
            fields[key].validate(key, value)

    def request(self, arguments: dict[str, Any]
                ) -> tuple[str, str, dict[str, Any], dict[str, Any] | None, str]:
        """(method, path, query, body, response_kind) for the bridge."""
        self.validate(arguments)
        path = self.path
        for fname in self.path_fields:
            path = path.replace("{" + fname + "}", quote(str(arguments[fname]), safe=""))
        rest = {k: v for k, v in arguments.items() if k not in self.path_fields}
        fields = self.required | self.optional
        query: dict[str, Any] = {}
        body_params: dict[str, Any] = {}
        for key, value in rest.items():
            location = fields[key].location
            if location == "auto":
                location = "query" if self.method == "GET" else "body"
            (query if location == "query" else body_params)[key] = value
        if self.body_builder is not None:
            body: dict[str, Any] | None = self.body_builder(dict(arguments))
        elif self.method == "GET" or not body_params:
            body = None
        else:
            body = body_params
        return self.method, path, query, body, self.response

    def as_catalog_entry(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "risk": self.risk,
            "epistemic_class": self.epistemic_class.value,
            "provenance": self.provenance,
            "parameters": {
                "type": "object",
                "properties": {
                    key: spec.json_schema()
                    for key, spec in (self.required | self.optional).items()
                },
                "required": list(self.required),
                "additionalProperties": False,
            },
        }


_REGISTRY: dict[str, Capability] = {}


def register(capability: Capability) -> Capability:
    if not capability.provenance:
        raise ValueError(f"{capability.name}: sin procedencia declarada")
    _REGISTRY[capability.name] = capability
    return capability


def capability(name: str) -> Capability:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise PlanValidationError(f"Herramienta no permitida: {name}") from exc


def catalog() -> dict[str, Capability]:
    return dict(_REGISTRY)


def read_only_names() -> list[str]:
    return sorted(n for n, c in _REGISTRY.items() if c.risk == "read")
