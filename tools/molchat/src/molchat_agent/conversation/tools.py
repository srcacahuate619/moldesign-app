"""Minimal tool backend for the deterministic turn.

Bridge scaffolding: the typed ``properties()`` call the engine needs now.
Evolves into ``tools/`` (tool-packs + catalog) in Fase 3. ``QualityBackend``
serves recorded RDKit fixtures so the quality suite runs offline and
deterministically; a ``PlatformBackend`` over HTTP replaces it later.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class ToolError(RuntimeError):
    """A tool failed. The engine answers with abstention, never a number."""


@dataclass
class MoleculeRecord:
    name: str
    smiles: str
    props: dict[str, Any] = field(default_factory=dict)
    druglikeness: dict[str, Any] | None = None
    source: str = "fixtures RDKit grabados"
    verified_values: set[float] = field(default_factory=set)
    methods: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for value in self.props.values():
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                self.verified_values.add(float(value))


class ToolBackend(Protocol):
    async def properties(self, smiles: str) -> MoleculeRecord: ...
    def name_for(self, smiles: str) -> str | None: ...


class PlatformBackend:
    """Compute against the authenticated, versioned MolDesign contract.

    Unknown versions, missing capabilities and malformed results abstain.
    No demo or cached scientific values are used as a fallback.
    """

    def __init__(self, bridge: Any) -> None:
        self._bridge = bridge

    def with_token(self, token: str | None) -> "PlatformBackend":
        return PlatformBackend(self._bridge.with_token(token))

    def name_for(self, smiles: str) -> str | None:
        return None

    async def properties(self, smiles: str) -> MoleculeRecord:
        import httpx

        if not self._bridge.token:
            raise ToolError("Se necesita una sesión de MolDesign para calcular propiedades")
        headers = {"Authorization": f"Bearer {self._bridge.token}"}
        try:
            contract = await self._bridge.client.get('/molchat-host/contract', headers=headers)
            if contract.status_code != 200 or len(contract.content) > 65536:
                raise ToolError("MolDesign no ofrece el contrato de propiedades")
            data = contract.json()
            if (not isinstance(data, dict) or data.get('contract') != 'moldesign.molchat/1'
                    or not isinstance(data.get('capabilities'), list)
                    or 'properties/1' not in data['capabilities']):
                raise ToolError("Contrato de MolDesign incompatible o capacidad ausente")
            response = await self._bridge.client.post(
                '/molchat-host/properties', headers=headers, json={'smiles': smiles})
            if response.status_code != 200 or len(response.content) > 65536:
                raise ToolError(f"MolDesign no calculó las propiedades (HTTP {response.status_code})")
            result = response.json()
            if not isinstance(result, dict) or result.get('contract') != 'properties/1':
                raise ToolError("Respuesta de propiedades incompatible")
            props = result.get('properties')
            keys = ('mw', 'logp', 'tpsa', 'hbd', 'hba', 'rot_bonds', 'heavy_atoms', 'rings')
            if not isinstance(props, dict) or any(
                isinstance(props.get(k), bool) or not isinstance(props.get(k), (int, float))
                or not math.isfinite(props[k]) for k in keys
            ):
                raise ToolError("MolDesign devolvió propiedades incompletas")
            canonical = result.get('canonical_smiles')
            source = result.get('source')
            warnings = result.get('warnings')
            if (not isinstance(canonical, str) or not canonical or not isinstance(source, str)
                    or not source or not isinstance(warnings, list)
                    or not all(isinstance(w, str) for w in warnings)):
                raise ToolError("MolDesign no declaró la identidad o procedencia")
            if warnings:
                source += ' | Avisos: ' + '; '.join(warnings)
            methods = result.get('methods', {})
            if not isinstance(methods, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in methods.items()):
                methods = {}
            return MoleculeRecord(name=canonical, smiles=canonical,
                                  props={k: props[k] for k in keys}, source=source,
                                  methods=methods, warnings=warnings)
        except (httpx.RequestError, ValueError) as exc:
            raise ToolError("No se pudo verificar o consultar MolDesign") from exc


class QualityBackend:
    """Fixture-backed backend for tests and the quality suite."""

    def __init__(self, fixtures_path: str | Path, *,
                 source: str = "fixtures RDKit grabados") -> None:
        payload = json.loads(Path(fixtures_path).read_text(encoding="utf-8"))
        self._source = source
        self._by_smiles: dict[str, dict] = {}
        self.calls: list[tuple[str, str]] = []
        for entry in payload["molecules"]:
            record = {"name": entry["name"], "smiles": entry["smiles"],
                      "props": entry["properties"],
                      "druglikeness": entry.get("druglikeness")}
            self._by_smiles[entry["smiles"]] = record
            if entry.get("canonical"):
                self._by_smiles.setdefault(entry["canonical"], record)

    async def properties(self, smiles: str) -> MoleculeRecord:
        self.calls.append(("properties", smiles))
        record = self._by_smiles.get((smiles or "").strip())
        if record is None:
            raise ToolError(f"sin datos registrados para {smiles!r}")
        return MoleculeRecord(name=record["name"], smiles=record["smiles"],
                              props=dict(record["props"]),
                              druglikeness=record["druglikeness"],
                              source=self._source)

    def name_for(self, smiles: str) -> str | None:
        record = self._by_smiles.get((smiles or "").strip())
        return record["name"] if record else None
