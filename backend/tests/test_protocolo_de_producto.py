"""B-2: una corrida dice si es comparable con las de hoy.

Los resultados de 1.0.1 no son comparables con los de 1.0.2 (receta del
receptor v7, ranking M4 v2). La comparación sólo usa lo que la corrida
persistió: `execution_provenance.receta_receptor` y `weights_calibration_id`.
Un dato ausente nunca se completa, y la ausencia no se lee como coincidencia.
"""

from __future__ import annotations

import inspect

import pytest

from core.models import EvaluationResultRead
from services.docking import protocolo_de_producto as protocolo
from services.docking.preparer import RECEPTOR_RECIPE_VERSION
from tests.test_f21_payload import _base_payload

V1 = "M4_STACKING_ALPHA_V1"


def _vigente(familia: str | None = None) -> str:
    calibracion = protocolo.calibracion_vigente(familia)
    assert calibracion, "el registro científico debe declarar una calibración vigente"
    return calibracion


def _con_receta(receta):
    return {"execution_provenance": {"receta_receptor": receta}}


def test_la_calibracion_vigente_es_la_que_usaria_el_motor():
    from scoring.engine import _get_stacking_weights

    for familia in (None, "", "gpcr", "kinase", "protease", "oncology", "familia_inventada"):
        _pesos, _fuente, _hash, calibracion = _get_stacking_weights(familia, with_provenance=True)
        assert protocolo.calibracion_vigente(familia) == calibracion, familia


@pytest.mark.parametrize(
    ("docking_protocol", "calibracion", "vigente", "diferencias"),
    [
        # 1.0.1: sin receta sellada y con el ranking M4 v1 → no comparable.
        (None, V1, False, ["calibracion_ranking"]),
        # Receta anterior aunque el ranking coincida → no comparable.
        (_con_receta(RECEPTOR_RECIPE_VERSION - 1), "VIGENTE", False, ["receta_receptor"]),
        # Las dos registradas y vigentes.
        (_con_receta(RECEPTOR_RECIPE_VERSION), "VIGENTE", True, []),
        # Receta vigente, calibración no registrada → no se afirma nada.
        (_con_receta(RECEPTOR_RECIPE_VERSION), None, None, []),
        # Receptor durable: la receta no se afirma.
        (_con_receta(None), "VIGENTE", None, []),
        # Nada registrado.
        ({}, None, None, []),
    ],
)
def test_describir_protocolo(docking_protocol, calibracion, vigente, diferencias):
    if calibracion == "VIGENTE":
        calibracion = _vigente()
    descripcion = protocolo.describir_protocolo(docking_protocol, calibracion, None)
    assert descripcion["vigente"] is vigente
    assert descripcion["diferencias"] == diferencias
    assert descripcion["receta_vigente"] == RECEPTOR_RECIPE_VERSION
    assert descripcion["calibracion_vigente"] == _vigente()


def test_una_receta_mal_tipada_no_se_toma_por_valida():
    for basura in ("7", 7.0, True):
        descripcion = protocolo.describir_protocolo(_con_receta(basura), _vigente(), None)
        assert descripcion["receta_receptor"] is None
        assert descripcion["vigente"] is None


def test_el_resultado_de_evaluacion_lo_publica():
    datos = EvaluationResultRead.model_validate({
        **_base_payload(),
        "docking_protocol": _con_receta(RECEPTOR_RECIPE_VERSION),
        "weights_calibration_id": V1,
    }).model_dump()
    assert datos["weights_calibration_id"] == V1
    assert datos["protocolo"]["vigente"] is False
    assert datos["protocolo"]["diferencias"] == ["calibracion_ranking"]


def test_vina_sella_la_receta_en_la_procedencia_de_ejecucion():
    """La corrida real se cubre en `check:evaluation-runtime`; aquí se fija que
    la clave se escribe con la constante de la receta y no con un literal."""
    from services.docking import vina_service

    fuente = inspect.getsource(vina_service)
    bloque = fuente[fuente.index("execution_provenance = {"):]
    bloque = bloque[: bloque.index("result = DockingResult(")]
    assert '"receta_receptor"' in bloque
    assert "RECEPTOR_RECIPE_VERSION if preparation_report is not None else None" in bloque
