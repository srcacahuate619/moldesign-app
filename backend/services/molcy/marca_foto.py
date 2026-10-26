"""La marca de MolDesign en una foto de Molcy y su procedencia dentro del PNG.

Decisión del propietario (2026-10-08): toda foto lleva el emblema de MolDesign, con su transparencia, en UNA esquina y sutil
(que casi no se note). No hay ajuste que la quite, como el cierre del vídeo. La pone MolDesign sobre el PNG que entrega el motor,
no el motor: así es la misma en CPU y en GPU y no depende de lo que haga una copia modificada del motor.

La esquina es la primera libre de rótulos según el acta del motor (`esquinas`: alfa máximo de la capa de rótulos reforzada en un
cuadrado de 16 % del lado corto, mayor que lo que ocupa la marca). Si ninguna está libre, la menos ocupada.

La procedencia viaja dentro del PNG (iTXt) para que una foto pegada en una diapositiva siga diciendo de qué corrida sale. Sólo
identificadores, hashes y versiones: ninguna ruta del equipo.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, PngImagePlugin

#: El emblema de MolDesign con fondo transparente (el mismo que usa el PDF).
LOGO = Path(__file__).resolve().parents[2] / "assets" / "logo.png"
#: Tamaño del emblema y margen, en fracción del lado corto; opacidad del emblema. Probado sobre 4FK3 a 1080×1920: a tamaño
#: completo apenas se ve y de cerca se reconoce.
LADO, MARGEN, OPACIDAD = 0.07, 0.03, 0.30
ESQUINAS = ("inferior_derecha", "superior_derecha", "inferior_izquierda", "superior_izquierda")
#: Las fotos se entregan a 300 ppp: la resolución de impresión con la que se eligieron los preajustes.
PPP = 300


def elegir_esquina(esquinas: dict[str, Any] | None) -> str:
    """La primera esquina libre de rótulos, o la menos ocupada (a igualdad, la preferida)."""
    medidas = {e: v for e, v in (esquinas or {}).items()
               if e in ESQUINAS and type(v) is int and 0 <= v <= 255}
    if len(medidas) != len(ESQUINAS):
        return ESQUINAS[0]          # un acta sin medida no sabe nada mejor que la preferida
    return min(ESQUINAS, key=lambda e: (medidas[e], ESQUINAS.index(e)))


@lru_cache(maxsize=8)
def _emblema(lado: int) -> Image.Image:
    with Image.open(LOGO) as im:
        logo = im.convert("RGBA")
    logo = logo.crop(logo.getbbox())
    logo.thumbnail((lado, lado), Image.LANCZOS)
    alfa = logo.getchannel("A").point(lambda v: round(v * OPACIDAD))
    logo.putalpha(alfa)
    return logo


def posicion(esquina: str, foto: tuple[int, int], marca: tuple[int, int]) -> tuple[int, int]:
    ancho, alto = foto
    margen = round(min(ancho, alto) * MARGEN)
    x = ancho - marca[0] - margen if esquina.endswith("derecha") else margen
    y = alto - marca[1] - margen if esquina.startswith("inferior") else margen
    return x, y


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def aplicar(origen: Path, destino: Path, *, esquinas: dict[str, Any] | None,
            procedencia: dict[str, Any], textos: dict[str, str]) -> dict[str, Any]:
    """Escribe en `destino` la foto de `origen` con la marca y la procedencia. No toca `origen`."""
    with Image.open(origen) as im:
        im.load()
        foto = im.convert("RGBA")
    esquina = elegir_esquina(esquinas)
    emblema = _emblema(max(16, round(min(foto.size) * LADO)))
    foto.alpha_composite(emblema, posicion(esquina, foto.size, emblema.size))
    info = PngImagePlugin.PngInfo()
    for clave, valor in textos.items():
        info.add_itxt(clave, valor)
    info.add_itxt("MolDesign", json.dumps(procedencia, ensure_ascii=False, sort_keys=True))
    temporal = destino.with_name(f".{destino.name}.{uuid.uuid4().hex}.tmp")
    try:
        foto.convert("RGB").save(temporal, format="PNG", pnginfo=info, dpi=(PPP, PPP), compress_level=6)
        os.replace(temporal, destino)
    finally:
        temporal.unlink(missing_ok=True)
    return {"esquina": esquina, "lado_px": emblema.width, "alto_px": emblema.height,
            "opacidad": OPACIDAD, "sha256": sha256(destino), "bytes": destino.stat().st_size}


def leer_procedencia(path: Path) -> dict[str, Any] | None:
    """La procedencia embebida de una foto entregada, o None si no la trae."""
    with Image.open(path) as im:
        texto = (getattr(im, "text", None) or {}).get("MolDesign")
    try:
        valor = json.loads(texto) if texto else None
    except ValueError:
        return None
    return valor if isinstance(valor, dict) else None
