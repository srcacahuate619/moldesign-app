"""La detección usa instalaciones del usuario, nunca rutas de la máquina de desarrollo."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from services.molcy import renderer
from api.routers import molcy


@pytest.fixture
def sin_configuracion(monkeypatch, tmp_path):
    monkeypatch.setattr(renderer.installation, "settings", lambda: {})
    monkeypatch.setattr(renderer.installation, "blender_path", lambda: None)
    monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_blender_path=None, molcy_engine_dir=None))
    monkeypatch.setattr(renderer.motor, "directorio_incluido", lambda: None)  # el motor que viaja es otro caso (test_molcy_motor_incluido)
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "Program Files"))
    monkeypatch.setattr(renderer.subprocess, "run", lambda *a, **k: pytest.fail("No se debe sondear un motor sin configurar"))
    return tmp_path


def test_descubrimiento_blender_solo_en_instalacion_estandar(sin_configuracion):
    standard = sin_configuracion / "Program Files" / "Blender Foundation" / "Blender 5.2" / "blender.exe"
    standard.parent.mkdir(parents=True)
    standard.touch()
    assert renderer._blender_candidatos() == [standard]


def test_blender_explicito_conservado(monkeypatch, sin_configuracion):
    blender = sin_configuracion / "mi Blender" / "blender.exe"
    monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_blender_path=str(blender), molcy_engine_dir=None))
    assert renderer._blender_candidatos() == [blender]


def test_motor_sin_configuracion_no_elige_copia_del_desarrollador(monkeypatch, sin_configuracion):
    blender = sin_configuracion / "blender.exe"
    blender.touch()
    monkeypatch.setattr(renderer, "_blender_candidatos", lambda: [blender])
    original_is_dir = Path.is_dir
    monkeypatch.setattr(Path, "is_dir", lambda p: True if str(p) == r"E:\proyect3d" else original_is_dir(p))
    original_is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda p: False if str(p).startswith(r"E:\proyect3d") else original_is_file(p))
    result = renderer.detectar()
    assert result["disponible"] is False
    assert "motor" not in result
    assert result["motivo"] == "No se encontró el motor Molcy. Elige su carpeta en la configuración de abajo."


@pytest.mark.parametrize("source", ["interfaz", "entorno"])
def test_motor_explicito_conservado(monkeypatch, sin_configuracion, source):
    blender = sin_configuracion / "blender.exe"
    blender.touch()
    monkeypatch.setenv("MOLCY_PERMITIR_MOTOR_PROPIO", "1")  # un motor propio sólo se acepta con el permiso de desarrollo
    engine = sin_configuracion / "mi motor"
    engine.mkdir()
    monkeypatch.setattr(renderer, "_blender_candidatos", lambda: [blender])
    if source == "interfaz":
        monkeypatch.setattr(renderer.installation, "settings", lambda: {"motor": str(engine)})
    else:
        monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_engine_dir=str(engine)))
    result = renderer.detectar()
    assert result["motor"] == str(engine.resolve())
    assert result["motivo"].startswith("La carpeta del motor Molcy está incompleta")


def test_estimacion_sin_motor_no_lee_la_copia_del_desarrollador(monkeypatch, sin_configuracion):
    import asyncio
    import uuid
    monkeypatch.setattr(renderer, "listar", lambda *_: [])
    monkeypatch.setattr(renderer, "capacidad_estimada", lambda: {})
    original_is_dir = Path.is_dir
    monkeypatch.setattr(Path, "is_dir", lambda p: True if str(p) == r"E:\proyect3d" else original_is_dir(p))
    monkeypatch.setattr(molcy.cpu, "huella_motor", lambda *_: pytest.fail("La estimación no debe leer E:\\proyect3d sin configuración"))
    monkeypatch.setattr(molcy.cpu, "recursos", lambda: {"cpu_hilos": 2, "cpu_hilos_disponibles": 4, "cpu_hilos_maximos": 3, "cpu_modelo": "QA2", "cpu_equipo_sha256": "qa2"})
    req = molcy.EstimacionFoto(orientacion="vertical", resolucion="1080p", dispositivo="cpu", cpu_hilos=2)
    value = asyncio.run(molcy.estimacion_foto(req, SimpleNamespace(id=uuid.uuid4())))
    assert value["estimado_s"] is None
    assert value["muestras"] == 0
