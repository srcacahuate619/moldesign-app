"""La pantalla de Molcy enseña el último fotograma completo mientras el render está en curso."""
from __future__ import annotations

import json
import os
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_current_user
from api.routers import molcy
from services.molcy import installation, renderer

#: Un PNG que sólo contiene lo que el servidor mira: el trozo IEND del final.
PNG_ENTERO = b"\x89PNG\r\n\x1a\n" + b"datos" * 40 + b"\x00\x00\x00\x00IEND\xaeB`\x82"
PNG_A_MEDIAS = PNG_ENTERO[: len(PNG_ENTERO) // 2]


@pytest.fixture
def mundo(monkeypatch, tmp_path):
    monkeypatch.setattr(installation, "data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(renderer, "data_dir", lambda: tmp_path / "data")
    (tmp_path / "data").mkdir()
    user = SimpleNamespace(id=uuid.uuid4())
    app = FastAPI()
    app.include_router(molcy.router)
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    job = str(uuid.uuid4())
    root = renderer.raiz_trabajo(str(user.id), job)
    sufijo = job.replace("-", "")[:12]
    carpeta = root / "salida" / f"render_social_vertical_{sufijo}"
    carpeta.mkdir(parents=True)
    # Sin esto `leer_estado` da por interrumpido un trabajo «renderizando» que ningún hilo reserva.
    with renderer._lock:
        renderer._reserved.add(job)
    renderer.guardar_estado(root, {"id": job, "estado": "renderizando", "formato": "social_vertical"})
    yield SimpleNamespace(user=user, app=app, client=client, job=job, root=root, carpeta=carpeta, sufijo=sufijo)
    with renderer._lock:
        renderer._reserved.discard(job)


def _ruta(mundo, **consulta):
    extra = "".join(f"&{k}={v}" for k, v in consulta.items())
    return f"/molcy/trabajos/{mundo.job}/fotograma?{extra[1:]}" if extra else f"/molcy/trabajos/{mundo.job}/fotograma"


def test_sin_fotogramas_aun_no_hay_nada_que_enseñar(mundo):
    response = mundo.client.get(_ruta(mundo))
    assert response.status_code == 204 and not response.content


def test_enseña_el_mas_reciente_con_su_numero_y_el_total(mundo):
    (mundo.root / "salida" / f"build_social_vertical_{mundo.sufijo}.parcial.json").write_text(
        json.dumps({"fotogramas": 360}), encoding="utf-8")
    for n in (1, 2, 3):
        (mundo.carpeta / f"f_{n:04d}.png").write_bytes(PNG_ENTERO + bytes([n]) * 0)
    response = mundo.client.get(_ruta(mundo))
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-molcy-fotograma"] == "3"
    assert response.headers["x-molcy-orden"] == "3"
    assert response.headers["x-molcy-total"] == "360"
    assert response.headers["cache-control"] == "no-store"
    assert response.content == PNG_ENTERO


def test_con_pausas_el_numero_que_va_sobre_el_total_es_el_orden_entre_los_rendidos(mundo):
    # Lo que vio el propietario: «Fotograma 681 de 667». Con pausas de lectura y fotogramas reutilizados el motor no
    # rinde todos los del guion; cada PNG se llama por su fotograma del GUION y el total cuenta los que se rinden.
    (mundo.root / "salida" / f"build_social_vertical_{mundo.sufijo}.parcial.json").write_text(
        json.dumps({"fotogramas": 800, "fotogramas_render_unicos": 667}), encoding="utf-8")
    rendidos = [f for f in range(1, 682) if f % 5]  # un hueco cada cinco: 545 PNG, el último es el 681
    for f in rendidos:
        (mundo.carpeta / f"f_{f:04d}.png").write_bytes(PNG_ENTERO)
    response = mundo.client.get(_ruta(mundo))
    assert response.status_code == 200
    assert response.headers["x-molcy-fotograma"] == "681"  # el cursor sigue siendo el del guion
    assert response.headers["x-molcy-orden"] == str(len(rendidos))
    assert response.headers["x-molcy-total"] == "667"
    assert int(response.headers["x-molcy-orden"]) <= int(response.headers["x-molcy-total"])
    # el orden es la misma cuenta que la barra de progreso
    estado = renderer.leer_estado(str(mundo.user.id), mundo.job)
    assert estado["progreso"] == {"fotogramas": len(rendidos), "total": 667}
    # si el último se está escribiendo se enseña el anterior, con SU orden
    (mundo.carpeta / "f_0683.png").write_bytes(PNG_A_MEDIAS)
    response = mundo.client.get(_ruta(mundo))
    assert response.headers["x-molcy-fotograma"] == "681"
    assert response.headers["x-molcy-orden"] == str(len(rendidos))


def test_si_el_ultimo_se_esta_escribiendo_enseña_el_anterior(mundo):
    (mundo.carpeta / "f_0001.png").write_bytes(PNG_ENTERO)
    (mundo.carpeta / "f_0002.png").write_bytes(PNG_A_MEDIAS)
    response = mundo.client.get(_ruta(mundo))
    assert response.status_code == 200 and response.headers["x-molcy-fotograma"] == "1"
    assert response.content == PNG_ENTERO


def test_no_repite_el_que_la_pantalla_ya_tiene(mundo):
    (mundo.carpeta / "f_0007.png").write_bytes(PNG_ENTERO)
    assert mundo.client.get(_ruta(mundo, despues=7)).status_code == 204
    assert mundo.client.get(_ruta(mundo, despues=8)).status_code == 204
    nuevo = mundo.client.get(_ruta(mundo, despues=6))
    assert nuevo.status_code == 200 and nuevo.headers["x-molcy-fotograma"] == "7"


def test_sólo_sirve_fotogramas_del_render_principal(mundo):
    # nada que no se llame f_NNNN.png: ni temporales, ni el vídeo, ni otros PNG
    for nombre in ("f_0001.png.tmp", "secreto.png", "f_1.png", "f_0001.PNG.bak"):
        (mundo.carpeta / nombre).write_bytes(PNG_ENTERO)
    assert mundo.client.get(_ruta(mundo)).status_code == 204
    # la capa del título está en OTRA carpeta (`..._titulo`): tampoco se mira
    titulo = mundo.root / "salida" / f"render_social_vertical_{mundo.sufijo}_titulo"
    titulo.mkdir()
    (titulo / "f_0001.png").write_bytes(PNG_ENTERO)
    assert mundo.client.get(_ruta(mundo)).status_code == 204


def test_un_trabajo_que_ya_no_renderiza_responde_404(mundo):
    (mundo.carpeta / "f_0001.png").write_bytes(PNG_ENTERO)
    renderer.guardar_estado(mundo.root, {"id": mundo.job, "estado": "completo", "formato": "social_vertical",
                                         "video": "v.mp4", "video_sha256": "0" * 64, "acta": "a.json"})
    response = mundo.client.get(_ruta(mundo))
    assert response.status_code == 404


def test_otro_usuario_no_ve_los_fotogramas_de_un_trabajo_ajeno(mundo):
    (mundo.carpeta / "f_0001.png").write_bytes(PNG_ENTERO)
    mundo.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    assert mundo.client.get(_ruta(mundo)).status_code == 404


def test_un_trabajo_inexistente_responde_404(mundo):
    assert mundo.client.get(f"/molcy/trabajos/{uuid.uuid4()}/fotograma").status_code == 404


def test_despues_negativo_se_rechaza(mundo):
    assert mundo.client.get(_ruta(mundo, despues=-1)).status_code == 422


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="sin enlaces simbólicos")
def test_una_carpeta_que_es_un_enlace_no_se_sigue(mundo, tmp_path):
    ajena = tmp_path / "ajena"
    ajena.mkdir()
    (ajena / "f_0001.png").write_bytes(PNG_ENTERO)
    for hijo in mundo.carpeta.iterdir():
        hijo.unlink()
    mundo.carpeta.rmdir()
    try:
        os.symlink(ajena, mundo.carpeta, target_is_directory=True)
    except OSError:
        pytest.skip("Windows sin permiso para crear enlaces")
    assert mundo.client.get(_ruta(mundo)).status_code == 204


def test_las_cabeceras_del_fotograma_se_exponen_al_navegador():
    from api import middleware
    import inspect
    fuente = inspect.getsource(middleware.register_middleware)
    assert "X-Molcy-Fotograma" in fuente and "X-Molcy-Orden" in fuente and "X-Molcy-Total" in fuente
