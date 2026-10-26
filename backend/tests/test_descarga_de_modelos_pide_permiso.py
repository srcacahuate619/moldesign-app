"""Descargar un modelo desde el Intérprete IA pide el permiso en el sitio.

EL FALLO. `POST /ai/models/download` sale a huggingface.co y exige que la cuenta
haya autorizado ese destino (`services/ai/red.py`). El 403 era una frase suelta,
la interfaz sólo enseñaba «HTTP 403» y ninguna pantalla de MolChat ofrecía
autorizar huggingface.co: los botones «Descargar» del Intérprete IA no podían
funcionar. Ahora el 403 dice el motivo (sin permiso u offline) y el destino, y
la interfaz ofrece «Autorizar huggingface.co y descargar».
"""
from __future__ import annotations

import uuid

import pytest

from services.ai import provider_config_store as store

ALICE = str(uuid.uuid4())
PEDIDO = {"model_id": "unsloth/Qwen3.5-4B-GGUF", "filename": "Qwen3.5-4B-Q4_K_M.gguf"}


@pytest.fixture(autouse=True)
def entorno_aislado(tmp_path, monkeypatch):
    secreto = tmp_path / "secret_key"
    secreto.write_text("c" * 64, encoding="utf-8")
    monkeypatch.setattr(store, "_STORE_DIR", tmp_path)
    monkeypatch.setattr(store, "_STORE_FILE", tmp_path / "provider_config.json")
    monkeypatch.setattr(store, "_SECRET_KEY_FILE", secreto)
    monkeypatch.delenv("MOLDESIGN_OFFLINE", raising=False)


@pytest.fixture
def cliente(monkeypatch):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from api.dependencies import get_current_user
    from api.main import app
    from services.ai import model_registry

    # Nunca una descarga real: se anota lo que se habría bajado.
    monkeypatch.setattr(
        model_registry, "start_download",
        lambda model_id, filename, user_id=None: {"id": "dl1", "model_id": model_id, "filename": filename},
    )
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=ALICE, email="a@ejemplo.test")
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_sin_permiso_el_403_dice_el_destino_que_hay_que_autorizar(cliente):
    r = cliente.post("/ai/models/download", json=PEDIDO)
    assert r.status_code == 403
    detalle = r.json()["detail"]
    assert detalle["motivo"] == "sin_permiso"
    assert detalle["servicio"] == "huggingface"
    assert detalle["host"] == "huggingface.co"
    assert "huggingface.co" in detalle["mensaje"]


def test_en_modo_offline_lo_dice_y_autorizar_no_lo_arreglaria(cliente, monkeypatch):
    monkeypatch.setenv("MOLDESIGN_OFFLINE", "1")
    r = cliente.post("/ai/models/download", json=PEDIDO)
    assert r.status_code == 403
    assert r.json()["detail"]["motivo"] == "offline"


def test_con_el_destino_autorizado_la_descarga_arranca(cliente):
    r = cliente.post("/ai/consent/red", json={"servicio": "huggingface", "host": "huggingface.co"})
    assert r.status_code == 200

    r = cliente.post("/ai/models/download", json=PEDIDO)
    assert r.status_code == 200
    assert r.json()["filename"] == "Qwen3.5-4B-Q4_K_M.gguf"
