#!/usr/bin/env python3
"""Convierte los fallos de pytest en anotaciones de GitHub Actions.

Los registros de Actions piden iniciar sesión; las anotaciones se leen sin ella,
por la API pública de check-runs. Vitest ya las emite y pytest no: el 2026-10-31
la CI del backend cayó y sólo decía «exit code 1», así que hubo que repetirla
entera en otra máquina para saber qué prueba era.

Uso: anotar_fallos_ci.py <junit.xml> [<junit.xml> ...]
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# GitHub enseña diez anotaciones de error por paso; las demás se pierden en silencio.
TOPE = 10
LARGO_DEL_MENSAJE = 600


def _escapar_mensaje(texto: str) -> str:
    return texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escapar_propiedad(texto: str) -> str:
    return _escapar_mensaje(texto).replace(":", "%3A").replace(",", "%2C")


def fallos_del_informe(ruta: Path) -> list[tuple[str, str]]:
    """Devuelve (prueba, motivo) de cada caso con <failure> o <error>."""
    encontrados = []
    for caso in ET.parse(ruta).getroot().iter("testcase"):
        for hijo in caso:
            if hijo.tag in ("failure", "error"):
                prueba = f"{caso.get('classname', '')}::{caso.get('name', '')}"
                encontrados.append((prueba, hijo.get("message") or (hijo.text or "").strip()))
                break
    return encontrados


def anotaciones(rutas: list[Path]) -> list[str]:
    fallos: list[tuple[str, str]] = []
    lineas: list[str] = []
    for ruta in rutas:
        try:
            fallos.extend(fallos_del_informe(ruta))
        except (OSError, ET.ParseError) as error:
            # Un informe ausente o a medias no es «sin fallos»: esa suite no llegó a terminar.
            lineas.append(f"::error title=Sin informe::{_escapar_mensaje(f'{ruta}: {error}')}")
    for prueba, motivo in fallos[:TOPE]:
        lineas.append(f"::error title={_escapar_propiedad(prueba)}::{_escapar_mensaje(motivo[:LARGO_DEL_MENSAJE])}")
    if len(fallos) > TOPE:
        resto = "; ".join(prueba for prueba, _ in fallos[TOPE:])
        lineas.append(f"::error title=Otros {len(fallos) - TOPE} fallos::{_escapar_mensaje(resto[:LARGO_DEL_MENSAJE])}")
    return lineas


def main(argumentos: list[str]) -> int:
    # En el ejecutor de Windows la salida es cp1252: un «≤» en el mensaje tumbaría este paso.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for linea in anotaciones([Path(a) for a in argumentos]):
        print(linea)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
