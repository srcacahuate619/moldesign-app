#!/usr/bin/env python3
"""Lockfile del intérprete EMBEBIDO, medido sobre el intérprete embebido.

# El problema que resuelve

`backend/requirements-desktop.lock.txt` dice, en su propia cabecera:

    Versiones EXACTAS resueltas contra el entorno de desarrollo actual:
    Python 3.14.3 (system) en Windows 11.

Pero el runtime que se distribuye es **CPython 3.11.9**. Es decir: el único
lockfile del repositorio describe un entorno que **no es** el que viaja en el
instalador. Con él no se puede reconstruir `python-embed/`, y `python-embed/`
no está versionado — así que hasta hoy no había forma de rehacerlo desde el
repositorio. Un repositorio público del que no se puede reconstruir el binario
distribuido incumple la promesa que la AGPL le hace a quien lo recibe.

Este script pregunta al **propio intérprete empaquetado** qué tiene instalado y
escribe `backend/requirements-embed.lock.txt`. No resuelve, no infiere y no
consulta la red: transcribe.

# Qué NO garantiza

Que `pip install -r` sobre ese lockfile produzca bytes idénticos. Las ruedas de
`torch`, `rdkit` u `openmm` pueden republicarse, y algunas dependencias tienen
extensiones nativas compiladas contra la máquina que las construyó. Lo que
garantiza es la lista exacta de nombres y versiones que hay dentro del runtime
distribuido, que es el dato que hoy no existe en ninguna parte.

Los hashes de los artefactos que SÍ viajan siguen viviendo donde ya vivían:
`runtime-manifest.json` para el bundle y `docs/api/sbom.json` para el
inventario de licencias.

# Uso

    python scripts/lock_embedded_runtime.py            # escribe el lockfile
    python scripts/lock_embedded_runtime.py --check    # falla si difiere
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# La consola de Windows usa cp1252: un carácter fuera de esa tabla convierte un
# informe en un traceback DESPUÉS de haber hecho el trabajo. Ver salida_consola.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # noqa: E402
    from salida_consola import consola_utf8
except ImportError:  # pragma: no cover - un clon puede no traer el ayudante
    # Se degrada en vez de morir: esto es presentación, no resultado. Un script
    # de aprovisionamiento que no arranca porque falta una comodidad de consola
    # deja al que clona sin la única herramienta que tenía para desbloquearse.
    def consola_utf8() -> None:
        import sys as _sys
        for _flujo in (_sys.stdout, _sys.stderr):
            _reconfigurar = getattr(_flujo, "reconfigure", None)
            if _reconfigurar is not None:
                try:
                    _reconfigurar(encoding="utf-8", errors="replace")
                except (ValueError, OSError):
                    pass

consola_utf8()


RAIZ = Path(__file__).resolve().parents[1]
PYTHON_EMBED = RAIZ / "python-embed" / "python.exe"
SALIDA = RAIZ / "backend" / "requirements-embed.lock.txt"

#: Se le pregunta al intérprete empaquetado, no al del desarrollador. Es la
#: misma técnica que usa `generate_sbom.py`, y por el mismo motivo: en esta
#: máquina hay dos intérpretes con inventarios distintos.
_GUION = (
    "import json,importlib.metadata as md,sys;"
    "print(json.dumps({"
    "'python': '%d.%d.%d' % sys.version_info[:3],"
    "'paquetes': sorted("
    "  ({'nombre': d.metadata['Name'], 'version': d.version}"
    "   for d in md.distributions() if d.metadata['Name']),"
    "  key=lambda p: p['nombre'].lower())}))"
)


def inventario() -> dict:
    if not PYTHON_EMBED.is_file():
        raise SystemExit(
            f"No existe {PYTHON_EMBED.relative_to(RAIZ).as_posix()}.\n"
            "Este lockfile describe el intérprete EMBEBIDO, así que no se puede "
            "generar sin él. Sobre un clon limpio, aprovisiona primero el árbol "
            "con `python scripts/bootstrap_dev_tree.py`."
        )
    proceso = subprocess.run(
        [str(PYTHON_EMBED), "-c", _GUION],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proceso.returncode != 0:
        raise SystemExit(
            f"El intérprete empaquetado no pudo inventariarse:\n{proceso.stderr[-1500:]}"
        )
    return json.loads(proceso.stdout)


def serializar(datos: dict) -> str:
    version = datos["python"]
    paquetes = datos["paquetes"]
    lineas = [
        "# requirements-embed.lock.txt",
        "#",
        "# GENERADO. No editar a mano: `python scripts/lock_embedded_runtime.py`.",
        "#",
        f"# Inventario EXACTO del intérprete que se distribuye: CPython {version},",
        "# Windows x86-64. Medido preguntándole al propio `python-embed/python.exe`,",
        "# no resuelto contra el entorno del desarrollador.",
        "#",
        "# POR QUÉ EXISTE, aparte de `requirements-desktop.lock.txt`. Ese otro",
        "# lockfile declara en su cabecera que se resolvió contra Python 3.14.3 del",
        "# sistema, mientras el runtime distribuido es 3.11. Describía un entorno",
        "# que nadie recibe, y con él `python-embed/` no se podía reconstruir.",
        "#",
        "# QUÉ NO GARANTIZA. Bytes idénticos: las ruedas se republican y algunas",
        "# traen extensiones nativas. Garantiza la lista exacta de nombres y",
        "# versiones dentro del runtime distribuido. Los hashes de los artefactos",
        "# que viajan están en `runtime-manifest.json` y `docs/api/sbom.json`.",
        "#",
        f"# {len(paquetes)} distribuciones.",
        "",
    ]
    lineas += [f"{p['nombre']}=={p['version']}" for p in paquetes]
    return "\n".join(lineas) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--check", action="store_true")
    parser.add_argument(
        "--permitir-runtime-ausente",
        action="store_true",
        help=(
            "no fallar si `python-embed/` no está. El runtime no viaja en el "
            "repositorio, así que sobre un clon limpio este gate no puede "
            "comprobar nada y lo DICE en vez de reventar. Se pasa desde CI."
        ),
    )
    args = parser.parse_args()

    if args.permitir_runtime_ausente and not PYTHON_EMBED.is_file():
        print(
            "Lockfile del runtime NO verificado: `python-embed/` no está presente. "
            "Saltar no es aprobar: la lista de dependencias del runtime "
            "distribuido queda sin comprobar en este clon."
        )
        return 0

    texto = serializar(inventario())

    if args.check:
        if not SALIDA.is_file():
            print(
                f"No existe {SALIDA.relative_to(RAIZ).as_posix()}. Ejecuta "
                "`python scripts/lock_embedded_runtime.py`.",
                file=sys.stderr,
            )
            return 1
        if SALIDA.read_text(encoding="utf-8") != texto:
            print(
                "El lockfile del runtime embebido está desactualizado: el "
                "intérprete distribuido tiene otras dependencias que las "
                "declaradas. Regenera y revisa el diff.",
                file=sys.stderr,
            )
            return 1
        print(f"Lockfile del runtime embebido verificado: {texto.count('==')} paquetes")
        return 0

    SALIDA.write_text(texto, encoding="utf-8")
    print(f"Generado: {SALIDA.relative_to(RAIZ).as_posix()}")
    print(f"  {texto.count('==')} paquetes del intérprete distribuido")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
