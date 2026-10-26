"""El motor Molcy viaja con MolDesign: se encuentra solo, se verifica antes de usarlo y el usuario no tiene que traer una carpeta.

# Qué se midió (2026-10-04)

El motor (scripts que se ejecutan dentro de Blender) NO viajaba ni se descargaba: aunque la aplicación bajara Blender y Molecular
Nodes, la pantalla pedía una «Carpeta del motor Molcy» que un investigador no tiene, y sin ella no había ningún vídeo. Ahora va en
`tools/molcy/` (~2,3 MB, GPL-3.0-or-later) con un manifiesto de SHA-256 por fichero.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.molcy import installation, motor, renderer

REPO = Path(__file__).resolve().parents[2]
VENDORIZADO = REPO / "tools" / "molcy"


@pytest.fixture
def copia_del_motor(tmp_path) -> Path:
    destino = tmp_path / "tools" / "molcy"
    shutil.copytree(VENDORIZADO, destino)
    return destino


@pytest.fixture(autouse=True)
def limpio(monkeypatch, tmp_path):
    monkeypatch.setattr(installation, "data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(renderer, "data_dir", lambda: tmp_path / "data")
    (tmp_path / "data").mkdir()
    monkeypatch.delenv("MOLDESIGN_MOLCY_DIR", raising=False)
    monkeypatch.delenv("MOLDESIGN_OPENBABEL_DIR", raising=False)
    monkeypatch.setattr(installation, "settings", lambda: {})
    renderer.invalidar()
    yield
    renderer.invalidar()


# --- Dónde está -----------------------------------------------------------------------------------------------------

def test_la_variable_de_rust_manda(monkeypatch, copia_del_motor):
    monkeypatch.setenv("MOLDESIGN_MOLCY_DIR", str(copia_del_motor))
    assert motor.directorio_incluido() == copia_del_motor.resolve()


def test_sin_la_variable_se_resuelve_junto_a_open_babel(monkeypatch, copia_del_motor):
    """Como Rust no pasaba la variable al escribirse esto, la carpeta hermana de Open Babel basta."""
    monkeypatch.setenv("MOLDESIGN_OPENBABEL_DIR", str(copia_del_motor.parent / "openbabel"))
    assert motor.directorio_incluido() == copia_del_motor.resolve()


def test_una_carpeta_sin_manifiesto_no_cuenta(monkeypatch, copia_del_motor):
    (copia_del_motor / motor.NOMBRE_MANIFIESTO).unlink()
    monkeypatch.setenv("MOLDESIGN_MOLCY_DIR", str(copia_del_motor))
    # cae al árbol del repositorio, que sí trae el suyo
    assert motor.directorio_incluido() == VENDORIZADO.resolve()


def test_sin_ninguna_carpeta_no_hay_motor_incluido(monkeypatch, tmp_path):
    monkeypatch.setattr(motor, "__file__", str(tmp_path / "backend" / "services" / "molcy" / "motor.py"))
    assert motor.directorio_incluido() is None


def test_el_arbol_de_desarrollo_trae_el_motor():
    assert motor.directorio_incluido() == VENDORIZADO.resolve()


# --- Integridad -----------------------------------------------------------------------------------------------------

def test_el_motor_del_repositorio_es_integro():
    assert motor.verificar_integridad(VENDORIZADO) == []


@pytest.mark.parametrize("como,esperado", [
    ("cambiar", "difiere del manifiesto"),
    ("sobrar", "no está en el manifiesto"),
    ("quitar", "falta scripts/salida/render.py"),
])
def test_cada_forma_de_corrupcion_se_ve(copia_del_motor, como, esperado):
    if como == "cambiar":
        f = copia_del_motor / "scripts" / "maestro.py"
        f.write_bytes(f.read_bytes() + b"\n# alterado\n")
    elif como == "sobrar":
        (copia_del_motor / "scripts" / "extra.py").write_text("x = 1", encoding="utf-8")
    else:
        (copia_del_motor / "scripts" / "salida" / "render.py").unlink()
    assert any(esperado in p for p in motor.verificar_integridad(copia_del_motor))


def test_un_png_alterado_tambien_se_ve(copia_del_motor):
    """El emblema no es código, pero sale en todos los vídeos: la integridad cubre TODO el motor."""
    png = copia_del_motor / "moldesign" / "assets" / "marca" / "emblema.png"
    png.write_bytes(png.read_bytes()[:-8] + b"alterado")
    assert any("emblema.png difiere" in p for p in motor.verificar_integridad(copia_del_motor))


def test_el_bytecode_que_escribe_blender_no_cuenta_como_alteracion(copia_del_motor):
    """Medido: tras el primer vídeo aparecieron 36 `.cpython-313.pyc` junto al motor y se declaraba «alterado». Blender ignora
    PYTHONDONTWRITEBYTECODE, así que el motor se ejecuta, escribe su bytecode y debe seguir siendo íntegro."""
    cache = copia_del_motor / "scripts" / "nucleo" / "__pycache__"
    cache.mkdir(exist_ok=True)
    (cache / "rutas.cpython-313.pyc").write_bytes(b"\x00bytecode")
    (copia_del_motor / "scripts" / "__pycache__").mkdir(exist_ok=True)
    (copia_del_motor / "scripts" / "__pycache__" / "maestro.cpython-313.pyc").write_bytes(b"\x00")
    assert motor.verificar_integridad(copia_del_motor) == []


@pytest.mark.parametrize("ruta", [
    "scripts/nucleo/__pycache__/codigo_nuevo.py",   # un .py dentro de __pycache__ NO es bytecode
    "scripts/nucleo/suelto.pyc",                     # un .pyc fuera de __pycache__ tampoco
    "scripts/nucleo/__pycache__/datos.bin",          # ni cualquier otro fichero dentro
])
def test_sólo_el_pyc_dentro_de_pycache_se_ignora(copia_del_motor, ruta):
    f = copia_del_motor / ruta
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"x")
    assert any(f"sobra {ruta}" in p for p in motor.verificar_integridad(copia_del_motor))


def test_manifiesto_ilegible_o_de_otro_esquema(copia_del_motor):
    ruta = copia_del_motor / motor.NOMBRE_MANIFIESTO
    manifiesto = json.loads(ruta.read_text(encoding="utf-8"))
    manifiesto["schema"] = "otro/9"
    ruta.write_text(json.dumps(manifiesto), encoding="utf-8")
    assert motor.verificar_integridad(copia_del_motor)[0].startswith("esquema desconocido")
    ruta.write_text("{no es json", encoding="utf-8")
    assert motor.verificar_integridad(copia_del_motor) == [f"{motor.NOMBRE_MANIFIESTO} ilegible"]


# --- Qué motor se elige ---------------------------------------------------------------------------------------------

def test_orden_de_eleccion_usuario_ajuste_incluido(monkeypatch, copia_del_motor, tmp_path):
    monkeypatch.setenv("MOLCY_PERMITIR_MOTOR_PROPIO", "1")  # un motor propio sólo se acepta con el permiso de desarrollo
    monkeypatch.setenv("MOLDESIGN_MOLCY_DIR", str(copia_del_motor))
    monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_engine_dir=None))
    assert renderer.motor_elegido() == (copia_del_motor.resolve(), "incluido")
    monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_engine_dir=str(tmp_path / "ajuste")))
    assert renderer.motor_elegido() == (tmp_path / "ajuste", "configurado")
    monkeypatch.setattr(installation, "settings", lambda: {"motor": str(tmp_path / "pantalla")})
    assert renderer.motor_elegido() == (tmp_path / "pantalla", "configurado")


def test_sin_nada_no_se_adivina_ningun_motor(monkeypatch, tmp_path):
    monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_engine_dir=None))
    monkeypatch.setattr(renderer.motor, "directorio_incluido", lambda: None)
    assert renderer.motor_elegido() == (Path(""), "ninguno")


# --- El detector con el motor que viaja -----------------------------------------------------------------------------------

def _con_blender_falso(monkeypatch, tmp_path, copia_del_motor, lanzamientos: list):
    blender = tmp_path / "blender.exe"
    blender.write_bytes(b"fake")
    monkeypatch.setenv("MOLDESIGN_MOLCY_DIR", str(copia_del_motor))
    monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_engine_dir=None, molcy_blender_path=None))
    monkeypatch.setattr(renderer, "_blender_candidatos", lambda: [blender])

    def falso(cmd, **_k):
        if "--python-expr" not in cmd:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        lanzamientos.append(1)
        if len(lanzamientos) == 1:
            return subprocess.CompletedProcess(cmd, 0, 'MOLCY_BLENDER_VERSION:[5,2,2]\nMOLCY_CPU_OK\n'
                                               'MOLCY_CAPS:{"version":[5,2,2],"molecular_nodes":"520.2.0"}\n', "")
        return subprocess.CompletedProcess(cmd, 0, "MOLCY_EEVEE_OK\n", "")

    monkeypatch.setattr(renderer.subprocess, "run", falso)


def test_el_detector_da_por_bueno_el_motor_que_viaja_y_registra_su_procedencia(monkeypatch, tmp_path, copia_del_motor):
    lanzamientos: list = []
    _con_blender_falso(monkeypatch, tmp_path, copia_del_motor, lanzamientos)
    capacidad = renderer.detectar()
    manifiesto = json.loads((copia_del_motor / motor.NOMBRE_MANIFIESTO).read_text(encoding="utf-8"))
    assert capacidad["disponible"] is True
    assert capacidad["motor_incluido"] is True
    assert capacidad["motor_origen"] == "incluido"
    assert capacidad["motor"] == str(copia_del_motor.resolve())
    assert capacidad["motor_commit"] == manifiesto["fuente"]["commit"]
    assert capacidad["motor_licencia"] == "GPL-3.0-or-later"
    assert len(lanzamientos) == 2


def test_un_motor_alterado_se_abstiene_sin_lanzar_blender(monkeypatch, tmp_path, copia_del_motor):
    lanzamientos: list = []
    _con_blender_falso(monkeypatch, tmp_path, copia_del_motor, lanzamientos)
    f = copia_del_motor / "scripts" / "nucleo" / "camara.py"
    f.write_bytes(f.read_bytes() + b"\nimport os; os.system('x')\n")
    capacidad = renderer.detectar()
    assert capacidad["disponible"] is False
    assert capacidad["motivo_codigo"] == "motor_alterado"
    assert "Reinstala MolDesign" in capacidad["motivo"]
    assert any("camara.py difiere" in p for p in capacidad["motor_problemas"])
    assert capacidad["motor_incluido"] is True
    assert lanzamientos == [], "no se ejecuta Blender con un motor que no es el distribuido"


def test_un_motor_alterado_despues_de_un_sondeo_bueno_se_ve(monkeypatch, tmp_path, copia_del_motor):
    """La caché no puede esconder una alteración: cualquier fichero del motor que viaja cambia la clave."""
    lanzamientos: list = []
    _con_blender_falso(monkeypatch, tmp_path, copia_del_motor, lanzamientos)
    assert renderer.detectar()["disponible"] is True
    png = copia_del_motor / "moldesign" / "assets" / "marca" / "emblema.png"
    png.write_bytes(png.read_bytes()[:-8] + b"alterado")
    assert renderer.detectar()["motivo_codigo"] == "motor_alterado"


def test_un_motor_configurado_a_mano_no_se_compara_con_ningun_manifiesto(monkeypatch, tmp_path, copia_del_motor):
    monkeypatch.setenv("MOLCY_PERMITIR_MOTOR_PROPIO", "1")  # un motor propio sólo se acepta con el permiso de desarrollo
    """El de un desarrollador (MOLCY_ENGINE_DIR o la pantalla) puede cambiar: sólo el que viaja se verifica."""
    lanzamientos: list = []
    _con_blender_falso(monkeypatch, tmp_path, copia_del_motor, lanzamientos)
    propio = tmp_path / "mi motor"
    shutil.copytree(copia_del_motor, propio)
    (propio / motor.NOMBRE_MANIFIESTO).unlink()
    f = propio / "scripts" / "nucleo" / "camara.py"
    f.write_bytes(f.read_bytes() + b"\n# mi cambio\n")
    monkeypatch.setattr(installation, "settings", lambda: {"motor": str(propio)})
    capacidad = renderer.detectar()
    assert capacidad["disponible"] is True
    assert capacidad["motor_origen"] == "configurado"
    assert "motor_commit" not in capacidad
