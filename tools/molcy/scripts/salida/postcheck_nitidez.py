from __future__ import annotations

import os
import sys
from pathlib import Path

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 2:
    raise SystemExit("uso: -- <mp4> <frame> [ancho] [alto]")
MP4, FRAME = Path(argv[0]), int(argv[1])
ANCHO = int(argv[2]) if len(argv) > 2 else 1920
ALTO = int(argv[3]) if len(argv) > 3 else 1080
OUT = Path(os.environ.get("TEMP", ".")) / "postcheck_v4"
OUT.mkdir(parents=True, exist_ok=True)
STEM = MP4.stem[:28]

sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = ANCHO, ALTO
se = sc.sequence_editor_create()
tiras = se.strips if hasattr(se, "strips") else se.sequences
tiras.new_movie(name="v", filepath=str(MP4), channel=1, frame_start=1)
sc.frame_set(FRAME)
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = str(OUT / STEM)
bpy.ops.render.render(write_still=True)

img = bpy.data.images.load(str(OUT / f"{STEM}.png"))
w, h = img.size
a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
# recorte del rotulo inferior izquierdo, en fraccion del cuadro: vale para
# 16:9 y para 9:16 sin tocar numeros.
h0, h1 = int(0.05 * ALTO), int(0.18 * ALTO)
w0, w1 = int(0.08 * ANCHO), int(0.47 * ANCHO)
g = a[..., :3].mean(axis=2)[h0:h1, w0:w1]
lap = (4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1]
       - g[1:-1, :-2] - g[1:-1, 2:])
print(f"NITIDEZ_MP4 {STEM} {float(lap.var()):.6f}", flush=True)
