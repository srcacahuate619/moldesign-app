from __future__ import annotations

import json
import threading
import time
from typing import AsyncIterator

import httpx

from services.ai.providers.base import AIProvider, ProviderConfig, ProviderInfo
from services.ai.redaccion import redactar_secretos
from utils.logger import get_logger

log = get_logger(__name__)

# Sondeo de `/api/tags`: un resultado por dirección, válido unos segundos y compartido por `get_info` y
# `validate_config`. Al abrir la app lo pedían varias llamadas seguidas y, sin Ollama instalado, cada una tardaba 4,4 s
# en Windows (`localhost`: IPv6 y luego IPv4, medido el 2026-10-10), con el backend congelado. Un Ollama local que
# escucha acepta la conexión en milisegundos: 0,5 s para conectar basta.
_SONDEO_VALIDO_S = 15.0
_SONDEO_TIMEOUT = httpx.Timeout(3.0, connect=0.5)
_sondeos: dict[str, tuple[float, bool, list[str], str]] = {}
_sondeo_cerrojo = threading.Lock()


def _sondear_tags(base_url: str) -> tuple[bool, list[str], str]:
    """(responde, modelos, motivo) de un Ollama en `base_url`; reutiliza el último sondeo si es reciente."""
    clave = base_url.rstrip("/")
    with _sondeo_cerrojo:  # dos llamadas a la vez no sondean dos veces: la segunda espera y reutiliza
        visto = _sondeos.get(clave)
        if visto and time.monotonic() - visto[0] < _SONDEO_VALIDO_S:
            return visto[1], visto[2], visto[3]
        modelos: list[str] = []
        try:
            resp = httpx.get(f"{clave}/api/tags", timeout=_SONDEO_TIMEOUT)
            responde = resp.status_code == 200
            motivo = "OK" if responde else f"Ollama no responde en {base_url}"
            if responde:
                try:
                    modelos = [m["name"] for m in resp.json().get("models", [])]
                except Exception:
                    modelos = []
        except Exception as e:
            responde, motivo = False, f"No se pudo conectar a Ollama: {str(e)[:80]}"
        _sondeos[clave] = (time.monotonic(), responde, modelos, motivo)
        return responde, modelos, motivo


def _nombre_instalado(modelo: str, instalados: list[str]) -> str | None:
    """El nombre con que Ollama lista `modelo`, o None si no lo tiene.

    Ollama resuelve un nombre sin etiqueta a `:latest` («llama3.2» es
    «llama3.2:latest»), y así lo lista `/api/tags`.
    """
    modelo = modelo.strip()
    if not modelo:
        return None
    candidatos = {modelo} if ":" in modelo else {modelo, f"{modelo}:latest"}
    return next((m for m in instalados if m in candidatos), None)


class OllamaProvider(AIProvider):
    id = "ollama"
    name = "Ollama"
    description = "Servidor Ollama local (localhost:11434). Sin API key, requiere Ollama instalado."

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        if not self._config.base_url:
            self._config.base_url = "http://localhost:11434"
        if not self._config.model:
            self._config.model = "gemma3:1b"
        if not self._config.temperature:
            self._config.temperature = 0.1
        if not self._config.max_tokens:
            self._config.max_tokens = 4096

    def validate_config(self) -> tuple[bool, str]:
        """Disponible = Ollama responde Y tiene el modelo elegido.

        Antes bastaba con que respondiera: con el modelo por defecto sin
        descargar (`gemma3:1b`), el turno salía y volvía «Error Ollama (404)»
        escrito como si fuera la respuesta de MolChat.
        """
        url = self._config.base_url
        responde, instalados, motivo = _sondear_tags(url)
        if not responde:
            return False, (
                f"Ollama no responde en {url} ({motivo}). Ábrelo, o instálalo desde "
                "ollama.com, y vuelve a intentarlo."
            )
        if not instalados:
            return False, (
                f"Ollama responde en {url} pero no tiene ningún modelo. Descarga uno "
                "con `ollama pull <modelo>` y elígelo en Opciones ▸ Intérprete IA."
            )
        if _nombre_instalado(self._config.model, instalados) is None:
            return False, (
                f"Ollama no tiene el modelo «{self._config.model}». Elige uno de los "
                f"instalados ({', '.join(instalados[:6])}) en Opciones ▸ Intérprete IA, "
                f"o descárgalo con `ollama pull {self._config.model}`."
            )
        return True, "OK"

    def get_info(self) -> ProviderInfo:
        _, models, _ = _sondear_tags(self._config.base_url)
        # La sugerencia para el campo «Modelo»: el elegido si está instalado; si
        # no, el primero que sí lo esté. Proponer uno ausente era proponer un 404.
        sugerido = (
            _nombre_instalado(self._config.model, models)
            or (models[0] if models else self._config.model)
        )
        return ProviderInfo(
            id=self.id,
            name=self.name,
            description=self.description,
            requires_api_key=False,
            requires_base_url=True,
            default_base_url="http://localhost:11434",
            default_model=sugerido,
            available_models=models,
            configured=self.validate_config()[0],
        )

    @staticmethod
    def _aviso_de_error(status: int, cuerpo: str, modelo: str) -> str:
        """Lo que Ollama devolvió, dicho como aviso y no como respuesta."""
        detalle = cuerpo
        try:
            detalle = json.loads(cuerpo).get("error", cuerpo)
        except (ValueError, AttributeError):
            pass
        detalle = redactar_secretos(str(detalle))[:160]
        if status == 404:
            return (
                f"__WARNING__:Ollama no tiene el modelo «{modelo}» ({detalle}). "
                f"Descárgalo con `ollama pull {modelo}` o elige otro en Opciones ▸ "
                "Intérprete IA."
            )
        return f"__WARNING__:Ollama respondió con un error ({status}): {detalle}"

    async def chat(
        self,
        messages: list[dict[str, str]],
        stream: bool = False,
    ) -> AsyncIterator[str]:
        url = f"{self._config.base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self._config.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self._config.temperature,
                "num_predict": self._config.max_tokens,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                if stream:
                    async with client.stream("POST", url, json=payload) as response:
                        if response.status_code != 200:
                            cuerpo = (await response.aread()).decode("utf-8", "replace")
                            yield self._aviso_de_error(response.status_code, cuerpo, self._config.model)
                            return
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                                if "message" in data and "content" in data["message"]:
                                    yield data["message"]["content"]
                            except json.JSONDecodeError:
                                pass
                else:
                    payload["stream"] = False
                    resp = await client.post(url, json=payload, timeout=120.0)
                    if resp.status_code != 200:
                        yield self._aviso_de_error(resp.status_code, resp.text, self._config.model)
                        return
                    data = resp.json()
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
        except Exception as e:
            yield (
                f"__WARNING__:No se pudo hablar con Ollama en {self._config.base_url}: "
                f"{redactar_secretos(e)[:100]}"
            )

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._config.base_url.rstrip('/')}/api/tags")
                if resp.status_code == 200:
                    return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            pass
        return [self._config.model]
