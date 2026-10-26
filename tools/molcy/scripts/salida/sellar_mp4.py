"""Anade al acta el sha256 del MP4 ya codificado. Python puro, sin Blender.

    python sellar_mp4.py <video.mp4> <build_*.json>

Por que un sidecar y no metadatos dentro del contenedor:

1. **Blender no puede escribirlos.** `scene.render.ffmpeg` no expone ningun
   campo de metadatos (ni titulo, ni comentario, ni etiquetas), y en esta
   maquina no hay un ffmpeg externo.
2. **Aunque pudiera, no sobrevivirian.** YouTube, TikTok, Instagram y LinkedIn
   reencodan lo que subes y rehacen el contenedor: los metadatos se pierden.
   Por eso el sello va quemado en el fotograma, que son pixeles.

Asi que la procedencia vive en tres capas, cada una con su trabajo:

  - **quemada en el video**: corta y humana, sobrevive al reencodado;
  - **en el acta `build_*.json`**: completa y legible por maquina, viaja con el
    archivo si lo entregas directamente;
  - **en `MANIFEST.sha256`**: los hashes de la geometria de partida.

Lo que faltaba era cerrar el circulo: el hash del propio video, para poder
afirmar que ESE archivo salio de ESE paquete.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


def sha256(ruta: Path, bloque: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for trozo in iter(lambda: fh.read(bloque), b""):
            h.update(trozo)
    return h.hexdigest()


def main() -> int:
    args = sys.argv[1:]
    cierre = None
    if "--cierre" in args:
        # el manifiesto del cierre de marca que se pego al final del video
        i = args.index("--cierre")
        cierre = Path(args[i + 1]) if i + 1 < len(args) else None
        args = args[:i] + args[i + 2:]
    if len(args) < 2:
        print("uso: sellar_mp4.py <video.mp4> <build_*.json> [--cierre <manifiesto.json>]")
        return 2
    video, acta = Path(args[0]), Path(args[1])
    if not video.exists():
        print(f"SELLO_MP4_FALTA: {video}")
        return 1
    if cierre is None or not cierre.exists():
        # El cierre de MolDesign es obligatorio en todo video: un video sin su manifiesto no se sella ni se entrega.
        print("SELLO_SIN_CIERRE: el cierre de MolDesign es obligatorio en todo video (--cierre <manifiesto.json>)")
        return 1

    dig = sha256(video)
    datos = json.loads(acta.read_text(encoding="utf-8")) if acta.exists() else {}
    datos["video"] = {
        "archivo": video.name,
        "bytes": video.stat().st_size,
        "sha256": dig,
    }
    if cierre is not None and cierre.exists():
        # Que firma lleva el video: la huella cubre el script del cierre, el
        # emblema, su relieve, las fuentes y la version de Blender.
        m = json.loads(cierre.read_text(encoding="utf-8"))
        esperado = "en" if os.environ.get("MOLCY_IDIOMA") == "en" else "es"
        if m.get("idioma") != esperado or not isinstance(m.get("lema"), str) or not m["lema"].strip():
            print("SELLO_IDIOMA_CIERRE: el manifiesto no acredita el idioma y lema pedidos")
            return 1
        datos["cierre"] = {k: m.get(k) for k in
                           ("segundos", "fotogramas", "muestras", "huella", "blender", "idioma", "lema")}
        datos["video"]["segundos"] = round(
            (datos.get("fotogramas") or 0) / (m.get("fps") or 30) + (m.get("segundos") or 0), 2)
    acta.write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                    encoding="utf-8")

    # y un .sha256 al lado, en el formato de `sha256sum -c`
    (video.parent / f"{video.name}.sha256").write_text(
        f"{dig}  {video.name}\n", encoding="utf-8")
    print(f"SELLO_MP4: {video.name} sha256={dig[:16]}... "
          f"({video.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
