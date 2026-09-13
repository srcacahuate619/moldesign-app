#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_registro_cientifico.py — construye el registro publico de experimentos.

Lee los manifests sellados de `scripts/artifacts_science/`, sus `metrics.json`, la
taxonomia editorial de `_taxonomia.json` y los papers escritos a mano de
`docs/papers/<ID>.md`, y emite JSON estatico para la app en
`frontend/public/registro/`.

Reglas de diseno
----------------
1. **El manifest es la fuente de verdad de los hechos.** Decision, gate, semillas,
   commit, hashes, duracion y metricas se leen del manifest en cada build. El paper
   escrito a mano aporta la PROSA; si el manifest cambia, la ficha cambia sola y la
   prosa no puede mentir sobre un numero sin que se note al lado.
2. **Nada de HTML crudo.** El markdown se convierte a bloques estructurados
   (`heading`, `parrafo`, `lista`, `tabla`, `cita`, `codigo`) que el frontend renderiza
   con sus propios componentes. La app tiene CSP estricta y `dangerouslySetInnerHTML`
   no entra aqui.
3. **Sin paper tambien funciona.** Un experimento sin `docs/papers/<ID>.md` se publica
   igual con su ficha generada. Los papers se van escribiendo sin romper la vista.

Uso
---
    python scripts/build_registro_cientifico.py [--check]

`--check` no escribe: falla con codigo 1 si el registro emitido no coincide con el
que hay en disco (util en CI para detectar que alguien edito el JSON a mano).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTEFACTOS = PROJECT_ROOT / "scripts" / "artifacts_science"
PAPERS = PROJECT_ROOT / "docs" / "papers"
SALIDA = PROJECT_ROOT / "frontend" / "public" / "registro"

CATEGORIAS = ("hallazgo", "refutacion", "medicion", "prerregistro",
              "corrigendum", "inconcluso")

RE_DESCRIPTIVO = re.compile(
    r"descriptiv|sin umbral|sin gates|sin gate\b|sin decision|no decide", re.I)
RE_CORRIGENDUM = re.compile(r"-(R1|R2|RE)$")
RE_PRERREGISTRO = re.compile(r"-PRE(-R1)?$")


# ────────────────────────────────────────────────────────── markdown → bloques

RE_NEGRITA = re.compile(r"\*\*(.+?)\*\*")
RE_CURSIVA = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
RE_CODIGO = re.compile(r"`([^`]+)`")
RE_ENLACE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _inline(texto: str) -> List[Dict[str, Any]]:
    """Parte una linea en fragmentos con marca. Orden: codigo, enlace, negrita, cursiva.

    Devuelve [{t: texto, m: None|'fuerte'|'enfasis'|'codigo'|'enlace', href}].
    """
    piezas: List[Dict[str, Any]] = [{"t": texto, "m": None}]

    def aplicar(rx: re.Pattern, marca: str, con_href: bool = False):
        nuevas: List[Dict[str, Any]] = []
        for p in piezas:
            if p["m"] is not None:
                nuevas.append(p)
                continue
            resto = p["t"]
            pos = 0
            for mm in rx.finditer(resto):
                if mm.start() > pos:
                    nuevas.append({"t": resto[pos:mm.start()], "m": None})
                if con_href:
                    nuevas.append({"t": mm.group(1), "m": marca, "href": mm.group(2)})
                else:
                    nuevas.append({"t": mm.group(1), "m": marca})
                pos = mm.end()
            if pos < len(resto):
                nuevas.append({"t": resto[pos:], "m": None})
        piezas[:] = [x for x in nuevas if x["t"] != ""]

    aplicar(RE_CODIGO, "codigo")
    aplicar(RE_ENLACE, "enlace", con_href=True)
    aplicar(RE_NEGRITA, "fuerte")
    aplicar(RE_CURSIVA, "enfasis")
    return piezas


def _fila_tabla(linea: str) -> List[str]:
    partes = linea.strip().strip("|").split("|")
    return [p.strip() for p in partes]


def markdown_a_bloques(texto: str) -> List[Dict[str, Any]]:
    """Subconjunto de markdown suficiente para escritura cientifica.

    Soporta: encabezados (##, ###, ####), parrafos, listas con - y 1., tablas con
    pipes, citas con >, y bloques de codigo con ```.
    """
    bloques: List[Dict[str, Any]] = []
    lineas = texto.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lineas):
        l = lineas[i]
        s = l.strip()

        if not s:
            i += 1
            continue

        if s.startswith("```"):
            lang = s[3:].strip() or None
            cuerpo: List[str] = []
            i += 1
            while i < len(lineas) and not lineas[i].strip().startswith("```"):
                cuerpo.append(lineas[i])
                i += 1
            i += 1
            bloques.append({"tipo": "codigo", "lang": lang, "texto": "\n".join(cuerpo)})
            continue

        m = re.match(r"^(#{2,4})\s+(.*)$", s)
        if m:
            bloques.append({"tipo": "encabezado", "nivel": len(m.group(1)),
                            "frag": _inline(m.group(2).strip())})
            i += 1
            continue

        if s.startswith(">"):
            cuerpo = []
            while i < len(lineas) and lineas[i].strip().startswith(">"):
                cuerpo.append(lineas[i].strip().lstrip(">").strip())
                i += 1
            bloques.append({"tipo": "cita", "frag": _inline(" ".join(cuerpo))})
            continue

        if s.startswith("|") and i + 1 < len(lineas) and \
                re.match(r"^\|[\s:\-|]+\|$", lineas[i + 1].strip()):
            cab = _fila_tabla(s)
            aliner = [("derecha" if c.endswith(":") and not c.startswith(":")
                       else "centro" if c.startswith(":") and c.endswith(":")
                       else "izquierda") for c in _fila_tabla(lineas[i + 1])]
            i += 2
            filas = []
            while i < len(lineas) and lineas[i].strip().startswith("|"):
                filas.append([_inline(c) for c in _fila_tabla(lineas[i])])
                i += 1
            bloques.append({"tipo": "tabla",
                            "cabecera": [_inline(c) for c in cab],
                            "alineacion": aliner, "filas": filas})
            continue

        if re.match(r"^[-*]\s+", s) or re.match(r"^\d+[.)]\s+", s):
            ordenada = bool(re.match(r"^\d+[.)]\s+", s))
            items = []
            while i < len(lineas):
                t = lineas[i].strip()
                mm = re.match(r"^(?:[-*]|\d+[.)])\s+(.*)$", t)
                if not mm:
                    break
                items.append(_inline(mm.group(1)))
                i += 1
            bloques.append({"tipo": "lista", "ordenada": ordenada, "items": items})
            continue

        inicio = i
        parrafo = []
        while i < len(lineas) and lineas[i].strip() and \
                not lineas[i].strip().startswith(("#", ">", "|", "```")) and \
                not re.match(r"^(?:[-*]|\d+[.)])\s+", lineas[i].strip()):
            parrafo.append(lineas[i].strip())
            i += 1
        if i == inicio:
            # GARANTIA DE AVANCE. Una linea que empieza por un caracter estructural
            # pero no formo bloque -por ejemplo un parrafo que arranca con notacion de
            # valor absoluto, |dq|, o un "|" suelto sin fila separadora debajo- dejaba
            # el indice sin avanzar y colgaba el generador en un bucle infinito que
            # acumulaba parrafos vacios hasta agotar la memoria (7 GB medidos).
            # Se consume como texto plano: preferible un parrafo mal formateado a un
            # build que no termina.
            parrafo.append(lineas[i].strip())
            i += 1
        bloques.append({"tipo": "parrafo", "frag": _inline(" ".join(parrafo))})

    return bloques


def leer_paper(exp_id: str) -> Optional[Dict[str, Any]]:
    """Lee docs/papers/<ID>.md con frontmatter YAML sencillo (clave: valor)."""
    p = PAPERS / f"{exp_id}.md"
    if not p.exists():
        return None
    texto = p.read_text(encoding="utf-8")
    meta: Dict[str, str] = {}
    if texto.startswith("---"):
        fin = texto.find("\n---", 3)
        if fin > 0:
            for linea in texto[3:fin].strip().split("\n"):
                if ":" in linea:
                    k, v = linea.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"')
            texto = texto[fin + 4:]
    return {"meta": meta, "bloques": markdown_a_bloques(texto.strip()),
            "fuente": f"docs/papers/{exp_id}.md"}


# ─────────────────────────────────────────────────────────────── clasificacion

def clasificar(man: Dict[str, Any], overrides: Dict[str, str]) -> str:
    i = man["experiment_id"]
    if i in overrides:
        return overrides[i]
    dec = man.get("decision")
    g = man.get("gate")
    gtxt = g.get("description", "") if isinstance(g, dict) else str(g or "")
    if RE_PRERREGISTRO.search(i):
        return "prerregistro"
    if dec == "NO_GO":
        return "refutacion"
    if dec == "INCONCLUSIVE":
        return "inconcluso"
    if RE_DESCRIPTIVO.search(gtxt):
        return "medicion"
    if RE_CORRIGENDUM.search(i):
        return "corrigendum"
    return "hallazgo"


def resumir_metricas(exp_dir: Path) -> Optional[Dict[str, Any]]:
    p = exp_dir / "metrics.json"
    if not p.exists() or p.stat().st_size < 20:
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict):
        return None
    plano: Dict[str, Any] = {}
    for k, v in d.items():
        if k in ("experiment_id", "timestamp"):
            continue
        if isinstance(v, (int, float, str, bool)) or v is None:
            plano[k] = v
    return {"plano": plano, "completo": d}


def contar_lineas(p: Path) -> int:
    if not p.exists():
        return 0
    with open(p, "rb") as f:
        return sum(1 for l in f if l.strip())


#: Direcciones de red PRIVADAS (RFC 1918). Publicar la topología interna de un
#: laboratorio no aporta nada a la reproducibilidad y sí expone infraestructura.
_IP_PRIVADA = re.compile(
    r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"
)


def redactar_infraestructura(obj: Any) -> Any:
    """Sustituye direcciones IP privadas antes de PUBLICAR el registro.

    POR QUÉ AQUÍ Y NO EN EL ORIGEN. La procedencia de un experimento sellado
    dice en qué máquina corrió, y eso está bien: es parte de la evidencia y sus
    bytes están fijados por `assets_hashes`. Tocarlos rompería el sellado y la
    regla 5 de `AGENTS.md`.

    Lo que no tiene por qué ocurrir es que esa dirección viaje al registro
    PÚBLICO que la aplicación sirve. El artefacto conserva el dato exacto; su
    renderizado público lo sustituye por un marcador. La afirmación científica
    —qué se ejecutó, con qué imagen, cuántos trabajos— no cambia; lo único que
    desaparece es la topología de una red que no es de quien lee.
    """
    if isinstance(obj, str):
        return _IP_PRIVADA.sub("<host-interno>", obj)
    if isinstance(obj, list):
        return [redactar_infraestructura(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redactar_infraestructura(v) for k, v in obj.items()}
    return obj


def construir() -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    tax = json.loads((ARTEFACTOS / "_taxonomia.json").read_text(encoding="utf-8"))
    overrides = tax.get("overrides", {})
    etiquetas_por_exp: Dict[str, List[str]] = {}
    for etq, ids in (tax.get("etiquetas") or {}).items():
        for i in ids:
            etiquetas_por_exp.setdefault(i, []).append(etq)
    # Un registro cuyas cifras selladas quedaron REEMPLAZADAS por otro experimento no se
    # reescribe ni se re-sella: se marca. El aviso viaja en el contrato y no en la prosa,
    # porque un lector que entra por enlace directo a la ficha tiene que verlo aunque nadie
    # haya escrito el paper.
    reemplazos: Dict[str, str] = {
        k: v for k, v in (tax.get("reemplazos") or {}).items() if not k.startswith("_")
    }

    entradas: List[Dict[str, Any]] = []
    papers: Dict[str, Dict[str, Any]] = {}

    for d in sorted(ARTEFACTOS.iterdir()):
        man_p = d / "manifest.json"
        if not d.is_dir() or not man_p.exists():
            continue
        man = json.loads(man_p.read_text(encoding="utf-8"))
        if not man.get("sealed"):
            continue
        i = man["experiment_id"]
        g = man.get("gate")
        gate_txt = g.get("description", "") if isinstance(g, dict) else str(g or "")
        git = man.get("git_state") or {}
        env = man.get("environment") or {}
        met = resumir_metricas(d)
        paper = leer_paper(i)

        hashes = 0
        for k in ("dataset_hashes", "model_hashes", "binary_hashes", "assets_hashes"):
            v = man.get(k)
            if isinstance(v, dict):
                hashes += len(v)

        entrada = {
            "id": i,
            "categoria": clasificar(man, overrides),
            "etiquetas": sorted(etiquetas_por_exp.get(i, [])),
            "decision": man.get("decision"),
            "hipotesis": man.get("hypothesis"),
            "protocolo": man.get("protocol"),
            "gate": gate_txt,
            "razonamiento": man.get("decision_rationale"),
            "sellado_en": man.get("sealed_at"),
            "creado_en": man.get("created_at"),
            "duracion_s": man.get("duration_seconds"),
            "semillas": man.get("seeds"),
            "git": {"rama": git.get("branch"), "commit": (git.get("commit") or "")[:10],
                    "sucio": git.get("dirty")},
            "entorno": {"os": env.get("os"), "cpu": env.get("cpu_count"),
                        "ram_mb": env.get("total_ram_mb"), "gpu": env.get("gpu")},
            "n_hashes": hashes,
            "n_complejos": contar_lineas(d / "per_complex.jsonl"),
            "n_fallos": contar_lineas(d / "failures.jsonl"),
            "metricas": met["plano"] if met else None,
            "mantenimiento_sello": len(man.get("seal_maintenance") or []),
            "reemplazado_por": reemplazos.get(i),
            "tiene_paper": paper is not None,
            "titulo": (paper or {}).get("meta", {}).get("titulo") or i,
            "entradilla": (paper or {}).get("meta", {}).get("entradilla"),
        }
        entradas.append(entrada)
        if paper:
            papers[i] = {"id": i, "meta": paper["meta"], "bloques": paper["bloques"],
                         "fuente": paper["fuente"]}

    conteo = {c: sum(1 for e in entradas if e["categoria"] == c) for c in CATEGORIAS}
    indice = {
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "generador": "scripts/build_registro_cientifico.py",
        "advertencia": (
            "El cociente GO/NO_GO del manifest NO es una tasa de aciertos: mezcla "
            "prerregistros -sellados GO al declararse-, mediciones sin gate y "
            "experimentos con gate real. Esta vista separa las tres poblaciones."),
        "categorias": tax.get("_categorias", {}),
        "conteo": conteo,
        "total": len(entradas),
        "con_paper": sum(1 for e in entradas if e["tiene_paper"]),
        "destacados": tax.get("destacados", {}),
        "experimentos": sorted(entradas, key=lambda e: e["id"]),
    }
    # La redaccion es parte de CONSTRUIR el registro publico, no un paso
    # opcional de `main()`. Ahi estaba antes, y la prueba de contrato -que llama
    # a `construir()` directamente- comparaba el disco redactado contra un
    # indice sin redactar. Con un solo camino no hay forma de publicar sin pasar
    # por aqui.
    return redactar_infraestructura(indice), redactar_infraestructura(papers)


def main() -> int:
    ap = argparse.ArgumentParser(description="Construye el registro publico de experimentos")
    ap.add_argument("--check", action="store_true",
                    help="no escribe; falla si el registro en disco no coincide")
    args = ap.parse_args()

    indice, papers = construir()

    if args.check:
        p = SALIDA / "index.json"
        if not p.exists():
            print("[registro] FALTA frontend/public/registro/index.json", file=sys.stderr)
            return 1
        viejo = json.loads(p.read_text(encoding="utf-8"))
        a = {k: v for k, v in viejo.items() if k != "generado_en"}
        b = {k: v for k, v in indice.items() if k != "generado_en"}
        if a != b:
            print("[registro] DESACTUALIZADO: corre build_registro_cientifico.py",
                  file=sys.stderr)
            return 1
        print(f"[registro] al dia: {indice['total']} registros, "
              f"{indice['con_paper']} con paper")
        return 0

    (SALIDA / "papers").mkdir(parents=True, exist_ok=True)
    (SALIDA / "index.json").write_text(
        json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    for i, p in papers.items():
        (SALIDA / "papers" / f"{i}.json").write_text(
            json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")

    c = indice["conteo"]
    print(f"[registro] {indice['total']} registros sellados -> {SALIDA}")
    print(f"  hallazgos {c['hallazgo']}  refutaciones {c['refutacion']}  "
          f"mediciones {c['medicion']}  prerregistros {c['prerregistro']}  "
          f"corrigenda {c['corrigendum']}  inconclusos {c['inconcluso']}")
    print(f"  papers escritos: {indice['con_paper']}/{indice['total']}")
    # `no-paper-standalone` NO es una deuda: es una decision editorial declarada en
    # `_taxonomia.json`. Listarla como hueco haria que el aviso mintiera un poco cada vez.
    tax = json.loads((ARTEFACTOS / "_taxonomia.json").read_text(encoding="utf-8"))
    sin_deuda = set(tax.get("etiquetas", {}).get("no-paper-standalone", []))
    faltan = [e["id"] for e in indice["experimentos"]
              if not e["tiene_paper"] and e["categoria"] in ("hallazgo", "refutacion")
              and e["id"] not in sin_deuda]
    if faltan:
        print(f"  sin paper en las dos columnas protagonistas ({len(faltan)}): "
              f"{', '.join(faltan)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
