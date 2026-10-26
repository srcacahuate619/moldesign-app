"""Conservative, local disk budget for Molcy frame sequences.

The bounds use 8-bit RGBA pixels before PNG compression.  This intentionally
overestimates ordinary output; a render must not fill the user's volume.
"""
from __future__ import annotations

import ast
import shutil
from pathlib import Path


GIB = 1024 ** 3
RESERVE_BYTES = GIB
ENCODE_BYTES = GIB // 2

# Same names, dimensions and durations as scripts/formatos in moldesign-molcy.
FORMATS: dict[str, tuple[int, int, int]] = {
    "previsualizacion": (720, 720, 90),
    "social_vertical": (1080, 1920, 360),
    "biblioteca": (1920, 1080, 681),
}
# The MolDesign outro closes EVERY video (3.6 s = 108 frames; 4.4 s = 132 at 30 fps): there is no format without it.
BRAND_FRAMES = {"previsualizacion": 108, "social_vertical": 108, "biblioteca": 132}
# What the engine's Formato uses when a format file does not set cierre_s (variables/formato.py: CIERRE_POR_DEFECTO_S).
ENGINE_DEFAULT_OUTRO_S = 3.6
# Worst-case retained cache for the two supported languages, per format/device.
BRAND_LANGUAGE_VARIANTS = 2


def validate_engine(engine: Path) -> None:
    """Refuse an engine whose format changed beyond the measured budget."""
    for name, expected in FORMATS.items():
        source = engine / "scripts" / "formatos" / f"{name}.py"
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        call = next((node.value for node in tree.body
                     if isinstance(node, ast.Assign) and
                     any(isinstance(target, ast.Name) and target.id == "FORMATO"
                         for target in node.targets) and isinstance(node.value, ast.Call)), None)
        if call is None:
            raise ValueError(f"No se pudo leer el formato Molcy {name}.")
        kwargs = {keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords
                  if keyword.arg in {"ancho", "alto", "fps", "segundos", "cierre_s"}}
        actual = (kwargs["ancho"], kwargs["alto"], round(kwargs["fps"] * kwargs["segundos"]))
        if actual != expected:
            raise ValueError(f"El formato Molcy {name} cambió; no se conoce su presupuesto de disco.")
        if round(kwargs["fps"] * kwargs.get("cierre_s", ENGINE_DEFAULT_OUTRO_S)) != BRAND_FRAMES[name]:
            raise ValueError(f"El cierre Molcy {name} cambió; no se conoce su presupuesto de disco.")


def required_bytes(format_name: str) -> int:
    """A GPU video (the only kind MolDesign renders since 2026-10-08; the CPU takes photos)."""
    width, height, frames = FORMATS[format_name]
    brand_frames = BRAND_FRAMES[format_name]  # the outro is mandatory in every video
    # Bound the title by a complete second sequence; the per-frame guard
    # also catches unexpected writes by other applications.
    # 4 bytes/pixel plus a small bound for scanline and DEFLATE overhead.
    main = (width * height * 4 + height + 65536) * frames
    title = (width * height * 4 + height + 65536) * frames
    brand = (width * height * 4 + height + 65536) * brand_frames * BRAND_LANGUAGE_VARIANTS
    return main + title + brand + ENCODE_BYTES + RESERVE_BYTES


def free_bytes(path: Path) -> int:
    parent = path
    while not parent.exists():
        if parent.parent == parent:
            raise OSError(f"No existe el volumen de salida: {path}")
        parent = parent.parent
    return shutil.disk_usage(parent).free


def budget(path: Path, format_name: str) -> dict[str, int | bool]:
    free = free_bytes(path)
    required = required_bytes(format_name)
    return {"libre_bytes": free, "necesario_bytes": required,
            "disponible": free >= required}


def assert_budget(path: Path, format_name: str) -> dict[str, int | bool]:
    result = budget(path, format_name)
    if not result["disponible"]:
        need = result["necesario_bytes"] / GIB
        free = result["libre_bytes"] / GIB
        raise OSError(f"Espacio insuficiente para Molcy: se reservan {need:.1f} GiB "
                      f"y hay {free:.1f} GiB libres en la unidad de salida.")
    return result


def assert_brand_budget(path: Path, format_name: str) -> None:
    """La caché del cierre puede estar en otra unidad distinta del caso."""
    width, height, _ = FORMATS[format_name]
    required = ((width * height * 4 + height + 65536) * BRAND_FRAMES[format_name]
                * BRAND_LANGUAGE_VARIANTS + ENCODE_BYTES + RESERVE_BYTES)
    free = free_bytes(path)
    if free < required:
        raise OSError(f"Espacio insuficiente en la unidad de la caché del cierre de MolDesign: "
                      f"se reservan {required / GIB:.1f} GiB y hay {free / GIB:.1f} GiB libres.")


# Photos: one frame at a time. The scene (.blend ~1 MB plus its Molecular Nodes session) and the thumbnails are small; what
# needs room is the photo itself while it is composed: the scene, the label layer and the composed PNG before and after the
# MolDesign mark, each bounded by its uncompressed 8-bit RGBA size.
PHOTO_SHORT_SIDE = {"720p": 720, "1080p": 1080, "1440p": 1440, "4k": 2160}
PHOTO_SCENE_BYTES = 64 * 1024 ** 2


def photo_required_bytes(resolution: str) -> int:
    short = PHOTO_SHORT_SIDE[resolution]
    long_ = short * 16 // 9
    frame = short * long_ * 4 + long_ + 65536
    return PHOTO_SCENE_BYTES + 4 * frame + RESERVE_BYTES


def photo_budget(path: Path, resolution: str) -> dict[str, int | bool]:
    free = free_bytes(path)
    required = photo_required_bytes(resolution)
    return {"libre_bytes": free, "necesario_bytes": required, "disponible": free >= required}


def assert_photo_budget(path: Path, resolution: str) -> dict[str, int | bool]:
    result = photo_budget(path, resolution)
    if not result["disponible"]:
        raise OSError(f"Espacio insuficiente para la foto: se reservan {result['necesario_bytes'] / GIB:.1f} GiB "
                      f"y hay {result['libre_bytes'] / GIB:.1f} GiB libres en la unidad de salida.")
    return result
