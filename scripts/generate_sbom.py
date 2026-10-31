"""SBOM del runtime que se distribuye, y sus licencias.

Gate de release. Antes de firmar y publicar hay que poder contestar tres
preguntas sin abrir una consola: qué se distribuye, bajo qué licencia, y con qué
huella. Las tres se contestaban a mano, que es como se contestan mal.

Alcance **deliberadamente estrecho**: el intérprete embebido
(`python-embed`), que es el que viaja en el instalador, más las dependencias
JavaScript bloqueadas del frontend, las crates Rust que enlaza el binario de
Windows y los ejecutables de terceros que `bundle_helper` empaqueta. No inventa
el árbol del desarrollador: en esta máquina hay 281 distribuciones Python
instaladas y sólo 170 se distribuyen. Un SBOM que declare las 281 es peor que
ninguno, porque afirma algo falso sobre lo que el investigador recibe.

`--check` falla en dos casos distintos: el archivo guardado ya no coincide con lo
que se genera, **o** la cobertura de licencias no es completa (algún componente
sin licencia, o las de Rust sin leer). Lo segundo es lo que impide sostener una
afirmación global como «ninguna dependencia declara AGPL ni SSPL».

Lo que este script **no** hace: buscar vulnerabilidades. Eso exige una base de
datos actualizada (OSV, GitHub Advisories) y por tanto red y una decisión sobre
qué servicio consultar. Aquí se deja el inventario listo para alimentarla.

Uso:
    python scripts/generate_sbom.py --write
    python scripts/generate_sbom.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON_EMBED = ROOT / "python-embed" / "python.exe"
LOCKFILE = ROOT / "frontend" / "package-lock.json"
CARGO_MANIFEST = ROOT / "frontend" / "src-tauri" / "Cargo.toml"
CARGO_LOCK = ROOT / "frontend" / "src-tauri" / "Cargo.lock"
SALIDA = ROOT / "docs" / "api" / "sbom.json"

#: Plataforma del instalador. Un `Cargo.lock` lista también las crates que sólo
#: se compilan para Linux, macOS o Android (222 de 575 hoy); el binario de
#: Windows no las lleva, y pedir su licencia hacía fallar `cargo metadata
#: --offline` porque no están en la caché. De ahí que el inventario cayera al
#: lockfile, que no trae licencias, y las 575 salieran en blanco.
PLATAFORMA_RUST = "x86_64-pc-windows-msvc"

#: Herramienta (directorio de `tools/`) → (ejecutable principal, fila de
#: THIRD_PARTY_NOTICES.md que declara su licencia). Las claves deben ser
#: exactamente `bundle_helper.HERRAMIENTAS_EMPAQUETADAS`: lo comprueba una
#: prueba. `smina` salió de aquí: nunca se empaquetó.
BINARIOS: dict[str, tuple[str, str | None]] = {
    "vina": ("tools/vina/vina.exe", "AutoDock Vina"),
    "xtb": ("tools/xtb/xtb.exe", "xTB"),
    "llama": ("tools/llama/llama-server.exe", "llama.cpp"),
    "openbabel": ("tools/openbabel/bin/obabel.exe", None),  # manifiesto propio
    "molcy": ("tools/molcy/scripts/maestro.py", None),  # programa propio del producto; manifiesto propio
    "molchat": ("tools/molchat/src/molchat_agent/__main__.py", None),  # programa propio; manifiesto propio
}

#: Dependencias sin licencia comprobable. Debe permanecer vacío para release.
SIN_RESOLVER: dict[str, str] = {}

#: Licencias que no permiten distribuir un binario cerrado sin abrir el propio.
#: No se bloquea automáticamente —hay excepciones legítimas, como un binario
#: invocado por subproceso— pero se marcan para que alguien las mire.
LICENCIAS_A_REVISAR = ("GPL", "AGPL", "SSPL", "CC BY-NC", "Commons Clause")

#: Un paquete puede declarar su copyleft con el nombre largo en vez del acrónimo:
#: `openbabel-wheel` dice "GNU GENERAL PUBLIC LICENSE", donde la subcadena "GPL"
#: no aparece. Buscar sólo el acrónimo dejaba el gate en verde con GPL-2.0
#: dentro del runtime distribuido. Se normaliza antes de comparar.
_SINONIMOS = (
    ("GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL"),
    ("AFFERO GENERAL PUBLIC LICENSE", "AGPL"),
    ("GNU LESSER GENERAL PUBLIC LICENSE", "LGPL"),
    ("GNU LIBRARY GENERAL PUBLIC LICENSE", "LGPL"),
    ("LESSER GENERAL PUBLIC LICENSE", "LGPL"),
    ("GNU GENERAL PUBLIC LICENSE", "GPL"),
    ("GENERAL PUBLIC LICENSE", "GPL"),
    ("SERVER SIDE PUBLIC LICENSE", "SSPL"),
    ("ATTRIBUTION-NONCOMMERCIAL", "CC BY-NC"),
    ("NONCOMMERCIAL", "CC BY-NC"),
)


def _normalizar_licencia(texto: str) -> str:
    """Nombre largo → acrónimo, para que la comparación por subcadena funcione."""
    normal = " ".join((texto or "").upper().split())
    for largo, corto in _SINONIMOS:
        if largo in normal:
            normal = normal.replace(largo, corto)
    return normal

_GUION = "python -c \"import json,importlib.metadata as md;print(json.dumps([{'nombre':d.metadata['Name'],'version':d.version,'licencia':(d.metadata.get('License-Expression') or d.metadata.get('License') or '').split(chr(10))[0][:80] or next((c.split('::')[-1].strip() for c in (d.metadata.get_all('Classifier') or []) if c.startswith('License')),'')} for d in md.distributions()]))\""


def _paquetes_python() -> list[dict]:
    """Lo que hay dentro de `python-embed`, preguntándoselo a él mismo."""
    if not PYTHON_EMBED.exists():
        raise SystemExit(
            f"No existe {PYTHON_EMBED}. El SBOM describe el runtime que se "
            "distribuye; sin él no hay nada que declarar."
        )
    proceso = subprocess.run(
        [str(PYTHON_EMBED), "-c", _GUION.split('"', 1)[1].rsplit('"', 1)[0]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proceso.returncode != 0:
        raise SystemExit(f"No se pudo inventariar python-embed:\n{proceso.stderr[-1500:]}")
    paquetes = json.loads(proceso.stdout)
    return sorted(
        ({"nombre": p["nombre"], "version": p["version"], "licencia": p["licencia"]}
         for p in paquetes if p.get("nombre")),
        key=lambda p: (p["nombre"] or "").lower(),
    )


def _paquetes_npm() -> list[dict]:
    """Dependencias JS **bloqueadas**: lo que `npm ci` instalará, ni más ni menos."""
    if not LOCKFILE.exists():
        return []
    datos = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    entradas = datos.get("packages", {})
    paquetes = []
    for ruta, info in entradas.items():
        if not ruta or info.get("dev"):
            continue
        nombre = ruta.split("node_modules/")[-1]
        paquetes.append({
            "nombre": nombre,
            "version": info.get("version", ""),
            "licencia": _licencia_npm(info),
        })
    return sorted(paquetes, key=lambda p: p["nombre"].lower())


def _licencia_npm(info: dict) -> str:
    """La licencia de un paquete npm, en cualquiera de sus tres formas.

    EL FALLO QUE ARREGLA. Este lector miraba sólo `license`, la forma moderna.
    npm admite además la forma HEREDADA `licenses`, que es una lista —de
    cadenas o de objetos `{type, url}`—, y cuatro paquetes distribuidos la
    usan: `busboy`, `eyes`, `streamsearch` y `asap`. Los cuatro DECLARAN MIT y
    los cuatro aparecían en `sin_licencia_declarada`.

    El coste no es cosmético. Ese apartado existe para que alguien mire lo que
    nadie ha mirado; llenarlo de paquetes que sí declaran licencia lo convierte
    en ruido, y el ruido es lo que hace que un apartado deje de leerse. Es el
    mismo modo de fallo que dejó el gate verde con Open Babel dentro: un
    detector que no sabe leer una forma legítima informa de lo que él no
    entiende, no de lo que pasa.
    """
    directa = info.get("license")
    if isinstance(directa, str) and directa.strip():
        return directa.strip()
    if isinstance(directa, dict):  # `{"type": "MIT", "url": ...}`
        return str(directa.get("type") or "").strip()

    heredada = info.get("licenses")
    if isinstance(heredada, str):
        return heredada.strip()
    if isinstance(heredada, list):
        tipos = [
            (e.get("type") if isinstance(e, dict) else e) or "" for e in heredada
        ]
        limpios = [str(t).strip() for t in tipos if str(t).strip()]
        # Varias licencias a elegir se expresan como `A OR B`, que es lo que
        # entiende SPDX y lo que el detector de copyleft ya sabe leer.
        return " OR ".join(dict.fromkeys(limpios))
    return ""



def _entrada_crate(paquete: dict) -> dict:
    return {
        "nombre": paquete.get("name", ""),
        "version": paquete.get("version", ""),
        "licencia": (paquete.get("license") or "").strip(),
        "fuente": paquete.get("repository") or paquete.get("source") or "",
    }


def _clasificar_crates(datos: dict) -> tuple[list[dict], list[dict]]:
    """(enlazadas, sólo-de-construcción) a partir de la salida de `cargo metadata`.

    *Enlazadas* son las que alcanza el producto por dependencias normales: lo que
    termina en el binario. *Sólo de construcción* son las que alcanza únicamente
    por `build-dependencies` (`build.rs`, `tauri-build`): se ejecutan al compilar
    y no viajan, pero se listan aparte para que nada quede escondido. Las de
    desarrollo (`dev`) no entran en ninguna de las dos. El producto mismo no es
    una dependencia de terceros de sí mismo.
    """
    paquetes = {p["id"]: p for p in datos.get("packages", [])}
    resolucion = datos.get("resolve") or {}
    nodos = {n["id"]: n for n in resolucion.get("nodes", [])}
    raiz = resolucion.get("root")

    if raiz is None or raiz not in nodos:
        # Un espacio de trabajo virtual no tiene raíz desde la que recorrer: no se
        # inventa una clausura, se declara todo como enlazado.
        todas = sorted(
            (_entrada_crate(p) for p in paquetes.values()),
            key=lambda p: (p["nombre"].lower(), p["version"]),
        )
        return todas, []

    def alcance(tipos: set) -> set[str]:
        visto: set[str] = set()
        pila = [raiz]
        while pila:
            actual = pila.pop()
            if actual in visto or actual not in nodos:
                continue
            visto.add(actual)
            for dependencia in nodos[actual].get("deps", []):
                kinds = {dk.get("kind") for dk in dependencia.get("dep_kinds", [])}
                if kinds & tipos:
                    pila.append(dependencia["pkg"])
        return visto - {raiz}

    normales = alcance({None})
    con_construccion = alcance({None, "build"})

    def ordenadas(ids: set[str]) -> list[dict]:
        return sorted(
            (_entrada_crate(paquetes[i]) for i in ids if i in paquetes),
            key=lambda p: (p["nombre"].lower(), p["version"]),
        )

    return ordenadas(normales), ordenadas(con_construccion - normales)


def _crates_del_lockfile() -> list[dict]:
    """Paquetes de `Cargo.lock` que vienen de un registro: sin la raíz ni rutas locales."""
    if not CARGO_LOCK.exists():
        return []
    return [
        p for p in tomllib.loads(CARGO_LOCK.read_text(encoding="utf-8")).get("package", [])
        if p.get("source")
    ]


def _paquetes_rust() -> dict:
    """Crates del binario Tauri de Windows, con la licencia que cada una declara.

    La fuente buena es `cargo metadata --filter-platform`, que trae el campo
    `license` de cada `Cargo.toml` y limita el grafo a lo que el instalador de
    Windows compila. Si Cargo no puede resolverlo —falta la caché, falta el
    propio `cargo`— el respaldo es `Cargo.lock`, que fija nombre y versión pero
    NO licencias, y por eso el resultado se declara `licencias_verificadas:
    False`: un vacío en ese estado no distingue «sin licencia» de «no se miró».
    """
    base = {
        "plataforma": PLATAFORMA_RUST,
        "enlazadas": [],
        "solo_de_construccion": [],
        "licencias_verificadas": False,
        "otras_plataformas_en_lockfile": None,
    }
    if not CARGO_MANIFEST.exists():
        return {**base, "fuente": "no hay Cargo.toml: no hay nada que verificar"}

    error = ""
    proceso = None
    try:
        proceso = subprocess.run(
            ["cargo", "metadata", "--locked", "--offline", "--format-version", "1",
             "--filter-platform", PLATAFORMA_RUST,
             "--manifest-path", str(CARGO_MANIFEST)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if proceso.returncode != 0:
            error = (proceso.stderr or "").strip()[-300:]
    except OSError as exc:
        error = f"no se pudo ejecutar cargo: {exc}"

    if proceso is not None and proceso.returncode == 0:
        datos = json.loads(proceso.stdout)
        enlazadas, construccion = _clasificar_crates(datos)
        en_lock = len(_crates_del_lockfile())
        return {
            **base,
            "fuente": (
                "cargo metadata --locked --offline --filter-platform "
                f"{PLATAFORMA_RUST}: campo `license` de cada Cargo.toml"
            ),
            "enlazadas": enlazadas,
            "solo_de_construccion": construccion,
            "licencias_verificadas": True,
            # El producto va en `packages`; el resto del lockfile es de otras plataformas.
            "otras_plataformas_en_lockfile": max(
                0, en_lock + 1 - len(datos.get("packages", []))
            ) if en_lock else None,
        }

    # Respaldo: nombre y versión exactos, licencias desconocidas. NO se inventan.
    if not CARGO_LOCK.exists():
        raise SystemExit(f"No se pudo inventariar las crates de Rust:\n{error}")
    crates = sorted(
        (_entrada_crate(p) for p in _crates_del_lockfile()),
        key=lambda p: (p["nombre"].lower(), p["version"]),
    )
    return {
        **base,
        "plataforma": "sin filtrar (Cargo.lock)",
        "fuente": (
            "Cargo.lock: nombre y versión, SIN licencias ni filtro de plataforma "
            f"(cargo metadata no pudo resolver: {error or 'sin detalle'})"
        ),
        "enlazadas": crates,
    }


def _hash_de_archivo(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as manejador:
        for bloque in iter(lambda: manejador.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def _licencias_de_los_avisos(raiz: Path) -> dict[str, str]:
    """Componente → licencia, leída de la tabla de `THIRD_PARTY_NOTICES.md`.

    Es la declaración que el PRODUCTO ya publica a quien lo recibe; el SBOM la
    cita en vez de escribir una segunda copia que se pueda quedar vieja. No es la
    lectura de un archivo de licencia dentro de la herramienta: el SBOM lo dice.
    """
    ruta = raiz / "frontend" / "public" / "legal" / "THIRD_PARTY_NOTICES.md"
    if not ruta.is_file():
        return {}
    filas: dict[str, str] = {}
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        if not linea.lstrip().startswith("|"):
            continue
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        # Componente | Versión | Función | Licencia / estado | Fuente
        if len(celdas) >= 5 and celdas[0] and not set(celdas[0]) <= set("-: "):
            filas.setdefault(celdas[0], celdas[3])
    return filas


def _binarios(raiz: Path | None = None) -> tuple[list[dict], list[dict]]:
    """(presentes, ausentes): ejecutables de terceros del instalador, con su huella.

    EL FALLO QUE ARREGLA. La lista de candidatos se recorría con `if not
    existe: continue`: lo que no estuviera en el árbol donde se generaba el SBOM
    desaparecía sin decirlo. El archivo guardado declaraba 2 binarios (Vina y
    Open Babel) y `bundle_helper` empaqueta 4; nada distinguía «no viaja» de
    «no estaba aquí cuando se generó».

    Ahora se recorre la lista de lo que el instalador empaqueta
    (`bundle_helper.HERRAMIENTAS_EMPAQUETADAS`). Una herramienta crítica ausente
    aborta, igual que aborta el empaquetado; una opcional ausente se DECLARA.
    """
    raiz = raiz or ROOT
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    from bundle_helper import HERRAMIENTAS_CRITICAS

    avisos = _licencias_de_los_avisos(raiz)
    presentes: list[dict] = []
    ausentes: list[dict] = []
    for herramienta, (relativa, fila_de_avisos) in BINARIOS.items():
        ruta = raiz / relativa
        if not ruta.exists():
            if herramienta in HERRAMIENTAS_CRITICAS:
                raise SystemExit(
                    f"Falta {relativa}: `{herramienta}` es crítica y sin ella el "
                    "instalador no se construye, así que el SBOM no tiene qué declarar."
                )
            ausentes.append({
                "herramienta": herramienta,
                "ejecutable_esperado": relativa,
                "consecuencia": (
                    "no viaja en un instalador construido desde este árbol: "
                    "`bundle_helper` la trata como opcional"
                ),
            })
            continue
        entrada = {
            "nombre": ruta.name,
            "ruta": relativa,
            "bytes": ruta.stat().st_size,
            "sha256": _hash_de_archivo(ruta),
        }
        if herramienta == "vina" and (raiz / "tools/vina/vina-trace-manifest.json").is_file():
            trace = json.loads((raiz / "tools/vina/vina-trace-manifest.json").read_text(encoding="utf-8"))
            companion = raiz / "tools/vina/vina_trace.exe"
            entrada["instrumentacion"] = {"ruta": "tools/vina/vina_trace.exe",
                "sha256": _hash_de_archivo(companion), "bytes": companion.stat().st_size,
                "licencia": trace["license"], "fuente_commit": trace["upstream_commit"],
                "compilador": trace["compiler"], "dependencias_estaticas": trace.get("static_dependencies", []),
                "textos_licencias": trace.get("licenses", {})}
        if herramienta == "openbabel":
            # Open Babel lleva un manifiesto propio con licencia y procedencia
            # verificada. Se lee de ahí en vez de repetirlo: una segunda copia de
            # la licencia es una segunda copia que se puede quedar vieja.
            manifiesto = json.loads(
                (raiz / "tools" / "openbabel" / "openbabel-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            entrada.update({
                "programa": manifiesto["programa"],
                "version": manifiesto["version_paquete"],
                "licencia": manifiesto["licencia_spdx"],
                "licencia_origen": "tools/openbabel/openbabel-manifest.json",
                "invocacion": "subproceso CLI (programa independiente)",
                "procedencia": manifiesto["procedencia"],
            })
        elif herramienta == "molcy":
            # El motor Molcy es un PROGRAMA PROPIO bajo GPL-3.0-or-later (se ejecuta dentro de Blender y usa bpy y Molecular
            # Nodes, ambos GPL-3.0-or-later). No es un binario: son scripts y una plantilla de arte, con un manifiesto de
            # SHA-256 por fichero y el commit del que salen. Se lee de ahí en vez de repetirlo.
            manifiesto = json.loads(
                (raiz / "tools" / "molcy" / "molcy-manifest.json").read_text(encoding="utf-8")
            )
            entrada.update({
                "programa": manifiesto["programa"],
                "version": manifiesto["fuente"]["commit"][:12],
                "licencia": manifiesto["licencia_spdx"],
                "licencia_origen": "tools/molcy/molcy-manifest.json",
                "invocacion": ("subproceso (vídeo: PowerShell → Blender -b --python maestro.py; fotos: Python → correr_foto.py → "
                               "Blender); programa independiente"),
                "procedencia": manifiesto["fuente"],
                "ficheros": len(manifiesto["archivos"]),
                "sha256_conjunto": manifiesto["sha256_conjunto"],
            })
        elif herramienta == "molchat":
            # El sidecar MolChat es un PROGRAMA PROPIO bajo GPL-3.0-or-later
            # (servicio Python en loopback + UI estática, sin enlazar con el
            # producto). Como el motor Molcy, se lee de su manifiesto en vez
            # de repetirlo. Opcional en runtime: si falta, queda DECLARADO
            # ausente en vez de abortar (no está en HERRAMIENTAS_CRITICAS).
            manifiesto = json.loads(
                (raiz / "tools" / "molchat" / "molchat-manifest.json").read_text(encoding="utf-8")
            )
            entrada.update({
                "programa": manifiesto["programa"],
                "version": manifiesto["version"],
                "licencia": manifiesto["licencia_spdx"],
                "licencia_origen": "tools/molchat/molchat-manifest.json",
                "invocacion": ("subproceso Python con bootstrap de src vendorizado "
                               "en loopback; programa independiente"),
                "procedencia": manifiesto["fuente"],
                "ficheros": len(manifiesto["archivos"]),
                "sha256_conjunto": manifiesto["sha256_conjunto"],
            })
        else:
            licencia = avisos.get(fila_de_avisos or "", "")
            entrada["licencia"] = licencia
            entrada["licencia_origen"] = (
                "frontend/public/legal/THIRD_PARTY_NOTICES.md (declaración del producto; "
                f"no hay archivo de licencia dentro de tools/{herramienta}/)"
                if licencia
                else "sin declarar en THIRD_PARTY_NOTICES.md"
            )
        presentes.append(entrada)
    return presentes, ausentes


# ── Lo que está instalado para construir pero NO se distribuye ───────────
#
# El SBOM describe el runtime que recibe el investigador. `openbabel-wheel`
# sigue instalado en `python-embed` porque es la FUENTE de la que
# `stage_openbabel_tool.py` saca `obabel.exe`, pero `bundle_helper.py` lo
# excluye del instalador: sus bindings de Python no viajan.
#
# Declararlo entre los paquetes distribuidos afirmaría que el investigador
# recibe una biblioteca GPL enlazable dentro de su intérprete, y eso ya no es
# cierto. Se mueve a `dependencias_de_construccion`, con el motivo escrito, y el
# programa aparece en `binarios` — que es donde de verdad está.
PAQUETES_SOLO_DE_CONSTRUCCION = {
    "openbabel-wheel": (
        "Fuente del binario `obabel.exe`. Sus bindings de Python se excluyen "
        "del runtime empaquetado (`bundle_helper.OPENBABEL_BINDINGS_DIRS`); "
        "Open Babel se distribuye como programa independiente GPL-2.0-only en "
        "`tools/openbabel/` y se invoca por subproceso. Ver "
        "`docs/79_ADR_FRONTERA_OPEN_BABEL.md`."
    ),
}


def _particionar_construccion(paquetes: list[dict]) -> tuple[list[dict], list[dict]]:
    """(distribuidos, sólo-de-construcción), comparando por nombre normalizado."""
    claves = {n.lower().replace("_", "-") for n in PAQUETES_SOLO_DE_CONSTRUCCION}
    distribuidos: list[dict] = []
    construccion: list[dict] = []
    for paquete in paquetes:
        nombre = (paquete.get("nombre") or "").lower().replace("_", "-")
        if nombre in claves:
            construccion.append(
                {**paquete, "motivo": PAQUETES_SOLO_DE_CONSTRUCCION[nombre]}
            )
        else:
            distribuidos.append(paquete)
    return distribuidos, construccion


def _a_revisar(paquetes: list[dict]) -> list[dict]:
    marcas = tuple(m.upper() for m in LICENCIAS_A_REVISAR)
    return [
        p for p in paquetes
        if any(marca in _normalizar_licencia(p.get("licencia") or "") for marca in marcas)
    ]


# ── Licencias resueltas LEYENDO EL PAQUETE, no la metadata ──────────────
#
# Un paquete puede distribuir su licencia como archivo y dejar la metadata
# vacía. El campo vacío entonces no significa «no tiene licencia»: significa
# que el empaquetador no la puso donde `importlib.metadata` la busca.
#
# Cada entrada aquí se resolvió ABRIENDO el archivo que viaja dentro del
# paquete distribuido, en esta misma máquina, el 2026-09-06. La columna de
# evidencia dice qué se leyó, para que la afirmación se pueda comprobar sin
# volver a confiar en quien la escribió.
LICENCIAS_RESUELTAS: dict[str, tuple[str, str]] = {
    # nombre: (SPDX, evidencia)
    "descriptastorus": (
        "BSD-3-Clause",
        "descriptastorus-2.8.0.dist-info/LICENSE: tres cláusulas BSD "
        "(fuente, binario y no-endoso), © Novartis Institutes for BioMedical Research",
    ),
    "llvmlite": (
        "BSD-2-Clause",
        "llvmlite-0.47.0.dist-info/LICENSE: dos cláusulas BSD, sin la de "
        "no-endoso, © Anaconda Inc.",
    ),
    "mhfp": (
        "MIT",
        "el LICENSE del paquete abre con «MIT License», © 2018 Reymond Group, "
        "Universität Bern",
    ),
    "kiwisolver": (
        "BSD-3-Clause",
        "kiwisolver-1.5.0.dist-info/licenses/LICENSE: «Modified BSD License (also known as "
        "New or Revised BSD)», tres cláusulas, © 2013-2026 Nucleic Development Team. Su "
        "metadata `License` trae el texto entero, y su primera línea es sólo «=»",
    ),
    "MDAnalysis": (
        "LGPL-3.0-or-later",
        "mdanalysis-2.10.0.dist-info/licenses/LICENSE: «The MDAnalysis library is "
        "packaged under the terms of the GNU Lesser General Public License version 3 "
        "or any later version (LGPLv3+)»; partes del código, bajo LGPL-2.1-or-later. "
        "Su metadata `License` trae el texto entero, y su primera línea es sólo «=»",
    ),
    "tabpfn": (
        "LicenseRef-PriorLabs-1.2",
        "tabpfn-8.0.8.dist-info/licenses/LICENSE: «Prior Labs License (Apache 2.0 "
        "with ADDITIONAL PROVISION), Version 1.2, Dec 2025». NO es Apache-2.0 a "
        "secas: la provisión añadida exige atribución de producto",
    ),
    "eve-raphael": (
        "Apache-2.0",
        "node_modules/eve-raphael/LICENSE: texto íntegro de Apache License 2.0",
    ),
    "webgl-constants": (
        "MIT",
        "node_modules/webgl-constants/LICENSE: «MIT License», © 2019 Tim van Scherpenzeel",
    ),
    "text-encoding-utf-8": (
        "Unlicense",
        "node_modules/text-encoding-utf-8/LICENSE.md: «released into the public "
        "domain»; los índices derivan del Encoding Standard de WHATWG",
    ),
    # ── Los que usan la forma HEREDADA `licenses`, que npm no copia al lock ──
    #
    # `_licencia_npm` ya sabe leer esa forma, pero el SBOM se construye desde
    # `package-lock.json`, y npm sencillamente NO registra ahí el campo cuando
    # el paquete usa la forma antigua. Se lee entonces del `package.json`
    # instalado, que es el archivo que de verdad viaja.
    #
    # `busboy` y `streamsearch` estaban aquí y salieron del lockfile: el informe
    # afirmaba haber resuelto paquetes que ya no se distribuyen. Si vuelven,
    # habrá que volver a leer sus archivos; no se conserva una lectura vieja.
    "eyes": (
        "MIT",
        "node_modules/eyes/package.json declara `licenses: ['MIT']` y trae su "
        "LICENSE; npm no copia ese campo al lockfile",
    ),
    "asap": (
        "MIT",
        "dos entradas en el lockfile: 2.0.6 declara MIT y 1.0.0 —anidada bajo "
        "font-face-observer— usa la forma heredada `licenses: [{type: MIT}]`, "
        "con su LICENSE.md, © 2009–2013 Contributors",
    ),
}


def _resolver(paquetes: list[dict]) -> list[dict]:
    """Rellena las licencias que la metadata calla y el paquete sí declara."""
    salida = []
    for paquete in paquetes:
        copia = dict(paquete)
        # Una «licencia» sin letras ni cifras es el adorno con que empieza un texto de
        # licencia copiado en la metadata (MDAnalysis abre con una línea de «=»): no
        # dice nada y no puede pasar por declarada.
        if not any(c.isalnum() for c in (copia.get("licencia") or "")):
            resuelta = LICENCIAS_RESUELTAS.get(copia["nombre"])
            if resuelta:
                copia["licencia"] = resuelta[0]
                copia["licencia_origen"] = "archivo del paquete"
                copia["licencia_evidencia"] = resuelta[1]
        salida.append(copia)
    return salida


def _sin_licencia(paquetes: list[dict]) -> list[dict]:
    """Un campo vacío no es «permisiva»: es que nadie lo ha mirado.

    Lo que quede aquí después de `_resolver` es lo que de verdad no declara
    licencia en ninguna parte del paquete distribuido, y exige mirar aguas
    arriba antes de redistribuirlo.
    """
    return [p for p in paquetes if not any(c.isalnum() for c in (p.get("licencia") or ""))]


def _resueltas_por_evidencia(*listas: list[dict]) -> dict[str, dict]:
    """Sólo las licencias que se aplicaron a un paquete que de verdad se distribuye.

    El diccionario `LICENCIAS_RESUELTAS` es conocimiento acumulado; el informe es
    una afirmación sobre ESTE inventario. Volcarlo entero declaraba resueltos
    paquetes que ya habían salido del lockfile.
    """
    resumen: dict[str, dict] = {}
    for lista in listas:
        for paquete in lista:
            if paquete.get("licencia_origen") != "archivo del paquete":
                continue
            resumen[paquete["nombre"]] = {
                "licencia": paquete["licencia"],
                "evidencia": paquete.get("licencia_evidencia", ""),
            }
    return dict(sorted(resumen.items()))


def _cobertura(
    *,
    python: list[dict],
    npm: list[dict],
    rust: list[dict],
    binarios: list[dict],
    rust_verificado: bool,
) -> dict:
    """¿Se puede sostener una afirmación GLOBAL sobre las licencias distribuidas?

    Una lista vacía en `sin_licencia_declarada` sólo dice algo si esa lista se
    construyó. Rust no tenía lista y `rust: 0` se leía como «sin riesgo» cuando
    era «sin mirar». La cobertura es completa únicamente si ningún ecosistema
    deja componentes sin licencia Y las licencias de Rust se leyeron de verdad.
    """
    sin = {
        "python": len(_sin_licencia(python)),
        "npm": len(_sin_licencia(npm)),
        "rust": len(_sin_licencia(rust)),
        "binarios": len(_sin_licencia(binarios)),
    }
    return {
        "criterio": (
            "Una afirmación global sobre licencias (p. ej. «ninguna dependencia "
            "declara AGPL ni SSPL») sólo es sostenible si ningún componente "
            "distribuido queda sin licencia y las de Rust se leyeron de `cargo "
            "metadata`. `generate_sbom.py --check` falla si `completa` es false."
        ),
        "python": {"componentes": len(python), "sin_licencia": sin["python"]},
        "npm": {"componentes": len(npm), "sin_licencia": sin["npm"]},
        "rust": {
            "componentes": len(rust),
            "sin_licencia": sin["rust"],
            "estado": (
                "licencias leídas de cargo metadata"
                if rust_verificado
                else "no verificado: cargo metadata no pudo resolver; el vacío no "
                     "distingue «sin licencia» de «no se miró»"
            ),
        },
        "binarios": {"componentes": len(binarios), "sin_licencia": sin["binarios"]},
        "completa": rust_verificado and not any(sin.values()),
    }


def _con_nota(componentes: list[dict]) -> list[dict]:
    return [
        {**p, "nota": SIN_RESOLVER.get(p["nombre"], "sin nota")}
        for p in _sin_licencia(componentes)
    ]


def _construir() -> dict:
    python_instalado = _resolver(_paquetes_python())
    python, solo_construccion = _particionar_construccion(python_instalado)
    npm = _resolver(_paquetes_npm())
    inventario_rust = _paquetes_rust()
    rust = inventario_rust["enlazadas"]
    binarios, binarios_ausentes = _binarios()
    return {
        "alcance": (
            "Runtime distribuido: python-embed + dependencias JS bloqueadas + "
            "crates Rust del binario de Windows + binarios de terceros "
            "empaquetados. NO es el entorno del desarrollador."
        ),
        "no_cubre": [
            "Análisis de vulnerabilidades: exige una base de datos actualizada "
            "(OSV/GitHub Advisories) y por tanto red y una decisión de servicio.",
            "Dependencias de desarrollo (dev) del frontend: no se distribuyen.",
            "Rust: la licencia es la expresión SPDX que cada crate DECLARA en su "
            "Cargo.toml. No se leyeron los textos de licencia ni el código "
            "vendorizado de las crates; una medición puntual de esos textos está "
            "en `docs/86_CORRECCIONES_AUDITORIA_LUNA_20261002.md`.",
            "Binarios: sólo se inventaría el ejecutable principal de cada "
            "herramienta de `tools/`. El directorio viaja ENTERO (DLL de ggml, "
            "Vina-GPU, utilidades de llama.cpp, DLL de xTB) y esos archivos "
            "auxiliares no se listan uno a uno (`docs/80_INVENTARIO_TECNOLOGICO_"
            "INTEGRAL.md`, §4). La licencia de vina, xtb y llama es la que el "
            "producto declara en THIRD_PARTY_NOTICES.md, no la lectura de un "
            "archivo de licencia dentro de `tools/`.",
        ],
        "dependencias_de_construccion": {
            "criterio": (
                "Instaladas en `python-embed` para construir el producto pero "
                "EXCLUIDAS del instalador, y crates de Cargo alcanzadas sólo por "
                "`build-dependencies`. No las recibe el investigador, así que "
                "declararlas entre lo distribuido afirmaría algo falso sobre lo "
                "que se le entrega."
            ),
            "python": solo_construccion,
            "rust": inventario_rust["solo_de_construccion"],
        },
        "python_embed": {"total": len(python), "paquetes": python},
        "npm_produccion": {"total": len(npm), "paquetes": npm},
        "rust_produccion": {
            "criterio": (
                "Crates que el binario Tauri de la plataforma indicada enlaza por "
                "dependencias normales, sin el propio producto. Las del Cargo.lock "
                "que sólo se compilan para otras plataformas no viajan y no se "
                "listan; se cuentan en `otras_plataformas_en_lockfile`."
            ),
            "plataforma": inventario_rust["plataforma"],
            "fuente": inventario_rust["fuente"],
            "licencias_verificadas": inventario_rust["licencias_verificadas"],
            "otras_plataformas_en_lockfile": inventario_rust["otras_plataformas_en_lockfile"],
            "total": len(rust),
            "paquetes": rust,
        },
        "binarios": binarios,
        "binarios_ausentes": {
            "criterio": (
                "Herramientas que `bundle_helper` empaqueta si existen y que no "
                "estaban en el árbol donde se generó este SBOM. Declararlas evita "
                "que «no viaja» y «no estaba aquí» se confundan."
            ),
            "herramientas": binarios_ausentes,
        },
        "licencias_a_revisar": {
            "criterio": list(LICENCIAS_A_REVISAR),
            "python": _a_revisar(python),
            "npm": _a_revisar(npm),
            "rust": _a_revisar(rust),
            # ── POR QUÉ LOS BINARIOS TAMBIÉN SE REVISAN ──────────────────
            #
            # Este párrafo del inventario decía «no hay GPL» y era falso: el
            # detector buscaba la subcadena "GPL" y `openbabel-wheel` declara
            # "GNU GENERAL PUBLIC LICENSE", donde no aparece. Se normalizó el
            # nombre y el gate volvió a ver el componente.
            #
            # Ahora Open Babel ya no es un paquete Python distribuido —viaja
            # como programa independiente— y sin esta línea el gate volvería a
            # quedarse verde con un componente GPL dentro del instalador, por
            # una razón distinta y con el mismo resultado. Que un binario se
            # invoque por subproceso puede cambiar sus obligaciones; no las
            # borra, y desde luego no borra la de mirarlo.
            "binarios": _a_revisar(binarios),
        },
        "licencias_resueltas_por_evidencia": {
            "criterio": (
                "Licencia leída del archivo que viaja DENTRO del paquete "
                "distribuido, no de su metadata. Cada una dice qué se leyó. Sólo "
                "figuran las aplicadas a un paquete de este inventario."
            ),
            "paquetes": _resueltas_por_evidencia(python, npm),
        },
        "sin_licencia_declarada": {
            "criterio": "El componente no declara licencia NI en su metadata NI en "
                        "un archivo dentro del propio paquete NI en los avisos del "
                        "producto. Lo que sólo faltaba en la metadata está "
                        "resuelto en `licencias_resueltas_por_evidencia`, con lo "
                        "que se leyó. Lo que queda aquí exige mirar aguas arriba "
                        "antes de redistribuirlo, y debe estar VACÍO para release: "
                        "`--check` falla si no lo está. Cada ecosistema tiene su "
                        "lista —Rust y los binarios la tenían ausente, y un `0` "
                        "sin lista no distingue «sin riesgo» de «sin mirar»—.",
            "python": _con_nota(python),
            "npm": _con_nota(npm),
            "rust": _con_nota(rust),
            "binarios": _con_nota(binarios),
        },
        "cobertura_de_licencias": _cobertura(
            python=python,
            npm=npm,
            rust=rust,
            binarios=binarios,
            rust_verificado=inventario_rust["licencias_verificadas"],
        ),
    }


def _informar_cobertura(sbom: dict) -> None:
    """Dice a stderr qué componentes impiden una afirmación global de licencias."""
    cobertura = sbom["cobertura_de_licencias"]
    print(
        "SBOM con componentes sin licencia comprobada: la cobertura de licencias "
        "NO es completa y ninguna afirmación global («no hay AGPL ni SSPL») se "
        "sostiene mientras tanto.",
        file=sys.stderr,
    )
    for ecosistema in ("python", "npm", "rust", "binarios"):
        parte = cobertura[ecosistema]
        if parte["sin_licencia"]:
            print(f"  - {ecosistema}: {parte['sin_licencia']} sin licencia", file=sys.stderr)
    if not sbom["rust_produccion"].get("licencias_verificadas", True):
        print(f"  - rust: {cobertura['rust']['estado']}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--write", action="store_true")
    grupo.add_argument("--check", action="store_true")
    parser.add_argument(
        "--permitir-runtime-ausente",
        action="store_true",
        help=(
            "no fallar si `python-embed/` no esta presente. El SBOM describe el "
            "runtime que se distribuye, y ese runtime no viaja en el repositorio "
            "Git: se descarga aparte. Sobre un clon limpio el gate no puede "
            "comprobar nada, y con esta bandera lo dice en vez de reventar. Se "
            "pasa explicitamente desde CI."
        ),
    )
    args = parser.parse_args()

    if args.check and args.permitir_runtime_ausente and not PYTHON_EMBED.exists():
        # No decimos "verificado". El SBOM sigue sin comprobarse.
        print(
            "SBOM NO verificado: `python-embed/` no esta presente, y el SBOM "
            "describe exactamente ese runtime. Las licencias del runtime "
            "distribuido quedan sin comprobar en este clon."
        )
        return 0

    sbom = _construir()
    texto = json.dumps(sbom, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    if args.check:
        if not SALIDA.exists():
            print("No hay SBOM. Ejecuta --write.", file=sys.stderr)
            return 1
        if SALIDA.read_text(encoding="utf-8") != texto:
            print(
                "SBOM desactualizado: el runtime cambió desde la última "
                "generación. Ejecuta --write y revisa el diff.",
                file=sys.stderr,
            )
            return 1
        # Que el archivo guardado coincida con el generado no basta: un inventario
        # idéntico y con huecos sigue teniendo huecos.
        if not sbom["cobertura_de_licencias"]["completa"]:
            _informar_cobertura(sbom)
            return 1
        ausentes = sbom.get("binarios_ausentes", {}).get("herramientas", [])
        print(
            f"SBOM verificado: {sbom['python_embed']['total']} paquetes Python, "
            f"{sbom['npm_produccion']['total']} npm, {sbom['rust_produccion']['total']} Rust, "
            f"{len(sbom['binarios'])} binarios"
            + (
                f" ({len(ausentes)} opcional(es) ausente(s): "
                + ", ".join(a["herramienta"] for a in ausentes) + ")"
                if ausentes else ""
            )
            + "; "
            f"{len(sbom['dependencias_de_construccion']['python'])} paquete(s) Python "
            "sólo de construcción, excluidos del instalador; cobertura de licencias completa"
        )
        return 0

    if args.write:
        SALIDA.parent.mkdir(parents=True, exist_ok=True)
        SALIDA.write_text(texto, encoding="utf-8")
        print(f"Generado: {SALIDA.relative_to(ROOT)}")
        print(f"  python-embed: {sbom['python_embed']['total']} paquetes")
        print(f"  npm (producción): {sbom['npm_produccion']['total']} paquetes")
        rust = sbom["rust_produccion"]
        print(
            f"  Rust (producción): {rust['total']} crates "
            f"[{rust['plataforma']}; licencias verificadas: {rust['licencias_verificadas']}]"
        )
        print(f"  binarios de terceros: {len(sbom['binarios'])}")
        for ausente in sbom.get("binarios_ausentes", {}).get("herramientas", []):
            print(f"     ausente (opcional): {ausente['herramienta']}")
        a_revisar = sbom["licencias_a_revisar"]
        cuantas = (
            len(a_revisar["python"])
            + len(a_revisar["npm"])
            + len(a_revisar["rust"])
            + len(a_revisar["binarios"])
        )
        if cuantas:
            # Sin emoji: la consola de Windows usa cp1252 y un carácter fuera
            # de esa tabla convierte un aviso en un traceback.
            print(f"  AVISO: licencias que hay que mirar: {cuantas}")
            for p in (
                *a_revisar["python"],
                *a_revisar["npm"],
                *a_revisar["rust"],
                *a_revisar["binarios"],
            ):
                print(
                    f"     - {p['nombre']} {p.get('version', '')}: {p['licencia']}"
                )
        if not sbom["cobertura_de_licencias"]["completa"]:
            _informar_cobertura(sbom)
            return 1
        return 0

    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
