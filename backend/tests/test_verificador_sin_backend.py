"""El verificador de paquetes corre sólo con la biblioteca estándar (FEP-06-HUM, 2026-10-26).

Los revisores externos de FEP-06-HUM lo ejecutan con su propio Python, sin instalar el backend. Antes fallaba con
`No module named 'starlette'`: `core.i18n` importaba Starlette arriba del todo, y `verify.py` tomaba dos constantes
de `package.py`, que arrastra pydantic. Aquí el verificador corre en un proceso que sólo deja importar la biblioteca
estándar y los módulos propios del backend (`core`, `services`); `-S` no basta con python-embed, cuyo `._pth`
añade `site-packages` igual.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.test_dossier_package import _paquete

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_dossier_package.py"

_BLOQUEO = """
import importlib.abc, runpy, sys
PERMITIDOS = set(sys.stdlib_module_names) | {"core", "services"}

class Bloqueo(importlib.abc.MetaPathFinder):
    def find_spec(self, nombre, path=None, target=None):
        if nombre.split(".")[0] not in PERMITIDOS:
            raise ModuleNotFoundError(f"fuera de la biblioteca estándar: {nombre}")
        return None

sys.meta_path.insert(0, Bloqueo())
"""


def _correr(codigo: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-I", "-c", _BLOQUEO + codigo],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def test_el_verificador_corre_sin_dependencias_del_backend(tmp_path):
    datos, _, _ = _paquete()
    zip_ = tmp_path / "paquete.zip"
    zip_.write_bytes(datos)
    proceso = _correr(
        f"sys.argv = [{str(SCRIPT)!r}, {str(zip_)!r}, '--lang', 'en']\n"
        f"runpy.run_path({str(SCRIPT)!r}, run_name='__main__')\n"
    )
    assert "fuera de la biblioteca" not in proceso.stderr, proceso.stderr
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
    assert "VALID" in proceso.stdout and "INVALID" not in proceso.stdout
    assert "Package: paquete.zip" in proceso.stdout


def test_el_bloqueo_ve_una_dependencia_del_backend():
    """Control negativo: con el mismo bloqueo, `package.py` (que arrastra pydantic) no se importa. Si esto deja de
    fallar, la prueba de arriba no demuestra nada."""
    backend = str(Path(__file__).resolve().parents[1])
    proceso = _correr(f"sys.path.insert(0, {backend!r})\nimport services.dossier.package\n")
    assert proceso.returncode != 0
    assert "fuera de la biblioteca" in proceso.stderr
