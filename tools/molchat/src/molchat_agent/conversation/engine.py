"""The conversational turn: classify, tools, deterministic answers.

Flow per turn: classify → tool (typed) → deterministic responder, or
verified LLM for conceptual questions → event stream. Factual numbers are
built by code from tool values; the model explains concepts and every
number it emits is verified against tool output.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from ..providers.base import ProviderDisabled, TurnContext
from ..providers.registry import ProviderRegistry, UnknownProviderError
from . import deterministic as det
from . import intents as intent_mod
from .deterministic import MoleculeProps
from .evidence import (
    VERIFICATION_NOTE,
    EpistemicClass,
    Evidence,
    block_for_flow,
    format_evidence,
    numbers_in,
    redact_unverified,
)
from .intents import Intent
from .memory import ConversationNotFound, MemoryStore, PersistenciaFallida
from .prompts import CONCEPTUAL_SYSTEM_P1
from .tools import MoleculeRecord, ToolBackend, ToolError

_GREETING = re.compile(r"^(hola|buenas|buenos d[ií]as|buenas tardes|hey|hi|hello)[.! ]*$",
                       re.IGNORECASE)

_DEFERRALS = {
    "docking": ("El docking desde el chat llega en la Fase 3: necesita crear "
                "propuestas con aprobación humana ligada a su hash, y ese "
                "circuito aún no existe en este build."),
    "preparation": ("La comprobación previa desde el chat llega en la Fase 3, "
                    "cuando las capacidades de plataforma estén cableadas."),
    "analog": ("Los análogos y similares llegan en la Fase 5: necesitan la API "
               "de plataforma (CR-01/CR-05), no duplicar RDKit aquí."),
    "suggest": ("Las sugerencias de moléculas llegan en la Fase 5, con la API "
                "de plataforma correspondiente."),
    "molgraph": ("Las consultas al grafo molecular llegan en la Fase 5 "
                 "(decisión D-04: la ciencia vive en la plataforma)."),
    "evaluation": ("Los detalles de evaluaciones persistidas llegan en la "
                   "Fase 3, con las capacidades de informes."),
    "source": ("Las fuentes verificadas (PubChem/ChEMBL) llegan en la Fase 5, "
               "con consentimiento por destino web."),
    "design": ("No diseño moléculas a pedido con requisitos estructurales: "
               "este sistema no puede generarlas con precisión y no voy a "
               "adivinar un SMILES."),
}


@dataclass
class TurnResult:
    text: str
    intent_name: str
    events: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    latency_ms: int = 0
    used_llm: bool = False
    verified_values: set[float] = field(default_factory=set)


class ConversationEngine:
    """One owner, one registry, one tool backend, one memory."""

    def __init__(self, *, registry: ProviderRegistry, backend: ToolBackend,
                 memory: MemoryStore, user_id: str,
                 provider_id: str | None = None) -> None:
        self._registry = registry
        self._backend = backend
        self._memory = memory
        self._user_id = user_id
        self._provider_id = provider_id

    async def turn(self, conv_id: str, text: str) -> TurnResult:
        result: TurnResult | None = None
        async for event in self.turn_stream(conv_id, text):
            if event["type"] == "result":
                result = event["result"]
        assert result is not None
        return result

    async def turn_stream(self, conv_id: str, text: str) -> AsyncIterator[dict[str, Any]]:
        started = time.monotonic()
        conv = self._memory.get_conversation(conv_id, self._user_id)
        if conv is None:
            raise ConversationNotFound(conv_id)
        intent = intent_mod.classify(text)
        yield {"type": "intent", "name": intent.name, "tool": intent.tool}
        try:
            answer, evidence, used_llm = await self._route(conv_id, text, intent)
        except ToolError as exc:
            answer, evidence, used_llm = self._abstain(str(exc))
        verified: set[float] = set()
        for item in evidence:
            for value in item.values.values():
                try:
                    verified.add(float(str(value).split()[0]))
                except (ValueError, IndexError):
                    pass
        flow = block_for_flow(format_evidence(evidence)) + answer if evidence else answer
        latency_ms = int((time.monotonic() - started) * 1000)
        yield {"type": "response", "used_llm": used_llm, "latency_ms": latency_ms}
        try:
            self._memory.add_message(conv_id, self._user_id, "user", text)
            self._memory.add_message(conv_id, self._user_id, "assistant", answer)
        except PersistenciaFallida as exc:
            flow += f"\n(Nota: no se pudo guardar el turno: {exc})"
        yield {"type": "result", "result": TurnResult(
            text=flow, intent_name=intent.name, events=[],
            evidence=evidence, latency_ms=latency_ms, used_llm=used_llm,
            verified_values=verified)}

    # ── routing ──────────────────────────────────────────────────────

    async def _route(self, conv_id: str, text: str, intent: Intent
                     ) -> tuple[str, list[Evidence], bool]:
        name = intent.name
        if name == "chemical" and intent.smiles:
            return await self._chemical(conv_id, text, intent.smiles, intent.smiles_source)
        if name == "compare":
            return await self._compare(conv_id, text, intent)
        if name == "rank_session":
            return await self._rank(conv_id, text), [], False
        if name == "query_history":
            return await self._history(conv_id), [], False
        if name == "druglikeness" and intent.smiles:
            return await self._druglikeness(conv_id, text, intent.smiles)
        if name == "recall_anaphoric":
            return await self._recall(conv_id, text)
        if name == "recall_molecular":
            return await self._recall_search(text), [], False
        if name == "case_action":
            return ("No puedo crear ni modificar casos desde esta conversación. "
                    "No se ha realizado ninguna acción; usa el menú Casos de MolDesign."), [], False
        if name in ("conceptual", "unknown"):
            return await self._conceptual(conv_id, text, intent)
        if name == "invalid_smiles":
            return ("Ese texto parece un SMILES pero no es válido "
                    "estructuralmente; dime el nombre de la molécula o revisa "
                    "la sintaxis."), [], False
        if name in _DEFERRALS:
            return _DEFERRALS[name], [], False
        return ("No puedo resolver esa petición en este build: "
                "falta el dato o la herramienta."), [], False

    # ── deterministic paths ──────────────────────────────────────────

    def _display_name(self, text: str, smiles: str) -> str:
        return (intent_mod.find_name(text) or self._backend.name_for(smiles)
                or (smiles[:20] + "…" if len(smiles) > 20 else smiles))

    @staticmethod
    def _to_props(display: str, record: MoleculeRecord) -> MoleculeProps:
        props = record.props
        return MoleculeProps(
            name=display, smiles=record.smiles,
            molecular_weight=props.get("mw"), log_p=props.get("logp"),
            tpsa=props.get("tpsa"), hbd=props.get("hbd"), hba=props.get("hba"),
            rotatable_bonds=props.get("rot_bonds"),
            heavy_atoms=props.get("heavy_atoms"), rings=props.get("rings"))

    @staticmethod
    def _values_text(record: MoleculeRecord) -> dict[str, str]:
        props = record.props
        out: dict[str, str] = {}
        for label, key, prec in (("MW", "mw", 1), ("LogP", "logp", 2),
                                 ("TPSA", "tpsa", 1)):
            if props.get(key) is not None:
                out[label] = det.fmt(float(props[key]), prec)
        for label, key in (("HBD", "hbd"), ("HBA", "hba"),
                           ("RotBonds", "rot_bonds"), ("HeavyAtoms", "heavy_atoms"),
                           ("Rings", "rings")):
            if props.get(key) is not None:
                out[label] = str(props[key])
        return out

    async def _chemical(self, conv_id: str, text: str, smiles: str,
                        source: str | None) -> tuple[str, list[Evidence], bool]:
        record = await self._backend.properties(smiles)
        display = self._display_name(text, smiles)
        self._memory.record_molecule(conv_id, self._user_id, display, smiles,
                                     {"props": record.props,
                                      "druglikeness": record.druglikeness})
        self._memory.set_molecule_context(
            conv_id, self._user_id, {"name": display, "smiles": smiles})
        answer = det.build_properties_response(display, self._to_props(display, record))
        if answer is None:
            return self._abstain("la herramienta no devolvió propiedades")
        evidence = [Evidence(tool="compute_properties", label=display,
                             epistemic_class=EpistemicClass.CALCULATION,
                             source=record.source,
                             values=self._values_text(record))]
        _ = source
        return answer, evidence, False

    async def _compare(self, conv_id: str, text: str, intent: Intent
                       ) -> tuple[str, list[Evidence], bool]:
        smiles_list = intent.smiles_list or [s for s in (intent.smiles, intent.smiles_b) if s]
        if len(smiles_list) < 2:
            return ("Para comparar necesito dos moléculas con nombre o SMILES "
                    "reconocibles."), [], False
        ordered = intent_mod.find_all_names(text) or []
        records = [await self._backend.properties(smiles) for smiles in smiles_list]
        displays = [ordered[i] if i < len(ordered)
                    else self._display_name("", record.smiles)
                    for i, record in enumerate(records)]
        for display, record in zip(displays, records):
            self._memory.record_molecule(conv_id, self._user_id, display,
                                         record.smiles,
                                         {"props": record.props,
                                          "druglikeness": record.druglikeness})
        self._memory.set_molecule_context(
            conv_id, self._user_id, {"name": displays[-1], "smiles": records[-1].smiles})
        molecules = [self._to_props(display, record)
                     for display, record in zip(displays, records)]
        if len(molecules) == 2:
            answer = det.build_compare_response(
                displays[0], molecules[0], displays[1], molecules[1])
        else:
            answer = det.build_multi_compare_response(molecules)
            if answer is None:
                return self._abstain("alguna molécula falló; no armo tablas parciales")
        label = (f"A={displays[0]} | B={displays[1]}" if len(displays) == 2
                 else ", ".join(displays))
        evidence = [Evidence(tool="compare_molecules", label=label,
                             epistemic_class=EpistemicClass.CALCULATION,
                             source=records[0].source,
                             values={d: self._values_text(r).get("MW", "?") + " Da"
                                     for d, r in zip(displays, records)})]
        return answer, evidence, False

    async def _rank(self, conv_id: str, text: str) -> str:
        stored = self._memory.session_molecules(conv_id, self._user_id)
        molecules = [self._to_props(item["name"], MoleculeRecord(
            name=item["name"], smiles=item["smiles"],
            props=item["props"].get("props", item["props"])))
            for item in stored]
        answer = det.build_rank_response(text, molecules)
        if answer is not None:
            return answer
        if not molecules:
            return ("No hay moléculas registradas en esta conversación. "
                    "Calcula propiedades de alguna molécula primero.")
        return ("No entiendo qué métrica ordenar; pide menor/mayor peso, "
                "lipofilicidad, TPSA, afinidad o score.")

    async def _history(self, conv_id: str) -> str:
        stored = self._memory.session_molecules(conv_id, self._user_id)
        molecules = [self._to_props(item["name"], MoleculeRecord(
            name=item["name"], smiles=item["smiles"],
            props=item["props"].get("props", item["props"])))
            for item in stored]
        return det.build_session_history_response(molecules)

    async def _druglikeness(self, conv_id: str, text: str, smiles: str
                            ) -> tuple[str, list[Evidence], bool]:
        record = await self._backend.properties(smiles)
        display = self._display_name(text, smiles)
        self._memory.record_molecule(conv_id, self._user_id, display, smiles,
                                     {"props": record.props,
                                      "druglikeness": record.druglikeness})
        pains = None
        if record.druglikeness is not None and record.druglikeness.get("pains_evaluated"):
            pains = list(record.druglikeness.get("pains_alerts", []))
        answer = det.build_druglikeness_response(
            display, self._to_props(display, record), pains)
        if answer is None:
            return self._abstain("faltan descriptores para evaluar reglas")
        evidence = [Evidence(tool="check_druglikeness", label=display,
                             epistemic_class=EpistemicClass.CALCULATION,
                             source=record.source,
                             values=self._values_text(record))]
        return answer, evidence, False

    async def _recall(self, conv_id: str, text: str
                      ) -> tuple[str, list[Evidence], bool]:
        name = intent_mod.find_name(text)
        if name and name in intent_mod.KNOWN_SMILES:
            return await self._chemical(conv_id, text, intent_mod.KNOWN_SMILES[name],
                                        "anaphora_name")
        conv = self._memory.get_conversation(conv_id, self._user_id)
        context = conv.molecule_context if conv else None
        if context and context.get("smiles"):
            # The stored name re-resolves as display text for the rerun.
            return await self._chemical(conv_id, context.get("name", ""),
                                        context["smiles"], "anaphora_context")
        return ("¿De qué molécula hablas? Aún no mencionamos ninguna en esta "
                "conversación."), [], False

    async def _recall_search(self, text: str) -> str:
        hits = self._memory.search_messages(text, self._user_id, limit=3)
        if not hits:
            return "No encuentro ese tema en tus conversaciones."
        lines = [f"- ({hit['role']}) {hit['snippet']}" for hit in hits]
        return "Esto encontramos en tu historial:\n" + "\n".join(lines)

    # ── verified LLM path + misc ─────────────────────────────────────

    async def _conceptual(self, conv_id: str, text: str, intent: Intent) -> tuple[str, list[Evidence], bool]:
        if not text.strip():
            return "Escribe una pregunta: puedo calcular propiedades, comparar y rankear moléculas.", [], False
        if _GREETING.match(text.strip()):
            return ("Hola. Puedo calcular propiedades, comparar y rankear "
                    "moléculas, o explicar conceptos de química computacional."), [], False
        provider_id = self._provider_id or self._registry.active_id
        if provider_id is None:
            # Sin proveedor no hay respuesta conceptual: se dice, no se inventa.
            return self._abstain("no hay proveedor de IA activo: elígelo en Ajustes > Proveedores")
        try:
            reason = self._registry.block_reason(provider_id)
            provider = self._registry.get(provider_id)
        except (ProviderDisabled, UnknownProviderError) as exc:
            return self._abstain(f"proveedor no disponible: {exc}")
        if reason:
            return reason, [], False
        conv = self._memory.get_conversation(conv_id, self._user_id)
        # F2-C6: history/summaries are scientific content. A remote provider
        # gets [system, query] only, unless content consent was granted for
        # its destination. Local providers keep full context (no exfiltration).
        messages = [{"role": "system", "content": CONCEPTUAL_SYSTEM_P1}]
        if self._registry.content_granted(provider_id) and conv is not None:
            recent, summary = self._memory.recent_context(conv)
            if summary:
                messages.append({"role": "system", "content": f"Resumen: {summary}"})
            messages.extend({"role": m.get("role", "user"), "content": m.get("content", "")}
                            for m in recent[-12:])
        messages.append({"role": "user", "content": text})
        try:
            events = [event async for event in provider.chat(
                TurnContext(text=text, messages=messages))]
        except (ToolError, ValueError, RuntimeError) as exc:
            return self._abstain(f"el proveedor conceptual falló: {exc}")
        body = "".join(e.text for e in events if not e.done)
        redacted, problems = redact_unverified(
            body, set(), quotable=frozenset(numbers_in(text)))
        if problems:
            return (f"{VERIFICATION_NOTE} el modelo emitió números sin "
                    f"herramienta ({len(problems)}); se retuvieron. {redacted}"), [], True
        return body, [], True

    @staticmethod
    def _abstain(reason: str) -> tuple[str, list[Evidence], bool]:
        return (f"No puedo responder eso de forma verificada: {reason} "
                f"Dime cómo obtener el dato y lo intentamos."), [], False
