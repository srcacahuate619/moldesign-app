"""Moldex dice dónde guarda: fichas en la base SQLite de la carpeta de datos, y sólo abre ESA carpeta."""
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import moldex
from api.dependencies import get_current_user


def _cliente(tmp_path, monkeypatch):
    monkeypatch.setattr("utils.local_storage.data_dir", lambda: tmp_path)
    app = FastAPI()
    app.include_router(moldex.router)
    app.dependency_overrides[get_current_user] = lambda: object()
    return TestClient(app)


def test_ubicacion_nombra_la_carpeta_y_la_base(tmp_path, monkeypatch):
    cuerpo = _cliente(tmp_path, monkeypatch).get("/moldex/ubicacion").json()
    assert cuerpo == {"carpeta_datos": str(tmp_path), "base_de_datos": str(tmp_path / "moldesign_local.db")}


def test_abrir_solo_abre_la_carpeta_de_datos_y_no_acepta_rutas(tmp_path, monkeypatch):
    cliente = _cliente(tmp_path, monkeypatch)
    with patch("subprocess.Popen") as popen:
        respuesta = cliente.post("/moldex/ubicacion/abrir?ruta=C:/Windows", json={"ruta": "C:/Windows"})
    assert respuesta.status_code == 200
    comando = popen.call_args[0][0]
    assert str(tmp_path) in comando and "C:/Windows" not in comando
