"""El receptor: cinta, huecos y varillas de hotspots. CONSTANTE.

Siempre se dibuja `prepared.pdb`, que es el receptor que el acoplamiento
ejecuta de verdad. Eso satisface POR CONSTRUCCION las prohibiciones sobre
aguas, metales y cofactores: lo que no esta en el archivo no puede dibujarse
mal. Si algun dia hace falta ensenar el hemo de un P450 o el zinc de una
anhidrasa, el contrato lo permite sobre `deposited.pdb` rotulado como ausente
del calculo, y eso seria otro sujeto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import bl_ext.blender_org.molecularnodes as mn
import bpy
import numpy as np
from mathutils import Vector

from . import arte
from .ciencia import Hotspot, Paquete


@dataclass
class Receptor:
    molecula: Any = None
    censo_estructura: dict = field(default_factory=dict)
    objeto: Any = None
    mat_cartoon: Any = None
    mat_hotspots: Any = None
    hotspots: list[Hotspot] = field(default_factory=list)
    segmentos: int = 0
    notas: list[str] = field(default_factory=list)


def montar(paq: Paquete, arte_importado: dict, n_hotspots: int = 3) -> Receptor:
    r = Receptor()
    r.molecula = mn.Molecule.load(str(paq.ruta("prepared")), name=paq.pdb_id)
    r.objeto = r.molecula.object
    r.mat_cartoon = arte.copiar_material(arte_importado["CH1_Cartoon"],
                                         f"{paq.pdb_id}_Cartoon")

    # Estructura secundaria: si el PDB no trae registros HELIX/SHEET, se calcula
    # con DSSP. Es un dato, no decoracion.
    try:
        import numpy as _np
        ss = r.molecula.named_attribute("sec_struct")
        if len(set(int(x) for x in _np.unique(ss))) < 2:
            bpy.context.view_layer.objects.active = r.objeto
            bpy.ops.mn.dssp_apply()
            r.notas.append("estructura secundaria calculada con DSSP: el PDB no "
                           "traia registros HELIX/SHEET utiles")
    except Exception as e:
        r.notas.append(f"no se pudo asegurar la estructura secundaria: {e}")

    r.censo_estructura = arte.pintar_por_estructura(
        r.molecula, con_cadena=len(paq.cadenas_conservadas or []) > 1)
    if r.censo_estructura:
        arte.usar_color_por_atomo(r.mat_cartoon)
        r.notas.append(f"carton coloreado por estructura secundaria: "
                       f"{r.censo_estructura}")

    # la cinta, partida en los huecos declarados por el contrato
    rid = r.molecula.named_attribute("res_id")
    lo, hi = int(rid.min()), int(rid.max())
    cadenas = paq.cadenas_conservadas or [paq.cadena_principal]
    for cad in cadenas:
        for a, b in paq.rangos_continuos(cad, lo, hi):
            if b - a < 2:
                continue
            r.molecula.add_style("cartoon", selection=f"resid {a}:{b}",
                                 material=r.mat_cartoon, name=f"cinta_{cad}_{a}")
            r.segmentos += 1
    if not r.segmentos:
        r.molecula.add_style("cartoon", material=r.mat_cartoon, name="cinta")
        r.segmentos = 1
    if paq.huecos:
        r.notas.append(
            f"cinta partida en {r.segmentos} segmentos por {len(paq.huecos)} "
            f"hueco(s); el mayor salta "
            f"{max(h.distancia_a for h in paq.huecos):.2f} A entre residuos "
            f"{max(paq.huecos, key=lambda h: h.distancia_a).desde} y "
            f"{max(paq.huecos, key=lambda h: h.distancia_a).hasta}")

    # Los hotspots se eligen aqui, pero las VARILLAS se crean despues, en
    # `poner_varillas()`: hay que esperar a saber a que residuos apuntan las
    # lineas de contacto para dibujarlos tambien. Ver el fallo de 1HWK.
    r.hotspots = paq.hotspots(n_hotspots)
    try:
        import numpy as _np
        n_h = int((r.molecula.named_attribute("atomic_number") == 1).sum())
    except Exception:
        n_h = 0
    if n_h:
        r.notas.append(
            f"{n_h} hidrogenos presentes en prepared.pdb NO se dibujan: a esta "
            "resolucion estan reconstruidos, y el contrato obliga a declararlos "
            "si aparecen en pantalla")
    descartados = [h.resname for h in paq.hotspots(None, solo_dibujables=False)
                   if h.resname.upper() in paq.SIN_CADENA_LATERAL]
    if descartados:
        r.notas.append(
            f"{len(descartados)} hotspot(s) sin cadena lateral descartados "
            f"({', '.join(sorted(set(descartados)))}): una etiqueta sobre una "
            "glicina apunta al vacio")
    return r


def poner_varillas(r: Receptor, paq: Paquete, extra_resids=()) -> list[int]:
    """Varillas de los hotspots MAS todo residuo que reciba una linea.

    El fallo que obliga a esto: en 1HWK se dibujaban varillas de
    {Arg590, Ser565, Leu853} y lineas de contacto hacia {Ser684, Glu559,
    Lys735}. Interseccion vacia. Los atomos de destino existen en
    `prepared.pdb` y son matematicamente correctos, pero sin estilo asignado no
    se renderizan: el espectador ve tres lineas punteadas apuntando al vacio.

    Una linea de contacto es una afirmacion sobre DOS atomos. Si uno de los dos
    no esta en pantalla, la afirmacion no se puede leer.
    """
    numeros = {h.numero for h in r.hotspots} | {int(x) for x in extra_resids}
    if not numeros:
        return []
    sel = " or ".join(f"(resid {n})" for n in sorted(numeros))
    # Fuera los hidrogenos: `prepared.pdb` los trae (449 en 1BN1, 966 en 1CX2)
    # y a esas resoluciones estan RECONSTRUIDOS. El contrato obliga a
    # declararlos si aparecen; ademas se leian como esferas blancas sueltas que
    # un lector confunde con iones.
    r.molecula.add_style(
        "ball_and_stick",
        selection=f"({sel}) and not backbone and not name H*",
        name="varillas")
    r.mat_hotspots = arte.material_del_estilo(r.molecula, "Ball and Stick",
                                              f"{paq.pdb_id}_Hotspots")
    nuevos = sorted(numeros - {h.numero for h in r.hotspots})
    if nuevos:
        r.notas.append(
            f"varillas anadidas para {len(nuevos)} residuo(s) que reciben linea "
            f"de contacto y no estaban entre los hotspots: {nuevos}. Sin esto "
            "las lineas apuntan a atomos no renderizados.")
    return sorted(numeros)


def anclar_gradiente(r: Receptor, pivote: Vector) -> None:
    """El gradiente de color del carton, al sitio activo de ESTE receptor."""
    nt = r.mat_cartoon.node_tree
    if "DEP_sub" in nt.nodes:
        nt.nodes["DEP_sub"].inputs[1].default_value = tuple(pivote)


def centro_de_residuo(molecula, numero: int, cadena_idx: int | None = None) -> Vector | None:
    """Centroide de la cadena lateral, en coordenadas de mundo.

    `cadena_idx` es imprescindible cuando el sitio esta repartido entre varias
    cadenas (110 de los 380): sin el, Asp25 de la cadena A y Asp25 de la B
    caen en el mismo numero de residuo y dan un centroide promediado entre las
    dos, con dos etiquetas identicas apuntando al mismo punto.
    """
    rid = molecula.named_attribute("res_id")
    pos = molecula.named_attribute("position")
    try:
        lado = molecula.named_attribute("is_side_chain").astype(bool)
    except Exception:
        lado = np.ones(len(rid), dtype=bool)
    sel = (rid == numero) & lado
    if cadena_idx is not None:
        try:
            sel = sel & (molecula.named_attribute("chain_id") == cadena_idx)
        except Exception:
            pass
    if not sel.any():
        sel = rid == numero
    if not sel.any():
        return None
    return Vector(pos[sel].mean(axis=0).tolist())


def indice_de_cadena(paq, letra: str) -> int | None:
    """Molecular Nodes numera las cadenas por orden de aparicion."""
    cadenas = paq.cadenas_conservadas or [paq.cadena_principal]
    return cadenas.index(letra) if letra in cadenas else None


def puntos(molecula, maximo: int = 4000) -> list[Vector]:
    pos = molecula.named_attribute("position")
    paso = max(1, len(pos) // maximo)
    return [Vector(p.tolist()) for p in pos[::paso]]
