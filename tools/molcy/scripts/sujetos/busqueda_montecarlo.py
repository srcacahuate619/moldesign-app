"""SUJETO: poses y estados retenidos de la búsqueda interna de Vina.

Todo lo que se dibuja sale de `docking.json` del paquete, que produce
molDesign-build: la caja son los parametros con los que CORRIO Vina (centro y
tamano en Angstrom), las poses son las que el motor devolvio con su afinidad,
y las instantáneas son configuraciones retenidas en monte_carlo.cpp tras la
optimización local. Nada se inventa aquí: sin la traza instrumentada, X se
abstiene (ver `disponible`).

El sitio biológico y la caja computacional no son equivalentes. Se conserva
el sistema de coordenadas del receptor y se distinguen los estados de una
réplica de las poses finales agregadas de todas las réplicas.
"""
from __future__ import annotations

from nucleo.ciencia import ESCALA
from variables.sujeto import Contexto, Montado, SujetoNoDisponible

ID = "busqueda_montecarlo"
DESCRIPCION = "Ligando dockeado, estados internos y poses finales de Vina."

MAX_POSES = None         # todas las poses devueltas por Vina
MAX_RECHAZADAS = 400     # las aceptadas se dibujan TODAS; el rechazo se muestrea

COLOR_CAJA = (0.36, 0.62, 1.0)
COLOR_ESFERA = (0.50, 0.72, 1.0)
COLOR_ACEPTADA = (1.0, 0.62, 0.20)
COLOR_RECHAZADA = (0.75, 0.32, 0.32)
COLOR_CAMINANTE = (1.0, 0.90, 0.55)


# ── disponibilidad: la cadena de buena fe antes de dibujar nada ─────────────
def disponible(paq) -> tuple[bool, str]:
    d = paq.dock
    if d is None:
        return False, ("el paquete no trae `docking.json` valido "
                       "(schema moldesign.dock/1 con caja y poses). Lo genera "
                       "molDesign-build: `scripts/scene_export/"
                       "build_docking_package.py --pdb-id ...`")
    traza = d.get("traza_interna") or {}
    if traza.get("tipo") != "vina_monte_carlo_bfgs_interno" or not traza.get("instantaneas"):
        return False, ("docking.json no trae estados de la busqueda interna "
                       "instrumentada de Vina; el muestreo independiente no sirve para X")
    faltantes = [p["archivo"] for p in d["poses"]
                 if not p.get("archivo") or paq.ruta_dock(p["archivo"]) is None]
    if faltantes:
        return False, ("docking.json cita poses que no estan en el paquete: "
                       + ", ".join(faltantes[:3]))
    faltantes = [p["archivo"] for p in traza["instantaneas"]
                 if not p.get("archivo") or paq.ruta_dock(p["archivo"]) is None]
    if faltantes:
        return False, ("faltan instantaneas internas de Vina: "
                       + ", ".join(faltantes[:3]))
    return True, (f"{len(d['poses'])} poses, "
                  f"{traza['pasos_totales']} pasos internos en {traza['replicas']} replicas")


# ── geometria ───────────────────────────────────────────────────────────────
def _material_emision(nombre: str, color: tuple, fuerza: float):
    """Material de emision puro: fundir() lo enciende por Strength."""
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    salida = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1.0)
    em.inputs["Strength"].default_value = fuerza
    nt.links.new(em.outputs["Emission"], salida.inputs["Surface"])
    return m


def _caja(nombre: str, centro_b: Vector, tam_b: Vector, grosor: float, mat):
    """Las doce aristas de la caja REAL de Vina como una curva biselada."""
    cx, cy, cz = centro_b
    sx, sy, sz = (t / 2.0 for t in tam_b)
    # esquinas ordenadas por bits: i = x + 2y + 4z
    V = [(cx + (sx if i & 1 else -sx), cy + (sy if i & 2 else -sy),
          cz + (sz if i & 4 else -sz)) for i in range(8)]
    aristas = [(0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3), (2, 6),
               (3, 7), (4, 5), (4, 6), (5, 7), (6, 7)]
    cu = bpy.data.curves.new(nombre, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = grosor
    cu.bevel_resolution = 0
    for a, b in aristas:
        s = cu.splines.new("POLY")
        s.points.add(1)
        s.points[0].co = (*V[a], 1.0)
        s.points[1].co = (*V[b], 1.0)
    cu.materials.append(mat)
    obj = bpy.data.objects.new(nombre, cu)
    bpy.context.scene.collection.objects.link(obj)
    return obj, V


def _esfera(nombre: str, centro_b: Vector, radio_b: float, mat):
    """La esfera de evidencia del sitio: translucida, y su radio se MIde."""
    me = bpy.data.meshes.new(nombre)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=radio_b,
                               matrix=Matrix.Translation(centro_b))
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(nombre, me)
    bpy.context.scene.collection.objects.link(obj)
    me.materials.append(mat)
    return obj


def _nube(nombre: str, puntos: list[Vector], radio: float, mat):
    """Una unica malla con todas las esferas de la traza (barata de rendir)."""
    if not puntos:
        return None
    bm = bmesh.new()
    for p in puntos:
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=radio,
                                   matrix=Matrix.Translation(p))
    me = bpy.data.meshes.new(nombre)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(nombre, me)
    bpy.context.scene.collection.objects.link(obj)
    me.materials.append(mat)
    return obj


def _trayectoria(nombre: str, puntos: list[Vector], grosor: float, mat):
    """Polilinea de estados aceptados; el guion revela el prefijo observado."""
    if len(puntos) < 2:
        return None
    cu = bpy.data.curves.new(nombre, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = grosor
    cu.bevel_resolution = 1
    cu.bevel_factor_end = 0.0
    spline = cu.splines.new("POLY")
    spline.points.add(len(puntos) - 1)
    for i, p in enumerate(puntos):
        spline.points[i].co = (*p, 1.0)
    cu.materials.append(mat)
    obj = bpy.data.objects.new(nombre, cu)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _silueta_anterior(nombre: str, mol, mat):
    """Enlaces de una muestra REAL anterior, para comparar dos estados.

    No une posiciones ni interpola un camino: cada segmento es un enlace
    inferido dentro de la geometria retenida que Vina escribio.
    """
    pos = mol.named_attribute("position")
    z = mol.named_attribute("atomic_number")
    cu = bpy.data.curves.new(nombre, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.016
    cu.bevel_resolution = 1
    for edge in mol.object.data.edges:
        a, b = tuple(edge.vertices)
        if int(z[a]) == 1 or int(z[b]) == 1:
            continue
        spline = cu.splines.new("POLY")
        spline.points.add(1)
        spline.points[0].co = (*pos[a], 1.0)
        spline.points[1].co = (*pos[b], 1.0)
    cu.materials.append(mat)
    obj = bpy.data.objects.new(nombre, cu)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _caminante(nombre, posicion, radio, mat):
    """Posicion absoluta solo en el objeto; geometria local centrada."""
    obj = _esfera(nombre, Vector((0, 0, 0)), radio, mat)
    obj.location = posicion
    return obj


def _material_translucido(nombre: str, color: tuple, alfa: float):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    bs = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"),
              None)
    if bs:
        bs.inputs["Base Color"].default_value = (*color, 1.0)
        bs.inputs["Alpha"].default_value = alfa
        bs.inputs["Roughness"].default_value = 0.6
    m.surface_render_method = "DITHERED"
    return m


# ── montaje ─────────────────────────────────────────────────────────────────
def cargar(paq, ctx: Contexto | None = None) -> Montado:
    ok, razon = disponible(paq)
    if not ok:
        raise SujetoNoDisponible(razon)
    ctx = ctx or Contexto()
    # Todo lo que dibuja se importa AQUI: `disponible` tiene que poder
    # responder sin Blender (la interfaz y las pruebas no lo tienen).
    global bpy, bmesh, mn, Matrix, Vector, arte, receptor
    import bmesh                                                             # noqa: E402
    import bpy                                                               # noqa: E402
    import bl_ext.blender_org.molecularnodes as mn                           # noqa: E402
    from mathutils import Matrix, Vector                                     # noqa: E402
    from nucleo import arte, receptor, contactos, interacciones              # noqa: E402
    d = paq.dock
    pref = f"{paq.pdb_id}_Dock_"

    m = Montado()
    from sujetos.ligando_cocristal import inferir_enlaces
    m.notas.append("La escena X muestra el ligando en sus poses calculadas "
                   "por Vina; la coordenada cristalografica no se dibuja.")
    centro_a = Vector(d["caja"]["centro"])
    tam_a = Vector(d["caja"]["tamano"])
    centro_b = centro_a * ESCALA
    tam_b = tam_a * ESCALA

    faltantes = [p["archivo"] for p in d["poses"]
                 if paq.ruta_dock(p["archivo"]) is None]
    if faltantes:
        raise SujetoNoDisponible("faltan archivos de pose: " + ", ".join(faltantes))

    # caja: los parametros con los que CORRIO el motor
    mat_caja = _material_emision(pref + "Caja", COLOR_CAJA, 1.5)
    caja_obj, esquinas = _caja(pref + "Caja", centro_b, tam_b,
                               max(tam_b) * 0.0015, mat_caja)
    m.objetos.append(caja_obj)
    m.materiales.append(mat_caja)
    s, sy, sz = (float(v) for v in tam_a)
    m.anclas.append(("caja", f"caja de busqueda: {s:g} x {sy:g} x {sz:g} A",
                     Vector(esquinas[7])))
    m.medido["caja_a"] = {"centro": [round(v, 3) for v in centro_a],
                          "tamano": [round(v, 3) for v in tam_a]}
    # La caja solo se encuadra en la retirada: el primer plano pertenece al
    # ligando dockeado, no al volumen computacional completo.
    m.dianas_generales += [Vector(v) for v in esquinas]

    # esfera de evidencia: radio medido por dispersion de hotspots
    radio_a = min(tam_a) / 2.0
    if ctx.receptor is not None and ctx.receptor.hotspots:
        distancias = []
        for h in ctx.receptor.hotspots:
            c = receptor.centro_de_residuo(ctx.receptor.molecula, h.numero,
                                           receptor.indice_de_cadena(paq, h.cadena))
            if c is not None:
                distancias.append((c - ctx.pivote).length / ESCALA)
        if distancias:
            radio_a = max(distancias)
            m.medido["esfera_radio_a"] = round(radio_a, 2)
    mat_esfera = _material_translucido(pref + "Esfera", COLOR_ESFERA, 0.10)
    # La esfera NO entra con la caja: durante la búsqueda sólo estorba (su grano
    # tapa el receptor). El guion la hace aparecer en la retirada final.
    m.extra["esfera"] = {"objeto": _esfera(pref + "Esfera", ctx.pivote,
                                           radio_a * ESCALA, mat_esfera),
                         "material": mat_esfera}

    traza = d["traza_interna"]
    m.extra["traza_interna"] = traza
    m.extra["instantaneas"] = []
    #: Geometría real (mundo, unidades de Blender) de cada estado y de cada pose:
    #: la cámara del guion encuadra con ella TODO lo que va a enseñar, no sólo
    #: la mejor pose.
    m.extra["puntos_instantaneas"] = []
    m.extra["puntos_poses"] = []
    mat_anterior = _material_emision(pref + "EstadoAnterior",
                                     (0.62, 0.48, 1.0), 2.5)
    anterior = None
    for i, p in enumerate(traza["instantaneas"], 1):
        ruta = paq.ruta_dock(p["archivo"])
        mol = mn.Molecule.load(str(ruta), name=f"{pref}EstadoInterno{i:02d}")
        inferir_enlaces(mol.object)
        mol.add_style("ball_and_stick", name=f"estado_interno_{i}")
        mat = arte.material_del_estilo(mol, "Ball and Stick",
                                       f"{pref}EstadoInterno{i:02d}_mat")
        if mat:
            arte.realzar_protagonista(mat)
        fantasma = (_silueta_anterior(pref + f"Anterior{i:02d}", anterior,
                                      mat_anterior)
                    if anterior is not None else None)
        m.extra["instantaneas"].append({"nombre": mol.object.name,
                                          "step": p["step"], "task": p["task"],
                                          "metrica_interna": p.get("metrica_interna"),
                                          "fantasma": (fantasma.name if fantasma else None)})
        m.extra["puntos_instantaneas"].append(arte.puntos_evaluados(mol.object))
        anterior = mol
    m.notas.append("La animacion muestra estados retenidos de la replica 1 "
                   f"de {traza['replicas']}; el contador total suma cada paso interno de las {traza['replicas']} "
                   "replicas. Los estados no son dinamica molecular ni una "
                   "interpolacion del movimiento fisico del ligando. La silueta "
                   "violeta corresponde exactamente a la muestra anterior.")

    # poses del acoplamiento, orden del motor, mejor primero
    poses = sorted(d["poses"], key=lambda p: p.get("rank", 99))
    m.extra["poses"] = []
    m.extra["contactos_por_pose"] = {}
    nombres = contactos.mapa_de_residuos(paq.ruta("prepared"))
    cadenas = paq.cadenas_conservadas or [paq.cadena_principal]
    presentados = [h.numero for h in (ctx.receptor.hotspots or [])]
    multicadena = len(cadenas) > 1
    mat_polar, mat_apolar = interacciones.materiales_de_linea(ctx.arte, pref)
    m.extra["materiales_contacto"] = [mat_polar, mat_apolar]
    datos_contactos = []
    m.extra["rotulos_por_pose"] = {}
    m.extra["colores_anclas"] = {}
    for p in poses:
        ruta = paq.ruta_dock(p["archivo"])
        mol = mn.Molecule.load(str(ruta), name=f"{pref}Pose{p['rank']}")
        # el PDB de la pose no trae CONECT (como site_ligand.pdb): enlaces por
        # distancia, misma convención declarada del ligando cocristalizado
        inferir_enlaces(mol.object)
        mol.add_style("ball_and_stick", name=f"pose{p['rank']}")
        mat = arte.material_del_estilo(mol, "Ball and Stick",
                                       f"{pref}Pose{p['rank']}_mat")
        if mat:
            arte.realzar_protagonista(mat)
        obj = mol.object
        m.secundarios.append(obj)
        m.extra["poses"].append({"nombre": obj.name, "rank": p["rank"],
                                  "afinidad": p.get("afinidad_kcal_mol"),
                                  "rmsd_vina_inferior_a": p.get("rmsd_vina_inferior_a"),
                                  "rmsd_vina_superior_a": p.get("rmsd_vina_superior_a")})
        if mat:
            m.materiales_secundarios.append(mat)
        c = arte.centro_evaluado(obj)
        # Contra TODOS los residuos del bolsillo de ESTA pose (no sólo contra los
        # hotspots del catálogo: 1J38 no trae ninguno y las nueve poses salían con
        # «polares 0 | apolares 0»); los hotspots que existan van primero.
        elegidos, n_pol, n_apo = interacciones.medir(
            ctx.receptor.molecula, mol, c, nombres=nombres, cadenas=cadenas,
            preferidos=presentados)
        lineas, rotulos = [], []
        for j, contacto in enumerate(elegidos):
            material = mat_apolar if contacto.tipo == "hidrofobico" else mat_polar
            linea = contactos.dibujar(
                f"{pref}Pose{p['rank']}_{contacto.tipo}_{j}", contacto, material)
            if linea is not None:
                lineas.append(linea.name)
            # Rótulo de la línea: residuo, clase y distancia (polar o apolar).
            # `dist*`: el motor las retira con las líneas si se apagan los contactos.
            ident = f"dist_p{p['rank']}_{j}"
            m.anclas.append((ident, interacciones.texto(contacto, multicadena),
                             contacto.medio))
            m.extra["colores_anclas"][ident] = interacciones.color(contacto)
            m.extra.setdefault("lineas_anclas", {})[ident] = (contacto.a.copy(), contacto.b.copy())
            rotulos.append(ident)
            if p["rank"] == 1:
                # La mejor pose también se rotula en el primer plano del sitio, que
                # es cuando el bolsillo se ve más de cerca.
                ident_sitio = f"dist_s_{j}"
                m.anclas.append((ident_sitio, interacciones.texto(contacto, multicadena),
                                 contacto.medio))
                m.extra["colores_anclas"][ident_sitio] = interacciones.color(contacto)
                m.extra["lineas_anclas"][ident_sitio] = (contacto.a.copy(), contacto.b.copy())
                m.extra.setdefault("rotulos_sitio", []).append(ident_sitio)
            datos_contactos.append({"pose": p["rank"], **interacciones.registro(contacto),
                                    "tipo_bruto": contacto.tipo})
        m.extra["rotulos_por_pose"][p["rank"]] = rotulos
        m.extra["contactos_por_pose"][p["rank"]] = lineas
        m.extra["poses"][-1]["contactos"] = {
            "polares": sum(c.tipo == "polar" for c in elegidos),
            "hidrofobicos": sum(c.tipo == "hidrofobico" for c in elegidos)}
        af = p.get("afinidad_kcal_mol")
        texto = f"#{p['rank']}" + (f"  {af:.1f} kcal/mol"
                                   if isinstance(af, (int, float)) else "")
        m.anclas.append((f"pose{p['rank']}", texto, c))
        m.dianas.append(c)
        m.extra["puntos_poses"].append(arte.puntos_evaluados(obj))
        if p["rank"] == 1:
            m.extra["ligando_dock_puntos"] = arte.puntos_evaluados(obj)
            m.medido["mejor_pose"] = {k: p.get(k) for k in
                                      ("afinidad_kcal_mol", "rmsd_cristal_a")}
            rmsd = p.get("rmsd_cristal_a")
            if isinstance(rmsd, (int, float)):
                m.anclas.append(("rmsd", f"RMSD {rmsd:.2f} A vs cristal", c))

    m.medido["n_poses_dibujadas"] = len(poses)
    m.medido["contactos"] = datos_contactos
    m.medido["residuos_de_contacto"] = sorted({c["resid"] for c in datos_contactos})
    #: El texto de pantalla de esta escena ocupa la esquina superior izquierda (NDC): los
    #: rótulos 3D no se colocan encima.
    m.extra["zona_texto_pantalla"] = [(-1.0, 0.45, 0.40, 1.0)]
    m.notas.append("Interacciones de cada pose final contra los residuos de su "
                   "bolsillo (hotspots del catalogo primero): polares y apolares, cada "
                   "una con su linea y su rotulo de residuo, clase y distancia. "
                   + interacciones.NOTA)
    m.medido["n_pasos"] = traza["pasos_totales"]
    m.medido["n_aceptados"] = traza["aceptados_totales"]
    m.medido["n_replicas"] = traza["replicas"]
    m.medido["n_instantaneas"] = len(traza["instantaneas"])
    m.medido["metricas_internas_por_muestra"] = [
        {"step": p["step"], **p["metrica_interna"]}
        for p in traza["instantaneas"] if p.get("metrica_interna")]
    m.medido["traza_es_busqueda_interna_vina"] = True
    m.medido["motor"] = d.get("motor", {})
    return m
