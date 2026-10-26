"""Una fila del dossier más alta que una página se parte entre páginas; el PDF no falla (FEP-06-HUM, 2026-10-25).

Al exportar en inglés el paquete de 2AW1 (anhidrasa carbónica II), una celda de `_tabla_campos` medía 843 pt y la página
deja 742: ReportLab lanzaba `LayoutError` y `POST /evaluation/dossier/{id}/package` respondía 500, así que esa corrida no
tenía paquete. La docstring de `_tabla_campos` ya decía que una fila larga se parte entre páginas, pero `Table` sólo parte
entre filas, nunca dentro de una, salvo con `splitInRow=1`.
"""
from __future__ import annotations

from dataclasses import replace

from services.dossier.model import Campo, Estado, build_case_dossier
from services.dossier.pdf import render_dossier_pdf
from tests.fixtures_dossier import caso_completo

_LARGO = " ".join(f"residuo A:{n} retirado a {n / 10:.1f} Å del ligando, declarado y sin modelar;" for n in range(1, 400))


def test_una_celda_mas_alta_que_la_pagina_no_rompe_el_pdf():
    dossier = build_case_dossier(**caso_completo())
    dossier = replace(dossier, preparacion=[Campo("Campo largo", _LARGO, Estado.REGISTRADO)] + list(dossier.preparacion))
    pdf = render_dossier_pdf(dossier).getvalue()
    assert pdf.startswith(b"%PDF")


def test_sin_partir_dentro_de_la_fila_el_mismo_dossier_fallaba(monkeypatch):
    """Control negativo: la misma tabla sin `splitInRow` no cabe. Si esto deja de fallar, la prueba de arriba no ve nada."""
    import pytest
    from reportlab.platypus import Table
    from reportlab.platypus.doctemplate import LayoutError

    from services.dossier import pdf as modulo

    class SinPartir(Table):
        def __init__(self, *a, **k):
            k.pop("splitInRow", None)
            super().__init__(*a, **k)

    monkeypatch.setattr(modulo, "Table", SinPartir)
    dossier = build_case_dossier(**caso_completo())
    dossier = replace(dossier, preparacion=[Campo("Campo largo", _LARGO, Estado.REGISTRADO)] + list(dossier.preparacion))
    with pytest.raises(LayoutError):
        render_dossier_pdf(dossier)
