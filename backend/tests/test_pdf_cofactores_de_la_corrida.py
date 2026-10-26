"""El PDF nombra los cofactores que conservó la corrida, y no confunde «vacía» con «ausente».

La metodología del PDF escribía «cofactores: ZN» con la lista de la diana. Hasta el arreglo de
MET-01 (2026-10-11) la evaluación descartaba esa lista y acoplaba sin el metal, así que el PDF de
esas corridas describía un receptor que no se usó. La corrida registra su lista en
`execution_provenance.receptor_prep.cofactors_whitelist`.

SCI-A-068: una lista vacía registrada es una decisión («ninguno conservado») y se imprimía
«sin whitelist registrada», lo mismo que cuando la corrida no registró nada. Cuando la lista
sale de la diana, se dice.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.i18n import reset_request_locale, set_request_locale
from services.blockchain.pdf_generator import _nota_de_cofactores


def _caso(registrada=None, declarada=("ZN",), registra=True):
    preparacion = {"chain": "A"}
    if registra:
        preparacion["cofactors_whitelist"] = list(registrada or [])
    resultado = SimpleNamespace(docking_protocol={"execution_provenance": {"receptor_prep": preparacion}})
    molecula = SimpleNamespace(target=SimpleNamespace(cofactors_whitelist=list(declarada)))
    return resultado, molecula


def test_la_corrida_que_no_conservo_el_metal_no_lo_nombra_y_dice_que_registro_vacia():
    nota = _nota_de_cofactores(*_caso(registrada=[]))
    assert "ZN" not in nota
    assert nota == "ninguno conservado (la corrida registró una lista vacía)"


def test_la_corrida_que_lo_conservo_lo_nombra():
    assert _nota_de_cofactores(*_caso(registrada=["ZN"])) == "ZN"


def test_sin_lista_registrada_se_usa_la_de_la_diana_y_se_dice():
    nota = _nota_de_cofactores(*_caso(registra=False))
    assert nota == "lista de la diana (la corrida no registró la suya): ZN"


def test_sin_protocolo_ni_diana_dice_que_no_se_registro():
    resultado = SimpleNamespace(docking_protocol=None)
    assert _nota_de_cofactores(resultado, SimpleNamespace(target=None)) == \
        "la corrida no registró la lista de cofactores"


def test_vacia_y_ausente_ya_no_dicen_lo_mismo():
    assert _nota_de_cofactores(*_caso(registrada=[])) != _nota_de_cofactores(
        SimpleNamespace(docking_protocol=None), SimpleNamespace(target=None))


@pytest.mark.parametrize("caso, esperado", [
    (dict(registrada=[]), "none kept (the run recorded an empty list)"),
    (dict(registra=False), "the target's list (the run did not record its own): ZN"),
])
def test_las_notas_tienen_ingles(caso, esperado):
    from core.i18n import translate_text
    token = set_request_locale("en")
    try:
        assert translate_text(_nota_de_cofactores(*_caso(**caso))) == esperado
    finally:
        reset_request_locale(token)
