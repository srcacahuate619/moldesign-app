"""Grupo 2 de los arreglos de PDF (2026-11-11): el dossier de cohorte en inglés no deja castellano ni códigos internos.

La cápsula de QA midió que «Cada escalón se cuenta…», los pasos «PUEDE concluirse» y «Próximos pasos» y la cabecera «Afinidad Vina
obs.» salían en castellano en el PDF inglés, y que el estado de la corrida y de cada fila se imprimía como `completed`,
`duplicate_reused`, `catalogo` o `none`. Genera el PDF de una cohorte real (Vina simulado, como el resto de la suite de cohortes)
y lee su texto.
"""
import io
import re

import pytest

from tests.test_cohort_execution import _abrir_y_esperar, _congelar, entorno, evaluador  # noqa: F401

pypdf = pytest.importorskip("pypdf")

CODIGOS = ("completed", "duplicate_reused", "catalogo", "not_evaluated", "completed_with_exceptions")
# Castellano que no puede quedar en un PDF inglés: tildes y palabras funcionales (los nombres de moléculas de la fixture, no).
CASTELLANO = re.compile(r"[áéíóúñ¿¡]|\b(?:el|los|las|del|que|con|sin|una|por|para)\b", re.IGNORECASE)


def _texto_del_pdf(datos: bytes) -> str:
    return "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(datos)).pages)


async def _pdf(entorno, idioma: str) -> str:  # noqa: F811
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app(localization_middleware=True)
    cohorte = _congelar(client)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])
    respuesta = client.post(f"/evaluation/cohort-runs/{run_id}/dossier/preview", headers={"Accept-Language": idioma})
    assert respuesta.status_code == 200, respuesta.text[:300]
    return _texto_del_pdf(respuesta.content)


@pytest.mark.asyncio
async def test_el_dossier_de_cohorte_en_ingles_no_deja_castellano(entorno, evaluador):  # noqa: F811
    texto = await _pdf(entorno, "en")
    sobrantes = [ln.strip() for ln in texto.splitlines() if CASTELLANO.search(ln)]
    assert not sobrantes, f"castellano en el PDF inglés: {sobrantes[:8]}"


@pytest.mark.asyncio
@pytest.mark.parametrize("idioma", ["es", "en"])
async def test_el_dossier_de_cohorte_no_imprime_codigos_de_estado(entorno, evaluador, idioma):  # noqa: F811
    texto = await _pdf(entorno, idioma)
    # Un código como VALOR de una celda sale solo en su línea; mencionarlo en una frase («`not_evaluated` describe al
    # validador») es prosa y se dibuja en monoespaciada.
    lineas = {ln.strip() for ln in texto.splitlines()}
    visibles = [c for c in CODIGOS if c in lineas]
    assert not visibles, f"códigos internos como valor en el PDF ({idioma}): {visibles}"
    assert "`" not in texto, "comillas inversas literales (B7)"
