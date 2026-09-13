"""SBOM del runtime que se distribuye, y sus licencias.

Gate de release. Antes de firmar y publicar hay que poder contestar tres
preguntas sin abrir una consola: qué se distribuye, bajo qué licencia, y con qué
huella. Las tres se contestaban a mano, que es como se contestan mal.

Alcance **deliberadamente estrecho**: el intérprete embebido
(`python-embed`), que es el que viaja en el instalador, más las dependencias
JavaScript bloqueadas del frontend. No inventa el árbol del desarrollador: en
esta máquina hay 281 distribuciones Python instaladas y sólo 170 se distribuyen.
Un SBOM que declare las 281 es peor que ninguno, porque afirma algo falso sobre
lo que el investigador recibe.

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



def _paquetes_rust() -> list[dict]:
    """Crates que Cargo resolverá para el binario Tauri, usando sólo el lockfile."""
    if not CARGO_MANIFEST.exists():
        return []
    proceso = subprocess.run(
        ["cargo", "metadata", "--locked", "--offline", "--format-version", "1",
         "--manifest-path", str(CARGO_MANIFEST)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proceso.returncode == 0:
        datos = json.loads(proceso.stdout)
        origen = datos.get("packages", [])
    else:
        # Cargo metadata necesita tener todas las crates en caché aun con --offline.
        # Cargo.lock sigue siendo una fuente exacta de nombre/versión para el SBOM;
        # la licencia vacía queda marcada para revisión en vez de inventarse.
        if not CARGO_LOCK.exists():
            raise SystemExit(f"No se pudo inventariar Cargo.lock offline:\n{proceso.stderr[-1500:]}")
        origen = tomllib.loads(CARGO_LOCK.read_text(encoding="utf-8")).get("package", [])
    paquetes = [
        {
            "nombre": paquete.get("name", ""),
            "version": paquete.get("version", ""),
            "licencia": paquete.get("license") or "",
            "fuente": paquete.get("repository") or paquete.get("source") or "",
        }
        for paquete in origen
    ]
    return sorted(paquetes, key=lambda p: (p["nombre"].lower(), p["version"]))

def _binarios() -> list[dict]:
    """Ejecutables de terceros que viajan en el instalador, con su huella."""
    candidatos = [
        ROOT / "tools" / "vina" / "vina.exe",
        ROOT / "tools" / "xtb" / "xtb.exe",
        ROOT / "tools" / "llama" / "llama-server.exe",
        ROOT / "tools" / "smina" / "smina.exe",
        ROOT / "tools" / "openbabel" / "bin" / "obabel.exe",
    ]
    salida = []
    for ruta in candidatos:
        if not ruta.exists():
            continue
        digest = hashlib.sha256(ruta.read_bytes()).hexdigest()
        entrada = {
            "nombre": ruta.name,
            "ruta": str(ruta.relative_to(ROOT)).replace("\\", "/"),
            "bytes": ruta.stat().st_size,
            "sha256": digest,
        }
        # Open Babel lleva un manifiesto propio con licencia y procedencia
        # verificada. Se lee de ahí en vez de repetirlo: una segunda copia de
        # la licencia es una segunda copia que se puede quedar vieja.
        if ruta.name == "obabel.exe":
            manifiesto = json.loads(
                (ROOT / "tools" / "openbabel" / "openbabel-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            entrada.update({
                "programa": manifiesto["programa"],
                "version": manifiesto["version_paquete"],
                "licencia": manifiesto["licencia_spdx"],
                "invocacion": "subproceso CLI (programa independiente)",
                "procedencia": manifiesto["procedencia"],
            })
        salida.append(entrada)
    return salida


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
    "busboy": (
        "MIT",
        "node_modules/busboy/package.json declara `licenses: [{type: MIT}]` "
        "(forma heredada) y trae su LICENSE; npm no copia ese campo al lockfile",
    ),
    "eyes": (
        "MIT",
        "node_modules/eyes/package.json declara `licenses: ['MIT']` y trae su "
        "LICENSE; npm no copia ese campo al lockfile",
    ),
    "streamsearch": (
        "MIT",
        "node_modules/streamsearch/package.json declara `licenses: [{type: MIT}]` "
        "y trae su LICENSE; npm no copia ese campo al lockfile",
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
        if not (copia.get("licencia") or "").strip():
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
    return [p for p in paquetes if not (p.get("licencia") or "").strip()]


def _construir() -> dict:
    python_instalado = _resolver(_paquetes_python())
    python, solo_construccion = _particionar_construccion(python_instalado)
    npm = _resolver(_paquetes_npm())
    rust = _paquetes_rust()
    return {
        "alcance": (
            "Runtime distribuido: python-embed + dependencias JS bloqueadas + "
            "binarios de terceros empaquetados. NO es el entorno del desarrollador."
        ),
        "no_cubre": [
            "Análisis de vulnerabilidades: exige una base de datos actualizada "
            "(OSV/GitHub Advisories) y por tanto red y una decisión de servicio.",
            "Dependencias de desarrollo (dev) del frontend: no se distribuyen.",
            "Si faltan crates en la caché offline, Cargo.lock fija nombre y versión; "
            "las licencias Rust vacías requieren revisión con cargo metadata completo.",
        ],
        "dependencias_de_construccion": {
            "criterio": (
                "Instaladas en `python-embed` para construir el producto pero "
                "EXCLUIDAS del instalador. No las recibe el investigador, así que "
                "declararlas entre lo distribuido afirmaría algo falso sobre lo "
                "que se le entrega."
            ),
            "python": solo_construccion,
        },
        "python_embed": {"total": len(python), "paquetes": python},
        "npm_produccion": {"total": len(npm), "paquetes": npm},
        "rust_produccion": {"total": len(rust), "paquetes": rust},
        "binarios": _binarios(),
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
            "binarios": _a_revisar(_binarios()),
        },
        "licencias_resueltas_por_evidencia": {
            "criterio": (
                "Licencia leída del archivo que viaja DENTRO del paquete "
                "distribuido, no de su metadata. Cada una dice qué se leyó."
            ),
            "paquetes": {
                nombre: {"licencia": spdx, "evidencia": evidencia}
                for nombre, (spdx, evidencia) in sorted(LICENCIAS_RESUELTAS.items())
            },
        },
        "sin_licencia_declarada": {
            "criterio": "El paquete no declara licencia NI en su metadata NI en "
                        "un archivo dentro del propio paquete. Lo que sólo "
                        "faltaba en la metadata está resuelto en "
                        "`licencias_resueltas_por_evidencia`, con lo que se "
                        "leyó. Lo que queda aquí exige mirar aguas arriba antes "
                        "de redistribuirlo. Rust queda fuera: la caché offline "
                        "de Cargo no trae el campo para ninguna crate, así que "
                        "su vacío no distingue nada (ver `no_cubre`).",
            "python": [
                {**p, "nota": SIN_RESOLVER.get(p["nombre"], "sin nota")}
                for p in _sin_licencia(python)
            ],
            "npm": [
                {**p, "nota": SIN_RESOLVER.get(p["nombre"], "sin nota")}
                for p in _sin_licencia(npm)
            ],
        },
    }


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
        print(
            f"SBOM verificado: {sbom['python_embed']['total']} paquetes Python, "
            f"{sbom['npm_produccion']['total']} npm, {sbom['rust_produccion']['total']} Rust, "
            f"{len(sbom['binarios'])} binarios; "
            f"{len(sbom['dependencias_de_construccion']['python'])} paquete(s) "
            "sólo de construcción, excluidos del instalador"
        )
        return 0

    if args.write:
        SALIDA.parent.mkdir(parents=True, exist_ok=True)
        SALIDA.write_text(texto, encoding="utf-8")
        print(f"Generado: {SALIDA.relative_to(ROOT)}")
        print(f"  python-embed: {sbom['python_embed']['total']} paquetes")
        print(f"  npm (producción): {sbom['npm_produccion']['total']} paquetes")
        print(f"  Rust (producción): {sbom['rust_produccion']['total']} crates")
        print(f"  binarios de terceros: {len(sbom['binarios'])}")
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
        return 0

    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
