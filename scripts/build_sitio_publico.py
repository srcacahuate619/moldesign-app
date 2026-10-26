#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_sitio_publico.py — arma las páginas de la web pública (`site/`).

La web son páginas HTML estáticas, sin framework ni servidor. Este script hace lo
que copiar a mano haría mal a la tercera edición:

1. **La portada manda en la cabecera y el pie.** Los bloques entre
   ``<!-- compartido:cabecera -->`` y ``<!-- /compartido:cabecera -->`` (y lo mismo
   con ``pie``) se copian de ``site/index.html`` a las demás páginas, con las rutas
   relativas corregidas para su carpeta y ``aria-current`` en el enlace de cada una.
   Se editan en la portada; en las otras se sobrescriben.
2. **/ciencia publica el registro científico entero**, renderizado aquí desde
   ``frontend/public/registro/``: el mismo JSON que la aplicación, que
   ``build_registro_cientifico.py`` emite desde los manifests sellados. Va como HTML
   y no como JSON que pinte JavaScript: así se lee sin JavaScript, lo encuentran los
   buscadores, y un enlace ``/ciencia/#CAL-8HFI-01`` abre ese expediente.
3. **/catalogo incrusta ``site/receptors.json``**, para que el explorador funcione
   sin peticiones (también abriendo el archivo con ``file:///``).
4. **Las cifras no se escriben a mano.** Un elemento con ``data-dato="registro-total"``
   recibe su número de la fuente: el registro, el catálogo, lo que Molcy declaró del
   vídeo de demostración (``assets/molcy-demo.json``, de ``preparar_demo_molcy.py``) y
   lo que midió FEP-09-R1 de la pestaña Preparación (sus métricas selladas).
5. **El tutorial de Molcy es el del Inicio de la aplicación**: sus capturas se copian
   byte a byte de ``frontend/public/tutorial/molcy/``, sus cajas de
   ``frontend/lib/tutorial/molcy-marcas.json`` y sus textos de
   ``frontend/context/traducciones/inicio.ts``. Si se regenera en la app, se regenera aquí.
6. **El dominio vive en una constante**: canonical, ``og:url``, ``sitemap.xml`` y
   ``robots.txt`` salen de ``DOMINIO``.

Uso
---
    python scripts/build_sitio_publico.py [--check]

``--check`` no escribe: falla si alguna página no coincide con lo que generaría o si
un enlace interno (archivo o ancla) no resuelve.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from urllib.parse import unquote

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITIO = PROJECT_ROOT / "site"
REGISTRO = PROJECT_ROOT / "frontend" / "public" / "registro"
# El tutorial de Molcy es el del Inicio de la aplicación: mismas capturas, mismas cajas,
# mismos textos. Lo regenera `frontend/scripts/capturas-tutorial-molcy.mjs`; la web lo copia.
TUTORIAL_CAPTURAS = PROJECT_ROOT / "frontend" / "public" / "tutorial" / "molcy"
TUTORIAL_MARCAS = PROJECT_ROOT / "frontend" / "lib" / "tutorial" / "molcy-marcas.json"
TUTORIAL_TEXTOS = PROJECT_ROOT / "frontend" / "context" / "traducciones" / "inicio.ts"
PASOS_DEL_TUTORIAL = ("caso", "receptor", "evaluar", "guardar", "corrida", "molcy")
# Lo que la portada dice de Preparación lo midió FEP-09-R1 (sellado; sólo se lee).
FEP09R1 = PROJECT_ROOT / "scripts" / "artifacts_science" / "FEP-09-R1" / "metrics.json"

# El explorador de /catalogo: se genera en cada construcción desde el catálogo y sus datos medidos. Antes era una
# foto escrita a mano el 2026-10-11 y se quedó atrás de dos correcciones del catálogo (familias y el nombre de 2HZI).
CATALOGO = PROJECT_ROOT / "curated_targets.json"
DISPONIBILIDAD = PROJECT_ROOT / "backend" / "data" / "disponibilidad_catalogo.json"
AVISOS = PROJECT_ROOT / "backend" / "data" / "avisos_catalogo.json"
VERIFICADOS = PROJECT_ROOT / "backend" / "data" / "receptores_verificados.json"
VERSIONES_DEL_CATALOGO = PROJECT_ROOT / "docs" / "catalog_versions"

#: Decisión del propietario (2026-10-11).
DOMINIO = "https://moldesign.amezcua-dev.com/"


@dataclass(frozen=True)
class Pagina:
    archivo: str  # relativo a site/
    ruta: str     # relativa al dominio
    clave: str    # la que lleva su enlace en data-pagina


PAGINAS: Tuple[Pagina, ...] = (
    Pagina("index.html", "", "inicio"),
    Pagina("ciencia/index.html", "ciencia/", "ciencia"),
    Pagina("catalogo/index.html", "catalogo/", "catalogo"),
)
MAESTRA = PAGINAS[0]
COMPARTIDOS = ("cabecera", "pie")


class ErrorDeSitio(Exception):
    pass


# ──────────────────────────────────────────────────────────────────── bloques

def _marcas(tipo: str, nombre: str) -> Tuple[str, str]:
    return f"<!-- {tipo}:{nombre} -->", f"<!-- /{tipo}:{nombre} -->"


def leer_bloque(texto: str, tipo: str, nombre: str, donde: str) -> str:
    ini, fin = _marcas(tipo, nombre)
    if texto.count(ini) != 1 or texto.count(fin) != 1:
        raise ErrorDeSitio(f"{donde}: hace falta exactamente un «{ini}» y un «{fin}»")
    a = texto.index(ini) + len(ini)
    b = texto.index(fin)
    if b < a:
        raise ErrorDeSitio(f"{donde}: «{fin}» aparece antes que «{ini}»")
    return texto[a:b]


def poner_bloque(texto: str, tipo: str, nombre: str, contenido: str, donde: str) -> str:
    leer_bloque(texto, tipo, nombre, donde)  # valida las marcas
    ini, fin = _marcas(tipo, nombre)
    a = texto.index(ini) + len(ini)
    return texto[:a] + contenido + texto[texto.index(fin):]


_ATRIBUTO_URL = re.compile(r'(\s(?:href|src)=")([^"]*)(")')
_EXTERNA = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|/)", re.I)


def reubicar(url: str, prefijo: str) -> str:
    """Una URL relativa a la portada, vista desde una página con ``prefijo`` (``../``)."""
    if not prefijo or _EXTERNA.match(url):
        return url
    if url in ("", ".", "./"):
        return prefijo
    if url.startswith("./"):
        url = url[2:]
    return prefijo + url


def reubicar_urls(fragmento: str, prefijo: str) -> str:
    return _ATRIBUTO_URL.sub(
        lambda m: m.group(1) + reubicar(m.group(2), prefijo) + m.group(3), fragmento)


def marcar_pagina_actual(fragmento: str, clave: str) -> str:
    sin = fragmento.replace(' aria-current="page"', "")
    return re.sub(
        r'(<a\b[^>]*\bdata-pagina="' + re.escape(clave) + r'")',
        r'\1 aria-current="page"', sin)


def prefijo_de(pagina: Pagina) -> str:
    return "../" * pagina.archivo.count("/")


# ──────────────────────────────────────────────────────────────────── datos

MESES = {
    "es": ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre", "octubre", "noviembre", "diciembre"),
    "en": ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"),
}


def bi(es: str, en: str) -> str:
    """Texto ya escapado en los dos idiomas del sitio."""
    return f'<span class="lang-es">{es}</span><span class="lang-en">{en}</span>'


def fecha_larga(iso: str) -> str:
    a, m, d = (int(x) for x in iso[:10].split("-"))
    return bi(f"{d} de {MESES['es'][m - 1]} de {a}", f"{MESES['en'][m - 1]} {d}, {a}")


def fecha_corta(iso: str) -> str:
    a, m, d = (int(x) for x in iso[:10].split("-"))
    return bi(f"{d} {MESES['es'][m - 1][:3]} {a}", f"{MESES['en'][m - 1][:3]} {d}, {a}")


def cargar_registro(raiz: Path = REGISTRO) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    indice = json.loads((raiz / "index.json").read_text(encoding="utf-8"))
    papers = {}
    for e in indice["experimentos"]:
        if e["tiene_paper"]:
            p = raiz / "papers" / f"{e['id']}.json"
            if not p.exists():
                raise ErrorDeSitio(f"{e['id']} declara paper y falta {p}; "
                                   "corre build_registro_cientifico.py")
            papers[e["id"]] = json.loads(p.read_text(encoding="utf-8"))
    return indice, papers


ESCENAS_DE_MOLCY = {"resultado": ("Resultado", "Result"), "receptor": ("Receptor", "Receptor"),
                    "busqueda": ("Búsqueda", "Search"), "ensamble": ("Ensamble", "Ensemble")}


def _miles(n: int) -> str:
    return bi(f"{n:,}".replace(",", " "), f"{n:,}")


def datos_de_la_demo(demo: Dict[str, Any], catalogo: Dict[str, Any], assets: Path) -> Dict[str, str]:
    """El pie del vídeo de Molcy, desde lo que Molcy declaró (``molcy-demo.json``)."""
    web = demo["web"]
    for archivo, sha in ((web["archivo"], web["sha256"]),
                         (demo["reposo"]["archivo"], demo["reposo"]["sha256"])):
        p = assets / archivo
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != sha:
            raise ErrorDeSitio(f"assets/{archivo} no es el que describe molcy-demo.json; "
                               "corre scripts/preparar_demo_molcy.py")
    m = demo["molcy"]
    if m["escena"] not in ESCENAS_DE_MOLCY:
        raise ErrorDeSitio(f"escena de Molcy sin nombre en la web: {m['escena']}")
    if m["pdb_id"] not in {r[0] for r in catalogo["records"]}:
        # El pie dice «del catálogo de Demostración»: con un receptor propio mentiría.
        raise ErrorDeSitio(f"el receptor de la demo, {m['pdb_id']}, no está en el catálogo")
    d = {
        "demo-corrida": e_(m["corrida"][:8]),
        "demo-pdb": e_(m["pdb_id"]),
        "demo-receptor": e_(m["receptor"]),
        "demo-escena": bi(*ESCENAS_DE_MOLCY[m["escena"]]),
        "demo-segundos": bi(f"{web['duracion_s']:.1f}".replace(".", ","), f"{web['duracion_s']:.1f}"),
        "demo-mb": bi(f"{web['bytes'] / 1e6:.1f}".replace(".", ","), f"{web['bytes'] / 1e6:.1f}"),
    }
    for k in ("poses", "replicas"):
        if k in m:
            d[f"demo-{k}"] = str(m[k])
    if "pasos" in m:
        d["demo-pasos"] = _miles(m["pasos"])
    return d


def datos_de_preparacion(metricas: Dict[str, Any]) -> Dict[str, str]:
    """Sensibilidad de Preparación medida en FEP-09-R1: detectados de auditados, por categoría."""
    cat = metricas["categories"]
    d: Dict[str, str] = {}
    for clave, categoria in (("huecos", "hueco_en_el_sitio"), ("estereo", "estereo_sin_asignar"),
                             ("agua", "agua_puente_retirada"), ("protonacion", "protonacion_del_sitio")):
        d[f"prep-{clave}"] = str(cat[categoria]["detections_route"])
        d[f"prep-{clave}-n"] = str(cat[categoria]["n_audited"])
    d["prep-falsas"] = str(metricas["false_alarm"]["n_changed"])
    d["prep-falsas-n"] = str(metricas["false_alarm"]["n_requirements"])
    d["prep-sin-casos"] = str(sum(1 for c in cat.values()
                                  if c["coverage"] == "declared" and c["n_applicable"] == 0))
    return d


def datos(indice: Dict[str, Any], catalogo: Dict[str, Any]) -> Dict[str, str]:
    """Las cifras que las páginas citan con ``data-dato``. Cada una, de su fuente."""
    d = {
        "registro-total": str(indice["total"]),
        "registro-con-paper": str(indice["con_paper"]),
        "registro-ultimo-sello": fecha_larga(
            max(e["sellado_en"] for e in indice["experimentos"] if e["sellado_en"])),
        "catalogo-total": str(catalogo["count"]),
        "catalogo-verificados": str(catalogo["verified_count"]),
        "catalogo-demostracion": str(catalogo["count"] - catalogo["verified_count"]),
        "catalogo-demostracion": str(catalogo["count"] - catalogo["verified_count"]),
        "catalogo-no-disponibles": str(catalogo["unavailable_count"]),
        "catalogo-avisos-ensamblaje": str(sum(
            1 for v in catalogo["warnings"].values()
            if "SITIO_FUERA_DE_LA_UNIDAD_BIOLOGICA" in v)),
        "catalogo-receta": str(catalogo["recipe"]),
        "catalogo-fecha": fecha_larga(catalogo["snapshot_date"]),
    }
    for c, n in indice["conteo"].items():
        d[f"registro-{c}"] = str(n)
    return d


_DATO = re.compile(r'(<(\w+)\b[^>]*\bdata-dato="([a-z0-9-]+)"[^>]*>)(.*?)(</\2>)', re.S)


def rellenar_datos(texto: str, valores: Dict[str, str], donde: str) -> str:
    def poner(m: re.Match) -> str:
        clave = m.group(3)
        if clave not in valores:
            raise ErrorDeSitio(f"{donde}: data-dato=\"{clave}\" no existe en datos()")
        if f"<{m.group(2)}" in valores[clave]:
            # Una fecha trae sus dos idiomas en <span>: dentro de otro <span>, la próxima
            # pasada cerraría el dato en el primer </span> interior y lo destrozaría.
            raise ErrorDeSitio(f"{donde}: data-dato=\"{clave}\" no puede ir en un "
                               f"<{m.group(2)}>; usa <time>")
        return m.group(1) + valores[clave] + m.group(5)
    return _DATO.sub(poner, texto)


def poner_url_canonica(texto: str, pagina: Pagina, donde: str) -> str:
    url = DOMINIO + pagina.ruta
    nuevo, n1 = re.subn(r'(<link rel="canonical" href=")[^"]*(")', rf"\g<1>{url}\2", texto)
    nuevo, n2 = re.subn(r'(<meta property="og:url" content=")[^"]*(")', rf"\g<1>{url}\2", nuevo)
    if n1 != 1 or n2 != 1:
        raise ErrorDeSitio(f"{donde}: necesita un <link rel=\"canonical\"> y un og:url")
    return nuevo


# ──────────────────────────────────────────────────────────────── el registro

CATEGORIAS = {
    "hallazgo": ("Hallazgo", "Finding",
                 "Criterio prerregistrado y superado. Es un resultado que sostiene algo.",
                 "Pre-registered criterion, passed. A result that supports something."),
    "refutacion": ("Refutación", "Refutation",
                   "Hipótesis propia puesta a prueba y derribada. La columna de la que más se aprende.",
                   "An own hypothesis put to the test and knocked down. The column you learn most from."),
    "medicion": ("Medición", "Measurement",
                 "Mide sin decidir: no tiene umbral de aceptación. Describe el terreno.",
                 "Measures without deciding: there is no acceptance threshold. It describes the terrain."),
    "prerregistro": ("Prerregistro", "Pre-registration",
                     "Declaración de hipótesis y criterio ANTES de mirar datos. Se sella GO por "
                     "convención; no es un éxito.",
                     "Hypothesis and criterion declared BEFORE looking at data. GO is sealed by "
                     "convention; it is not a success."),
    "corrigendum": ("Corrigendum", "Correction notice",
                    "Corrección de un resultado propio cuyo valor principal es la corrección.",
                    "Correction of an own result whose main value is the correction."),
    "inconcluso": ("Inconcluso", "Inconclusive",
                   "Ejecutado y declarado sin conclusión. No se reclasifica a posteriori.",
                   "Executed and declared without a conclusion. It is not reclassified afterwards."),
}

e_ = html.escape


def _frags(frags: Iterable[Dict[str, Any]], ids: set) -> str:
    out = []
    for f in frags:
        t = e_(f["t"])
        m = f["m"]
        if m == "fuerte":
            out.append(f"<strong>{t}</strong>")
        elif m == "enfasis":
            out.append(f"<em>{t}</em>")
        elif m == "codigo":
            out.append(f"<code>{t}</code>")
        elif m == "enlace":
            href = f.get("href") or ""
            destino = Path(href.split("#")[0]).stem
            if href.startswith("https://"):
                out.append(f'<a href="{e_(href)}" rel="noopener noreferrer">{t}</a>')
            elif destino in ids:
                # Un paper que cita a otro: en la web es un ancla de esta misma página.
                out.append(f'<a href="#{e_(destino)}">{t}</a>')
            else:
                # Un documento del repositorio (una auditoría, un prerregistro) que la
                # web no publica: el texto queda, el enlace no lleva a ninguna parte.
                out.append(t)
        else:
            out.append(t)
    return "".join(out)


def _bloques(bloques: List[Dict[str, Any]], ids: set) -> str:
    out = []
    for b in bloques:
        tipo = b["tipo"]
        if tipo == "encabezado":
            n = min(b["nivel"] + 1, 6)  # ## del paper → h3 dentro de la página
            out.append(f"<h{n}>{_frags(b['frag'], ids)}</h{n}>")
        elif tipo == "parrafo":
            out.append(f"<p>{_frags(b['frag'], ids)}</p>")
        elif tipo == "cita":
            out.append(f"<blockquote><p>{_frags(b['frag'], ids)}</p></blockquote>")
        elif tipo == "lista":
            et = "ol" if b["ordenada"] else "ul"
            items = "".join(f"<li>{_frags(it, ids)}</li>" for it in b["items"])
            out.append(f"<{et}>{items}</{et}>")
        elif tipo == "tabla":
            alin = b["alineacion"]

            def celda(et: str, frags: List[Dict[str, Any]], i: int) -> str:
                a = alin[i] if i < len(alin) else "izquierda"
                clase = {"derecha": ' class="num"', "centro": ' class="centro"'}.get(a, "")
                return f"<{et}{clase}>{_frags(frags, ids)}</{et}>"
            cab = "".join(celda("th", c, i) for i, c in enumerate(b["cabecera"]))
            filas = "".join(
                "<tr>" + "".join(celda("td", c, i) for i, c in enumerate(f)) + "</tr>"
                for f in b["filas"])
            out.append(f'<div class="table-wrap"><table><thead><tr>{cab}</tr></thead>'
                       f"<tbody>{filas}</tbody></table></div>")
        elif tipo == "codigo":
            out.append(f"<pre><code>{e_(b['texto'])}</code></pre>")
        else:
            raise ErrorDeSitio(f"bloque de paper desconocido: {tipo}")
    return "".join(out)


def _duracion(s: Optional[float]) -> Optional[str]:
    if not s or s <= 0:
        return None
    if s < 60:
        return f"{round(s)} s"
    if s < 3600:
        return f"{round(s / 60)} min"
    h, m = int(s // 3600), round((s % 3600) / 60)
    return f"{h} h {m} min" if m else f"{h} h"


def _dato(clave_html: str, valor: Optional[str], lang_es: bool = False) -> str:
    if valor is None or valor == "":
        return ""
    lang = ' lang="es"' if lang_es else ""
    return f"<div><dt>{clave_html}</dt><dd{lang}>{valor}</dd></div>"


def render_experimento(e: Dict[str, Any], paper: Optional[Dict[str, Any]], ids: set) -> str:
    c = e["categoria"]
    nombre_es, nombre_en, desc_es, desc_en = CATEGORIAS[c]
    tiene_paper = paper is not None
    titulo = e["titulo"] if tiene_paper else (e["hipotesis"] or e["gate"] or e["id"])

    etiquetas = [f'<span class="record-cat">{bi(nombre_es, nombre_en)}</span>']
    if tiene_paper:
        etiquetas.append(f'<span class="record-flag">{bi("Artículo", "Paper")}</span>')
    if e["reemplazado_por"]:
        etiquetas.append('<span class="record-flag record-flag-warn">'
                         f'{bi("Cifras reemplazadas", "Figures replaced")}</span>')
    if e["n_complejos"]:
        etiquetas.append(f"<span>n={e['n_complejos']}</span>")
    if e["sellado_en"]:
        etiquetas.append(f'<time datetime="{e["sellado_en"][:10]}">'
                         f"{fecha_corta(e['sellado_en'])}</time>")

    cuerpo = []
    if e["reemplazado_por"]:
        r = e_(e["reemplazado_por"])
        cuerpo.append(
            '<p class="record-replaced" role="note">' + bi(
                f"<strong>Cifras reemplazadas.</strong> Un defecto detectado <em>después</em> de "
                f'sellar invalidó las cifras de este registro. <a href="#{r}">{r}</a> las mide de '
                "nuevo y las sustituye. Este artefacto no se reescribe ni se re-sella: se conserva "
                "tal como quedó, para que la corrección sea auditable.",
                f"<strong>Figures replaced.</strong> A defect found <em>after</em> sealing "
                f'invalidated the figures of this record. <a href="#{r}">{r}</a> measures them '
                "again and replaces them. This artifact is not rewritten or re-sealed: it is "
                "preserved as it remained, so that the correction is auditable.") + "</p>")
    if tiene_paper:
        if e["entradilla"]:
            cuerpo.append(f'<p class="record-lede" lang="es">{e_(e["entradilla"])}</p>')
        cuerpo.append(f'<div class="paper" lang="es">{_bloques(paper["bloques"], ids)}</div>')
    else:
        cuerpo.append('<p class="record-note">' + bi(
            "El paper de este registro todavía no está redactado. Abajo está la ficha completa, "
            "generada del manifest sellado, que es la fuente de verdad de todos sus números.",
            "The paper for this record has not been written yet. Below is the full sheet, "
            "generated from the sealed manifest, which is the source of truth for all its "
            "numbers.") + "</p>")

    ficha = [
        _dato(bi("Categoría", "Category"),
              f"{bi(nombre_es, nombre_en)} · {bi(e_(desc_es), e_(desc_en))}"),
        _dato(bi("Decisión del manifest", "Manifest decision"),
              f"<code>{e_(e['decision'])}</code>" if e["decision"] else None),
        _dato(bi("Hipótesis", "Hypothesis"), e_(e["hipotesis"]) if e["hipotesis"] else None, True),
        _dato(bi("Criterio prerregistrado", "Pre-registered criterion"),
              e_(e["gate"]) if e["gate"] else None, True),
        _dato(bi("Protocolo", "Protocol"), e_(e["protocolo"]) if e["protocolo"] else None, True),
        _dato(bi("Razón de la decisión", "Reason for the decision"),
              e_(e["razonamiento"]) if e["razonamiento"] else None, True),
    ]
    cuerpo.append(f'<section class="record-section"><h3>{bi("Ficha del registro sellado", "Sealed record sheet")}</h3>'
                  f'<dl class="record-facts">{"".join(ficha)}</dl></section>')

    if e["metricas"]:
        filas = "".join(_dato(f"<code>{e_(k)}</code>", e_(json.dumps(v, ensure_ascii=False))
                              if not isinstance(v, str) else e_(v))
                        for k, v in e["metricas"].items())
        cuerpo.append(f'<section class="record-section"><h3>{bi("Métricas registradas", "Recorded metrics")}</h3>'
                      f'<dl class="record-metrics">{filas}</dl></section>')

    git = e["git"]
    ent = e["entorno"]
    entorno = " · ".join(x for x in (
        e_(ent["os"]) if ent["os"] else None,
        bi(f"{ent['cpu']} núcleos", f"{ent['cpu']} cores") if ent["cpu"] else None,
        f"{round(ent['ram_mb'] / 1024)} GB" if ent["ram_mb"] else None,
        e_(ent["gpu"]) if ent["gpu"] and ent["gpu"] != "unknown" else None,
    ) if x)
    repro = [
        _dato("commit", f"<code>{e_(git['commit'])}</code>"
              + (" (dirty)" if git["sucio"] else "") if git["commit"] else None),
        _dato(bi("rama", "branch"), f"<code>{e_(git['rama'])}</code>" if git["rama"] else None),
        _dato(bi("semilla", "seed"), e_(str(e["semillas"])) if e["semillas"] is not None else None),
        _dato(bi("sellado", "sealed"), fecha_larga(e["sellado_en"]) if e["sellado_en"] else None),
        _dato(bi("duración", "duration"), _duracion(e["duracion_s"])),
        _dato(bi("complejos", "complexes"), str(e["n_complejos"]) if e["n_complejos"] else None),
        _dato(bi("fallos", "failures"), str(e["n_fallos"]) if e["n_fallos"] else None),
        _dato("hashes SHA-256", str(e["n_hashes"]) if e["n_hashes"] else None),
        _dato(bi("entorno", "environment"), entorno or None),
        _dato(bi("mantenimiento", "maintenance"), bi(
            f"{e['mantenimiento_sello']} mantenimiento(s) declarados. El hash actual no acredita "
            "qué código produjo la cifra original.",
            f"{e['mantenimiento_sello']} declared maintenance action(s). The current hash does "
            "not establish which code produced the original figure.")
            if e["mantenimiento_sello"] else None),
    ]
    cuerpo.append(f'<section class="record-section"><h3>{bi("Reproducibilidad", "Reproducibility")}</h3>'
                  f'<dl class="record-repro">{"".join(repro)}</dl></section>')
    cuerpo.append(f'<p><a class="text-link" href="#{e_(e["id"])}">'
                  f'{bi("Enlace a este expediente", "Link to this record")}</a></p>')

    return (
        f'<details class="record" id="{e_(e["id"])}" data-categoria="{c}" '
        f'data-paper="{1 if tiene_paper else 0}">'
        f'<summary><span class="record-id">{e_(e["id"])}</span><span class="record-main">'
        f'<span class="record-title" lang="es">{e_(titulo)}</span>'
        f'<span class="record-tags">{"".join(etiquetas)}</span></span></summary>'
        f'<div class="record-body">{"".join(cuerpo)}</div></details>'
    )


def render_registro(indice: Dict[str, Any], papers: Dict[str, Dict[str, Any]]) -> str:
    ids = {e["id"] for e in indice["experimentos"]}
    # Lo último sellado, arriba: es lo que alguien que vuelve no ha leído.
    orden = sorted(indice["experimentos"], key=lambda e: (e["sellado_en"] or "", e["id"]),
                   reverse=True)
    return "\n" + "\n".join(render_experimento(e, papers.get(e["id"]), ids) for e in orden) + "\n"


CLAVES_DEL_TUTORIAL = (
    ["ini_tut", "ini_tut_titulo", "ini_tut_intro", "ini_tut_paso", "ini_tut_anterior",
     "ini_tut_siguiente"]
    + [f"ini_tut_{p}_{c}" for p in PASOS_DEL_TUTORIAL for c in ("titulo", "texto", "alt")])


def leer_textos_del_tutorial(ts: str) -> Dict[str, Dict[str, str]]:
    """Las cadenas ``ini_tut_*`` de ``traducciones/inicio.ts``, en los dos idiomas.

    No hay un intérprete de TypeScript aquí: el módulo declara ``es: {…}`` y ``en: {…}``
    con una clave por línea (la cadena puede ir en la línea siguiente). Una clave que
    falte o cambie de forma falla, en vez de publicar un tutorial a medias.
    """
    inicio_en = re.search(r"^\s{2}en:\s*\{", ts, re.M)
    inicio_es = re.search(r"^\s{2}es:\s*\{", ts, re.M)
    if not inicio_en or not inicio_es or inicio_es.start() > inicio_en.start():
        raise ErrorDeSitio("traducciones/inicio.ts ya no tiene la forma «es: {…} en: {…}»")
    bloques = {"es": ts[inicio_es.end():inicio_en.start()], "en": ts[inicio_en.end():]}
    textos: Dict[str, Dict[str, str]] = {}
    for idioma, bloque in bloques.items():
        encontrados = {
            m.group(1): json.loads(f'"{m.group(2)}"')
            for m in re.finditer(r'^\s*(ini_tut[a-z_]*):\s*\n?\s*"((?:[^"\\]|\\.)*)",?\s*$', bloque, re.M)}
        faltan = [k for k in CLAVES_DEL_TUTORIAL if k not in encontrados]
        if faltan:
            raise ErrorDeSitio(f"traducciones/inicio.ts ({idioma}): faltan {', '.join(faltan)}")
        textos[idioma] = {k: encontrados[k] for k in CLAVES_DEL_TUTORIAL}
    return textos


def _caja_del_tutorial(marca: Dict[str, Any]) -> Tuple[str, str, bool]:
    """El recuadro y la flecha de un paso, como en ``TutorialMolcy.tsx``: en % de la captura.

    La flecha apunta desde arriba; si el botón está pegado al borde superior, desde abajo.
    ``assets/molcy.js`` repite este cálculo al cambiar de paso o de idioma.
    """
    x, y, w, h = marca["caja"]
    ancho, alto = marca["ancho"], marca["alto"]

    def pc(v: float, total: float) -> str:
        return f"{v / total * 100:.2f}%"
    recuadro = (f"left:{pc(x - 4, ancho)};top:{pc(y - 4, alto)};"
                f"width:{pc(w + 8, ancho)};height:{pc(h + 8, alto)}")
    desde_abajo = y / alto < 0.14
    flecha = f"left:{pc(x + w / 2, ancho)};top:{pc(y + h + 10 if desde_abajo else y - 10, alto)}"
    return recuadro, flecha, desde_abajo


def render_tutorial(textos: Dict[str, Dict[str, str]], marcas: Dict[str, Any]) -> str:
    """El tutorial «Del caso al vídeo», del Inicio de la aplicación, para la portada."""
    es, en = textos["es"], textos["en"]

    def t(clave: str) -> str:
        return bi(e_(es[clave]), e_(en[clave]))
    pasos = []
    for i, p in enumerate(PASOS_DEL_TUTORIAL):
        actual = ' aria-current="step"' if i == 0 else ""
        pasos.append(
            f'<li><button type="button" data-paso="{p}"{actual}><span class="tutorial-n">{i + 1:02d}</span>'
            f'<span class="tutorial-step"><strong>{t(f"ini_tut_{p}_titulo")}</strong>'
            f'<span class="tutorial-text">{t(f"ini_tut_{p}_texto")}</span></span></button></li>')
    primero = PASOS_DEL_TUTORIAL[0]
    marca = marcas["es"][primero]
    recuadro, flecha, desde_abajo = _caja_del_tutorial(marca)
    total = len(PASOS_DEL_TUTORIAL)
    contador = bi(e_(es["ini_tut_paso"].format(n=1, total=total)),
                  e_(en["ini_tut_paso"].format(n=1, total=total)))
    datos_js = json.dumps({
        "pasos": list(PASOS_DEL_TUTORIAL),
        "marcas": {i: {p: marcas[i][p] for p in PASOS_DEL_TUTORIAL} for i in ("es", "en")},
        "paso": {"es": es["ini_tut_paso"], "en": en["ini_tut_paso"]},
        "alt": {i: {p: textos[i][f"ini_tut_{p}_alt"] for p in PASOS_DEL_TUTORIAL} for i in ("es", "en")},
    }, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (
        '<div class="tutorial" data-tutorial>'
        '<div class="tutorial-copy">'
        f'<span class="eyebrow">{t("ini_tut")}</span>'
        f'<h3 id="tutorial-title">{t("ini_tut_titulo")}</h3>'
        f'<p class="tutorial-intro">{t("ini_tut_intro")}</p>'
        f'<ol class="tutorial-steps">{"".join(pasos)}</ol></div>'
        '<figure class="tutorial-figure"><div class="tutorial-frame">'
        f'<img src="assets/tutorial/molcy/es/{primero}.webp" width="{marca["ancho"]}" height="{marca["alto"]}" '
        f'alt="{e_(es[f"ini_tut_{primero}_alt"])}" loading="lazy" data-tutorial-img>'
        f'<span class="tutorial-box" aria-hidden="true" data-tutorial-box style="{recuadro}"></span>'
        f'<span class="tutorial-arrow" aria-hidden="true" data-tutorial-arrow '
        f'data-desde="{"abajo" if desde_abajo else "arriba"}" style="{flecha}">'
        '<svg viewBox="0 0 24 24"><path d="M12 4v16m-6-6 6 6 6-6"/></svg></span></div>'
        f'<figcaption class="tutorial-caption"><span class="tutorial-count" data-tutorial-count>{contador}</span>'
        '<span class="tutorial-nav">'
        f'<button type="button" data-tutorial-prev disabled data-label-es="{e_(es["ini_tut_anterior"])}" '
        f'data-label-en="{e_(en["ini_tut_anterior"])}" aria-label="{e_(es["ini_tut_anterior"])}">'
        '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M19 12H5m6 6-6-6 6-6"/></svg></button>'
        f'<button type="button" data-tutorial-next data-label-es="{e_(es["ini_tut_siguiente"])}" '
        f'data-label-en="{e_(en["ini_tut_siguiente"])}" aria-label="{e_(es["ini_tut_siguiente"])}">'
        '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M5 12h14m-6-6 6 6-6 6"/></svg></button>'
        '</span></figcaption></figure>'
        f'<script type="application/json" id="datos-tutorial-molcy">{datos_js}</script></div>'
    )


def capturas_del_tutorial(sitio: Path) -> Dict[Path, bytes]:
    """Las capturas del tutorial, copiadas tal cual de la aplicación."""
    salida = {}
    for idioma in ("es", "en"):
        for p in PASOS_DEL_TUTORIAL:
            origen = TUTORIAL_CAPTURAS / idioma / f"{p}.webp"
            if not origen.exists():
                raise ErrorDeSitio(f"falta {origen}; regenera el tutorial de la aplicación")
            salida[sitio / "assets" / "tutorial" / "molcy" / idioma / f"{p}.webp"] = origen.read_bytes()
    return salida


def catalogo_publico() -> Dict[str, Any]:
    """Lo que /catalogo enseña de los receptores, sacado de sus fuentes en cada construcción.

    La fecha es la de la última versión registrada del catálogo (`docs/catalog_versions/*-AAAA-MM-DD.json`), no la de
    hoy: así la misma fuente da siempre el mismo fichero.
    """
    crudo = CATALOGO.read_bytes()
    filas = json.loads(crudo.decode("utf-8"))
    disponibilidad = json.loads(DISPONIBILIDAD.read_text(encoding="utf-8"))
    sha = hashlib.sha256(crudo).hexdigest()
    if disponibilidad.get("catalogo_sha256") != sha:
        raise ErrorDeSitio("disponibilidad_catalogo.json no es la del catálogo actual; "
                           "corre scripts/generate_catalog_availability.py --write")
    fechas = sorted(m.stem[-10:] for m in VERSIONES_DEL_CATALOGO.glob("*-????-??-??.json"))
    if not fechas:
        raise ErrorDeSitio("no hay ninguna versión registrada del catálogo en docs/catalog_versions")
    verificados = json.loads(VERIFICADOS.read_text(encoding="utf-8")).get("verificados") or []
    no_disponibles = {k: v.get("paso") for k, v in sorted(disponibilidad["no_disponibles"].items())}
    return {
        "source": CATALOGO.name,
        "sha256": sha,
        "snapshot_date": fechas[-1],
        "count": len(filas),
        "section": "demostracion",
        "verified_count": len(verificados),
        # Lo que la ficha del explorador cita de cada verificado; el resto del sello vive en la aplicación.
        "verified": {pdb: {"experiment": v["experimento"], "rho": v["calibracion"]["rho"], "ci95": v["calibracion"]["ic95"],
                           "n": v["calibracion"]["n"], "panel": v["calibracion"]["panel"]}
                     for pdb, v in sorted(verificados.items())},
        # Lo que la ficha del explorador cita de cada verificado; el resto del sello vive en la aplicación.
        "verified": {pdb: {"experiment": v["experimento"], "rho": v["calibracion"]["rho"], "ci95": v["calibracion"]["ic95"],
                           "n": v["calibracion"]["n"], "panel": v["calibracion"]["panel"]}
                     for pdb, v in sorted(verificados.items())},
        "recipe": disponibilidad["receta_receptor"],
        "unavailable_count": len(no_disponibles),
        "record_fields": ["pdb", "name", "family", "organism", "resolution", "chain"],
        "records": [[f["pdb_id"], f.get("name"), f.get("structural_family"), f.get("organism"), f.get("resolution"),
                     f.get("chain")] for f in filas],
        "unavailable": no_disponibles,
        "warnings": json.loads(AVISOS.read_text(encoding="utf-8"))["avisos"],
    }


def render_receptores(catalogo: Dict[str, Any]) -> str:
    crudo = json.dumps(catalogo, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" id="datos-receptores">{crudo}</script>'


# ──────────────────────────────────────────────────────────────── construcción

def construir(sitio: Path = SITIO, registro: Path = REGISTRO) -> Dict[Path, Union[str, bytes]]:
    """Devuelve el contenido que debería tener cada archivo generado o gestionado.

    Texto para las páginas; ``bytes`` para las capturas del tutorial, que se copian.
    """
    textos = {}
    for p in PAGINAS:
        ruta = sitio / p.archivo
        if not ruta.exists():
            raise ErrorDeSitio(f"falta {ruta}")
        textos[p] = ruta.read_text(encoding="utf-8")

    indice, papers = cargar_registro(registro)
    catalogo = catalogo_publico()
    valores = datos(indice, catalogo)
    demo_p = sitio / "assets" / "molcy-demo.json"
    if demo_p.exists():
        valores.update(datos_de_la_demo(json.loads(demo_p.read_text(encoding="utf-8")),
                                        catalogo, sitio / "assets"))
    valores.update(datos_de_preparacion(json.loads(FEP09R1.read_text(encoding="utf-8"))))
    tutorial = render_tutorial(
        leer_textos_del_tutorial(TUTORIAL_TEXTOS.read_text(encoding="utf-8")),
        json.loads(TUTORIAL_MARCAS.read_text(encoding="utf-8")))

    maestros = {n: leer_bloque(textos[MAESTRA], "compartido", n, MAESTRA.archivo)
                for n in COMPARTIDOS}

    salida: Dict[Path, Union[str, bytes]] = {
        sitio / "receptors.json": json.dumps(catalogo, ensure_ascii=False, indent=2) + "\n"}
    for p, texto in textos.items():
        if p is not MAESTRA:
            for n in COMPARTIDOS:
                bloque = marcar_pagina_actual(reubicar_urls(maestros[n], prefijo_de(p)), p.clave)
                texto = poner_bloque(texto, "compartido", n, bloque, p.archivo)
        if "<!-- generado:registro -->" in texto:
            texto = poner_bloque(texto, "generado", "registro",
                                 render_registro(indice, papers), p.archivo)
        if "<!-- generado:receptores -->" in texto:
            texto = poner_bloque(texto, "generado", "receptores",
                                 render_receptores(catalogo), p.archivo)
        if "<!-- generado:tutorial-molcy -->" in texto:
            texto = poner_bloque(texto, "generado", "tutorial-molcy", tutorial, p.archivo)
        texto = rellenar_datos(texto, valores, p.archivo)
        texto = poner_url_canonica(texto, p, p.archivo)
        salida[sitio / p.archivo] = texto

    urls = "".join(f"  <url><loc>{DOMINIO}{p.ruta}</loc></url>\n" for p in PAGINAS)
    salida[sitio / "sitemap.xml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n")
    salida[sitio / "robots.txt"] = f"User-agent: *\nAllow: /\n\nSitemap: {DOMINIO}sitemap.xml\n"
    salida.update(capturas_del_tutorial(sitio))
    return salida


# ──────────────────────────────────────────────────────────────── enlaces

class _Recolector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set = set()
        self.urls: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        for k in ("href", "src"):
            if a.get(k) is not None:
                self.urls.append(a[k])


def comprobar_enlaces(paginas: Dict[Path, Union[str, bytes]], sitio: Path) -> List[str]:
    """Cada URL relativa de cada página resuelve a un archivo, y cada ancla a un id.

    Un archivo de ``paginas`` se mira con su contenido nuevo, no el del disco: en
    ``--check`` es lo que se publicaría.
    """
    recolectados: Dict[Path, _Recolector] = {}

    def recolectar(ruta: Path) -> Optional[_Recolector]:
        ruta = ruta.resolve()
        if ruta not in recolectados:
            texto = paginas.get(ruta)
            if isinstance(texto, bytes):
                return None
            if texto is None:
                if not ruta.exists():
                    return None
                texto = ruta.read_text(encoding="utf-8")
            r = _Recolector()
            r.feed(texto)
            recolectados[ruta] = r
        return recolectados[ruta]

    paginas = {k.resolve(): v for k, v in paginas.items()}
    errores = []
    for origen in [k for k in paginas if k.suffix == ".html"]:
        rec = recolectar(origen)
        assert rec is not None
        for url in rec.urls:
            if _EXTERNA.match(url) or url.startswith(("data:", "mailto:")):
                continue
            camino, _, ancla = url.partition("#")
            destino = origen if not camino else (origen.parent / unquote(camino))
            if camino.endswith("/") or (camino and destino.resolve().is_dir()):
                destino = destino / "index.html"
            destino = destino.resolve()
            try:
                destino.relative_to(sitio.resolve())
            except ValueError:
                errores.append(f"{origen.relative_to(sitio.resolve())}: «{url}» sale de site/")
                continue
            rd = recolectar(destino) if destino.suffix == ".html" else None
            if rd is None and not destino.exists() and destino not in paginas:
                errores.append(f"{origen.relative_to(sitio.resolve())}: «{url}» no existe")
                continue
            if ancla and rd is not None and unquote(ancla) not in rd.ids:
                errores.append(f"{origen.relative_to(sitio.resolve())}: «{url}»: no hay "
                               f"ningún id=\"{unquote(ancla)}\"")
    return errores


def al_dia(p: Path, esperado: Union[str, bytes]) -> bool:
    """¿El archivo en disco es lo que se generaría? (sin mirar finales de línea en el texto)"""
    if not p.exists():
        return False
    if isinstance(esperado, bytes):
        return p.read_bytes() == esperado
    return p.read_text(encoding="utf-8").replace("\r\n", "\n") == esperado


def main() -> int:
    ap = argparse.ArgumentParser(description="Arma las páginas de la web pública")
    ap.add_argument("--check", action="store_true",
                    help="no escribe; falla si algo no coincide o un enlace no resuelve")
    args = ap.parse_args()

    try:
        salida = construir()
    except ErrorDeSitio as exc:
        print(f"[sitio] {exc}", file=sys.stderr)
        return 1

    errores = comprobar_enlaces(salida, SITIO)
    if args.check:
        distintos = [str(p.relative_to(SITIO)) for p, t in salida.items() if not al_dia(p, t)]
        for d in distintos:
            print(f"[sitio] DESACTUALIZADO: {d}; corre build_sitio_publico.py", file=sys.stderr)
        for e in errores:
            print(f"[sitio] ENLACE ROTO: {e}", file=sys.stderr)
        if distintos or errores:
            return 1
        print(f"[sitio] al día: {len(PAGINAS)} páginas, enlaces internos resueltos")
        return 0

    for p, t in salida.items():
        if al_dia(p, t):
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        # Se escribe aparte y se sustituye: un fallo a media escritura (un archivo que otro
        # programa tiene abierto, en Windows) no puede dejar una página vacía.
        tmp = p.with_name(p.name + ".tmp")
        if isinstance(t, bytes):
            tmp.write_bytes(t)
        else:
            tmp.write_text(t, encoding="utf-8", newline="\n")
        os.replace(tmp, p)
    for e in errores:
        print(f"[sitio] ENLACE ROTO: {e}", file=sys.stderr)
    tam = {str(p.relative_to(SITIO)): len(t.encode("utf-8")) for p, t in salida.items()
           if isinstance(t, str)}
    print("[sitio] " + ", ".join(f"{k} {v / 1024:.0f} KiB" for k, v in tam.items())
          + f"; {sum(isinstance(t, bytes) for t in salida.values())} capturas del tutorial")
    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
