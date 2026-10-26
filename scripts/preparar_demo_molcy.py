#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preparar_demo_molcy.py — convierte un vídeo de Molcy en la demostración de la web.

La web (`site/`) enseña un vídeo real de Molcy en bucle, sin sonido, como haría un
GIF. No es un GIF porque pesa siete veces menos y conserva color y fluidez (medido el
2026-10-11 sobre el vídeo de 4FK3: GIF de 360 px a 15 fps, 18,6 MB; MP4 de 720 px a
30 fps, 2,6 MB).

El vídeo se recomprime, nada más: mismo contenido, mismo cierre de MolDesign, menos
píxeles. Lo que dice el pie del vídeo en la web (corrida, receptor, escena, poses,
pasos) no se escribe a mano: sale del `scene.json` y del `build_*.json` que Molcy
dejó junto al vídeo, y se guarda en `site/assets/molcy-demo.json` con el SHA-256 del
original, que se comprueba contra el `.sha256` que lo acompaña.

Uso
---
    python scripts/preparar_demo_molcy.py --video <salida de Molcy>/<vídeo>.mp4

Escribe `site/assets/molcy-demo.mp4`, `molcy-demo.webp` (el fotograma de reposo) y
`molcy-demo.json`. Después hay que correr `scripts/build_sitio_publico.py`.

ffmpeg: ``--ffmpeg``, o el del PATH, o el que trae ``imageio-ffmpeg``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS = PROJECT_ROOT / "site" / "assets"

ANCHO_WEB = 720   # se ve a unos 360 px CSS: el doble para pantallas de alta densidad
CRF = 27
SEGUNDO_DE_REPOSO = 6.0


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _ffmpeg(explicito: str | None) -> str:
    if explicito:
        return explicito
    en_path = shutil.which("ffmpeg")
    if en_path:
        return en_path
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("[demo] no hay ffmpeg: pásalo con --ffmpeg o instala imageio-ffmpeg")


def _correr(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit(f"[demo] falló: {' '.join(cmd[:3])}…\n{r.stderr[-2000:]}")
    return r.stderr


def procedencia(video: Path) -> Dict[str, Any]:
    """Lo que Molcy declaró de este vídeo, leído de los archivos que dejó a su lado."""
    salida = video.parent
    huella = video.stem.rsplit("_", 1)[-1]
    escena_p = salida / "scene.json"
    builds = list(salida.glob(f"build_*_{huella}.json"))
    if not escena_p.exists() or len(builds) != 1:
        sys.exit(f"[demo] {salida} no trae scene.json y un build_*_{huella}.json: "
                 "¿es la carpeta salida de Molcy?")
    escena = json.loads(escena_p.read_text(encoding="utf-8"))
    build = json.loads(builds[0].read_text(encoding="utf-8"))
    pro = escena["procedencia"]
    formato = build["formato"]
    sujeto = build.get("sujeto") or {}
    datos: Dict[str, Any] = {
        "origen": pro["origen"],
        "corrida": pro["task_id"],
        "escena": pro["escena"],
        "pdb_id": pro["pdb_id"],
        "receptor": pro["target_name"],
        "receptor_sha256": pro["receptor_sha256"],
        "poses_sha256": pro["poses_sha256"],
        "formato": formato["nombre"],
        "ancho": formato["ancho"],
        "alto": formato["alto"],
        "fps": formato["fps"],
        "cierre_s": formato["cierre_s"],
    }
    # «9 poses, 128520 pasos internos en 8 replicas»: la escena Búsqueda lo declara así.
    m = re.match(r"(\d+) poses, (\d+) pasos internos en (\d+) r[eé]plicas", sujeto.get("razon") or "")
    if m:
        datos.update(poses=int(m.group(1)), pasos=int(m.group(2)), replicas=int(m.group(3)))
    return datos


def main() -> int:
    ap = argparse.ArgumentParser(description="Convierte un vídeo de Molcy en la demo de la web")
    ap.add_argument("--video", required=True, type=Path, help="el .mp4 de la carpeta salida de Molcy")
    ap.add_argument("--ffmpeg", help="ruta a ffmpeg (por defecto: PATH o imageio-ffmpeg)")
    ap.add_argument("--reposo", type=float, default=SEGUNDO_DE_REPOSO,
                    help="segundo del fotograma que se ve antes de reproducir")
    args = ap.parse_args()

    video: Path = args.video
    if not video.exists():
        sys.exit(f"[demo] no existe {video}")
    sha = _sha256(video)
    lateral = video.with_name(video.name + ".sha256")
    if lateral.exists() and lateral.read_text(encoding="utf-8").split()[0] != sha:
        sys.exit(f"[demo] {video.name} no coincide con su .sha256: no se publica un vídeo alterado")
    ff = _ffmpeg(args.ffmpeg)
    datos = procedencia(video)

    mp4 = ASSETS / "molcy-demo.mp4"
    reposo = ASSETS / "molcy-demo.webp"
    _correr([ff, "-hide_banner", "-y", "-i", str(video), "-an",
             "-vf", f"scale={ANCHO_WEB}:-2:flags=lanczos", "-c:v", "libx264", "-preset", "slow",
             "-crf", str(CRF), "-profile:v", "high", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", "-map_metadata", "-1", str(mp4)])
    _correr([ff, "-hide_banner", "-y", "-ss", str(args.reposo), "-i", str(video), "-frames:v", "1",
             "-vf", f"scale={ANCHO_WEB}:-2:flags=lanczos", "-c:v", "libwebp", "-quality", "82",
             "-map_metadata", "-1", str(reposo)])
    # «ffmpeg -i» sin salida termina con código 1 por diseño: sólo se lee lo que describe.
    info = subprocess.run([ff, "-hide_banner", "-i", str(mp4)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stderr
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    dim = re.search(r"Video: .*?, (\d+)x(\d+)", info)
    version = subprocess.run([ff, "-version"], capture_output=True, text=True).stdout.split("\n")[0]

    salida = {
        "que_es": "Vídeo de Molcy recomprimido para la web: mismo contenido y cierre, menos píxeles.",
        "generador": "scripts/preparar_demo_molcy.py",
        "original": {"archivo": video.name, "sha256": sha, "bytes": video.stat().st_size},
        "molcy": datos,
        "web": {
            "archivo": mp4.name, "sha256": _sha256(mp4), "bytes": mp4.stat().st_size,
            "ancho": int(dim.group(1)) if dim else None, "alto": int(dim.group(2)) if dim else None,
            "duracion_s": round(int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3)), 2)
            if dur else None,
            "codec": "H.264 High, yuv420p, sin audio", "crf": CRF, "ffmpeg": version,
        },
        "reposo": {"archivo": reposo.name, "sha256": _sha256(reposo), "segundo": args.reposo},
    }
    (ASSETS / "molcy-demo.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"[demo] {mp4.name} {mp4.stat().st_size / 1e6:.1f} MB, {reposo.name}, molcy-demo.json "
          f"({datos['pdb_id']}, escena {datos['escena']}, corrida {datos['corrida'][:8]})")
    print("[demo] ahora: python scripts/build_sitio_publico.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
