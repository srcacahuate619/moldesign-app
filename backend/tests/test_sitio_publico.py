"""Guardas de la web pública (`site/`), que arma `scripts/build_sitio_publico.py`.

La web son varias páginas estáticas que comparten cabecera y pie, citan cifras del
registro y del catálogo y se enlazan entre sí. Sin estas pruebas, una página puede
quedarse con el menú viejo, citar 171 experimentos cuando ya hay más o enlazar a un
expediente que no existe, y nada falla. Cada guarda lleva su control negativo: un
guardián que no demuestra que ve no vale (restricción 2 de AGENTS.md).
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "moldesign_build_sitio", ROOT / "scripts" / "build_sitio_publico.py"
)
assert SPEC and SPEC.loader
SITIO = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SITIO  # @dataclass busca su módulo ahí
SPEC.loader.exec_module(SITIO)


def _en_disco(p: Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


@pytest.fixture(scope="module")
def construido():
    return SITIO.construir()


def test_las_paginas_publicadas_estan_al_dia(construido) -> None:
    """Cabecera, pie, registro, catálogo, tutorial y cifras: site/ es lo que se generaría."""
    distintos = [str(p.relative_to(ROOT)) for p, t in construido.items()
                 if not SITIO.al_dia(p, t)]
    assert not distintos, (
        f"desactualizado: {', '.join(distintos)}; corre python scripts/build_sitio_publico.py"
    )


def test_ningun_enlace_interno_esta_roto(construido) -> None:
    assert SITIO.comprobar_enlaces(construido, SITIO.SITIO) == []


def test_cada_experimento_sellado_tiene_su_expediente_en_ciencia(construido) -> None:
    indice, _ = SITIO.cargar_registro()
    ciencia = construido[SITIO.SITIO / "ciencia" / "index.html"]
    faltan = [e["id"] for e in indice["experimentos"]
              if f'<details class="record" id="{e["id"]}"' not in ciencia]
    assert not faltan, f"sin expediente en /ciencia: {', '.join(faltan)}"
    assert ciencia.count('<details class="record"') == indice["total"]


def test_la_portada_no_lleva_los_datos_del_catalogo(construido) -> None:
    """Viven en /catalogo: quien sólo quiere descargar no carga 381 receptores."""
    portada = construido[SITIO.SITIO / "index.html"]
    assert "datos-receptores" not in portada
    assert 'id="datos-receptores"' in construido[SITIO.SITIO / "catalogo" / "index.html"]


def test_canonical_y_sitemap_salen_del_dominio(construido) -> None:
    for p in SITIO.PAGINAS:
        t = construido[SITIO.SITIO / p.archivo]
        assert f'<link rel="canonical" href="{SITIO.DOMINIO}{p.ruta}">' in t, p.archivo
        assert f'<meta property="og:url" content="{SITIO.DOMINIO}{p.ruta}">' in t, p.archivo
    sitemap = construido[SITIO.SITIO / "sitemap.xml"]
    assert all(f"<loc>{SITIO.DOMINIO}{p.ruta}</loc>" in sitemap for p in SITIO.PAGINAS)


# ── Los guardianes ven ──────────────────────────────────────────────────────────

@pytest.fixture()
def copia(tmp_path: Path) -> Path:
    destino = tmp_path / "site"
    shutil.copytree(SITIO.SITIO, destino)
    return destino


def test_ve_un_enlace_roto(copia: Path) -> None:
    salida = SITIO.construir(copia)
    ciencia = copia / "ciencia" / "index.html"
    salida[ciencia] = salida[ciencia].replace(
        '<a class="text-link" href="#CAL-8HFI-01">', '<a class="text-link" href="#NO-EXISTE-01">', 1)
    salida[copia / "index.html"] += '<a href="catalogo/no-existe.html">x</a>'
    errores = SITIO.comprobar_enlaces(salida, copia)
    assert any("NO-EXISTE-01" in e for e in errores)
    assert any("no-existe.html" in e for e in errores)


def test_la_cabecera_se_edita_en_la_portada_y_llega_a_las_demas(copia: Path) -> None:
    portada = copia / "index.html"
    portada.write_text(
        portada.read_text(encoding="utf-8").replace(
            '<span class="lang-es">Novedades</span>', '<span class="lang-es">Noticias</span>'),
        encoding="utf-8")
    salida = SITIO.construir(copia)
    assert '<span class="lang-es">Noticias</span>' in salida[copia / "ciencia" / "index.html"]
    # Y el --check de la página vieja lo habría visto.
    assert salida[copia / "ciencia" / "index.html"] != _en_disco(copia / "ciencia" / "index.html")


def test_una_cifra_sin_fuente_no_se_publica(copia: Path) -> None:
    catalogo = copia / "catalogo" / "index.html"
    catalogo.write_text(catalogo.read_text(encoding="utf-8").replace(
        "</main>", '<span data-dato="cifra-inventada">9</span></main>', 1), encoding="utf-8")
    with pytest.raises(SITIO.ErrorDeSitio, match="cifra-inventada"):
        SITIO.construir(copia)


def test_una_fecha_no_cabe_en_un_span() -> None:
    with pytest.raises(SITIO.ErrorDeSitio, match="usa <time>"):
        SITIO.rellenar_datos('<span data-dato="f">x</span>',
                             {"f": SITIO.fecha_larga("2026-10-11")}, "prueba")
    assert "octubre" in SITIO.rellenar_datos(
        '<time data-dato="f"></time>', {"f": SITIO.fecha_larga("2026-10-11")}, "prueba")


@pytest.mark.parametrize("url, esperado", [
    ("./", "../"),
    ("#app", "../#app"),
    ("ciencia/", "../ciencia/"),
    ("assets/logo.png", "../assets/logo.png"),
    ("https://apps.microsoft.com/detail/9N96SW3GBK8V", "https://apps.microsoft.com/detail/9N96SW3GBK8V"),
    ("mailto:moldesign@amezcua-dev.com", "mailto:moldesign@amezcua-dev.com"),
    ("/robots.txt", "/robots.txt"),
])
def test_reubicar_una_url_de_la_portada(url: str, esperado: str) -> None:
    assert SITIO.reubicar(url, "../") == esperado


def test_un_enlace_entre_papers_es_un_ancla_y_uno_al_repositorio_es_texto() -> None:
    ids = {"FEP-09-SENSIBILIDAD"}
    html = SITIO._frags([
        {"t": "FEP-09", "m": "enlace", "href": "FEP-09-SENSIBILIDAD.md"},
        {"t": "prerregistro", "m": "enlace", "href": "../auditorias/FEP-09-prerregistro.md"},
        {"t": "<x>", "m": "codigo"},
    ], ids)
    assert html == ('<a href="#FEP-09-SENSIBILIDAD">FEP-09</a>prerregistro'
                    "<code>&lt;x&gt;</code>")


# ── Novedades: Molcy y Preparación ──────────────────────────────────────────────

def test_el_tutorial_de_la_portada_es_el_de_la_aplicacion(construido) -> None:
    """Mismas capturas, byte a byte, y los mismos textos que el Inicio de la app."""
    for idioma in ("es", "en"):
        for paso in SITIO.PASOS_DEL_TUTORIAL:
            web = SITIO.SITIO / "assets" / "tutorial" / "molcy" / idioma / f"{paso}.webp"
            app = SITIO.TUTORIAL_CAPTURAS / idioma / f"{paso}.webp"
            assert construido[web] == app.read_bytes(), f"{idioma}/{paso}.webp no es la de la app"
    textos = SITIO.leer_textos_del_tutorial(SITIO.TUTORIAL_TEXTOS.read_text(encoding="utf-8"))
    portada = construido[SITIO.SITIO / "index.html"]
    for idioma in ("es", "en"):
        for paso in SITIO.PASOS_DEL_TUTORIAL:
            titulo = SITIO.e_(textos[idioma][f"ini_tut_{paso}_titulo"])
            assert titulo in portada, f"falta el paso «{titulo}» ({idioma}) en la portada"


def test_un_texto_del_tutorial_que_falta_no_se_publica_a_medias() -> None:
    ts = SITIO.TUTORIAL_TEXTOS.read_text(encoding="utf-8")
    sin_clave = re.sub(r"^\s*ini_tut_guardar_alt:.*$", "", ts, count=1, flags=re.M)
    assert sin_clave != ts
    with pytest.raises(SITIO.ErrorDeSitio, match="ini_tut_guardar_alt"):
        SITIO.leer_textos_del_tutorial(sin_clave)


def test_el_pie_de_la_demo_sale_de_lo_que_molcy_declaro(construido) -> None:
    demo = json.loads((SITIO.SITIO / "assets" / "molcy-demo.json").read_text(encoding="utf-8"))
    portada = construido[SITIO.SITIO / "index.html"]
    assert f'<code data-dato="demo-corrida">{demo["molcy"]["corrida"][:8]}</code>' in portada
    assert f'<span data-dato="demo-pdb">{demo["molcy"]["pdb_id"]}</span>' in portada
    # Sin JavaScript, o con «reducir movimiento», el vídeo no arranca solo.
    video = re.search(r"<video\b[^>]*>", portada).group(0)
    assert "autoplay" not in video and "controls" in video and "muted" in video


def test_un_video_que_no_es_el_descrito_no_se_publica(copia: Path) -> None:
    video = copia / "assets" / "molcy-demo.mp4"
    video.write_bytes(video.read_bytes() + b"\0")
    with pytest.raises(SITIO.ErrorDeSitio, match="molcy-demo.json"):
        SITIO.construir(copia)


def test_lo_que_la_portada_dice_de_preparacion_es_lo_que_midio_fep09r1(construido) -> None:
    metricas = json.loads(SITIO.FEP09R1.read_text(encoding="utf-8"))
    huecos = metricas["categories"]["hueco_en_el_sitio"]
    agua = metricas["categories"]["agua_puente_retirada"]
    portada = construido[SITIO.SITIO / "index.html"]
    assert f'<span data-dato="prep-huecos">{huecos["detections_route"]}</span>' in portada
    assert f'<span data-dato="prep-huecos-n">{huecos["n_audited"]}</span>' in portada
    # Lo que no detecta se publica igual que lo que sí.
    assert f'<span data-dato="prep-agua">{agua["detections_route"]}</span>' in portada
    otra = SITIO.datos_de_preparacion(
        {**metricas, "categories": {**metricas["categories"],
                                    "hueco_en_el_sitio": {**huecos, "detections_route": 14}}})
    assert otra["prep-huecos"] == "14"


def test_el_explorador_del_catalogo_sale_del_catalogo_actual(construido) -> None:
    """`site/receptors.json` se genera: era una foto del 2026-10-11 y se quedó atrás de dos correcciones del catálogo."""
    import hashlib

    publicado = json.loads(construido[SITIO.SITIO / "receptors.json"])
    crudo = SITIO.CATALOGO.read_bytes()
    assert publicado["sha256"] == hashlib.sha256(crudo).hexdigest()
    nombres = {f["pdb_id"]: f.get("name") for f in json.loads(crudo.decode("utf-8"))}
    assert {r[0]: r[1] for r in publicado["records"]} == nombres
    assert publicado["count"] == len(nombres)


def test_un_catalogo_que_cambia_sin_su_disponibilidad_no_se_publica(tmp_path, monkeypatch) -> None:
    otro = tmp_path / "curated_targets.json"
    otro.write_bytes(SITIO.CATALOGO.read_bytes().replace(b"ABL1 Kinase PD180970", b"ABL1 otra cosa"))
    monkeypatch.setattr(SITIO, "CATALOGO", otro)
    with pytest.raises(SITIO.ErrorDeSitio, match="disponibilidad"):
        SITIO.catalogo_publico()
