"""Local STT with faster-whisper: the sidecar's own offline transcriber.

Fallback for when the platform endpoint cannot transcribe (e.g. a MolDesign
build without faster-whisper answers 501). The model loads lazily on first
use; transcription runs in a worker thread because faster-whisper is sync.
Text only ever comes back — the caller confirms it before it is a turn.
"""

from __future__ import annotations

import asyncio
import io
from typing import Any, Callable

from ..bridge import BridgeError
from .stt import AUDIO_LIMIT, LANGS, STTError
from .vocabulary import initial_prompt


def faster_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


class LocalWhisperSTT:
    """SpeechToText over a local faster-whisper model (default: tiny)."""

    def __init__(self, model_size: str = "tiny",
                 model_factory: Callable[..., Any] | None = None) -> None:
        self._model_size = model_size or "tiny"
        self._factory = model_factory
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            factory = self._factory
            if factory is None:
                from faster_whisper import WhisperModel
                factory = WhisperModel
            self._model = factory(self._model_size, device="cpu",
                                  compute_type="int8")
        return self._model

    def _transcribe_sync(self, audio_bytes: bytes, lang: str) -> str:
        model = self._load()
        segments, _info = model.transcribe(
            io.BytesIO(audio_bytes), language=lang,
            initial_prompt=initial_prompt(lang))
        return "".join(segment.text for segment in segments).strip()

    async def transcribe(self, audio_bytes: bytes, *, lang: str = "es") -> str:
        if not audio_bytes or len(audio_bytes) > AUDIO_LIMIT:
            raise ValueError("Audio vacío o superior al límite local de 15 MB")
        if lang not in LANGS:
            raise ValueError("Esta primera integración admite es/en")
        try:
            return await asyncio.to_thread(self._transcribe_sync, audio_bytes, lang)
        except ImportError as exc:
            raise STTError("faster-whisper no está instalado en este equipo") from exc


class ChainSTT:
    """Try each STT backend in order; the first success wins.

    Platform first (its Whisper is the default), local second. A backend
    that answers with an error (e.g. HTTP 501 without faster-whisper) falls
    through to the next; if every backend fails, the last error propagates.
    """

    def __init__(self, backends: list[Any]) -> None:
        if not backends:
            raise ValueError("ChainSTT necesita al menos un backend")
        self._backends = backends

    async def transcribe(self, audio_bytes: bytes, *, lang: str = "es") -> str:
        last: Exception | None = None
        for backend in self._backends:
            try:
                return await backend.transcribe(audio_bytes, lang=lang)
            except (BridgeError, STTError, ValueError, RuntimeError) as exc:
                last = exc
        assert last is not None
        raise last
