"""BATCH-BE-002 — un batch heredado pertenece a la cuenta que lo lanzó.

`_batches` es un diccionario en memoria sin dueño: `GET /evaluation/batch/{id}`
y `/export` devolvían resultados a cualquiera que conociera el identificador.
No es enumerable (UUID4), pero el gate del plan no habla de dificultad: dos
cuentas en la misma máquina tienen que estar aisladas, y un identificador que
viaja en un enlace, un log de soporte o una captura no puede ser la única
credencial de un cribado completo.

Se responde 404 —no 403— para no confirmar la existencia del batch ajeno.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_current_user_optional
from api.routers import batch as batch_mod
from core.database import get_db


ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"


@pytest.fixture
def app_con_sesion(monkeypatch):
    from api.main import app

    async def _sin_db():
        yield None

    app.dependency_overrides[get_db] = _sin_db

    async def _falso_process_batch(*_args, **_kwargs):
        return None

    monkeypatch.setattr(batch_mod, "_process_batch", _falso_process_batch)

    sesion: dict[str, object] = {"usuario": None}
    app.dependency_overrides[get_current_user_optional] = lambda: sesion["usuario"]

    try:
        yield app, sesion
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user_optional, None)
        batch_mod._batches.clear()


def _lanzar(cliente: TestClient) -> str:
    respuesta = cliente.post(
        "/evaluation/batch",
        files={"file": ("moleculas.csv", f"smiles,name\n{ASPIRINA},aspirina\n".encode(), "text/csv")},
        params={"target_pdb_id": "7E2Y"},
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["batch_id"]


def test_una_segunda_cuenta_no_lee_ni_exporta_el_batch_ajeno(app_con_sesion):
    app, sesion = app_con_sesion
    cliente = TestClient(app)

    sesion["usuario"] = SimpleNamespace(id=uuid.uuid4())  # alice
    batch_id = _lanzar(cliente)
    assert cliente.get(f"/evaluation/batch/{batch_id}").status_code == 200

    sesion["usuario"] = SimpleNamespace(id=uuid.uuid4())  # bob
    ajeno = cliente.get(f"/evaluation/batch/{batch_id}")
    assert ajeno.status_code == 404
    # No se confirma la existencia del cribado ajeno.
    assert "permiso" not in ajeno.text.lower()

    exportado = cliente.get(f"/evaluation/batch/{batch_id}/export")
    assert exportado.status_code == 404


def test_el_propietario_conserva_su_batch_entre_peticiones(app_con_sesion):
    app, sesion = app_con_sesion
    cliente = TestClient(app)

    alice = SimpleNamespace(id=uuid.uuid4())
    sesion["usuario"] = alice
    batch_id = _lanzar(cliente)

    primera = cliente.get(f"/evaluation/batch/{batch_id}")
    segunda = cliente.get(f"/evaluation/batch/{batch_id}")

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert segunda.json()["batch_id"] == batch_id


def test_un_batch_anonimo_no_lo_hereda_una_cuenta(app_con_sesion):
    """El cribado sin sesión pertenece a esa sesión anónima, no a la siguiente."""
    app, sesion = app_con_sesion
    cliente = TestClient(app)

    sesion["usuario"] = None
    batch_id = _lanzar(cliente)
    assert cliente.get(f"/evaluation/batch/{batch_id}").status_code == 200

    sesion["usuario"] = SimpleNamespace(id=uuid.uuid4())
    assert cliente.get(f"/evaluation/batch/{batch_id}").status_code == 404
