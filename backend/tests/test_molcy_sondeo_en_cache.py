"""El sondeo del renderizador (dos arranques de Blender) no se repite sin motivo y no se solapa.

# Qué se midió (2026-10-04, cápsula 3, Blender 5.2.2 real)

Abrir la pestaña de Molcy disparaba el sondeo; con la página montada dos veces seguidas llegaron dos sondeos a la vez
(cuatro arranques de Blender) y `GET /molcy/renderizador` tardó 49,0 s. Cada «Generar» sondeaba otra vez (10,7 s y 6,9 s) y
cada cambio de idioma, también. Un sondeo sólo cambia si cambia Blender o el motor: se reutiliza el que salió BIEN, y sólo ése
(quien ve «falta Molecular Nodes» está arreglándolo, y el siguiente sondeo tiene que ver el arreglo).
"""

import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_current_user
from api.routers import molcy
from services.molcy import installation, renderer


@pytest.fixture(autouse=True)
def sin_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(installation, "data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(renderer, "data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(renderer.motor, "directorio_incluido", lambda: None)
    (tmp_path / "data").mkdir()
    renderer.invalidar()
    yield
    renderer.invalidar()


def _sondeo_falso(monkeypatch, resultados):
    """`_detectar` sustituido: devuelve los resultados en orden y cuenta las llamadas (con la clave fija)."""
    llamadas = []
    monkeypatch.setattr(renderer, "_clave_de_sondeo", lambda: ("clave",))

    def falso():
        llamadas.append(time.monotonic())
        return dict(resultados[min(len(llamadas), len(resultados)) - 1])

    monkeypatch.setattr(renderer, "_detectar", falso)
    return llamadas


def test_un_resultado_bueno_se_reutiliza(monkeypatch):
    llamadas = _sondeo_falso(monkeypatch, [{"disponible": True, "motivo": None}])
    primero = renderer.detectar()
    segundo = renderer.detectar()
    assert primero == segundo == {"disponible": True, "motivo": None, "motor_incluido": False, "blenders_encontrados": []}
    assert len(llamadas) == 1
    assert renderer.capacidad_estimada() == segundo  # la última capacidad conocida sigue actualizándose


def test_la_copia_devuelta_no_contamina_la_caja(monkeypatch):
    _sondeo_falso(monkeypatch, [{"disponible": True, "motivo": None}])
    renderer.detectar()["disponible"] = False
    assert renderer.detectar()["disponible"] is True


def test_forzar_vuelve_a_sondear(monkeypatch):
    llamadas = _sondeo_falso(monkeypatch, [{"disponible": True}])
    renderer.detectar()
    renderer.detectar(forzar=True)
    assert len(llamadas) == 2


def test_un_resultado_negativo_no_se_guarda(monkeypatch):
    llamadas = _sondeo_falso(monkeypatch, [{"disponible": False, "motivo_codigo": "falta_addon"}, {"disponible": True}])
    assert renderer.detectar()["disponible"] is False
    assert renderer.detectar()["disponible"] is True  # el arreglo se ve en el siguiente sondeo
    assert renderer.detectar()["disponible"] is True
    assert len(llamadas) == 2


def test_un_sondeo_bueno_caduca(monkeypatch):
    llamadas = _sondeo_falso(monkeypatch, [{"disponible": True}])
    monkeypatch.setattr(renderer, "CACHE_SONDEO_S", 0.0)
    renderer.detectar()
    renderer.detectar()
    assert len(llamadas) == 2


def test_cambiar_la_clave_invalida(monkeypatch):
    llamadas = _sondeo_falso(monkeypatch, [{"disponible": True}])
    renderer.detectar()
    monkeypatch.setattr(renderer, "_clave_de_sondeo", lambda: ("otra clave",))
    renderer.detectar()
    assert len(llamadas) == 2


def test_invalidar_olvida_el_ultimo_sondeo(monkeypatch):
    llamadas = _sondeo_falso(monkeypatch, [{"disponible": True}])
    renderer.detectar()
    renderer.invalidar()
    renderer.detectar()
    assert len(llamadas) == 2


def test_dos_sondeos_simultaneos_lanzan_Blender_una_vez(monkeypatch):
    """Lo que pasó al montarse la página dos veces seguidas: ahora el segundo espera al primero y reutiliza su resultado."""
    llamadas = []
    monkeypatch.setattr(renderer, "_clave_de_sondeo", lambda: ("clave",))

    def lento():
        llamadas.append(1)
        time.sleep(0.4)
        return {"disponible": True}

    monkeypatch.setattr(renderer, "_detectar", lento)
    resultados = []
    hilos = [threading.Thread(target=lambda: resultados.append(renderer.detectar())) for _ in range(4)]
    [h.start() for h in hilos]
    [h.join(10) for h in hilos]
    assert len(llamadas) == 1
    assert resultados == [{"disponible": True, "motor_incluido": False, "blenders_encontrados": []}] * 4


# --- La clave de verdad: qué la cambia y qué no ------------------------------------------------------------------------

@pytest.fixture
def instalacion_falsa(monkeypatch, tmp_path):
    blender = tmp_path / "Blender" / "blender.exe"
    blender.parent.mkdir()
    blender.write_bytes(b"MZ blender")
    monkeypatch.setenv("MOLCY_PERMITIR_MOTOR_PROPIO", "1")  # un motor propio sólo se acepta con el permiso de desarrollo
    motor = tmp_path / "motor"
    for ruta, contenido in {"scripts/maestro.py": "x = 1", "scripts/correr_caso.ps1": "param()",
                            "scripts/variables/cpu.py": "y = 2", "moldesign/assets/blender/plantilla_arte.blend": "blend",
                            "README.md": "no es código del motor"}.items():
        destino = motor / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")
    monkeypatch.setattr(renderer, "_blender_candidatos", lambda: [blender])
    monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_engine_dir=str(motor), molcy_blender_path=None))
    monkeypatch.setattr(installation, "settings", lambda: {})
    return blender, motor


def test_la_clave_cambia_con_blender_y_con_el_codigo_del_motor(instalacion_falsa):
    blender, motor = instalacion_falsa
    base = renderer._clave_de_sondeo()
    assert renderer._clave_de_sondeo() == base  # determinista

    (motor / "scripts" / "maestro.py").write_text("x = 1  # editado", encoding="utf-8")
    cambiada_por_motor = renderer._clave_de_sondeo()
    assert cambiada_por_motor != base

    blender.write_bytes(b"MZ blender actualizado")
    assert renderer._clave_de_sondeo() != cambiada_por_motor


def test_la_clave_ignora_el_bytecode_y_lo_que_no_es_codigo_del_motor(instalacion_falsa):
    _, motor = instalacion_falsa
    base = renderer._clave_de_sondeo()
    (motor / "scripts" / "__pycache__").mkdir()
    (motor / "scripts" / "__pycache__" / "maestro.cpython-311.pyc").write_bytes(b"\0")  # lo escribe Blender al renderizar
    (motor / "README.md").write_text("otro texto", encoding="utf-8")
    (motor / "scripts" / "salida.log").write_text("log", encoding="utf-8")
    assert renderer._clave_de_sondeo() == base


def test_la_clave_cambia_si_aparece_otro_blender(instalacion_falsa, monkeypatch, tmp_path):
    _, _ = instalacion_falsa
    base = renderer._clave_de_sondeo()
    otro = tmp_path / "Otro" / "blender.exe"
    otro.parent.mkdir()
    otro.write_bytes(b"MZ otro")
    monkeypatch.setattr(renderer, "_blender_candidatos", lambda: [otro])
    assert renderer._clave_de_sondeo() != base


# --- La ruta ------------------------------------------------------------------------------------------------------------

def _cliente(monkeypatch):
    app = FastAPI()
    app.include_router(molcy.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    recibido = []

    def falso(*, forzar=False):
        recibido.append(forzar)
        return {"disponible": True, "motivo": None}

    monkeypatch.setattr(renderer, "detectar", falso)
    return TestClient(app), recibido


def test_la_ruta_sondea_con_cache_salvo_que_se_pida_recomprobar(monkeypatch):
    cliente, recibido = _cliente(monkeypatch)
    assert cliente.get("/molcy/renderizador").status_code == 200
    assert cliente.get("/molcy/renderizador?recomprobar=true").status_code == 200
    assert cliente.get("/molcy/renderizador?recomprobar=false").status_code == 200
    assert recibido == [False, True, False]


def test_guardar_la_configuracion_invalida_la_cache(monkeypatch, tmp_path):
    cliente, _ = _cliente(monkeypatch)
    avisos = []
    monkeypatch.setattr(renderer, "invalidar", lambda: avisos.append(1))
    monkeypatch.setattr(installation, "configure", lambda *_: None)
    monkeypatch.setattr(installation, "status", lambda: {"estado": "inactivo"})
    assert cliente.put("/molcy/configuracion", json={"modo": "administrado"}).status_code == 200
    assert avisos == [1]


def test_tras_instalar_Molecular_Nodes_se_comprueba_de_verdad():
    """`addon._instalar` fuerza el sondeo: la caché no puede darle por bueno lo que acaba de instalarse."""
    fuente = (Path(molcy.__file__).parents[2] / "services" / "molcy" / "addon.py").read_text(encoding="utf-8")
    assert "renderer.detectar(forzar=True)" in fuente
