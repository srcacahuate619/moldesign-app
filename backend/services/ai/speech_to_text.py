"""
services/ai/speech_to_text.py

Transcripción de audio local usando faster-whisper + modelo tiny (~75 MB).
Funciona 100% offline. Sin API keys. Sin internet.

Modelos disponibles (auto-descarga de HuggingFace):
  tiny:  75 MB, ~0.5-1s por utterance, precisión aceptable
  base: 145 MB, ~1-2s, mejor precisión
  small: 500 MB, ~2-4s, buena precisión (recomendado si sobra espacio)

Uso:
  transcriber = get_transcriber()
  text = transcriber.transcribe(audio_bytes, lang="es")
"""

from __future__ import annotations

import threading
import tempfile
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)

_MODEL_SIZE = "tiny"
_MODEL_DIR = Path(__file__).parent.parent.parent.parent / "models" / "whisper"


class WhisperTranscriber:
    def __init__(self):
        self._model = None
        self._ready = False
        self._load_error: str | None = None
        self._model_size = _MODEL_SIZE

    def _ensure_model_dir(self):
        _MODEL_DIR.mkdir(parents=True, exist_ok=True)

    def load(self) -> bool:
        if self._ready:
            return True
        if self._load_error:
            return False

        with threading.Lock():
            if self._ready:
                return True
            try:
                from faster_whisper import WhisperModel
                self._ensure_model_dir()

                compute_type = "int8"
                try:
                    import torch
                    if torch.cuda.is_available():
                        compute_type = "float16"
                except ImportError:
                    pass

                self._model = WhisperModel(
                    self._model_size,
                    device="cpu",
                    compute_type=compute_type,
                    download_root=str(_MODEL_DIR),
                )
                self._ready = True
                log.info("whisper_loaded", model=self._model_size)
                return True
            except ImportError:
                self._load_error = (
                    "faster-whisper no instalado. Ejecutá: "
                    "pip install faster-whisper"
                )
                log.warning("whisper_import_error")
                return False
            except Exception as e:
                self._load_error = str(e)[:200]
                log.error("whisper_load_failed", error=str(e)[:150])
                return False

    def transcribe(self, audio_bytes: bytes, lang: str = "es") -> str:
        if not self._ready:
            if not self.load():
                return ""
        if not self._model:
            return ""

        try:
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name

            segments, info = self._model.transcribe(
                tmp_path,
                language=lang,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=300,
                ),
            )
            text = " ".join(s.text.strip() for s in segments).strip()

            try:
                Path(tmp_path).unlink()
            except Exception:
                pass

            return text
        except Exception as e:
            log.warning("whisper_transcribe_failed", error=str(e)[:100])
            return ""

    def transcribe_chunk(self, audio_chunks: list[bytes], lang: str = "es") -> str:
        """Transcribir múltiples chunks concatenados."""
        if not audio_chunks:
            return ""
        combined = b"".join(audio_chunks)
        return self.transcribe(combined, lang)


_transcriber: WhisperTranscriber | None = None
_trans_lock = threading.Lock()


def get_transcriber() -> WhisperTranscriber:
    global _transcriber
    if _transcriber is None:
        with _trans_lock:
            if _transcriber is None:
                _transcriber = WhisperTranscriber()
    return _transcriber


def is_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False
