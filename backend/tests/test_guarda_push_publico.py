"""La guarda de publicación, puesta a prueba.

# Por qué esto existe

El 2026-09-21 la rama de desarrollo y el tag `v1.0.1` llegaron al repositorio
público con los 56 ficheros retenidos y la contraseña del servidor en el
historial. La regla que lo prohibía sólo estaba escrita en la memoria de los
agentes. `scripts/check_push_publico.py` la convierte en un hook `pre-push`.

Aquí se comprueba que la guarda ve (su autotest, fuera del hook), que su propio
código no se bloquea a sí mismo al publicarse, y que la lista de retenidos no
se ha separado del `.gitignore` de la rama `publico`, que es de donde salió.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GUARDA = RAIZ / "scripts" / "check_push_publico.py"


def _cargar_guarda():
    """Importa el script de guarda como módulo, sin ejecutar su `main`."""
    if not GUARDA.is_file():
        pytest.skip("no está scripts/check_push_publico.py")
    spec = importlib.util.spec_from_file_location("_guarda_push_publico", GUARDA)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_guarda_push_publico"] = modulo
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


guarda = _cargar_guarda()


def test_los_detectores_distinguen_sus_muestras():
    guarda._autotest_detectores()


def test_p1_ve_un_retenido_que_salio_de_la_punta():
    guarda._autotest_git(guarda.leer_retenidos())


def test_la_propia_guarda_no_dispara_p2_al_publicarse():
    # Las muestras positivas se construyen por concatenación precisamente para
    # esto: si una línea del script casara, el primer push que lo llevara al
    # remoto quedaría bloqueado por él mismo.
    for archivo in (GUARDA, Path(__file__)):
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            assert not guarda.credenciales_en(linea), f"{archivo.name}:{numero}"


def test_la_lista_coincide_con_el_gitignore_de_publico():
    resultado = subprocess.run(
        ["git", "show", "publico:.gitignore"], cwd=RAIZ,
        capture_output=True, text=True, encoding="utf-8",
    )
    if resultado.returncode != 0:
        pytest.skip("este clon no tiene la rama publico")
    bloque = resultado.stdout.split("Retenido del repositorio publico", 1)
    assert len(bloque) == 2, "el .gitignore de publico perdió su bloque de retenidos"
    _, despues_del_rotulo = bloque[1].split("\n", 1)
    en_gitignore = {
        linea.strip() for linea in despues_del_rotulo.splitlines()
        if linea.strip() and not linea.strip().startswith("#")
    }
    assert set(guarda.leer_retenidos()) == en_gitignore
