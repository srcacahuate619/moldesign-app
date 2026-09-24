#!/usr/bin/env python3
r"""validar_sellos.py — que los experimentos sellados se puedan comprobar desde un clon.

# El problema, medido el 2026-09-23

En un clon limpio del repositorio (Git para Windows, `core.autocrlf=true`)
sólo validaban **12 de 167** experimentos sellados. En la máquina del mantenedor
validaban casi todos. Tres causas, ninguna científica:

1. **Fin de línea.** Muchos activos sellados viven fuera de
   `scripts/artifacts_science/` sin el atributo `-text`: al desprotegerlos, git
   los reescribe con CRLF y su SHA-256 ya no es el sellado.
2. **Ficheros que no viajan.** PDBBind (su licencia no permite redistribuirlo),
   el runtime que aprovisiona `bootstrap_dev_tree.py`, datasets derivados.
   `experiment_manifest.py validate` no distingue «no distribuido» de «roto».
3. **Activos que cambiaron después del sello** (módulos vivos sellados; ver la
   regla 4 del programa experimental). Ésos fallaban también en local.

# Qué hace

Recorre todos los manifiestos con las mismas funciones que
`scripts/experiment_manifest.py` —que no se modifica: está sellado como activo en
26 experimentos— y clasifica cada fichero sellado:

    VERIFICADO        presente y con el hash sellado
    NO_DISTRIBUIDO    ausente y declarado en scripts/sellos_no_distribuidos.json
    DISTINTO          presente con otro hash                     → fallo
    AUSENTE           ausente y no declarado                     → fallo

`--check` sale con 1 si hay algún fallo o un manifiesto no pasa el esquema.
`--gitattributes` regenera, en `.gitattributes`, el bloque de activos sellados
de texto fuera de `artifacts_science/` que tienen que viajar sin conversión.

    python scripts/validar_sellos.py --check [--detalle]
    python scripts/validar_sellos.py --gitattributes
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ARTEFACTOS = RAIZ / "scripts" / "artifacts_science"
TABLA = RAIZ / "scripts" / "sellos_no_distribuidos.json"
GITATTRIBUTES = RAIZ / ".gitattributes"
CAMPOS = ("dataset_hashes", "model_hashes", "binary_hashes", "assets_hashes")
INICIO = "# >>> activos sellados sin conversión de fin de línea (scripts/validar_sellos.py --gitattributes)"
FIN = "# <<< activos sellados"


def _cargar_manifest_tool():
    ruta = RAIZ / "scripts" / "experiment_manifest.py"
    spec = importlib.util.spec_from_file_location("experiment_manifest", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _no_distribuido(tabla: list[dict], experimento: str, ruta: str) -> dict | None:
    for e in tabla:
        if ruta.startswith(e["prefijo"]) and experimento in e.get("experimentos", [experimento]):
            return e
    return None


def revisar(detalle: bool = False) -> tuple[Counter, dict]:
    em = _cargar_manifest_tool()
    tabla = json.loads(TABLA.read_text(encoding="utf-8"))["entradas"]
    esquema = em._load_schema()
    base = em._git_toplevel()
    totales: Counter = Counter()
    fallos: dict = defaultdict(list)
    no_distribuidos: Counter = Counter()
    for manifest_path in sorted(ARTEFACTOS.glob("*/manifest.json")):
        exp = manifest_path.parent.name
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        errores: list[str] = []
        em._validate(manifest, esquema, "$", errores)
        for e in errores:
            fallos[exp].append(f"ESQUEMA: {e}")
        if not manifest.get("sealed"):
            totales["sin_sellar"] += 1
            continue
        totales["sellados"] += 1
        for campo in CAMPOS:
            for guardada, esperado in (manifest.get(campo) or {}).items():
                resuelta = em._resolve_stored_path(guardada, base)
                if not Path(resuelta).is_file():
                    entrada = _no_distribuido(tabla, exp, guardada)
                    if entrada:
                        totales["NO_DISTRIBUIDO"] += 1
                        no_distribuidos[entrada["clase"]] += 1
                    else:
                        totales["AUSENTE"] += 1
                        fallos[exp].append(f"AUSENTE: {guardada}")
                    continue
                if em._sha256_file(resuelta) == esperado:
                    totales["VERIFICADO"] += 1
                else:
                    totales["DISTINTO"] += 1
                    fallos[exp].append(f"DISTINTO: {guardada}")
    return totales, {"fallos": dict(fallos), "no_distribuidos": dict(no_distribuidos)}


def _activos_de_texto_fuera() -> list[str]:
    """Rutas selladas y versionadas que no cubre `scripts/artifacts_science/** -text`.

    Declarar `-text` un binario es inocuo, así que no se distingue.
    """
    rastreadas = set(subprocess.run(["git", "-C", str(RAIZ), "ls-files"], capture_output=True, text=True,
                                    encoding="utf-8").stdout.splitlines())
    rutas = set()
    for manifest_path in ARTEFACTOS.glob("*/manifest.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for campo in CAMPOS:
            for guardada in manifest.get(campo) or {}:
                r = guardada.replace("\\", "/")
                if r in rastreadas and not r.startswith("scripts/artifacts_science/"):
                    rutas.add(r)
    return sorted(rutas)


def escribir_gitattributes() -> int:
    rutas = _activos_de_texto_fuera()
    bruto = GITATTRIBUTES.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in bruto else "\n"
    texto = bruto.replace("\r\n", "\n")
    bloque = (INICIO + "\n# Su SHA-256 está en un manifiesto sellado: git no puede reescribir sus bytes.\n"
              + "".join(f"{r} -text\n" for r in rutas) + FIN + "\n")
    if INICIO in texto:
        antes, resto = texto.split(INICIO, 1)
        texto = antes + bloque + resto.split(FIN + "\n", 1)[1]
    else:
        texto = texto.rstrip("\n") + "\n\n" + bloque
    GITATTRIBUTES.write_bytes(texto.replace("\n", nl).encode("utf-8"))
    print(f".gitattributes: {len(rutas)} activos sellados fuera de artifacts_science/ sin conversión")
    return 0


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--gitattributes", action="store_true")
    ap.add_argument("--detalle", action="store_true", help="lista cada fichero que falla")
    args = ap.parse_args()
    if args.gitattributes:
        return escribir_gitattributes()
    totales, info = revisar()
    fallos = info["fallos"]
    print(f"sellados {totales['sellados']} (sin sellar {totales['sin_sellar']}); ficheros: "
          f"verificados {totales['VERIFICADO']}, no distribuidos {totales['NO_DISTRIBUIDO']} "
          f"{info['no_distribuidos']}, distintos {totales['DISTINTO']}, ausentes {totales['AUSENTE']}")
    if fallos:
        print(f"FALLAN {len(fallos)} experimentos:")
        for exp, lista in sorted(fallos.items()):
            print(f"  {exp}: {len(lista)} — {lista[0]}")
            if args.detalle:
                for linea in lista[1:]:
                    print(f"      {linea}")
        return 1
    print("todos los experimentos sellados validan (lo no distribuido, declarado)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
