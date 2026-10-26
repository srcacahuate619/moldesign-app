"""El rig y el horneado del trayecto. CONSTANTE.

No sabe que esta filmando. Recibe una lista de estados por fotograma —posicion,
objetivo, lente, diafragma, gradiente— y los hornea.

Incluye el rig de luces, que orbita y escala con la camara: sin eso, media
vuelta del plano general se queda a oscuras porque las luces se disenaron para
un primer plano concreto.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import bpy
from mathutils import Vector

from . import horneado as H


@dataclass
class Rig:
    camara: Any
    objetivo: Any
    luces: Any


def montar_rig(pivote: Vector, lente_inicial: float, sensor: float = 36.0) -> Rig:
    sc = bpy.context.scene
    tgt = bpy.data.objects.new("Cine_Objetivo", None)
    tgt.empty_display_size = 0.3
    tgt.location = pivote
    sc.collection.objects.link(tgt)

    datos = bpy.data.cameras.new("Cine_CamaraDatos")
    datos.lens, datos.sensor_width = lente_inicial, sensor
    # Ajuste FIJO a horizontal. Con el AUTO de Blender, un render vertical
    # cambia el ajuste a VERTICAL (los 36 mm pasan a la altura) y todo el
    # encuadre medido —que supone ajuste horizontal en `encuadre`,
    # `rotulos.colocar` y `crear_pantalla`— queda mal: en el piloto vertical
    # el titulo cayo fuera del cuadro (origen en NDC -0.21 en vez de 0.10).
    # En 16:9 AUTO ya es HORIZONTAL, asi que aqui no cambia nada.
    datos.sensor_fit = "HORIZONTAL"
    datos.clip_start, datos.clip_end = 0.02, 500.0
    datos.dof.use_dof = True
    datos.dof.focus_object = tgt
    cam = bpy.data.objects.new("Cine_Camara", datos)
    sc.collection.objects.link(cam)
    c = cam.constraints.new("TRACK_TO")
    c.target, c.track_axis, c.up_axis = tgt, "TRACK_NEGATIVE_Z", "UP_Y"
    sc.camera = cam

    rig = bpy.data.objects.new("Cine_RigLuces", None)
    rig.location = pivote
    sc.collection.objects.link(rig)
    bpy.context.view_layer.update()
    for n in ("Key", "Fill", "Rim"):
        L = bpy.data.objects.get(n)
        if L is None:
            continue
        mundo = L.location.copy()
        L.parent = rig
        L.matrix_parent_inverse = rig.matrix_world.inverted()
        L.location = mundo      # con esa inversa, la local ES la mundial
    bpy.context.view_layer.update()
    return Rig(camara=cam, objetivo=tgt, luces=rig)


def _mapa(nt, nombre: str, ubicacion: tuple, to_min: float, to_max: float) -> Any:
    """MapRange suave y acotado, que es como se quiere medir una transicion."""
    m = nt.nodes.new("ShaderNodeMapRange")
    m.name, m.location, m.clamp = nombre, ubicacion, True
    m.interpolation_type = "SMOOTHSTEP"
    m.inputs["To Min"].default_value = to_min
    m.inputs["To Max"].default_value = to_max
    return m


def preparar_disolucion(mat_cartoon, portal: bool = False) -> Any:
    """Anade al carton la disolucion por profundidad de camara.

    El push-in atraviesa literalmente la cascara de la proteina (en el caso 001
    la camara acaba a 3.94 unidades del centro, con radio 5.91). Sin esto, o te
    quedas fuera mirando superficie o atraviesas la cinta y se ve feo.

    Con `portal`, en vez de vaciar por profundidad TODO lo que hay delante, se
    dibuja un fantasma translucido solo dentro del cilindro que va de la camara
    al pivote: la cascara que se interpone conserva su silueta a opacidad baja y
    el resto del receptor —lo que no tapa el sitio— no se toca.
    """
    nt = mat_cartoon.node_tree
    bsdf = H.nodo_por_tipo(nt, "ShaderNodeBsdfPrincipled")
    for n in ("CINE_camdata", "CINE_depth"):
        if n in nt.nodes:
            nt.nodes.remove(nt.nodes[n])
    if portal:
        return _preparar_portal(nt, bsdf)
    cdn = nt.nodes.new("ShaderNodeCameraData")
    cdn.name, cdn.location = "CINE_camdata", (-700, -400)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.name, mr.location, mr.clamp = "CINE_depth", (-500, -400), True
    mr.inputs["To Min"].default_value = 0.0
    mr.inputs["To Max"].default_value = 1.0
    nt.links.new(cdn.outputs["View Z Depth"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], bsdf.inputs["Alpha"])
    return mr


#: Nodos del fantasma. Se declaran juntos porque se crean, se cablean y se
#: hornean en tres sitios distintos y una errata en un nombre no se ve hasta
#: que el render sale con la cascara entera o con el receptor entero de cristal.
_NODOS_PORTAL = ("CINE_pos", "CINE_campos", "CINE_dir", "CINE_axis_v",
                 "CINE_axis_t", "CINE_axis_sc", "CINE_perp", "CINE_perp_r",
                 "CINE_rad", "CINE_far", "CINE_mascara", "CINE_uno",
                 "CINE_efecto", "CINE_fuerza", "CINE_alpha")


def _preparar_portal(nt, bsdf) -> dict:
    """Cilindro camara->pivote: dentro se es fantasma, fuera se es normal.

    Por fragmento se mide la distancia PERPENDICULAR al eje camara->pivote y la
    distancia A LO LARGO de el. El alfa se baja al piso solo donde ambas caen
    dentro de la ventana: radio del cilindro, y por delante del pivote. Las dos
    fronteras van con smoothstep, asi que la silueta aparece y se apaga de a
    poco en vez de recortarse.

    La posicion es de MUNDO (no de objeto): el eje esta medido en coordenadas de
    mundo y el objeto de la molecula no tiene por que venir en identidad.
    """
    for n in _NODOS_PORTAL:
        if n in nt.nodes:
            nt.nodes.remove(nt.nodes[n])

    pos = nt.nodes.new("ShaderNodeNewGeometry")
    pos.name, pos.location = "CINE_pos", (-1500, -600)
    campos = nt.nodes.new("ShaderNodeCombineXYZ")
    campos.name, campos.location = "CINE_campos", (-1500, -780)
    direccion = nt.nodes.new("ShaderNodeCombineXYZ")
    direccion.name, direccion.location = "CINE_dir", (-1500, -960)

    v = nt.nodes.new("ShaderNodeVectorMath")
    v.name, v.operation, v.location = "CINE_axis_v", "SUBTRACT", (-1300, -600)
    largo = nt.nodes.new("ShaderNodeVectorMath")
    largo.name, largo.operation, largo.location = "CINE_axis_t", "DOT_PRODUCT", (-1100, -560)
    escala = nt.nodes.new("ShaderNodeVectorMath")
    escala.name, escala.operation, escala.location = "CINE_axis_sc", "SCALE", (-1100, -760)
    perp = nt.nodes.new("ShaderNodeVectorMath")
    perp.name, perp.operation, perp.location = "CINE_perp", "SUBTRACT", (-900, -600)
    radio = nt.nodes.new("ShaderNodeVectorMath")
    radio.name, radio.operation, radio.location = "CINE_perp_r", "LENGTH", (-700, -600)

    mapa_rad = _mapa(nt, "CINE_rad", (-500, -480), 1.0, 0.0)
    mapa_far = _mapa(nt, "CINE_far", (-500, -700), 1.0, 0.0)
    mascara = nt.nodes.new("ShaderNodeMath")
    mascara.name, mascara.operation, mascara.location = "CINE_mascara", "MULTIPLY", (-280, -600)
    uno = nt.nodes.new("ShaderNodeMath")
    uno.name, uno.operation, uno.location = "CINE_uno", "SUBTRACT", (-280, -820)
    uno.inputs[0].default_value = 1.0
    efecto = nt.nodes.new("ShaderNodeMath")
    efecto.name, efecto.operation, efecto.location = "CINE_efecto", "MULTIPLY", (-60, -700)
    fuerza = nt.nodes.new("ShaderNodeMath")
    fuerza.name, fuerza.operation, fuerza.location = "CINE_fuerza", "MULTIPLY", (160, -700)
    alfa = nt.nodes.new("ShaderNodeMath")
    alfa.name, alfa.operation, alfa.location = "CINE_alpha", "SUBTRACT", (380, -700)
    alfa.inputs[0].default_value = 1.0

    nt.links.new(pos.outputs["Position"], v.inputs[0])
    nt.links.new(campos.outputs[0], v.inputs[1])
    nt.links.new(v.outputs[0], largo.inputs[0])
    nt.links.new(direccion.outputs[0], largo.inputs[1])
    nt.links.new(direccion.outputs[0], escala.inputs[0])
    nt.links.new(largo.outputs[1], escala.inputs[3])      # Value -> Scale
    nt.links.new(v.outputs[0], perp.inputs[0])
    nt.links.new(escala.outputs[0], perp.inputs[1])
    nt.links.new(perp.outputs[0], radio.inputs[0])
    nt.links.new(radio.outputs[1], mapa_rad.inputs["Value"])
    nt.links.new(largo.outputs[1], mapa_far.inputs["Value"])
    nt.links.new(mapa_rad.outputs["Result"], mascara.inputs[0])
    nt.links.new(mapa_far.outputs["Result"], mascara.inputs[1])
    nt.links.new(mascara.outputs[0], efecto.inputs[0])
    nt.links.new(uno.outputs[0], efecto.inputs[1])
    nt.links.new(efecto.outputs[0], fuerza.inputs[0])
    nt.links.new(fuerza.outputs[0], alfa.inputs[1])
    nt.links.new(alfa.outputs[0], bsdf.inputs["Alpha"])
    return {"modo": "portal",
            "nodos": {"campos": campos, "dir": direccion, "rad": mapa_rad,
                      "far": mapa_far, "uno": uno, "fuerza": fuerza}}


def _hornear_portal(nt, nodos: dict, estados, frames) -> None:
    """Hornea los controles del fantasma, uno por fotograma.

    El eje y el largo se derivan aqui de la posicion de camara y el pivote ya
    resueltos en `estados`: si se recalcularan en el shader harian falta mas
    nodos para lo mismo.
    """
    def canal(nombre: str, ruta: str, valores) -> None:
        H.hornear(nt, f'nodes["{nombre}"].{ruta}', -1, frames, valores)

    for eje in range(3):
        canal("CINE_campos", f"inputs[{eje}].default_value",
              [e["portal"]["campos"][eje] for e in estados])
        canal("CINE_dir", f"inputs[{eje}].default_value",
              [e["portal"]["dir"][eje] for e in estados])
    i = H.indice_entrada(nodos["rad"], "From Min")
    canal("CINE_rad", f"inputs[{i}].default_value",
          [e["portal"]["r0"] for e in estados])
    i = H.indice_entrada(nodos["rad"], "From Max")
    canal("CINE_rad", f"inputs[{i}].default_value",
          [e["portal"]["r1"] for e in estados])
    i = H.indice_entrada(nodos["far"], "From Min")
    canal("CINE_far", f"inputs[{i}].default_value",
          [e["portal"]["t1"] for e in estados])
    i = H.indice_entrada(nodos["far"], "From Max")
    canal("CINE_far", f"inputs[{i}].default_value",
          [e["portal"]["t2"] for e in estados])
    canal("CINE_uno", "inputs[1].default_value",
          [e["portal"]["piso"] for e in estados])
    canal("CINE_fuerza", "inputs[1].default_value",
          [e["portal"]["fuerza"] for e in estados])


def hornear_trayecto(rig: Rig, estados, frames, mat_cartoon, nodo_disolucion,
                     dist_referencia: float) -> None:
    cam, tgt, luces = rig.camara, rig.objetivo, rig.luces
    for o in (cam, tgt, cam.data, luces):
        H.limpiar(o)

    for i in range(3):
        H.hornear(cam, "location", i, frames, [e["pos"][i] for e in estados])
        H.hornear(tgt, "location", i, frames, [e["objetivo"][i] for e in estados])
        H.hornear(luces, "scale", i, frames,
                  [e["dist"] / dist_referencia for e in estados])
    H.hornear(luces, "rotation_euler", 2, frames, [e["giro"] for e in estados])
    H.hornear(cam.data, "lens", -1, frames, [e["lente"] for e in estados])
    H.hornear(cam.data, "dof.aperture_fstop", -1, frames, [e["diafragma"] for e in estados])

    for n in ("Key", "Fill", "Rim"):
        L = bpy.data.objects.get(n)
        if L is None:
            continue
        base = L.get("energia_base", L.data.energy)
        H.limpiar(L.data)
        H.hornear(L.data, "energy", -1, frames,
                  [base * (e["dist"] / dist_referencia) ** 2 for e in estados])

    nt = mat_cartoon.node_tree
    H.limpiar(nt)
    for nn in ("DEP_map", "DEP_rough"):
        if nn in nt.nodes:
            i = H.indice_entrada(nt.nodes[nn], "From Max")
            H.hornear(nt, f'nodes["{nn}"].inputs[{i}].default_value', -1, frames,
                      [e["gradiente"] for e in estados])
    if isinstance(nodo_disolucion, dict):
        _hornear_portal(nt, nodo_disolucion["nodos"], estados, frames)
        return
    i0 = H.indice_entrada(nodo_disolucion, "From Min")
    i1 = H.indice_entrada(nodo_disolucion, "From Max")
    H.hornear(nt, f'nodes["CINE_depth"].inputs[{i0}].default_value', -1, frames,
              [e["diso0"] for e in estados])
    H.hornear(nt, f'nodes["CINE_depth"].inputs[{i1}].default_value', -1, frames,
              [e["diso1"] for e in estados])
