"""Las suites no pueden escribir en `~/MolDesign`.

`core.database` ya se protegía con `MOLDESIGN_TESTING=1`: una suite nunca cae
por accidente en `~/MolDesign/data/moldesign_local.db`. Los almacenes del
asistente —el grafo químico y la memoria de MolChat— no tenían ese guard, y
dependían de que cada prueba se acordara de redirigir la ruta con `monkeypatch`.

Dependía de acordarse, y falló: al separar el corpus público del almacén privado
(MOLCHAT-BE-009), una ejecución de la suite corrió la migración sobre el
`molgraph.db` **real** de quien la ejecutaba. La migración hizo lo que debía —
mover al almacén privado, como heredado y sin dueño, lo que no venía en el seed—
y no se perdió nada, pero una prueba no tiene por qué tocar los datos de nadie.

Estas pruebas fijan el guard para que la protección no vuelva a depender de la
memoria de quien escribe la siguiente.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.config import Settings, directorio_de_datos
from services.ai import limbic_system, memory_store, molgraph
from services.ai.tools import rdkit_tools, web_tools

#: El directorio de datos del PRODUCTO. En Windows el temporal cuelga del home
#: (`AppData\Local\Temp`), así que «fuera del home» no significaría nada; lo que
#: importa es no escribir donde el investigador guarda su trabajo.
DATOS_DEL_PRODUCTO = (Path.home() / "MolDesign").resolve()

MODULOS_CON_ALMACEN = [
    pytest.param(molgraph, "_PUBLIC_DB", id="molgraph-corpus"),
    pytest.param(molgraph, "_PRIVATE_DB", id="molgraph-privado"),
    pytest.param(memory_store, "_DB_PATH", id="memoria-molchat"),
    pytest.param(limbic_system, "_STATE_PATH", id="limbic"),
    pytest.param(rdkit_tools, "_TOOL_CACHE", id="cache-herramientas"),
    pytest.param(web_tools, "_PUBCHEM_CACHE", id="cache-pubchem"),
    pytest.param(web_tools, "_CHEMBL_CACHE", id="cache-chembl"),
]

BACKEND = Path(__file__).resolve().parents[1]


def test_la_suite_declara_que_es_una_suite():
    assert os.environ.get("MOLDESIGN_TESTING") == "1", (
        "el guard depende de esta variable; la fija conftest.py al importarse"
    )


@pytest.mark.parametrize("modulo,atributo", MODULOS_CON_ALMACEN)
def test_ningun_almacen_apunta_al_home_del_usuario(modulo, atributo):
    ruta = Path(getattr(modulo, atributo)).resolve()

    assert DATOS_DEL_PRODUCTO not in ruta.parents, (
        f"{modulo.__name__}.{atributo} apunta a {ruta}, dentro de los datos "
        "reales del investigador: una prueba escribiría sobre su trabajo"
    )


@pytest.mark.parametrize("modulo", [molgraph, memory_store], ids=["molgraph", "memoria-molchat"])
def test_sin_la_variable_el_almacen_si_es_el_del_producto(modulo, monkeypatch):
    """El guard es para las pruebas; en producción la ruta es la de la base."""
    from core.config import get_settings

    monkeypatch.delenv("MOLDESIGN_TESTING", raising=False)

    directorio = modulo._directorio_de_datos().resolve()

    assert directorio == Path(get_settings().local_data_dir).resolve(), (
        "fuera de las pruebas los datos viven con la base SQLite; el guard es "
        f"sólo para la suite (se resolvió a {directorio})"
    )


def test_sin_local_data_dir_los_datos_viven_donde_siempre(monkeypatch):
    """Quien instaló la aplicación no ve ningún cambio: el defecto sigue siendo el de 1.0.1."""
    monkeypatch.delenv("LOCAL_DATA_DIR", raising=False)

    assert Path(Settings().local_data_dir).resolve() == DATOS_DEL_PRODUCTO / "data"


def test_local_data_dir_aisla_todos_los_almacenes(tmp_path):
    """F→B-005 (2026-09-23): el smoke fijaba LOCAL_DATA_DIR y aun así varios almacenes
    escribían en ~/MolDesign/data. En un proceso nuevo, sin la guardia de pruebas y
    con la variable fijada, todos tienen que colgar de ella.
    """
    datos = tmp_path / "datos"
    entorno = {k: v for k, v in os.environ.items() if k != "MOLDESIGN_TESTING"}
    entorno.update(LOCAL_DATA_DIR=str(datos), SECRET_KEY="x" * 64, PYTHONPATH=str(BACKEND))
    # El Python embebido ignora PYTHONPATH (lleva un ._pth): la ruta va en el código.
    codigo = "; ".join((
        f"import json, sys; sys.path.insert(0, {str(BACKEND)!r})",
        "from services.ai import limbic_system, memory_store, molgraph",
        "from services.ai.tools import rdkit_tools, web_tools",
        "print(json.dumps([str(p) for p in (molgraph._PUBLIC_DB, molgraph._PRIVATE_DB, "
        "memory_store._DB_PATH, limbic_system._STATE_PATH, rdkit_tools._TOOL_CACHE, "
        "web_tools._PUBCHEM_CACHE, web_tools._CHEMBL_CACHE)]))",
    ))
    salida = subprocess.run([sys.executable, "-c", codigo], cwd=BACKEND, env=entorno,
                            capture_output=True, text=True, timeout=120)
    assert salida.returncode == 0, salida.stderr[-2000:]
    rutas = [Path(r).resolve() for r in json.loads(salida.stdout.strip().splitlines()[-1])]
    fuera = [r for r in rutas if datos.resolve() not in r.parents]
    assert not fuera, f"almacenes que ignoran LOCAL_DATA_DIR: {fuera}"


def test_la_siembra_del_arranque_escribe_donde_lee_el_grafo(tmp_path, monkeypatch):
    """`_auto_seed_molgraph_if_missing` copiaba a ~/MolDesign/data aunque el grafo leyera de otro sitio."""
    import asyncio

    from api import main

    semilla = tmp_path / "semilla.db"
    semilla.write_bytes(b"corpus")
    destino = tmp_path / "datos" / "molgraph.db"
    monkeypatch.setattr(molgraph, "_SEED_DB", semilla)
    monkeypatch.setattr(molgraph, "_PUBLIC_DB", destino)

    asyncio.run(main._auto_seed_molgraph_if_missing())

    assert destino.read_bytes() == b"corpus"


def test_el_guard_no_se_puede_desactivar_por_descuido_en_la_suite():
    """`conftest` usa `setdefault`: si alguien la pone a otra cosa, se ve aquí."""
    assert os.environ["MOLDESIGN_TESTING"] == "1"
    assert "moldesign-tests" in str(molgraph._PUBLIC_DB)
    assert "moldesign-tests" in str(memory_store._DB_PATH)
