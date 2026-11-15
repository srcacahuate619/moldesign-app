"""Grupo 2 de los arreglos de PDF (2026-11-11): lo que el informe inglés dejaba en castellano.

La cápsula de QA midió castellano en 8 de 14 informes y dossiers ingleses: el nombre por defecto «Ligando f99cb628» y los dos
avisos de `vina_service.py` (caja amplia, ligando más grande que la caja), más el respaldo del modelo cuando falla el control de
calidad con la correlación. Estas pruebas GENERAN el informe en inglés y leen su texto.
"""
from __future__ import annotations

import importlib.util
import re

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("reportlab") is None or importlib.util.find_spec("pypdf") is None,
    reason="reportlab o pypdf no disponibles en este entorno",
)

from tests.test_pdf_informe_figuras_y_cuadros import HASH, _informe, _texto  # noqa: E402


def _en(**kw) -> str:
    from core.i18n import reset_request_locale, set_request_locale

    token = set_request_locale("en")
    try:
        return re.sub(r"\s+", " ", _texto(_informe(**kw)))
    finally:
        reset_request_locale(token)


def _avisos():
    from services.avisos import Severidad, aviso

    return [
        aviso("CAJA_BUSQUEDA_AMPLIA", Severidad.PRECAUCION,
              "La caja ocupa 34328 Å³ (> 27000 Å³). Exhaustividad efectiva: 8. El umbral y el escalón automático son una "
              "política conservadora; no garantizan convergencia de poses."),
        aviso("LIGANDO_MAYOR_QUE_LA_CAJA", Severidad.CRITICA,
              "El diámetro del ligando (21.7 Å) más 4.0 Å de margen supera el lado menor de la caja (20.0 Å). Target: "
              "USR_CB957C. Vina puede rotar el ligando, pero no hay una orientación que garantice que quepa entero: revise "
              "si las poses tocan el borde."),
    ]


def test_el_nombre_por_defecto_del_ligando_sale_en_ingles():
    texto = _en(nombre=None)
    assert f"Ligand {HASH[:8]}" in texto
    assert "Ligando" not in texto


def test_el_nombre_por_defecto_del_ligando_sigue_en_castellano_en_espanol():
    from core.i18n import reset_request_locale, set_request_locale

    token = set_request_locale("es")
    try:
        texto = re.sub(r"\s+", " ", _texto(_informe(nombre=None)))
    finally:
        reset_request_locale(token)
    assert f"Ligando {HASH[:8]}" in texto


def test_los_avisos_de_docking_salen_en_ingles():
    texto = _en(avisos=[a for a in _avisos()])
    assert "The box occupies 34328" in texto
    assert "The ligand diameter (21.7" in texto
    assert not re.search(r"\b(?:caja|ligando|exhaustividad|umbral)\b", texto, re.IGNORECASE), "castellano en el informe inglés"


def test_los_avisos_siguen_en_castellano_en_espanol():
    from core.i18n import reset_request_locale, set_request_locale

    token = set_request_locale("es")
    try:
        texto = re.sub(r"\s+", " ", _texto(_informe(avisos=_avisos())))
    finally:
        reset_request_locale(token)
    assert "La caja ocupa 34328" in texto and "El diámetro del ligando" in texto
