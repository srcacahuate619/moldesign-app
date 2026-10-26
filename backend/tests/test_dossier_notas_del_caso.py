"""
AMP-05: las notas del caso llegan al dossier que lee una persona.

Las notas ya viajaban en `case_snapshot.json` del paquete pero no en el
documento humano: un canal que sólo ve quien abre el ZIP. La auditoría pidió
decidir si son privadas o parte del documento y comunicarlo. Decisión: parte del
documento (si salen del equipo, se ven), rotuladas como lo que son —contexto
libre que no entra en ningún cálculo— y declaradas así en el formulario.
"""

from __future__ import annotations

import io
import re

import pytest

from services.dossier.model import build_case_dossier
from services.dossier.pdf import render_dossier_pdf
from services.dossier.taxonomy import Estado
from tests.fixtures_dossier import caso_completo

ETIQUETA = "Notas del caso (contexto libre; no entra en ningún cálculo)"


def _caso(notas):
    caso = caso_completo()
    caso["projection"].context.notes = notas
    return caso


def _notas(dossier):
    return [c for c in dossier.proposito if c.etiqueta == ETIQUETA]


def test_las_notas_con_texto_aparecen_en_el_proposito_con_su_rotulo():
    dossier = build_case_dossier(**_caso("SOL-AUDIT-SIGUIENTE: revisión por un investigador independiente."))
    (campo,) = _notas(dossier)
    assert campo.estado == Estado.REGISTRADO
    assert campo.valor == "SOL-AUDIT-SIGUIENTE: revisión por un investigador independiente."


def test_sin_notas_no_se_imprime_un_hueco_por_un_campo_opcional():
    assert _notas(build_case_dossier(**_caso(None))) == []
    assert _notas(build_case_dossier(**_caso("   "))) == []


def test_las_notas_llegan_al_pdf():
    pypdf = pytest.importorskip("pypdf", reason="el PDF se lee con pypdf")
    marca = "NOTA-AMP05-visible-en-el-pdf"
    datos = render_dossier_pdf(build_case_dossier(**_caso(marca))).getvalue()
    texto = "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(datos)).pages)
    texto = re.sub(r"\s+", " ", texto)
    assert marca in texto
    assert "no entra en ningún cálculo" in texto
