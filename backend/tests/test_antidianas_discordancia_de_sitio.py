"""D-09 (revisión final de 1.0.4): tres anti-dianas del panel de Bowes tienen una caja que el redocking reproduce pero que
NO es el sitio del ensayo que las motiva: SCN5A/6LQA (poro con quinidina frente al «site 2» de batracotoxina), OPRM1/8Y72
(modulador alostérico positivo, no el bolsillo ortostérico) y GRIN1/9GJ1 (sitio de glicina de GluN1 frente a un ensayo
competitivo en el de glutamato). Siguen acoplándose y conservan su score; la alerta dice, además del aviso genérico, por qué
esa caja no equivale al sitio del ensayo. La cuarta incompatibilidad, OPRK1/7UL2, no se acopla (ver
`test_antidiana_estructura_incompatible.py`).
"""
from __future__ import annotations

import pytest

from services.docking.selectivity import (
    AVISO_SITIO_NO_ADJUDICADO,
    discordancia_de_sitio_de,
    panel_bowes_2012,
    texto_de_alerta,
)

DISCORDANTES = {
    "6LQA": ("quinidina", "site 2"),
    "8Y72": ("alostérico", "ortostérico"),
    "9GJ1": ("glicina", "glutamato"),
}


@pytest.mark.parametrize("pdb,frases", DISCORDANTES.items())
def test_la_fila_declara_por_que_su_caja_no_es_el_sitio_del_ensayo(pdb, frases):
    texto = discordancia_de_sitio_de(pdb)
    assert texto is not None
    for frase in frases:
        assert frase in texto, (pdb, frase)


def test_solo_esas_tres_filas_la_declaran_y_ninguna_esta_adjudicada():
    con_texto = {str(f["pdb_id"]).upper() for f in panel_bowes_2012() if f.get("discordancia_de_sitio")}
    assert con_texto == set(DISCORDANTES)
    for fila in panel_bowes_2012():
        if fila.get("discordancia_de_sitio"):
            assert fila["sitio_adjudicado"] is False and fila["estado"] == "validada"


def test_lo_que_el_panel_no_dice_no_se_afirma():
    assert discordancia_de_sitio_de("5VA1") is None      # hERG, adjudicada
    assert discordancia_de_sitio_de("PROPIA") is None    # una anti-diana del usuario
    assert discordancia_de_sitio_de(None) is None
    assert discordancia_de_sitio_de("7UL2") is None      # incompatible: no se acopla, su motivo es otro


def test_la_alerta_suma_la_discordancia_al_aviso_generico_y_nada_mas():
    base = texto_de_alerta("NaV1.5", -7.6, -7.0, "arritmia", False)
    con = texto_de_alerta("NaV1.5", -7.6, -7.0, "arritmia", False, discordancia_de_sitio_de("6LQA"))
    assert con.startswith(base) and AVISO_SITIO_NO_ADJUDICADO in con
    assert "quinidina" in con and "quinidina" not in base
    # Sin sitio sin adjudicar (o sin constancia) la discordancia no se escribe: el aviso manda.
    assert texto_de_alerta("NaV1.5", -7.6, -7.0, "arritmia", True, "texto") == texto_de_alerta(
        "NaV1.5", -7.6, -7.0, "arritmia", True)
    assert texto_de_alerta("NaV1.5", -7.6, -7.0, "arritmia", None, "texto") == texto_de_alerta(
        "NaV1.5", -7.6, -7.0, "arritmia", None)


def test_la_guardia_demuestra_que_ve(monkeypatch):
    """Control negativo: si el panel pierde el texto de una fila, la lectura devuelve None y la comprobación de arriba fallaría."""
    import services.docking.selectivity as sel

    sin_texto = [{k: v for k, v in f.items() if k != "discordancia_de_sitio"} for f in panel_bowes_2012()]
    monkeypatch.setattr(sel, "panel_bowes_2012", lambda: sin_texto)
    assert sel.discordancia_de_sitio_de("6LQA") is None
    assert {str(f["pdb_id"]).upper() for f in sin_texto if f.get("discordancia_de_sitio")} != set(DISCORDANTES)
