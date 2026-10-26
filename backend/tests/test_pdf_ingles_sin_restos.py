"""El PDF inglés de una corrida real no deja frases del sistema en castellano (B01 de la QA de 1.0.2).

# Qué se midió (2026-10-10, QA de release de Sol sobre una corrida real de 8HFI)

El PDF inglés llevaba cuatro restos que la guardia de `test_dossier_en_ingles_completo` no veía:
no tienen tildes ni dos palabras funcionales, y el caso de prueba no traía ni un motivo de
respaldo ni cadenas medidas:

* «8HFI · cadenas A (measured from…)»: la plantilla genérica «{n1} (medido sobre…)» iba antes
  que la específica y dejaba lo de delante sin traducir;
* «Receptor source: curado»: el origen estaba en la lista de datos de la persona, pero es uno de
  cinco valores del sistema;
* «fallback: Familia 'transporter' sin modelo entrenado disponible — modelo universal usado»: el
  motivo no tenía plantilla, y además la frase que lo contiene no traducía lo capturado;
* «Protocolo:» y «Procedencia:» estaban escritos tal cual en `pdf.py`.

Y en el PDF castellano, «Apéndice A. Outputs heredados».
"""
from __future__ import annotations

import copy

import pytest
from reportlab.platypus import Paragraph

from core.i18n import reset_request_locale, set_request_locale
from core.i18n_plantillas import traducir
from services.dossier.localization import ORIGENES_DEL_RECEPTOR, traducir_dossier
from services.dossier.model import build_case_dossier
from services.dossier.pdf import render_dossier_pdf
from tests.fixtures_dossier import caso_completo

#: Lo que la QA encontró en el PDF inglés. Ninguno es un dato de la persona.
RESTOS = ("cadenas", "curado", "Protocolo:", "Procedencia:", "sin modelo", "modelo universal", "Familia '")

MOTIVO = "Familia 'transporter' sin modelo entrenado disponible — modelo universal usado."
COLA = (" El motor de acoplamiento y su version se declaran en la traza de reproducibilidad, "
        "no aqui: son identidades distintas.")
COLA_EN = (" The docking engine and its version are listed in the reproducibility trace, "
           "not here; they are distinct identities.")


@pytest.mark.parametrize("es, en", [
    ("8HFI · cadenas A (medido sobre los bytes del PDBQT hasheado)",
     "8HFI · chains A (measured from the hashed PDBQT bytes)"),
    ("cadenas A+P (medido sobre los bytes del PDBQT hasheado)",
     "chains A+P (measured from the hashed PDBQT bytes)"),
    (MOTIVO, "Family 'transporter' has no trained model available — the universal model was used."),
    # El motivo, dentro de la frase del dominio del modelo: con su punto y sin él («usado.. El motor»).
    ("modelo universal; fallback: " + MOTIVO + "." + COLA,
     "universal model; fallback: Family 'transporter' has no trained model available — the universal model "
     "was used." + COLA_EN),
    ("universal; fallback: " + MOTIVO + "." + COLA,
     "universal; fallback: Family 'transporter' has no trained model available — the universal model "
     "was used." + COLA_EN),
    ("modelo universal; fallback: Familia 'protease' sin modelo validado (quality gate: p 0.266 >= 0.05) — "
     "modelo universal usado.." + COLA,
     "universal model; fallback: Family 'protease' has no validated model (quality gate: p 0.266 >= 0.05) — "
     "the universal model was used." + COLA_EN),
])
def test_cada_resto_se_traduce_entero(es, en):
    assert traducir(es, "en") == en


def test_una_frase_que_empieza_igual_no_se_traduce_a_medias():
    """{ids…} sólo casa identificadores: un párrafo que empiece por «cadenas» no se convierte en «chains …» en castellano."""
    assert traducir("cadenas A y B sin modelar", "en") == "cadenas A y B sin modelar"


@pytest.mark.parametrize("origen, en", [
    ("curado", "curated"), ("privado", "private"), ("comunidad", "community"),
    ("subido", "uploaded"), ("desconocido", "unknown"),
])
def test_el_origen_del_receptor_es_un_valor_del_sistema(origen, en):
    assert origen in ORIGENES_DEL_RECEPTOR
    caso = copy.deepcopy(caso_completo())
    caso["projection"] = caso["projection"].model_copy(deep=True)
    caso["projection"].inputs.receptor.origin = origen
    vista = traducir_dossier(build_case_dossier(**caso), "en")
    valores = [c.valor for c in _campos(vista) if c.etiqueta == "Receptor source"]
    assert valores == [en]


def _campos(valor):
    """Todos los Campo del dossier, estén en la sección que estén."""
    from dataclasses import fields, is_dataclass

    from services.dossier.model import Campo

    if isinstance(valor, Campo):
        yield valor
    elif isinstance(valor, (list, tuple)):
        for item in valor:
            yield from _campos(item)
    elif is_dataclass(valor) and not isinstance(valor, type):
        for campo in fields(valor):
            yield from _campos(getattr(valor, campo.name))


def test_los_origenes_del_backend_son_los_del_frontend():
    """El espejo no puede quedarse atrás: un origen nuevo del frontend saldría sin traducir."""
    import re
    from pathlib import Path

    tipos = (Path(__file__).resolve().parents[2] / "frontend/lib/cases/types.ts").read_text(encoding="utf-8")
    declarados = re.search(r"RECEPTOR_ORIGINS = \[([^\]]*)\]", tipos)
    assert declarados, "no se encontró RECEPTOR_ORIGINS en el frontend"
    assert tuple(re.findall(r'"([^"]+)"', declarados.group(1))) == ORIGENES_DEL_RECEPTOR


def _caso_como_el_de_la_qa() -> dict:
    """El caso completo con lo que traía la corrida real: motivo de respaldo y cadenas medidas."""
    caso = copy.deepcopy(caso_completo())
    resultado = caso["eval_result"]
    resultado.fallback_reason = MOTIVO
    resultado.model_used = "universal"
    protocolo = dict(resultado.docking_protocol or {})
    protocolo["execution_provenance"] = {**(protocolo.get("execution_provenance") or {}),
                                         "receptor_prep": {"prepared_chains": ["R"]}}
    resultado.docking_protocol = protocolo
    return caso


def _parrafos_del_pdf(caso: dict, idioma: str, monkeypatch) -> str:
    parrafos: list[str] = []
    original = Paragraph.__init__

    def espiar(self, texto, *args, **kwargs):
        parrafos.append(str(texto))
        original(self, texto, *args, **kwargs)

    monkeypatch.setattr(Paragraph, "__init__", espiar)
    token = set_request_locale(idioma)
    try:
        render_dossier_pdf(build_case_dossier(**caso))
    finally:
        reset_request_locale(token)
    assert len(parrafos) > 100  # el PDF se generó de verdad
    return "\n".join(parrafos)


def test_el_pdf_ingles_de_una_corrida_como_la_de_la_qa_no_deja_restos(monkeypatch):
    texto = _parrafos_del_pdf(_caso_como_el_de_la_qa(), "en", monkeypatch)
    encontrados = [r for r in RESTOS if r in texto]
    assert encontrados == [], encontrados
    assert "chains R (measured from the hashed PDBQT bytes)" in texto
    assert "has no trained model available" in texto
    assert "Protocol:" in texto


def test_el_pdf_castellano_dice_resultados_heredados(monkeypatch):
    texto = _parrafos_del_pdf(_caso_como_el_de_la_qa(), "es", monkeypatch)
    assert "Apéndice A. Resultados heredados (no decisionales)" in texto
    assert "Outputs" not in texto
    # El castellano no se toca: sigue diciendo lo que decía.
    assert "Protocolo:" in texto and "cadenas R" in texto and MOTIVO[:-1] in texto


def test_la_guardia_ve_los_restos_que_encontro_la_qa():
    """Control: con la salida del PDF de la QA, la lista de restos salta."""
    salida_de_la_qa = ("8HFI · cadenas A (measured from the hashed PDBQT bytes)\nReceptor source curado\n"
                       "Procedencia: build_evidence_summary\nfallback: " + MOTIVO)
    assert [r for r in RESTOS if r in salida_de_la_qa] == [
        "cadenas", "curado", "Procedencia:", "sin modelo", "modelo universal", "Familia '"]
