"""UNA FOTO: fotogramas sueltos de una escena ya construida, rendidos con Cycles.

    blender -b <escena>.blend --factory-startup --addons bl_ext.blender_org.molecularnodes \\
        --python foto.py -- --escena escena_fotos_X.json --fotogramas 42,253 \\
        --ancho 1920 --alto 1080 --muestras 128 --dispositivo gpu --salida <carpeta>

Abre el `.blend` que dejó `maestro.py --fotos`, con todo horneado: no vuelve a
montar la escena. Por cada fotograma deja `escena_<f>.png` (la escena, opaca) y,
si en ese instante se ve algún texto, `capa_<f>.png` (la capa de rótulos con
alfa, sin profundidad de campo), igual que el vídeo. Componerlas es cosa de
`correr_foto.py`.

Cycles en CPU y en GPU, con el mismo denoiser (OpenImageDenoise), la misma semilla
y el mismo muestreo: lo que cambia con el equipo es el tiempo, no la foto. Sin
desenfoque de movimiento: una foto es un instante quieto y una estela se leería
como un error. Sin sello: la marca la pone MolDesign sobre el PNG final.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

import bpy                                                      # noqa: E402

from salida import render                                       # noqa: E402
from variables.momentos import validar_fotograma                # noqa: E402

#: Tipos de dispositivo de Cycles, del preferido al último recurso. CUDA antes
#: que OptiX: en una GPU sin núcleos RT (GTX) OptiX no acelera nada y su primer
#: uso compila los núcleos; CUDA viaja precompilado.
PREFERENCIA_GPU = ("CUDA", "OPTIX", "HIP", "ONEAPI", "METAL")
#: Muestras de la capa de rótulos: es texto plano sobre transparente, sin denoiser
#: (el denoiser emborronaría los bordes de las letras).
MUESTRAS_CAPA = 32
#: Límites de sanidad; los de producto (720p a 4K) los pone quien llama.
LADO_MINIMO, LADO_MAXIMO = 64, 8192


def preparar_gpu() -> tuple[str | None, list[str]]:
    """Activa SÓLO las GPU del primer tipo de Cycles que tenga alguna. (tipo, nombres)."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for tipo in PREFERENCIA_GPU:
        try:
            prefs.compute_device_type = tipo
        except TypeError:          # este Blender no conoce el tipo (METAL fuera de macOS)
            continue
        prefs.get_devices_for_type(tipo)        # refresca la lista
        gpus = [d for d in prefs.devices if d.type == tipo]
        if not gpus:
            continue
        for d in prefs.devices:
            d.use = d.type == tipo
        return tipo, [d.name for d in gpus]
    prefs.compute_device_type = "NONE"
    return None, []


def configurar(dispositivo: str, ancho: int, alto: int, muestras: int) -> dict:
    """Cycles con el dispositivo pedido. Devuelve lo que se usará, para el acta."""
    sc = bpy.context.scene
    r = sc.render
    r.engine = "CYCLES"
    tipo, gpus = None, []
    if dispositivo == "gpu":
        tipo, gpus = preparar_gpu()
        if not tipo:
            # Pedir GPU y rendir en CPU sin decirlo sería una procedencia falsa.
            raise SystemExit("SIN_GPU_CYCLES: Cycles no encontró ninguna GPU utilizable")
        sc.cycles.device = "GPU"
    elif dispositivo == "cpu":
        bpy.context.preferences.addons["cycles"].preferences.compute_device_type = "NONE"
        sc.cycles.device = "CPU"
    else:
        raise SystemExit(f"DISPOSITIVO_DESCONOCIDO: {dispositivo}")
    from variables.cpu import hilos_cpu
    r.threads_mode = "FIXED"
    r.threads = hilos_cpu()
    sc.cycles.samples = muestras
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.01
    sc.cycles.seed = 0
    sc.cycles.use_animated_seed = False
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    if hasattr(sc.cycles, "denoising_use_gpu"):
        sc.cycles.denoising_use_gpu = dispositivo == "gpu"
    r.resolution_x, r.resolution_y, r.resolution_percentage = ancho, alto, 100
    r.use_motion_blur = False
    r.use_stamp = False
    r.film_transparent = False
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.color_depth = "8"
    cam = sc.camera
    return {"motor": r.engine, "blender": bpy.app.version_string,
            "dispositivo": "GPU" if dispositivo == "gpu" else "CPU",
            "tipo_gpu": tipo, "gpus": gpus, "muestras": muestras,
            "muestreo_adaptativo": True, "umbral_adaptativo": 0.01,
            "denoiser": sc.cycles.denoiser, "semilla": sc.cycles.seed,
            "hilos_cpu": r.threads, "resolucion": [ancho, alto],
            "rebotes": {"max": sc.cycles.max_bounces,
                        "transparencia": sc.cycles.transparent_max_bounces},
            "desenfoque_movimiento": False,
            "profundidad_de_campo": bool(cam and cam.data.dof.use_dof),
            "exposicion": round(sc.view_settings.exposure, 3),
            "muestras_capa": MUESTRAS_CAPA}


def con_texto(capa: dict | None, f: int) -> bool:
    return bool(capa) and any(a <= f <= b for a, b in capa["ventanas"])


def rendir(f: int, salida: Path, capa: dict | None) -> dict:
    """La escena y, si en `f` se ve algún texto, su capa de rótulos."""
    sc = bpy.context.scene
    render.comprobar_espacio(salida, sc.render.resolution_x, sc.render.resolution_y)
    sc.frame_set(f)
    escena = salida / f"escena_{f:04d}.png"
    escena.unlink(missing_ok=True)
    sc.render.filepath = str(escena.with_suffix(""))
    t = time.time()
    bpy.ops.render.render(write_still=True)
    out = {"fotograma": f, "escena": escena.name, "capa": None,
           "segundos_escena": round(time.time() - t, 2), "segundos_capa": 0.0}
    if not render.png_completo(escena):
        raise SystemExit(f"FOTO_SIN_PNG: el fotograma {f} no se escribió entero")
    if con_texto(capa, f):
        muestras, denoise = sc.cycles.samples, sc.cycles.use_denoising
        tmp = salida / f"_capa_{f:04d}"
        try:
            sc.cycles.samples, sc.cycles.use_denoising = MUESTRAS_CAPA, False
            t = time.time()
            render.pasada_titulo(tmp, capa["objetos"], (f, f), fotogramas=[f])
            out["segundos_capa"] = round(time.time() - t, 2)
        finally:
            sc.cycles.samples, sc.cycles.use_denoising = muestras, denoise
        hecho = tmp / f"f_{f:04d}.png"
        if hecho.is_file():
            destino = salida / f"capa_{f:04d}.png"
            destino.unlink(missing_ok=True)
            shutil.move(str(hecho), str(destino))
            out["capa"] = destino.name
        shutil.rmtree(tmp, ignore_errors=True)
        sc.frame_set(f)
    return out


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="foto")
    ap.add_argument("--escena", required=True, help="escena_fotos_*.json de maestro.py --fotos")
    ap.add_argument("--fotogramas", required=True, help="fotogramas fuente, separados por comas")
    ap.add_argument("--ancho", type=int, required=True)
    ap.add_argument("--alto", type=int, required=True)
    ap.add_argument("--muestras", type=int, required=True)
    ap.add_argument("--dispositivo", choices=("cpu", "gpu"), required=True)
    ap.add_argument("--salida", required=True, help="carpeta donde se dejan los PNG")
    a = ap.parse_args(argv)

    escena = json.loads(Path(a.escena).read_text(encoding="utf-8"))
    if escena.get("schema") != "molcy.fotos.escena/1":
        raise SystemExit("ESCENA_DESCONOCIDA: el acta no es de maestro.py --fotos")
    abierto = Path(bpy.data.filepath).name
    if abierto != escena["blend"]["nombre"]:
        raise SystemExit(f"BLEND_EQUIVOCADO: abierto {abierto!r}, el acta dice {escena['blend']['nombre']!r}")
    n = escena["fotogramas_fuente"]
    fotogramas = [validar_fotograma(int(x), n) for x in a.fotogramas.split(",") if x.strip()]
    if not fotogramas:
        raise SystemExit("SIN_FOTOGRAMAS")
    fw, fh = escena["formato"]["ancho"], escena["formato"]["alto"]
    if not (LADO_MINIMO <= min(a.ancho, a.alto) and max(a.ancho, a.alto) <= LADO_MAXIMO):
        raise SystemExit(f"RESOLUCION_FUERA_DE_LIMITES: {a.ancho}x{a.alto}")
    # Los rótulos se colocaron para el aspecto de la escena: otro aspecto los movería.
    if abs(a.ancho * fh - a.alto * fw) > 0.01 * a.alto * fw:
        raise SystemExit(f"ASPECTO_DISTINTO: {a.ancho}x{a.alto} no es {fw}x{fh}")
    if not 1 <= a.muestras <= 4096:
        raise SystemExit(f"MUESTRAS_FUERA_DE_LIMITES: {a.muestras}")

    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    ajustes = configurar(a.dispositivo, a.ancho, a.alto, a.muestras)
    print("FOTO_AJUSTES " + json.dumps(ajustes, ensure_ascii=False), flush=True)
    for f in fotogramas:
        hecho = rendir(f, salida, escena.get("capa"))
        print("FOTO_FOTOGRAMA " + json.dumps(hecho, ensure_ascii=False), flush=True)
    print("FOTO_LISTA", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
