"""El inventario i18n no cuenta como pendiente un castellano que viaja con su inglés.

`ErrorDeSubida(codigo, es, en)` y los diccionarios `{"es": …, "en": …}` traen su traducción dentro: marcarlos
pendientes subía el ratchet sin que faltara nada. Cada caso trae su control negativo: un texto español suelto,
al lado, SÍ debe contarse.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from inventario_i18n import inventariar_fuente  # noqa: E402


def _textos(fuente: str) -> list[str]:
    return [c["texto_es"] for c in inventariar_fuente(fuente, "modulo.py")]


def test_los_argumentos_de_un_error_de_subida_no_son_pendientes():
    fuente = (
        'raise ErrorDeSubida("X", "El archivo no tiene átomos que podamos leer.", '
        '"The file has no atoms we can read.")\n'
        'suelto = "Este mensaje sí puede llegar a la interfaz sin traducción."\n'
    )

    assert _textos(fuente) == ["Este mensaje sí puede llegar a la interfaz sin traducción."]


def test_un_diccionario_con_es_y_en_lleva_su_traduccion():
    fuente = (
        'aviso = {"codigo": "A", "es": "El PDBQT no tiene hidrógenos polares ni átomos de agua.", '
        '"en": "The PDBQT has no polar hydrogens or water atoms."}\n'
        'otro = {"es": "Un diccionario sin su inglés sigue siendo un pendiente del producto."}\n'
    )

    assert _textos(fuente) == ["Un diccionario sin su inglés sigue siendo un pendiente del producto."]
