"""Estado local y compresión determinista de conversaciones MolChat."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any


def get_adaptive_params(mode: str = "speed") -> tuple[int, int, int]:
    """Presupuesto de contexto alineado con el servidor local de 16k tokens."""
    keep = 6 if mode == "speed" else 12
    n_ctx = 16384
    return keep, keep, n_ctx


@dataclass
class Conversation:
    """Estado de una conversación, independiente de providers y tools."""

    id: str
    #: Cuenta propietaria. MOLCHAT-BE-004: sin esto la conversación —y su
    #: `molecule_context`, que lleva el caso y la molécula— era de todos.
    #: `None` sólo en filas anteriores a la columna (D-07).
    user_id: str | None = None
    messages: list[dict[str, str]] = field(default_factory=list)
    summary: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    molecule_context: dict[str, Any] | None = None
    fallback_provider: str | None = None
    allowed_smiles_web: set[str] = field(default_factory=set)
    #: MOLCHAT-BE-008. `_persist_conv` corre después de que el modelo contestó,
    #: así que un fallo de disco no puede tumbar el turno — pero tampoco puede
    #: pasar en silencio. Queda marcado aquí y el turno lo declara.
    persistencia_degradada: bool = False
    persistencia_error: str | None = None

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self.updated_at = time.time()

    def estimated_tokens(self) -> int:
        return sum(int(len(message.get("content", "")) * 0.45) for message in self.messages)

    def to_list(self) -> list[dict[str, str]]:
        return self.messages

    def get_recent_and_compressed(self, current_query: str = "") -> tuple[list[dict], str]:
        """Conserva contexto relevante y comprime el historial más antiguo."""
        keep_recent, _, _ = get_adaptive_params()
        noise_words = {
            "gracias", "ok", "bien", "perfecto", "excelente", "dale", "hola",
            "buenos días", "buenas tardes", "buenas", "sí", "si", "no",
            "gracias!", "ok.", "vale", "genial",
        }
        meaningful = []
        for message in self.messages:
            content = message.get("content", "").strip().lower()
            is_noise = (
                len(content) < 8
                or content in noise_words
                or content.rstrip(".! ") in noise_words
            )
            if not is_noise:
                meaningful.append(message)

        if len(meaningful) <= keep_recent + 5:
            return self.messages, ""

        if current_query:
            query_terms = set(current_query.lower().split())
            scored = []
            for index, message in enumerate(meaningful):
                content = message.get("content", "").lower()
                overlap = sum(1 for term in query_terms if term in content) if query_terms else 0
                recency = (index - len(meaningful)) / max(len(meaningful), 1)
                scored.append((overlap + recency * 0.5, message))
            scored.sort(key=lambda item: item[0], reverse=True)
            recent = [message for _, message in scored[:keep_recent]]
        else:
            recent = meaningful[-keep_recent:]

        if self.summary:
            return recent, self.summary

        old = meaningful[:-keep_recent]
        compressed = self._quick_compress(old)
        self.summary = compressed
        return recent, compressed

    @staticmethod
    def _quick_compress(messages: list[dict]) -> str:
        temas = set()
        preguntas = []
        molecules = set()
        targets = set()
        facts = {}
        for message in messages:
            content = message.get("content", "")
            role = message.get("role", "")
            if role == "user":
                preguntas.append(content[:100])
                continue
            if role == "assistant":
                facts_pat = [
                    (r"afinidad\s*(?:de|:)?\s*([-\d.]+)\s*kcal", "aff"),
                    (r"score\s*(?:total|general)?\s*(?:de|:)?\s*(\d+)\s*/100", "score"),
                    (r"(\d+\.?\d*)\s*Da\b", "mw"),
                    (r"log\s*[pP]\s*(?:de|:)?\s*([-\d.]+)", "logp"),
                ]
                for pattern, key in facts_pat:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match and key not in facts:
                        facts[key] = match.group(1)
            lowered = content.lower()
            for molecule in ("aspirina", "ibuprofeno", "paracetamol", "cafeina"):
                if molecule in lowered:
                    molecules.add(molecule)
            for target in ("5-ht1a", "7e2y", "factor xa", "egfr", "gpcr"):
                if target in lowered:
                    targets.add(target.upper())
            for keyword in (
                "afinidad", "docking", "score", "lipinski", "admet", "logp", "tpsa",
                "pains", "hotspot", "selectividad", "solubilidad", "toxicidad", "sintesis",
            ):
                if keyword in lowered:
                    temas.add(keyword)
        parts = [f"Charla anterior ({len(messages)} msgs)"]
        if molecules:
            parts.append(f"mols: {', '.join(sorted(molecules))}")
        if targets:
            parts.append(f"targets: {', '.join(sorted(targets))}")
        if facts:
            parts.append(f"datos: {', '.join(f'{key}={value}' for key, value in facts.items())}")
        if temas:
            parts.append(f"temas: {', '.join(sorted(temas)[:6])}")
        if preguntas:
            parts.append(f"ultimas: {' | '.join(preguntas[-2:])}")
        return (". ".join(parts))[:500]
