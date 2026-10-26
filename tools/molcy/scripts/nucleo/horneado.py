"""Claves por fotograma. CONSTANTE.

Todo el movimiento de esta maquina se hornea: una clave por fotograma con el
suavizado ya resuelto en la matematica, en vez de dejar interpolar a Blender.
Asi la curva es exactamente la calculada y no hay rebotes de Bezier en los
extremos, que es donde se notan.
"""
from __future__ import annotations


# ── suavizados ───────────────────────────────────────────────────────────
def ss(x: float) -> float:
    """Smoothstep: arranca y termina parado."""
    return x * x * (3 - 2 * x)


def eo(x: float) -> float:
    """Ease-out cuadratico: arranca rapido y frena."""
    return 1 - (1 - x) ** 2


def salida_con_velocidad(u: float, pendiente_final: float) -> float:
    """De 0 a 1, arrancando parado y llegando con la velocidad pedida.

    Sirve para encadenar dos planos sin que el primero frene del todo: entrega
    su velocidad residual al siguiente y el empalme no se nota.
    """
    return -2 * u ** 3 + 3 * u ** 2 + pendiente_final * (u ** 3 - u ** 2)


# ── acceso a curvas (Acciones con ranuras, Blender 4.4+) ─────────────────
def fcurves(idobj):
    ad = idobj.animation_data
    act = ad.action
    if hasattr(act, "fcurves"):          # API vieja
        return list(act.fcurves)
    out = []
    ranuras = [ad.action_slot] if ad.action_slot else list(act.slots)
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


def limpiar(idobj) -> None:
    """Quita la animacion de un datablock.

    Imprescindible tras `copy()`: las copias heredan la accion del original, y
    esa animacion pisa cualquier valor que se asigne despues, en cada cambio de
    fotograma.
    """
    if idobj is not None and getattr(idobj, "animation_data", None):
        idobj.animation_data_clear()


def limpiar_material(m) -> None:
    limpiar(m)
    if getattr(m, "use_nodes", False) and m.node_tree:
        limpiar(m.node_tree)


def hornear(idobj, ruta: str, indice: int, frames, valores, interp="LINEAR") -> None:
    idobj.keyframe_insert(data_path=ruta, index=indice, frame=frames[0])
    fc = next(c for c in fcurves(idobj)
              if c.data_path == ruta and (indice < 0 or c.array_index == indice))
    fc.keyframe_points.clear()
    fc.keyframe_points.add(len(valores))
    plano = []
    for f, v in zip(frames, valores):
        plano += [float(f), float(v)]
    fc.keyframe_points.foreach_set("co", plano)
    for kp in fc.keyframe_points:
        kp.interpolation = interp
    fc.update()


def visible_en(obj, frames, desde: int, hasta: int) -> None:
    """Hornea hide_render/hide_viewport como ventana dura."""
    oculto = [1.0 if (f < desde or f > hasta) else 0.0 for f in frames]
    hornear(obj, "hide_render", -1, frames, oculto, "CONSTANT")
    hornear(obj, "hide_viewport", -1, frames, oculto, "CONSTANT")


def curva(tramos, frames):
    """Curva 0..1 por fotograma desde tramos (f_ini, f_fin, v_ini, v_fin)."""
    vals = []
    for f in frames:
        v = 0.0 if f < tramos[0][0] else 1.0
        for (fa, fb, va, vb) in tramos:
            if f >= fb:
                v = float(vb)
            elif f > fa:
                v = va + (vb - va) * ss((f - fa) / (fb - fa))
        vals.append(v)
    return vals


# ── materiales ───────────────────────────────────────────────────────────
def nodo_por_tipo(nt, bl_idname):
    """Busca por tipo, NUNCA por nombre.

    Los materiales hechos a mano con la interfaz en espanol llevan
    "BSDF Principista"; los que genera Molecular Nodes, el nombre ingles.
    Buscar por nombre falla en la mitad de ellos.
    """
    for nd in nt.nodes:
        if nd.bl_idname == bl_idname:
            return nd
    return None


def fundir(m, frames, valores) -> str | None:
    """Anima la aparicion de un material, de superficie o de emision."""
    nt = m.node_tree
    bs = nodo_por_tipo(nt, "ShaderNodeBsdfPrincipled")
    if bs is not None:
        s = bs.inputs["Alpha"]
        base = s.default_value if s.default_value > 0 else 1.0
        i = list(bs.inputs).index(s)
        limpiar(nt)
        hornear(nt, f'nodes["{bs.name}"].inputs[{i}].default_value', -1, frames,
                [base * v for v in valores])
        return "alfa"
    em = nodo_por_tipo(nt, "ShaderNodeEmission")
    if em is not None:
        # una linea que brilla no se desvanece: se enciende
        s = em.inputs["Strength"]
        base = s.default_value if s.default_value > 0 else 1.0
        i = list(em.inputs).index(s)
        limpiar(nt)
        hornear(nt, f'nodes["{em.name}"].inputs[{i}].default_value', -1, frames,
                [base * v for v in valores])
        return "emision"
    return None


def indice_entrada(nodo, nombre: str) -> int:
    """Indice del zocalo VALUE con ese nombre.

    Un MapRange tiene `From Max` float y `From_Max_FLOAT3` vector con el mismo
    nombre visible; hay que filtrar por tipo.
    """
    return [i for i, s in enumerate(nodo.inputs)
            if s.name == nombre and s.type == "VALUE"][0]
