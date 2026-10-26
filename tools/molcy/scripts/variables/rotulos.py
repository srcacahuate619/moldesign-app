"""VARIABLE: que se rotula, y de que clase.

Dos clases, y la diferencia no es estetica sino geometrica:

`EtiquetaAnclada` — texto 3D con linea guia hasta un atomo o un residuo. Tiene
    posicion en el mundo, asi que **se ladea en cuanto la camara se mueve**. Por
    eso solo se ve con la imagen QUIETA: en una pausa de camara (Resultado) o en
    un fotograma congelado del montaje (Busqueda, Ensamble; ver
    `variables/pausas.py`), y se coloca UNA vez, con la camara de ese instante.
    Todas las de un mismo instante se reparten juntas y sin solaparse
    (`colocar`, `variables/disposicion.py`), y van en la capa de rotulos: nada
    de la escena las tapa.

`RotuloPantalla` — texto emparentado a la camara. No tiene ancla, no se ladea y
    **puede vivir durante el movimiento**. Es lo que necesita la busqueda de
    Montecarlo, que no tiene ningun momento quieto, y el gancho de los primeros
    segundos en redes sociales.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import bpy
from mathutils import Matrix, Vector

from nucleo import horneado as H
from nucleo.fundido import curva
# El nombre del rotulo inferior vive en `titulos.py`, sin bpy, para poder
# probarlo fuera de Blender. Se reexporta: el maestro lo llama desde aqui.
from variables.titulos import NOMBRES_CURADOS, nombre_legible, titulo_pantalla  # noqa: F401

#: Fraccion de la distancia camara->ancla a la que se coloca la etiqueta.
#: Cerca de la camara para quedar por delante de la geometria.
CERCANIA = 0.45

#: Profundidad (unidades de escena) a la que un rótulo con `igualar_tamano` conserva su escala
#: de diseño: la distancia típica de los planos de seguimiento de `x`.
PROFUNDIDAD_NOMINAL = 2.2

@dataclass
class Rotulo:
    id: str
    texto: str
    objeto: object = None
    guia: object = None
    material: object = None
    ventana: tuple[int, int] = (1, 1)
    fundido: list = field(default_factory=list)
    #: Fotograma con el que se coloca (la cámara de ese instante); None = el del beat del guion.
    colocar_en: int | None = None
    #: Puntos (mundo) del sujeto que este rótulo no debe tapar: se reserva su caja en pantalla.
    reservar: list | None = None


def _duplicar(prototipo, nombre: str, texto: str, escala_texto: float):
    """Duplica el prototipo del caso 001 para heredar tipografia y material."""
    lab = prototipo.copy()
    lab.data = prototipo.data.copy()
    # Sin esto las copias comparten la accion del prototipo y cada horneado
    # pisa al anterior: la ultima etiqueta acaba decidiendo por todas.
    lab.animation_data_clear()
    lab.name = nombre
    lab.data.body = texto
    if "tamano_base" not in lab.data:
        lab.data["tamano_base"] = prototipo.data.size
    lab.data.size = lab.data["tamano_base"] * escala_texto
    # El contorno del prototipo esta en unidades de mundo y se diseño para su
    # tamaño: heredado tal cual en un texto mas pequeño (las interacciones, los
    # datos de pantalla) engordaba los trazos hasta cerrar las contraformas.
    if "contorno_base" not in lab.data:
        lab.data["contorno_base"] = prototipo.data.offset
    lab.data.offset = lab.data["contorno_base"] * min(1.0, escala_texto)
    lab.data.materials.clear()
    mat = prototipo.data.materials[0].copy()
    mat.name = f"Mat_{nombre}"
    H.limpiar_material(mat)
    mat.blend_method = "BLEND"
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    lab.data.materials.append(mat)
    lab.hide_render = lab.hide_viewport = False
    # Una etiqueta no puede arrojar sombra: estaba imprimiendo su texto sobre
    # la helice de detras como si fuera un grabado, y se leia como un duplicado
    # fantasma. Tampoco debe recibirla ni aparecer en reflejos.
    for prop in ("visible_shadow", "visible_diffuse", "visible_glossy"):
        if hasattr(lab, prop):
            setattr(lab, prop, False)
    bpy.context.scene.collection.objects.link(lab)
    return lab, mat


# ── etiqueta anclada en 3D ───────────────────────────────────────────────
def crear_anclada(id_: str, texto: str, ancla: Vector, prototipo, proto_guia,
                  escala_texto: float = 1.0) -> Rotulo:
    lab, mat = _duplicar(prototipo, f"Lab_{id_}", texto, escala_texto)
    lab["ancla_pos"] = list(ancla)
    guia = proto_guia.copy()
    guia.data = proto_guia.data.copy()
    guia.animation_data_clear()
    guia.name = f"Guia_{id_}"
    guia.data.materials.clear()
    guia.data.materials.append(mat)
    guia.hide_render = guia.hide_viewport = False
    for prop in ("visible_shadow", "visible_diffuse", "visible_glossy"):
        if hasattr(guia, prop):
            setattr(guia, prop, False)
    bpy.context.scene.collection.objects.link(guia)
    return Rotulo(id=id_, texto=texto, objeto=lab, guia=guia, material=mat)


def tintar(rotulo: "Rotulo", color, emision: float = 1.0) -> None:
    """Color plano del texto y de su guia (comparten material); el alfa no se toca.

    Distingue lo que se rotula: POLAR y APOLAR con el color de su linea, los
    hotspots en neutro. Solo EMITE: con el color tambien en la base, la luz de la
    escena se sumaba a la emision y AgX llevaba el resultado al blanco —las dos
    clases salian del mismo crema y no se distinguian de nada—.
    """
    nodos = rotulo.material.node_tree.nodes if rotulo.material else []
    for nodo in nodos:
        if "Base Color" in nodo.inputs:
            nodo.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        if "Emission Color" in nodo.inputs:
            nodo.inputs["Emission Color"].default_value = (*color, 1.0)
        if "Emission Strength" in nodo.inputs:
            nodo.inputs["Emission Strength"].default_value = emision
        if "Color" in nodo.inputs and nodo.bl_idname == "ShaderNodeEmission":
            nodo.inputs["Color"].default_value = (*color, 1.0)


def _factor_de_tamano(profundidades: dict, igualar: bool) -> dict:
    """Escala de cada rótulo para que TODOS se vean del mismo tamaño en pantalla.

    El rótulo se coloca a una fracción fija de la distancia cámara→ancla, así que su
    tamaño en pantalla es 1/profundidad: con la cámara cerca (la escena `x` sigue a la
    pose a 1–3 unidades) un ancla próxima daba un texto el doble de grande que una
    lejana, y el mismo rótulo cambiaba de tamaño según el plano. Con `igualar` cada uno
    se escala por su profundidad respecto a `PROFUNDIDAD_NOMINAL`: tamaño en pantalla
    constante en todos los planos.
    """
    if not igualar or not profundidades:
        return {k: 1.0 for k in profundidades}
    return {k: max(0.35, min(2.0, v / PROFUNDIDAD_NOMINAL)) for k, v in profundidades.items()}


#: Grosor de la guía, en fracción del ANCHO del cuadro: el mismo trazo en pantalla
#: a cualquier profundidad y en cualquier formato (antes era un radio en metros
#: que en vertical se ensanchaba a mano).
GROSOR_GUIA = 0.0024

#: Intentos, de más a menos exigente: (tamaño del texto, ¿puede una guía cruzar
#: la línea de otra interacción?, ¿puede un texto tapar una línea?). Si ni el
#: último cabe, se rotulan menos —las últimas del grupo, las menos importantes— y
#: el acta dice cuáles. Lo que nunca se acepta es un solape entre textos o guías.
INTENTOS = ((1.0, False, False), (1.0, True, False), (0.88, True, False),
            (0.76, True, False), (0.76, True, True))


def _caja_local(lab) -> tuple[float, float]:
    """Semiejes del texto en sus unidades. Si Blender aun no los midio, estima
    por avance medio: mejor una caja aproximada que ninguna busqueda."""
    xs = [c[0] for c in lab.bound_box]
    ys = [c[1] for c in lab.bound_box]
    hx0, hy0 = (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2
    if hx0 <= 0 or hy0 <= 0:
        tam = lab.data.size * max(len(lab.data.body or ""), 1)
        hx0, hy0 = 0.30 * tam, 0.35 * tam
    return hx0, hy0


def _centro_local(lab):
    xs = [c[0] for c in lab.bound_box]
    ys = [c[1] for c in lab.bound_box]
    return Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 0.0))


def _largo_local_guia(guia) -> tuple[float, float]:
    """(diámetro, largo) del prototipo de guía en sus unidades: un cilindro en Z."""
    xs = [c[0] for c in guia.bound_box]
    zs = [c[2] for c in guia.bound_box]
    return max(max(xs) - min(xs), 1e-6), max(max(zs) - min(zs), 1e-6)


def colocar(cam, rotulos, reservados=(), zonas_texto=(), igualar_tamano: bool = True,
            lineas=None) -> list:
    """Coloca un grupo de etiquetas ancladas con la cámara de ESTE fotograma.

    Las cajas son las de los glifos reales; el reparto lo decide
    `variables.disposicion.disponer`, que no acepta solapes ni cruces. El texto
    se cuelga a `CERCANIA` de la distancia cámara→ancla (por delante de la
    geometría) y su guía va del ancla al borde del texto, ambos en el plano de la
    etiqueta: en pantalla la guía nace exactamente sobre el ancla.

    `lineas`: {id del rótulo: (a, b)} en mundo, la línea de interacción que
    explica; ningún texto se pone encima de una (ver `disposicion`).

    Devuelve los `Rotulo` que no caben ni achicando el texto: quien llama los
    quita de la escena y lo deja en el acta.
    """
    from variables.disposicion import SinEspacio, disponer
    sc = bpy.context.scene
    grupo = [r for r in rotulos if r.objeto is not None]
    if not grupo:
        return []
    bpy.context.view_layer.update()
    M = cam.matrix_world
    q = M.to_quaternion()
    rg, uv, fw = (q @ Vector(v) for v in ((1, 0, 0), (0, 1, 0), (0, 0, -1)))
    tan = cam.data.sensor_width / (2 * cam.data.lens)       # ajuste HORIZONTAL fijo
    asp = sc.render.resolution_x / max(sc.render.resolution_y, 1)

    def proyectar(p):
        v = p - M.translation
        z = v.dot(fw)
        return (v.dot(rg) / (tan * z), v.dot(uv) * asp / (tan * z)), z

    anclas = {r.id: Vector(r.objeto["ancla_pos"]) for r in grupo}
    prof = {r.id: proyectar(anclas[r.id])[1] for r in grupo}
    delante = [r for r in grupo if prof[r.id] > 1e-4]
    omitidas = [r for r in grupo if prof[r.id] <= 1e-4]
    factores = _factor_de_tamano({r.id: prof[r.id] for r in delante}, igualar_tamano)
    for r in delante:
        r.objeto.data.align_x = "CENTER"
        r.objeto.data.align_y = "CENTER"
    bpy.context.view_layer.update()
    medidas = {r.id: (_caja_local(r.objeto), _centro_local(r.objeto)) for r in delante}

    segmentos = []
    for ident, (p0, p1) in (lineas or {}).items():
        (n0, z0), (n1, z1) = proyectar(Vector(p0)), proyectar(Vector(p1))
        if z0 > 1e-4 and z1 > 1e-4:
            segmentos.append((ident, (n0, n1)))

    solucion, reduccion = None, 1.0
    while delante and solucion is None:
        for reduccion, cruzar, tapar in INTENTOS:
            etiquetas = []
            for r in delante:
                (hx, hy), _c = medidas[r.id]
                f, z = factores[r.id] * reduccion, prof[r.id]
                etiquetas.append((r.id, proyectar(anclas[r.id])[0],
                                  2 * hx * f / (tan * z), 2 * hy * f * asp / (tan * z)))
            try:
                solucion = disponer(etiquetas, reservados, zonas_texto=zonas_texto,
                                    lineas=() if tapar else segmentos, cruzar_lineas=cruzar)
                break
            except SinEspacio:
                continue
        if solucion is None:
            omitidas.append(delante.pop())        # la última del grupo es la menos importante

    for r in delante:
        caja, guia = solucion[r.id]
        z = prof[r.id] * CERCANIA
        escala = CERCANIA * factores[r.id] * reduccion

        def mundo(ndc, z=z):
            return M.translation + fw * z + rg * (ndc[0] * tan * z) + uv * (ndc[1] * tan * z / asp)

        centro = mundo(((caja[0] + caja[2]) / 2, (caja[1] + caja[3]) / 2))
        r.objeto.location = centro - q @ (medidas[r.id][1] * escala)
        r.objeto.scale = (escala,) * 3
        r.objeto.rotation_mode = "QUATERNION"
        r.objeto.rotation_quaternion = q
        r.objeto["caja_pantalla"] = [round(v, 5) for v in caja]
        r.objeto["reduccion"] = reduccion
        if r.guia is not None:
            a, b = mundo(guia[0]), mundo(guia[1])
            v = b - a
            diametro, largo = _largo_local_guia(r.guia)
            grosor = GROSOR_GUIA * 2 * tan * z           # fracción del ancho → metros a esa profundidad
            r.guia.location = (a + b) / 2
            r.guia.rotation_mode = "QUATERNION"
            r.guia.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(v.normalized())
            r.guia.scale = (grosor / diametro, grosor / diametro, v.length / largo)
            r.guia["segmento_pantalla"] = [round(x, 5) for x in (*guia[0], *guia[1])]
    print(f"ETIQUETAS_SIN_SOLAPES: {len(delante)} colocadas"
          + (f" al {reduccion:.0%} del tamaño" if delante and reduccion < 1.0 else "")
          + (f", {len(omitidas)} sin sitio" if omitidas else ""), flush=True)
    return omitidas


# ── rotulo pegado a la camara ────────────────────────────────────────────
def crear_pantalla(id_: str, texto: str, cam, prototipo,
                   esquina: str = "inferior_izquierda",
                   escala_texto: float = 1.0, margen: float = 0.10,
                   lente_referencia: float | None = None,
                   distancia: float | None = None) -> Rotulo:
    """Texto emparentado a la camara: nunca se ladea ni sale de cuadro.

    Se cuelga a 1 unidad por delante y se situa en coordenadas de cuadro, asi
    que vale igual para 16:9 que para 9:16 sin tocar nada.

    `lente_referencia` tiene que ser la lente MAS LARGA del plano, no la del
    momento de crearlo: la lente esta animada, y colocar el rotulo con el
    encuadre abierto lo deja fuera de cuadro en cuanto se cierra.

    AVISO: a `dist` corta, la profundidad de campo —enfocada al sitio activo—
    lo deja irreconocible. Para texto permanente (procedencia) usar el sellado
    nativo de `salida/procedencia.py`. Esto sirve para ganchos de redes en
    planos sin desenfoque, o con `formato.profundidad_de_campo=False`.
    """
    sc = bpy.context.scene
    lab, mat = _duplicar(prototipo, f"Rot_{id_}", texto, escala_texto * 0.42)
    lab.parent = cam
    # Identidad, NO la inversa de la camara: la camara lleva una restriccion
    # Track To y su matriz cambia cada fotograma, asi que una inversa tomada al
    # crear el rotulo lo deja transformado dos veces y fuera de cuadro.
    lab.matrix_parent_inverse = Matrix.Identity(4)

    # `distancia` deberia ser la DISTANCIA DE ENFOQUE del plano: ahi el texto
    # sale nitido. Como la posicion y la escala son lineales en `dist`, el
    # tamano en pantalla no cambia, solo la profundidad — asi que se puede
    # mover libremente para esquivar el desenfoque o la geometria.
    dist = distancia if distancia else 0.12
    lente = lente_referencia or cam.data.lens
    hx = math.atan(cam.data.sensor_width / 2 / lente)
    semi_x = math.tan(hx) * dist
    semi_y = semi_x / (sc.render.resolution_x / max(sc.render.resolution_y, 1))
    x = -semi_x + margen * 2 * semi_x
    y = -semi_y + margen * 2 * semi_y
    lab.data.align_x = "LEFT"
    if hasattr(lab.data, "space_line"):
        # 0.90 juntaba los renglones de los bloques de datos (VINA | POSE…).
        lab.data.space_line = 1.10
    # Blender alinea el texto por ARRIBA por defecto, asi que un rotulo puesto
    # en el borde inferior cuelga fuera de cuadro. Hay que decirlo explicito.
    lab.data.align_y = "BOTTOM"
    if "derecha" in esquina:
        x = semi_x - margen * 2 * semi_x
        lab.data.align_x = "RIGHT"
    if "superior" in esquina:
        y = semi_y - margen * 2 * semi_y
        lab.data.align_y = "TOP"
    lab.location = (x, y, -dist)
    # El prototipo viene en modo QUATERNION (se lo puso el billboard viejo), y
    # con ese modo `rotation_euler` no hace absolutamente nada: el rotulo salia
    # girado en diagonal con la orientacion heredada.
    lab.rotation_mode = "XYZ"
    lab.rotation_euler = (0.0, 0.0, 0.0)
    lab.scale = (dist, dist, dist)
    return Rotulo(id=id_, texto=texto, objeto=lab, guia=None, material=mat)


# ── horneado comun ───────────────────────────────────────────────────────
def hornear(rotulos, frames) -> None:
    """Ventana de visibilidad y fundido de cada rotulo."""
    for r in rotulos:
        if r.objeto is None:
            continue
        a, b = r.ventana
        for o in (r.objeto, r.guia):
            if o is not None:
                H.visible_en(o, frames, a, b)
        if r.fundido:
            H.fundir(r.material, frames, curva(r.fundido, frames))
