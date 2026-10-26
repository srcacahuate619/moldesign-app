"""Direccion de arte: materiales, luces, fondo, tipografia. CONSTANTE.

No se re-deriva: se importa del caso 001, que es el aprobado. Asi el aspecto se
conserva por construccion y no por suerte.

La plantilla es `plantilla_arte.blend`: solo materiales, luces y prototipo de
etiqueta, SIN una sola clave de animacion. Se regenera con
`herramientas/extraer_plantilla_arte.py`. Nunca apuntar al .blend de EGFR hecho
a mano: sus acciones se heredan al copiar y pisan los valores que se asignen
despues. Aun asi, todo lo que se copia se limpia: cinturon y tirantes.
"""
from __future__ import annotations

import bpy
from mathutils import Vector

from .horneado import limpiar, limpiar_material, nodo_por_tipo
from .rutas import PLANTILLA_ARTE

MATERIALES = ("CH1_Cartoon", "Lab_Lab_Erlo", "CH1_Dash_Water", "HBond_EGFR_Gold")
OBJETOS = ("Key", "Fill", "Rim", "Lab_Erlo", "Leader_Lab_Erlo")

#: Sitio activo del caso 001. Las luces se guardan como desplazamiento respecto
#: a el, para que el esquema se traslade a cualquier receptor en vez de quedarse
#: donde estaba el bolsillo de EGFR.
_K_001 = Vector((2.248, -0.109, 5.553))
LUCES = {
    "Key": (Vector((-0.53, 2.21, 3.41)) - _K_001, 140.0),
    "Fill": (Vector((-0.08, -1.58, 6.42)) - _K_001, 25.0),
    # Rim un 20% por encima del caso 001: con el fondo a (0.02,0.026,0.042) las
    # zonas tangenciales del carton se fundian con la oscuridad y la silueta de
    # la macromolecula se perdia.
    "Rim": (Vector((4.41, -2.23, 3.73)) - _K_001, 276.0),
}

FONDO = (0.02, 0.026, 0.042, 0.35)   # color y fuerza del caso 001


def limpiar_escena_por_defecto() -> list[str]:
    """Quita el cubo, la luz y la camara de `--factory-startup`.

    El cubo no solo sale en pantalla tapando media proteina: bloquea los rayos
    de la medida de oclusion y falsea la eleccion del arco.
    """
    fuera = []
    for o in list(bpy.data.objects):
        if o.name in ("Cube", "Light", "Camera"):
            fuera.append(o.name)
            bpy.data.objects.remove(o, do_unlink=True)
    return fuera


def poner_fondo(r=FONDO[0], g=FONDO[1], b=FONDO[2], fuerza=FONDO[3]) -> None:
    """Se fija explicitamente en vez de importarlo.

    Al hacer `append` el mundo colisiona de nombre con el que ya existe y queda
    como 'World.001', asi que `bpy.data.worlds[0]` devuelve el gris por defecto.
    """
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new("Cine_World")
    sc.world = w
    w.use_nodes = True
    for n in w.node_tree.nodes:
        if n.bl_idname == "ShaderNodeBackground":
            n.inputs["Color"].default_value = (r, g, b, 1.0)
            n.inputs["Strength"].default_value = fuerza


def importar() -> dict:
    """Trae materiales, luces y prototipos de etiqueta del caso 001."""
    traido = {}
    with bpy.data.libraries.load(str(PLANTILLA_ARTE), link=False) as (src, dst):
        dst.materials = [m for m in src.materials if m in MATERIALES]
        dst.objects = [o for o in src.objects if o in OBJETOS]
    for m in bpy.data.materials:
        if m.name in MATERIALES:
            traido[m.name] = m
    for o in bpy.data.objects:
        if o.name in OBJETOS:
            traido[o.name] = o
            # `libraries.load` los deja en bpy.data pero NO los enlaza a ninguna
            # coleccion: sin esto las tres luces existen y no alumbran.
            if o.name not in bpy.context.scene.collection.objects:
                bpy.context.scene.collection.objects.link(o)
    poner_fondo()
    for n in ("Lab_Erlo", "Leader_Lab_Erlo"):      # prototipos, nunca en pantalla
        if n in traido:
            traido[n].hide_render = traido[n].hide_viewport = True
    return traido


def colocar_luces(arte: dict, pivote: Vector) -> None:
    for nombre, (desplazamiento, energia) in LUCES.items():
        L = arte.get(nombre)
        if L is None:
            continue
        L.location = pivote + desplazamiento
        L.data.energy = energia
        L["energia_base"] = energia
        limpiar(L.data)


#: Paleta por estructura secundaria. Molecular Nodes codifica `sec_struct`
#: como 0=no proteina, 1=helice, 2=lamina, 3=lazo.
#:
#: Por que ESTO y no arcoiris N->C: el degradado de arcoiris es el cliche del
#: campo, es bonito y no significa nada —codifica posicion en la secuencia, que
#: no es una propiedad interesante—. La estructura secundaria SI es un dato:
#: el ojo lee la arquitectura del pliegue de un vistazo.
#:
#: Y por que no atomo por atomo: la cinta ya es una abstraccion, no dibuja
#: atomos sino el recorrido del esqueleto. Pintar cada atomo sobre ella es
#: ruido. El coloreado CPK por atomo esta donde tiene sentido: ligando y
#: varillas.
#:
#: La paleta se queda fria a proposito para que el ligando siga siendo el unico
#: acento calido de la escena.
#: Los tres tonos quedan OSCUROS a proposito, en el rango del gris pizarra
#: original (0.225, 0.265, 0.335). La informacion la lleva el TONO, no el
#: brillo. La primera version usaba valores mas claros (helice 0.32/0.44/0.62)
#: y el resultado fue una regresion: el receptor se iluminaba, el ligando
#: palido dejaba de destacar sobre el, y las lineas de contacto doradas se
#: perdian contra la cinta. El ligando tiene que seguir siendo lo mas claro y
#: lo unico calido de la escena.
PALETA_ESTRUCTURA = {
    0: (0.19, 0.21, 0.27),   # no proteina
    1: (0.21, 0.28, 0.40),   # helice: azul
    2: (0.17, 0.32, 0.33),   # lamina: verde azulado
    3: (0.15, 0.17, 0.22),   # lazo: neutro oscuro
}

#: Paleta sobria por subunidad. Se mezcla con la estructura secundaria para
#: que la cadena se entienda en el plano general y el pliegue siga visible en
#: el primer plano. No codifica una propiedad fisicoquímica.
PALETA_CADENA = (
    (0.15, 0.23, 0.35),  # A: azul pizarra / petróleo
    (0.23, 0.25, 0.29),  # B: carbón / titanio
    (0.18, 0.29, 0.36),  # C: azul acero desaturado
    (0.27, 0.30, 0.36),  # D: pizarra fría clara
)


def pintar_por_estructura(molecula, con_cadena: bool = False) -> dict:
    """Escribe el atributo `Color` por atomo segun estructura secundaria.

    Devuelve el censo de lo pintado, para el acta.
    """
    import numpy as np
    try:
        ss = molecula.named_attribute("sec_struct")
    except Exception:
        return {}
    n = len(ss)
    col = np.zeros((n, 4), dtype=np.float32)
    col[:, 3] = 1.0
    for clave, rgb in PALETA_ESTRUCTURA.items():
        col[ss == clave, :3] = rgb
    desconocidas = sorted(set(int(x) for x in np.unique(ss)) - set(PALETA_ESTRUCTURA))
    for k in desconocidas:                       # convenciones nuevas de MN
        col[ss == k, :3] = PALETA_ESTRUCTURA[3]

    if con_cadena:
        try:
            ch = molecula.named_attribute("chain_id")
            for i in range(int(ch.max()) + 1):
                mask = ch == i
                if not mask.any():
                    continue
                tono = np.array(PALETA_CADENA[i % len(PALETA_CADENA)],
                                dtype=np.float32)
                # El tono de cadena domina ligeramente; la estructura
                # secundaria conserva el contraste de hélice/lámina/lazo.
                col[mask, :3] = 0.54 * tono + 0.46 * col[mask, :3]
        except Exception:
            pass
    np.clip(col, 0.0, 1.0, out=col)
    molecula.store_named_attribute(col, "Color", atype="FLOAT_COLOR")

    import collections
    censo = collections.Counter(int(x) for x in ss)
    nombres = {0: "no_proteina", 1: "helice", 2: "lamina", 3: "lazo"}
    return {nombres.get(k, f"clase_{k}"): v for k, v in sorted(censo.items())}


def usar_color_por_atomo(mat) -> bool:
    """Hace que el carton lea el atributo `Color` en vez de un tono plano.

    Se enchufa al zocalo A del nodo `DEP_mix`, que era el color CERCANO del
    degradado por distancia al bolsillo. Asi la senal de profundidad se
    conserva intacta —lo lejano sigue yendo a casi negro— y lo unico que cambia
    es de que color parte lo cercano.
    """
    if mat is None or not mat.use_nodes:
        return False
    nt = mat.node_tree
    mix = nt.nodes.get("DEP_mix")
    if mix is None:
        return False
    if "CINE_color" in nt.nodes:
        nt.nodes.remove(nt.nodes["CINE_color"])
    at = nt.nodes.new("ShaderNodeAttribute")
    at.name, at.location = "CINE_color", (-900, 260)
    at.attribute_name = "Color"
    destino = next((s for s in mix.inputs
                    if s.name == "A" and s.type == "RGBA"), None)
    if destino is None:
        return False
    nt.links.new(at.outputs["Color"], destino)
    return True


def realzar_protagonista(mat) -> None:
    """Sube el brillo especular del sujeto para que el ojo lo fije.

    El ligando comparte reflectividad con las cadenas laterales del bolsillo y
    se lee como un residuo mas. Es el protagonista: se le da un acabado mas
    pulido. No se toca el color por atomo (sigue siendo CPK) ni la geometria.
    """
    if mat is None or not mat.use_nodes:
        return
    bs = nodo_por_tipo(mat.node_tree, "ShaderNodeBsdfPrincipled")
    if bs is None:
        return
    if "Roughness" in bs.inputs:
        bs.inputs["Roughness"].default_value = min(
            0.22, bs.inputs["Roughness"].default_value)
    if "Specular IOR Level" in bs.inputs:
        bs.inputs["Specular IOR Level"].default_value = 0.72
    if "Coat Weight" in bs.inputs:
        bs.inputs["Coat Weight"].default_value = 0.25


def acabado_receptor(mat, experimental: bool = False) -> None:
    """Acabado satinado experimental para el cartón del receptor."""
    if not experimental or mat is None or not mat.use_nodes:
        return
    bs = nodo_por_tipo(mat.node_tree, "ShaderNodeBsdfPrincipled")
    if bs is not None:
        if "Roughness" in bs.inputs:
            bs.inputs["Roughness"].default_value = 0.46
        if "Specular IOR Level" in bs.inputs:
            bs.inputs["Specular IOR Level"].default_value = 0.30
        if "Coat Weight" in bs.inputs:
            bs.inputs["Coat Weight"].default_value = 0.04
        if "Subsurface Weight" in bs.inputs:
            bs.inputs["Subsurface Weight"].default_value = 0.018
        elif "Subsurface" in bs.inputs:
            bs.inputs["Subsurface"].default_value = 0.018
    for node in mat.node_tree.nodes:
        if "ambient" not in node.name.lower() and "ao" not in node.name.lower():
            continue
        for socket in node.inputs:
            if socket.name.lower() == "distance":
                socket.default_value = 0.50


def _fijar(nodo, nombre, valor) -> bool:
    """Asigna un zocalo o una propiedad sin importar como lo llame esta version.

    Blender 5 movio a zocalos cosas que eran propiedades (el tipo y la calidad
    del glare) y cambio tipos (el tamano del blur paso de float a vector). Un
    ayudante tolerante evita una cascada de `hasattr` en cada linea.
    """
    try:
        if nombre in nodo.inputs:
            nodo.inputs[nombre].default_value = valor
            return True
    except (TypeError, AttributeError, ValueError):
        pass
    try:
        if hasattr(nodo, nombre):
            setattr(nodo, nombre, valor)
            return True
    except (TypeError, AttributeError, ValueError):
        pass
    return False


def subir_emision(mat, fuerza: float) -> None:
    """Fija la intensidad de emision de un material que brilla."""
    if mat is None or not mat.use_nodes:
        return
    em = nodo_por_tipo(mat.node_tree, "ShaderNodeEmission")
    if em is not None and "Strength" in em.inputs:
        em.inputs["Strength"].default_value = fuerza


def compositor(activar: bool = False) -> None:
    """DESACTIVADO. En Blender 5 el compositor por grupo devuelve blanco aqui.

    En Blender 5 el compositor dejo de ser `scene.node_tree` con Render Layers
    y Composite, y paso a ser un GRUPO (`scene.compositing_node_group`) con
    entrada y salida de grupo. Cableado asi —entrada -> Denoise -> salida— el
    render sale **en blanco**: el grupo no recibe la imagen renderizada, asi que
    su entrada queda en el valor por defecto.

    Se deja el intento documentado y apagado en vez de borrarlo: el denoise
    valdria la pena (quitaria grano sin subir muestras, que es lo unico que
    cuesta tiempo), pero es acabado y no informacion. No merece arriesgar la
    imagen hasta entender como alimenta Blender 5 ese grupo.

    A 128 muestras en `biblioteca` el grano no se ve; en `previsualizacion`, a
    48, si se nota algo.
    """
    sc = bpy.context.scene
    if not activar:
        sc.use_nodes = False
        if hasattr(sc, "compositing_node_group"):
            sc.compositing_node_group = None
        return


def copiar_material(base, nombre: str):
    m = base.copy()
    m.name = nombre
    limpiar_material(m)     # las copias heredan keyframes del original
    return m


def material_del_estilo(molecula, fragmento: str, nombre_nuevo: str):
    """Copia el material de UN estilo concreto, buscandolo por nombre de nodo.

    Coger el primer zocalo de material del grupo no vale: hay un estilo por cada
    segmento de cinta mas los de varillas, y el primero es siempre el carton.
    Cruzarlos deja la cinta con el material y el fundido de las varillas.

    Se copia en vez de crearlo porque el material de MN lee el atributo `Color`
    por atomo y conserva el coloreado CPK; un Principled liso lo perderia.
    """
    ng = molecula.object.modifiers[0].node_group
    for nd in ng.nodes:
        if fragmento.lower() not in nd.name.lower():
            continue
        for s in nd.inputs:
            if s.type == "MATERIAL" and getattr(s, "default_value", None) is not None:
                nuevo = s.default_value.copy()
                nuevo.name = nombre_nuevo
                limpiar_material(nuevo)
                s.default_value = nuevo
                return nuevo
    return None


# ── utilidades de geometria evaluada ─────────────────────────────────────
def puntos_evaluados(obj) -> list[Vector]:
    dg = bpy.context.evaluated_depsgraph_get()
    oe = obj.evaluated_get(dg)
    me = oe.to_mesh()
    pts = [obj.matrix_world @ v.co for v in me.vertices]
    oe.to_mesh_clear()
    return pts


def centro_evaluado(obj) -> Vector:
    pts = puntos_evaluados(obj)
    if not pts:
        return obj.matrix_world.translation.copy()
    return sum(pts, Vector()) / len(pts)
