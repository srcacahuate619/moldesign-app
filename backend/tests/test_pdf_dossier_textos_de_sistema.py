"""Grupo 2 de los arreglos de PDF (2026-11-11): ningún código interno sin traducir en el dossier.

La cápsula de QA midió, en 14 de 14 corridas, que el dossier imprimía `prepare-evidence` (tipo de estudio), `completed` (estado
técnico) y `docking_vina` (política de heteroátomos) tal como los guarda el caso, y que a un receptor «Verificado» le añadía
«Condición declarada: ENSAYO_DTBZ_PLAQUETAS». Estas pruebas GENERAN el PDF y leen su texto.
"""
from __future__ import annotations

import importlib.util
import io
import re

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("reportlab") is None or importlib.util.find_spec("pypdf") is None,
    reason="reportlab o pypdf no disponibles en este entorno",
)

CODIGOS = ("prepare-evidence", "completed", "docking_vina", "ENSAYO_DTBZ_PLAQUETAS", "KD_POR_LOTE_NO_ADJUDICADO")


def _texto(datos: bytes) -> str:
    import pypdf

    return "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(datos)).pages)


def _dossier_pdf(idioma: str, **cambios) -> str:
    from core.i18n import reset_request_locale, set_request_locale
    from services.dossier.model import build_case_dossier
    from services.dossier.pdf import render_dossier_pdf
    from tests.fixtures_dossier import caso_completo

    caso = caso_completo()
    # El caso de la fixture explora una hipótesis; el que la cápsula midió era «preparar evidencia».
    caso["projection"].context.study_kind = cambios.pop("study_kind", "prepare-evidence")
    for clave, valor in cambios.items():
        caso[clave] = valor
    token = set_request_locale(idioma)
    try:
        return _texto(render_dossier_pdf(build_case_dossier(**caso)).getvalue())
    finally:
        reset_request_locale(token)


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_el_dossier_no_imprime_los_codigos_de_sistema(idioma):
    texto = _dossier_pdf(idioma)
    visibles = [c for c in ("prepare-evidence", "completed", "docking_vina") if re.search(rf"(?<![\w-]){c}(?![\w-])", texto)]
    assert not visibles, f"códigos internos en el PDF ({idioma}): {visibles}"


def test_los_nombres_de_sistema_salen_en_cada_idioma():
    es = _dossier_pdf("es")
    en = _dossier_pdf("en")
    assert "Preparar evidencia para un cálculo posterior" in re.sub(r"\s+", " ", es)
    assert "Completada" in es
    assert "Docking con AutoDock Vina" in re.sub(r"\s+", " ", es)
    assert "Prepare evidence for a later calculation" in re.sub(r"\s+", " ", en)
    assert "Completed" in en
    assert "Docking with AutoDock Vina" in re.sub(r"\s+", " ", en)


def test_un_valor_que_no_se_conoce_se_imprime_como_llego():
    """Nunca se omite ni se adivina: la tabla sólo mejora lo que conoce."""
    texto = _dossier_pdf("es", study_kind="tipo-que-no-existe")
    assert "tipo-que-no-existe" in texto


def test_control_negativo_sin_la_tabla_los_codigos_vuelven_a_verse(monkeypatch):
    """La prueba de arriba tiene que ver lo que busca: sin los rótulos, el código sale."""
    from services.dossier import pdf

    monkeypatch.setattr(pdf, "_ROTULOS_DE_SISTEMA", {})
    texto = _dossier_pdf("es")
    assert re.search(r"(?<![\w-])completed(?![\w-])", texto)
    assert "prepare-evidence" in texto


def test_las_condiciones_del_sello_de_8t69_se_leen_como_frases():
    from services.dossier.model import _CONDICIONES_DEL_SELLO
    import json
    from pathlib import Path

    verificados = json.loads((Path(__file__).resolve().parents[1] / "data" / "receptores_verificados.json").read_text("utf-8"))
    for pdb, entrada in verificados["verificados"].items():
        for codigo in entrada["condiciones"]:
            assert codigo in _CONDICIONES_DEL_SELLO, f"{pdb}: la condición {codigo} no tiene frase y saldría como código"


def test_el_dossier_no_imprime_comillas_inversas_y_conserva_los_nombres_de_archivo():
    """«`manifest.json`» es sintaxis de Markdown: en el PDF sale como un carácter suelto (B7)."""
    texto = _dossier_pdf("es")
    assert "`" not in texto
    assert "manifest.json" in texto and "checksums.sha256" in texto
