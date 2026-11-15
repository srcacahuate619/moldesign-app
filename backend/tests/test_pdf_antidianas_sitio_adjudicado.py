"""El informe PDF marca la anti-diana que cruza el umbral con el sitio sin adjudicar (D-09, segunda opinión).

La segunda opinión del 2026-11-15 vio que el aviso del panel no llegaba al PDF: la tabla de anti-dianas decía «CRUZA
UMBRAL» sin decir si la caja estaba adjudicada a su mecanismo. Ahora el nombre lleva «†» y una nota al pie lo explica,
también en inglés. La lectura de la tabla y el umbral (estricto, como el backend) no cambian.

`pypdf` no viaja en el runtime, así que se espían los `Paragraph` y `Table` de reportlab que usa el generador en vez
de extraer el texto.
"""

from __future__ import annotations

import datetime
import uuid

import pytest

from core.models import EvaluationResultORM, MoleculeORM, TargetORM
from services.blockchain import pdf_generator


def _generar(monkeypatch, anti: list[dict]) -> tuple[list[str], list[list]]:
    parrafos: list[str] = []
    filas: list[list] = []
    # El generador envuelve Paragraph y Table dentro de la función (traducción); los de reportlab son del módulo.
    paragraph, table = pdf_generator._ReportLabParagraph, pdf_generator._ReportLabTable

    def espia_parrafo(texto, *a, **k):
        parrafos.append(str(texto))
        return paragraph(texto, *a, **k)

    def espia_tabla(datos, *a, **k):
        filas.extend(list(f) for f in datos)
        return table(datos, *a, **k)

    monkeypatch.setattr(pdf_generator, "_ReportLabParagraph", espia_parrafo)
    monkeypatch.setattr(pdf_generator, "_ReportLabTable", espia_tabla)

    target = TargetORM(pdb_id="7E2Y", name="5-HT1A", chain="R", grid_center_x=1.0, grid_center_y=2.0,
                       grid_center_z=3.0, is_private=False)
    mol = MoleculeORM(smiles="CC(=O)Oc1ccccc1C(=O)O", name="Aspirina", smiles_hash="d" * 64)
    mol.target = target
    resultado = EvaluationResultORM(
        molecule_id=uuid.uuid4(), affinity_kcal=-8.0, total_score=50.0,
        docking_poses=[{"rank": 1, "affinity": -8.0, "rmsd_lb": 0.0, "rmsd_ub": 0.0}],
        selectivity_ran=True, anti_target_results=anti, selectivity_delta_delta_g=0.8,
        selectivity_verdict="margen estrecho",
        evaluated_at=datetime.datetime(2026, 11, 15, tzinfo=datetime.timezone.utc),
    )
    datos = pdf_generator.generate_certificate_pdf(mol, resultado, target_name=target.name).getvalue()
    assert datos.startswith(b"%PDF")
    return parrafos, filas


def _nombres(filas: list[list]) -> list[str]:
    return [str(f[0]) for f in filas if f and isinstance(f[0], str)]


def test_la_que_cruza_sin_sitio_adjudicado_lleva_la_marca_y_la_nota(monkeypatch):
    parrafos, filas = _generar(monkeypatch, [
        {"pdb_id": "7UL2", "name": "OPRK1", "affinity": -7.2, "threshold": -7.0, "status": "ok",
         "sitio_adjudicado": False},
        {"pdb_id": "5VA1", "name": "hERG", "affinity": -7.4, "threshold": -7.0, "status": "ok",
         "sitio_adjudicado": True},
        {"pdb_id": "6LQA", "name": "SCN5A", "affinity": -6.0, "threshold": -7.0, "status": "ok",
         "sitio_adjudicado": False},                                  # no cruza: sin marca
        {"pdb_id": "PROPIA", "name": "Propia", "affinity": -7.5, "threshold": -7.0, "status": "ok"},
    ])
    nombres = _nombres(filas)

    assert "OPRK1 †" in nombres
    assert "hERG" in nombres and "SCN5A" in nombres and "Propia" in nombres
    assert pdf_generator._NOTA_PDF_SITIO_NO_ADJUDICADO in parrafos


@pytest.mark.parametrize("anti", [
    [{"pdb_id": "5VA1", "name": "hERG", "affinity": -7.4, "threshold": -7.0, "status": "ok", "sitio_adjudicado": True}],
    [{"pdb_id": "7UL2", "name": "OPRK1", "affinity": -7.0, "threshold": -7.0, "status": "ok",
      "sitio_adjudicado": False}],                                     # empate exacto: no cruza
    [{"pdb_id": "OLD", "name": "Antigua", "affinity": -9.0, "threshold": -7.0, "status": "ok"}],   # sin el campo
])
def test_sin_una_que_cruce_con_el_sitio_sin_adjudicar_no_hay_nota(monkeypatch, anti):
    parrafos, filas = _generar(monkeypatch, anti)
    assert pdf_generator._NOTA_PDF_SITIO_NO_ADJUDICADO not in parrafos
    assert not any(n.endswith("†") for n in _nombres(filas))


def test_la_nota_tiene_su_ingles():
    from core.i18n_plantillas import traducir
    from tests.test_dossier_en_ingles_completo import _parece_espanol

    en = traducir(pdf_generator._NOTA_PDF_SITIO_NO_ADJUDICADO, "en")
    assert en.startswith("<i>† Site not adjudicated: it has not been verified")
    assert not _parece_espanol(en.replace("<i>", "").replace("</i>", ""))
