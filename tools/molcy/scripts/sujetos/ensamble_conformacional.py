"""SUJETO: el ensamble conformacional de una corrida de MolDesign.

Todo lo que se dibuja sale de `ensamble.json` del paquete, que produce
molDesign-build a partir de la corrida guardada: las conformaciones de entrada
(las que de verdad aportaron poses entregadas), las poses entregadas por la
piscina del ensamble y los controles físicos que el producto aplicó a cada una.
Sin ese contrato verificado, la escena se abstiene. El prototipo explícito
ensamble_fluido puede añadir una excursión GEOMÉTRICA ILUSTRATIVA cerrada desde
una entrada con rig verificado; no es una geometría medida ni una trayectoria,
y nunca recibe energía, contactos o controles físicos de una pose.

Qué es y qué NO es lo que se ve (el contrato lo declara y el acta lo repite):

- Las conformaciones son geometrías DISCRETAS de entrada (ETKDG + MMFF), no una
  película de rotaciones. Se alinean rígidamente a la mejor pose sólo para
  compararlas; Vina recibió cada una sin alinear. Pasar de una a otra es un
  corte, no un movimiento físico.
- Cada conformación fue una corrida independiente de Vina en la misma caja. Las
  poses se juntaron en UNA piscina y se reordenaron por afinidad observada: la
  mejor pose no prueba que su conformación sea «la correcta», sólo que Vina la
  puntuó mejor.
- Los controles físicos se aplicaron DESPUÉS del acoplamiento; no participan en
  la búsqueda. «No evaluada» no significa «inválida».
"""
from __future__ import annotations

import hashlib

from variables.sujeto import Contexto, Montado, SujetoNoDisponible

#: Zona de la pantalla (NDC: x0, y0, x1, y1) que ocupa el texto de datos de arriba a la izquierda y
#: donde no se colocan rótulos 3D. El bloque de una pose son CUATRO líneas y llega a x≈0.6 en un
#: formato vertical: con la zona de `x` (hasta 0.40) la etiqueta de un residuo lo pisaba.
ZONA_TEXTO_PANTALLA = (-1.0, 0.45, 0.75, 1.0)

ID = "ensamble_conformacional"
DESCRIPCION = ("Conformaciones de entrada, poses entregadas del ensamble de Vina "
               "y sus controles físicos.")


def _sha(ruta) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _pedir(paq, cosa: dict, que: str):
    """El archivo citado por una entrada del contrato, verificado, o el motivo."""
    ruta = paq.ruta_ensamble(cosa.get("archivo", ""))
    if ruta is None:
        return None, f"{que}: falta el archivo {cosa.get('archivo')!r}"
    if _sha(ruta) != cosa.get("sha256"):
        return None, f"{que}: el archivo no coincide con su SHA-256"
    return ruta, None


# ── disponibilidad: la cadena de buena fe antes de dibujar nada ─────────────
def disponible(paq) -> tuple[bool, str]:
    d = paq.ensamble
    if d is None:
        return False, ("el paquete no trae `ensamble.json` valido (schema "
                       "moldesign.ensamble/1 con caja, conformaciones y poses). Lo "
                       "genera molDesign-build desde una corrida de ensamble guardada")
    indices = set()
    for c in d["conformeros"]:
        _, falla = _pedir(paq, c, f"conformacion {c.get('indice')}")
        if falla:
            return False, falla
        indices.add(c.get("indice"))
    for p in d["poses"]:
        _, falla = _pedir(paq, p, f"pose {p.get('rank')}")
        if falla:
            return False, falla
        if p.get("conformero") not in indices:
            return False, (f"la pose {p.get('rank')} cita una conformacion "
                           f"({p.get('conformero')}) que el paquete no trae")
    resumen = d.get("resumen") or {}
    return True, (f"{len(d['conformeros'])} conformaciones con poses entregadas, "
                  f"{len(d['poses'])} poses entregadas de "
                  f"{resumen.get('poses_candidatas', '?')} candidatas")


# ── montaje ─────────────────────────────────────────────────────────────────
def _cargar_molecula(mn, arte, inferir_enlaces, ruta, nombre: str, estilo: str):
    """Una molécula en bolas y varillas, con su material de protagonista."""
    mol = mn.Molecule.load(str(ruta), name=nombre)
    # El PDB no trae CONECT: enlaces por distancia, misma convención declarada del
    # ligando cocristalizado y de las poses de la escena x.
    inferir_enlaces(mol.object)
    mol.add_style("ball_and_stick", name=estilo)
    mat = arte.material_del_estilo(mol, "Ball and Stick", f"{nombre}_mat")
    if mat:
        arte.realzar_protagonista(mat)
    return mol


def cargar(paq, ctx: Contexto | None = None) -> Montado:
    ok, razon = disponible(paq)
    if not ok:
        raise SujetoNoDisponible(razon)
    import bl_ext.blender_org.molecularnodes as mn                           # noqa: E402
    from nucleo import arte, contactos, interacciones                        # noqa: E402
    from sujetos.ligando_cocristal import inferir_enlaces                    # noqa: E402

    ctx = ctx or Contexto()
    d = paq.ensamble
    pref = f"{paq.pdb_id}_Ens_"
    m = Montado()
    resumen = d.get("resumen") or {}
    m.notas += [
        # SCI-A-025: no todas se minimizan con MMFF (sin parametros, quedan sin
        # minimizar); el metodo de cada una va en el acta (`conformeros`).
        "Las conformaciones son geometrias discretas de entrada generadas con ETKDG "
        "(cada una declara en el acta si se minimizo con MMFF94 o quedo sin minimizar), "
        "no una pelicula de rotaciones. Se alinearon rigidamente a la mejor pose solo "
        "para compararlas: Vina recibio cada una sin alinear y busco poses "
        "independientes en la misma caja. El corte de una a otra no es movimiento "
        "fisico.",
        "Las poses son las mejores de la piscina de todas las corridas, reordenada por "
        "la afinidad de Vina. Ese orden no prueba que una conformacion sea la correcta "
        "ni se compara con la afinidad medida.",
        "Los controles fisicos se aplicaron despues del acoplamiento y no participan en "
        "la busqueda ni rotan el ligando. «No evaluada» no significa «invalida».",
    ]

    # conformaciones de entrada ------------------------------------------------
    m.extra["conformeros"] = []
    m.extra["puntos_conformeros"] = []
    m.extra["receptor_contexto"] = ctx.receptor.objeto.name
    m.extra["rigs_torsionales"] = {}
    m.extra["rigs_no_disponibles"] = {}
    for c in d["conformeros"]:
        i = c["indice"]
        mol = _cargar_molecula(mn, arte, inferir_enlaces, paq.ruta_ensamble(c["archivo"]),
                               f"{pref}Conf{i:02d}", f"ens_conf_{i}")
        m.extra["conformeros"].append({
            "nombre": mol.object.name, "indice": i, "semilla": c.get("semilla"),
            "energia_mmff": c.get("energia_mmff"), "torsiones": c.get("torsiones") or [],
            "poses_entregadas": c.get("poses_entregadas"),
            "mejor_afinidad": c.get("mejor_afinidad_kcal_mol")})
        m.extra["puntos_conformeros"].append(arte.puntos_evaluados(mol.object))

        if c.get("rig_torsional"):
            from nucleo.torsiones import validar_rig, RigNoDisponible
            try:
                sdf = paq.ruta_ensamble(c.get("sdf", ""))
                if sdf is None or _sha(sdf) != c.get("sdf_sha256"):
                    raise RigNoDisponible("el SDF de entrada no coincide con su hash")
                rig = validar_rig(c["rig_torsional"], sdf_sha256=c["sdf_sha256"])
                lineas = paq.ruta_ensamble(c["archivo"]).read_text(encoding="utf-8").splitlines()
                pdb = [linea for linea in lineas if linea.startswith(("ATOM  ", "HETATM"))]
                identidad = [(linea[12:16].strip(), linea[76:78].strip().upper()) for linea in pdb]
                esperada = [(at["id"], at["elemento"].upper()) for at in rig["atomos"]]
                if identidad != esperada:
                    raise RigNoDisponible("los IDs o elementos del PDB no son los del rig")
                from nucleo.torsiones import validar_coordenadas
                validar_coordenadas(rig, [(float(l[30:38]), float(l[38:46]), float(l[46:54]))
                                         for l in pdb])
                m.extra["rigs_torsionales"][i] = {"nombre": mol.object.name, "rig": rig}
            except (RigNoDisponible, OSError, KeyError, ValueError) as exc:
                m.extra["rigs_no_disponibles"][i] = str(exc)
        else:
            m.extra["rigs_no_disponibles"][i] = "el paquete no trae un rig torsional"

    # poses entregadas, en el orden de la piscina ----------------------------
    poses = sorted(d["poses"], key=lambda p: p["rank"])
    m.extra["poses"] = []
    m.extra["puntos_poses"] = []
    m.extra["contactos_por_pose"] = {}
    m.extra["rotulos_por_pose"] = {}
    m.extra["colores_anclas"] = {}
    nombres = contactos.mapa_de_residuos(paq.ruta("prepared"))
    cadenas = paq.cadenas_conservadas or [paq.cadena_principal]
    presentados = [h.numero for h in (ctx.receptor.hotspots or [])]
    multicadena = len(cadenas) > 1
    mat_polar, mat_apolar = interacciones.materiales_de_linea(ctx.arte, pref)
    m.extra["materiales_contacto"] = [mat_polar, mat_apolar]
    datos_contactos = []
    for p in poses:
        rank = p["rank"]
        mol = _cargar_molecula(mn, arte, inferir_enlaces, paq.ruta_ensamble(p["archivo"]),
                               f"{pref}Pose{rank:02d}", f"ens_pose_{rank}")
        obj = mol.object
        centro = arte.centro_evaluado(obj)
        # Contra TODOS los residuos del bolsillo de ESTA pose; los hotspots que
        # existan van primero (misma regla que la escena x).
        elegidos, _n_pol, _n_apo = interacciones.medir(
            ctx.receptor.molecula, mol, centro, nombres=nombres, cadenas=cadenas,
            preferidos=presentados)
        lineas, rotulos = [], []
        for j, contacto in enumerate(elegidos):
            material = mat_apolar if contacto.tipo == "hidrofobico" else mat_polar
            linea = contactos.dibujar(f"{pref}Pose{rank}_{contacto.tipo}_{j}",
                                      contacto, material)
            if linea is not None:
                lineas.append(linea.name)
                # Sólo las LÍNEAS son «contactos»: si se apagan, las poses se quedan.
                m.secundarios.append(linea)
            ident = f"dist_p{rank}_{j}"
            m.anclas.append((ident, interacciones.texto(contacto, multicadena),
                             contacto.medio))
            m.extra["colores_anclas"][ident] = interacciones.color(contacto)
            m.extra.setdefault("lineas_anclas", {})[ident] = (contacto.a.copy(), contacto.b.copy())
            rotulos.append(ident)
            datos_contactos.append({"pose": rank, **interacciones.registro(contacto),
                                    "tipo_bruto": contacto.tipo})
        m.extra["rotulos_por_pose"][rank] = rotulos
        m.extra["contactos_por_pose"][rank] = lineas
        m.extra["poses"].append({
            "nombre": obj.name, "rank": rank, "conformero": p["conformero"],
            "rank_local": p.get("rank_local"), "afinidad": p.get("afinidad_kcal_mol"),
            "controles": p.get("controles"),
            "contactos": {"polares": sum(c.tipo == "polar" for c in elegidos),
                          "hidrofobicos": sum(c.tipo == "hidrofobico" for c in elegidos)}})
        m.dianas.append(centro)
        m.extra["puntos_poses"].append(arte.puntos_evaluados(obj))
        if rank == 1:
            m.extra["ligando_dock_puntos"] = arte.puntos_evaluados(obj)

    # corridas: la mejor pose entregada de cada conformación ---------------------
    # Si una conformación tiene poses entregadas, la mejor de ellas es la mejor de
    # su corrida: la piscina ordena por afinidad, así que si alguna de sus poses
    # llegó a las entregadas, también lo hizo la que Vina puso primera en ella.
    por_conformero: dict[int, dict] = {}
    for pose in m.extra["poses"]:
        previa = por_conformero.get(pose["conformero"])
        if previa is None or (pose["rank_local"] or 99) < (previa["rank_local"] or 99):
            por_conformero[pose["conformero"]] = pose
    m.extra["corridas"] = []
    m.extra["puntos_corridas"] = []
    puntos_de = {pose["rank"]: pts for pose, pts in zip(m.extra["poses"], m.extra["puntos_poses"])}
    for c in m.extra["conformeros"]:
        pose = por_conformero.get(c["indice"])
        if pose is None:
            continue
        m.extra["corridas"].append({"conformero": c["indice"], "rank": pose["rank"],
                                    "nombre": pose["nombre"], "rank_local": pose["rank_local"],
                                    "afinidad": pose["afinidad"]})
        m.extra["puntos_corridas"].append(puntos_de[pose["rank"]])

    m.extra["resumen"] = resumen
    m.extra["validacion"] = d.get("validacion")
    m.extra["contactos_visibles"] = True
    # El texto de pantalla ocupa la esquina superior izquierda: los rótulos 3D no se
    # colocan ahí (todos van ya por encima de la geometría, en la capa de rótulos).
    m.extra["zona_texto_pantalla"] = [ZONA_TEXTO_PANTALLA]
    m.notas.append("Interacciones de cada pose entregada contra los residuos de su "
                   "bolsillo (hotspots primero): polares y apolares, cada una con su "
                   "linea y su rotulo de residuo, clase y distancia. " + interacciones.NOTA)
    m.medido.update(
        caja_a=d["caja"], resumen=resumen, validacion=d.get("validacion"),
        # `minimizacion`: MMFF94, UFF, sin_minimizar o None si el exportador no la
        # declara (SCI-A-025); la nota de arriba remite aqui.
        conformeros=[{k: c.get(k) for k in ("indice", "semilla", "energia_mmff", "minimizacion",
                                            "mejor_afinidad_kcal_mol", "poses_entregadas")}
                     for c in d["conformeros"]],
        poses_entregadas=[{k: p.get(k) for k in ("rank", "conformero", "rank_local",
                                                 "afinidad_kcal_mol")} for p in poses],
        contactos=datos_contactos,
        residuos_de_contacto=sorted({c["resid"] for c in datos_contactos}),
        motor=d.get("motor", {}))
    return m
