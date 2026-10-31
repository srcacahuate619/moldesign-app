"""Evidence blocks and numeric verification (the anti-hallucination guard).

Reimplemented from ``tool_registry.format_tool_results`` (epistemic classes,
abstention wording, ``FIN_DE_EVIDENCIA`` marker) and the numerical-claim
verification of the internal 5-layer guard. Same UI contract: the frontend
``BloqueDeEvidencia`` splits on the same marker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re

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


_NUMBER_RE = re.compile(r"-?\d+\.?\d*")


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


_NUMBER_RE = re.compile(r"-?\d+\.?\d*")
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
                      literals: frozenset[str] = frozenset()) -> tuple[str, list[str]]:
    """Replace unbacked numbers with a marker; quotable/ordinals survive."""
    problems = verify_numbers(text, verified, tolerance, quotable, literals)
    if not problems:
        return text, []
    ordinal_starts = _ordinal_starts(text) | _protected_starts(text, literals)

    def _sub(match: re.Match) -> str:
        raw = match.group(0)
        if raw in quotable or match.start(0) in ordinal_starts:
            return raw
        try:
            claimed = float(raw)
        except ValueError:
            return raw
        if any(abs(claimed - value) <= tolerance for value in verified):
            return raw
        return "[dato no verificado]"

    return _NUMBER_RE.sub(_sub, text), problems


def verify_numbers(text: str, verified: set[float], tolerance: float = 0.25,
                   quotable: frozenset[str] = frozenset(),
                   literals: frozenset[str] = frozenset()) -> list[str]:
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
            claimed = float(raw)
        except ValueError:
            continue
        if not any(abs(claimed - value) <= tolerance for value in verified):
            problems.append(f"número {raw} sin herramienta que lo respalde")
    return problems
