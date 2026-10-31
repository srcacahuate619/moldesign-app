"""MolDesign's local Whisper endpoint as a SpeechToText backend.

Moved verbatim from ``MolDesignBridge.transcribe_local`` (PLAN §5.2): the
bridge keeps a delegating shim. faster-whisper tiny, offline, authenticated.
"""

from __future__ import annotations

import httpx
from collections.abc import Awaitable, Callable

from .stt import AUDIO_LIMIT, LANGS, STTError


class MolDesignWhisper:
    def __init__(self, client: httpx.AsyncClient, token: str,
                 *, ensure_contract: Callable[[], Awaitable[None]] | None = None) -> None:
        self._client = client
        self._token = token
        self._ensure_contract = ensure_contract

    async def transcribe(self, audio_bytes: bytes, *, lang: str = "es") -> str:
        """Use MolDesign's authenticated local Whisper endpoint."""
        if not audio_bytes or len(audio_bytes) > AUDIO_LIMIT:
            raise ValueError("Audio vacío o superior al límite local de 15 MB")
        if lang not in LANGS:
            raise ValueError("Esta primera integración admite es/en")
        if self._ensure_contract is not None:
            await self._ensure_contract()
        try:
            response = await self._client.post(
                "/ai/speech-to-text", params={"lang": lang}, content=audio_bytes,
                headers={"Authorization": f"Bearer {self._token}",
                         "Content-Type": "audio/wav", "Accept": "application/json"},
                timeout=90.0,
            )
            if response.status_code >= 400 or response.is_redirect:
                raise STTError(f"Transcripción local falló (HTTP {response.status_code})")
            value = response.json().get("text", "")
            if not isinstance(value, str):
                raise STTError("Formato de transcripción inesperado")
            return value
        except (httpx.RequestError, ValueError) as exc:
            raise STTError("No se pudo transcribir el audio local") from exc
