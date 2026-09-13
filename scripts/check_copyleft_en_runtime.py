"""Puerta: ningun paquete con copyleft fuerte viaja sin estar declarado.

POR QUE EXISTE. El runtime embebido llevaba `padelpy`, cuyo METADATA declara MIT
pero que empaqueta `PaDEL-Descriptor.jar` bajo **AGPL-3.0**. El SBOM lo daba por
MIT, `THIRD_PARTY_NOTICES.md` no lo inventariaba y nadie en el codigo lo
importaba: 22,5 MB de obligacion AGPL viajando en el MSIX a cambio de nada. No
fue un despiste puntual; fue que la licencia de un paquete se leia del METADATA
del wrapper y no de lo que ese paquete METE DENTRO.

QUE COMPRUEBA. Recorre los paquetes del runtime staged, busca textos de licencia
-los del propio paquete y los de cualquier subdirectorio que traiga- y marca los
que contienen la cabecera de AGPL o GPL. LGPL no se marca: la frontera de
relinking esta documentada en `SOURCE_CODE_AND_RELINKING.md`.

QUE NO HACE. No decide si una licencia es aceptable. Un paquete copyleft puede
distribuirse perfectamente; lo que no puede es hacerlo sin aparecer en los
avisos. Por eso la salida no es "prohibido" sino "declaralo o quitalo".

Uso:
    python scripts/check_copyleft_en_runtime.py
    python scripts/check_copyleft_en_runtime.py --runtime <ruta a site-packages>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_PACKAGES = ROOT / "frontend" / "src-tauri" / "resources" / "python" / "Lib" / "site-packages"
AVISOS = ROOT / "frontend" / "public" / "legal" / "THIRD_PARTY_NOTICES.md"

# Firmas del texto de licencia, no del metadato: el metadato es justo lo que
# mintio. Se busca la cabecera literal del documento.
FIRMAS = {
    "AGPL": ("GNU AFFERO GENERAL PUBLIC LICENSE",),
    "GPL": ("GNU GENERAL PUBLIC LICENSE",),
}
# LGPL comparte la cabecera de GPL en algunas copias; se descarta por su propia
# cabecera, que es inequivoca.
FIRMA_LGPL = "GNU LESSER GENERAL PUBLIC LICENSE"

NOMBRES_DE_LICENCIA = ("license", "licence", "copying", "licenses")

# Paquetes con copyleft que SI se distribuyen y estan declarados. Cada entrada
# exige su justificacion en los avisos; la prueba lo comprueba.
DECLARADOS: dict[str, str] = {
    # nombre de paquete -> como aparece en THIRD_PARTY_NOTICES.md
}


def textos_de_licencia(paquete: Path) -> list[Path]:
    """Ficheros de licencia del paquete y de lo que empaqueta dentro."""
    encontrados: list[Path] = []
    for p in paquete.rglob("*"):
        if not p.is_file():
            continue
        nombre = p.name.lower()
        if any(n in nombre for n in NOMBRES_DE_LICENCIA) and p.stat().st_size < 200_000:
            encontrados.append(p)
        elif p.parent.name.lower() in NOMBRES_DE_LICENCIA and p.stat().st_size < 200_000:
            encontrados.append(p)
    return encontrados


def clasificar(ficheros: list[Path]) -> dict[str, list[Path]]:
    hallazgos: dict[str, list[Path]] = {}
    for f in ficheros:
        try:
            texto = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        cabecera = texto[:4000].upper()
        if FIRMA_LGPL in cabecera:
            continue
        for etiqueta, firmas in FIRMAS.items():
            if any(s in cabecera for s in firmas):
                hallazgos.setdefault(etiqueta, []).append(f)
                break
    return hallazgos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runtime", type=Path, default=SITE_PACKAGES)
    args = ap.parse_args()

    if not args.runtime.is_dir():
        print(f"No hay runtime staged en {args.runtime}; nada que comprobar.")
        return 0

    avisos = AVISOS.read_text(encoding="utf-8", errors="replace") if AVISOS.is_file() else ""

    problemas: list[str] = []
    revisados = 0
    for paquete in sorted(args.runtime.iterdir()):
        if not paquete.is_dir() or paquete.name.endswith((".dist-info", ".egg-info")):
            continue
        revisados += 1
        hallazgos = clasificar(textos_de_licencia(paquete))
        if not hallazgos:
            continue
        etiquetas = ",".join(sorted(hallazgos))
        declarado = paquete.name in DECLARADOS or paquete.name.lower() in avisos.lower()
        marca = "declarado" if declarado else "SIN DECLARAR"
        ejemplo = hallazgos[sorted(hallazgos)[0]][0]
        try:
            rel = ejemplo.relative_to(args.runtime)
        except ValueError:
            rel = ejemplo
        print(f"  [{etiquetas:4}] {paquete.name:28} {marca}   {rel}")
        if not declarado:
            problemas.append(
                f"{paquete.name} ({etiquetas}) viaja en el runtime y no aparece en "
                f"THIRD_PARTY_NOTICES.md. Evidencia: {rel}"
            )

    print(f"\npaquetes revisados: {revisados}")
    if problemas:
        print("\nABORTADO: copyleft fuerte sin declarar\n")
        for p in problemas:
            print(f"  - {p}")
        print(
            "\nDos salidas, y ninguna es ignorarlo:\n"
            "  1. Declararlo en THIRD_PARTY_NOTICES.md y en el SBOM, entregar su\n"
            "     licencia integra y su codigo fuente u oferta valida.\n"
            "  2. Quitarlo del runtime si no se usa, que es lo que se hizo con\n"
            "     padelpy: nadie lo importaba y arrastraba AGPL-3.0.\n"
        )
        return 1

    print("OK: ningun paquete con copyleft fuerte sin declarar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
