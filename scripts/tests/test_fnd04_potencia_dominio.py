"""SCI-B-018 y SCI-B-002: los MDE de FND-04 dentro de su dominio y con la varianza observada."""
import math

import pytest

import analisis_fnd04_potencia_dominio as a


def test_la_formula_sellada_sin_dominio_da_un_efecto_imposible():
    # control negativo: la fórmula sellada devuelve 0,1322 con d = 3/33, mayor que d
    assert a.mde_modelo(33, 3 / 33) > 3 / 33
    assert a.mde_en_dominio(33, 3 / 33) is None


def test_dentro_del_dominio_coincide_con_la_formula_sellada():
    assert a.mde_en_dominio(92, 0.6304) == pytest.approx(0.2226, abs=1e-4)


def test_con_respuestas_en_mas_menos_uno_el_empirico_se_acerca_al_modelo():
    difs = [1.0] * 30 + [-1.0] * 30 + [0.0] * 40          # d = 0,6, media 0
    assert a.mde_empirico(difs) == pytest.approx(a.mde_modelo(100, 0.6), rel=0.06)  # la fórmula sellada usa n + k, no n


def test_los_casos_sellados():
    r = {c["gate"]: c for c in a.analizar()["casos"]}
    assert not r["MF-19"]["alcanzable"] and not r["MF-08"]["alcanzable"]
    assert r["D-MF-HARD-EXH4"]["alcanzable"]
    for g in ("RS-14", "RS-14-R1"):
        assert r[g]["n_difs"] == 92 and r[g]["fraccionarias"] > 0
        assert r[g]["mde_80_empirico"] < r[g]["mde_80_sellado"]
    assert r["RS-14"]["mde_80_empirico"] == pytest.approx(0.1558, abs=1e-4)


def test_mf12_con_los_87_de_evaluacion():
    r = {c["gate"]: c for c in a.analizar()["casos"]}["MF-12"]
    assert r["n_del_sellado"] == 203 and r["n"] == 87
    assert r["mde_80_sellado"] == pytest.approx(a.mde_modelo(203, 0.5), abs=1e-4)
    assert r["mde_80_en_dominio"] == pytest.approx(0.2034, abs=1e-4)
