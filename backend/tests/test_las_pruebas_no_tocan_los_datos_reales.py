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

import os
from pathlib import Path

import pytest

from services.ai import memory_store, molgraph

#: El directorio de datos del PRODUCTO. En Windows el temporal cuelga del home
#: (`AppData\Local\Temp`), así que «fuera del home» no significaría nada; lo que
#: importa es no escribir donde el investigador guarda su trabajo.
DATOS_DEL_PRODUCTO = (Path.home() / "MolDesign").resolve()

MODULOS_CON_ALMACEN = [
    pytest.param(molgraph, "_PUBLIC_DB", id="molgraph-corpus"),
    pytest.param(molgraph, "_PRIVATE_DB", id="molgraph-privado"),
    pytest.param(memory_store, "_DB_PATH", id="memoria-molchat"),
]


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


@pytest.mark.parametrize("modulo,atributo", MODULOS_CON_ALMACEN)
def test_sin_la_variable_el_almacen_si_es_el_del_producto(modulo, atributo, monkeypatch):
    """El guard es para las pruebas; en producción la ruta tiene que ser la real."""
    monkeypatch.delenv("MOLDESIGN_TESTING", raising=False)

    directorio = modulo._directorio_de_datos().resolve()

    assert directorio == DATOS_DEL_PRODUCTO / "data", (
        "fuera de las pruebas los datos viven donde siempre; el guard es sólo "
        f"para la suite (se resolvió a {directorio})"
    )


def test_el_guard_no_se_puede_desactivar_por_descuido_en_la_suite():
    """`conftest` usa `setdefault`: si alguien la pone a otra cosa, se ve aquí."""
    assert os.environ["MOLDESIGN_TESTING"] == "1"
    assert "moldesign-tests" in str(molgraph._PUBLIC_DB)
    assert "moldesign-tests" in str(memory_store._DB_PATH)
