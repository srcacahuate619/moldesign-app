"""QA-016: un error 500 tiene que poder leerse desde la interfaz.

Starlette instala el manejador de `Exception` en `ServerErrorMiddleware`, por
fuera de `CORSMiddleware`. Sin cabeceras CORS, el navegador —y la ventana de
Tauri, que es otro origen que el backend— no puede leer la respuesta: `fetch`
lanza un error de red y la interfaz decía «no se pudo contactar con el motor
local de MolDesign» con el motor vivo. Lo encontró la QA del 2026-09-27 al
ejecutar una cohorte sin semilla (QA-015).
"""

from __future__ import annotations

import asyncio
import json

from starlette.requests import Request

from api.main import app, handle_unexpected_error, settings


def _peticion(origen: str | None) -> Request:
    cabeceras = [(b"origin", origen.encode())] if origen else []
    return Request({"type": "http", "method": "POST", "path": "/x", "headers": cabeceras,
                    "query_string": b"", "client": ("127.0.0.1", 1)})


def test_el_manejador_esta_registrado_para_cualquier_excepcion():
    assert app.exception_handlers.get(Exception) is handle_unexpected_error


def test_un_500_desde_un_origen_autorizado_lleva_cors():
    origen = settings.cors_origins[0]
    respuesta = asyncio.run(handle_unexpected_error(_peticion(origen), TypeError("int(None)")))

    assert respuesta.status_code == 500
    assert respuesta.headers["access-control-allow-origin"] == origen
    assert respuesta.headers["access-control-allow-credentials"] == "true"
    assert json.loads(respuesta.body)["error"] == "InternalServerError"


def test_un_origen_ajeno_no_recibe_cors():
    respuesta = asyncio.run(
        handle_unexpected_error(_peticion("https://ajeno.example"), RuntimeError("x"))
    )
    assert "access-control-allow-origin" not in respuesta.headers
