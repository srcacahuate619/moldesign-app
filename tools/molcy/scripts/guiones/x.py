"""Escena X: ligando dockeado, estados internos de Vina y poses calculadas."""
from __future__ import annotations

import math

from nucleo.horneado import ss
from nucleo.interacciones import MAX_POR_TIPO
from variables.guion import Beat

NOMBRE = "x"
DESCRIPCION = "Ligando dockeado, busqueda interna instrumentada de Vina, poses y orbita final."
SUJETO = "busqueda_montecarlo"

#: Los lee `maestro.medir`, que es agnostico del guion pero no de sus constantes.
LENTE_GENERAL, LENTE_PRIMER_PLANO = 35.0, 50.0
EL_GENERAL, EL_PRIMER_PLANO = 12.0, -22.0
SWEEP_GENERAL = 338.0
#: Lo que el guion va a usar de verdad: contexto sobrio alrededor del sitio,
#: con giro final alrededor del complejo.
BARRIDO = 120.0
REPOSICION = 12.0
#: Cuánto gira la cámara mientras explora (grados), de la búsqueda a la convergencia.
DERIVA = 24.0
#: Aire de cada plano sobre lo que tiene que caber (`encuadre.distancia_visible`
#: multiplica la distancia): el sitio deja mucho receptor alrededor para que se
#: reconozca el bolsillo; la caja, la búsqueda y las poses casi llenan el cuadro
#: porque lo que se enseña es el recorrido entero.
MARGEN_SITIO, MARGEN_CAJA, MARGEN_SEGUIMIENTO = 2.2, 1.12, 1.6
#: Suavizado (σ, en fracción de segundo) del recorrido de la cámara: sin él cada
#: estado de la búsqueda la sacudiría de sitio.
SUAVIZADO_S = 0.15

#: El primer plano de esta escena encuadra la CAJA de acoplamiento (el
#: volumen donde corrió la búsqueda), que puede ser MÁS ancha que el núcleo
#: del receptor: en `convergencia` la cámara da un paso atrás a propósito.
#: Salida/control lo tolera SOLO cuando el guion lo declara aqui.
QC_PERMITE_ALEJAMIENTO = True
QC_DIANAS_FACTOR = 0.9

BEATS = [
    Beat("sitio", peso=2.0, papel="aproximar", requiere="sujeto"),
    Beat("caja", peso=1.5, papel="aproximar", requiere="sujeto"),
    Beat("busqueda", peso=5.0, papel="explorar", requiere="sujeto"),
    Beat("convergencia", peso=2.5, papel="explorar", requiere="sujeto"),
    Beat("salida", peso=2.5, papel="explorar", requiere="sujeto"),
    Beat("general", peso=3.0, papel="establecer"),
    Beat("reposo", peso=0.5, papel="reposo", minimo_fotogramas=2),
]


def ajustar_rangos(rangos, formato):
    """Fija el primer segundo y reserva los ultimos tres para la retirada."""
    if formato.bucle or not all(k in rangos for k in
                               ("sitio", "caja", "busqueda", "convergencia", "salida")):
        return rangos
    n = max(b for _, b in rangos.values())
    salida = min(3 * formato.fps, max(1, n // 3))
    sitio = min(formato.fps, max(1, (n - salida) // 4))
    if n <= 3 * formato.fps:
        sitio = min(sitio, max(1, formato.fps // 3))
    caja = min(formato.fps, max(1, (n - salida - sitio) // 3))
    if n <= 3 * formato.fps:
        caja = min(caja, max(1, formato.fps // 3))
    convergencia = min(4 * formato.fps,
                       max(1, (n - salida - sitio - caja) * (1 if n <= 3 * formato.fps else 2) // (2 if n <= 3 * formato.fps else 3)))
    busqueda = n - salida - sitio - caja - convergencia
    if busqueda < 1:
        return rangos
    largos = (sitio, caja, busqueda, convergencia, salida)
    nuevos, inicio = {}, 1
    for clave, largo in zip(("sitio", "caja", "busqueda", "convergencia", "salida"), largos):
        nuevos[clave] = (inicio, inicio + largo - 1)
        inicio += largo
    return nuevos


def _centro(puntos):
    """Centro de la caja envolvente: no se sesga hacia donde hay más átomos."""
    from mathutils import Vector
    xs, ys, zs = zip(*((p.x, p.y, p.z) for p in puntos))
    return Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                   (min(zs) + max(zs)) / 2))


def _radio(puntos, centro):
    return max((p - centro).length for p in puntos)


#: Direcciones (sin normalizar) con las que se muestrea la esfera del sujeto.
_DIRECCIONES = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
                (1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1),
                (-1, 1, 1), (-1, 1, -1), (-1, -1, 1), (-1, -1, -1))


def _visibilidad(centro, radio, desde, objeto_receptor):
    """Fracción de rayos que llegan a la esfera del sujeto sin que el RECEPTOR se interponga.

    `oclusion.visibilidad` cuenta cualquier objeto como obstáculo. Aquí la caja, la
    esfera de evidencia y las demás poses también están en la escena y, por ir
    delante, taparían siempre: sólo cuenta el receptor, y un rayo que toca otra
    cosa sigue su camino. El rayo termina al entrar en la esfera, así que las
    varillas del propio ligando no se cuentan como obstáculo.
    """
    import bpy
    from mathutils import Vector
    dg = bpy.context.evaluated_depsgraph_get()
    escena = bpy.context.scene
    limite = (centro - desde).length - radio * 1.05
    if limite <= 0.0:
        return 0.0
    destinos = [centro] + [centro + Vector(d).normalized() * radio * 0.8
                           for d in _DIRECCIONES]
    libres = 0
    for destino in destinos:
        v = destino - desde
        largo = v.length
        if largo < 1e-6:
            continue
        direccion, origen, restante, tapado = v / largo, desde.copy(), limite, False
        for _ in range(8):
            golpe, ubicacion, _n, _i, objeto, _m = escena.ray_cast(
                dg, origen, direccion, distance=restante)
            if not golpe:
                break
            if objeto is not None and objeto.name == objeto_receptor:
                tapado = True
                break
            avance = (ubicacion - origen).length + 1e-4
            origen = ubicacion + direccion * 1e-4
            restante -= avance
            if restante <= 0:
                break
        libres += 0 if tapado else 1
    return libres / len(destinos)


def ajustar_medidas(medidas, paq, rec, montado, formato, visibilidad=None):
    """Planifica la cámara con TODO lo que la escena va a enseñar.

    El plano anterior encuadraba sólo la mejor pose del ligando —con `distancia`,
    que subestima cuando el ligando queda delante del pivote—, así que en 1J38 la
    molécula salía más grande que el cuadro, sin sitio activo a la vista y con las
    demás poses y los estados de la búsqueda fuera de campo. Ahora cada beat tiene
    su plano, medido con la geometría real (`encuadre.distancia_visible`):

    - sitio: la mejor pose y su bolsillo, con aire alrededor;
    - caja: la caja de acoplamiento entera, donde corrió la búsqueda;
    - búsqueda: todos los estados retenidos y todas las poses;
    - convergencia: las poses finales.

    El azimut y la elevación se eligen midiendo qué ángulo deja el sitio sin
    receptor por delante.

    `visibilidad` sustituye esa medida (misma firma que `_visibilidad`): la escena
    `y` la cambia por la de los átomos del ligando, porque allí el protagonista es
    el propio ligando y no el volumen del sitio. Sin ella nada cambia.
    """
    visible = visibilidad or _visibilidad
    from nucleo import encuadre, receptor
    K = medidas["pivote"]
    extra = montado.extra or {}
    ligando = list(extra.get("ligando_dock_puntos", []))
    poses = [p for nube in extra.get("puntos_poses", []) for p in nube]
    estados_vina = [p for nube in extra.get("puntos_instantaneas", []) for p in nube]
    hotspots = []
    for h in rec.hotspots:
        c = receptor.centro_de_residuo(rec.molecula, h.numero,
                                      receptor.indice_de_cadena(paq, h.cadena))
        if c is not None:
            hotspots.append(c)
    sitio = ligando + hotspots
    if not sitio:
        sitio = [p for p in receptor.puntos(rec.molecula) if (p - K).length <= 0.8]
    if not sitio:
        return
    caja = list(montado.dianas_generales)
    L, aspecto = LENTE_PRIMER_PLANO, formato.aspecto
    objeto_receptor = rec.molecula.object.name

    ancla = _centro(sitio)
    radio_ancla = _radio(sitio, ancla)
    mejor = None
    for el in (-24.0, -12.0, 0.0, 12.0, 24.0):
        for az in range(0, 360, 15):
            dist = encuadre.distancia_visible(sitio, ancla, L, aspecto, el, [float(az)],
                                              MARGEN_SITIO)
            vis = visible(ancla, radio_ancla,
                               encuadre.posicion(ancla, az, el, dist), objeto_receptor)
            # La visibilidad manda; a igualdad (±0.05) gana la elevación más
            # cinematográfica y, después, el plano más cerrado.
            clave = (round(vis / 0.1), 1.0 - min(1.0, abs(el + 12.0) / 48.0), -dist)
            if mejor is None or clave > mejor[0]:
                mejor = (clave, float(az), el, dist, vis)
    _, az, el, Ds, vis = mejor

    def plano(puntos, margen, objetivo=None):
        objetivo = objetivo if objetivo is not None else _centro(puntos)
        return {"objetivo": objetivo,
                "dist": encuadre.distancia_visible(puntos, objetivo, L, aspecto, el,
                                                   [az], margen),
                "radio": _radio(puntos, objetivo)}

    def seguimiento(nubes):
        """Un plano por nube, con sus vecinas: la cámara sigue lo que se enseña y,
        al incluir la anterior y la siguiente, el cambio de plano no deja nada fuera."""
        planos = []
        for i in range(len(nubes)):
            grupo = [p for nube in nubes[max(0, i - 1):i + 2] for p in nube]
            if grupo:
                planos.append(plano(grupo, MARGEN_SEGUIMIENTO))
        return planos

    p_sitio = {"objetivo": ancla, "dist": Ds, "radio": radio_ancla}
    p_caja = plano(caja + sitio, MARGEN_CAJA, K if caja else None)
    p_estados = seguimiento(extra.get("puntos_instantaneas", []))
    p_poses = seguimiento(extra.get("puntos_poses", []))
    # Con la caja entera encuadrada la cámara está lo más abierta posible: ningún
    # plano de seguimiento puede pedir más (cuando la caja es menor que el
    # recorrido, la que manda es la mayor).
    p_caja["dist"] = max([p_caja["dist"]] + [p["dist"] for p in p_estados + p_poses])

    pose_sitio = {"azimut": az, "elevacion": el, "cobertura": round(vis, 4),
                  "distancia_requerida": round(Ds, 3), "criterio": "esfera_del_sitio",
                  "puntos": len(sitio)}
    medidas.update(azimut=az, elevacion=el, pose_sitio=pose_sitio,
                   visibilidad_azimut=round(vis, 3), radio_sitio=radio_ancla,
                   dist_sitio=Ds, dist_primer_plano=Ds,
                   plan_camara={"sitio": p_sitio, "caja": p_caja,
                                "estados_vina": p_estados, "poses": p_poses})
    # `medir` calcula el arco de la RETIRADA de `sitio_activo`, que esta escena no
    # recorre; su mínimo (0.000 con puntos dentro del propio ligando) avisaba de un
    # plano que no existe. Lo que sí se recorre de cerca es el sitio y cada pose.
    cerca = [visible(ancla, radio_ancla,
                          encuadre.posicion(p["objetivo"], az, el, p["dist"]),
                          objeto_receptor)
             for p in [p_sitio] + p_poses[:1]]
    medidas["arco"] = dict(medidas.get("arco") or {}, span=DERIVA, el_fin=el,
                           minimo=round(min(cerca), 4),
                           media=round(sum(cerca) / len(cerca), 4),
                           nota="planos de cerca de la escena x: sitio y convergencia")


def _portal_fantasma(K, pos, distancia, fuerza, medidas):
    from guiones.sitio_activo import _portal_fantasma as portal
    return portal(K, pos, distancia, fuerza, medidas)


#: Cada beat de la aproximación va del plano de uno al plano de otro.
_TRAMOS = {"sitio": ("sitio", "sitio"), "caja": ("sitio", "caja"),
           "busqueda": ("caja", "busqueda"), "convergencia": ("busqueda", "convergencia")}


def _planos(medidas):
    """Los planos que dejó `ajustar_medidas`; sin ellos, el plano único anterior."""
    K = medidas["pivote"]
    D0 = medidas["dist_primer_plano"]
    Ds = min(medidas.get("dist_sitio", D0), D0)
    rn = medidas.get("radio_sitio", medidas.get("radio_portal", Ds * 0.35))
    unico = {"objetivo": K, "dist": Ds, "radio": rn}
    planos = {nombre: dict(unico) for nombre in _TRAMOS}
    planos.update({k: v for k, v in (medidas.get("plan_camara") or {}).items()
                   if k in _TRAMOS})
    return planos


def _mezcla(a, b, u):
    return a + (b - a) * u


def _suavizar(serie, sigma):
    """Media gaussiana de una serie de números o Vector; los extremos se repiten."""
    n = len(serie)
    if sigma <= 0 or n < 3:
        return list(serie)
    radio = max(1, int(3 * sigma))
    pesos = [math.exp(-0.5 * (k / sigma) ** 2) for k in range(-radio, radio + 1)]
    total = sum(pesos)
    salida = []
    for i in range(n):
        acumulado = None
        for k, peso in zip(range(-radio, radio + 1), pesos):
            valor = serie[min(max(i + k, 0), n - 1)] * peso
            acumulado = valor if acumulado is None else acumulado + valor
        salida.append(acumulado / total)
    return salida


def _interpolar(controles, f):
    """Valor lineal en el fotograma `f` entre controles (fotograma, objetivo, dist, radio)."""
    if f <= controles[0][0]:
        return controles[0][1:]
    for (f0, *v0), (f1, *v1) in zip(controles, controles[1:]):
        if f <= f1:
            u = (f - f0) / max(f1 - f0, 1)
            return tuple(_mezcla(a, b, u) for a, b in zip(v0, v1))
    return controles[-1][1:]


def _recorrido(medidas, rangos, fps):
    """Objetivo, distancia y radio por fotograma de sitio → caja → búsqueda → convergencia.

    Con un plano por estado y por pose (`plan_camara`) la cámara sigue lo que se
    está enseñando —los estados lejanos de la caja abren el plano, los que
    convergen lo cierran— y el recorrido se suaviza para que no sacuda. Sin esos
    planos (medidas de otra versión) devuelve None y manda el plano único.
    """
    plan = medidas.get("plan_camara") or {}
    if not (plan.get("estados_vina") and plan.get("poses")
            and all(k in rangos for k in _TRAMOS)):
        return None
    sitio, caja = plan["sitio"], plan["caja"]
    entrada = lambda p: (p["objetivo"], p["dist"], p["radio"])      # noqa: E731
    controles = [(1, *entrada(sitio)), (rangos["sitio"][1], *entrada(sitio)),
                 (rangos["caja"][1], *entrada(caja)),
                 (rangos["busqueda"][0], *entrada(caja))]
    for ventana, p in zip(ventanas_instantaneas(rangos, len(plan["estados_vina"])),
                          plan["estados_vina"]):
        controles.append(((ventana[0] + ventana[1]) / 2, *entrada(p)))
    for ventana, p in zip(ventanas_poses(rangos, len(plan["poses"])), plan["poses"]):
        controles.append(((ventana[0] + ventana[1]) / 2, *entrada(p)))
    fin = rangos["convergencia"][1]
    controles.append((fin, *entrada(plan["poses"][-1])))
    controles.sort(key=lambda c: c[0])
    crudo = [_interpolar(controles, f) for f in range(1, fin + 1)]
    sigma = SUAVIZADO_S * max(1, fps)
    objetivos = _suavizar([c[0] for c in crudo], sigma)
    distancias = _suavizar([c[1] for c in crudo], sigma)
    radios = _suavizar([c[2] for c in crudo], sigma)
    return {f + 1: (objetivos[f], distancias[f], radios[f]) for f in range(fin)}


def estados(medidas, rangos, n_frames, formato, experimental=False):
    from nucleo import encuadre
    P = medidas["centro_general"]
    planos = _planos(medidas)
    seguido = _recorrido(medidas, rangos, formato.fps)
    fin_conv = rangos.get("convergencia", (1, 1))[1]
    if seguido:
        cierre = seguido[fin_conv]
        fin = {"objetivo": cierre[0], "dist": cierre[1], "radio": cierre[2]}
    else:
        fin = planos["convergencia"]
    # La salida siempre se aleja fisicamente, incluso con una caja muy grande.
    D1 = max(medidas["dist_general"], fin["dist"] * 1.12)
    A0 = medidas["azimut"]
    Ar = A0 + REPOSICION
    ec = medidas.get("elevacion", EL_PRIMER_PLANO)
    eg = medidas.get("elevacion_general", EL_GENERAL)
    gc, gg = medidas["gradiente_cerca"], medidas["gradiente_general"]
    # El disolvente de lo que queda pegado a la lente crece con la distancia de
    # la cámara: con el plano único anterior eran 8 y 20 cm de escena a 1.07.
    cercano = lambda d: (d * 0.076, d * 0.19)                       # noqa: E731
    out = []
    for f in range(1, n_frames + 1):
        beat = next((k for k, (a, b) in rangos.items() if a <= f <= b), "reposo")
        a, b = rangos.get(beat, (f, f))
        u = ss((f - a) / max(b - a, 1))
        L, el, az, grad = LENTE_PRIMER_PLANO, ec, A0, gc
        fuerza = 1.0
        if beat in _TRAMOS:
            if seguido:
                T, D, radio = seguido[f]
            else:
                de, hacia = (planos[k] for k in _TRAMOS[beat])
                T = _mezcla(de["objetivo"], hacia["objetivo"], u)
                D = _mezcla(de["dist"], hacia["dist"], u)
                radio = _mezcla(de["radio"], hacia["radio"], u)
            diso = cercano(D)
            # La cámara se asienta en el ángulo elegido y deriva despacio mientras
            # explora: el paralaje deja ver la profundidad del bolsillo.
            if beat == "caja":
                az = A0 + REPOSICION * u
            elif beat in ("busqueda", "convergencia"):
                a0, b0 = rangos["busqueda"][0], rangos["convergencia"][1]
                az = Ar + DERIVA * (f - a0) / max(b0 - a0, 1)
        elif beat == "salida":
            az = Ar + DERIVA + BARRIDO * u
            T = _mezcla(fin["objetivo"], P, u)
            D = _mezcla(fin["dist"], D1, u)
            radio = fin["radio"]
            L = LENTE_PRIMER_PLANO + (LENTE_GENERAL - LENTE_PRIMER_PLANO) * u
            el = ec + (eg - ec) * u
            grad = gc + (gg - gc) * u
            fuerza = 1.0 - u
            diso = tuple(v + (z - v) * u for v, z in zip(cercano(fin["dist"]), (0.02, 0.05)))
        else:       # general, reposo
            T, D, L, el, grad = P.copy(), D1, LENTE_GENERAL, eg, gg
            radio = fin["radio"]
            az = A0 + BARRIDO * (u if beat == "general" else 1.0)
            if formato.bucle:
                az = A0 + 360.0 * (f - 1) / n_frames
            fuerza, diso = 0.0, (0.02, 0.05)
        pos = encuadre.posicion(T, az, el, D)
        estado = dict(pos=pos, objetivo=T, lente=L,
                      diafragma=14.0 if formato.profundidad_de_campo else 32.0,
                      gradiente=grad, diso0=diso[0], diso1=diso[1], dist=D,
                      giro=math.radians(az - A0))
        if experimental:
            # El portal atraviesa el receptor por el eje cámara → objetivo con el
            # radio de lo que se enseña en ese plano.
            estado["portal"] = _portal_fantasma(T, pos, D, fuerza,
                dict(medidas, radio_portal=radio))
        out.append(estado)
    return out


#: Una pose se ve menos de esto y su rótulo no llega a leerse: se omite (la vista de CPU, de
#: tres segundos, reparte las nueve poses en unos pocos fotogramas cada una).
MINIMO_ROTULO = 6
#: Cuánto se congela la imagen para leer los rótulos de una pose (o del sitio).
PAUSA_LECTURA_S = 1.0


def anotaciones(rangos, formato, fps, n_sujeto: int = 1, montado=None):
    """Cuándo se ve cada rótulo 3D de interacción, alineado con `montado.anclas`.

    La cámara de esta escena no se detiene nunca (sigue a cada pose), y un rótulo
    anclado que viaja con la escena se ladea y no se lee. Así que los de cada pose
    se ven en UN fotograma —a mitad de su ventana, con la cámara de ese instante—
    y el montaje lo congela `PAUSA_LECTURA_S` (`variables/pausas.py`): la imagen se
    detiene, se leen, y la escena sigue sin ellos. Las de la mejor pose también en
    el primer plano del sitio. Las anclas que no son interacciones (la caja, el
    número de pose…) no se rotulan: su entrada es None.
    """
    plan = {"hotspots": [], "sujeto": [], "pausas": []}
    if montado is None or not formato.etiquetas_3d:
        return plan
    extra = montado.extra or {}
    por_pose = extra.get("rotulos_por_pose") or {}
    del_sitio = set(extra.get("rotulos_sitio") or [])
    poses = extra.get("poses") or []
    ventana_de = dict(zip((p["rank"] for p in poses),
                          ventanas_poses(rangos, len(poses))))
    sitio = rangos.get("sitio")

    nubes = {p["rank"]: nube for p, nube in zip(poses, extra.get("puntos_poses") or [])}

    def entrada(a, b, rank):
        if b - a + 1 < MINIMO_ROTULO:
            return None
        f = (a + b) // 2
        return {"ventana": (f, f), "colocar_en": f, "reservar": nubes.get(rank),
                "fundido": []}

    for ident, _texto, _pos in montado.anclas:
        cfg = None
        if ident in del_sitio and sitio:
            # El primer plano del sitio, con la cámara quieta.
            cfg = entrada(sitio[0] + 2, sitio[1], 1)
        else:
            rank = next((r for r, ids in por_pose.items() if ident in ids), None)
            if rank in ventana_de:
                cfg = entrada(*ventana_de[rank], rank)
        plan["sujeto"].append(cfg)
    for f in sorted({c["colocar_en"] for c in plan["sujeto"] if c}):
        plan["pausas"].append({"en": f, "tipo": "lectura", "segundos": PAUSA_LECTURA_S})
    return plan


def aparicion_del_sujeto(rangos, fps):
    """La caja real aparece cuando la camara se abre para enseñarla (beat `caja`).

    Antes entraba en la retirada final: durante toda la búsqueda no había nada
    que dijera DÓNDE se buscaba.
    """
    clave = "caja" if "caja" in rangos else "salida"
    if clave not in rangos:
        return None
    a, b = rangos[clave]
    return {"ventana": (a, None), "fundido": [(a, a + max(5, int(0.9 * fps)), 0, 1)]}


def aparicion_de_hotspots(rangos, fps):
    """Los hotspots del receptor se presentan en el plano general: son la
    evidencia biológica antes de que la caja (el cómputo) se dibuje."""
    if "sitio" not in rangos:
        return None
    a, b = rangos["sitio"]
    return {"ventana": (a, None), "fundido": [(a, a, 1, 1)]}


def aparicion_de_contactos(rangos, fps):
    """Cada pose tiene su propia ventana, horneada por animar_sujeto."""
    return None


def titulo(rangos, formato, fps):
    return None


def ventanas_poses(rangos, n):
    """Una pose de Vina por turno; todos los rangos son inclusivos."""
    if n < 1 or "convergencia" not in rangos:
        return []
    a, b = rangos["convergencia"]
    largo = b - a + 1
    return [(a + (i * largo) // n,
             a + ((i + 1) * largo) // n - 1) for i in range(n)]


def ventanas_instantaneas(rangos, n):
    if n < 1 or "busqueda" not in rangos:
        return []
    a, b = rangos["busqueda"]
    largo = b - a + 1
    return [(a + (i * largo) // n,
             a + ((i + 1) * largo) // n - 1) for i in range(n)]


def rotulos_datos(rangos, formato, fps, montado):
    """Distingue los pasos internos reales de las poses finales."""
    if not formato.rotulos_pantalla:
        return []
    poses = (montado.extra or {}).get("poses") or []
    traza = (montado.extra or {}).get("traza_interna") or {}
    if not poses:
        return []
    total = len(poses)
    mejor = poses[0].get("afinidad")
    energia = f"{mejor:.2f} kcal/mol" if isinstance(mejor, (int, float)) else ""
    escala = formato.escala_texto * 0.62
    out = []
    def poner(id_, texto, ventana, esquina="superior_izquierda"):
        out.append(dict(id=id_, texto=texto, ventana=ventana,
                        esquina=esquina, escala=escala))
    if "sitio" in rangos:
        a = rangos["sitio"][0]
        b = rangos.get("caja", rangos["sitio"])[1]
        poner("vina_ligando", f"RESULTADO ANTICIPADO\nVINA  |  {total} POSES", (a, b))
    instantaneas = (montado.extra or {}).get("instantaneas") or []
    if "busqueda" in rangos and traza.get("torsiones_activas"):
        poner("vina_torsiones", f"{traza['torsiones_activas']} TORSIONES ACTIVAS",
              rangos["busqueda"])
    for i, (muestra, ventana) in enumerate(zip(
            instantaneas, ventanas_instantaneas(rangos, len(instantaneas)))):
        anterior = "\nVIOLETA: MUESTRA ANTERIOR" if muestra.get("fantasma") else ""
        metrica = muestra.get("metrica_interna") or {}
        lectura = ""
        if metrica:
            estado = "PROPUESTA ACEPTADA" if metrica["aceptada_en_paso"] else "PROPUESTA RECHAZADA"
            # Una línea por dato: en vertical caben ~36 caracteres y la antigua
            # «ESTADO RETENIDO … | PROPUESTA ACEPTADA» (43) se salía del cuadro.
            lectura = (f"\nESTADO RETENIDO {metrica['retenida']:.2f}\n{estado}"
                       f"\nMEJOR DE ESTA REPLICA {metrica['mejor_hasta_paso']:.2f}"
                       f"\nACEPTADOS {metrica['aceptadas_acumuladas']:,}/{muestra['step']:,}")
        poner(f"vina_pasos_{i}",
              f"VINA  |  REPLICA 1/{traza['replicas']}\n"
              f"PASO {muestra['step']:,}/{traza['pasos_replica']:,}"
              f"{lectura}{anterior}",
              ventana, "inferior_izquierda")
    for i, (pose, ventana) in enumerate(zip(poses, ventanas_poses(rangos, total)), 1):
        af = pose.get("afinidad")
        valor = f"{af:.2f} kcal/mol" if isinstance(af, (int, float)) else ""
        cuenta = pose.get("contactos", {})
        # SCI-A-031: son los contactos DIBUJADOS, recortados a MAX_POR_TIPO por clase,
        # no todos los medidos; el rótulo lo dice.
        lectura = (f"\nDIBUJADOS (MAX. {MAX_POR_TIPO} POR CLASE)"
                   f"\nPOLARES {cuenta.get('polares', 0)}  |  "
                   f"APOLARES {cuenta.get('hidrofobicos', 0)}"
                   if montado.extra.get("contactos_visibles", True) else "")
        rmsd = pose.get("rmsd_vina_inferior_a")
        if i > 1 and isinstance(rmsd, (int, float)):
            lectura += f"\nRMSD VS POSE 1: {rmsd:.2f} A\n(COTA INFERIOR)"
        poner(f"vina_pose_{i}",
              f"VINA  |  POSE {i}/{total}\n{valor}{lectura}", ventana)
    if "salida" in rangos:
        poner("vina_resultado", f"VINA  |  {total} POSES\nMEJOR {energia}",
              rangos["salida"])
        if traza.get("pasos_totales"):
            poner("vina_total", f"BUSQUEDA INTERNA\n{traza['pasos_totales']:,} PASOS / {traza['replicas']} REPLICAS",
                  rangos["salida"], "inferior_izquierda")
    return out


def animar_sujeto(rangos, fps, montado, frames):
    """Enseña el ligando y cada pose real sin inventar una trayectoria."""
    import bpy
    from nucleo.fundido import curva
    from nucleo.horneado import fundir, hornear, visible_en
    poses = (montado.extra or {}).get("poses") or []
    ventanas = ventanas_poses(rangos, len(poses))
    busqueda = rangos.get("busqueda")
    esfera = (montado.extra or {}).get("esfera")
    if esfera and "salida" in rangos:
        a = rangos["salida"][0]
        fundir(esfera["material"], frames,
               curva([(a, a + max(5, int(0.9 * fps)), 0, 1)], frames))
        visible_en(esfera["objeto"], frames, a, frames[-1])
    for i, pose in enumerate(poses):
        obj = bpy.data.objects.get(pose["nombre"])
        if obj is None:
            continue
        ventana = ventanas[i] if i < len(ventanas) else None
        oculto = []
        for f in frames:
            en_pose = ventana is not None and ventana[0] <= f <= ventana[1]
            mejor = i == 0 and (busqueda is None or
                               f < busqueda[0] or f > rangos["convergencia"][1])
            oculto.append(0.0 if en_pose or mejor else 1.0)
        hornear(obj, "hide_render", -1, frames, oculto, "CONSTANT")
        hornear(obj, "hide_viewport", -1, frames, oculto, "CONSTANT")
        for nombre in montado.extra.get("contactos_por_pose", {}).get(
                pose.get("rank"), []):
            linea = bpy.data.objects.get(nombre)
            if linea is not None:
                hornear(linea, "hide_render", -1, frames, oculto, "CONSTANT")
                hornear(linea, "hide_viewport", -1, frames, oculto, "CONSTANT")
    instantaneas = (montado.extra or {}).get("instantaneas", [])
    for muestra, ventana in zip(instantaneas,
                               ventanas_instantaneas(rangos, len(instantaneas))):
        obj = bpy.data.objects.get(muestra["nombre"])
        if obj is not None:
            visible_en(obj, frames, *ventana)
        fantasma = bpy.data.objects.get(muestra.get("fantasma") or "")
        if fantasma is not None:
            visible_en(fantasma, frames, *ventana)
