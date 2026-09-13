"""
Ningún ejecutable de consola debe abrir una ventana en Windows.

# El fallo, y por qué no se veía

Tres sitios del backend creían estar protegidos con:

    creationflags=getattr(_asyncio.subprocess, "CREATE_NO_WINDOW", 0)

`CREATE_NO_WINDOW` vive en el módulo `subprocess`, **no** en
`asyncio.subprocess`. Medido sobre el intérprete que se empaqueta:

    hasattr(asyncio.subprocess, "CREATE_NO_WINDOW")      ->  False
    getattr(asyncio.subprocess, "CREATE_NO_WINDOW", 0)   ->  0
    subprocess.CREATE_NO_WINDOW                          ->  0x8000000

El valor por defecto del `getattr` convirtió un módulo equivocado en un cero
silencioso: esos tres sitios pasaban `creationflags=0`, exactamente igual que
no pasar nada. Y los cuatro de `vina_service` —Vina, Open Babel, el exportador
de Meeko— no lo pasaban en absoluto.

En producción el backend corre bajo Tauri, que es un proceso GUI: cada uno de
esos lanzamientos parpadea una consola negra y puede robar el foco, decenas de
veces por evaluación.

Estas pruebas fijan dos propiedades: **la constante es la de verdad**, y
**nadie vuelve a leerla del módulo equivocado**.
"""

import ast
import asyncio.subprocess
import subprocess
import sys
from pathlib import Path

import pytest

from utils.procesos import BANDERAS_SIN_VENTANA

RAIZ = Path(__file__).resolve().parents[1]

#: Los módulos que lanzan ejecutables de consola.
LANZADORES = [
    "services/docking/vina_service.py",
    "services/pipeline/runner.py",
    "services/docking/queue_handler.py",
    "services/ai/local_llm.py",
    "services/ai/resource_manager.py",
    "services/motores/sidecar.py",
]


def test_la_constante_no_esta_en_asyncio_subprocess():
    """La premisa del fallo, comprobada en vez de recordada."""
    assert not hasattr(asyncio.subprocess, "CREATE_NO_WINDOW")


@pytest.mark.skipif(sys.platform != "win32", reason="bandera exclusiva de Windows")
def test_en_windows_la_bandera_no_es_cero():
    assert BANDERAS_SIN_VENTANA & subprocess.CREATE_NO_WINDOW
    # Y el grupo de proceso propio: sin él, un Ctrl-C en la consola padre mata
    # el acoplamiento en curso.
    assert BANDERAS_SIN_VENTANA & subprocess.CREATE_NEW_PROCESS_GROUP


@pytest.mark.skipif(sys.platform == "win32", reason="comportamiento fuera de Windows")
def test_fuera_de_windows_la_bandera_es_cero():
    """`creationflags` distinto de 0 en POSIX es un error, no una opción."""
    assert BANDERAS_SIN_VENTANA == 0


@pytest.mark.parametrize("ruta", LANZADORES)
def test_nadie_lee_la_bandera_del_modulo_equivocado(ruta: str):
    fuente = (RAIZ / ruta).read_text(encoding="utf-8")
    assert "_asyncio.subprocess, \"CREATE_NO_WINDOW\"" not in fuente
    assert "asyncio.subprocess, \"CREATE_NO_WINDOW\"" not in fuente


@pytest.mark.parametrize("ruta", LANZADORES)
def test_todo_lanzamiento_declara_creationflags(ruta: str):
    """Cada `create_subprocess_exec` / `Popen` / `run` pasa la bandera.

    Es una comprobación estructural porque el síntoma —un destello de consola—
    sólo se ve en un Windows con interfaz, y no en la suite.
    """
    arbol = ast.parse((RAIZ / ruta).read_text(encoding="utf-8"))
    lanzamientos = {"create_subprocess_exec", "create_subprocess_shell", "Popen", "run"}
    sin_bandera = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        nombre = getattr(nodo.func, "attr", None) or getattr(nodo.func, "id", None)
        if nombre not in lanzamientos:
            continue
        # `run` es un nombre común; sólo cuenta si es sobre `subprocess`.
        if nombre == "run":
            base = getattr(nodo.func, "value", None)
            if getattr(base, "id", None) != "subprocess":
                continue
        if not any(k.arg == "creationflags" for k in nodo.keywords):
            sin_bandera.append(nodo.lineno)

    assert not sin_bandera, (
        f"{ruta}: lanzamientos sin `creationflags` en las líneas {sin_bandera}. "
        f"Usa `BANDERAS_SIN_VENTANA` de `utils/procesos.py` o en Windows "
        f"parpadeará una consola."
    )
