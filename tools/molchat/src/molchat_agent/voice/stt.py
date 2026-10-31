"""SpeechToText port: audio bytes in, confirmed-later text out."""

from __future__ import annotations

from typing import Protocol

AUDIO_LIMIT = 15_000_000
LANGS = ("es", "en")


class STTError(RuntimeError):
    """Transcription failed. Carries no audio, no keys."""


class SpeechToText(Protocol):
    async def transcribe(self, audio_bytes: bytes, *, lang: str = "es") -> str:
        """Transcribe audio. Returns text only; the caller confirms it."""
        ...
