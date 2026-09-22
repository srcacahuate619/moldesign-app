r"""
Construye el **paquete de escena** de un receptor curado: geometría + contrato.

# Qué problema resuelve

Renderizar los 380 receptores del catálogo en Blender es, en el fondo, el mismo
problema que resuelve el resto de MolDesign: entregar algo que un tercero pueda
reconstruir, con sus hashes y sus condiciones, y que **no permita afirmar más de
lo que se midió**. Un render es una afirmación visual. Si la escena enseña un
zinc que el receptor acoplado no tiene, el vídeo miente exactamente igual que
mentiría un dossier.

Por eso este módulo no produce una escena de Blender. Produce el **contrato**
que una escena de Blender debe respetar:

    dist/scenes/<PDB_ID>/
        scene.json            el contrato. Ni un solo concepto de Blender.
        geometry/
            deposited.pdb     unidad biológica (BIOMT aplicado si lo había)
            prepared.pdb      lo que el acoplamiento realmente ve
            site_ligand.pdb   el ligando cocristalizado, si lo hay
        MANIFEST.sha256

`scene.json` lleva tres bloques que importan más que la geometría:

  - `declarado`  — lo que se midió: aguas del sitio, diff fuente→preparado,
                   operadores de simetría aplicados, especies perdidas.
  - `no_dibujar` — lo que la escena NO puede representar porque MolDesign no lo
                   respalda. Es una lista dura.
  - `declarar_si_se_dibuja` — lo que sí puede aparecer, pero sólo con su
                   condición escrita en pantalla.

La lista `no_dibujar` es el aporte científico real de este exportador. El agente
que monte la escena no tiene por qué conocer `censo_de_aguas` ni haber leído
`analyzer.py` para saber que el ángulo del puente de hidrógeno no es medible
aquí; le basta con leer el contrato.

# Por qué la política de preparación se REUTILIZA y no se reimplementa

`prepared.pdb` sale de `services.docking.preparer._filter_pdb_content`, que es
la función que el producto ejecuta de verdad. Reimplementar el filtro «más o
menos igual» habría producido una geometría que se parece a la que se acopla sin
serlo, y el render habría heredado la diferencia sin que nadie pudiera verla.

Hay una desviación, y va declarada en `scene.json`: el camino multicadena real
aplica además `_recortar_al_sitio`, que deja un receptor de pocos kB alrededor
de la caja. Para renderizar queremos el receptor entero, así que el recorte NO
se aplica y el contrato lo dice en `prepared.recorte_al_sitio_aplicado = false`.

# El hallazgo que hace falta declarar en los 380

`cofactors_whitelist` está **vacío en las 380 entradas** de
`curated_targets.json`. Según el propio encabezado de
`services/chemistry/preparation_report.py`, eso significa que la ruta de
acoplamiento del producto elimina todas las aguas y, en la práctica, todos los
metales, en **todo** el catálogo. Un render de la estructura depositada que
enseñe su zinc y sus aguas no está enseñando el receptor que MolDesign evalúa.
Ambas geometrías se exportan, con nombres distintos, y el contrato dice cuál es
cuál.

# Uso

    PYTHONPATH=backend python scripts/scene_export/build_scene_package.py \
        --pdb-id 1AJ6 --pdb-id 5VB8 --out dist/scenes

    # los doce de prueba, uno por familia estructural grande
    PYTHONPATH=backend python scripts/scene_export/build_scene_package.py \
        --muestra-por-familia 1 --out dist/scenes

    # la tanda completa
    PYTHONPATH=backend python scripts/scene_export/build_scene_package.py \
        --todos --out dist/scenes

No escribe nunca fuera de `--out`, y `--out` no puede caer dentro de
`scripts/artifacts_science/`.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
SCHEMA = "moldesign.scene/1"

# Sólo para que el script corra desde cualquier cwd sin exigir PYTHONPATH.
if str(RAIZ / "backend") not in sys.path:
    sys.path.insert(0, str(RAIZ / "backend"))

from services.chemistry.censo_de_aguas import censar_aguas  # noqa: E402
from services.chemistry.ensamblaje_biologico import (  # noqa: E402
    generar_unidad_biologica,
)
from services.chemistry.preparation_report import preparation_report  # noqa: E402
from services.docking.preparer import _filter_pdb_content  # noqa: E402

CATALOGO = RAIZ / "curated_targets.json"
ESTRUCTURAS = RAIZ / "data" / "targets"

#: "A:ARG76" -> cadena, resname, numero. El formato lo fija `hotspots_source`.
_HOTSPOT = re.compile(r"^(?P<cadena>[A-Za-z0-9]+):(?P<resname>[A-Z]{1,3})(?P<num>-?\d+)$")


class SinEstructura(RuntimeError):
    """No hay archivo para ese PDB ID. Abstenerse es una salida válida."""


# ─────────────────────────────── entrada ────────────────────────────────


def _sha256_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _sha256_fichero(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def cargar_catalogo() -> list[dict[str, Any]]:
    return json.loads(CATALOGO.read_text(encoding="utf-8"))


def leer_estructura(pdb_id: str) -> tuple[str, Path]:
    """El `.pdb(.gz)` depositado. La búsqueda ignora mayúsculas a propósito:
    `data/targets/` mezcla `1AJ6.pdb.gz` con `1a0h.pdb.gz`."""
    objetivo = pdb_id.lower()
    for candidato in ESTRUCTURAS.iterdir():
        tallo = candidato.name.split(".")[0].lower()
        if tallo != objetivo:
            continue
        if candidato.name.endswith(".gz"):
            with gzip.open(candidato, "rt", encoding="utf-8", errors="replace") as fh:
                return fh.read(), candidato
        return candidato.read_text(encoding="utf-8", errors="replace"), candidato
    raise SinEstructura(f"{pdb_id}: sin estructura en {ESTRUCTURAS}")


# ─────────────────────────── piezas de la escena ────────────────────────


def parsear_hotspots(crudos: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """`[{'name': 'A:ARG76', 'importance': 1.0}]` -> selección estructurada.

    Un hotspot que no case con el patrón se conserva con `parseado = false` en
    vez de descartarse: perder silenciosamente un residuo del sitio sería el
    defecto, no la forma rara de su nombre.
    """
    salida: list[dict[str, Any]] = []
    for h in crudos or []:
        nombre = str(h.get("name", ""))
        m = _HOTSPOT.match(nombre)
        registro: dict[str, Any] = {
            "nombre": nombre,
            "importancia": h.get("importance"),
            "parseado": bool(m),
        }
        if m:
            registro |= {
                "cadena": m["cadena"],
                "resname": m["resname"],
                "numero": int(m["num"]),
            }
        salida.append(registro)
    return salida


def extraer_ligando_del_sitio(pdb_texto: str, het: str) -> tuple[str, list[tuple[float, float, float]]]:
    """Los HETATM de ese código químico, y sus coordenadas pesadas.

    Devuelve `("", [])` si el código no aparece. El ligando cocristalizado no
    siempre está en el archivo que se distribuye, y eso se declara.
    """
    het = het.strip().upper()
    lineas: list[str] = []
    coords: list[tuple[float, float, float]] = []
    for linea in pdb_texto.splitlines():
        if not linea.startswith("HETATM"):
            continue
        if linea[17:20].strip().upper() != het:
            continue
        lineas.append(linea)
        # Elemento en 77-78; el hidrógeno no cuenta como pesado.
        if linea[76:78].strip().upper() in {"H", "D"}:
            continue
        try:
            coords.append((float(linea[30:38]), float(linea[38:46]), float(linea[46:54])))
        except ValueError:
            continue
    return ("\n".join(lineas) + "\n" if lineas else "", coords)


def detectar_huecos_de_cadena(pdb_texto: str, corte_a: float = 4.5) -> list[dict[str, Any]]:
    """Roturas del esqueleto: CA consecutivos más lejos de lo que un enlace da.

    Un Cα-Cα contiguo mide 3.8 Å. Por encima de `corte_a` el esqueleto está
    roto, sea por residuos no resueltos o por un corte real. Importa para el
    render porque una cinta de tipo cartoon se dibuja **continua** por defecto:
    sin esta lista, la escena inventaría conectividad que la estructura no tiene.

    `FEP-02` midió huecos en 86 de 203 complejos, así que esto no es un caso raro.
    """
    por_cadena: dict[str, list[tuple[int, tuple[float, float, float]]]] = {}
    for linea in pdb_texto.splitlines():
        if not linea.startswith("ATOM  ") or linea[12:16] != " CA ":
            continue
        try:
            resi = int(linea[22:26])
            punto = (float(linea[30:38]), float(linea[38:46]), float(linea[46:54]))
        except ValueError:
            continue
        por_cadena.setdefault(linea[21], []).append((resi, punto))

    huecos: list[dict[str, Any]] = []
    for cadena, residuos in por_cadena.items():
        for (r1, p1), (r2, p2) in zip(residuos, residuos[1:]):
            d = sum((a - b) ** 2 for a, b in zip(p1, p2)) ** 0.5
            if d <= corte_a:
                continue
            huecos.append({
                "cadena": cadena,
                "entre_residuos": [r1, r2],
                "distancia_ca_ca_a": round(d, 2),
                "residuos_ausentes": max(0, r2 - r1 - 1),
            })
    return huecos


def _serie_censo(censo: Any) -> dict[str, Any]:
    """`CensoDeAguas` -> dict, incluidas las propiedades que no son campos."""
    candidatas = censo.candidatas_a_conservar
    return {
        "en_la_estructura": censo.en_la_estructura,
        "en_la_caja": censo.en_la_caja,
        "bien_coordinadas": censo.bien_coordinadas,
        "max_puentes": censo.max_puentes,
        "candidatas_a_conservar": len(candidatas),
        "aguas_de_la_caja": [asdict(a) | {"encerrada": a.encerrada} for a in censo.aguas],
        "nota": (
            "`candidatas_a_conservar` NO es una política: el producto retira "
            "todas las aguas. Es el corte que la medición deja en pie, pendiente "
            "de contrastar contra redocking. No la dibujes como decidida."
        ),
    }


def _procedencia(entrada_sha: str, fuente: Path) -> dict[str, Any]:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=RAIZ,
            capture_output=True, text=True, timeout=15,
        ).stdout.strip() or None
        sucio = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=RAIZ,
            capture_output=True, text=True, timeout=15,
        ).stdout.strip())
    except Exception:
        sha, sucio = None, None
    return {
        "generador": "scripts/scene_export/build_scene_package.py",
        "generado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": sha,
        "arbol_sucio": sucio,
        "curated_targets_sha256": entrada_sha,
        "estructura_fuente": str(fuente.relative_to(RAIZ)),
        "estructura_fuente_sha256": _sha256_fichero(fuente),
        "python": sys.version.split()[0],
    }


# ──────────────────────── lo que la escena no puede afirmar ─────────────


def _restricciones(ctx: dict[str, Any]) -> dict[str, Any]:
    """Las prohibiciones duras y las condicionadas, con su razón y su fuente.

    Cada entrada cita el módulo que la respalda para que se pueda auditar sin
    creerle nada a este archivo.
    """
    no: list[dict[str, str]] = [
        {
            "id": "angulo_puente_hidrogeno",
            "razon": (
                "El receptor no llega protonado al análisis PLIF, así que "
                "`_estimate_hbond_angle` devuelve None a propósito. Dibujar el "
                "hidrógeno en el puente o su geometría angular sería inventar la "
                "medida que el código se niega a estimar."
            ),
            "fuente": "backend/services/interactions/analyzer.py:278",
            "permitido_en_su_lugar": (
                "La línea punteada del contacto y su distancia en Å, sin H."
            ),
        },
        {
            "id": "trayectoria_de_union",
            "razon": (
                "MolDesign no ejecuta dinámica molecular. Un ligando que entra "
                "volando al bolsillo es una interpolación, y la unión real ocurre "
                "en µs-ms: ninguna trayectoria renderizable contiene ese evento."
            ),
            "fuente": "AGENTS.md, 'Lo que MolDesign NO es'",
            "permitido_en_su_lugar": (
                "Cámara en movimiento sobre receptor quieto; o modos normales "
                "(ProDy/ANM) etiquetados como aproximación armónica."
            ),
        },
        {
            "id": "movimiento_del_receptor_como_resultado",
            "razon": (
                "Vina acopla con receptor rígido. Cualquier deformación animada "
                "es invención del render, no salida del motor."
            ),
            "fuente": "backend/services/docking/vina_service.py",
            "permitido_en_su_lugar": (
                "Movimiento declarado como ilustrativo, nunca como resultado."
            ),
        },
    ]

    politica = ctx["politica"]

    if politica.get("aguas") == "elimina_todas":
        no.append({
            "id": "aguas_en_prepared",
            "razon": (
                f"El preparador retira HOH/WAT/DOD sin excepción. Esta estructura "
                f"trae {ctx['aguas_en_la_estructura']} aguas depositadas, "
                f"{ctx['aguas_en_la_caja']} de ellas dentro de la caja de "
                "acoplamiento. Ninguna existe en `prepared.pdb`."
            ),
            "fuente": "backend/services/docking/preparer.py:246 (_WATER_RESIDUES)",
            "permitido_en_su_lugar": (
                "Dibujarlas sobre `deposited.pdb`, rotuladas como retiradas."
            ),
        })

    # Metales y cofactores van por separado: el HEM de un citocromo P450 no es un
    # metal, es el centro catalítico entero, y desaparece igual.
    for clave, etiqueta in (("metales_eliminados", "metales"), ("cofactores_eliminados", "cofactores")):
        eliminados = politica.get(clave) or []
        if not eliminados:
            continue
        en_sitio = [e for e in eliminados if e in (ctx["especies_del_sitio_perdidas"] or [])]
        no.append({
            "id": f"{etiqueta}_en_prepared",
            "razon": (
                f"El receptor acoplado NO contiene {', '.join(sorted(eliminados))}"
                + (f" (en el sitio: {', '.join(sorted(en_sitio))})" if en_sitio else "")
                + ". La puerta de conservación depende de `cofactors_whitelist`, "
                "vacío en las 380 entradas del catálogo."
            ),
            "fuente": "backend/services/chemistry/preparation_report.py: politica_observada",
            "permitido_en_su_lugar": (
                "Sobre `deposited.pdb`, rotulados como ausentes del cálculo."
            ),
        })

    if ctx["huecos"]:
        peor = max(ctx["huecos"], key=lambda h: h["residuos_ausentes"])
        no.append({
            "id": "cinta_continua_sobre_hueco",
            "razon": (
                f"`prepared.pdb` tiene {len(ctx['huecos'])} rotura(s) del esqueleto "
                f"(la mayor: cadena {peor['cadena']}, entre {peor['entre_residuos'][0]} "
                f"y {peor['entre_residuos'][1]}, {peor['residuos_ausentes']} residuos "
                "ausentes). El estilo cartoon dibuja la cinta continua por defecto y "
                "eso inventa conectividad que la estructura no resuelve."
            ),
            "fuente": "detectado aquí: Cα-Cα > 4.5 Å entre residuos consecutivos",
            "permitido_en_su_lugar": (
                "Cortar la cinta en el hueco, o marcarlo con línea discontinua. "
                "Las posiciones exactas están en `declarado.huecos_de_cadena`."
            ),
        })

    condicionado: list[dict[str, str]] = [
        {
            "id": "hidrogenos",
            "condicion": (
                f"La estructura depositada es de {ctx['resolucion']} Å y no trae "
                "hidrógenos. Cualquier H en pantalla está reconstruido, y la "
                "validez física sólo es comparable bajo el protocolo de "
                "reconstrucción de MF-33-H-COR. Si aparecen, dilo."
            ),
            "fuente": "AGENTS.md, restricción 6",
        },
        {
            "id": "superficie_molecular",
            "condicion": (
                "El estilo de superficie de Molecular Nodes es una isosuperficie "
                "gaussiana, NO una SES de Connolly con sonda de 1.4 Å. Para un "
                "plano que argumente el encaje, calcula la SES fuera (ChimeraX/"
                "MSMS) o no llames 'superficie molecular' a lo que se ve."
            ),
            "fuente": "convención de representación",
        },
        {
            "id": "ligando_del_sitio",
            "condicion": (
                "`site_ligand.pdb` sale de registros HETATM y NO lleva órdenes de "
                "enlace: los aromáticos se infieren por distancia y salen mal. "
                "Para renderizarlo con química correcta, trae el SDF ideal del "
                "Chemical Component Dictionary de ese código HET."
            ),
            "fuente": "formato PDB",
        },
        {
            "id": "unidad_biologica",
            "condicion": (
                f"Se aplicaron {ctx['operadores']} operadores BIOMT "
                f"({'se generaron cadenas nuevas' if ctx['generado'] else 'sólo la identidad'}). "
                "Las cadenas generadas por simetría son copias exactas, no "
                "conformaciones independientes."
            ),
            "fuente": "backend/services/chemistry/ensamblaje_biologico.py",
        },
    ]

    if ctx["cadenas_perdidas_cerca_del_sitio"]:
        condicionado.append({
            "id": "cadena_proxima_al_sitio_ausente",
            "condicion": (
                "La(s) cadena(s) "
                f"{', '.join(ctx['cadenas_perdidas_cerca_del_sitio'])} están cerca "
                "del sitio en `deposited.pdb` pero NO en `prepared.pdb`. Si la "
                "escena las muestra contactando el bolsillo, di que no participaron "
                "en el acoplamiento."
            ),
            "fuente": "alerta CADENA_O_HUECO_CERCA_DEL_SITIO",
        })

    return {"no_dibujar": no, "declarar_si_se_dibuja": condicionado}


# ───────────────────────────── construcción ─────────────────────────────


def construir(entrada: dict[str, Any], destino: Path, catalogo_sha: str) -> dict[str, Any]:
    pdb_id = entrada["pdb_id"]
    depositado, fuente = leer_estructura(pdb_id)

    ensamblaje = generar_unidad_biologica(depositado, pdb_id=pdb_id)
    biologico = ensamblaje.pdb

    centro = (entrada["grid_center_x"], entrada["grid_center_y"], entrada["grid_center_z"])
    tamano = (entrada["grid_size_x"], entrada["grid_size_y"], entrada["grid_size_z"])

    censo = censar_aguas(biologico, centro, tamano, medir_sitio=True)

    cadenas_sitio = entrada.get("site_chains") or [entrada.get("chain") or "A"]
    # Misma política que el producto. Sin `_recortar_al_sitio`: aquí se quiere el
    # receptor entero para poder renderizarlo, y el contrato lo declara.
    preparado = _filter_pdb_content(
        biologico,
        set(cadenas_sitio),
        keep_hetatm=False,
        cofactors_whitelist=entrada.get("cofactors_whitelist") or None,
    )

    het = (entrada.get("site_ligand") or "").strip()
    ligando_texto, ligando_coords = extraer_ligando_del_sitio(biologico, het) if het else ("", [])

    reporte = preparation_report(
        biologico,
        preparado,
        ruta="producto_docking",
        ligando_coords=ligando_coords or None,
    )

    # ── escritura ──
    carpeta = destino / pdb_id.upper()
    geo = carpeta / "geometry"
    geo.mkdir(parents=True, exist_ok=True)

    archivos: dict[str, str] = {}

    def _escribir(nombre: str, texto: str) -> dict[str, Any]:
        ruta = geo / nombre
        ruta.write_text(texto, encoding="utf-8")
        archivos[f"geometry/{nombre}"] = _sha256_texto(texto)
        return {
            "ruta": f"geometry/{nombre}",
            "sha256": archivos[f"geometry/{nombre}"],
            "atomos": sum(1 for l in texto.splitlines() if l.startswith(("ATOM  ", "HETATM"))),
        }

    geo_depositado = _escribir("deposited.pdb", biologico) | {
        "que_es": "unidad biológica del archivo depositado, antes de preparar",
        "operadores_biomt": ensamblaje.operadores,
        "genero_cadenas_nuevas": ensamblaje.generado,
        "cadenas": list(ensamblaje.cadenas_finales),
    }
    geo_preparado = _escribir("prepared.pdb", preparado) | {
        "que_es": "el receptor que la ruta de acoplamiento ejecuta de verdad",
        "politica": "services.docking.preparer._filter_pdb_content",
        "cadenas_conservadas": sorted(cadenas_sitio),
        "recorte_al_sitio_aplicado": False,
        "nota_recorte": (
            "El camino multicadena del producto aplica además `_recortar_al_sitio`. "
            "Aquí NO se aplica, porque la escena necesita el receptor completo. La "
            "química conservada es la misma; la extensión no."
        ),
    }
    geo_ligando: dict[str, Any] | None = None
    if ligando_texto:
        geo_ligando = _escribir("site_ligand.pdb", ligando_texto) | {
            "que_es": f"ligando cocristalizado {het}, extraído del depositado",
            "codigo_het": het,
            "ordenes_de_enlace": False,
        }

    huecos = detectar_huecos_de_cadena(preparado)
    resumen_sitio = reporte.get("resumen_sitio") or {}
    cadenas_cerca = [
        c
        for a in reporte.get("alertas", [])
        if a.get("codigo") == "CADENA_O_HUECO_CERCA_DEL_SITIO"
        for c in (a.get("detalle") or {}).get("cadenas_perdidas", [])
    ]

    restricciones = _restricciones({
        "politica": reporte.get("politica_observada") or {},
        "especies_del_sitio_perdidas": resumen_sitio.get("especies_del_sitio_perdidas") or [],
        "cadenas_perdidas_cerca_del_sitio": cadenas_cerca,
        "huecos": huecos,
        "aguas_en_la_estructura": censo.en_la_estructura,
        "aguas_en_la_caja": censo.en_la_caja,
        "resolucion": entrada.get("resolution"),
        "operadores": ensamblaje.operadores,
        "generado": ensamblaje.generado,
    })

    escena = {
        "schema": SCHEMA,
        "receptor": {
            "pdb_id": pdb_id.upper(),
            "nombre": entrada.get("name"),
            "organismo": entrada.get("organism"),
            "resolucion_a": entrada.get("resolution"),
            "familia_estructural": entrada.get("structural_family"),
            "cadena_principal": entrada.get("chain"),
            "cadenas_del_sitio": sorted(cadenas_sitio),
            "sitio_multicadena": len(cadenas_sitio) > 1,
            "destacado": bool(entrada.get("is_hot")),
        },
        "encuadre": {
            "objetivo": list(centro),
            "caja": list(tamano),
            "fuente": "curated_targets.json: grid_center_* / grid_size_*",
            "evidencia_del_sitio": entrada.get("site_evidence"),
            "nota": (
                "El objetivo es el centro de la caja de acoplamiento adjudicada, "
                "no el centroide de la proteína. Apunta la cámara aquí."
            ),
        },
        "resaltar": {
            "hotspots": parsear_hotspots(entrada.get("hotspots")),
            "fuente": entrada.get("hotspots_source"),
            "nota": (
                "`importancia` ordena residuos del bolsillo; no es energía de "
                "unión ni contribución medida."
            ),
        },
        "geometria": {
            "deposited": geo_depositado,
            "prepared": geo_preparado,
            "site_ligand": geo_ligando,
        },
        "declarado": {
            "aguas": _serie_censo(censo),
            "huecos_de_cadena": huecos,
            "politica_de_preparacion": reporte.get("politica_observada"),
            "diff_fuente_preparado": reporte,
            "unidad_biologica": {
                "operadores_aplicados": ensamblaje.operadores,
                "cadenas_originales": list(ensamblaje.cadenas_originales),
                "cadenas_finales": list(ensamblaje.cadenas_finales),
                "genero_cadenas_nuevas": ensamblaje.generado,
            },
        },
        **restricciones,
        "procedencia": _procedencia(catalogo_sha, fuente),
    }

    (carpeta / "scene.json").write_text(
        json.dumps(escena, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    (carpeta / "MANIFEST.sha256").write_text(
        "".join(f"{sha}  {ruta}\n" for ruta, sha in sorted(archivos.items())),
        encoding="utf-8",
    )
    return escena


# ─────────────────────────────── CLI ────────────────────────────────────


def seleccionar(catalogo: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.todos:
        return catalogo
    if args.pdb_id:
        pedidos = {p.upper() for p in args.pdb_id}
        elegidos = [e for e in catalogo if e["pdb_id"].upper() in pedidos]
        faltan = pedidos - {e["pdb_id"].upper() for e in elegidos}
        if faltan:
            raise SystemExit(f"No están en el catálogo: {', '.join(sorted(faltan))}")
        return elegidos
    if args.muestra_por_familia:
        por_familia: dict[str, list[dict[str, Any]]] = {}
        for e in catalogo:
            por_familia.setdefault(e.get("structural_family") or "sin_familia", []).append(e)
        # Familias grandes primero: es donde se rompe el encuadre automático.
        orden = sorted(por_familia.items(), key=lambda kv: -len(kv[1]))
        return [e for _, v in orden for e in v[: args.muestra_por_familia]]
    raise SystemExit("Elige --todos, --pdb-id o --muestra-por-familia.")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pdb-id", action="append", help="uno o varios IDs del catálogo")
    p.add_argument("--todos", action="store_true", help="los 380")
    p.add_argument("--muestra-por-familia", type=int, metavar="N",
                   help="N receptores por familia estructural, las grandes primero")
    p.add_argument("--out", default="dist/scenes", help="destino (por defecto dist/scenes)")
    args = p.parse_args()

    destino = (RAIZ / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    if "artifacts_science" in destino.parts:
        raise SystemExit("`scripts/artifacts_science/` está sellado: elige otro --out.")
    destino.mkdir(parents=True, exist_ok=True)

    catalogo = cargar_catalogo()
    catalogo_sha = _sha256_fichero(CATALOGO)
    elegidos = seleccionar(catalogo, args)

    print(f"{len(elegidos)} receptores -> {destino}\n")
    ok, fallos = 0, []
    for e in elegidos:
        pdb_id = e["pdb_id"]
        try:
            escena = construir(e, destino, catalogo_sha)
        except Exception as exc:  # una estructura mala no debe tumbar la tanda
            fallos.append((pdb_id, f"{type(exc).__name__}: {exc}"))
            print(f"  ABSTENIDO {pdb_id:6s}  {type(exc).__name__}: {exc}")
            continue
        ok += 1
        g = escena["geometria"]
        print(
            f"  OK        {pdb_id:6s}  {escena['receptor']['familia_estructural'] or '-':22s}"
            f" dep {g['deposited']['atomos']:6d}  prep {g['prepared']['atomos']:6d}"
            f"  aguas_caja {escena['declarado']['aguas']['en_la_caja']:3d}"
            f"  lig {'si' if g['site_ligand'] else 'no'}"
            f"  no_dibujar {len(escena['no_dibujar'])}"
        )

    print(f"\n{ok} paquetes escritos, {len(fallos)} abstenciones.")
    for pdb_id, motivo in fallos:
        print(f"  {pdb_id}: {motivo}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
