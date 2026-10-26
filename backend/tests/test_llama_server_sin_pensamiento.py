"""Las tres llamadas a llama-server apagan el pensamiento de la plantilla.

EL FALLO. Qwen3.5 (el modelo «Avanzado» que sustituye a Phi-3.5 Mini) piensa
por defecto y llama-server separa ese texto en `reasoning_content`, que MolChat
no enseña. Con el tope de 128 tokens del modo Rápido, el pensamiento se los
comía todos: medido el 2026-10-10 con el `local_llm` anterior y el llama-server
b10199 que viaja, el streaming devolvía 0 caracteres. Con
`chat_template_kwargs = {"enable_thinking": False}` responde en ~7 s en CPU.
"""
from __future__ import annotations

import json

import httpx
import pytest

from services.ai import local_llm
from services.ai.local_llm import LocalLLM

CUERPOS: list[dict] = []


class _ProcesoVivo:
    """Un llama-server que «está vivo» sin existir; la limpieza de salida lo cierra."""

    pid = 1

    def poll(self):
        return None

    def terminate(self):
        pass

    def kill(self):
        pass

    def wait(self, timeout=None):
        return 0


def _respuesta(request: httpx.Request) -> httpx.Response:
    cuerpo = json.loads(request.content)
    CUERPOS.append(cuerpo)
    if cuerpo.get("stream"):
        sse = 'data: {"choices":[{"delta":{"content":"hola"}}]}\n\ndata: [DONE]\n\n'
        return httpx.Response(200, content=sse.encode(), headers={"Content-Type": "text/event-stream"})
    return httpx.Response(200, json={"choices": [{"message": {"content": "hola", "tool_calls": []}}]})


@pytest.fixture
def llm(monkeypatch):
    CUERPOS.clear()
    transporte = httpx.MockTransport(_respuesta)
    cliente, cliente_async = httpx.Client, httpx.AsyncClient
    monkeypatch.setattr(local_llm.httpx, "Client", lambda *a, **k: cliente(*a, transport=transporte, **k))
    monkeypatch.setattr(local_llm.httpx, "AsyncClient", lambda *a, **k: cliente_async(*a, transport=transporte, **k))
    modelo = LocalLLM()
    modelo._loaded = True
    modelo._process = _ProcesoVivo()
    modelo._port = 8499
    return modelo


MENSAJES = [{"role": "user", "content": "hola"}]


def _sin_pensamiento(cuerpo: dict) -> bool:
    return cuerpo.get("chat_template_kwargs", {}).get("enable_thinking") is False


@pytest.mark.asyncio
async def test_streaming(llm):
    texto = "".join([t async for t in llm.generate_stream(messages=MENSAJES, max_tokens=128)])
    assert texto == "hola"
    assert _sin_pensamiento(CUERPOS[-1])


def test_sin_streaming(llm):
    assert llm.generate(messages=MENSAJES, max_tokens=128) == "hola"
    assert _sin_pensamiento(CUERPOS[-1])


def test_con_herramientas(llm):
    llm.generate_with_tools(messages=MENSAJES, tools=[], max_tokens=128)
    assert _sin_pensamiento(CUERPOS[-1])
