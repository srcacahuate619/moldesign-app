"""Contactos polares y apolares medidos sobre las coordenadas del paquete.

QUE ES Y QUE NO ES
------------------
Esto NO es un PLIF. No hay protonacion ni angulos donante-H-aceptor. Los pares
N/O son proximidades polares, no puentes H confirmados. Para contactos
hidrofobicos se filtran carbonos unidos a heteroatomos y se exige una cadena
lateral proteica, pero no se sustituyen los patrones SMARTS de ProLIF.

El contrato lo permite explicitamente. En `no_dibujar.angulo_puente_hidrogeno`
dice que `_estimate_hbond_angle` devuelve None a proposito porque el receptor no
llega protonado, y que lo permitido en su lugar es «la linea punteada del
contacto y su distancia en A, sin H». Las poses de X vienen de Vina; la
medicion se repite en cada una, sin interpolar o inventar contactos.

Cuando el exportador exponga un `interactions.json` con ProLIF y
`confirmado_por` (ver el estandar de oro de 001), habra que preferirlo y dejar
esto como respaldo. Mientras tanto, se dibuja lo que se puede medir, rotulado
por lo que es.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from .ciencia import ESCALA

#: Rango de distancia para un contacto polar entre atomos pesados, en Angstrom.
#: 2.4 descarta solapes y errores de coordenadas; 3.5 es el corte habitual.
MIN_A, MAX_A = 2.4, 3.5

#: Numeros atomicos de los donantes/aceptores que se consideran.
POLARES = (7, 8)          # N, O
METALES = (12, 20, 25, 26, 27, 28, 29, 30)   # Mg Ca Mn Fe Co Ni Cu Zn
MAX_METAL_A = 2.6
MAX_HIDROFOBICO_A = 4.5  # ProLIF: https://prolif.readthedocs.io/en/latest/source/modules/interaction-fingerprint.html
MIN_HIDROFOBICO_A = 2.8  # evita representar solapamientos estericos
ENLACE_CH_A = 1.9        # carbonos unidos a heteroatomos no son apolares


@dataclass
class Contacto:
    a: Vector                 # atomo del receptor, en mundo
    b: Vector                 # atomo del sujeto, en mundo
    distancia_a: float
    resname: str
    resid: int
    cadena: str
    tipo: str = "polar"       # polar | hidrofobico | metal

    @property
    def etiqueta(self) -> str:
        return f"{self.distancia_a:.2f} A".replace("A", "Å")

    @property
    def medio(self) -> Vector:
        return (self.a + self.b) * 0.5


def _atomos(molecula, numeros):
    """Posiciones (mundo) y numero atomico de los atomos pedidos."""
    z = molecula.named_attribute("atomic_number")
    pos = molecula.named_attribute("position")
    sel = np.isin(z, numeros)
    return pos[sel], z[sel], sel


# El mapa vive en `interacciones` (puro, sin bpy) y se busca por (cadena, número):
# ver SCI-A-030 en su docstring.
from .interacciones import mapa_de_residuos, nombre_de_residuo  # noqa: E402,F401


def medir(receptor_mol, sujeto_mol, cerca_de: Vector | None = None,
          radio_a: float = 14.0, nombres: dict[tuple[str, int], str] | None = None,
          cadenas: list[str] | None = None,
          solo_residuos: set[tuple[str, int]] | None = None) -> list[Contacto]:
    """Contactos polares entre el sujeto y el receptor, por distancia.

    `cerca_de` acota la busqueda al entorno del sitio activo: sin eso, en un
    receptor grande se comparan decenas de miles de pares sin necesidad.
    """
    zr = receptor_mol.named_attribute("atomic_number")
    pr = receptor_mol.named_attribute("position")
    rid = receptor_mol.named_attribute("res_id")
    try:
        rname = receptor_mol.named_attribute("res_name")
    except Exception:
        rname = None
    try:
        chid = receptor_mol.named_attribute("chain_id")
    except Exception:
        chid = None

    mask = np.isin(zr, POLARES)
    if cerca_de is not None:
        c = np.array([cerca_de.x, cerca_de.y, cerca_de.z])
        d = np.linalg.norm(pr - c, axis=1)
        mask &= d < (radio_a * ESCALA)
    idx = np.nonzero(mask)[0]
    if idx.size == 0:
        return []

    zs = sujeto_mol.named_attribute("atomic_number")
    ps = sujeto_mol.named_attribute("position")
    js = np.nonzero(np.isin(zs, POLARES))[0]
    if js.size == 0:
        return []

    lo, hi = MIN_A * ESCALA, MAX_A * ESCALA
    out: list[Contacto] = []
    for j in js:
        d = np.linalg.norm(pr[idx] - ps[j], axis=1)
        for k in np.nonzero((d >= lo) & (d <= hi))[0]:
            i = idx[k]
            numero = int(rid[i])
            ci = int(chid[i]) if chid is not None else -1
            cadena = (cadenas[ci] if cadenas and 0 <= ci < len(cadenas)
                      else str(ci))
            if solo_residuos is not None and (cadena, numero) not in solo_residuos:
                continue
            out.append(Contacto(
                a=Vector(pr[i].tolist()), b=Vector(ps[j].tolist()),
                distancia_a=float(d[k]) / ESCALA,
                resname=nombre_de_residuo(nombres, cadena, numero),
                resid=numero,
                cadena=cadena))
    out.sort(key=lambda c: c.distancia_a)
    return out


def _carbonos_apolares(z, pos, candidatos):
    """Carbonos sin N/O/S/F/halogeno a distancia covalente.

    La conectividad del PDB no contiene ordenes de enlace. Este filtro espacial
    es deliberadamente conservador; no afirma energia de interaccion. Sigue
    la exclusion de carbonos ligados a heteroatomos de ProLIF/PLIP, aunque
    sin sus patrones SMARTS ni su analisis completo de grupos funcionales.
    """
    heteros = pos[np.isin(z, (7, 8, 9, 16, 17, 35, 53))]
    idx = np.nonzero(candidatos & (z == 6))[0]
    if not len(heteros):
        return idx
    corte2 = (ENLACE_CH_A * ESCALA) ** 2
    return np.array([i for i in idx
                     if not np.any(np.sum((heteros - pos[i]) ** 2, axis=1) < corte2)],
                    dtype=int)


def medir_hidrofobicos(receptor_mol, sujeto_mol,
                       cerca_de: Vector | None = None, radio_a: float = 14.0,
                       nombres: dict[tuple[str, int], str] | None = None,
                       cadenas: list[str] | None = None,
                       solo_residuos: set[tuple[str, int]] | None = None
                       ) -> list[Contacto]:
    """Proximidad entre carbonos apolares del ligando y cadenas laterales.

    Umbral de 4.5 Å como ProLIF. Se excluyen C ligados a heteroatomos; en el
    receptor se exige cadena lateral. Es un contacto geometrico compatible con
    asociacion hidrofobica, no una energia de enlace ni un PLIF completo.
    """
    zr = receptor_mol.named_attribute("atomic_number")
    pr = receptor_mol.named_attribute("position")
    rid = receptor_mol.named_attribute("res_id")
    try:
        lado = receptor_mol.named_attribute("is_side_chain").astype(bool)
    except Exception:
        lado = np.zeros(len(zr), dtype=bool)  # sin evidencia, no inferir
    try:
        chid = receptor_mol.named_attribute("chain_id")
    except Exception:
        chid = None
    if cerca_de is not None:
        c = np.array(tuple(cerca_de))
        lado &= np.linalg.norm(pr - c, axis=1) < radio_a * ESCALA
    ir = _carbonos_apolares(zr, pr, lado)
    zs = sujeto_mol.named_attribute("atomic_number")
    ps = sujeto_mol.named_attribute("position")
    js = _carbonos_apolares(zs, ps, np.ones(len(zs), dtype=bool))
    lo, hi = MIN_HIDROFOBICO_A * ESCALA, MAX_HIDROFOBICO_A * ESCALA
    out = []
    for j in js:
        d = np.linalg.norm(pr[ir] - ps[j], axis=1)
        for k in np.nonzero((d >= lo) & (d <= hi))[0]:
            i = ir[k]
            numero = int(rid[i])
            ci = int(chid[i]) if chid is not None else -1
            cadena = (cadenas[ci] if cadenas and 0 <= ci < len(cadenas)
                      else str(ci))
            if solo_residuos is not None and (cadena, numero) not in solo_residuos:
                continue
            out.append(Contacto(
                a=Vector(pr[i].tolist()), b=Vector(ps[j].tolist()),
                distancia_a=float(d[k]) / ESCALA,
                resname=nombre_de_residuo(nombres, cadena, numero),
                resid=numero, cadena=cadena, tipo="hidrofobico"))
    return sorted(out, key=lambda c: c.distancia_a)


def elegir_por_tipo(polares, hidrofobicos, max_por_tipo=3, preferidos=()):
    """Una linea por residuo y clase para evitar abanicos ilegibles."""
    return (sin_duplicar_residuo(polares, max_por_tipo, preferidos) +
            sin_duplicar_residuo(hidrofobicos, max_por_tipo, preferidos))


def material_hidrofobico(nombre):
    """Cian discontinuo, visualmente distinto del oro de contacto polar."""
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    salida = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.20, 0.82, 0.84, 1.0)
    em.inputs["Strength"].default_value = 4.5
    nt.links.new(em.outputs["Emission"], salida.inputs["Surface"])
    return m


def dibujar(nombre, c: Contacto, material):
    if c.tipo == "hidrofobico":
        return malla_punteada(nombre, c.a, c.b, material,
                              trozos=4, grosor=0.019, relleno=0.72)
    return malla_punteada(nombre, c.a, c.b, material)


def sin_duplicar_residuo(contactos: list[Contacto], cuantos: int,
                         preferidos=()) -> list[Contacto]:
    """Un contacto por residuo, el mas corto. Evita abanicos ilegibles.

    Un mismo carbonilo puede quedar a menos de 3.5 A de tres atomos del ligando;
    dibujar las tres lineas no anade informacion y tapa el bolsillo.

    `preferidos` son los residuos que la escena YA presento y rotulo como
    hotspots. Van primero aunque otro este 0.1 A mas cerca: el video gana mucho
    mas ensenando el enlace de un residuo que el espectador acaba de conocer que
    el de uno anonimo. En 1HWK el corte ciego por distancia descartaba
    Arg590 (3.03 A) y Ser565 (2.86 A) —ambos presentados— para dibujar
    Ser684 (2.65 A), Glu559 (2.69 A) y Lys735 (2.76 A), que no lo estaban.
    """
    pref = {int(x) for x in preferidos}
    contactos = sorted(contactos, key=lambda c: (c.resid not in pref, c.distancia_a))
    vistos, out = set(), []
    for c in contactos:
        clave = (c.cadena, c.resid)
        if clave in vistos:
            continue
        vistos.add(clave)
        out.append(c)
        if len(out) >= cuantos:
            break
    return out


# ── geometria de la linea punteada ───────────────────────────────────────
def malla_punteada(nombre: str, a: Vector, b: Vector, material,
                   trozos: int = 7, grosor: float = 0.024,
                   relleno: float = 0.55):
    """Un objeto con `trozos` segmentos cortos entre a y b.

    Se construye la malla a mano en vez de usar un modificador de matriz: es
    determinista, no depende de la evaluacion del depsgraph para el trazado de
    rayos, y deja un solo objeto por contacto que se funde con un material.

    El grosor subio de 0.011 a 0.024 tras comprobarlo a resolucion completa: con
    el carton coloreado por estructura —mas claro que el gris pizarra plano de
    antes— las lineas finas doradas simplemente no se leian.
    """
    u = b - a
    largo = u.length
    if largo < 1e-5:
        return None
    dirn = u.normalized()
    paso = largo / trozos
    me = bpy.data.meshes.new(nombre)
    bm = bmesh.new()
    rot = Vector((0, 0, 1)).rotation_difference(dirn).to_matrix().to_4x4()
    for i in range(trozos):
        c0 = a + dirn * (paso * (i + 0.5 - relleno / 2))
        c1 = a + dirn * (paso * (i + 0.5 + relleno / 2))
        centro = (c0 + c1) * 0.5
        m = rot.copy()
        m.translation = centro
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=6,
                              radius1=grosor, radius2=grosor,
                              depth=(c1 - c0).length, matrix=m)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(nombre, me)
    if material is not None:
        me.materials.append(material)
    bpy.context.scene.collection.objects.link(obj)
    return obj
