"""Host mínimo: estado público, sesiones atadas a la cuenta, 503 honesto.

El lanzador se sustituye por un doble: su ciclo de vida real ya está
probado contra la copia vendorizada (`test_molchat_host_lanzador.py`); aquí
importa el contrato HTTP (quién puede pedir, qué recibe, qué falla).
"""

import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_current_user
from api.routers import molchat_host
from core.config import get_settings
from services.molchat_host import launcher, sesion


class DobleLanzador:
    def __init__(self, url="http://127.0.0.1:59999", roto=False):
        self._url = url
        self._roto = roto
        self.arranques = 0

    def arrancar(self):
        self.arranques += 1
        if self._roto:
            raise launcher.LanzadorError("sidecar roto (fixture)")
        return self._url

    def estado(self):
        return {"disponible": True, "motivo": "ok", "en_marcha": True,
                "url": self._url, "version": "0.1.0", "commit": "abc123",
                "contrato": "moldesign.molchat/1"}


@pytest.fixture
def cliente(monkeypatch):
    doble = DobleLanzador()
    monkeypatch.setattr(launcher, "obtener_lanzador", lambda *a, **k: doble)
    sesion.fijar_secreto_host(b"test-secret-32-bytes-0123456789ab")
    app = FastAPI()
    app.include_router(molchat_host.router)
    usuario = SimpleNamespace(id=uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: usuario
    cliente = TestClient(app)
    cliente.doble = doble
    cliente.usuario = usuario
    return cliente


def test_status_sin_autenticar_cuenta_estado(cliente):
    respuesta = cliente.get("/molchat-host/status")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["disponible"] is True
    assert cuerpo["url"] == "http://127.0.0.1:59999"
    assert "token" not in cuerpo and "secreto" not in cuerpo


def test_session_acuna_para_la_cuenta_que_pide(cliente):
    respuesta = cliente.post("/molchat-host/session")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["url"] == "http://127.0.0.1:59999"
    assert cuerpo["expira_en_s"] == get_settings().molchat_ttl_s
    assert cuerpo["scopes"] == sorted(molchat_host.PERMISOS_DE_UI)
    assert cliente.doble.arranques == 1  # levantó bajo demanda
    visto = sesion.verificar_para_plataforma(cuerpo["token"])
    assert visto is not None
    assert visto["sub"] == str(cliente.usuario.id)


def test_session_exige_cuenta_y_sidecar_sano(monkeypatch):
    app = FastAPI()
    app.include_router(molchat_host.router)
    sin_cuenta = TestClient(app)
    assert sin_cuenta.post("/molchat-host/session").status_code in (401, 403)
    monkeypatch.setattr(launcher, "obtener_lanzador",
                        lambda *a, **k: DobleLanzador(roto=True))
    sesion.fijar_secreto_host(b"test-secret-32-bytes-0123456789ab")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    roto = TestClient(app)
    respuesta = roto.post("/molchat-host/session")
    assert respuesta.status_code == 503
    assert "roto" in respuesta.json()["detail"]


def test_host_usa_puerto_real_y_no_cabecera_host(cliente, monkeypatch):
    urls = []
    monkeypatch.setattr(launcher, "obtener_lanzador", lambda url: urls.append(url) or cliente.doble)
    cliente.get("/molchat-host/status", headers={"host": "atacante.example:1234"})
    cliente.post("/molchat-host/session", headers={"host": "atacante.example:1234"})
    assert urls == ["http://127.0.0.1:80", "http://127.0.0.1:80"]
