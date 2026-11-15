"""La unión extrema a proteína plasmática se informa y no veta (auditoría científica 1.0.4, S2-4).

La capa 2a vetaba el consenso de BBB con cualquier PPB mayor que 99 %. Decisión del propietario, 2026-11-14: esa PPB
conserva la categoría «extreme» como estimación de unión plasmática y deja de cambiar el veredicto. La capa 2b (PPB
mayor que 92 % y al menos tres anillos aromáticos) sigue como estaba y cambia en el commit siguiente.

El panel de 47 no ejerce nunca 2a (su PPB máxima es 94,96 %), así que no puede medir este cambio: los controles son
fármacos de acción central con PPB predicha entre 99 y 100 %, con las salidas de ADMET-AI 2.0.1 sobre
`drugbank_approved.csv`.
"""

from __future__ import annotations

import pytest

from chem.bbb_consenso import decidir_bbb
from tests.test_bbb_consenso import REFERENCIA, _decidir
from tests.test_ppb_valida_bbb import (
    ARIPIPRAZOL,
    ARIPIPRAZOL_ADMET,
    _calcular,
    _decidir_con,
)

BUTAPERAZINA = "CCCC(=O)c1ccc2Sc3ccccc3N(CCCN4CCN(C)CC4)c2c1"
FLUPENTIXOL = "OCCN1CCN(CCC=C2c3ccccc3Sc3ccc(C(F)(F)F)cc32)CC1"

#: (nombre, SMILES, p_BBB, PPB predicha, anillos aromáticos). Los dos con dos anillos aromáticos: 2b no se activa.
CENTRALES_CON_PPB_EXTREMA = [
    ("butaperazina", BUTAPERAZINA, 0.986, 99.90, 2),
    ("flupentixol", FLUPENTIXOL, 0.981, 99.47, 2),
    ("aripiprazol", *ARIPIPRAZOL_ADMET),
]


@pytest.mark.parametrize(
    "nombre,smiles,p,ppb,aro", CENTRALES_CON_PPB_EXTREMA, ids=[fila[0] for fila in CENTRALES_CON_PPB_EXTREMA]
)
def test_un_central_con_ppb_extrema_valida_ya_no_sale_no_permeable(nombre, smiles, p, ppb, aro):
    decision = _decidir_con(smiles, p, ppb, aro)

    assert decision.permeable is True, f"{nombre}: {decision.capa} — {decision.motivo}"
    assert decision.capa == "3_modelo_confiado"


def test_la_capa_2a_ya_no_decide_ninguna_fila_del_panel():
    capas = {_decidir(fila).capa for fila in REFERENCIA}

    assert "2a_ppb_total" not in capas


def test_el_panel_no_puede_medir_este_cambio_porque_nunca_ejerce_2a():
    """Su PPB máxima es 94,96 %: ninguna fila supera 99, así que retirar 2a no mueve ni una."""
    ppb_maxima = max(f[3] for f in REFERENCIA if f[3] is not None)

    assert ppb_maxima == pytest.approx(94.96)
    assert ppb_maxima < 99.0


def test_una_ppb_extrema_no_cambia_un_negativo_independiente_ni_lo_explica():
    """Con p = 0,2 el resultado es negativo por el modelo; la PPB no figura en el motivo."""
    decision = _decidir_con(BUTAPERAZINA, 0.2, 99.9, 2)

    assert decision.permeable is False
    assert decision.capa == "defecto"
    assert "proteína plasmática" not in decision.motivo


def test_sin_modelo_una_ppb_extrema_ya_no_decide_sola():
    """Antes salía `False` por 2a aunque no hubiera predicción; ahora es «sin predicción», que no es «no permeable»."""
    decision = decidir_bbb(
        BUTAPERAZINA, p_modelo=None, ppb=99.9, anillos_aromaticos=2,
        mw=411.6, logp=4.6, tpsa=43.9, hbd=0, hba=5,
    )

    assert decision.permeable is None
    assert decision.capa == "sin_prediccion"


def test_la_categoria_sigue_diciendo_extrema(monkeypatch):
    """Lo que se conserva: la estimación de unión plasmática, como dato."""
    resultado = _calcular(monkeypatch, ARIPIPRAZOL, 0.974926, 99.5)

    assert resultado.blood_ppb_category == "extreme"
    assert resultado.blood_bbb_permeable is True


def test_una_ppb_extrema_no_activa_2b_sin_tres_anillos():
    decision = _decidir_con(ARIPIPRAZOL, 0.974926, 99.99, 2)

    assert decision.capa != "2b_conflicto_ppb_aromatico"
    assert decision.permeable is True


def test_la_constante_del_veto_retirado_ya_no_existe():
    """Que nadie vuelva a leerla creyendo que sigue siendo una regla."""
    import chem.bbb_consenso as consenso

    assert not hasattr(consenso, "PPB_ATRAPAMIENTO_TOTAL")
