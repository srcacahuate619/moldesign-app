"""La pestaña Evaluación sabe a qué corrida pertenece el sello.

Al reevaluar una molécula, `blockchain_tx_id` se conserva (fase 4 de la
auditoría `ae4db6a`), pero describe la corrida anterior. Moldex ya lo declaraba
con `matches_current_run`; `EvaluationResultRead` no traía `certified_task_id`,
y la pestaña Evaluación decía «Certificado» con la firma de otra corrida.

La regla es una sola (`services/blockchain/sello.py`) y aquí se fija que el
resultado de evaluación y Moldex la aplican igual.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api import moldex
from core.models import EvaluationResultRead
from services.blockchain.sello import sello_describe_la_corrida
from tests.test_f21_payload import _base_payload


def _resultado(**campos) -> EvaluationResultRead:
    return EvaluationResultRead.model_validate({**_base_payload(), **campos})


@pytest.mark.parametrize(
    ("campos", "esperado"),
    [
        # Sello de esta misma corrida.
        ({"blockchain_tx_id": "firma", "certified_task_id": "t-2", "certified_total_score": 71.5,
          "task_id": "t-2", "total_score": 71.5}, True),
        # Reevaluada después de certificar: el sello es de t-1.
        ({"blockchain_tx_id": "firma", "certified_task_id": "t-1", "certified_total_score": 71.5,
          "task_id": "t-2", "total_score": 64.0}, False),
        # Misma tarea y score distinto: no describe lo que se enseña.
        ({"blockchain_tx_id": "firma", "certified_task_id": "t-2", "certified_total_score": 71.5,
          "task_id": "t-2", "total_score": 64.0}, False),
        # Un cero medido es un valor, no un faltante (MOLDEX-SCI-002).
        ({"blockchain_tx_id": "firma", "certified_task_id": "t-2", "certified_total_score": 0.0,
          "task_id": "t-2", "total_score": 0.0}, True),
        # Sello anterior a v14: no registra qué corrida cubrió.
        ({"blockchain_tx_id": "firma", "certified_task_id": None, "task_id": "t-2",
          "total_score": 71.5}, None),
        # Sin sello.
        ({"blockchain_tx_id": None, "task_id": "t-2", "total_score": 71.5}, None),
    ],
)
def test_el_resultado_declara_si_el_sello_es_de_esta_corrida(campos, esperado):
    datos = _resultado(**campos).model_dump()
    assert datos["seal_matches_current_run"] is esperado
    assert "certified_task_id" in datos
    assert "certified_total_score" in datos


def test_una_fila_antigua_sin_las_columnas_valida_como_indeterminada():
    fila = SimpleNamespace(**{**_base_payload(), "blockchain_tx_id": "firma"})
    resultado = EvaluationResultRead.model_validate(fila)
    assert resultado.certified_task_id is None
    assert resultado.seal_matches_current_run is None


@pytest.mark.parametrize(
    ("sellada", "score_sellado", "vigente", "score_vigente"),
    [("t-1", 50.0, "t-1", 50.0), ("t-1", 50.0, "t-2", 50.0), (None, None, "t-2", 50.0)],
)
def test_moldex_y_evaluacion_aplican_la_misma_regla(sellada, score_sellado, vigente, score_vigente):
    fila = SimpleNamespace(
        blockchain_tx_id="firma",
        certified_task_id=sellada,
        certified_total_score=score_sellado,
        task_id=vigente,
        total_score=score_vigente,
    )
    esperado = sello_describe_la_corrida(
        tx_id="firma",
        certified_task_id=sellada,
        certified_total_score=score_sellado,
        task_id=vigente,
        total_score=score_vigente,
    )
    assert moldex._estado_del_sello(fila)["matches_current_run"] is esperado
    evaluacion = _resultado(
        blockchain_tx_id="firma",
        certified_task_id=sellada,
        certified_total_score=score_sellado,
        task_id=vigente,
        total_score=score_vigente,
    )
    assert evaluacion.seal_matches_current_run is esperado
