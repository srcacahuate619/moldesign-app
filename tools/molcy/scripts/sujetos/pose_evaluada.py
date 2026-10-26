"""Vina top-1 de una corrida MolDesign, nunca el ligando cocristalizado."""
from __future__ import annotations

import hashlib

import bl_ext.blender_org.molecularnodes as mn

from nucleo import arte, contactos, interacciones
from variables.sujeto import Montado, SujetoNoDisponible

ID = "pose_evaluada"
DESCRIPCION = "Primera pose 3D persistida por una corrida concreta de Vina, con sus interacciones medidas."


def disponible(paq):
    d = paq.dock
    if d is None:
        return False, "la corrida no conserva docking.json con caja y poses"
    pose = d["poses"][0]
    ruta = paq.ruta_dock(pose.get("pdb_visual", ""))
    if ruta is None:
        return False, "falta la geometría PDB de la pose top-1"
    if hashlib.sha256(ruta.read_bytes()).hexdigest() != pose.get("pdb_visual_sha256"):
        return False, "el hash de la geometría visual no coincide"
    return True, "Vina top-1 con coordenadas y hash verificados"


def cargar(paq, ctx=None):
    ok, razon = disponible(paq)
    if not ok:
        raise SujetoNoDisponible(razon)
    pose = paq.dock["poses"][0]
    lig = mn.Molecule.load(str(paq.ruta_dock(pose["pdb_visual"])),
                           name=f"{paq.pdb_id}_vina_top1")
    lig.add_style("ball_and_stick", name="vina_top1")
    mat = arte.material_del_estilo(lig, "Ball and Stick", f"{paq.pdb_id}_VinaTop1")
    arte.realzar_protagonista(mat)
    m = Montado()
    m.objetos.append(lig.object)
    if mat:
        m.materiales.append(mat)
    centro = arte.centro_evaluado(lig.object)
    m.anclas.append(("vina_top1", "Vina top-1", centro))
    puntos = arte.puntos_evaluados(lig.object)
    m.dianas += puntos[::max(1, len(puntos) // 120)]
    m.medido["pose_rank"] = 1
    m.medido["afinidad_kcal_mol"] = pose.get("afinidad_kcal_mol")
    m.notas.append("Pose Vina top-1 de la corrida declarada; no es ligando cristalográfico.")
    m.notas.append("No se dibuja trayectoria de búsqueda: no se midió.")
    _interacciones(paq, ctx, lig, centro, m)
    return m


def _interacciones(paq, ctx, lig, centro, m) -> None:
    """Líneas polares y apolares entre la pose y el receptor, con su rótulo de residuo, clase y distancia."""
    if ctx is None or ctx.receptor is None or ctx.receptor.molecula is None:
        m.notas.append("sin contexto de receptor: no se midieron interacciones")
        return
    cadenas = paq.cadenas_conservadas or [paq.cadena_principal]
    presentados = [h.numero for h in (ctx.receptor.hotspots or [])]
    elegidos, n_pol, n_apo = interacciones.medir(
        ctx.receptor.molecula, lig, centro,
        nombres=contactos.mapa_de_residuos(paq.ruta("prepared")), cadenas=cadenas,
        preferidos=presentados)
    m.medido["interacciones"] = [interacciones.registro(c) for c in elegidos]
    m.medido["interacciones_candidatas"] = {"polares": n_pol, "apolares": n_apo}
    m.medido["residuos_de_contacto"] = sorted({c.resid for c in elegidos})
    if not elegidos:
        m.notas.append("no se midio ninguna interaccion polar (2.4-3.5 A) ni apolar "
                       "(2.8-4.5 A) entre la pose y el receptor")
        return
    mat_polar, mat_apolar = interacciones.materiales_de_linea(ctx.arte, f"{paq.pdb_id}_")
    m.materiales_secundarios += [mat_polar, mat_apolar]
    multicadena = len(cadenas) > 1
    colores = {}
    for i, c in enumerate(elegidos):
        material = mat_apolar if c.tipo == "hidrofobico" else mat_polar
        linea = contactos.dibujar(f"Contacto_{i}_{interacciones.tipo(c)}", c, material)
        if linea is not None:
            m.secundarios.append(linea)
        # `dist*`: el motor las trata como rótulo de distancia y las retira con las líneas.
        m.anclas.append((f"dist{i}", interacciones.texto(c, multicadena), c.medio))
        colores[f"dist{i}"] = interacciones.color(c)
        # La línea que explica el rótulo: ningún texto se coloca encima (`maestro`).
        m.extra.setdefault("lineas_anclas", {})[f"dist{i}"] = (c.a.copy(), c.b.copy())
    m.extra["colores_anclas"] = colores
    m.notas.append(f"{len(elegidos)} interaccion(es) dibujada(s) de {n_pol} polares y "
                   f"{n_apo} apolares medidas. " + interacciones.NOTA)
