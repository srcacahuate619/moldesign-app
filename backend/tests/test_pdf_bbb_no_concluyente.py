"""El informe PDF muestra el motivo de una abstención de BBB, no «Salida no serializada» (auditoría 1.0.4, S2-4).

Con la capa 2b como conflicto, el consenso devuelve `permeable = None` con un motivo. El informe imprimía «N/A» y
«Salida no serializada.» para cualquier nulo, así que una abstención registrada se leía como un dato que no se guardó.
Ahora un nulo con motivo sale como «No concluyente» con el motivo de la corrida, en los dos idiomas; un nulo sin
motivo conserva «N/A» y la frase de siempre.
"""

from __future__ import annotations

import importlib.util
import re

import pytest

from chem.bbb_consenso import decidir_bbb
from tests.test_pdf_i18n_layer3 import _capturar_pdf

PIMOZIDA = "O=C1Nc2ccccc2N1C1CCN(CCCC(c2ccc(F)cc2)c2ccc(F)cc2)CC1"

pytestmark = pytest.mark.skipif(importlib.util.find_spec("reportlab") is None, reason="reportlab no disponible")


def _conflicto():
    return decidir_bbb(
        PIMOZIDA, p_modelo=0.969579, ppb=99.5, anillos_aromaticos=4, mw=461.5, logp=5.9, tpsa=38.1, hbd=1, hba=2,
    )


def _sin_prediccion():
    return decidir_bbb(
        PIMOZIDA, p_modelo=None, ppb=None, anillos_aromaticos=4, mw=461.5, logp=5.9, tpsa=38.1, hbd=1, hba=2,
    )


def _con_bbb(permeable, motivo):
    def configurar(_target, result):
        result.blood_bbb_permeable = permeable
        result.blood_bbb_motivo = motivo

    return configurar


def test_la_abstencion_por_conflicto_sale_en_el_pdf_en_castellano(monkeypatch):
    decision = _conflicto()
    assert decision.permeable is None and decision.capa == "2b_conflicto_ppb_aromatico"

    _pdf, texto, _meta = _capturar_pdf(monkeypatch, "es", _con_bbb(None, decision.motivo))

    assert "No concluyente" in texto
    assert "el modelo de permeabilidad da p = 0.970" in texto
    assert "99.5 %" in texto and "4 anillos aromáticos" in texto
    assert "Salida no serializada" not in texto


def test_la_abstencion_por_conflicto_sale_en_el_pdf_en_ingles_sin_castellano(monkeypatch):
    decision = _conflicto()

    _pdf, texto, _meta = _capturar_pdf(monkeypatch, "en", _con_bbb(None, decision.motivo))

    assert "Inconclusive" in texto
    assert "the permeability model gives p = 0.970" in texto
    assert "99.5 %" in texto and "4 aromatic rings" in texto
    assert "Output not serialized" not in texto
    assert not re.search(r"[áéíóúñ¿¡]", texto.replace("Ácido Mefenámico (entrada)", "")), "quedó castellano en el informe en inglés"


def test_sin_prediccion_tambien_sale_con_su_motivo_en_los_dos_idiomas(monkeypatch):
    decision = _sin_prediccion()
    assert decision.capa == "sin_prediccion"

    _pdf, es, _m = _capturar_pdf(monkeypatch, "es", _con_bbb(None, decision.motivo))
    _pdf, en, _m = _capturar_pdf(monkeypatch, "en", _con_bbb(None, decision.motivo))

    assert "No hay predicción de permeabilidad" in es
    assert "No permeability prediction: the ADMET model was not available" in en
    assert "Output not serialized" not in en and "Salida no serializada" not in es


@pytest.mark.parametrize("idioma,rotulo,frase", [("es", "N/A", "Salida no serializada"), ("en", "N/A", "Output not serialized")])
def test_un_nulo_sin_motivo_conserva_na_y_la_frase_de_siempre(monkeypatch, idioma, rotulo, frase):
    _pdf, texto, _meta = _capturar_pdf(monkeypatch, idioma, _con_bbb(None, None))

    assert rotulo in texto
    assert frase in texto
    assert "No concluyente" not in texto and "Inconclusive" not in texto


@pytest.mark.parametrize("permeable,es,en", [(True, "Permeable (SNC+)", "Permeable (CNS+)"), (False, "No permeable (SNC-)", "Not permeable (CNS−)")])
def test_un_veredicto_con_valor_no_cambia(monkeypatch, permeable, es, en):
    _pdf, texto_es, _m = _capturar_pdf(monkeypatch, "es", _con_bbb(permeable, "Un motivo cualquiera."))
    _pdf, texto_en, _m = _capturar_pdf(monkeypatch, "en", _con_bbb(permeable, "Un motivo cualquiera."))

    assert es in texto_es
    assert en in texto_en
    assert "No concluyente" not in texto_es and "Inconclusive" not in texto_en
