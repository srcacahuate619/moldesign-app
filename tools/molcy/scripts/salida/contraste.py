"""Contraste del texto en la capa de rótulos. Python puro con Pillow, sin Blender.

    python contraste.py <carpeta_capa> <build_*.json>

Las etiquetas se leían mal sobre el receptor claro: texto crema sobre cinta
gris clara. Aquí, en la capa transparente (nunca en la escena):

- un halo oscuro alrededor de TODO el texto (el alfa dilatado unos píxeles);
- una placa oscura detrás de cada etiqueta anclada, del tamaño de su caja
  medida (`etiquetas_lectura` del acta) y con la opacidad de la propia etiqueta
  en ese fotograma: entra y sale con su fundido, y no aparece si la etiqueta
  aún no se ve.

Se ejecuta entre la pasada de la capa y `codificar.py` (`correr_caso.ps1`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

#: Color de la placa y del halo: el azul casi negro del fondo de la escena.
OSCURO = (6, 12, 17)
#: Opacidad máxima de la placa (con la etiqueta entera) y del halo.
PLACA, HALO = 0.80, 0.85


def reforzar(capa: Image.Image, cajas=()) -> Image.Image:
    """La capa con halo y placas. `cajas` en píxeles (x0, y0, x1, y1)."""
    capa = capa.convert("RGBA")
    alfa = capa.getchannel("A")
    # El halo, en píxeles e impar, proporcional al cuadro: 3 hasta 1080 de lado
    # corto (lo que mide el vídeo) y más en una foto de 1440 o 4K, donde 3 px se
    # pierden. Antes era 3 o 5 con un corte en 1400.
    lado = max(3, round(min(capa.size) * 3 / 1080)) | 1
    halo = alfa.filter(ImageFilter.MaxFilter(lado)).point(lambda v: round(v * HALO))
    fondo = Image.new("RGBA", capa.size, (*OSCURO, 0))
    fondo.putalpha(halo)
    dibujo = ImageDraw.Draw(fondo)
    radio = max(3, round(min(capa.size) / 240))
    for x0, y0, x1, y1 in cajas:
        if x1 <= x0 or y1 <= y0:
            continue
        fuerza = alfa.crop((x0, y0, x1, y1)).getextrema()[1]
        if fuerza:
            dibujo.rounded_rectangle((x0, y0, x1, y1), radius=radio,
                                     fill=(*OSCURO, round(fuerza * PLACA)))
    return Image.alpha_composite(fondo, capa)


def cajas_en_pixeles(etiquetas, fotograma: int, ancho: int, alto: int) -> list:
    """Las cajas (NDC del acta) de las etiquetas visibles en `fotograma`, en píxeles."""
    aire = max(3, round(min(ancho, alto) * 0.008))
    out = []
    for e in etiquetas:
        a, b = e["ventana"]
        if not a <= fotograma <= b:
            continue
        x0, y0, x1, y1 = e["caja"]
        out.append((max(0, round((x0 + 1) * ancho / 2) - aire),
                    max(0, round((1 - y1) * alto / 2) - aire),
                    min(ancho, round((x1 + 1) * ancho / 2) + aire),
                    min(alto, round((1 - y0) * alto / 2) + aire)))
    return out


def main(argv) -> int:
    if len(argv) < 2:
        print("uso: contraste.py <carpeta_capa> <build_*.json>")
        return 2
    carpeta, acta = Path(argv[0]), Path(argv[1])
    etiquetas = json.loads(acta.read_text(encoding="utf-8")).get("etiquetas_lectura") or []
    n = 0
    for png in sorted(carpeta.glob("f_*.png")):
        fotograma = int(png.stem.split("_")[-1])
        with Image.open(png) as imagen:
            imagen.load()
            salida = reforzar(imagen, cajas_en_pixeles(etiquetas, fotograma, *imagen.size))
        salida.save(png)
        n += 1
    print(f"CONTRASTE_OK: {n} fotogramas de la capa, {len(etiquetas)} etiquetas con placa",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
