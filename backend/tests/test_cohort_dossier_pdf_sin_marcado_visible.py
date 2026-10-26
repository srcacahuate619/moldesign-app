"""El PDF del paquete de Batch no imprime etiquetas de marcado como texto, en ningún idioma.

`parrafo("<b>Embudo estructural</b>")` escapa el texto (a propósito: lleva datos de la persona) y el PDF imprimía `<b>Embudo estructural</b>` con las
etiquetas visibles, en español y en inglés. El énfasis se pone con `negrita(...)`, que escapa el texto y no la etiqueta.
"""
import pytest
from reportlab.platypus import Paragraph

from tests.test_cohort_dossier_api import _abrir_zip
from tests.test_cohort_execution import _abrir_y_esperar, _congelar, entorno, evaluador  # noqa: F401


@pytest.mark.asyncio
@pytest.mark.parametrize("idioma", ["es", "en"])
async def test_el_pdf_de_batch_no_muestra_etiquetas_de_marcado(entorno, evaluador, idioma, monkeypatch):  # noqa: F811
    textos: list[str] = []
    original = Paragraph.__init__

    def capturar(self, text, *args, **kwargs):
        textos.append(str(text))
        original(self, text, *args, **kwargs)

    monkeypatch.setattr(Paragraph, "__init__", capturar)
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app(localization_middleware=True)
    cohorte = _congelar(client)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])
    respuesta = client.post(f"/evaluation/cohort-runs/{run_id}/dossier/package", headers={"Accept-Language": idioma})
    assert respuesta.status_code == 200, respuesta.text
    _abrir_zip(respuesta.content)

    visibles = [t for t in textos if "&lt;b&gt;" in t or "&lt;/b&gt;" in t]
    assert not visibles, f"el PDF imprime etiquetas como texto: {visibles[:3]}"
    # Y el énfasis sigue existiendo, como marcado: el embudo y las exclusiones salen en negrita.
    assert sum(1 for t in textos if t.startswith("<b>") and t.endswith("</b>")) >= 2
