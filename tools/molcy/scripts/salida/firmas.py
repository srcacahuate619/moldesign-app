"""Qué cambia de un fotograma a otro: si nada, su render ya existe.

Todo lo que se mueve en estas escenas está horneado como claves por fotograma
(cámara, luces, materiales, visibilidad y deformaciones por shape keys). La «firma» de un fotograma es el valor
de todas esas curvas en él; dos fotogramas con la misma firma dan la misma imagen
(EEVEE es determinista) y basta con rendir uno. `variables.pausas.representantes`
decide cuál.

Dos firmas, porque son dos pasadas:

- la de la ESCENA no mira los rótulos: van ocultos a la cámara en esa pasada, así
  que mientras las etiquetas entran sobre una cámara quieta la escena no cambia;
- la de la CAPA de rótulos sólo mira los rótulos, la lente y —cuando hay una
  etiqueta anclada a la vista— la posición de la cámara: el texto de pantalla va
  pegado a la cámara y no cambia porque ella se mueva (medido en Búsqueda, 4FK3:
  diferencia máxima 5–7 sobre 255 entre fotogramas del mismo texto).

Lo que no está en una curva no entra en la firma; en estas escenas no hay nada
así (ni controladores, ni nodos que lean el fotograma). `maestro` lo comprueba:
si encuentra un controlador, no reutiliza nada.
"""
from __future__ import annotations

import bpy

#: Decimales con los que se comparan los valores (las curvas son números de coma flotante).
DECIMALES = 6


def _curvas(idb) -> list:
    ad = getattr(idb, "animation_data", None)
    if ad is None or ad.action is None:
        return []
    act = ad.action
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    out = []
    ranuras = [ad.action_slot] if getattr(ad, "action_slot", None) else list(act.slots)
    for capa in act.layers:
        for tira in capa.strips:
            for r in ranuras:
                if r is None:
                    continue
                try:
                    bolsa = tira.channelbag(r)
                except Exception:
                    continue
                if bolsa:
                    out += list(bolsa.fcurves)
    return out


def _bloques():
    for coleccion in (bpy.data.objects, bpy.data.cameras, bpy.data.lights, bpy.data.materials,
                      bpy.data.node_groups, bpy.data.worlds, bpy.data.scenes, bpy.data.curves,
                      bpy.data.meshes, getattr(bpy.data, "shape_keys", ())):
        for idb in coleccion:
            yield idb
            nt = getattr(idb, "node_tree", None)
            if nt is not None:
                yield nt


def hay_controladores() -> bool:
    """Un controlador (driver) cambia valores sin curva: con él la firma no vale."""
    return any(getattr(getattr(idb, "animation_data", None), "drivers", None)
               for idb in _bloques())


def _clave(idb) -> int:
    """Identidad del bloque. NUNCA el nombre: todos los árboles de nodos de material
    se llaman «Shader Nodetree», y por nombre el del receptor pasaba por uno de un
    rótulo (y la escena dejaba de ver el fundido de su material)."""
    return idb.as_pointer()


def _de_rotulos(nombres) -> set:
    """Los bloques que sólo ven los rótulos: sus objetos, sus datos y sus materiales."""
    ids = set()
    for n in nombres:
        o = bpy.data.objects.get(n)
        if o is None:
            continue
        ids.add(_clave(o))
        datos = getattr(o, "data", None)
        if datos is not None:
            ids.add(_clave(datos))
            for m in getattr(datos, "materials", ()) or ():
                if m is not None:
                    ids.add(_clave(m))
                    if m.node_tree is not None:
                        ids.add(_clave(m.node_tree))
    return ids


def _evaluar(curvas, desde: int, hasta: int) -> dict:
    return {f: tuple(round(c.evaluate(f), DECIMALES) for c in curvas)
            for f in range(desde, hasta + 1)}


def de_escena(nombres_rotulos, n: int) -> dict:
    """Firma por fotograma (0..n+1) de todo lo que ve la pasada principal."""
    fuera = _de_rotulos(nombres_rotulos)
    curvas = [c for idb in _bloques() if _clave(idb) not in fuera for c in _curvas(idb)]
    return _evaluar(curvas, 0, n + 1)


def de_capa(nombres_rotulos, camara, anclados, n: int) -> dict:
    """Firma por fotograma (0..n+1) de la capa de rótulos.

    `anclados`: {fotograma: True} donde se ve una etiqueta anclada en el mundo; ahí
    la posición de la cámara (y de su objetivo) también cuenta.
    """
    dentro = _de_rotulos(nombres_rotulos)
    curvas = [c for idb in _bloques() if _clave(idb) in dentro for c in _curvas(idb)]
    lente = _curvas(camara.data)
    mundo = _curvas(camara)
    for restriccion in camara.constraints:
        destino = getattr(restriccion, "target", None)
        if destino is not None:
            mundo += _curvas(destino)
    base = _evaluar(curvas + lente, 0, n + 1)
    posicion = _evaluar(mundo, 0, n + 1)
    return {f: base[f] + (posicion[f] if anclados.get(f) else ()) for f in base}
