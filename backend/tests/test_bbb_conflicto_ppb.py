"""La PPB alta con varios anillos aromáticos contradice un positivo: el consenso se abstiene (auditoría 1.0.4, S2-4).

Decisión del propietario, 2026-11-14. La capa 2b ya no veta. Primero deciden las demás capas; sólo si dan un POSITIVO
y la PPB válida es mayor que 92 % con al menos tres anillos aromáticos medidos, el resultado es `permeable = None`
(«no concluyente») con un motivo que nombra la predicción positiva del modelo, la PPB y los anillos. Un negativo
independiente conserva su salida y su motivo. La regla no atribuye el resultado a albúmina ni a eflujo por P-gp.

Por qué no hay mejora medida que invocar: el panel de 47 tiene exactamente dos moléculas que 2b decide (domperidona y
loperamida), ambas sustratos de P-gp en ensayos de transporte. Con los errores sin cambio (5), dos aciertos pasan a
abstenciones. La justificación es retirar un veto sin mecanismo medido, no una ganancia de aciertos.
"""

from __future__ import annotations

import pytest

from chem.bbb_consenso import decidir_bbb
from tests.test_bbb_consenso import REFERENCIA, _decidir, _fila
from tests.test_ppb_valida_bbb import ARIPIPRAZOL, PIMOZIDA, _calcular, _decidir_con

ARIPIPRAZOL_P = 0.974926


def _con(smiles, p, ppb, aro, **cambios):
    return decidir_bbb(
        smiles, p_modelo=p, ppb=ppb, anillos_aromaticos=aro,
        **{"mw": 410.0, "logp": 4.0, "tpsa": 40.0, "hbd": 0, "hba": 3, **cambios},
    )


# ── Lo que activa la capa ──────────────────────────────────────────────────────────────────────────────────────


def test_un_positivo_con_ppb_alta_y_tres_anillos_es_no_concluyente():
    d = _con(PIMOZIDA, 0.969579, 92.01, 3)

    assert d.permeable is None
    assert d.capa == "2b_conflicto_ppb_aromatico"


@pytest.mark.parametrize("ppb,aro", [(92.0, 3), (92.0, 4), (50.0, 4), (99.9, 2), (99.9, 0)])
def test_sin_ppb_mayor_que_92_o_sin_tres_anillos_el_positivo_se_conserva(ppb, aro):
    d = _con(PIMOZIDA, 0.969579, ppb, aro)

    assert d.permeable is True
    assert d.capa == "3_modelo_confiado"


def test_sin_anillos_medidos_la_capa_no_se_activa():
    """Un conteo ausente deja la señal sin activar, no la activa."""
    d = _con(PIMOZIDA, 0.969579, 99.0, None)

    assert d.permeable is True


@pytest.mark.parametrize("ppb", [100.1, -1.0, float("nan"), float("inf"), None])
def test_una_ppb_no_valida_no_activa_la_capa(ppb):
    d = _con(PIMOZIDA, 0.969579, ppb, 4)

    assert d.permeable is True


def test_la_capa_4_tambien_se_abstiene():
    """Un positivo moderado (p entre 0,50 y 0,90, que pasa los filtros) entra por el mismo camino."""
    independiente = _con(PIMOZIDA, 0.7, None, 4)
    d = _con(PIMOZIDA, 0.7, 95.0, 4)

    assert (independiente.permeable, independiente.capa) == (True, "4_modelo_moderado")
    assert (d.permeable, d.capa) == (None, "2b_conflicto_ppb_aromatico")
    assert "capa_independiente=4_modelo_moderado" in d.hallazgos


# ── Lo que NO cambia ───────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("p", [0.2, 0.49])
def test_un_negativo_del_modelo_conserva_su_salida_y_su_motivo(p):
    independiente = _con(PIMOZIDA, p, None, 4)
    d = _con(PIMOZIDA, p, 99.0, 4)

    assert (d.permeable, d.capa, d.motivo) == (independiente.permeable, independiente.capa, independiente.motivo)
    assert d.permeable is False


def test_un_negativo_de_los_filtros_conserva_su_motivo():
    """p moderado y perfil demasiado polar: la capa 4 lo veta y 2b no lo toca."""
    d = _con(PIMOZIDA, 0.7, 99.0, 4, logp=0.2, tpsa=120.0, hbd=4)

    assert (d.permeable, d.capa) == (False, "4_polar_vence_al_modelo")


def test_la_carga_permanente_y_el_anion_conservan_su_motivo():
    permanente = decidir_bbb(
        "C[N+](C)(C)CCOC(=O)C1(O)c2ccccc2-c2ccccc21", p_modelo=0.99, ppb=99.0, anillos_aromaticos=4,
        mw=340.0, logp=2.0, tpsa=60.0, hbd=1, hba=4,
    )
    anion = decidir_bbb(
        "CC(=O)Oc1ccccc1C(=O)O", p_modelo=0.99, ppb=99.0, anillos_aromaticos=4,
        mw=180.16, logp=1.31, tpsa=63.6, hbd=1, hba=3,
    )

    assert (permanente.permeable, permanente.capa) == (False, "0_carga_permanente")
    assert (anion.permeable, anion.capa) == (False, "1_anion")


def test_sin_prediccion_del_modelo_se_conserva_sin_prediccion():
    d = _con(PIMOZIDA, None, 99.0, 4)

    assert d.permeable is None
    assert d.capa == "sin_prediccion"


# ── El motivo ──────────────────────────────────────────────────────────────────────────────────────────────────


def test_el_motivo_nombra_la_prediccion_la_ppb_y_los_anillos():
    d = _con(PIMOZIDA, 0.969579, 100.0, 4)

    assert "No concluyente" in d.motivo
    assert "p = 0.970" in d.motivo
    assert "positivo" in d.motivo
    assert "100.0 %" in d.motivo
    assert "4 anillos aromáticos" in d.motivo
    assert d.p_modelo == pytest.approx(0.969579)


@pytest.mark.parametrize("palabra", ["albúmina", "albumina", "P-gp", "P-glicoproteína", "eflujo", "atrapamiento", "secuestr"])
def test_el_motivo_no_atribuye_el_resultado_a_un_mecanismo(palabra):
    d = _con(PIMOZIDA, 0.969579, 100.0, 4)

    assert palabra.lower() not in d.motivo.lower()


def test_el_motivo_nombra_la_capa_independiente_sin_perder_el_positivo():
    d = _con(PIMOZIDA, 0.969579, 100.0, 4)

    assert "capa_independiente=3_modelo_confiado" in d.hallazgos
    assert "ppb=100.0" in d.hallazgos
    assert "anillos_aromaticos=4" in d.hallazgos


# ── El panel de 47 ─────────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("nombre", ["domperidona", "loperamida"])
def test_las_dos_moleculas_que_decidia_2b_se_abstienen(nombre):
    d = _decidir(_fila(nombre))

    assert d.permeable is None
    assert d.capa == "2b_conflicto_ppb_aromatico"
    assert "capa_independiente=" in "".join(d.hallazgos)


def test_ningun_otro_farmaco_del_panel_cambia_de_veredicto():
    """Sólo domperidona y loperamida son distintas de lo que daba el consenso con 2b como veto."""
    con_ppb_alta = [
        f[0] for f in REFERENCIA
        if f[3] is not None and 92.0 < f[3] <= 100.0 and (f[9] or 0) >= 3
    ]

    assert sorted(con_ppb_alta) == ["domperidona", "loperamida"]


# ── Entre las dos piezas del producto ──────────────────────────────────────────────────────────────────────────


def test_blood_viability_guarda_el_nulo_y_su_motivo(monkeypatch):
    resultado = _calcular(monkeypatch, PIMOZIDA, 0.969579, 99.5)

    assert resultado.blood_bbb_permeable is None
    assert "No concluyente" in resultado.blood_bbb_motivo
    assert resultado.blood_ppb_category == "extreme"


def test_blood_viability_con_ppb_imposible_conserva_el_positivo(monkeypatch):
    resultado = _calcular(monkeypatch, PIMOZIDA, 0.969579, 100.52966)

    assert resultado.blood_bbb_permeable is True
    assert resultado.blood_ppb_category is None


def test_el_aripiprazol_con_dos_anillos_no_se_abstiene_con_ppb_alta():
    d = _decidir_con(ARIPIPRAZOL, ARIPIPRAZOL_P, 99.5, 2)

    assert d.permeable is True
