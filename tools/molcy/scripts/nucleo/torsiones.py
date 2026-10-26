"""Rig geométrico para excursiones ILUSTRATIVAS cerradas, sin Blender ni RDKit.

El productor demuestra el grafo desde el SDF guardado. Aquí se comprueban sus
invariantes y se rotan subárboles; no se infieren enlaces por distancia, no se
reconstruyen trayectorias ni se calculan energía o calidad de intermedios.
"""
from __future__ import annotations

import math
import re

SCHEMA = "moldesign.rig-torsional/1"
VARIANTES = ("lenta", "detallada")


class RigNoDisponible(ValueError):
    pass


def _real(value, nombre):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RigNoDisponible(f"{nombre}: se requiere un número finito")
    return float(value)


def _resta(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _suma(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _escala(a, k):
    return tuple(x * k for x in a)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cruz(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norma(a):
    return math.sqrt(_dot(a, a))


def _girar(punto, origen, eje, grados):
    """Rodrigues; conserva distancias y ángulos del grupo rígido."""
    largo = _norma(eje)
    if largo < 1e-10:
        raise RigNoDisponible("eje de rotación degenerado")
    n = _escala(eje, 1 / largo)
    v = _resta(punto, origen)
    r = math.radians(grados)
    c, s = math.cos(r), math.sin(r)
    return _suma(origen, _suma(_suma(_escala(v, c), _escala(_cruz(n, v), s)),
                               _escala(n, _dot(n, v) * (1 - c))))


def _componente(vecinos, inicio, corte):
    visitados, pendientes = set(), [inicio]
    while pendientes:
        atomo = pendientes.pop()
        if atomo in visitados:
            continue
        visitados.add(atomo)
        pendientes.extend(v for v in vecinos[atomo]
                          if frozenset((atomo, v)) != corte and v not in visitados)
    return visitados


def validar_rig(datos, *, sdf_sha256=None):
    """Valida identidad declarada, grafo y partición exacta de cada eje.

    Las banderas químicas son responsabilidad del productor; se exigen explícitas.
    No se considera una molécula físicamente válida por superar esta comprobación.
    """
    if not isinstance(datos, dict) or datos.get("schema") != SCHEMA:
        raise RigNoDisponible("falta el esquema de rig torsional")
    huella = datos.get("sdf_sha256")
    if not isinstance(huella, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", huella):
        raise RigNoDisponible("falta el hash del SDF de entrada")
    if sdf_sha256 is not None and huella.lower() != sdf_sha256.lower():
        raise RigNoDisponible("el rig no corresponde al SDF verificado")
    atomos, ids = [], set()
    for a in datos.get("atomos") or []:
        if not isinstance(a, dict):
            raise RigNoDisponible("átomo sin estructura declarada")
        ident, elemento, xyz = a.get("id"), a.get("elemento"), a.get("xyz_a")
        if not isinstance(ident, str) or not ident or ident in ids:
            raise RigNoDisponible("IDs de átomos ausentes o repetidos")
        if not isinstance(elemento, str) or not elemento or elemento.upper() == "H":
            raise RigNoDisponible("el rig visual requiere átomos pesados identificados")
        if not isinstance(xyz, (list, tuple)) or len(xyz) != 3:
            raise RigNoDisponible(f"{ident}: coordenadas incompletas")
        atomos.append({"id": ident, "elemento": elemento,
                       "xyz_a": tuple(_real(x, ident) for x in xyz)})
        ids.add(ident)
    if len(atomos) < 4:
        raise RigNoDisponible("faltan átomos para una torsión")
    vecinos = {i: set() for i in ids}
    enlaces = {}
    for e in datos.get("enlaces") or []:
        if not isinstance(e, dict):
            raise RigNoDisponible("enlace sin estructura declarada")
        par = e.get("atomos")
        if not isinstance(par, (list, tuple)) or len(par) != 2:
            raise RigNoDisponible("enlace sin dos IDs")
        a, b = par
        clave = frozenset(par)
        if a not in ids or b not in ids or a == b or clave in enlaces:
            raise RigNoDisponible("enlace repetido o con identidad desconocida")
        orden = _real(e.get("orden"), "orden de enlace")
        if orden not in (1.0, 1.5, 2.0, 3.0):
            raise RigNoDisponible("orden de enlace no admitido")
        flags = {}
        for nombre in ("anillo", "aromatico", "conjugado"):
            if type(e.get(nombre)) is not bool:
                raise RigNoDisponible(f"el enlace no declara {nombre}")
            flags[nombre] = e[nombre]
        enlaces[clave] = {"atomos": [a, b], "orden": orden, **flags}
        vecinos[a].add(b)
        vecinos[b].add(a)
    if _componente(vecinos, atomos[0]["id"], frozenset()) != ids:
        raise RigNoDisponible("el rig requiere un grafo conectado")
    ejes, vistos = [], set()
    posicion = {a["id"]: a["xyz_a"] for a in atomos}
    for e in datos.get("ejes") or []:
        if not isinstance(e, dict):
            raise RigNoDisponible("eje sin estructura declarada")
        cuatro = e.get("atomos")
        if not isinstance(cuatro, (list, tuple)) or len(cuatro) != 4 or len(set(cuatro)) != 4:
            raise RigNoDisponible("un diedro necesita cuatro átomos distintos")
        if any(i not in ids for i in cuatro):
            raise RigNoDisponible("diedro con IDs desconocidos")
        i, j, k, l = cuatro
        clave = frozenset((j, k))
        if clave in vistos:
            raise RigNoDisponible("un enlace aparece dos veces como eje")
        if any(frozenset(p) not in enlaces for p in ((i, j), (j, k), (k, l))):
            raise RigNoDisponible("los cuatro átomos no forman un diedro del grafo")
        enlace = enlaces[clave]
        if enlace["orden"] != 1 or any(enlace[n] for n in ("anillo", "aromatico", "conjugado")):
            raise RigNoDisponible("el eje debe ser simple, acíclico y no conjugado")
        moviles = e.get("moviles")
        lado = _componente(vecinos, k, clave)
        if j in lado:
            raise RigNoDisponible("el eje pertenece a un ciclo del grafo")
        if (not isinstance(moviles, (list, tuple)) or len(set(moviles)) != len(moviles)
                or set(moviles) != lado or i in lado or j in lado or l not in lado):
            raise RigNoDisponible("el grupo móvil no es la componente exacta del enlace")
        amplitud = _real(e.get("amplitud_grados"), "amplitud ilustrativa")
        if not 0 < abs(amplitud) <= 60:
            raise RigNoDisponible("la amplitud ilustrativa debe ser no nula y de hasta 60 grados")
        eje = _resta(posicion[k], posicion[j])
        if _norma(eje) < 1e-6:
            raise RigNoDisponible("eje de longitud nula")
        desplazamiento = max(_norma(_resta(
            _girar(posicion[a], posicion[j], eje, amplitud), posicion[a])) for a in lado)
        if desplazamiento < 0.05:
            raise RigNoDisponible("el eje no produce torsión visual discernible")
        ejes.append({"atomos": list(cuatro), "moviles": list(moviles),
                     "amplitud_grados": amplitud})
        vistos.add(clave)
    if not ejes:
        raise RigNoDisponible("ningún eje elegible para ilustrar torsión interna")
    return {"schema": SCHEMA, "sdf_sha256": huella.lower(), "atomos": atomos,
            "enlaces": list(enlaces.values()), "ejes": ejes}


def curvas(progreso, variante):
    """Ambos movimientos simultáneos; recorrido de ida y vuelta al mismo extremo."""
    t = _real(progreso, "progreso")
    if not 0 <= t <= 1 or variante not in VARIANTES:
        raise RigNoDisponible("progreso o variante desconocida")
    if t in (0, 1):
        return 0.0, 0.0
    s = t * t * (3 - 2 * t)
    if variante == "lenta":
        return math.sin(math.pi * s) ** 2, math.sin(math.pi * s) ** 2
    # La torsión alcanza su máximo antes que el giro global, sin fases inmóviles.
    return math.sin(math.pi * s ** 0.8) ** 2, math.sin(math.pi * s ** 1.25) ** 2


def posiciones(rig, progreso, variante="lenta", *, giro_grados=60.0):
    """Coordenadas de presentación en Å; cero/uno reproducen exactamente la fuente.

    Nunca se añaden energía, calidad ni contactos a los intermedios. El recentrado
    y el giro global son editoriales, no desplazamiento físico hacia un receptor.
    """
    torsion, orientacion = curvas(progreso, variante)
    if torsion == orientacion == 0:
        return [tuple(a["xyz_a"]) for a in rig["atomos"]]
    puntos = {a["id"]: tuple(a["xyz_a"]) for a in rig["atomos"]}
    for e in rig["ejes"]:
        _, j, k, _ = e["atomos"]
        origen, eje = puntos[j], _resta(puntos[k], puntos[j])
        for ident in e["moviles"]:
            puntos[ident] = _girar(puntos[ident], origen, eje, e["amplitud_grados"] * torsion)
    n = len(puntos)
    centro_fuente = tuple(sum(a["xyz_a"][i] for a in rig["atomos"]) / n for i in range(3))
    centro_actual = tuple(sum(p[i] for p in puntos.values()) / n for i in range(3))
    traslado = _resta(centro_fuente, centro_actual)
    giro = _real(giro_grados, "giro de presentación") * orientacion
    return [_girar(_suma(puntos[a["id"]], traslado), centro_fuente, (0.0, 0.0, 1.0), giro)
            for a in rig["atomos"]]


def validar_coordenadas(rig, puntos_a, tolerancia_a=0.002):
    """El orden del mesh debe coincidir con los IDs persistentes del productor."""
    if len(puntos_a) != len(rig["atomos"]):
        raise RigNoDisponible("el mesh y el rig no tienen los mismos átomos pesados")
    error = max(_norma(_resta(p, a["xyz_a"])) for p, a in zip(puntos_a, rig["atomos"]))
    if error > tolerancia_a:
        raise RigNoDisponible(f"el mesh no reproduce el extremo guardado: {error:.6f} A")
    return error


def hornear_objeto(objeto, rig, desde, hasta, frames, variante):
    """Adaptador perezoso Blender: shape keys absolutas, una geometría por frame.

    No se ejecuta al importar el módulo ni en las pruebas geométricas puras.
    Cada shape key conserva el mismo mesh, grafo y IDs. Se usa una copia; el
    objeto fuente permanece sin deformar para los extremos y la procedencia.
    """
    from nucleo.horneado import hornear
    from nucleo.ciencia import ESCALA

    validar_coordenadas(rig, [tuple(float(x) / ESCALA for x in v.co)
                             for v in objeto.data.vertices])
    copia = objeto.copy()
    copia.data = objeto.data.copy()
    copia.name = objeto.name + "_Ilustracion"
    objeto.users_collection[0].objects.link(copia)
    if copia.data.shape_keys:
        copia.shape_key_clear()
    # El dibujo animado utiliza conectividad SDF, nunca enlaces inferidos por cercanía.
    import bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(copia.data)
        bm.verts.ensure_lookup_table()
        for enlace in list(bm.edges):
            bm.edges.remove(enlace)
        indices = {a["id"]: i for i, a in enumerate(rig["atomos"])}
        for enlace in rig["enlaces"]:
            a, b = enlace["atomos"]
            bm.edges.new((bm.verts[indices[a]], bm.verts[indices[b]]))
        bm.to_mesh(copia.data)
    finally:
        bm.free()
    validar_coordenadas(rig, [tuple(float(x) / ESCALA for x in v.co)
                             for v in copia.data.vertices])
    copia.shape_key_add(name="Extremo_guardado")
    keys = copia.data.shape_keys
    keys.use_relative = False
    tiempos = {}
    for f in range(desde, hasta + 1):
        bloque = copia.shape_key_add(name=f"Ilustracion_{f:05d}")
        bloque.interpolation = "KEY_LINEAR"
        xyz = posiciones(rig, (f - desde) / max(1, hasta - desde), variante)
        bloque.data.foreach_set("co", [x * ESCALA for p in xyz for x in p])
        tiempos[f] = bloque.frame
    valores = [tiempos[min(hasta, max(desde, f))] for f in frames]
    hornear(keys, "eval_time", -1, frames, valores)
    return copia
