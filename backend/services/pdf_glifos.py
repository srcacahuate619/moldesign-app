"""Quita de un texto los caracteres que las fuentes de los PDF no tienen.

Una fuente sin el glifo de un carácter lo pinta como un cuadro negro (o lo extrae como U+0000 o U+007F), y a quien lee el PDF
le parece un error de impresión. Medido en 14 de 14 corridas de la cápsula de QA (2026-11-11): los avisos heredados del
motor empiezan con «⚠️» (`pipeline/runner.py`), las fuentes de los dos documentos no lo tienen y el aviso salía como «■■».

Los avisos ya guardados en el historial de la gente conservan el emoji, así que arreglar el origen no basta: se quita al
dibujar. Lo que se quita es sólo lo que no se puede ver; el texto que lo rodea no cambia.
"""
from __future__ import annotations

import re

# Selectores de variación, uniones de ancho cero, espacio de ancho cero y la marca de orden de bytes: no tienen glifo.
_INVISIBLES = "︎️​‌‍⁠﻿"

# Pictogramas: «Símbolos varios» y «Dingbats» (⚠ ⚡ ☀ ✈ …) salvo la marca de verificación y la cruz, que las fuentes del
# producto sí dibujan (`test_pdf_extraible.py` lo mide), y todo el plano suplementario de emoji.
_PICTOGRAMAS = re.compile("[☀-⛿✀-✒✔-✖✘-➿\U0001f000-\U0001faff]")

# Lo que sobra tras quitar un pictograma al principio de una línea: el espacio que lo separaba del texto.
_ESPACIO_INICIAL = re.compile(r"^[ \t]+")
_ESPACIOS_DOBLES = re.compile(r"[ \t]{2,}")

_CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sin_glifos_ausentes(texto: str) -> str:
    """`texto` sin pictogramas, caracteres invisibles ni caracteres de control (conserva saltos de línea y tabuladores)."""
    if not texto:
        return texto
    limpio = texto
    for c in _INVISIBLES:
        limpio = limpio.replace(c, "")
    limpio = _CONTROL.sub("", limpio)
    if _PICTOGRAMAS.search(limpio):
        limpio = _PICTOGRAMAS.sub("", limpio)
        # El pictograma solía ir seguido de un espacio: al quitarlo no puede quedar una sangría ni un hueco doble.
        limpio = "\n".join(_ESPACIO_INICIAL.sub("", linea) for linea in limpio.split("\n"))
        limpio = _ESPACIOS_DOBLES.sub(" ", limpio)
    return limpio


# `código` entre comillas inversas, como lo escribe la prosa del producto («`manifest.json`», «`not_evaluated`»).
_CODIGO = re.compile(r"`([^`\n]+)`")


def codigo_en_monoespaciada(marcado: str, fuente: str = "Courier") -> str:
    """Convierte «`x`» en `x` en letra monoespaciada, para un `Paragraph` de ReportLab.

    Las comillas inversas son sintaxis de Markdown: en un PDF salen como un carácter suelto («`manifest.json`») y no
    significan nada para quien lo lee (B7, 14 de 14 dossiers). Se aplica sobre texto YA escapado, dentro de un `Paragraph`.
    """
    if not marcado or "`" not in marcado:
        return marcado
    return _CODIGO.sub(lambda m: f"<font face=\"{fuente}\">{m.group(1)}</font>", marcado)
