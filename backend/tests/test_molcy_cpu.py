"""Recursos CPU, y el vídeo por CPU retirado: la CPU toma fotos (ver test_molcy_fotos.py)."""
from __future__ import annotations
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.dependencies import get_current_user
from api.routers import molcy
from core.database import get_db
from services.molcy import cpu, renderer

INFO = {"cpu_hilos": 4, "cpu_hilos_disponibles": 8, "cpu_hilos_maximos": 6, "cpu_logicos": 8, "cpu_equipo_sha256": "equipo"}


def test_available_threads_respect_process_affinity(monkeypatch):
    monkeypatch.setattr(cpu.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(cpu, "_afinidad", lambda: 4)
    monkeypatch.setattr(cpu, "_carga_actual", lambda: 0)
    assert cpu.recursos()["cpu_logicos"] == 16
    assert cpu.recursos()["cpu_hilos_disponibles"] == 4
    assert cpu.recursos()["cpu_hilos"] == 2
    assert cpu.recursos()["cpu_hilos_maximos"] == 3
    monkeypatch.setattr(cpu.os, "cpu_count", lambda: None)
    assert cpu.recursos()["cpu_hilos"] == 1


@pytest.mark.parametrize("value", [0, -1, 7, 8, 9, True, 1.5, "4"])
def test_invalid_thread_count_is_rejected(value):
    with pytest.raises(ValueError): cpu.validar_hilos(value, INFO)


@pytest.fixture
def client(monkeypatch):
    app = FastAPI(); app.include_router(molcy.router)
    user = SimpleNamespace(id=uuid.uuid4())
    db = AsyncMock()
    async def database(): yield db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = database
    monkeypatch.setattr(cpu, "recursos", lambda: dict(INFO))
    with TestClient(app) as client: yield client, db, user


@pytest.mark.parametrize("threads", [0, 9, True, "2", 1.5])
def test_api_invalid_cpu_count_never_probes_blender(client, monkeypatch, threads):
    monkeypatch.setattr(renderer, "detectar", lambda: pytest.fail("No debe sondear Blender"))
    response = client[0].post("/molcy/trabajos", json={"origen": "receptor", "id": "1AJ6", "escena": "receptor", "formato": "previsualizacion", "dispositivo": "cpu", "cpu_hilos": threads})
    assert response.status_code == 422


def test_gpu_request_cannot_silently_accept_cpu_threads(client):
    response = client[0].post("/molcy/trabajos", json={"origen": "receptor", "id": "1AJ6", "escena": "receptor", "formato": "previsualizacion", "dispositivo": "gpu", "cpu_hilos": 4})
    assert response.status_code == 422


# --- El vídeo por CPU ya no existe (decisión del propietario, 2026-10-08) -------------------------------------------------

@pytest.mark.parametrize("hilos", [None, 4])
def test_un_video_por_cpu_se_rechaza_sin_sondear_blender_y_dice_que_hacer(client, monkeypatch, hilos):
    monkeypatch.setattr(renderer, "detectar", lambda: pytest.fail("No debe sondear Blender"))
    cuerpo = {"origen": "receptor", "id": "1AJ6", "escena": "receptor", "formato": "vertical", "dispositivo": "cpu"}
    if hilos is not None:
        cuerpo["cpu_hilos"] = hilos
    response = client[0].post("/molcy/trabajos", json=cuerpo)
    assert response.status_code == 422
    assert response.json()["detail"] == renderer.MENSAJE_VIDEO_SOLO_GPU
    assert "fotos" in renderer.MENSAJE_VIDEO_SOLO_GPU


def test_el_lanzador_de_video_no_acepta_cpu(tmp_path):
    for dispositivo, hilos in (("cpu", None), ("cpu", 4), ("gpu", 4)):
        with pytest.raises(ValueError, match="sólo con GPU"):
            renderer.iniciar(tmp_path, job_id=str(uuid.uuid4()), pdb_id="1AJ6", sujeto="receptor_solo", formato="biblioteca",
                             dispositivo=dispositivo, capacidad={}, fuente={}, cpu_hilos=hilos)
    assert not (tmp_path / "estado.json").exists()


def test_la_estimacion_del_video_por_cpu_ya_no_existe(client):
    response = client[0].post("/molcy/cpu/estimacion", json={"origen": "receptor", "id": "1AJ6", "formato": "previsualizacion", "cpu_hilos": 4})
    assert response.status_code in (404, 405)
    assert not hasattr(cpu, "estimar") and not hasattr(cpu, "muestra")
