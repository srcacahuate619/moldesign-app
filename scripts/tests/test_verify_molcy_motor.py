"""La verificación del bundle comprueba el motor Molcy desde el backend EMPAQUETADO (restricción 1 de AGENTS.md).

    python -m pytest scripts/tests/test_verify_molcy_motor.py -q

`check:molcy-motor` mira `tools/molcy/` del repositorio; esto mira la copia que viaja en el runtime staged y comprueba que el código
instalado la encuentra con la resolución por defecto, SIN la variable `MOLDESIGN_MOLCY_DIR` que pasa Rust. El runtime staged real pesa
GB; aquí se monta uno sintético con lo único que esta comprobación toca (el módulo del backend y la carpeta del motor) y se ejecuta con
el intérprete de la prueba en lugar del empaquetado. Lo que NO demuestra: que el `python.exe` empaquetado arranque (eso lo hace
`verify:desktop-runtime` sobre el bundle real).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import verify_desktop_bundle as vdb

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def recursos(tmp_path: Path, monkeypatch) -> Path:
    """Un `resources/` mínimo con la misma forma relativa que el instalado: backend/services/molcy/motor.py y tools/molcy."""
    recursos = tmp_path / "resources"
    modulo = recursos / "backend" / "services" / "molcy"
    modulo.mkdir(parents=True)
    shutil.copy2(RAIZ / "backend" / "services" / "molcy" / "motor.py", modulo / "motor.py")
    shutil.copytree(RAIZ / "tools" / "molcy", recursos / "tools" / "molcy")
    # `python.exe` empaquetado: se sustituye por el intérprete de la prueba, conservando el resto del comando y el entorno.
    original = vdb.run_checked

    def con_interprete_de_la_prueba(command, **kwargs):
        return original([sys.executable, *command[1:]], **kwargs)

    monkeypatch.setattr(vdb, "run_checked", con_interprete_de_la_prueba)
    return recursos


def test_el_motor_que_viaja_pasa_la_verificacion(recursos):
    vdb.validate_molcy_motor(recursos)


def test_un_fichero_alterado_al_empaquetar_se_ve(recursos):
    f = recursos / "tools" / "molcy" / "scripts" / "nucleo" / "camara.py"
    f.write_bytes(f.read_bytes() + b"\n# alterado\n")
    with pytest.raises(RuntimeError, match="camara.py difiere"):
        vdb.validate_molcy_motor(recursos)


def test_un_fichero_que_el_empaquetado_se_comio_se_ve(recursos):
    (recursos / "tools" / "molcy" / "scripts" / "salida" / "render.py").unlink()
    with pytest.raises(RuntimeError, match="falta scripts/salida/render.py"):
        vdb.validate_molcy_motor(recursos)


def test_un_motor_ausente_del_runtime_es_un_empaquetado_incompleto(recursos):
    shutil.rmtree(recursos / "tools" / "molcy")
    with pytest.raises(FileNotFoundError, match="empaquetado incompleto"):
        vdb.validate_molcy_motor(recursos)


def test_se_resuelve_sin_la_variable_de_rust(recursos, monkeypatch):
    """La resolución por defecto del backend instalado (carpeta hermana de `backend/`) basta: es la que se prueba."""
    monkeypatch.setenv("MOLDESIGN_MOLCY_DIR", str(recursos / "no-existe"))
    monkeypatch.setenv("MOLDESIGN_OPENBABEL_DIR", str(recursos / "tampoco"))
    vdb.validate_molcy_motor(recursos)  # la función quita ambas del entorno de la sonda
