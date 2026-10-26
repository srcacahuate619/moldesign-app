"""Render y limpieza. El formato manda; aqui solo se obedece."""
from __future__ import annotations

import shutil
import os
import time
from pathlib import Path

import bpy

#: Los ultimos 12 bytes de todo PNG entero: el trozo IEND. Un PNG cortado a
#: medio escribir (proceso muerto) no lo tiene.
_FIN_PNG = b"\x00\x00\x00\x00IEND\xaeB`\x82"
_ESPACIO_MINIMO = 1024 ** 3
#: Tipos de objeto con geometría que se rinde. Los rótulos son FONT y no están aquí.
_GEOMETRIA = frozenset({"MESH", "CURVE", "SURFACE", "META", "CURVES", "POINTCLOUD",
                        "VOLUME", "GREASEPENCIL"})


def comprobar_espacio(destino: Path, ancho: int, alto: int) -> None:
    """Aborta antes de escribir otro PNG si se consumió la reserva del volumen."""
    libre = shutil.disk_usage(destino).free
    siguiente = ancho * alto * 4 + alto + 65536
    if libre < _ESPACIO_MINIMO + siguiente:
        raise RuntimeError(
            f"ESPACIO_INSUFICIENTE: quedan {libre / 1024**3:.2f} GiB "
            f"en {destino}; se conserva 1 GiB para el sistema y la codificación"
        )


def configurar(formato, renderizador: str = "gpu") -> None:
    sc = bpy.context.scene
    if renderizador == "cpu":
        sc.render.engine = "CYCLES"
        sc.cycles.device = "CPU"
        sc.cycles.samples = formato.muestras
        sc.cycles.use_denoising = True
        from variables.cpu import hilos_cpu
        sc.render.threads_mode = "FIXED"
        sc.render.threads = hilos_cpu()
    elif renderizador == "gpu":
        sc.render.engine = "BLENDER_EEVEE"
    else:
        raise ValueError(f"Renderizador desconocido: {renderizador}")
    sc.render.resolution_x = formato.ancho
    sc.render.resolution_y = formato.alto
    sc.render.resolution_percentage = formato.escala_render
    sc.render.fps = formato.fps
    sc.eevee.taa_render_samples = formato.muestras
    sc.eevee.shadow_resolution_scale = formato.escala_sombras
    # Medido: 0.06 s/fotograma. A 72 grados/s son 2.4 grados por fotograma y
    # sin desenfoque la orbita estroboscopea, asi que sale gratis.
    sc.render.use_motion_blur = formato.desenfoque_movimiento
    if formato.desenfoque_movimiento:
        sc.render.motion_blur_shutter = formato.obturador
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "8"
    if hasattr(sc.render.image_settings, "media_type"):
        sc.render.image_settings.media_type = "IMAGE"


def ajustes() -> dict:
    """Lo que EEVEE va a usar de verdad, para el acta.

    Las muestras las pone el formato, pero las sombras, la GI y el trazado de
    rayos venian de la plantilla de arte y no constaban en ninguna parte:
    regenerar la plantilla podia cambiar el coste o el look sin dejar rastro.
    """
    sc = bpy.context.scene
    e, r = sc.eevee, sc.render
    cam = sc.camera
    base = {
        "motor": r.engine,
        "blender": bpy.app.version_string,
        "desenfoque_movimiento": r.use_motion_blur,
        "exposicion": round(sc.view_settings.exposure, 3),
        "obturador": round(r.motion_blur_shutter, 3),
        "profundidad_de_campo": bool(cam and cam.data.dof.use_dof),
        "resolucion": [r.resolution_x, r.resolution_y, r.resolution_percentage],
    }
    if r.engine == "CYCLES":
        base.update({"dispositivo": sc.cycles.device, "muestras": sc.cycles.samples,
                     "denoise": sc.cycles.use_denoising, "hilos_cpu": r.threads})
    else:
        base.update({"dispositivo": "GPU", "muestras": e.taa_render_samples,
                     "escala_sombras": round(e.shadow_resolution_scale, 3),
                     "sombras": e.use_shadows, "rayos_sombra": e.shadow_ray_count,
                     "pasos_sombra": e.shadow_step_count,
                     "trazado_de_rayos": e.use_raytracing, "gi_rapida": e.use_fast_gi})
    return base


def png_completo(ruta: Path) -> bool:
    """Existe y termina en IEND: no se quedo a medias al morir el proceso."""
    try:
        with open(ruta, "rb") as fh:
            fh.seek(-len(_FIN_PNG), 2)
            return fh.read() == _FIN_PNG
    except OSError:
        return False


def secuencia(destino: Path, frames, huella: str | None = None,
              cada: int = 50, fijos=()) -> dict:
    """Rinde la secuencia; si una corrida anterior quedo cortada, la retoma.

    `frames` son los fotogramas que el montaje usa (`variables/pausas.py`): una
    pausa repite un PNG y un tramo identico se salta, asi que no hay que rendir
    todos los del guion. `fijos` son los que el video congela: se rinden sin
    desenfoque de movimiento, porque una imagen quieta con estela se lee como
    un error (la camara de `x` sigue moviendose en el instante congelado).

    Solo se reaprovechan fotogramas de la MISMA construccion: `huella` resume
    el acta, el codigo y la plantilla (ver `maestro.huella_de_construccion`).
    Si la carpeta trae otra huella, o ninguna, se borra entera como antes:
    mezclar fotogramas de dos versiones del codigo daria un salto a mitad de
    video que nadie buscaria ahi.
    """
    sc = bpy.context.scene
    marca = destino / ".huella"
    if destino.exists():
        previa = marca.read_text(encoding="utf-8") if marca.exists() else None
        if huella is None or previa != huella:
            shutil.rmtree(destino)
    destino.mkdir(parents=True, exist_ok=True)
    if huella:
        marca.write_text(huella, encoding="utf-8")

    hechos = [f for f in frames if png_completo(destino / f"f_{f:04d}.png")]
    listos = set(hechos)
    pendientes = [f for f in frames if f not in listos]
    if hechos:
        print(f"RENDER_REANUDA: {len(hechos)}/{len(frames)} fotogramas ya "
              f"estaban hechos con la misma huella", flush=True)
    t0 = time.time()
    estela = getattr(sc.render, "use_motion_blur", False)
    fijos = set(fijos)
    try:
        for i, f in enumerate(pendientes):
            comprobar_espacio(destino, sc.render.resolution_x, sc.render.resolution_y)
            png = destino / f"f_{f:04d}.png"
            # Un PNG truncado se borra antes: reescribir encima de un archivo
            # existente daba «Could not open file» y Blender salia con codigo 0.
            png.unlink(missing_ok=True)
            sc.frame_set(f)
            if estela:
                sc.render.use_motion_blur = f not in fijos
            sc.render.filepath = str(destino / f"f_{f:04d}")
            bpy.ops.render.render(write_still=True)
            if i % cada == 0:
                print(f"RENDER {len(hechos) + i + 1}/{len(frames)}  "
                      f"{time.time() - t0:.0f}s", flush=True)
    finally:
        if estela:
            sc.render.use_motion_blur = True
    seg = time.time() - t0
    n = max(len(pendientes), 1)
    print(f"RENDER_LISTO {len(frames)} ({len(pendientes)} rendidos ahora) en "
          f"{seg:.0f}s ({seg / n:.2f} s/fotograma)", flush=True)
    return {"fotogramas": len(frames), "rendidos": len(pendientes),
            "reanudados": len(hechos), "segundos": round(seg, 1),
            "por_fotograma": round(seg / n, 3)}


def pasada_titulo(destino: Path, nombre_objeto, ventana,
                  cada: int = 50, fotogramas=None) -> dict:
    """Segunda pasada solo-titulo, con alfa, para componer por encima.

    El rotulo de pantalla se cuelga a la distancia de ENFOQUE del plano, que es
    la misma profundidad del receptor: cualquier geometria por delante lo tapa
    por test de profundidad y ahi no hay nada que hacer desde el material. Se
    rinde aparte —solo el rotulo, film transparente, sin profundidad de campo y
    sin sello— y `codificar.py` lo monta en un canal superior. Asi el titulo
    nunca lo tapa nada mientras exista, y ademas es la UNICA version que se ve:
    el pase principal lo esconde (`visible_camera=False`) porque su copia suave
    asomaria por los bordes y el texto se leeria borroso.

    Se rinden solo los fotogramas de su ventana: fuera de ella el rotulo ni
    existe. Con `fotogramas`, solo esos (los que el montaje usa y en los que
    algun texto se ve); `codificar.py` pone una capa vacia en los demas.
    """
    sc = bpy.context.scene
    cam = sc.camera
    nombres = {nombre_objeto} if isinstance(nombre_objeto, str) else set(nombre_objeto)
    objetos = [bpy.data.objects.get(n) for n in nombres]
    if not nombres or any(o is None for o in objetos):
        return {"fotogramas": 0, "razon": f"no existe {nombre_objeto}"}
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)

    a, b = int(ventana[0]), int(ventana[1])
    frames = [f for f in range(max(1, a), min(sc.frame_end, b) + 1)]
    if fotogramas is not None:
        pedidos = set(fotogramas)
        frames = [f for f in frames if f in pedidos]
    antes = {o.name: o.hide_render for o in bpy.data.objects}
    film = sc.render.film_transparent
    color = sc.render.image_settings.color_mode
    sello = sc.render.use_stamp
    visible = {o.name: o.visible_camera for o in objetos}
    dof = cam.data.dof.use_dof if cam else False
    estela = getattr(sc.render, "use_motion_blur", False)
    # Todo lo que se rinde y no es un rotulo. Antes sólo se apagaban las MALLAS, y
    # además con `hide_render`, que en el sujeto y en la caja está ANIMADO: la
    # animación se evalúa después de asignar la propiedad y gana, así que el
    # ligando (animado) y la caja (una curva) salían en la capa del título y,
    # por ir más cerca de la cámara que el rótulo, lo tapaban.
    ocultables = [o for o in bpy.data.objects
                  if o.type in _GEOMETRIA and o.name not in nombres]
    acciones: dict[str, tuple] = {}
    t0 = time.time()

    def apagar_geometria() -> None:
        for o in ocultables:
            datos = o.animation_data
            if datos is not None and datos.action is not None and o.name not in acciones:
                acciones[o.name] = (datos.action, getattr(datos, "action_slot", None))
                datos.action = None
            o.hide_render = True

    try:
        apagar_geometria()
        for o in objetos:
            o.visible_camera = True
        sc.render.film_transparent = True
        sc.render.use_stamp = False     # el sello ya va quemado en el principal
        if cam:
            cam.data.dof.use_dof = False
        # Sin estela: el texto de pantalla va pegado a la cámara (no tiene movimiento
        # relativo) y una etiqueta anclada sólo se ve con la imagen quieta. Así la
        # capa depende sólo del estado del texto y se puede reutilizar entre
        # fotogramas (`salida/firmas.py`).
        sc.render.use_motion_blur = False
        sc.render.image_settings.color_mode = "RGBA"
        for i, f in enumerate(frames):
            comprobar_espacio(destino, sc.render.resolution_x, sc.render.resolution_y)
            sc.frame_set(f)
            apagar_geometria()
            sc.render.filepath = str(destino / f"f_{f:04d}")
            bpy.ops.render.render(write_still=True)
            if i % cada == 0:
                print(f"TITULO_PASADA {i + 1}/{len(frames)}  "
                      f"{time.time() - t0:.0f}s", flush=True)
    finally:
        for nombre, (accion, ranura) in acciones.items():
            objeto = bpy.data.objects.get(nombre)
            if objeto is None or objeto.animation_data is None:
                continue
            objeto.animation_data.action = accion
            if ranura is not None:
                try:
                    objeto.animation_data.action_slot = ranura
                except (AttributeError, TypeError, RuntimeError):
                    pass
        for o in bpy.data.objects:
            if o.name in antes:
                o.hide_render = antes[o.name]
        for o in objetos:
            o.visible_camera = visible[o.name]
        sc.render.film_transparent = film
        sc.render.use_stamp = sello
        if cam:
            cam.data.dof.use_dof = dof
        sc.render.use_motion_blur = estela
        sc.render.image_settings.color_mode = color
    seg = time.time() - t0
    print(f"TITULO_LISTO {len(frames)} en {seg:.0f}s", flush=True)
    return {"carpeta": destino.name, "ventana": [a, b],
            "fotogramas": len(frames), "segundos": round(seg, 1)}
