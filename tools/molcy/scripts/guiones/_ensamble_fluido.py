"""Plan experimental de Ensamble: torsión y orientación combinadas, cámara fija."""
from __future__ import annotations

from nucleo import torsiones


def configurar(montado, config):
    if config is None:
        return
    from variables.presentacion import validar_ensamble
    cfg = validar_ensamble(config)
    extra = montado.extra
    candidatos = extra.get("rigs_torsionales") or {}
    indice = cfg.get("conformero")
    if indice is None:
        indice = next(iter(candidatos), None)
    if indice not in candidatos:
        motivos = extra.get("rigs_no_disponibles") or {}
        raise torsiones.RigNoDisponible(
            f"no hay torsión elegible para la entrada {indice}: {motivos}")
    elegido = candidatos[indice]
    todas = list(extra.get("conformeros") or [])
    nubes = list(extra.get("puntos_conformeros") or [])
    pos = next(i for i, c in enumerate(todas) if c["indice"] == indice)
    extra["conformeros_completos"] = todas
    extra["poses_completas"] = list(extra.get("poses") or [])
    extra["conteos_completos"] = {
        "conformeros": len(todas), "corridas": len(extra.get("corridas") or []),
        "poses": len(extra["poses_completas"])}
    extra["conformeros"] = [todas[pos]]
    extra["puntos_conformeros"] = [nubes[pos]] if nubes else []
    extra["corridas"] = []
    extra["puntos_corridas"] = []
    extra["poses"] = extra["poses_completas"][:2]
    extra["puntos_poses"] = list(extra.get("puntos_poses") or [])[:2]
    extra["ensamble_fluido"] = {
        **cfg, "conformero": indice, "rig": elegido["rig"], "nombre": elegido["nombre"],
        "contrato": "excursion_ilustrativa_anclada", "giro_presentacion_grados": 60.0}
    montado.notas.append(
        "Ensamble experimental: excursión geométrica ilustrativa cerrada desde una "
        "entrada guardada. La torsión y el giro de presentación son simultáneos, con "
        "cámara estable; no reconstruyen una trayectoria física ni una ruta de docking. "
        "Sólo los extremos guardados y las poses posteriores tienen datos científicos.")


def rangos(fps):
    # Tiempos de lectura ya incluidos: no agregar congelaciones de montaje.
    return {"sitio": (1, fps), "conformeros": (fps + 1, 9 * fps),
            "corridas": (9 * fps + 1, 10 * fps),
            "validacion": (10 * fps + 1, 16 * fps),
            "salida": (16 * fps + 1, 20 * fps)}


def ventana_movimiento(rangos_, fps):
    return rangos_["conformeros"][0] + fps, rangos_["conformeros"][1] - fps


def ventanas_poses(rangos_, numero):
    a, b = rangos_["validacion"]
    n = min(2, numero)
    return [(a + i * (b - a + 1) // n, a + (i + 1) * (b - a + 1) // n - 1)
            for i in range(n)] if n else []


def camara_fija(estados, rangos_, numero_poses):
    """Congela TODOS los parámetros de cámara en cada pausa ya presupuestada."""
    out = list(estados)
    for a, b in [rangos_["conformeros"], *ventanas_poses(rangos_, numero_poses)]:
        fijo = dict(estados[(a + b) // 2 - 1])
        for f in range(a, b + 1):
            out[f - 1] = dict(fijo)
    return out


def mostradas(montado):
    extra = montado.extra
    return {"conformeros": 1, "corridas": 0, "poses": len(extra["poses"]),
            "poses_en_conjunto": len(extra["poses_completas"]),
            "disponibles": dict(extra["conteos_completos"]),
            "intermedios": "ilustrativos_sin_evaluacion",
            "contrato": "excursion_ilustrativa_anclada"}


def rotulos(rangos_, formato, fps, montado, controles):
    extra, cfg = montado.extra, montado.extra["ensamble_fluido"]
    i, escala = cfg["conformero"], formato.escala_texto * .59
    a, b = rangos_["conformeros"]
    inicio, fin = ventana_movimiento(rangos_, fps)
    out = []

    def poner(ident, texto, ventana, esquina="superior_izquierda", escala_relativa=1.0):
        out.append({"id": ident, "texto": texto, "ventana": ventana,
                    "esquina": esquina, "escala": escala * escala_relativa})

    total = extra["conteos_completos"]
    poner("yf_intro", "ENSAMBLE CONFORMACIONAL\nENTRADAS Y POSES DE VINA", rangos_["sitio"])
    poner("yf_ancla_antes", f"ENTRADA {i} GUARDADA\nGEOMETRIA DE LA CORRIDA", (a, inicio - 1))
    poner("yf_ilustracion", "TRANSICION ILUSTRATIVA\n"
          "TORSION + GIRO / SIN ENERGIA NI CONTROLES", (inicio, fin), escala_relativa=.90)
    poner("yf_ancla_despues", f"ENTRADA {i} GUARDADA\nREGRESO A LA MISMA GEOMETRIA", (fin + 1, b))
    poner("yf_cobertura",
          f"1/{total['conformeros']} ENTRADAS MOSTRADAS\n"
          "DESPUES: POSES OBTENIDAS CON VINA", rangos_["corridas"])
    for pose, ventana in zip(extra["poses"], ventanas_poses(rangos_, len(extra["poses"]))):
        afinidad = pose.get("afinidad")
        energia = f"{afinidad:.2f} KCAL/MOL" if isinstance(afinidad, (float, int)) else "NO DISPONIBLE"
        texto = (f"POSE {pose['rank']} GUARDADA | ENTRADA {pose['conformero']}\n"
                 f"VINA {energia}\n{controles(pose.get('controles'), 'CONTROLES FISICOS')}")
        if extra.get("contactos_visibles", True):
            cuenta = pose.get("contactos") or {}
            texto += (f"\nLINEAS: POLARES {cuenta.get('polares', 0)} | "
                      f"APOLARES {cuenta.get('hidrofobicos', 0)}")
        poner(f"yf_pose_{pose['rank']}", texto, ventana)
    poner("yf_final", f"{len(extra['poses'])}/{total['poses']} POSES DETALLADAS\n"
          f"{total['poses']}/{total['poses']} EN CONJUNTO\n"
          "CONTROLES APLICADOS DESPUES DEL DOCKING", rangos_["salida"])
    return out


def animar(rangos_, fps, montado, frames):
    import bpy
    from nucleo.horneado import hornear
    extra, cfg = montado.extra, montado.extra["ensamble_fluido"]
    inicio, fin = ventana_movimiento(rangos_, fps)
    objeto = bpy.data.objects.get(cfg["nombre"])
    if objeto is None:
        raise torsiones.RigNoDisponible("el objeto de la entrada guardada no existe")
    copia = torsiones.hornear_objeto(objeto, cfg["rig"], inicio, fin, frames, cfg["variante"])
    asignados = {cfg["nombre"]: [(rangos_["conformeros"][0], inicio - 1),
                                 (fin + 1, rangos_["conformeros"][1])],
                 copia.name: [(inicio, fin)]}
    for p, v in zip(extra["poses"], ventanas_poses(rangos_, len(extra["poses"]))):
        asignados.setdefault(p["nombre"], []).append(v)
        for nombre in (extra.get("contactos_por_pose") or {}).get(p["rank"], []):
            asignados.setdefault(nombre, []).append(v)
    for p in extra["poses_completas"]:
        asignados.setdefault(p["nombre"], []).append(rangos_["salida"])
    nombres = ([c["nombre"] for c in extra["conformeros_completos"]]
               + [p["nombre"] for p in extra["poses_completas"]]
               + [n for ns in (extra.get("contactos_por_pose") or {}).values() for n in ns]
               + [copia.name])
    for nombre in dict.fromkeys(nombres):
        obj = bpy.data.objects.get(nombre)
        if obj is None:
            continue
        ventanas = asignados.get(nombre, [])
        oculto = [0.0 if any(a <= f <= b for a, b in ventanas) else 1.0 for f in frames]
        for ruta in ("hide_render", "hide_viewport"):
            hornear(obj, ruta, -1, frames, oculto, "CONSTANT")
    # En automático, la demostración de entrada no ocurre visualmente dentro
    # del receptor: no se sugiere un recorrido físico ni se dibujan choques ficticios.
    modo = (montado.medido.get("presentacion") or {}).get("receptor", "automatico")
    if modo == "automatico":
        receptor = bpy.data.objects.get(extra.get("receptor_contexto") or "")
        if receptor is not None:
            oculto = [1.0 if rangos_["conformeros"][0] <= f <= rangos_["corridas"][1]
                      else 0.0 for f in frames]
            for ruta in ("hide_render", "hide_viewport"):
                hornear(receptor, ruta, -1, frames, oculto, "CONSTANT")
    montado.medido["mostradas_en_el_video"] = mostradas(montado)
    montado.medido["ensamble_fluido"] = {
        **{k: v for k, v in cfg.items() if k != "nombre"},
        "intermedios": "geometria_ilustrativa_sin_energia_ni_controles",
        "ventana_movimiento": [inicio, fin], "camara": "estable",
        "fotogramas_escena": len(frames), "fps": fps,
        "cierre": "se_conserva_completo_segun_formato"}
