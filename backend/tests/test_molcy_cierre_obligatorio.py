"""El cierre de MolDesign es obligatorio en todo video y el backend no da por completo uno que no lo lleve.

La firma de marca al final de cada video generado es parte del producto. El motor ya no ofrece ningún mando para quitarla, pero el backend no se
fía de una sola afirmación: exige que el acta (que escribe el motor) la acredite Y mide el MP4 con un analizador de contenedor. Un video que dura lo
de la escena y no lo de la escena MÁS el cierre se rechaza, en CPU y en GPU, en los tres formatos.

Medido (2026-10-04) antes de este cambio: la previsualización GPU de 3 s (la «Prueba») salía SIN cierre, y para CPU el backend sólo miraba que el acta
tuviera la clave `cierre`, sin comprobar que el video durase lo que debía.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_current_user
from api.routers import molcy
from services.molcy import cierre, disk, installation, renderer
from tests.molcy_ayudas import acta_con_cierre, escribir_mp4, mp4_falso


# --- El analizador de MP4 -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs", [
    {}, {"escala": 90000}, {"escala": 600, "version": 1}, {"moov_al_principio": True}, {"ampliado": True},
    {"version": 1, "moov_al_principio": True, "ampliado": True},
])
def test_el_analizador_lee_la_duracion_de_cualquier_mp4_bien_formado(tmp_path, kwargs):
    ruta = escribir_mp4(tmp_path / "v.mp4", 6.6, **kwargs)
    assert cierre.duracion_mp4_s(ruta) == pytest.approx(6.6, abs=0.01)


@pytest.mark.parametrize("contenido", [b"", b"no es un mp4", b"\x00" * 7, mp4_falso(6.6)[:20], b"\x00\x00\x00\x08moov",
                                       b"\xff\xff\xff\xff" + b"moov" + b"\0" * 8])
def test_el_analizador_devuelve_none_si_no_hay_un_mp4_legible(tmp_path, contenido):
    ruta = tmp_path / "x.mp4"
    ruta.write_bytes(contenido)
    assert cierre.duracion_mp4_s(ruta) is None


def test_el_analizador_no_falla_con_un_fichero_que_no_existe(tmp_path):
    assert cierre.duracion_mp4_s(tmp_path / "no-existe.mp4") is None


def test_el_analizador_ve_la_diferencia_entre_con_y_sin_cierre(tmp_path):
    """Lo que de verdad se mide: 3,0 s de escena sin cierre frente a 6,6 s con él."""
    sin = cierre.duracion_mp4_s(escribir_mp4(tmp_path / "sin.mp4", 3.0))
    con = cierre.duracion_mp4_s(escribir_mp4(tmp_path / "con.mp4", 6.6))
    assert con - sin == pytest.approx(3.6, abs=0.01)


# --- verificar(): cada forma de entregar un video sin su cierre ------------------------------------------------------------

def test_un_video_con_su_cierre_pasa(tmp_path):
    cierre.verificar(acta_con_cierre(), escribir_mp4(tmp_path / "v.mp4", 6.6))


@pytest.mark.parametrize("formato,escena_s,cierre_s", [("previsualizacion", 3.0, 3.6), ("social_vertical", 12.0, 3.6), ("biblioteca", 22.7, 4.4)])
def test_los_tres_formatos_pasan_con_su_cierre(tmp_path, formato, escena_s, cierre_s):
    acta = acta_con_cierre(escena_s=escena_s, cierre_s=cierre_s)
    acta["formato"]["nombre"] = formato
    cierre.verificar(acta, escribir_mp4(tmp_path / "v.mp4", escena_s + cierre_s))


@pytest.mark.parametrize("cambio", [
    {"formato": None}, {"cierre": None}, {"formato": {"cierre_s": 0}}, {"formato": {"cierre_s": 2.9}},
    {"formato": {"cierre_s": True}}, {"formato": {"cierre_s": "3.6"}}, {"formato": {"cierre_s": float("nan")}},
    {"formato": {"cierre_s": -3.6}}, {"cierre": {"segundos": 3.6, "fotogramas": 0, "huella": "h"}},
    {"cierre": {"segundos": 3.6, "fotogramas": 108, "huella": ""}}, {"cierre": {"segundos": 1.0, "fotogramas": 30, "huella": "h"}},
    {"cierre": {"fotogramas": 108, "huella": "h"}}, {"duracion_s": None}, {"duracion_s": 0}, {"video": {}}, {"video": {"segundos": 3.0}},
    {"video": {"segundos": "6.6"}},
])
def test_un_acta_que_no_acredita_el_cierre_se_rechaza(tmp_path, cambio):
    acta = acta_con_cierre()
    for clave, valor in cambio.items():
        if isinstance(valor, dict) and isinstance(acta.get(clave), dict):
            acta[clave] = {**acta[clave], **valor} if "cierre_s" in valor else valor
        else:
            acta[clave] = valor
    with pytest.raises(RuntimeError, match="no acredita el cierre de MolDesign"):
        cierre.verificar(acta, escribir_mp4(tmp_path / "v.mp4", 6.6))


def test_un_acta_sin_ninguna_clave_de_cierre_se_rechaza(tmp_path):
    with pytest.raises(RuntimeError, match="no acredita el cierre"):
        cierre.verificar({"duracion_s": 3.0, "render_ajustes": {"motor": "BLENDER_EEVEE"}}, escribir_mp4(tmp_path / "v.mp4", 3.0))


def test_un_video_que_dura_lo_de_la_escena_sin_el_cierre_se_rechaza_aunque_el_acta_lo_jure(tmp_path):
    """El caso que importa: el acta (que la escribe el motor) dice que hay cierre, el MP4 mide otra cosa."""
    with pytest.raises(RuntimeError, match="falta el cierre de MolDesign"):
        cierre.verificar(acta_con_cierre(), escribir_mp4(tmp_path / "v.mp4", 3.0))


def test_un_video_ilegible_se_rechaza(tmp_path):
    ruta = tmp_path / "v.mp4"
    ruta.write_bytes(b"no es un mp4")
    with pytest.raises(RuntimeError, match="falta el cierre de MolDesign"):
        cierre.verificar(acta_con_cierre(), ruta)


def test_la_tolerancia_es_la_del_contenedor_no_la_de_un_cierre_entero(tmp_path):
    acta = acta_con_cierre()
    cierre.verificar(acta, escribir_mp4(tmp_path / "justo.mp4", 6.6 - cierre.TOLERANCIA_S + 0.01))
    with pytest.raises(RuntimeError):
        cierre.verificar(acta, escribir_mp4(tmp_path / "corto.mp4", 6.6 - cierre.TOLERANCIA_S - 0.05))
    cierre.verificar(acta, escribir_mp4(tmp_path / "largo.mp4", 7.5))  # más largo no es un cierre de menos


# --- El runner: vídeo sólo con GPU, los tres formatos --------------------------------------------------------------------------------

INFO = {"cpu_modelo": "x", "cpu_logicos": 8, "cpu_hilos_disponibles": 8, "cpu_hilos": 6, "cpu_hilos_maximos": 6, "cpu_equipo_sha256": "e" * 64}


def _ejecutar(monkeypatch, tmp_path, *, dispositivo, formato, video_s, acta, presentacion=None, acreditar_receta=True):
    def forbidden(*_):
        raise AssertionError("El render automático no debe consultar ni limitar VRAM")
    monkeypatch.setattr(renderer.gpu, "recursos", forbidden)
    monkeypatch.setattr(renderer.gpu, "validar_presupuesto", forbidden)
    monkeypatch.setattr(disk, "assert_budget", lambda *_: {})
    monkeypatch.setattr(renderer.cpu, "recursos", lambda: dict(INFO))
    root = tmp_path / "job"
    root.mkdir()
    estado = {"id": str(uuid.uuid4()), "estado": "en_cola", "formato": formato, "dispositivo": dispositivo, "sujeto": "receptor_solo",
              "fuente": {"origen": "receptor", "id": "1HSG"},
              "renderizador": {"motor": str(tmp_path), "blender": str(tmp_path / "blender.exe"), "cpu_hilos_configurables": True, **INFO}}

    if presentacion is not None:
        from services.molcy import presentacion as receta
        receta.guardar(root, estado, presentacion=presentacion)

    def correr(command, *, env, **kwargs):
        assert callable(kwargs["monitor"])  # vigila el disco del caso y del cierre (010a3215)
        assert 0 < kwargs["cpu_rate"] <= 7500
        # El render corre en la carpeta del trabajo, nunca en la del backend (BUG-molcy-render-WindowsApps).
        assert os.path.normcase(kwargs["cwd"]) == os.path.normcase(str(root))
        assert command[command.index("-Python") + 1] == str(python_falso)  # el halo y el sellado usan el Python auxiliar
        sufijo = estado["id"].replace("-", "")[:12]
        salida = root / "salida"
        video = salida / f"1HSG_sitio_activo_{formato}_{sufijo}.mp4"
        escribir_mp4(video, video_s)
        datos = json.loads(json.dumps(acta))
        if presentacion is not None:
            ruta_receta = Path(command[command.index("-Ajustes") + 1])
            entrada = json.loads(ruta_receta.read_text(encoding="utf-8"))
            assert entrada == estado["ajustes"]
            if acreditar_receta:
                datos["ajustes"] = {"entrada": entrada}
        datos.setdefault("render_ajustes", {})["motor"] = "BLENDER_EEVEE"
        datos.setdefault("video", {})["sha256"] = renderer.sha256_archivo(video)
        (salida / f"build_{formato}_{sufijo}.json").write_text(json.dumps(datos), encoding="utf-8")
        return SimpleNamespace(returncode=0)

    python_falso = tmp_path / "python_auxiliar" / "python.exe"
    monkeypatch.setattr(renderer, "python_auxiliar", lambda: python_falso)  # sin el Python de MolDesign real (python_auxiliar.py)
    monkeypatch.setattr(renderer, "run_owned", correr)
    renderer._ejecutar(root, estado, "1HSG")
    return estado


@pytest.mark.parametrize("dispositivo", ["gpu"])
def test_un_video_con_cierre_se_da_por_completo(monkeypatch, tmp_path, dispositivo):
    estado = _ejecutar(monkeypatch, tmp_path, dispositivo=dispositivo, formato="previsualizacion", video_s=6.6, acta=acta_con_cierre())
    assert estado["estado"] == "completo", estado.get("motivo")


@pytest.mark.parametrize("dispositivo", ["gpu"])
def test_un_acta_sin_cierre_hace_fallar_el_trabajo(monkeypatch, tmp_path, dispositivo):
    acta = acta_con_cierre()
    del acta["cierre"]
    estado = _ejecutar(monkeypatch, tmp_path, dispositivo=dispositivo, formato="previsualizacion", video_s=6.6, acta=acta)
    assert estado["estado"] == "fallido"
    assert "cierre de MolDesign" in estado["motivo"]


@pytest.mark.parametrize("dispositivo", ["gpu"])
def test_un_video_sin_cierre_hace_fallar_el_trabajo_aunque_el_acta_diga_otra_cosa(monkeypatch, tmp_path, dispositivo):
    estado = _ejecutar(monkeypatch, tmp_path, dispositivo=dispositivo, formato="previsualizacion", video_s=3.0, acta=acta_con_cierre())
    assert estado["estado"] == "fallido"
    assert "falta el cierre de MolDesign" in estado["motivo"]


def test_la_prueba_de_gpu_sin_cierre_ya_no_se_entrega(monkeypatch, tmp_path):
    """El caso medido: la previsualización GPU (la «Prueba · 3 s») salía de 3,0 s, sin cierre, y el backend la daba por buena."""
    acta = {"duracion_s": 3.0, "render_ajustes": {"motor": "BLENDER_EEVEE"}, "fotogramas": 90, "video": {}}
    estado = _ejecutar(monkeypatch, tmp_path, dispositivo="gpu", formato="previsualizacion", video_s=3.0, acta=acta)
    assert estado["estado"] == "fallido"
    assert "video_sha256" not in estado and "video" not in estado


# --- El motor propio: sólo con permiso de desarrollo --------------------------------------------------------------------------

@pytest.fixture
def app_y_motor(monkeypatch, tmp_path):
    monkeypatch.setattr(installation, "data_dir", lambda: tmp_path / "data")
    (tmp_path / "data").mkdir()
    monkeypatch.delenv("MOLCY_PERMITIR_MOTOR_PROPIO", raising=False)
    motor_propio = tmp_path / "mi-motor"
    (motor_propio / "scripts").mkdir(parents=True)
    (motor_propio / "scripts" / "maestro.py").write_text("x = 1", encoding="utf-8")
    app = FastAPI()
    app.include_router(molcy.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    renderer.invalidar()
    yield TestClient(app), motor_propio
    renderer.invalidar()


def test_la_aplicacion_no_acepta_elegir_otro_motor(app_y_motor):
    cliente, motor_propio = app_y_motor
    respuesta = cliente.put("/molcy/configuracion", json={"modo": "administrado", "motor": str(motor_propio)})
    assert respuesta.status_code == 409
    assert "motor Molcy incluido" in respuesta.json()["detail"]
    assert installation.settings().get("motor") is None


def test_guardar_sin_motor_propio_sigue_funcionando(app_y_motor):
    cliente, _ = app_y_motor
    assert cliente.put("/molcy/configuracion", json={"modo": "administrado", "motor": None}).status_code == 200
    assert cliente.put("/molcy/configuracion", json={"modo": "administrado"}).status_code == 200


def test_con_el_permiso_de_desarrollo_se_acepta_y_se_usa(app_y_motor, monkeypatch):
    cliente, motor_propio = app_y_motor
    monkeypatch.setenv("MOLCY_PERMITIR_MOTOR_PROPIO", "1")
    assert cliente.put("/molcy/configuracion", json={"modo": "administrado", "motor": str(motor_propio)}).status_code == 200
    assert renderer.motor_elegido() == (motor_propio, "configurado")


@pytest.mark.parametrize("valor", ["", "0", "true", "yes", "si"])
def test_sólo_el_valor_exacto_1_concede_el_permiso(monkeypatch, valor):
    monkeypatch.setenv("MOLCY_PERMITIR_MOTOR_PROPIO", valor)
    assert renderer.motor.motor_propio_permitido() is False


def test_sin_permiso_un_motor_guardado_o_de_el_entorno_se_ignora(monkeypatch, tmp_path):
    """Una configuración vieja (o `MOLCY_ENGINE_DIR`) no puede esquivar el motor incluido."""
    monkeypatch.delenv("MOLCY_PERMITIR_MOTOR_PROPIO", raising=False)
    incluido = tmp_path / "tools" / "molcy"
    incluido.mkdir(parents=True)
    monkeypatch.setattr(renderer.motor, "directorio_incluido", lambda: incluido)
    monkeypatch.setattr(installation, "settings", lambda: {"motor": str(tmp_path / "otro")})
    monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_engine_dir=str(tmp_path / "otro-aun")))
    assert renderer.motor_elegido() == (incluido, "incluido")


def test_el_video_transporta_y_acredita_la_receta_personalizada(monkeypatch, tmp_path):
    estado = _ejecutar(monkeypatch, tmp_path, dispositivo="gpu", formato="previsualizacion",
                        video_s=6.6, acta=acta_con_cierre(),
                        presentacion={"titulo": "Mi figura", "contactos": False})
    assert estado["estado"] == "completo", estado.get("motivo")
    assert estado["ajustes"]["presentacion"]["titulo"] == "Mi figura"


def test_un_motor_que_ignora_la_receta_no_entrega_video_personalizado(monkeypatch, tmp_path):
    estado = _ejecutar(monkeypatch, tmp_path, dispositivo="gpu", formato="previsualizacion",
                        video_s=6.6, acta=acta_con_cierre(), presentacion={"titulo": "No ignorar"},
                        acreditar_receta=False)
    assert estado["estado"] == "fallido"
    assert "receta" in estado["motivo"]
    assert "video" not in estado
