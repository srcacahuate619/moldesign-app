"""Regresiones científicas: ausencia de SAR no equivale a cero ni identidad."""

from api.routers.sar import (
    _best_available,
    _difference,
    _first_available,
    _tanimoto_similarity,
)


def test_delta_solo_existe_si_ambas_metricas_existen():
    assert _difference(82.4, 80.0, digits=1) == 2.4
    assert _difference(None, 80.0, digits=1) is None
    assert _difference(82.4, None, digits=1) is None
    assert _difference(float("nan"), 80.0, digits=1) is None


def test_best_of_ignora_ausencias_y_no_fabrica_cero():
    assert _best_available([None, None]) is None
    assert _best_available([None, 0.0, -2.0]) == 0.0
    assert _best_available([None, -7.2, -8.1], lower_is_better=True) == -8.1


def test_score_ml_cero_es_un_valor_y_no_activa_otro_fallback():
    assert _first_available(0.0, 0.8, 0.9) == 0.0
    assert _first_available(None, 0.8, 0.9) == 0.8


def test_similitud_no_calculable_permanece_ausente():
    assert _tanimoto_similarity(None, "CCO") is None
    assert _tanimoto_similarity(object(), None) is None
    assert _tanimoto_similarity(object(), "SMILES INVALIDO") is None
