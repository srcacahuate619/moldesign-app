"""Evidence blocks and numeric verification (the anti-hallucination guard).

Reimplemented from ``tool_registry.format_tool_results`` (epistemic classes,
abstention wording, ``FIN_DE_EVIDENCIA`` marker) and the numerical-claim
verification of the internal 5-layer guard. Same UI contract: the frontend
``BloqueDeEvidencia`` splits on the same marker.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field
from enum import Enum
import math
import re
from typing import Any

from ..lang import tr

#: Closes the evidence block in flow text. The model never sees it in
#: history; the UI splits evidence from answer on it.
EVIDENCE_END = "<!--__FIN_DE_EVIDENCIA__-->"

#: Prefix the engine adds when it flags LLM output. Validators treat its
#: presence as a corrected (not silent) turn.
VERIFICATION_NOTE = "Nota de verificación:"


class EpistemicClass(Enum):
    CALCULATION = "cálculo"
    PERSISTED = "dato persistido"
    INFERENCE = "inferencia (predicción de modelo, no medida)"
    EXTERNAL = "recuperación externa"
    EXPLANATION = "explicación"


@dataclass
class Evidence:
    tool: str
    label: str  # which molecule (or "A=x | B=y") this block is about
    epistemic_class: EpistemicClass
    source: str
    values: dict[str, str] = field(default_factory=dict)
    error: str | None = None


#: A number in running text. Spanish writes decimals with a comma ("-9,48") and
#: models often use the typographic minus (U+2212). A hyphen is a sign only where
#: a number cannot be the end of a range: "0.22-0.54" holds two positive numbers,
#: "IC [-0.16; 0.41]" holds one negative.
_NUMBER_RE = re.compile(r"(?:(?<![\w.,)\]])[-−])?\d+(?:[.,]\d+)?")


def to_float(raw: str) -> float:
    """Parse a token found by ``_NUMBER_RE`` (decimal comma and U+2212 included)."""
    return float(raw.replace("−", "-").replace(",", "."))


def _decimals(raw: str) -> int:
    body = raw.replace(",", ".")
    return len(body.split(".", 1)[1]) if "." in body else 0


def numeric_leaves(value: Any) -> set[float]:
    """Every number a tool result carries: in numeric fields and inside its texts.

    Keys are not read ("ic95" does not make 95 a fact). A tool that returns a
    number is what backs it, so callers register this instead of picking fields
    by hand and leaving the rest to be hidden as unverified.
    """
    found: set[float] = set()
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, bool):
            continue
        if isinstance(item, (int, float)):
            if math.isfinite(item):
                found.add(float(item))
        elif isinstance(item, str):
            found.update(to_float(match.group(0)) for match in _NUMBER_RE.finditer(item))
        elif isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, (list, tuple)):
            pending.extend(item)
    return found


def _backed(raw: str, claimed: float, verified: Collection[float], tolerance: float,
            exact: Collection[float]) -> bool:
    """``verified`` keeps its wide tolerance; ``exact`` demands the claim's own precision.

    A claim backed by ``exact`` must be the stored value rounded to the decimals
    the claim writes: 0.4 and 0.39 agree, 0.3 and 0.39 do not.
    """
    if any(abs(claimed - value) <= tolerance for value in verified):
        return True
    half = 0.5 * 10 ** -_decimals(raw) + 1e-9
    return any(abs(claimed - value) <= half for value in exact)


def format_evidence(results: list[Evidence]) -> str:
    """Render tool results declaring what each one is and where it is from.

    Errors render as abstention ("no se obtuvo dato"), never as numbers.
    """
    if not results:
        return ""
    lines = ["[Sistema: resultados de herramientas ejecutadas. Cada bloque "
             "declara QUÉ es y DE DÓNDE sale:]"]
    for result in results:
        header = (f"[{result.epistemic_class.value} · {result.source}] "
                  f"{result.tool} ({result.label})")
        if result.error is not None:
            lines.append(f"{header}: no se obtuvo dato ({result.error}). "
                         "No inventes el valor: dilo y ofrece cómo obtenerlo.")
        else:
            body = ", ".join(f"{key}: {value}"
                             for key, value in result.values.items())
            lines.append(f"{header}: {body}")
    return "\n".join(lines)


def block_for_flow(evidence_text: str) -> str:
    """Evidence as emitted to the flow: closed by the end marker."""
    if not evidence_text:
        return ""
    return f"\n\n{evidence_text}\n{EVIDENCE_END}\n"


def split_flow(text: str) -> tuple[str, str]:
    """Split flow text into (evidence, answer) on the end marker."""
    if EVIDENCE_END not in text:
        return "", text
    evidence, _, answer = text.partition(EVIDENCE_END)
    return evidence.strip(), answer.strip()


_ORDINAL_RE = re.compile(r"(?:^|\n)\s*(?:#{1,6}\s+)?(?:\*\*)?\d+(?:\.(?!\d)|[):])")


def context_literals(text: str) -> set[str]:
    """Extract exact identifiers and quoted names, never bare scientific values."""
    literals = set(re.findall(r"(?<![\w.])(?:[A-Za-z][A-Za-z0-9@+=()\[\]#\\/.-]*\d[A-Za-z0-9@+=()\[\]#\\/.-]*|\d[A-Za-z][A-Za-z0-9]*|\d+(?:\.\d+){2,})(?![\w.])", text))
    for match in re.finditer(r'[`"“]([^`"”\n]{2,200})[`"”]', text):
        value = match.group(1).strip()
        if re.search(r"[A-Za-z]", value) and re.search(r"\d", value):
            literals.add(value)
    return literals


def _protected_starts(text: str, literals: frozenset[str]) -> set[int]:
    starts: set[int] = set()
    for literal in literals:
        if not literal:
            continue
        for match in re.finditer(r"(?<!\w)" + re.escape(literal) + r"(?!\w|\.\d)", text):
            starts.update(match.start() + number.start() for number in _NUMBER_RE.finditer(literal))
    return starts


def numbers_in(text: str) -> list[str]:
    """Raw numeric tokens in a text (query quotation detection)."""
    return [match.group(0) for match in _NUMBER_RE.finditer(text)]


def _ordinal_starts(text: str) -> set[int]:
    starts: set[int] = set()
    for match in _ORDINAL_RE.finditer(text):
        digits = re.search(r"\d+", match.group(0))
        if digits:
            starts.add(match.start(0) + digits.start(0))
    return starts


def redact_unverified(text: str, verified: set[float],
                      quotable: frozenset[str] = frozenset(),
                      tolerance: float = 0.25,
                      literals: frozenset[str] = frozenset(),
                      exact: Collection[float] = frozenset()) -> tuple[str, list[str]]:
    """Replace unbacked numbers with a marker; quotable/ordinals survive."""
    problems = verify_numbers(text, verified, tolerance, quotable, literals, exact)
    if not problems:
        return text, []
    ordinal_starts = _ordinal_starts(text) | _protected_starts(text, literals)

    def _sub(match: re.Match) -> str:
        raw = match.group(0)
        if raw in quotable or match.start(0) in ordinal_starts:
            return raw
        try:
            claimed = to_float(raw)
        except ValueError:
            return raw
        if _backed(raw, claimed, verified, tolerance, exact):
            return raw
        return tr("[dato no verificado]", "[unverified value]")

    return _NUMBER_RE.sub(_sub, text), problems


def verify_numbers(text: str, verified: set[float], tolerance: float = 0.25,
                   quotable: frozenset[str] = frozenset(),
                   literals: frozenset[str] = frozenset(),
                   exact: Collection[float] = frozenset()) -> list[str]:
    """Every number in ``text`` must match a verified tool value.

    Two principled exemptions (both observed against Qwen 1.5B):
    - ``quotable``: numbers verbatim in the user query ("que es 12345?" ->
      "12345 es un número") are quotation, not fabrication.
    - list ordinals ("1. Identificar…"): enumeration markers, not claims.
      A value smuggled AS an ordinal ("1802. …") is the accepted residual.
    Returns problem descriptions (empty = clean). Deterministic answers
    never fail this: they are built FROM the verified values.
    """
    problems: list[str] = []
    ordinal_starts = _ordinal_starts(text) | _protected_starts(text, literals)
    for match in _NUMBER_RE.finditer(text):
        raw = match.group(0)
        if raw in quotable:
            continue
        if match.start(0) in ordinal_starts:
            continue
        try:
            claimed = to_float(raw)
        except ValueError:
            continue
        if not _backed(raw, claimed, verified, tolerance, exact):
            problems.append(f"número {raw} sin herramienta que lo respalde")
    return problems
