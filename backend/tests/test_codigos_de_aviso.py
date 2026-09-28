"""B-5: los códigos de aviso son un contrato con la interfaz.

La interfaz enseña un título traducido por `codigo`, porque el `mensaje` llega
en castellano y es dinámico. Si el backend emite un código que no declara, la
interfaz no tiene título que enseñar; si declara uno que ya no emite, la lista
miente. Esta prueba cruza `CODIGOS_DE_AVISO` con el código fuente.

Restricción 2 de AGENTS.md: un guardián tiene que demostrar que ve. El escáner
se prueba primero contra fuentes sintéticas.
"""

from __future__ import annotations

import re
from pathlib import Path

from services.avisos import CODIGOS_DE_AVISO, CODIGOS_DE_NORMALIZACION

RAIZ = Path(__file__).resolve().parents[2]
_EN_AVISO = re.compile(r"\baviso\(\s*\"([A-Z][A-Z0-9_]+)\"")
_LINEA_CODIGO = re.compile(r"[\"']codigo[\"']\s*:")
_LITERAL = re.compile(r"\"([A-Z][A-Z0-9_]{2,})\"")


def codigos_emitidos(fuente: str) -> set[str]:
    """Códigos literales de `aviso("X", ...)` y de líneas `"codigo": "X"`."""
    encontrados = set(_EN_AVISO.findall(fuente))
    for linea in fuente.splitlines():
        if _LINEA_CODIGO.search(linea):
            encontrados.update(_LITERAL.findall(linea))
    return encontrados - CODIGOS_DE_NORMALIZACION


def _fuentes() -> list[Path]:
    rutas = []
    for carpeta in (RAIZ / "backend", RAIZ / "rescoring"):
        for ruta in carpeta.rglob("*.py"):
            partes = set(ruta.parts)
            if "tests" in partes or "__pycache__" in partes:
                continue
            rutas.append(ruta)
    return rutas


def test_el_escaner_ve_lo_que_tiene_que_ver():
    muestra = (
        'x = aviso(\n    "CODIGO_INVENTADO", Severidad.INFO, "m")\n'
        'y = aviso("OTRO_CODIGO", Severidad.CRITICA, f"{z}")\n'
        '{"codigo": "UNO" if a else "DOS", "severidad": "info"}\n'
    )
    assert codigos_emitidos(muestra) == {"CODIGO_INVENTADO", "OTRO_CODIGO", "UNO", "DOS"}


def test_el_escaner_no_ve_lo_que_no_es_un_aviso():
    muestra = (
        'log.warning("NO_ES_UN_AVISO")\n'
        'estado = "EN_REVISION"\n'
        '{"codigo": "HEREDADO", "severidad": "heredada"}\n'
    )
    assert codigos_emitidos(muestra) == set()


def test_cada_codigo_emitido_esta_declarado_y_viceversa():
    emitidos: set[str] = set()
    for ruta in _fuentes():
        if ruta.name == "avisos.py" and ruta.parent.name == "services":
            continue  # la declaración no cuenta como emisión
        emitidos |= codigos_emitidos(ruta.read_text(encoding="utf-8", errors="replace"))

    sin_declarar = sorted(emitidos - CODIGOS_DE_AVISO)
    sin_emitir = sorted(CODIGOS_DE_AVISO - emitidos)
    assert not sin_declarar, f"Códigos emitidos sin declarar en CODIGOS_DE_AVISO: {sin_declarar}"
    assert not sin_emitir, f"Códigos declarados que ya no se emiten: {sin_emitir}"
