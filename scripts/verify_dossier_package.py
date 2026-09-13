#!/usr/bin/env python
"""
Verifica un paquete reproducible de MolDesign.

    python scripts/verify_dossier_package.py <archivo.zip> [--json]

Comprueba, SIN extraer ni ejecutar nada del paquete:

    · que ninguna entrada escape del directorio raíz (rutas absolutas, `..`,
      unidades de disco, separadores de Windows, enlaces simbólicos);
    · que `manifest.json` exista, sea JSON y de una versión compatible;
    · que todos los archivos declarados estén presentes;
    · que su tamaño y su SHA-256 coincidan;
    · que no haya duplicados ni archivos no declarados;
    · que `checksums.sha256` esté ordenado y concuerde con el contenido.

Código de salida: 0 si el paquete es VÁLIDO, 1 si es INVÁLIDO, 2 si no se pudo
leer el archivo. El 2 se distingue a propósito: «no pude comprobarlo» no es lo
mismo que «lo comprobé y está mal».
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from services.dossier.verify import verificar_paquete  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifica la integridad de un paquete reproducible de MolDesign.",
    )
    parser.add_argument("paquete", help="Ruta al archivo .zip")
    parser.add_argument("--json", action="store_true", help="Informe en JSON")
    args = parser.parse_args()

    ruta = Path(args.paquete)
    if not ruta.is_file():
        print(f"No existe el archivo: {ruta}", file=sys.stderr)
        return 2

    try:
        datos = ruta.read_bytes()
    except OSError as exc:
        print(f"No se pudo leer {ruta}: {exc}", file=sys.stderr)
        return 2

    resultado = verificar_paquete(datos)

    if args.json:
        print(json.dumps(resultado.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Paquete: {ruta.name}")
        print(resultado.informe())

    return 0 if resultado.valido else 1


if __name__ == "__main__":
    raise SystemExit(main())
