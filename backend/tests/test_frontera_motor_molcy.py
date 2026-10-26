"""La frontera del motor Molcy (GPL-3.0-or-later): el backend no lo importa y el motor no importa al backend.

Mismo patrón que `test_guarda_frontera_open_babel.py`: el motor se ejecuta por subproceso y se comunica por ficheros. Un `import bpy` o un
`from nucleo import ...` en el backend lo convertiría en una sola obra con el producto (PolyForm Noncommercial) y destruiría la frontera
de programa independiente sobre la que se distribuye junto al instalador. Ver `docs/95_ADR_MOTOR_MOLCY_EN_EL_INSTALADOR.md`.
"""

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CARPETAS_DEL_PRODUCTO = ("backend", "rescoring")
#: Lo que sólo existe dentro de Blender o es del motor: ningún módulo del producto puede importarlo.
PROHIBIDOS_EN_EL_PRODUCTO = {"bpy", "bmesh", "mathutils", "bl_ext", "molecularnodes", "maestro", "nucleo", "marca", "sujetos",
                             "guiones", "variables", "salida", "formatos", "correr_caso"}
#: Lo que el motor no puede importar: el producto.
PROHIBIDOS_EN_EL_MOTOR = {"backend", "services", "api", "core", "db", "rescoring", "utils"}
#: Módulos del producto que se llaman como uno del motor pero NO lo son (paquetes propios del backend con ese nombre).
HOMONIMOS_DEL_PRODUCTO = {"core", "db", "utils", "salida", "variables"}


def raices_importadas(fuente: str) -> set[str]:
    """Nombres de primer nivel que importa un módulo, incluidos los imports dinámicos con nombre constante."""
    encontrados: set[str] = set()
    for nodo in ast.walk(ast.parse(fuente)):
        if isinstance(nodo, ast.Import):
            encontrados.update(a.name.split(".")[0] for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            encontrados.add(nodo.module.split(".")[0])
        elif (isinstance(nodo, ast.Call) and getattr(nodo.func, "id", getattr(nodo.func, "attr", "")) in {"import_module", "__import__"}
              and nodo.args and isinstance(nodo.args[0], ast.Constant) and isinstance(nodo.args[0].value, str)):
            encontrados.add(nodo.args[0].value.split(".")[0])
    return encontrados


# --- El detector tiene que demostrar que ve (AGENTS.md, restricción 2) -----------------------------------------------------------

@pytest.mark.parametrize("fuente,esperado", [
    ("import bpy", {"bpy"}),
    ("from nucleo import rutas", {"nucleo"}),
    ("import molecularnodes.entities as e", {"molecularnodes"}),
    ("import importlib\nm = importlib.import_module('bl_ext.blender_org.molecularnodes')", {"importlib", "bl_ext"}),
    ("m = __import__('bpy')", {"bpy"}),
    ("from . import x\nfrom .y import z", set()),
    ("import json, os", {"json", "os"}),
])
def test_el_detector_ve_los_imports(fuente, esperado):
    assert raices_importadas(fuente) == esperado


# --- La frontera real ---------------------------------------------------------------------------------------------------------

def _py_del_producto():
    for carpeta in CARPETAS_DEL_PRODUCTO:
        for ruta in (REPO / carpeta).rglob("*.py"):
            if "python-embed" in ruta.parts or "__pycache__" in ruta.parts:
                continue
            yield ruta


def test_el_producto_no_importa_nada_del_motor_ni_de_blender():
    ofensas = []
    revisados = 0
    for ruta in _py_del_producto():
        revisados += 1
        # `salida`, `variables`, `core`... son nombres corrientes: sólo cuentan los que no son paquetes del propio producto.
        raices = raices_importadas(ruta.read_text(encoding="utf-8")) - HOMONIMOS_DEL_PRODUCTO
        malos = raices & PROHIBIDOS_EN_EL_PRODUCTO
        if malos:
            ofensas.append(f"{ruta.relative_to(REPO).as_posix()}: {sorted(malos)}")
    assert revisados > 300, f"el recorrido miró {revisados} ficheros: ¿cambió la estructura?"
    assert not ofensas, "El producto importa el motor o Blender (frontera GPL):\n  " + "\n  ".join(ofensas)


def test_el_motor_no_importa_nada_del_producto():
    ofensas = []
    ficheros = list((REPO / "tools" / "molcy").rglob("*.py"))
    assert len(ficheros) > 30
    for ruta in ficheros:
        malos = raices_importadas(ruta.read_text(encoding="utf-8")) & (PROHIBIDOS_EN_EL_MOTOR - {"core", "db", "utils"})
        if malos:
            ofensas.append(f"{ruta.relative_to(REPO).as_posix()}: {sorted(malos)}")
    assert not ofensas, "El motor importa el producto:\n  " + "\n  ".join(ofensas)


def test_el_backend_sólo_ejecuta_el_motor_por_subproceso_con_ruta_absoluta():
    """`renderer._ejecutar` lanza PowerShell con la ruta ABSOLUTA del `correr_caso.ps1` del motor elegido y de Blender: nunca por PATH."""
    fuente = (REPO / "backend" / "services" / "molcy" / "renderer.py").read_text(encoding="utf-8")
    assert 'str(engine / "scripts" / "correr_caso.ps1")' in fuente
    assert '"-Blender", cfg["blender"]' in fuente
    assert "shutil.which" not in fuente
