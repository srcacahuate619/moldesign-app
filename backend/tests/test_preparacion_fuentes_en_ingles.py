"""Con la interfaz en inglés, la «fuente» de cada requisito de Preparación sale en inglés.

# El defecto (2026-10-25, al grabar el vídeo de Preparación)

Preparación enseña debajo de cada requisito de dónde salió («source: …»). Con la interfaz en inglés, trece de esas
fuentes seguían en castellano («secuencia del receptor · HEADER del depósito», «pose top-1 · estructura de origen
comprobada por la receta del receptor»…): `localization.py` no traducía el campo `fuente`. Las que son un campo del
código (`receptor_prep.backbone_gaps`) se quedan como están; las que describen algo en prosa se traducen.

La guarda recorre las fuentes LITERALES de `services/dossier/preparacion.py`: una nueva en prosa sin traducción falla
aquí, no en la pantalla de un usuario.
"""
from __future__ import annotations

import ast
from pathlib import Path

from core.i18n_plantillas import traducir
from services.dossier.localization import traducir_dossier

PREPARACION = Path(__file__).resolve().parents[1] / "services" / "dossier" / "preparacion.py"


def _literales(nodo: ast.AST) -> list[str]:
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return [nodo.value]
    if isinstance(nodo, ast.IfExp):
        return _literales(nodo.body) + _literales(nodo.orelse)
    return []


def _fuentes_literales() -> list[tuple[int, str]]:
    arbol = ast.parse(PREPARACION.read_text(encoding="utf-8"))
    fuentes = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", None) == "Requisito":
            argumento = nodo.args[2] if len(nodo.args) >= 3 else next(
                (k.value for k in nodo.keywords if k.arg == "fuente"), None)
            if argumento is not None:
                fuentes += [(nodo.lineno, s) for s in _literales(argumento)]
        elif isinstance(nodo, ast.Assign) and any(getattr(t, "id", "").startswith("fuente") for t in nodo.targets):
            fuentes += [(nodo.lineno, s) for s in _literales(nodo.value)]
    return fuentes


def _es_campo_del_codigo(fuente: str) -> bool:
    """`receptor_prep.species_diff · box_size`: cada parte es un nombre sin espacios."""
    return all(parte.strip() and " " not in parte.strip() for parte in fuente.split(" · "))


def _sin_traducir(fuentes: list[str]) -> list[str]:
    return [f for f in fuentes if not _es_campo_del_codigo(f) and traducir(f, "en") == f]


def test_el_detector_ve_una_fuente_en_prosa_sin_traducir():
    # control negativo: sin esto, una guarda que no mira nada daría verde
    assert _sin_traducir(["estructura inventada del depósito", "receptor_prep.backbone_gaps"]) == [
        "estructura inventada del depósito"]


def test_la_guarda_encuentra_las_fuentes_de_preparacion():
    fuentes = [f for _, f in _fuentes_literales()]
    assert "receptor_prep.backbone_gaps" in fuentes
    assert "secuencia del receptor · HEADER del depósito" in fuentes
    assert len(fuentes) > 40


def test_toda_fuente_en_prosa_tiene_traduccion():
    faltan = _sin_traducir([f for _, f in _fuentes_literales()])
    assert faltan == [], f"fuentes de Preparación sin traducción al inglés: {faltan}"


def _auditoria(fuente: str) -> dict:
    return {"estado": "REVISION", "bloques": [{"id": "entorno", "requisitos": [{
        "clave": "entorno.membrana", "etiqueta": "Proteína de membrana", "valor": None, "estado": "REVISAR",
        "razon": None, "fuente": fuente, "imprescindible": False}]}]}


def test_la_fuente_de_un_requisito_se_traduce_en_ingles():
    en = traducir_dossier(_auditoria("secuencia del receptor · HEADER del depósito"), "en")
    assert en["bloques"][0]["requisitos"][0]["fuente"] == "receptor sequence · HEADER of the deposit"
    es = traducir_dossier(_auditoria("secuencia del receptor · HEADER del depósito"), "es")
    assert es["bloques"][0]["requisitos"][0]["fuente"] == "secuencia del receptor · HEADER del depósito"


def test_un_campo_del_codigo_no_cambia():
    en = traducir_dossier(_auditoria("receptor_prep.backbone_gaps"), "en")
    assert en["bloques"][0]["requisitos"][0]["fuente"] == "receptor_prep.backbone_gaps"


def test_una_fuente_fuera_de_un_requisito_no_se_toca():
    # p. ej. la fuente de un Ki que declaró el caso: es dato de la persona, no texto del sistema
    dato = {"ensayo": {"fuente": "secuencia del receptor · HEADER del depósito"}}
    assert traducir_dossier(dato, "en") == dato


def test_el_receptor_preparado_no_deja_receta_en_castellano():
    """«SHA-256 … · receta …» salía tal cual con la interfaz en inglés (vídeo de Preparación, 2026-10-25)."""
    from core.i18n_plantillas import traducir

    texto = "SHA-256 8fc027cae876 · receta c83e542ca8f3"
    assert traducir(texto, "en") == "SHA-256 8fc027cae876 · recipe c83e542ca8f3"
    assert traducir(texto, "es") == texto


def test_el_encabezado_del_dossier_en_ingles_dice_run():
    """La cabecera de cada página del PDF decía «… · corrida <id>» con el dossier en inglés (vídeo, 2026-10-25)."""
    from core.i18n_plantillas import traducir

    assert traducir("corrida", "en") == "run"
    assert traducir("corrida", "es") == "corrida"
