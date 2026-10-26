"""La sección del catálogo sale del producto: dossier, PDF y Preparación.

Lo que impiden, en orden de gravedad:

1. Que un resultado de un receptor de demostración salga del producto
   pareciendo de uno verificado: la portada lo dice, en los dos idiomas.
2. Que un sello de «verificado» describa una corrida que no midió: otro
   receptor u otros parámetros se declaran y piden revisión.
3. Que Preparación bloquee por la sección: demostración pide revisión, no
   impide nada (sugerir, no bloquear).
"""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from core.i18n_plantillas import traducir
from services.dossier.model import (
    AVISOS_DEL_CATALOGO,
    ETIQUETA_SECCION_DEL_CATALOGO,
    build_case_dossier,
    campo_de_la_seccion,
    texto_del_aviso_del_catalogo,
)
from services.dossier.preparacion import build_preparacion
from services.dossier.taxonomy import Estado
from services.docking.preparer import RECEPTOR_RECIPE_VERSION
from services.targets import seccion_catalogo as sc
from tests.fixtures_dossier import caso_completo

SHA = "a" * 64


@pytest.fixture(autouse=True)
def limpiar_cache():
    sc._leer.cache_clear()
    yield
    sc._leer.cache_clear()


def _verificado():
    return {
        "receta_receptor": RECEPTOR_RECIPE_VERSION,
        "receptor_sha256": SHA,
        "protocolo": {"exhaustiveness": 8, "num_poses": 9, "semilla": 42},
        "condiciones": ["RECEPTOR_SIN_IONES", "SERIE_CONGENERICA",
                        "CONDICIONES_DEL_ENSAYO_NO_DOCUMENTADAS", "CODIGO_NUEVO"],
        "pose": {"semillas": 5, "semillas_rmsd_ok": 4, "posebusters_valida": True},
        "calibracion": {"rho": 0.4123, "ic95": [0.1711, 0.6089], "n": 57, "endpoint": "Ki",
                        "panel": "CHEMBL853189"},
    }


def _inyectar(monkeypatch, tmp_path, pdb_id="7E2Y"):
    ruta = tmp_path / "verificados.json"
    ruta.write_text(json.dumps({"verificados": {pdb_id: _verificado()}}), encoding="utf-8")
    monkeypatch.setattr(sc, "RUTA_VERIFICADOS", ruta)


def _protocolo(seed=42, sha=SHA, exhaustiveness=8, num_poses=9):
    return {"exhaustiveness": exhaustiveness, "num_poses": num_poses, "seed": seed,
            "execution_provenance": {"receptor_sha256": sha}}


def _target(pdb_id="7E2Y", **extra):
    return SimpleNamespace(pdb_id=pdb_id, is_private=False, is_community=False, **extra)


def _ingles_completo(texto: str) -> str:
    """Traducido entero: ninguna frase del sistema se queda en castellano."""
    en = traducir(texto, "en")
    assert en != texto, texto
    for palabra in ("receptor preparado", "Medido con", "Verificado", "Demostración", "semillas",
                    "corrida", "Condición declarada", "Las cadenas"):
        assert palabra not in en, (palabra, en)
    return en


# ── catalogo_de_la_corrida ───────────────────────────────────────────

def test_receptor_del_catalogo_es_demostracion_con_sus_avisos():
    c = sc.catalogo_de_la_corrida(_target("1UZJ"), _protocolo())
    assert c["seccion"] == "demostracion" and c["pdb_id"] == "1UZJ"
    assert c["avisos"] == ["SITIO_FUERA_DE_LA_UNIDAD_BIOLOGICA"]
    assert c["aplica_a_esta_corrida"] is False and c["verificacion"] is None


@pytest.mark.parametrize("campo", ["is_private", "is_community"])
def test_receptor_del_usuario_queda_fuera_del_catalogo(campo):
    target = _target("1UZJ")
    setattr(target, campo, True)
    c = sc.catalogo_de_la_corrida(target, _protocolo())
    assert c["seccion"] is None and c["avisos"] == []


def test_sin_receptor_no_hay_seccion():
    c = sc.catalogo_de_la_corrida(None, _protocolo())
    assert c["seccion"] is None and c["pdb_id"] is None


def test_el_sello_describe_la_corrida_con_su_receptor_y_sus_parametros(monkeypatch, tmp_path):
    _inyectar(monkeypatch, tmp_path)
    c = sc.catalogo_de_la_corrida(_target(), _protocolo())
    assert c["seccion"] == "verificado"
    assert c["aplica_a_esta_corrida"] is True and c["difiere_en"] == []


@pytest.mark.parametrize("cambio, difiere, sin_declarar", [
    ({"seed": 7}, ["seed"], []),
    ({"exhaustiveness": 32}, ["exhaustiveness"], []),
    ({"num_poses": 5}, ["num_poses"], []),
    ({"sha": "b" * 64}, ["receptor"], []),
    # Lo que la corrida no declara no es una diferencia, pero el sello tampoco la describe.
    ({"sha": None, "seed": None}, [], ["receptor", "seed"]),
    ({"sha": "b" * 64, "num_poses": None}, ["receptor"], ["num_poses"]),
])
def test_otra_corrida_no_hereda_el_sello(monkeypatch, tmp_path, cambio, difiere, sin_declarar):
    _inyectar(monkeypatch, tmp_path)
    c = sc.catalogo_de_la_corrida(_target(), _protocolo(**cambio))
    assert c["seccion"] == "verificado"
    assert c["aplica_a_esta_corrida"] is False
    assert c["difiere_en"] == difiere and c["sin_declarar"] == sin_declarar


def test_una_corrida_sin_procedencia_no_declara_nada(monkeypatch, tmp_path):
    _inyectar(monkeypatch, tmp_path)
    c = sc.catalogo_de_la_corrida(_target(), None)
    assert c["aplica_a_esta_corrida"] is False and c["difiere_en"] == []
    assert c["sin_declarar"] == ["receptor", "exhaustiveness", "num_poses", "seed"]


# ── campo_de_la_seccion ──────────────────────────────────────────────

def test_demostracion_pide_revision_y_se_dice_en_los_dos_idiomas():
    campo = campo_de_la_seccion(sc.catalogo_de_la_corrida(_target("8HFI"), _protocolo()))
    assert campo.etiqueta == ETIQUETA_SECCION_DEL_CATALOGO
    assert campo.valor == "Demostración" and campo.estado == Estado.REVISAR
    assert campo.valor_es_clasificacion
    assert "sin verificación de pose ni calibración" in campo.razon
    assert _ingles_completo(campo.valor) == "Demo"
    _ingles_completo(campo.razon)
    assert _ingles_completo(campo.etiqueta) == "Catalog section"


def test_verificado_que_aplica_imprime_cifras_parametros_y_condiciones(monkeypatch, tmp_path):
    _inyectar(monkeypatch, tmp_path)
    campo = campo_de_la_seccion(sc.catalogo_de_la_corrida(_target(), _protocolo()))
    assert campo.estado == Estado.REGISTRADO
    assert "ρ = 0.41 (IC 95 %: 0.17–0.61; n = 57; Ki, CHEMBL853189)" in campo.valor
    assert "4 de 5 semillas" in campo.valor
    assert "exhaustividad 8, 9 poses y semilla 42" in campo.valor
    assert "sin los iones del depósito" in campo.valor
    assert "serie de análogos" in campo.valor
    assert "no constan en las fuentes" in campo.valor
    # Un código desconocido se imprime: una condición nunca se omite.
    assert "Condición declarada: CODIGO_NUEVO." in campo.valor
    en = _ingles_completo(campo.valor)
    assert "Verified · ρ = 0.41 (95% CI: 0.17–0.61" in en and "Declared condition: CODIGO_NUEVO." in en


@pytest.mark.parametrize("cambio, es, en", [
    ({"seed": 7},
     "esta corrida difiere en seed: la calibración no la describe.",
     "this run differs in seed: the calibration does not describe it."),
    ({"sha": None},
     "esta corrida no declara receptor: no se puede comprobar que la calibración la describa.",
     "this run does not declare receptor: it cannot be confirmed that the calibration describes it."),
    ({"seed": 7, "sha": None, "num_poses": None},
     "esta corrida difiere en seed y no declara receptor, num_poses: la calibración no la describe.",
     "this run differs in seed and does not declare receptor, num_poses: the calibration does not describe it."),
])
def test_verificado_que_no_aplica_dice_en_que_difiere_y_que_no_declara(monkeypatch, tmp_path, cambio, es, en):
    _inyectar(monkeypatch, tmp_path)
    campo = campo_de_la_seccion(sc.catalogo_de_la_corrida(_target(), _protocolo(**cambio)))
    assert campo.valor == "Verificado; el sello no describe esta corrida"
    assert campo.estado == Estado.REVISAR
    assert campo.razon.endswith(es) and SHA[:12] in campo.razon
    assert _ingles_completo(campo.valor) == "Verified; the seal does not describe this run"
    traducida = _ingles_completo(campo.razon)
    assert traducida.endswith(en) and traducida.startswith("The seal was measured with exhaustiveness 8")


def test_receptor_del_usuario_y_corrida_sin_receptor():
    propio = _target("MIO1")
    propio.is_private = True
    campo = campo_de_la_seccion(sc.catalogo_de_la_corrida(propio, _protocolo()))
    assert campo.estado == Estado.REGISTRADO and campo.valor.startswith("Receptor del usuario")
    _ingles_completo(campo.valor)
    vacio = campo_de_la_seccion(sc.catalogo_de_la_corrida(None, _protocolo()))
    assert vacio.estado == Estado.NO_EVALUADO
    _ingles_completo(vacio.razon)


def test_avisos_del_catalogo_traducidos():
    for codigo in AVISOS_DEL_CATALOGO:
        _ingles_completo(texto_del_aviso_del_catalogo(codigo))
    assert _ingles_completo(texto_del_aviso_del_catalogo("OTRO")) == "Catalog notice: OTRO."


# ── Dossier y Preparación ────────────────────────────────────────────

def test_el_dossier_lo_dice_en_la_portada_y_en_los_datos():
    dossier = build_case_dossier(**caso_completo())
    campo = next(c for c in dossier.portada if c.etiqueta == ETIQUETA_SECCION_DEL_CATALOGO)
    assert campo.valor == "Demostración"
    assert dossier.as_dict()["run"]["catalogo"]["seccion"] == "demostracion"
    assert dossier.as_dict()["run"]["catalogo"]["pdb_id"] == "7E2Y"


@pytest.mark.parametrize("cabecera, esperado", [
    ("es", ("Sección del catálogo", "Demostración", "sin verificación de pose ni calibración")),
    ("en", ("Catalog section", "Demo", "without pose verification or calibration")),
])
def test_el_pdf_lo_imprime_en_cada_idioma(cabecera, esperado):
    """Lo que sale del producto es el PDF: el campo tiene que estar en su texto."""
    import io

    pypdf = pytest.importorskip("pypdf", reason="extracción semántica del PDF")
    from core.i18n import reset_request_locale, set_request_locale
    from services.dossier.pdf import render_dossier_pdf

    token = set_request_locale(cabecera)
    try:
        datos = render_dossier_pdf(build_case_dossier(**caso_completo())).getvalue()
    finally:
        reset_request_locale(token)
    texto = " ".join(" ".join((p.extract_text() or "").split())
                     for p in pypdf.PdfReader(io.BytesIO(datos)).pages)
    for fragmento in esperado:
        assert fragmento in texto, (cabecera, fragmento)
    if cabecera == "en":
        assert "Sección del catálogo" not in texto and "Demostración" not in texto


def test_el_aviso_medido_va_a_las_incertidumbres():
    caso = caso_completo()
    caso["target"].pdb_id = "1UZJ"
    dossier = build_case_dossier(**caso)
    assert AVISOS_DEL_CATALOGO["SITIO_FUERA_DE_LA_UNIDAD_BIOLOGICA"] in dossier.incertidumbres


def test_preparacion_pide_revision_sin_bloquear_y_da_el_pdb():
    caso = caso_completo()
    auditoria = build_preparacion(build_case_dossier(**caso), caso["eval_result"], caso["projection"])
    receptor = next(b for b in auditoria["bloques"] if b["id"] == "receptor")
    req = next(r for r in receptor["requisitos"] if r["clave"] == "receptor.seccion_catalogo")
    assert req["imprescindible"] is False
    assert "receptor.seccion_catalogo" in auditoria["en_revision"]
    assert "receptor.seccion_catalogo" not in auditoria["bloqueantes"]
    assert auditoria["corrida"]["pdb_id"] == "7E2Y"


def test_preparacion_con_un_sello_que_aplica_no_pide_revision_por_la_seccion(monkeypatch, tmp_path):
    caso = copy.deepcopy(caso_completo())
    _inyectar(monkeypatch, tmp_path)
    protocolo = dict(caso["eval_result"].docking_protocol or {})
    protocolo.update(_protocolo())
    caso["eval_result"].docking_protocol = protocolo
    auditoria = build_preparacion(build_case_dossier(**caso), caso["eval_result"], caso["projection"])
    assert "receptor.seccion_catalogo" not in auditoria["en_revision"]
    assert "receptor.seccion_catalogo" not in auditoria["bloqueantes"]
