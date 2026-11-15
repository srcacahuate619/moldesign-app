"""Manifiesto de la evidencia de Colab: tamaño y SHA-256 de cada archivo, para citarla sin meterla en el repositorio.

Los resultados completos de una ejecución del cuaderno (alineamientos MSA, matrices PAE, CIF, registros, zip) pesan
cientos de MB y se archivan fuera del repositorio, en ``F:\\Backups\\moldesign-evidencia\\``. En el repositorio queda el
manifiesto: con él, cualquiera que tenga el archivo puede comprobar que es exactamente el que se citó, y un recorte que
se use como fixture puede declarar de qué original sale.

    python scripts/colab_plddt/manifiesto_evidencia.py escribir <carpeta> <manifiesto.json> [--archivado-en RUTA] [--origen TEXTO]
    python scripts/colab_plddt/manifiesto_evidencia.py verificar <carpeta> <manifiesto.json>

``verificar`` termina con código 0 sólo si no falta, cambia ni sobra ningún archivo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ESQUEMA = 1


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def construir(carpeta: Path | str, archivado_en: str | None = None, origen: str | None = None) -> dict:
    carpeta = Path(carpeta)
    archivos = {}
    for ruta in sorted(p for p in carpeta.rglob("*") if p.is_file()):
        archivos[ruta.relative_to(carpeta).as_posix()] = {"bytes": ruta.stat().st_size, "sha256": _sha256(ruta)}
    return {
        "esquema": ESQUEMA,
        "archivado_en": archivado_en,
        "origen": origen,
        "archivos_totales": len(archivos),
        "bytes_totales": sum(a["bytes"] for a in archivos.values()),
        "archivos": archivos,
    }


def verificar(carpeta: Path | str, manifiesto: dict) -> dict:
    actual = construir(carpeta)["archivos"]
    esperado = manifiesto["archivos"]
    faltan = sorted(set(esperado) - set(actual))
    sobran = sorted(set(actual) - set(esperado))
    distintos = sorted(k for k in set(esperado) & set(actual) if esperado[k] != actual[k])
    return {"coincide": not (faltan or sobran or distintos), "faltan": faltan, "sobran": sobran,
            "distintos": distintos, "comprobados": len(set(esperado) & set(actual))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="orden", required=True)
    escribir = sub.add_parser("escribir")
    escribir.add_argument("carpeta", type=Path)
    escribir.add_argument("manifiesto", type=Path)
    escribir.add_argument("--archivado-en", default=None)
    escribir.add_argument("--origen", default=None)
    comprobar = sub.add_parser("verificar")
    comprobar.add_argument("carpeta", type=Path)
    comprobar.add_argument("manifiesto", type=Path)
    args = parser.parse_args()

    if args.orden == "escribir":
        datos = construir(args.carpeta, args.archivado_en, args.origen)
        args.manifiesto.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{datos['archivos_totales']} archivos, {datos['bytes_totales']} bytes → {args.manifiesto}")
        return 0
    resultado = verificar(args.carpeta, json.loads(args.manifiesto.read_text(encoding="utf-8")))
    print(json.dumps({k: (v[:20] if isinstance(v, list) else v) for k, v in resultado.items()}, ensure_ascii=False))
    return 0 if resultado["coincide"] else 1


if __name__ == "__main__":
    sys.exit(main())
