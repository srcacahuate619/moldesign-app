"""SCI-A-022: el dossier no presenta como registrada una corrida que nadie comprobó.

Con un resultado almacenado sin `task_id`, el campo «Corrida» imprimía el
identificador que declara el caso con REGISTRADO. La falta de un identificador
guardado no demuestra que coincidan.
"""
from __future__ import annotations

import pytest

from core.i18n_plantillas import traducir
from services.dossier.model import _campo_de_la_corrida, build_case_dossier
from services.dossier.taxonomy import Estado
from tests.fixtures_dossier import caso_completo


def _corrida(dossier):
    return next(c for c in dossier.portada if c.etiqueta == "Corrida")


def test_coinciden_y_queda_registrada():
    campo = _corrida(build_case_dossier(**caso_completo()))
    assert campo.estado is Estado.REGISTRADO and campo.valor == "task-completa-0001"


def test_sin_identificador_guardado_queda_por_comprobar():
    caso = caso_completo()
    caso["eval_result"].task_id = None
    campo = _corrida(build_case_dossier(**caso))
    assert campo.estado is Estado.REVISAR
    assert campo.texto.startswith("task-completa-0001 (declarada por el caso)")
    assert "no se pudo comprobar" in campo.razon


@pytest.mark.parametrize("declarado, registrado, estado", [
    ("A", "A", Estado.REGISTRADO), ("A", None, Estado.REVISAR),
    (None, "B", Estado.REGISTRADO), ("A", "B", Estado.REVISAR),
])
def test_las_cuatro_combinaciones(declarado, registrado, estado):
    assert _campo_de_la_corrida(declarado, registrado).estado is estado


def test_sale_en_ingles():
    campo = _campo_de_la_corrida("task-7", None)
    assert traducir(campo.valor, "en") == "task-7 (declared by the case)"
    assert traducir(campo.razon, "en") != campo.razon
    otra = _campo_de_la_corrida("task-7", "task-9")
    assert traducir(otra.razon, "en") == "The stored result belongs to run «task-9»."
