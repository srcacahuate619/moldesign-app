"""
Ningún lanzamiento de procesos del backend puede olvidar `creationflags`, esté donde esté.

# Por qué otra prueba si ya existe `test_subprocesos_sin_ventana.py`

Aquélla comprueba SEIS módulos escritos a mano (`LANZADORES`). Un módulo nuevo —Molcy lanzó Blender cinco veces y
PowerShell una, todo sin bandera— no está en la lista y nadie lo mira: una lista de «lo que ya sabemos que lanza procesos»
no puede detectar lo que aún no sabemos. Ésta recorre TODOS los `.py` que viajan en el instalador (el backend sin sus
pruebas, auditorías y scripts de desarrollo) y exige la bandera en cada lanzamiento.

# Qué se midió (2026-10-04, Windows 11 build 26200, Windows Terminal como consola por defecto)

Un hijo de consola lanzado SIN bandera por un padre que Tauri arrancó con `CREATE_NO_WINDOW` hereda esa consola sin
ventana y no abre otra (0 ventanas nuevas en 147 muestras de 40 ms); el control positivo —un hijo con
`CREATE_NEW_CONSOLE`— sí fue visto por el vigilante (una ventana de Windows Terminal y su pseudoconsola). Es decir: con
el lanzamiento real de producción la bandera es redundante. Se exige igual porque (1) deja de depender de CÓMO se lanzó el
backend (un arranque manual, `tauri dev`, otro contenedor, una futura activación desde el Store) y (2) el repositorio ya
decidió esa regla en `utils/procesos.py`; una regla que sólo se cumple donde alguien se acordó no es una regla.

# Qué cuenta como lanzamiento y qué como excepción

Lanzan: `subprocess.run/Popen/check_output/check_call/call` y `asyncio.create_subprocess_exec/shell`. Una llamada es válida
si pasa `creationflags=` con algo que no sea el literal `0` (el valor por defecto de un `getattr` sobre el módulo
equivocado era 0 y fue el fallo original). La ÚNICA excepción son los abridores de carpeta de macOS y Linux (`open`,
`xdg-open`): `creationflags` distinto de cero es un error fuera de Windows y esas ramas nunca corren allí.
"""

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
#: Carpetas que NO viajan en el instalador (o no son código de producto): pruebas, auditorías, herramientas de
#: desarrollo, artefactos y datos. `bundle_helper.py` las excluye; el resto del backend sí viaja.
CARPETAS_FUERA = {"tests", "audits", "scripts", "artifacts", "data", "assets", "__pycache__"}

LANZAN_SUBPROCESS = {"run", "Popen", "check_output", "check_call", "call"}
LANZAN_ASYNCIO = {"create_subprocess_exec", "create_subprocess_shell"}
ABRIDORES_NO_WINDOWS = {"open", "xdg-open"}


def _es_abridor_no_windows(llamada: ast.Call) -> bool:
    """`subprocess.run(["open", ruta])`: rama de macOS/Linux, sin consola que ocultar."""
    if not llamada.args or not isinstance(llamada.args[0], (ast.List, ast.Tuple)) or not llamada.args[0].elts:
        return False
    primero = llamada.args[0].elts[0]
    return isinstance(primero, ast.Constant) and primero.value in ABRIDORES_NO_WINDOWS


def _bandera_del_modulo_equivocado(nodo: ast.AST) -> bool:
    """`getattr(asyncio.subprocess, "CREATE_NO_WINDOW", 0)`: devuelve 0 siempre (la constante vive en `subprocess`)."""
    if not (isinstance(nodo, ast.Call) and getattr(nodo.func, "id", None) == "getattr" and len(nodo.args) >= 2):
        return False
    base, nombre = nodo.args[0], nodo.args[1]
    return (isinstance(base, ast.Attribute) and base.attr == "subprocess"
            and getattr(base.value, "id", None) in {"asyncio", "_asyncio"}
            and isinstance(nombre, ast.Constant) and nombre.value == "CREATE_NO_WINDOW")


def lanzamientos_sin_bandera(fuente: str) -> list[tuple[int, str]]:
    """(línea, motivo) de cada lanzamiento de la fuente que no declara una bandera que de verdad oculte la consola."""
    problemas: list[tuple[int, str]] = []
    for nodo in ast.walk(ast.parse(fuente)):
        if not isinstance(nodo, ast.Call) or not isinstance(nodo.func, ast.Attribute):
            continue
        base = getattr(nodo.func.value, "id", None)
        atributo = nodo.func.attr
        lanza = (base == "subprocess" and atributo in LANZAN_SUBPROCESS) or atributo in LANZAN_ASYNCIO
        if not lanza or _es_abridor_no_windows(nodo):
            continue
        bandera = next((k for k in nodo.keywords if k.arg == "creationflags"), None)
        if bandera is None:
            problemas.append((nodo.lineno, "sin `creationflags`"))
        elif isinstance(bandera.value, ast.Constant) and bandera.value.value == 0:
            problemas.append((nodo.lineno, "`creationflags=0` equivale a no pasar nada"))
        elif any(_bandera_del_modulo_equivocado(n) for n in ast.walk(bandera.value)):
            problemas.append((nodo.lineno, "la constante se lee de `asyncio.subprocess`, donde no existe (da 0)"))
    return problemas


def _fuentes_que_viajan() -> list[Path]:
    return sorted(p for p in RAIZ.rglob("*.py") if not CARPETAS_FUERA & set(p.relative_to(RAIZ).parts[:-1]))


# --- El guardián tiene que demostrar que ve (AGENTS.md, restricción 2) -------------------------------------------------

DEBE_DETECTAR = {
    "subprocess.run sin bandera": "import subprocess\nsubprocess.run(['blender', '-b'])\n",
    "Popen sin bandera": "import subprocess\nsubprocess.Popen(['x'], stdout=None)\n",
    "check_output sin bandera": "import subprocess\nsubprocess.check_output(['x'])\n",
    "asyncio sin bandera": "import asyncio\nasync def f():\n    await asyncio.create_subprocess_exec('x')\n",
    "alias _asyncio sin bandera": "async def f():\n    await _asyncio.create_subprocess_exec('x')\n",
    "creationflags=0": "import subprocess\nsubprocess.run(['x'], creationflags=0)\n",
    "getattr sobre asyncio.subprocess": (
        "import asyncio, subprocess\n"
        "subprocess.run(['x'], creationflags=getattr(asyncio.subprocess, 'CREATE_NO_WINDOW', 0))\n"),
    "abridor que no es de otra plataforma": "import subprocess\nsubprocess.run(['explorer', '.'])\n",
}
NO_DEBE_DETECTAR = {
    "con la constante del proyecto": (
        "import subprocess\nfrom utils.procesos import BANDERAS_SIN_VENTANA\n"
        "subprocess.run(['x'], creationflags=BANDERAS_SIN_VENTANA)\n"),
    "con una variable": "import subprocess\nf = 0x08000000\nsubprocess.Popen(['x'], creationflags=f)\n",
    "asyncio con bandera": (
        "import asyncio\nasync def f():\n    await asyncio.create_subprocess_exec('x', creationflags=B)\n"),
    "abridor de macOS": "import subprocess\nsubprocess.run(['open', str(p)])\n",
    "abridor de Linux": "import subprocess\nsubprocess.run(('xdg-open', str(p)))\n",
    "otro `run` que no es de subprocess": "import foo\nfoo.run(['x'])\nrunner.run(['y'])\n",
}


@pytest.mark.parametrize("nombre", sorted(DEBE_DETECTAR))
def test_el_guardian_ve_lo_que_debe_ver(nombre: str):
    assert lanzamientos_sin_bandera(DEBE_DETECTAR[nombre]), f"el guardián no detectó: {nombre}"


@pytest.mark.parametrize("nombre", sorted(NO_DEBE_DETECTAR))
def test_el_guardian_no_acusa_lo_valido(nombre: str):
    assert lanzamientos_sin_bandera(NO_DEBE_DETECTAR[nombre]) == [], f"el guardián acusó a una llamada válida: {nombre}"


def test_el_recorrido_encuentra_el_backend_de_verdad():
    """Un recorrido que no encuentra nada «pasa» sin haber mirado (así quedó una vez un guardián con 0x08 en la expresión)."""
    fuentes = _fuentes_que_viajan()
    nombres = {p.relative_to(RAIZ).as_posix() for p in fuentes}
    assert len(fuentes) > 150
    for esperado in ("services/molcy/renderer.py", "services/docking/vina_service.py", "sidecars/esmfold/predictor.py",
                     "api/routers/agent_platform.py"):
        assert esperado in nombres, esperado
    assert not any(n.startswith(("tests/", "audits/", "scripts/")) for n in nombres)


def test_el_recorrido_ve_lanzamientos_reales():
    """Al menos una veintena de lanzamientos reales en el árbol: si fueran cero, el AST estaría ciego."""
    total = 0
    for ruta in _fuentes_que_viajan():
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute):
                if (getattr(nodo.func.value, "id", None) == "subprocess" and nodo.func.attr in LANZAN_SUBPROCESS) \
                        or nodo.func.attr in LANZAN_ASYNCIO:
                    total += 1
    assert total >= 20, total


def test_todo_lanzamiento_del_backend_oculta_su_consola():
    sin_bandera = []
    for ruta in _fuentes_que_viajan():
        for linea, motivo in lanzamientos_sin_bandera(ruta.read_text(encoding="utf-8")):
            sin_bandera.append(f"{ruta.relative_to(RAIZ).as_posix()}:{linea}: {motivo}")
    assert not sin_bandera, (
        "Lanzamientos que pueden abrir una consola en Windows. Usa `BANDERAS_SIN_VENTANA` de `utils/procesos.py`:\n  "
        + "\n  ".join(sin_bandera)
    )
