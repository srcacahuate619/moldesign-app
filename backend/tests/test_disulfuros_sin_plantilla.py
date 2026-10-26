"""SCI-C-001: un puente S–S sólo se da por conservado si sus dos cisteínas son CYX.

Antes, una plantilla ausente daba el mismo «no roto» que una CYX. El camino C
con origen escribe `protonation_templates = {}`, así que un receptor sin ninguna
plantilla salía con «ninguno queda como tiol libre» sin que nada lo comprobara.
"""
from __future__ import annotations

import pytest

from services.dossier.contexto_estructural import _Atomo, _disulfuros


def _cisteina(cadena: str, numero: str, xyz) -> list:
    return [_Atomo(registro="ATOM", cadena=cadena, numero=numero, insercion="", residuo="CYS",
                   nombre="SG", altloc="", ocupacion=1.0, xyz=xyz, elemento="S")]


# Dos puentes: A:3–A:9 (S–S a 2,04 Å) y A:18–A:45.
POR_RESIDUO = {
    ("A", "3", "", "CYS"): _cisteina("A", "3", (0.0, 0.0, 0.0)),
    ("A", "9", "", "CYS"): _cisteina("A", "9", (2.04, 0.0, 0.0)),
    ("A", "18", "", "CYS"): _cisteina("A", "18", (20.0, 0.0, 0.0)),
    ("A", "45", "", "CYS"): _cisteina("A", "45", (22.04, 0.0, 0.0)),
}


def _plantillas(**por_residuo):
    return {k.replace("_", ":"): {"input_resname": "CYS", "template": v} for k, v in por_residuo.items()}


def test_dos_cyx_son_puentes_conservados():
    rotos, total, sin = _disulfuros(POR_RESIDUO, {"A"}, _plantillas(A_3="CYX", A_9="CYX", A_18="CYX", A_45="CYX"))
    assert (rotos, total, sin) == ([], 2, [])


def test_un_cys_es_un_puente_roto():
    rotos, total, sin = _disulfuros(POR_RESIDUO, {"A"}, _plantillas(A_3="CYX", A_9="CYS", A_18="CYX", A_45="CYX"))
    assert rotos == ["A:3–A:9"] and sin == []


def test_sin_ninguna_plantilla_nada_queda_evaluado():
    rotos, total, sin = _disulfuros(POR_RESIDUO, {"A"}, {})
    assert rotos == [] and total == 2
    assert sin == ["A:18–A:45", "A:3–A:9"]


def test_una_plantilla_parcial_no_basta():
    rotos, _total, sin = _disulfuros(POR_RESIDUO, {"A"}, _plantillas(A_3="CYX", A_18="CYX", A_45="CYX"))
    assert rotos == [] and sin == ["A:3–A:9"]


@pytest.mark.parametrize("terminal", ["NCYX", "CCYX"])
def test_las_variantes_terminales_de_cyx_cuentan(terminal):
    rotos, _total, sin = _disulfuros(POR_RESIDUO, {"A"}, _plantillas(A_3=terminal, A_9="CYX", A_18="CYX", A_45="CYX"))
    assert rotos == [] and sin == []


def test_un_puente_entero_fuera_del_receptor_no_se_cuenta_como_sin_evaluar():
    en_receptor = {("A", "3", ""), ("A", "9", "")}
    rotos, total, sin = _disulfuros(POR_RESIDUO, {"A"}, _plantillas(A_3="CYX", A_9="CYX"), en_receptor)
    assert (rotos, total, sin) == ([], 2, [])


def test_sin_saber_que_hay_en_el_receptor_la_ausencia_no_se_lee_como_fuera():
    rotos, total, sin = _disulfuros(POR_RESIDUO, {"A"}, _plantillas(A_3="CYX", A_9="CYX"), None)
    assert sin == ["A:18–A:45"]
