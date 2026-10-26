"""Los errores de los proveedores en la nube son avisos que dicen qué hacer.

EL FALLO. Claude, Gemini y los compatibles con OpenAI devolvían sus errores
como texto de la respuesta —«Error API (401): …», «Error Gemini (400)», «Error en
Claude API: …»—: MolChat los pintaba como si los hubiera escrito él, se guardaban
en la conversación y no decían qué hacer (¿la clave?, ¿el modelo?, ¿el saldo?).
Ahora salen como `__WARNING__:` —la banda amarilla del chat— con la causa y el
remedio, y sin la credencial.
"""
from __future__ import annotations

import httpx
import pytest

from services.ai.providers import gemini_provider, openai_provider
from services.ai.providers.base import ProviderConfig, aviso_de_error_http
from services.ai.providers.claude_provider import ClaudeProvider
from services.ai.providers.gemini_provider import GeminiProvider
from services.ai.providers.openai_provider import OpenAIProvider

MENSAJES = [{"role": "system", "content": "s"}, {"role": "user", "content": "hola"}]


@pytest.mark.parametrize(
    ("status", "detalle", "esperado"),
    [
        (401, "invalid x-api-key", "rechazó la clave de API"),
        (403, "forbidden", "rechazó la clave de API"),
        (400, "API key not valid. Please pass a valid API key.", "rechazó la clave de API"),
        (404, "model not found", "no reconoce el modelo «m-1»"),
        (429, "rate limit", "no tiene saldo"),
        (503, "overloaded", "fallo de su lado"),
        (418, "teapot", "respondió con un error (418)"),
    ],
)
def test_cada_estado_dice_que_hacer(status, detalle, esperado):
    aviso = aviso_de_error_http("Prov", status, detalle, "m-1")
    assert aviso.startswith("__WARNING__:")
    assert esperado in aviso


def test_el_detalle_no_lleva_la_credencial():
    aviso = aviso_de_error_http("Prov", 401, "bad key in https://x.io/v1?api_key=sk-SECRETO", "m")
    assert "sk-SECRETO" not in aviso


def _transporte(monkeypatch, modulo, status: int, cuerpo: dict):
    original = httpx.AsyncClient

    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=cuerpo)

    monkeypatch.setattr(
        modulo.httpx, "AsyncClient",
        lambda *a, **k: original(*a, transport=httpx.MockTransport(responder), **k),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [True, False])
async def test_openai_compatible_401_es_un_aviso_de_clave(monkeypatch, stream):
    _transporte(monkeypatch, openai_provider, 401, {"error": {"message": "Incorrect API key"}})
    p = OpenAIProvider(ProviderConfig(api_key="sk-x", base_url="https://api.groq.com/openai/v1", model="m"))
    tokens = [t async for t in p.chat(MENSAJES, stream=stream)]
    assert len(tokens) == 1 and tokens[0].startswith("__WARNING__:")
    assert "rechazó la clave de API" in tokens[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [True, False])
async def test_gemini_404_es_un_aviso_de_modelo(monkeypatch, stream):
    _transporte(monkeypatch, gemini_provider, 404, {"error": {"message": "models/x is not found"}})
    p = GeminiProvider(ProviderConfig(api_key="g-x", model="gemini-viejo"))
    tokens = [t async for t in p.chat(MENSAJES, stream=stream)]
    assert len(tokens) == 1 and tokens[0].startswith("__WARNING__:")
    assert "no reconoce el modelo «gemini-viejo»" in tokens[0]


@pytest.mark.asyncio
async def test_claude_autenticacion_fallida_es_un_aviso_de_clave(monkeypatch):
    import anthropic

    peticion = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.AuthenticationError(
        "invalid x-api-key", response=httpx.Response(401, request=peticion), body=None
    )

    class _Mensajes:
        async def create(self, **_):
            raise error

    class _Cliente:
        def __init__(self, **_):
            self.messages = _Mensajes()

    monkeypatch.setattr(anthropic, "AsyncAnthropic", _Cliente)
    p = ClaudeProvider(ProviderConfig(api_key="sk-ant-x", model="claude-x"))
    tokens = [t async for t in p.chat(MENSAJES)]
    assert len(tokens) == 1 and tokens[0].startswith("__WARNING__:")
    assert "rechazó la clave de API (401)" in tokens[0]
