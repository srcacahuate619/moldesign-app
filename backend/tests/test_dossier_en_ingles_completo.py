"""El dossier en inglés no deja en español ningún texto del SISTEMA; sólo los datos de la persona.

# Qué se midió (2026-10-04, al fusionar la traducción del entregable)

Se generó el paquete de un caso de prueba en inglés (JSON, README, PDF y verificador) y se buscó español en todo lo que se escribe. Quedaban
cuatro textos del sistema sin traducir, justo en los caminos que más ven los clientes de un tercero:

* el respaldo del receptor en la portada: «Calibrado para este receptor (Spearman ρ medido) — ρ = 0.512» (tres de sus cuatro niveles; sólo el
  «curado» estaba traducido);
* la cola del veredicto físico: «… Motor: posebusters:1.0:dock. Cobertura 3/3 poses.» (el texto sale de un fichero sellado, así que se traduce
  sólo en la capa de presentación; la frase larga estaba en el catálogo, pero la cola variable impedía que casara);
* el estado «reconocida» de una decisión humana en la tabla del PDF.

Lo que SÍ se conserva en español es lo que escribió la persona (nombre y pregunta del caso, supuestos, notas de una decisión, nombre del receptor):
la prueba lo enmascara por valor y exige que todo lo demás esté en inglés.
"""
from __future__ import annotations

import io
import re
import zipfile
from typing import Any

import pytest
from reportlab.platypus import Paragraph

from core.i18n import reset_request_locale, set_request_locale
from services.dossier.localization import traducir_dossier
from services.dossier.model import build_case_dossier
from services.dossier.package import construir_paquete
from services.dossier.pdf import render_dossier_pdf
from services.dossier.verify import verificar_paquete
from tests.fixtures_dossier import caso_completo, caso_parcial

_MARCAS = re.compile(r"[áéíóúñ¿¡ÁÉÍÓÚÑ]")
_FUNCION = {"el", "la", "los", "las", "del", "que", "con", "sin", "una", "por", "para", "se", "es", "al", "este", "esta", "como"}


def _cadenas(valor: Any):
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from _cadenas(v)
    elif isinstance(valor, (list, tuple)):
        for v in valor:
            yield from _cadenas(v)


def _datos_de_la_persona(caso: dict) -> list[str]:
    """Todo texto libre que puso quien creó el caso: la proyección (nombre, pregunta, supuestos, notas de decisión…) y el receptor."""
    cadenas = list(_cadenas(caso["projection"].model_dump(mode="json")))
    for atributo in ("name", "pdb_id", "chain"):
        cadenas.append(str(getattr(caso["target"], atributo, "") or ""))
        cadenas.append(str(getattr(caso["molecule"], atributo, "") or ""))
    return sorted({c for c in cadenas if len(c.strip()) >= 6}, key=len, reverse=True)


def _sin_datos_de_la_persona(texto: str, datos: list[str]) -> str:
    for dato in datos:
        texto = texto.replace(dato, " ")
    return texto


def _parece_espanol(texto: str) -> bool:
    limpio = re.sub(r"<[^>]+>", " ", texto)
    limpio = re.sub(r"`[^`]*`", " ", limpio)
    limpio = re.sub(r"https?://\S+|[\w./\\-]+\.(?:json|md|pdf|sdf|pdbqt|csv|sha256|txt|log)\b|\b[A-Za-z0-9_]{12,}\b", " ", limpio)
    palabras = [w.lower() for w in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+", limpio)]
    return bool(_MARCAS.search(limpio)) or sum(1 for w in palabras if w in _FUNCION) >= 2


def _generar(caso: dict, idioma: str, monkeypatch) -> tuple[dict[str, str], list[str], Any, bytes]:
    parrafos: list[str] = []
    original = Paragraph.__init__

    def espiar(self, texto, *args, **kwargs):
        parrafos.append(str(texto))
        original(self, texto, *args, **kwargs)

    monkeypatch.setattr(Paragraph, "__init__", espiar)
    token = set_request_locale(idioma)
    try:
        dossier = traducir_dossier(build_case_dossier(**caso), idioma)
        pdf = render_dossier_pdf(dossier).getvalue()
        datos, _entradas, _raiz = construir_paquete(
            dossier=dossier, pdf_bytes=pdf, projection_json=caso["projection"].model_dump_json(indent=2))
    finally:
        reset_request_locale(token)
    with zipfile.ZipFile(io.BytesIO(datos)) as zip_:
        textos = {n: zip_.read(n).decode("utf-8") for n in zip_.namelist() if n.endswith((".md", ".json", ".txt", ".csv"))}
    return textos, parrafos, dossier, datos


@pytest.mark.parametrize("nombre", ["completo"])
def test_el_paquete_en_ingles_solo_conserva_en_espanol_lo_que_escribio_la_persona(nombre, monkeypatch):
    """El caso completo: todo texto del sistema sale en inglés. (El parcial lo ejercita la prueba de abajo: sus fixtures traen texto guardado
    inventado —«El rescoring GNN no cargó…»— que ningún código del producto emite y que, por diseño, queda como se guardó si no hay traducción.)"""
    caso = caso_completo()
    textos, parrafos, _dossier, _datos = _generar(caso, "en", monkeypatch)
    persona = _datos_de_la_persona(caso)
    restos = []
    for ruta, texto in textos.items():
        for numero, linea in enumerate(texto.splitlines(), 1):
            if _parece_espanol(_sin_datos_de_la_persona(linea, persona)):
                restos.append(f"{ruta}:{numero}: {linea.strip()[:160]}")
    for parrafo in parrafos:
        if _parece_espanol(_sin_datos_de_la_persona(parrafo, persona)):
            compacto = re.sub(r"\s+", " ", parrafo)[:160]
            restos.append(f"pdf: {compacto}")
    assert restos == [], "texto del sistema que sigue en español en el dossier en inglés:\n" + "\n".join(restos[:30])
    assert len(parrafos) > 100  # el PDF se renderizó de verdad: sin esto, «nada en español» no probaría nada


def test_la_guardia_ve_el_espanol_del_sistema_y_no_acusa_ingles_ni_datos_de_la_persona():
    assert _parece_espanol("Calibrado para este receptor (Spearman ρ medido) — ρ = 0.512")
    assert _parece_espanol("La batería no corrió entera sobre todas las poses.")
    assert _parece_espanol("El control no se ejecutó en esta corrida.")
    assert not _parece_espanol("Calibrated for this receptor (measured Spearman ρ) — ρ = 0.512")
    assert not _parece_espanol("Engine: posebusters:1.0:dock. Coverage: 3/3 poses.")
    assert _sin_datos_de_la_persona("Declared by the case: Se asume el receptor rígido.", ["Se asume el receptor rígido."]).strip() == \
        "Declared by the case:"


def _receptor_verificado(monkeypatch, tmp_path, pdb_id="7E2Y"):
    """SCI-D-001: `CALIBRADO` exige la medida de Verificados, no una ρ suelta."""
    import json
    from services.docking.preparer import RECEPTOR_RECIPE_VERSION
    from services.targets import seccion_catalogo as sc

    ruta = tmp_path / "verificados.json"
    ruta.write_text(json.dumps({"verificados": {pdb_id: {
        "receta_receptor": RECEPTOR_RECIPE_VERSION, "receptor_sha256": "0" * 64,
        "pose": {"semillas": 5, "semillas_rmsd_ok": 4, "posebusters_valida": True},
        "calibracion": {"rho": 0.512, "ic95": [0.21, 0.71], "n": 48, "endpoint": "Ki",
                        "panel": "CHEMBL0"},
        "protocolo": {"exhaustiveness": 8, "num_poses": 9, "semilla": 42},
        "condiciones": [],
    }}}), encoding="utf-8")
    monkeypatch.setattr(sc, "RUTA_VERIFICADOS", ruta)
    sc._leer.cache_clear()


def test_el_respaldo_del_receptor_y_el_veredicto_fisico_salen_en_ingles(monkeypatch, tmp_path):
    from services.targets import seccion_catalogo as sc

    _receptor_verificado(monkeypatch, tmp_path)
    try:
        _textos, parrafos, _dossier, _datos = _generar(caso_completo(), "en", monkeypatch)
    finally:
        sc._leer.cache_clear()
    unido = "\n".join(parrafos)
    assert ("Calibrated for this receptor (measured Spearman ρ) — ρ = 0.51, 95% CI [0.21; 0.71], "
            "n = 48") in unido
    assert "Engine: posebusters:1.0:dock. Coverage: 3/3 poses." in unido
    # SCI-A-007: `review` también significa «la principal pasa y una alternativa
    # falla», así que la frase nombra las dos causas. Lo que se comprueba aquí
    # sigue siendo lo mismo: que sale entera en inglés.
    assert (
        "Either the full check suite did not run on every pose, or the primary pose "
        "passes while an alternative fails. ‘Review required’ describes a check that "
        "must be inspected, NOT an approved pose."
    ) in unido
    assert "acknowledged · 2026-08-24T09:10:00+00:00" in unido


def test_el_verificador_valida_el_paquete_en_los_dos_idiomas(monkeypatch):
    for idioma in ("es", "en"):
        _textos, _parrafos, _dossier, datos = _generar(caso_completo(), idioma, monkeypatch)
        token = set_request_locale(idioma)
        try:
            resultado = verificar_paquete(datos)
            cabecera = resultado.informe().splitlines()[0]  # el informe se escribe en el idioma de la petición
        finally:
            reset_request_locale(token)
        assert resultado.valido and resultado.errores == [] and resultado.avisos == [], (idioma, resultado.errores, resultado.avisos)
        assert cabecera == ("VALID" if idioma == "en" else "VÁLIDO")


@pytest.mark.parametrize("respaldo,motivo", [
    ("Pipeline calibrado por familia; este receptor no está calibrado individualmente",
     "falta calibrar Spearman ρ contra afinidades medidas de este receptor"),
    ("Sin curar: sin familia estructural conocida",
     "falta curar el receptor: familia estructural, preparación y Spearman ρ"),
    ("Curado estructuralmente; sin calibrar y sin pipeline de familia",
     "faltan Spearman ρ del receptor y stacking calibrado para su familia"),
])
def test_los_cuatro_niveles_del_respaldo_del_receptor_se_traducen_completos(respaldo, motivo):
    """La portada escribe «resumen — motivo» (o «— ρ = x»): cada nivel tiene que salir entero en inglés, no a medias."""
    from core.i18n_plantillas import traducir
    texto = traducir(f"{respaldo} — {motivo}", "en")
    assert not _parece_espanol(texto), texto
    assert "—" in texto


def test_en_espanol_el_dossier_no_cambia(monkeypatch):
    caso = caso_completo()
    original = build_case_dossier(**caso)
    assert traducir_dossier(original, "es") is original


def test_un_caso_sin_poses_no_deja_su_razon_en_espanol(monkeypatch):
    """`poses_razon` es el único texto del sistema que el modelo guarda como cadena suelta, fuera de un Campo: el localizador no lo visitaba
    y la sección de poses de una corrida fallida salía en inglés con «NOT AVAILABLE — La corrida no serializó poses…»."""
    caso = caso_parcial()
    _textos, parrafos, dossier, _datos = _generar(caso, "en", monkeypatch)
    assert dossier.poses_razon == "This run did not serialize poses; there is no structural evidence to review."
    assert any("This run did not serialize poses; there is no structural evidence to review." in p for p in parrafos)
    assert not any("La corrida no serializó poses" in p for p in parrafos)
    # en español, el modelo guardado no cambia
    assert traducir_dossier(build_case_dossier(**caso_parcial()), "es").poses_razon == (
        "La corrida no serializó poses; no hay evidencia estructural que revisar.")
