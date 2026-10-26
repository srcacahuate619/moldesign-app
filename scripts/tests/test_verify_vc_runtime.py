"""La verificación del bundle comprueba el runtime de Visual C++ para Blender desde el backend EMPAQUETADO (VM-MOLCY-01).

    python -m pytest scripts/tests/test_verify_vc_runtime.py -q

El backend da al Python de Blender las DLL de `tools/vc-runtime/` sólo si coinciden con su manifiesto. Esto comprueba que la
copia staged las trae íntegras y que el código instalado las encuentra por la resolución por defecto, sin variables. Como en
`test_verify_molcy_motor.py`, el runtime staged real pesa GB: se monta uno sintético con lo único que esta comprobación toca y
se ejecuta con el intérprete de la prueba. Lo que NO demuestra: que el `python.exe` empaquetado arranque (eso lo hace
`verify:desktop-runtime` sobre el bundle real) ni que las DLL basten en un Windows limpio (eso, una VM sin el redistribuible).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

import verify_desktop_bundle as vdb

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def recursos(tmp_path: Path, monkeypatch) -> Path:
    recursos = tmp_path / "resources"
    for relativa in ("services/molcy/runtime_vc.py", "services/molcy/__init__.py", "utils/procesos.py"):
        destino = recursos / "backend" / relativa
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / "backend" / relativa, destino)
    shutil.copytree(RAIZ / "tools" / "vc-runtime", recursos / "tools" / "vc-runtime")
    original = vdb.run_checked

    def con_interprete_de_la_prueba(command, **kwargs):
        return original([sys.executable, *command[1:]], **kwargs)

    monkeypatch.setattr(vdb, "run_checked", con_interprete_de_la_prueba)
    return recursos


def test_el_runtime_que_viaja_pasa_la_verificacion(recursos):
    vdb.validate_vc_runtime(recursos)


def test_una_dll_alterada_al_empaquetar_se_ve(recursos):
    dll = recursos / "tools" / "vc-runtime" / "x64" / "vcruntime140_1.dll"
    dll.write_bytes(dll.read_bytes()[:-1] + b"\0")
    with pytest.raises(RuntimeError, match="vcruntime140_1.dll: no coincide con su manifiesto"):
        vdb.validate_vc_runtime(recursos)


def test_una_dll_que_el_empaquetado_se_comio_se_ve(recursos):
    (recursos / "tools" / "vc-runtime" / "x64" / "msvcp140.dll").unlink()
    with pytest.raises(RuntimeError, match="msvcp140.dll: falta"):
        vdb.validate_vc_runtime(recursos)


def test_un_runtime_ausente_del_bundle_se_ve(recursos):
    shutil.rmtree(recursos / "tools" / "vc-runtime")
    with pytest.raises(RuntimeError, match="no encuentra su runtime de Visual C"):
        vdb.validate_vc_runtime(recursos)


def test_se_resuelve_sin_variables(recursos, monkeypatch):
    """Ni la variable de diagnóstico ni la carpeta de Open Babel que pasa Rust: la resolución por defecto basta."""
    monkeypatch.setenv("MOLDESIGN_VC_RUNTIME_DIR", str(recursos / "no-existe"))
    monkeypatch.setenv("MOLDESIGN_OPENBABEL_DIR", str(recursos / "tampoco"))
    vdb.validate_vc_runtime(recursos)
