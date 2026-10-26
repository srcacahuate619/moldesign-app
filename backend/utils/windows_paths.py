"""Escritura de rutas para programas que no aceptan el namespace extendido."""
from __future__ import annotations

from pathlib import Path


def ruta_para_programa(path: str | Path) -> str:
    """Conserva la ruta canónica interna; adapta sólo su argumento externo.

    Rust canonicaliza las carpetas autorizadas como ``\\\\?\\C:\\...``.
    PowerShell 5.1 y el namespace del Shell requieren unidad/UNC habitual.
    No se resuelve de nuevo: hacerlo puede reintroducir el prefijo.
    """
    name = str(path)
    if name[:8].upper() == "\\\\?\\UNC\\":
        return "\\\\" + name[8:]
    if name.startswith("\\\\?\\"):
        regular = name[4:]
        if (len(regular) >= 3 and regular[0].isascii() and regular[0].isalpha()
                and regular[1:3] == ":\\"):
            return regular
        raise ValueError("Esta operación requiere una ruta de unidad o de red UNC para el programa externo.")
    return name
