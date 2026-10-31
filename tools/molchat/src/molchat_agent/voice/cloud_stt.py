"""Cloud speech-to-text behind explicit opt-in (Fase 5).

OpenAI-compatible ``/audio/transcriptions`` over HTTPS (multipart): the same
contract served by several vendors, so the operator chooses the destination.
Audio leaves the machine ONLY when all three hold: ``MOLCHAT_CLOUD_STT=1``,
a configured base URL + key, and a session holding the ``transcribe`` scope.
The UI declares the active STT backend and warns while it is cloud.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import httpx

from .stt import AUDIO_LIMIT, LANGS, STTError


class CloudSTT:
    def __init__(self, *, base_url: str, api_key: str, model: str,
                 client: httpx.AsyncClient | None = None) -> None:
        base = (base_url or "").strip().rstrip("/")
        url = urlsplit(base)
        if url.scheme != "https" or not url.hostname:
            raise ValueError("STT en nube exige una base https explícita")
        if not api_key:
            raise ValueError("STT en nube exige clave")
        if not model.strip():
            raise ValueError("STT en nube exige modelo")
        self._base_url = base
        self._api_key = api_key
        self._model = model.strip()
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "CloudSTT":
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def destination(self) -> str:
        return urlsplit(self._base_url).hostname or ""

    async def transcribe(self, audio_bytes: bytes, *, lang: str = "es") -> str:
        if not audio_bytes or len(audio_bytes) > AUDIO_LIMIT:
            raise ValueError("Audio vacío o superior al límite de 15 MB")
        if lang not in LANGS:
            raise ValueError("Esta primera integración admite es/en")
        client = self._client or httpx.AsyncClient(timeout=90.0, trust_env=False)
        try:
            response = await client.post(
                f"{self._base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                files={"file": ("audio.wav", audio_bytes, "audio/wav")},
                data={"model": self._model, "language": lang},
            )
            if response.status_code >= 400:
                raise STTError(f"Transcripción en nube falló (HTTP {response.status_code})")
            value = response.json().get("text", "")
            if not isinstance(value, str):
                raise STTError("Formato de transcripción inesperado")
            return value
        except (httpx.RequestError, ValueError) as exc:
            raise STTError("No se pudo transcribir en la nube") from exc
        finally:
            if self._client is None:
                await client.aclose()
