"""Ningún proceso del motor Molcy hereda la carpeta del backend (BUG-molcy-render-WindowsApps).

En el paquete instalado el backend vive en `WindowsApps`. Molecular Nodes hace `chdir` a la carpeta del .blend en
`save_post` y, al volver, Windows niega la carpeta anterior (`PermissionError: [WinError 5]`): el render termina con
código 1. Estas pruebas miran el directorio de trabajo que recibe el proceso (comportamiento real) y que cada lanzamiento
del motor pase `cwd=` (guardia estática: un lanzamiento nuevo sin él falla aquí).
"""
import ast
import os
import sys
import threading
from pathlib import Path

import utils.local_storage
from services.molcy.process import carpeta_de_proceso, run_owned

BACKEND = Path(__file__).resolve().parents[1]
MOLCY = BACKEND / "services" / "molcy"
LLAMADAS_SUBPROCESS = {"run", "Popen", "call", "check_call", "check_output"}


def test_run_owned_lanza_el_proceso_en_el_cwd_pedido(tmp_path):
    destino = tmp_path / "trabajo"
    destino.mkdir()
    salida = tmp_path / "salida.txt"
    with salida.open("w", encoding="utf-8") as log:
        run_owned([sys.executable, "-c", "import os,sys; sys.stdout.write(os.getcwd())"],
                  env=dict(os.environ), stdout=log, cancel=threading.Event(),
                  on_start=lambda _: None, timeout=60, cwd=str(destino))
    assert destino.resolve() != Path.cwd().resolve()  # sin esto la prueba no distinguiría nada
    assert Path(salida.read_text(encoding="utf-8").strip()).resolve() == destino.resolve()


def test_carpeta_de_proceso_es_de_datos_del_usuario_y_no_la_del_backend(monkeypatch, tmp_path):
    monkeypatch.setattr(utils.local_storage, "data_dir", lambda: tmp_path)
    carpeta = Path(carpeta_de_proceso())
    assert carpeta == tmp_path / "molcy" and carpeta.is_dir()
    assert BACKEND not in carpeta.parents and carpeta != BACKEND


def _llamadas_de_proceso(texto: str) -> list[tuple[int, bool]]:
    """(línea, tiene cwd) de cada `subprocess.<llamada>(...)` y de cada `run_owned(...)` del texto."""
    encontradas = []
    for nodo in ast.walk(ast.parse(texto)):
        if not isinstance(nodo, ast.Call):
            continue
        func = nodo.func
        es_subprocess = (isinstance(func, ast.Attribute) and func.attr in LLAMADAS_SUBPROCESS
                         and isinstance(func.value, ast.Name) and func.value.id == "subprocess")
        es_run_owned = isinstance(func, ast.Name) and func.id == "run_owned"
        if es_subprocess or es_run_owned:
            # Un `**kwargs` sin `cwd` explícito cuenta como sin cwd: no se puede comprobar.
            encontradas.append((nodo.lineno, any(k.arg == "cwd" for k in nodo.keywords)))
    return encontradas


def test_la_guardia_ve_los_lanzamientos_sin_cwd():
    # Un guardián tiene que demostrar que ve: muestras que debe marcar y una que no.
    sin = _llamadas_de_proceso('import subprocess\nsubprocess.run(["x"])\nrun_owned(c, env=e)\nsubprocess.Popen(["y"], **kw)\n')
    con = _llamadas_de_proceso('import subprocess\nsubprocess.run(["x"], cwd=d)\nrun_owned(c, env=e, cwd=d)\n')
    assert [tiene for _, tiene in sin] == [False, False, False]
    assert [tiene for _, tiene in con] == [True, True]


def test_todo_lanzamiento_del_motor_declara_cwd():
    hallazgos = []
    total = 0
    for ruta in sorted(MOLCY.glob("*.py")):
        for linea, tiene_cwd in _llamadas_de_proceso(ruta.read_text(encoding="utf-8")):
            total += 1
            if not tiene_cwd:
                hallazgos.append(f"{ruta.name}:{linea}")
    assert total >= 8, "la guardia no encuentra los lanzamientos del motor: revisar el recorrido"
    assert hallazgos == [], f"lanzamientos sin cwd (heredarían la carpeta del backend): {hallazgos}"
