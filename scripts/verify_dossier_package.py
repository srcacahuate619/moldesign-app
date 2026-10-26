#!/usr/bin/env python
"""
Verifica un paquete reproducible de MolDesign.

    python scripts/verify_dossier_package.py <archivo.zip> [--json] [--lang en]

Sólo usa la biblioteca estándar de Python (probado con 3.11 y 3.14 en un entorno vacío): no hace falta
instalar el backend.

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

from core.i18n import set_request_locale  # noqa: E402
from services.dossier.verify import verificar_paquete  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifica la integridad de un paquete reproducible de MolDesign.",
    )
    parser.add_argument("paquete", help="Ruta al archivo .zip")
    parser.add_argument("--json", action="store_true", help="Informe en JSON")
    parser.add_argument("--lang", choices=["es", "en"], default="es", help="Idioma del informe (es / en)")
    args = parser.parse_args()
    set_request_locale(args.lang)
    # Con la salida redirigida, Windows usa la página de códigos del sistema y las tildes salían rotas.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    en = args.lang == "en"
    ruta = Path(args.paquete)
    if not ruta.is_file():
        print(f"File not found: {ruta}" if en else f"No existe el archivo: {ruta}", file=sys.stderr)
        return 2

    try:
        datos = ruta.read_bytes()
    except OSError as exc:
        print(f"Could not read {ruta}: {exc}" if en else f"No se pudo leer {ruta}: {exc}", file=sys.stderr)
        return 2

    resultado = verificar_paquete(datos)

    if args.json:
        print(json.dumps(resultado.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"{'Package' if en else 'Paquete'}: {ruta.name}")
        print(resultado.informe())

    return 0 if resultado.valido else 1


if __name__ == "__main__":
    raise SystemExit(main())
