"""EL CIERRE: la firma de MolDesign al final de cada video.

    blender -b --factory-startup --python scripts/marca/cierre.py -- --formato social_vertical
    blender -b --factory-startup --python scripts/marca/cierre.py -- --formato biblioteca --fotograma 60 --escala 50

Sustituye al sello de texto que se quemaba arriba («Video generado por MolDesign»)
por un cierre de verdad, rendido con el mismo EEVEE que el resto del video:

  1. Negro con motas en suspension (profundidad y bokeh).
  2. El emblema se materializa en RELIEVE como una onda de luz que nace del
     cerebro y recorre la red: la «ciencia» encendiendose.
  3. Siete anillos moleculares 3D vuelan a sus medallones y destellan al
     encajar, como un enlace que se forma.
  4. Un barrido de luz cruza el relieve y las letras.
  5. «MolDesign» se escribe con luz; debajo, el lema de la web y la direccion.

El emblema no se redibuja: es el logo del instalador de MolDesign desplazado por
un mapa de profundidad (`preparar_emblema.py`, Depth Anything V2), asi que la
marca es la de siempre pixel a pixel y aun asi tiene volumen, sombra y brillo.

Se rinde una vez por formato y se guarda con su huella en
`moldesign/assets/marca/cierre/<formato>/`. Con `--si-falta` no hace nada si la
huella coincide: el runner lo llama antes de cada encode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

AQUI = Path(__file__).resolve().parent
SCRIPTS = AQUI.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from marca.idioma import idioma_del_cierre, lema_del_idioma   # noqa: E402
from marca import medallones              # noqa: E402
from nucleo import horneado as H          # noqa: E402
from variables import formato as fmt      # noqa: E402
from salida.render import comprobar_espacio  # noqa: E402

MARCA = SCRIPTS.parent / "moldesign" / "assets" / "marca"

# ── identidad (de la web de MolDesign) ───────────────────────────────────
NOMBRE = ("Mol", "Design")
LEMA = lema_del_idioma()
WEB = "moldesign.amezcua-dev.com"


def _fuente_del_sistema(*candidatas: str) -> Path | None:
    """La primera fuente que exista en la carpeta de fuentes de Windows, o None.

    Sin suponer la unidad (`C:`) ni que una fuente opcional este instalada: Cascadia Mono viene con Windows Terminal y con Windows 11,
    no con todo Windows 10, y una fuente ausente hacia fallar el cierre de TODOS los videos. Con None el texto usa la fuente interna
    de Blender.
    """
    raiz = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if not raiz:
        return None
    for nombre in candidatas:
        ruta = Path(raiz) / "Fonts" / nombre
        if ruta.is_file():
            return ruta
    return None


#: Inter y JetBrains Mono no estan instaladas; la web cae a Segoe UI y Cascadia Mono, que son las que se ven de verdad en la app
#: de escritorio. Si faltan, las alternativas de siempre en Windows (Segoe UI -> Arial; Cascadia Mono -> Consolas -> Courier).
FUENTE_NOMBRE = _fuente_del_sistema("seguisb.ttf", "segoeui.ttf", "arial.ttf")
FUENTE_MONO = _fuente_del_sistema("CascadiaMono.ttf", "consola.ttf", "cour.ttf")
#: El degradado de la barra de progreso de MolDesign (#3b82f6 -> #8b5cf6).
AZUL, VIOLETA = "#3b82f6", "#8b5cf6"
BLANCO, GRIS, GRIS_TENUE = "#f4f4f5", "#a1a1aa", "#80808b"

# ── el emblema ───────────────────────────────────────────────────────────
ANCHO_EMBLEMA = 2.0          # unidades de Blender
RELIEVE = 0.17               # cuanto sale lo mas cercano, en unidades
PASO_MALLA = 2               # un vertice cada 2 px de la imagen
#: Donde BUSCAR los siete medallones (px de `emblema.png`, sentido horario desde
#: arriba). Centro, radio y giro exactos los mide `medallones.ajustar` sobre el
#: marco dibujado: a ojo se estimo un radio de 63 px y era de ~69, y el
#: medallon 3D quedaba desplazado sobre el del logo, con dos hexagonos a la vista.
MEDALLONES_PX = [(490, 92), (832, 282), (882, 505), (831, 746),
                 (150, 737), (88, 510), (152, 262)]
RADIO_HEX_PX = 66
#: Px de mas que se recortan alrededor del marco medido: el hueco se lleva la
#: linea del logo y su brillo, y el marco 3D (mas grueso) tapa el borde del corte.
CORTE_PX = 3.5
CEREBRO_PX = (490, 512)



# ── utilidades ───────────────────────────────────────────────────────────
def lineal(hexa: str) -> tuple[float, float, float, float]:
    h = hexa.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4) for v in c) + (1.0,)


def suave(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (x * 6 - 15) + 10)          # smootherstep


def sale(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3                              # ease-out cubico


def zocalo(coleccion, nombre: str, tipo: str = "RGBA"):
    """El zocalo con ese nombre Y ese tipo. El nodo Mix tiene un «A», un «B» y
    un «Result» por cada tipo de dato: por nombre solo, sale el de numero."""
    return next(z for z in coleccion if z.name == nombre and z.type == tipo)


def leer_imagen(ruta: Path, no_color: bool) -> np.ndarray:
    img = bpy.data.images.load(str(ruta))
    if no_color:
        img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    return buf.reshape(h, w, 4)[::-1]                     # filas de arriba abajo


def imagen_desde(valores: np.ndarray, nombre: str):
    """Una imagen de Blender (datos, no color) a partir de un array de filas de
    arriba abajo. Para la transparencia del emblema con los huecos."""
    alto, ancho = valores.shape
    img = bpy.data.images.new(nombre, ancho, alto, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    rgba = np.ones((alto, ancho, 4), dtype=np.float32)
    rgba[..., :3] = valores[::-1, :, None]
    img.pixels.foreach_set(rgba.ravel())
    return img


class Lienzo:
    """Pixeles de `emblema.png` -> coordenadas del mundo (plano XZ, mira a -Y)."""

    def __init__(self, ancho_px: int, alto_px: int, origen: Vector):
        self.w, self.h = ancho_px, alto_px
        self.escala = ANCHO_EMBLEMA / ancho_px
        self.alto = alto_px * self.escala
        self.origen = origen

    def mundo(self, px: float, py: float, y: float = 0.0) -> Vector:
        return self.origen + Vector(((px - self.w / 2) * self.escala, y,
                                     (self.h / 2 - py) * self.escala))


# ── escena ───────────────────────────────────────────────────────────────
def escena_vacia(formato, n: int, muestras: int, escala: int,
                renderizador: str = "gpu") -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES" if renderizador == "cpu" else "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = formato.ancho, formato.alto
    sc.render.resolution_percentage = escala
    sc.render.fps = formato.fps
    sc.frame_start, sc.frame_end = 1, n
    if renderizador == "cpu":
        sc.cycles.device = "CPU"
        sc.cycles.samples = muestras
        sc.cycles.use_denoising = True
        from variables.cpu import hilos_cpu
        sc.render.threads_mode = "FIXED"
        sc.render.threads = hilos_cpu()
    else:
        sc.eevee.taa_render_samples = muestras
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "8"
    sc.render.image_settings.color_mode = "RGB"
    # Standard y no AgX: los colores del emblema son la marca y AgX los lava.
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    w = bpy.data.worlds.new("Cierre_Mundo")
    sc.world = w
    w.use_nodes = True
    fondo = w.node_tree.nodes["Background"]
    fondo.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    fondo.inputs["Strength"].default_value = 0.0


def compositor() -> None:
    """Bloom. En Blender 5 el compositor es un grupo que se alimenta con un nodo
    Render Layers DENTRO del grupo; cablearlo desde la entrada del grupo lo deja
    en blanco (es lo que tumbo el denoise en `nucleo/arte.py`)."""
    sc = bpy.context.scene
    g = bpy.data.node_groups.new("Cierre_Compositor", "CompositorNodeTree")
    g.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = g.nodes.new("CompositorNodeRLayers")
    gl = g.nodes.new("CompositorNodeGlare")
    gl.inputs["Type"].default_value = "Bloom"
    gl.inputs["Threshold"].default_value = 0.85
    gl.inputs["Strength"].default_value = 0.38
    gl.inputs["Size"].default_value = 0.6
    sal = g.nodes.new("NodeGroupOutput")
    g.links.new(rl.outputs["Image"], gl.inputs["Image"])
    g.links.new(gl.outputs["Image"], sal.inputs[0])
    sc.compositing_node_group = g
    sc.render.use_compositing = True


def material_basico(nombre: str, color, emision: float = 0.0, rugosidad: float = 0.3,
                    capa: float = 0.0):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = color
    bs.inputs["Roughness"].default_value = rugosidad
    bs.inputs["Coat Weight"].default_value = capa
    bs.inputs["Emission Color"].default_value = color
    bs.inputs["Emission Strength"].default_value = emision
    return m, bs


# ── el relieve del emblema ───────────────────────────────────────────────
def relieve(lienzo: Lienzo, color_px: np.ndarray, alfa: np.ndarray, prof: np.ndarray):
    h, w = alfa.shape
    xs = np.arange(0, w, PASO_MALLA)
    ys = np.arange(0, h, PASO_MALLA)
    gx, gy = np.meshgrid(xs, ys)
    a = alfa[gy, gx]
    d = prof[gy, gx]
    X = (gx - w / 2) * lienzo.escala + lienzo.origen.x
    Z = (h / 2 - gy) * lienzo.escala + lienzo.origen.z
    Y = -d * RELIEVE + lienzo.origen.y
    co = np.stack([X, Y, Z], axis=-1).reshape(-1, 3)
    nx = len(xs)
    idx = np.arange(len(ys) * nx).reshape(len(ys), nx)
    v00, v10 = idx[:-1, :-1], idx[:-1, 1:]
    v01, v11 = idx[1:, :-1], idx[1:, 1:]
    amax = np.maximum.reduce([a[:-1, :-1], a[:-1, 1:], a[1:, :-1], a[1:, 1:]])
    vivo = amax > 0.03
    caras = np.stack([v00[vivo], v01[vivo], v11[vivo], v10[vivo]], axis=-1)
    usados = np.unique(caras)
    remap = -np.ones(len(co), dtype=np.int64)
    remap[usados] = np.arange(len(usados))
    me = bpy.data.meshes.new("Emblema")
    me.from_pydata(co[usados].tolist(), [], remap[caras].tolist())
    uv = np.stack([gx / (w - 1), 1 - gy / (h - 1)], axis=-1).reshape(-1, 2)[usados]
    capa_uv = me.uv_layers.new(name="UV")
    bucles = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get("vertex_index", bucles)
    capa_uv.data.foreach_set("uv", uv[bucles].astype(np.float32).ravel())
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), dtype=bool))
    me.update()
    ob = bpy.data.objects.new("Emblema", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def material_emblema(lienzo: Lienzo, imagen_alfa) -> tuple:
    """El logo tal cual, con una onda de revelado que sale del cerebro.
    `imagen_alfa` ya trae los huecos de los medallones: los pone el 3D."""
    m = bpy.data.materials.new("Emblema")
    m.use_nodes = True
    m.surface_render_method = "DITHERED"
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bs = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord")
    tex = N.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(MARCA / "emblema.png"))
    tex.interpolation = "Cubic"
    tal = N.new("ShaderNodeTexImage")
    tal.image = imagen_alfa
    L.new(tc.outputs["UV"], tex.inputs["Vector"])
    L.new(tc.outputs["UV"], tal.inputs["Vector"])

    # distancia al cerebro en el plano del emblema
    geo = N.new("ShaderNodeNewGeometry")
    centro = lienzo.mundo(*CEREBRO_PX)
    resta = N.new("ShaderNodeVectorMath"); resta.operation = "SUBTRACT"
    resta.inputs[1].default_value = (centro.x, 0.0, centro.z)
    plano = N.new("ShaderNodeVectorMath"); plano.operation = "MULTIPLY"
    plano.inputs[1].default_value = (1.0, 0.0, 1.0)
    largo = N.new("ShaderNodeVectorMath"); largo.operation = "LENGTH"
    L.new(geo.outputs["Position"], resta.inputs[0])
    L.new(resta.outputs[0], plano.inputs[0])
    L.new(plano.outputs[0], largo.inputs[0])

    frente = N.new("ShaderNodeValue"); frente.name = "Frente"
    atras = N.new("ShaderNodeMath"); atras.operation = "SUBTRACT"
    atras.inputs[1].default_value = 0.28
    L.new(frente.outputs[0], atras.inputs[0])
    onda = N.new("ShaderNodeMapRange"); onda.interpolation_type = "SMOOTHSTEP"
    onda.inputs["To Min"].default_value = 1.0
    onda.inputs["To Max"].default_value = 0.0
    L.new(largo.outputs["Value"], onda.inputs["Value"])
    L.new(atras.outputs[0], onda.inputs["From Min"])
    L.new(frente.outputs[0], onda.inputs["From Max"])
    # borde = 4 r (1 - r): vale 1 justo en el frente de la onda
    uno_menos = N.new("ShaderNodeMath"); uno_menos.operation = "SUBTRACT"
    uno_menos.inputs[0].default_value = 1.0
    L.new(onda.outputs["Result"], uno_menos.inputs[1])
    borde = N.new("ShaderNodeMath"); borde.operation = "MULTIPLY"
    L.new(onda.outputs["Result"], borde.inputs[0]); L.new(uno_menos.outputs[0], borde.inputs[1])

    alfa = N.new("ShaderNodeMath"); alfa.operation = "MULTIPLY"
    L.new(tal.outputs["Color"], alfa.inputs[0]); L.new(onda.outputs["Result"], alfa.inputs[1])
    L.new(alfa.outputs[0], bs.inputs["Alpha"])

    # color: el logo; en el frente de la onda se tiñe de cian y brilla
    cian = N.new("ShaderNodeMix"); cian.data_type = "RGBA"; cian.blend_type = "ADD"
    zocalo(cian.inputs, "B").default_value = lineal("#67e8f9")
    tinte = N.new("ShaderNodeMath"); tinte.operation = "MULTIPLY"
    tinte.inputs[1].default_value = 3.0
    L.new(borde.outputs[0], tinte.inputs[0])
    L.new(tinte.outputs[0], zocalo(cian.inputs, "Factor", "VALUE"))
    L.new(tex.outputs["Color"], zocalo(cian.inputs, "A"))
    oscuro = N.new("ShaderNodeMix"); oscuro.data_type = "RGBA"; oscuro.blend_type = "MULTIPLY"
    zocalo(oscuro.inputs, "Factor", "VALUE").default_value = 1.0
    zocalo(oscuro.inputs, "B").default_value = (0.35, 0.35, 0.35, 1.0)
    L.new(tex.outputs["Color"], zocalo(oscuro.inputs, "A"))
    L.new(zocalo(oscuro.outputs, "Result"), bs.inputs["Base Color"])
    L.new(zocalo(cian.outputs, "Result"), bs.inputs["Emission Color"])
    brillo = N.new("ShaderNodeValue"); brillo.name = "Brillo"
    fuerza = N.new("ShaderNodeMath"); fuerza.operation = "MULTIPLY_ADD"
    fuerza.inputs[1].default_value = 7.0
    L.new(borde.outputs[0], fuerza.inputs[0]); L.new(brillo.outputs[0], fuerza.inputs[2])
    L.new(fuerza.outputs[0], bs.inputs["Emission Strength"])
    bs.inputs["Roughness"].default_value = 0.3
    bs.inputs["Coat Weight"].default_value = 0.7
    bs.inputs["Coat Roughness"].default_value = 0.06
    bs.inputs["Specular IOR Level"].default_value = 0.4
    return m, frente, brillo


# ── anillos moleculares 3D ───────────────────────────────────────────────
def _cilindro(bm, a: Vector, b: Vector, r: float, lados: int = 12) -> None:
    import bmesh
    v = b - a
    largo = v.length
    if largo < 1e-6:
        return
    rot = Vector((0, 0, 1)).rotation_difference(v.normalized()).to_matrix().to_4x4()
    M = Matrix.Translation((a + b) / 2) @ rot
    bmesh.ops.create_cone(bm, cap_ends=True, segments=lados, radius1=r, radius2=r,
                          depth=largo, matrix=M)


def _esfera(bm, c: Vector, r: float) -> None:
    import bmesh
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=r,
                              matrix=Matrix.Translation(c))


def _en_plano(angulo: float, radio: float) -> Vector:
    """Punto del plano XZ local (mirando a -Y) a ese angulo en grados."""
    return Vector((radio * math.cos(math.radians(angulo)), 0,
                   radio * math.sin(math.radians(angulo))))


def medallon(nombre: str, r: float, color_linea, color_placa):
    """El medallon del logo, en 3D: SUSTITUYE al dibujado (que se recorta del
    relieve), asi que copia su anatomia medida sobre la imagen:

    - hexagono con un vertice arriba, marco cian de ~0.055 r y un nodo
      brillante de ~0.11 r en cada vertice;
    - benceno de bolas y varillas (anillo a 0.37 r) con seis sustituyentes que
      llegan a 0.66 r;
    - placa de vidrio azul marino detras, del color de relleno del propio logo.

    Todo en el plano XZ local, mirando a -Y. La placa es un objeto hijo: vuela
    con el medallon pero lleva su propio material, que no destella.
    """
    import bmesh
    bm = bmesh.new()
    R, R2 = r * 0.37, r * 0.66
    atomos = [_en_plano(90 + 60 * k, R) for k in range(6)]
    for k, p in enumerate(atomos):
        _esfera(bm, p, r * 0.085)
        _cilindro(bm, p, atomos[(k + 1) % 6], r * 0.03)
        q = p * (R2 / R)
        _cilindro(bm, p, q, r * 0.026)
        _esfera(bm, q, r * 0.075)
    marco = [_en_plano(90 + 60 * k, r) for k in range(6)]
    for k, p in enumerate(marco):
        _cilindro(bm, p, marco[(k + 1) % 6], r * 0.055, 10)
        _esfera(bm, p, r * 0.11)
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), dtype=bool))
    ob = bpy.data.objects.new(nombre, me)
    bpy.context.scene.collection.objects.link(ob)
    m, bs = material_basico(f"{nombre}_mat", color_linea, 0.0, rugosidad=0.18, capa=1.0)
    bs.inputs["Base Color"].default_value = tuple(c * 0.25 for c in color_linea[:3]) + (1.0,)
    ob.data.materials.append(m)

    # placa: prisma hexagonal fino, un poco por detras del benceno
    bm = bmesh.new()
    # create_cone ya pone los vertices a 30, 90, 150...: con el giro a XZ queda
    # uno arriba, como el marco. (Un giro extra de 30 grados lo dejaba plano.)
    M = Matrix.Translation((0, r * 0.1, 0)) @ Matrix.Rotation(math.radians(90), 4, "X")
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=r * 0.99,
                          radius2=r * 0.99, depth=r * 0.05, matrix=M)
    mp = bpy.data.meshes.new(f"{nombre}_placa")
    bm.to_mesh(mp)
    bm.free()
    placa = bpy.data.objects.new(f"{nombre}_placa", mp)
    bpy.context.scene.collection.objects.link(placa)
    placa.parent = ob
    placa.matrix_parent_inverse = Matrix.Identity(4)
    # Barniz leve: con capa 1.0 la placa reflejaba la luz clave entera y salia
    # gris claro en vez del azul marino del logo.
    mat_placa, bp = material_basico(f"{nombre}_placa_mat", color_placa, 0.6,
                                    rugosidad=0.4, capa=0.25)
    bp.inputs["Coat Roughness"].default_value = 0.12
    bp.inputs["Specular IOR Level"].default_value = 0.2
    placa.data.materials.append(mat_placa)
    return ob, m


# ── texto ────────────────────────────────────────────────────────────────
def texto(nombre: str, cuerpo: str, fuente: Path | None, tam: float, extrusion: float,
          bisel: float, alinear: str = "CENTER", espaciado: float = 1.0):
    cu = bpy.data.curves.new(nombre, "FONT")
    cu.body = cuerpo
    if fuente is not None:                    # sin fuente del sistema, la interna de Blender
        cu.font = bpy.data.fonts.load(str(fuente), check_existing=True)
    cu.size = tam
    cu.extrude = extrusion
    cu.bevel_depth = bisel
    cu.bevel_resolution = 3
    cu.align_x = alinear
    cu.align_y = "CENTER"
    cu.space_character = espaciado
    ob = bpy.data.objects.new(nombre, cu)
    ob.rotation_euler = (math.radians(90), 0, 0)      # del plano XY al XZ, mirando a -Y
    bpy.context.scene.collection.objects.link(ob)
    return ob


def material_escritura(nombre: str, colores: tuple, emision: float, frente_nodo_nombre: str):
    """Material de letra con revelado de izquierda a derecha y un filo de luz."""
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    m.surface_render_method = "DITHERED"
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bs = N["Principled BSDF"]
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs["Vector"])
    frente = N.new("ShaderNodeValue"); frente.name = frente_nodo_nombre
    atras = N.new("ShaderNodeMath"); atras.operation = "SUBTRACT"
    atras.inputs[1].default_value = 0.22
    L.new(frente.outputs[0], atras.inputs[0])
    rev = N.new("ShaderNodeMapRange"); rev.interpolation_type = "SMOOTHSTEP"
    rev.inputs["To Min"].default_value = 1.0
    rev.inputs["To Max"].default_value = 0.0
    L.new(sep.outputs["X"], rev.inputs["Value"])
    L.new(atras.outputs[0], rev.inputs["From Min"])
    L.new(frente.outputs[0], rev.inputs["From Max"])
    uno = N.new("ShaderNodeMath"); uno.operation = "SUBTRACT"; uno.inputs[0].default_value = 1.0
    L.new(rev.outputs["Result"], uno.inputs[1])
    borde = N.new("ShaderNodeMath"); borde.operation = "MULTIPLY"
    L.new(rev.outputs["Result"], borde.inputs[0]); L.new(uno.outputs[0], borde.inputs[1])
    if len(colores) == 1:
        col = N.new("ShaderNodeRGB"); col.outputs[0].default_value = colores[0]
        salida_color = col.outputs[0]
    else:
        # degradado en X de mundo, como la barra de progreso de MolDesign
        rampa = N.new("ShaderNodeValToRGB")
        rampa.color_ramp.elements[0].color = colores[0]
        rampa.color_ramp.elements[1].color = colores[1]
        mr = N.new("ShaderNodeMapRange")
        mr.name = "Degradado"
        L.new(sep.outputs["X"], mr.inputs["Value"])
        L.new(mr.outputs["Result"], rampa.inputs["Fac"])
        salida_color = rampa.outputs["Color"]
    L.new(salida_color, bs.inputs["Base Color"])
    L.new(salida_color, bs.inputs["Emission Color"])
    fuerza = N.new("ShaderNodeMath"); fuerza.operation = "MULTIPLY_ADD"
    fuerza.inputs[1].default_value = 12.0
    fuerza.inputs[2].default_value = emision
    L.new(borde.outputs[0], fuerza.inputs[0])
    L.new(fuerza.outputs[0], bs.inputs["Emission Strength"])
    L.new(rev.outputs["Result"], bs.inputs["Alpha"])
    bs.inputs["Roughness"].default_value = 0.22
    bs.inputs["Coat Weight"].default_value = 0.8
    return m


# ── composicion y animacion ──────────────────────────────────────────────
def construir(formato, segundos: float, muestras: int, escala: int,
              renderizador: str = "gpu") -> int:
    n = int(round(segundos * formato.fps))
    frames = list(range(1, n + 1))
    t_de = lambda f: (f - 1) / max(n - 1, 1)                     # noqa: E731
    escena_vacia(formato, n, muestras, escala, renderizador)
    compositor()
    sc = bpy.context.scene
    rng = random.Random(1618)

    color_px = leer_imagen(MARCA / "emblema.png", no_color=False)
    alfa = leer_imagen(MARCA / "emblema_alfa.png", no_color=True)[..., 0]
    prof = leer_imagen(MARCA / "emblema_profundidad.png", no_color=True)[..., 0]
    alto_px, ancho_px = alfa.shape

    vertical = formato.alto > formato.ancho
    alto_emb = ANCHO_EMBLEMA * alto_px / ancho_px
    if vertical:
        origen = Vector((0.0, 0.0, 0.58))
        centro_bloque = Vector((0.0, 0.0, -0.10))
        z_nombre = origen.z - alto_emb / 2 - 0.34
        x_texto, alinear = 0.0, "CENTER"
        # en un movil: el lema tiene que leerse sin acercarse la pantalla
        tam_nombre, tam_lema, tam_web = 0.46, 0.086, 0.07
        z_lema, z_web = z_nombre - 0.38, z_nombre - 0.58
        semiancho = 1.26
    else:
        # emblema a la izquierda, texto a la derecha, y el conjunto centrado
        origen = Vector((-1.18, 0.0, 0.0))
        centro_bloque = Vector((-0.2, 0.0, 0.0))
        z_nombre = 0.22
        x_texto, alinear = 0.12, "LEFT"
        tam_nombre, tam_lema, tam_web = 0.62, 0.086, 0.07
        z_lema, z_web = z_nombre - 0.44, z_nombre - 0.64
        semiancho = 2.25
    lienzo = Lienzo(ancho_px, alto_px, origen)

    # Los medallones se MIDEN sobre el marco dibujado, y el relieve se queda con
    # un hueco donde estaban: los pone el 3D. Hueco y medallon 3D salen de los
    # mismos numeros, asi que no puede haber dos hexagonos a la vista.
    brillo = color_px[..., :3].max(axis=2)
    hexes = [medallones.ajustar(brillo, c, RADIO_HEX_PX) for c in MEDALLONES_PX]
    hueco = np.zeros(alfa.shape, dtype=bool)
    for h in hexes:
        hueco |= medallones.dentro(ancho_px, alto_px, h, margen=CORTE_PX)
        print(f"MEDALLON: centro ({h['cx']:.1f}, {h['cy']:.1f}) px, radio {h['r']:.1f} px, "
              f"giro {h['giro']:+.1f}, contraste {h['contraste']}")
    alfa_hueco = np.where(hueco, 0.0, alfa).astype(np.float32)

    # relieve
    emb = relieve(lienzo, color_px, alfa_hueco, prof)
    m_emb, nodo_frente, nodo_brillo = material_emblema(
        lienzo, imagen_desde(alfa_hueco, "Emblema_Alfa_Huecos"))
    emb.data.materials.append(m_emb)
    nt = m_emb.node_tree
    # la onda sale del cerebro en 0.06-0.50 y el emblema se asienta a brillo 1
    H.hornear(nt, 'nodes["Frente"].outputs[0].default_value', -1, frames,
              [-0.3 + 2.1 * suave((t_de(f) - 0.06) / 0.46) for f in frames])
    H.hornear(nt, 'nodes["Brillo"].outputs[0].default_value', -1, frames,
              [0.55 + 0.45 * suave((t_de(f) - 0.2) / 0.4) for f in frames])

    def a_lineal(c: np.ndarray) -> np.ndarray:
        return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

    # medallones 3D: aterrizan cuando la onda llega a su sitio y se quedan
    for i, h in enumerate(hexes):
        px, py = h["cx"], h["cy"]
        dentro_i = medallones.dentro(ancho_px, alto_px, h)
        interior = medallones.dentro(ancho_px, alto_px, h, margen=-0.15 * h["r"])
        rgb = color_px[..., :3]
        # linea: lo brillante del medallon, a lineal y llevado al maximo
        linea = rgb[dentro_i & (brillo > 0.5)]
        lin = a_lineal(linea.mean(axis=0) if len(linea) else np.array([0.3, 0.75, 1.0]))
        lin = np.clip(lin / max(lin.max(), 1e-3), 0, 1)
        color_linea = (float(lin[0]), float(lin[1]), float(lin[2]), 1.0)
        # placa: el relleno azul marino (ni fondo negro ni lineas)
        fondo = rgb[interior & (brillo > 0.04) & (brillo < 0.35)]
        pl = a_lineal(np.median(fondo, axis=0) if len(fondo) else np.array([0.07, 0.13, 0.25]))
        color_placa = (float(pl[0]), float(pl[1]), float(pl[2]), 1.0)
        ob, m = medallon(f"Medallon_{i}", h["r"] * lienzo.escala, color_linea, color_placa)
        y_placa = -float(np.median(prof[dentro_i])) * RELIEVE
        final = lienzo.mundo(px, py, y_placa - 0.02)
        fuera = (final - lienzo.mundo(*CEREBRO_PX)).normalized()
        inicio = final + fuera * rng.uniform(0.7, 1.1) + Vector((0, -rng.uniform(1.4, 2.2), 0)) \
            + Vector((rng.uniform(-0.2, 0.2), 0, rng.uniform(-0.2, 0.2)))
        # giro medido en la imagen (antihorario en pantalla) = giro sobre -Y
        giro_final = [0.0, -math.radians(h["giro"]), 0.0]
        giro0 = [giro_final[e] + rng.uniform(-2.6, 2.6) for e in range(3)]
        t_llega = 0.20 + 0.035 * i
        t_sale = t_llega - 0.24
        pos, rot, esc, emi = [], [], [], []
        for f in frames:
            u = (t_de(f) - t_sale) / (t_llega - t_sale)
            k = sale(u)
            pos.append(inicio.lerp(final, k))
            rot.append([g0 + (gf - g0) * k for g0, gf in zip(giro0, giro_final)])
            esc.append(0.0 if u <= 0 else 0.55 + 0.45 * k)
            despues = t_de(f) - t_llega
            if u <= 0:
                e = 0.0
            elif despues < 0:
                e = 2.5 * k
            else:                                        # destello al encajar
                e = 2.2 + 16.0 * math.exp(-despues / 0.035)
            emi.append(e)
        for eje in range(3):
            H.hornear(ob, "location", eje, frames, [p[eje] for p in pos])
            H.hornear(ob, "rotation_euler", eje, frames, [r[eje] for r in rot])
            H.hornear(ob, "scale", eje, frames, esc)
        bs = m.node_tree.nodes["Principled BSDF"]
        idx = list(bs.inputs).index(bs.inputs["Emission Strength"])
        H.hornear(m.node_tree, f'nodes["{bs.name}"].inputs[{idx}].default_value', -1, frames, emi)

    # motas en suspension: dan profundidad y el bokeh del desenfoque
    malla_mota = bpy.data.meshes.new("Mota")
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    bm.to_mesh(malla_mota); bm.free()
    tonos = [lineal("#67e8f9"), lineal("#a78bfa"), lineal("#93c5fd"), lineal("#f4f4f5")]
    mats_mota = [material_basico(f"Mota_{k}", c, 1.1)[0] for k, c in enumerate(tonos)]
    for k in range(170):
        ob = bpy.data.objects.new(f"Mota_{k}", malla_mota.copy())
        ob.data.materials.append(mats_mota[k % len(mats_mota)])
        bpy.context.scene.collection.objects.link(ob)
        r = rng.uniform(0.004, 0.013)
        ob.scale = (r, r, r)
        x = rng.uniform(-semiancho * 1.5, semiancho * 1.5)
        # Delante del plano solo en los bordes del cuadro: una mota delante de
        # una letra del lema la tapaba. El resto, detras del emblema.
        y = rng.uniform(-1.6, -0.3) if abs(x - centro_bloque.x) > semiancho * 0.95 \
            else rng.uniform(0.35, 3.5)
        p0 = Vector((x, y, centro_bloque.z + rng.uniform(-2.4, 2.4)))
        deriva = Vector((rng.uniform(-0.06, 0.06), rng.uniform(-0.05, 0.05), rng.uniform(0.08, 0.22)))
        for eje in range(3):
            H.hornear(ob, "location", eje, [1, n], [p0[eje], p0[eje] + deriva[eje]])

    # nombre, lema y direccion
    col_mol = lineal(BLANCO)
    m_mol = material_escritura("Nombre_Mol", (col_mol,), 1.1, "Frente")
    m_des = material_escritura("Nombre_Design", (lineal(AZUL), lineal(VIOLETA)), 1.3, "Frente")
    nombre = texto("Nombre", "".join(NOMBRE), FUENTE_NOMBRE, tam_nombre, 0.018, 0.004, alinear)
    nombre.location = (x_texto, -0.02, z_nombre)
    nombre.data.materials.append(m_mol)
    nombre.data.materials.append(m_des)
    for i in range(len(NOMBRE[0]), len(NOMBRE[0]) + len(NOMBRE[1])):
        nombre.data.body_format[i].material_index = 1
    bpy.context.view_layer.update()
    xs = [(nombre.matrix_world @ Vector(c)).x for c in nombre.bound_box]
    x0, x1 = min(xs), max(xs)
    mr = m_des.node_tree.nodes["Degradado"]
    mr.inputs["From Min"].default_value = x0 + (x1 - x0) * 0.33
    mr.inputs["From Max"].default_value = x1
    for m in (m_mol, m_des):
        H.hornear(m.node_tree, 'nodes["Frente"].outputs[0].default_value', -1, frames,
                  [x0 - 0.3 + (x1 - x0 + 0.6) * suave((t_de(f) - 0.52) / 0.24) for f in frames])

    for nombre_obj, cuerpo, tam, z, color, t0 in (
            ("Lema", LEMA, tam_lema, z_lema, lineal(GRIS), 0.66),
            ("Web", WEB, tam_web, z_web, lineal(GRIS_TENUE), 0.72)):
        ob = texto(nombre_obj, cuerpo, FUENTE_MONO, tam, 0.0015, 0.0, alinear, 1.1)
        ob.location = (x_texto, -0.02, z)
        m = material_escritura(f"{nombre_obj}_mat", (color,), 0.9, "Frente")
        ob.data.materials.append(m)
        bpy.context.view_layer.update()
        xs = [(ob.matrix_world @ Vector(c)).x for c in ob.bound_box]
        a0, a1 = min(xs), max(xs)
        H.hornear(m.node_tree, 'nodes["Frente"].outputs[0].default_value', -1, frames,
                  [a0 - 0.3 + (a1 - a0 + 0.6) * suave((t_de(f) - t0) / 0.18) for f in frames])

    # luces: clave suave, contraluz cian y un barrido que cruza la escena
    def luz(nombre_luz, tipo, energia, color, pos, mira, tam=1.0, tam_y=None, difusa=1.0):
        d = bpy.data.lights.new(nombre_luz, tipo)
        d.energy, d.color = energia, color
        d.diffuse_factor = difusa
        if tipo == "AREA":
            d.shape = "RECTANGLE"
            d.size, d.size_y = tam, tam_y or tam
        ob = bpy.data.objects.new(nombre_luz, d)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = pos
        ob.rotation_euler = (Vector(mira) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        return ob
    luz("Clave", "AREA", 260, (1.0, 0.97, 0.94), (-2.2, -3.2, 2.6), centro_bloque, 2.5)
    luz("Contra", "AREA", 220, (0.55, 0.9, 1.0), (2.6, 1.8, 1.8), centro_bloque, 2.0)
    # Solo especular: un brillo que cruza el barniz del relieve y el bisel de las
    # letras. Con difusa quemaba el cerebro a blanco.
    barrido = luz("Barrido", "AREA", 520, (1.0, 1.0, 1.0), (0, -1.6, centro_bloque.z),
                  (0, 1, centro_bloque.z), 0.3, 8.0, difusa=0.0)
    # en diagonal: una franja vertical se lee como un escaner; inclinada, como luz
    barrido.rotation_euler.rotate_axis("Z", math.radians(28))
    H.hornear(barrido, "location", 0, frames,
              [-semiancho * 1.6 + semiancho * 3.2 * suave((t_de(f) - 0.40) / 0.36) for f in frames])

    # camara: llega de lado y de mas lejos, y se asienta de frente
    objetivo = bpy.data.objects.new("Cierre_Objetivo", None)
    objetivo.location = centro_bloque + Vector((0, -0.05, 0))
    bpy.context.scene.collection.objects.link(objetivo)
    cd = bpy.data.cameras.new("Cierre_Camara")
    cd.lens, cd.sensor_width, cd.sensor_fit = 50.0, 36.0, "HORIZONTAL"
    cd.clip_start, cd.clip_end = 0.05, 100.0
    cd.dof.use_dof = True
    cd.dof.focus_object = objetivo
    cam = bpy.data.objects.new("Cierre_Camara", cd)
    bpy.context.scene.collection.objects.link(cam)
    sc.camera = cam
    c = cam.constraints.new("TRACK_TO")
    c.target, c.track_axis, c.up_axis = objetivo, "TRACK_NEGATIVE_Z", "UP_Y"
    D = semiancho * 1.06 / math.tan(math.atan(18 / 50))
    pos = []
    for f in frames:
        t = t_de(f)
        k = suave(t / 0.78)
        az = math.radians(-15 * (1 - k))
        el = math.radians(7 * (1 - k) + 1.5)
        dist = D * (1.14 - 0.14 * k) * (1 - 0.025 * max(0.0, t - 0.78) / 0.22)
        pos.append(objetivo.location + Vector((math.sin(az) * math.cos(el) * dist,
                                               -math.cos(az) * math.cos(el) * dist,
                                               math.sin(el) * dist)))
    for eje in range(3):
        H.hornear(cam, "location", eje, frames, [p[eje] for p in pos])
    H.hornear(cd, "dof.aperture_fstop", -1, frames,
              [2.4 + 3.2 * suave(t_de(f) / 0.7) for f in frames])

    # del negro al negro
    H.hornear(sc, "view_settings.exposure", -1, frames,
              [-8 + 8 * suave(t_de(f) / 0.07) - 8 * suave((t_de(f) - 0.94) / 0.06) for f in frames])
    return n


# ── huella y render ──────────────────────────────────────────────────────
def huella(formato, segundos: float, muestras: int,
           renderizador: str = "gpu") -> str:
    h = hashlib.sha256()
    h.update(Path(__file__).read_bytes())
    h.update((SCRIPTS / "nucleo" / "horneado.py").read_bytes())
    h.update((AQUI / "medallones.py").read_bytes())
    for n in ("emblema.png", "emblema_alfa.png", "emblema_profundidad.png"):
        h.update((MARCA / n).read_bytes())
    h.update(json.dumps([formato.ancho, formato.alto, formato.fps, segundos, muestras, renderizador,
                         bpy.app.version_string, idioma_del_cierre(), lema_del_idioma(), getattr(FUENTE_NOMBRE, "name", "interna"),
                         getattr(FUENTE_MONO, "name", "interna")]).encode())
    return h.hexdigest()


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="cierre")
    ap.add_argument("--formato", required=True)
    ap.add_argument("--renderizador", choices=("cpu", "gpu"), default="gpu")
    ap.add_argument("--muestras", type=int, default=64)
    ap.add_argument("--escala", type=int, default=100, help="% de resolucion (pruebas)")
    ap.add_argument("--fotograma", type=int, action="append",
                    help="rinde solo estos fotogramas (pruebas), sin manifiesto")
    ap.add_argument("--salida", default="", help="carpeta; por defecto la del formato")
    ap.add_argument("--si-falta", action="store_true",
                    help="no hace nada si ya existe un cierre con la misma huella")
    a = ap.parse_args(argv)

    formato = fmt.para_dispositivo(fmt.cargar(a.formato), a.renderizador)
    # La duracion es del formato (`cierre_s`): la previsualizacion, que es un
    # bucle, no lleva cierre.
    if formato.cierre_s <= 0:
        print(f"CIERRE_NO_APLICA: {a.formato} no lleva cierre")
        return 0
    segundos = formato.cierre_s
    destino = Path(a.salida) if a.salida else MARCA / "cierre" / f"{a.formato}_{idioma_del_cierre()}"
    firma = huella(formato, segundos, a.muestras, a.renderizador)
    manifiesto = destino / "manifiesto.json"
    if a.si_falta and not a.fotograma and manifiesto.exists():
        previo = json.loads(manifiesto.read_text(encoding="utf-8"))
        pngs = list(destino.glob("f_*.png"))
        if previo.get("huella") == firma and len(pngs) == previo.get("fotogramas"):
            print(f"CIERRE_AL_DIA: {destino} ({len(pngs)} fotogramas)")
            return 0

    t0 = time.time()
    n = construir(formato, segundos, a.muestras, a.escala, a.renderizador)
    sc = bpy.context.scene
    destino.mkdir(parents=True, exist_ok=True)
    if a.fotograma:
        for f in a.fotograma:
            comprobar_espacio(destino, sc.render.resolution_x, sc.render.resolution_y)
            sc.frame_set(f)
            sc.render.filepath = str(destino / f"prueba_{f:04d}")
            bpy.ops.render.render(write_still=True)
            print(f"CIERRE_PRUEBA: {destino / f'prueba_{f:04d}.png'}")
        return 0
    for viejo in destino.glob("f_*.png"):
        viejo.unlink()
    manifiesto.unlink(missing_ok=True)
    for f in range(1, n + 1):
        comprobar_espacio(destino, sc.render.resolution_x, sc.render.resolution_y)
        sc.frame_set(f)
        sc.render.filepath = str(destino / f"f_{f:04d}")
        bpy.ops.render.render(write_still=True)
        if f % 20 == 1:
            print(f"CIERRE {f}/{n}  {time.time() - t0:.0f}s", flush=True)
    manifiesto.write_text(json.dumps({
        "formato": a.formato, "ancho": formato.ancho, "alto": formato.alto,
        "fps": formato.fps, "segundos": segundos, "fotogramas": n,
        "muestras": a.muestras, "renderizador": a.renderizador,
        "hilos_cpu": sc.render.threads if a.renderizador == "cpu" else None,
        "huella": firma, "blender": bpy.app.version_string,
        "idioma": idioma_del_cierre(), "lema": LEMA,
        "rendido_s": round(time.time() - t0, 1),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"CIERRE_LISTO: {n} fotogramas en {time.time() - t0:.0f}s -> {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
