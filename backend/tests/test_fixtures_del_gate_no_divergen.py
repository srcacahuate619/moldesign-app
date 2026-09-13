"""Los dos ficheros que escriben el MISMO fixture no pueden separarse.

═══════════════════════════════════════════════════════════════════════════
LO QUE PASÓ
═══════════════════════════════════════════════════════════════════════════

`scripts/generate_goldens.py` sella las corridas doradas y
`scripts/verify_embedded_dossier.py` comprueba que el runtime EMBEBIDO produce
lo mismo. Para eso los dos necesitan la misma entrada, y cada uno la llevaba
escrita a mano. El segundo lo declaraba en un comentario —«las entradas son las
mismas que sella `generate_goldens.py`»— sin nada que lo garantizara.

Al corregir el detector de warheads a V2 se actualizó uno y no el otro. El gate
falló con este mensaje:

    golden   : '0.8833 · M5_ZN_ACE_1O86_V2 …'
    embebido : '0.8532 · M5_ZN_ACE_1O86_V1 …'
    Una diferencia EXIGE explicación.

Y la explicación no era la que el mensaje sugiere. El gate existe para detectar
que **el código embebido** produzca algo distinto del código del repositorio;
lo que detectó fue que **dos copias de una constante** habían divergido. Con
entradas distintas no compara el producto: compara los fixtures.

Cuesta doce minutos de build descubrirlo. Cuesta un segundo aquí.

Y la forma peligrosa es la contraria: si alguien actualiza los dos a la vez con
un valor equivocado, el gate pasa con el producto mal.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GENERADOR = RAIZ / "scripts" / "generate_goldens.py"
GATE = RAIZ / "scripts" / "verify_embedded_dossier.py"

#: Las claves que los dos ficheros declaran para el mismo caso. Si aparece una
#: nueva en ambos lados, añádela: lo que esta prueba vigila es que ninguna se
#: quede a medio actualizar.
CLAVES = ("ums_warhead", "m5_score", "m5_protocol_id", "xgb_score")


def _valores(ruta: Path, clave: str) -> set[str]:
    """Los valores LITERALES que un fichero asigna a esa clave.

    Sólo números y cadenas entre comillas: los dos ficheros también escriben
    expresiones —`"m5_score": resultado.m5_score`— cuando el valor sale del
    objeto en vez de ser un dato de entrada, y ésas no son el fixture.
    """
    texto = ruta.read_text(encoding="utf-8")
    crudos = re.findall(rf'"{clave}"\s*:\s*([^,\n}}]+)', texto)
    literales = set()
    for v in (x.strip() for x in crudos):
        if re.fullmatch(r'-?\d+(\.\d+)?', v) or re.fullmatch(r'"[^"]*"', v):
            literales.add(v)
    return literales


@pytest.mark.parametrize("clave", CLAVES)
def test_los_dos_ficheros_declaran_los_mismos_valores(clave: str):
    del_generador = _valores(GENERADOR, clave)
    del_gate = _valores(GATE, clave)

    assert del_generador, f"{GENERADOR.name} ya no declara «{clave}»"
    assert del_gate, f"{GATE.name} ya no declara «{clave}»"

    solo_generador = del_generador - del_gate
    solo_gate = del_gate - del_generador
    assert not solo_generador and not solo_gate, (
        f"«{clave}» divergió entre los dos ficheros.\n"
        f"  sólo en {GENERADOR.name}: {sorted(solo_generador)}\n"
        f"  sólo en {GATE.name}:      {sorted(solo_gate)}\n"
        "Los dos tienen que describir la MISMA entrada, o el gate del dossier "
        "embebido deja de comparar el producto y pasa a comparar sus fixtures."
    )


def test_ninguno_se_quedo_en_la_version_anterior_del_protocolo():
    """La forma concreta en que se rompió: uno en V2 y el otro en V1."""
    for ruta in (GENERADOR, GATE):
        texto = ruta.read_text(encoding="utf-8")
        rezagados = re.findall(r'"(M5_ZN_\w+?_V1)"', texto)
        assert not rezagados, (
            f"{ruta.name} todavía nombra {sorted(set(rezagados))}. El protocolo "
            "vigente es V2 desde que se corrigió el detector de warheads."
        )
