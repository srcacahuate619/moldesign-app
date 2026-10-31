"""Transcription evaluation: did the expected chemical terms survive?

Pure scoring (unit-tested): term recall over word boundaries, case- and
accent-insensitive, plus the list of missed terms. The live leg needs real
audio + a terms file and lives in ``scripts/eval_stt.py`` (operator-run,
skips without inputs — same honesty rule as the contract suite).
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


def _fold(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class TranscriptionScore:
    expected: int
    found: int
    recall: float
    missed: tuple[str, ...]

    def as_dict(self) -> dict:
        return {"expected": self.expected, "found": self.found,
                "recall": round(self.recall, 3), "missed": list(self.missed)}


def score_transcript(expected_terms: list[str], transcript: str) -> TranscriptionScore:
    """Recall of expected terms in a transcript (word boundaries)."""
    folded = _fold(transcript)
    missed: list[str] = []
    for term in expected_terms:
        pattern = r"\b" + re.escape(_fold(term)) + r"\b"
        if not re.search(pattern, folded):
            missed.append(term)
    found = len(expected_terms) - len(missed)
    recall = (found / len(expected_terms)) if expected_terms else 1.0
    return TranscriptionScore(expected=len(expected_terms), found=found,
                              recall=recall, missed=tuple(missed))
