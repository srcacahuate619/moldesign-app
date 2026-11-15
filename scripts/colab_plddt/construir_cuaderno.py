"""Construye ``convencion_plddt_boltz_chai.ipynb`` a partir de ``celdas/`` y de los dos módulos que el cuaderno escribe.

El cuaderno no se edita a mano: se edita la celda (o el módulo) y se vuelve a construir. Con ``--check`` no escribe
nada y falla si el cuaderno versionado no es el que saldría de las fuentes (la misma regla que los demás ``--check``
del repositorio: lo que se verifica tiene que ser lo que se entrega).

    python scripts/colab_plddt/construir_cuaderno.py           # escribe
    python scripts/colab_plddt/construir_cuaderno.py --check   # sólo comprueba
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CUADERNO = AQUI / "convencion_plddt_boltz_chai.ipynb"
DESTINO_EN_COLAB = "/content/plddt_boltz_chai"

#: (tipo, fuente). «escribir» = una celda %%writefile que deja el módulo en Colab tal cual está en el repositorio.
CELDAS = [
    ("markdown", "celdas/00_introduccion.md"),
    ("code", "celdas/01_parametros.py"),
    ("code", "celdas/02_entorno.py"),
    ("escribir", "analisis_plddt.py"),
    ("escribir", "ejecutar_chai.py"),
    ("code", "celdas/03_secuencias.py"),
    ("code", "celdas/04_instalacion.py"),
    ("code", "celdas/05_entradas.py"),
    ("code", "celdas/06_boltz.py"),
    ("code", "celdas/07_chai.py"),
    ("code", "celdas/08_pesos.py"),
    ("code", "celdas/09_analisis.py"),
    ("code", "celdas/10_descarga.py"),
    ("markdown", "celdas/11_despues.md"),
]


def _lineas(texto: str) -> list[str]:
    lineas = texto.splitlines(keepends=True)
    if lineas and lineas[-1].endswith("\n"):
        lineas[-1] = lineas[-1][:-1]
    return lineas


def construir() -> str:
    celdas = []
    for tipo, fuente in CELDAS:
        texto = (AQUI / fuente).read_text(encoding="utf-8")
        if tipo == "escribir":
            texto = f"%%writefile {DESTINO_EN_COLAB}/{Path(fuente).name}\n{texto}"
            tipo = "code"
        celda = {"cell_type": tipo, "metadata": {}, "source": _lineas(texto)}
        if tipo == "code":
            celda.update(execution_count=None, outputs=[])
        celdas.append(celda)
    cuaderno = {
        "cells": celdas,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"provenance": [], "gpuType": "L4"},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 0,
    }
    return json.dumps(cuaderno, ensure_ascii=False, indent=1) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    nuevo = construir()
    if args.check:
        actual = CUADERNO.read_text(encoding="utf-8") if CUADERNO.exists() else None
        if actual != nuevo:
            print(f"{CUADERNO.name} no coincide con sus fuentes: ejecuta construir_cuaderno.py sin --check")
            return 1
        print(f"{CUADERNO.name} coincide con sus fuentes ({len(CELDAS)} celdas)")
        return 0
    CUADERNO.write_text(nuevo, encoding="utf-8", newline="\n")
    print(f"escrito {CUADERNO} ({len(CELDAS)} celdas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
