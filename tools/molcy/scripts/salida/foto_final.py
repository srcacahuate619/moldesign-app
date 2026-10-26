"""La foto final: escena + capa de rótulos, con el mismo contraste que el vídeo.

Python puro con Pillow, sin Blender. La capa se refuerza (halo y placa oscuros,
`contraste.py`) y se compone encima de la escena, igual que `codificar.py` la
monta en el vídeo. Además se mide qué hay en cada esquina de la capa: quien pone
una marca encima no debe taparle una etiqueta a nadie.
"""
from __future__ import annotations

from PIL import Image

from salida.contraste import cajas_en_pixeles, reforzar

ESQUINAS = ("inferior_derecha", "superior_derecha", "inferior_izquierda", "superior_izquierda")
#: Lado del cuadrado que se mide en cada esquina, en fracción del lado corto.
LADO_ESQUINA = 0.16


def componer(escena: Image.Image, capa: Image.Image | None, etiquetas, fotograma: int):
    """(foto RGB, capa reforzada o None). `etiquetas`: `etiquetas_lectura` del acta."""
    base = escena.convert("RGBA")
    if capa is None:
        return base.convert("RGB"), None
    if capa.size != base.size:
        raise ValueError(f"la capa mide {capa.size} y la escena {base.size}")
    reforzada = reforzar(capa, cajas_en_pixeles(etiquetas, fotograma, *base.size))
    return Image.alpha_composite(base, reforzada).convert("RGB"), reforzada


def ocupacion_esquinas(capa: Image.Image | None, size: tuple[int, int],
                       lado: float = LADO_ESQUINA) -> dict[str, int]:
    """El alfa máximo (0-255) de la capa reforzada en cada esquina; 0 = libre."""
    ancho, alto = size
    if capa is None:
        return {e: 0 for e in ESQUINAS}
    a = max(1, round(min(ancho, alto) * lado))
    cajas = {"inferior_derecha": (ancho - a, alto - a, ancho, alto),
             "superior_derecha": (ancho - a, 0, ancho, a),
             "inferior_izquierda": (0, alto - a, a, alto),
             "superior_izquierda": (0, 0, a, a)}
    alfa = capa.getchannel("A")
    return {e: int(alfa.crop(cajas[e]).getextrema()[1]) for e in ESQUINAS}
