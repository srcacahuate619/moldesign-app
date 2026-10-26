"""Desde donde se ve lo que hay que ver. CONSTANTE.

Elegir el angulo a ojo falla: en el caso 001 la direccion que parecia natural
dejaba el ligando con visibilidad minima 0.036 (desaparecia media vuelta),
frente a 0.566 de la elegida por medicion. Merece la pena medirlo siempre.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

from .encuadre import posicion
from .horneado import ss

#: El rayo se detiene a esta fraccion del camino: interesa si algo se interpone,
#: no si el propio objetivo tiene volumen. Sin el recorte, las varillas del
#: ligando bloquean los rayos hacia sus propios atomos.
MARGEN_RAYO = 0.86

#: Cuanto puede bajar la cobertura respecto a la mejor pose antes de que deje de
#: considerarse empate. 0.5% absorbe el ruido del trazado de rayos sin permitir
#: que la composicion se coma visibilidad de verdad.
TOLERANCIA = 0.005


def margen_para(dianas) -> float:
    """Cuanto se recorta el rayo, segun el tipo de diana.

    Una NUBE de atomos —el ligando— necesita recorte: sus propias varillas
    bloquean los rayos hacia sus atomos de atras y sin recorte la medida se
    desploma (medido: 1.0 -> 0.233 al anadirle enlaces). Un PUNTO —el centroide
    de una cadena lateral, el punto medio de un contacto— no tiene volumen
    propio que estorbe, asi que recortar solo ciega el tramo final del camino.

    Ese fallo costo un plano: en 3ERT las lineas de contacto salieron tapadas
    por las helices aunque la medida daba cobertura 1.0, porque el occluder
    estaba dentro del 14% que el margen no miraba.
    """
    return MARGEN_RAYO if len(dianas) > 8 else 0.97


def visibilidad(dianas, desde: Vector, dg=None, margen: float | None = None) -> float:
    """Fraccion de dianas que se ven sin nada por delante."""
    sc = bpy.context.scene
    dg = dg or bpy.context.evaluated_depsgraph_get()
    m = margen if margen is not None else margen_para(dianas)
    libres = 0
    for p in dianas:
        d = p - desde
        L = d.length
        if L < 1e-6:
            continue
        if not sc.ray_cast(dg, desde, d / L, distance=L * m)[0]:
            libres += 1
    return libres / max(len(dianas), 1)


def mejor_azimut(dianas, pivote: Vector, elevacion: float, dist: float,
                 paso: int = 12) -> tuple[float, float]:
    """Azimut desde el que mejor se ve el sitio. Ahi aterriza la aproximacion."""
    dg = bpy.context.evaluated_depsgraph_get()
    mejor = (0.0, -1.0)
    for k in range(0, 360, paso):
        v = visibilidad(dianas, posicion(pivote, k, elevacion, dist), dg)
        if v > mejor[1]:
            mejor = (float(k), v)
    return mejor


#: Mínimo de visibilidad por debajo del cual un arco deja el sujeto tapado: el
#: mismo umbral con el que la puerta de calidad (`salida/control.py`) avisa.
UMBRAL_ARCO = 0.40


def _candidatos(cortos: bool = False):
    giros = (60.0, -60.0, 45.0, -45.0, 30.0, -30.0) if cortos \
        else (120.0, -120.0, 150.0, -150.0, 90.0, -90.0)
    return [{"span": s, "el_fin": e, "rampa": r, "hump": h}
            for s in giros
            for e in (22.0, 0.0, -18.0)
            for r, h in ((0.45, 10.0), (0.30, 0.0))]


def recorrido(c, pivote, az0, el0, d0, muestras=21):
    pts = []
    for i in range(muestras):
        w = i / (muestras - 1)
        s = ss(w)
        az = az0 + c["span"] * s
        el = el0 + (c["el_fin"] - el0) * ss(min(w / c["rampa"], 1.0)) \
            + c["hump"] * math.sin(math.pi * w)
        D = d0 * (1.0 + 0.07 * s) + d0 * 0.12 * math.sin(math.pi * w)
        pts.append(posicion(pivote, az, el, D))
    return pts


def mejor_arco(dianas, pivote: Vector, az0: float, el0: float, d0: float,
               candidatos=None, muestras: int = 21) -> dict:
    """Arco que menos ocluye. Puntua sobre todo por el PEOR momento.

    Un arco con buena media pero un instante tapado se nota mas que uno
    mediocre y parejo, asi que el minimo pesa 0.7 y la media 0.3.

    Los giros grandes (90°–150°) son los que dan más cine, y se prueban primero.
    Si NINGUNO esquiva el receptor (mínimo por debajo de `UMBRAL_ARCO`: en 4CA8
    el mejor dejaba el ligando al 9 % durante parte de la retirada, con una
    cinta oscura delante), se prueban también giros cortos (30°–60°), que se
    quedan dentro de la ventana despejada que midió la pose. Los arcos que ya
    eran buenos no cambian.
    """
    dg = bpy.context.evaluated_depsgraph_get()
    mejor = None

    def probar(lista):
        nonlocal mejor
        for c in lista:
            v = [visibilidad(dianas, p, dg)
                 for p in recorrido(c, pivote, az0, el0, d0, muestras)]
            puntuacion = min(v) * 0.7 + (sum(v) / len(v)) * 0.3
            if mejor is None or puntuacion > mejor["puntuacion"]:
                mejor = dict(c, puntuacion=round(puntuacion, 4),
                             minimo=round(min(v), 4),
                             media=round(sum(v) / len(v), 4))

    probar(candidatos or _candidatos())
    if not candidatos and mejor["minimo"] < UMBRAL_ARCO:
        probar(_candidatos(cortos=True))
    return mejor


def arco_cerrado(dianas, pivote: Vector, az0: float, el0: float, d0: float) -> dict:
    """Arco que VUELVE a su punto de partida, para formatos en bucle.

    Una previsualizacion al pasar el cursor tiene que empalmar consigo misma,
    asi que el recorrido no puede acabar en otro sitio: span 360 y elevacion
    de vuelta a la inicial.
    """
    c = {"span": 360.0, "el_fin": el0, "rampa": 0.5, "hump": 0.0}
    dg = bpy.context.evaluated_depsgraph_get()
    v = [visibilidad(dianas, p, dg) for p in recorrido(c, pivote, az0, el0, d0, 24)]
    return dict(c, puntuacion=round(min(v) * 0.7 + sum(v) / len(v) * 0.3, 4),
                minimo=round(min(v), 4), media=round(sum(v) / len(v), 4),
                cerrado=True)


# ── pose heroe: el angulo desde el que TODO se ve y se lee ───────────────
def _proyectar(p: Vector, pos: Vector, fwd: Vector, rg: Vector, uv: Vector,
               th: float, aspecto: float):
    """Coordenadas de cuadro normalizadas (-1..1). None si queda detras."""
    d = p - pos
    z = d.dot(fwd)
    if z <= 1e-6:
        return None
    return Vector((d.dot(rg) / (th * z), d.dot(uv) / (th * z / aspecto)))


def mejor_pose(grupos, pivote: Vector, dist: float, lente: float,
               aspecto: float, elevaciones=(-32, -24, -16, -8, 0, 8, 16, 24, 32),
               paso_az: int = 15, preferencia_el: float = -16.0,
               distancia_requerida=None) -> dict:
    """Busca azimut Y elevacion. Hasta ahora solo se buscaba el azimut.

    Tres cosas que la version anterior no hacia:

    1. **Barre la elevacion.** `EL_PRIMER_PLANO` era una constante heredada de
       la camara de EGFR (-22). Se optimizaba un angulo de dos: si el bolsillo
       abre hacia arriba, -22 puede ser el peor sitio posible.

    2. **Pondera por GRUPO, no por atomo.** Contar la fraccion de puntos visibles
       hace que una Arg (11 atomos pesados) pese cinco veces mas que una Ser (2),
       y que el ligando valga lo mismo que una cadena lateral cualquiera. El
       ligando es el protagonista y cada hotspot cuenta como uno.

    3. **Mide si se LEE, no solo si se ve.** Dos dianas pueden estar ambas sin
       ocluir y proyectarse una encima de la otra: visibles y aun asi ilegibles,
       con las etiquetas pisandose. Se premia que queden separadas en pantalla.

    Y acota la busqueda: optimizar a ciegas da cenitales que maximizan
    visibilidad y parecen un diagrama, no cine. La elevacion se limita y, a
    igualdad de puntuacion, gana la pose mas cercana al angulo cinematografico.

    `grupos`: [(nombre, peso, [puntos_mundo]), ...]
    """
    dg = bpy.context.evaluated_depsgraph_get()
    th = math.tan(math.atan(36.0 / 2 / lente))
    peso_total = sum(g[1] for g in grupos) or 1.0
    centros = [(n, w, sum(p, Vector()) / len(p)) for n, w, p in grupos if p]

    candidatas = []
    for el in elevaciones:
        for az in range(0, 360, paso_az):
            pos = posicion(pivote, az, el, dist)
            fwd = (pivote - pos).normalized()
            rg = fwd.cross(Vector((0, 0, 1)))
            if rg.length < 1e-6:
                continue
            rg.normalize()
            uv = rg.cross(fwd).normalized()

            desglose = {}
            cobertura = 0.0
            for nombre, peso, puntos in grupos:
                if not puntos:
                    continue
                v = visibilidad(puntos, pos, dg)
                desglose[nombre] = round(v, 3)
                cobertura += peso * v
            cobertura /= peso_total

            # separacion en pantalla entre los centros de cada grupo
            proy = [_proyectar(c, pos, fwd, rg, uv, th, aspecto)
                    for _, _, c in centros]
            proy = [p for p in proy if p is not None]
            if len(proy) > 1:
                pares = [(proy[i] - proy[j]).length
                         for i in range(len(proy)) for j in range(i + 1, len(proy))]
                separacion = min(1.0, (sum(pares) / len(pares)) / 0.9)
            else:
                separacion = 1.0

            cine = 1.0 - min(1.0, abs(el - preferencia_el) / 90.0)
            # Cuanto hay que alejarse desde aqui para que quepa todo. Una pose
            # que obliga a retroceder ensena lo mismo mas pequeno: en 3ERT la
            # ganadora pedia 6.03 frente a 4.37 de otra casi igual de visible,
            # y el plano perdia la mitad del tamano del ligando.
            d_req = distancia_requerida(az, el) if distancia_requerida else 1.0
            candidatas.append({"azimut": float(az), "elevacion": float(el),
                               "cobertura": cobertura, "separacion": separacion,
                               "cine": cine, "d_req": d_req,
                               "por_grupo": desglose})

    if not candidatas:
        return {"azimut": 0.0, "elevacion": preferencia_el, "score": 0.0,
                "cobertura": 0.0, "separacion": 0.0, "por_grupo": {}}

    # Lexicografico, no suma ponderada. Una suma deja que el optimizador cambie
    # visibilidad por composicion: medido en 1CX2, cedia un 0.4% de cobertura
    # para ganar un 25% de separacion. La cobertura es el requisito —que el
    # ligando y los hotspots SE VEAN— y la legibilidad el criterio de desempate.
    tope = max(c["cobertura"] for c in candidatas)
    empatadas = [c for c in candidatas if c["cobertura"] >= tope - TOLERANCIA]
    d_min = min(c["d_req"] for c in empatadas) or 1.0

    def desempate(c):
        cercania = d_min / max(c["d_req"], 1e-6)     # 1.0 = la mas cerrada
        return 0.45 * c["separacion"] + 0.35 * cercania + 0.20 * c["cine"]

    mejor = max(empatadas, key=desempate)
    return {"azimut": mejor["azimut"], "elevacion": mejor["elevacion"],
            "score": round(desempate(mejor), 4),
            "distancia_requerida": round(mejor["d_req"], 3),
            "cobertura": round(mejor["cobertura"], 4),
            "separacion": round(mejor["separacion"], 4),
            "cobertura_maxima": round(tope, 4),
            "poses_empatadas": len(empatadas),
            "por_grupo": mejor["por_grupo"]}


def mejor_elevacion_orbita(dianas, pivote: Vector, dist: float,
                           elevaciones=(0, 8, 16, 24, 32, -8, -16),
                           paso_az: int = 20) -> dict:
    """Elevacion que deja el MINIMO mas alto en una vuelta completa.

    Un formato en bucle recorre los 360 grados por obligacion, asi que el
    azimut no se puede elegir: se pasa por todos. Lo unico ajustable es la
    altura del recorrido, y no se estaba ajustando —la orbita iba clavada a
    EL_GENERAL=12. Medido en 1HSG: el minimo del recorrido cerrado salia
    0.3953, o sea que durante parte de la vuelta el sujeto quedaba tapado y la
    previsualizacion vendia mal un receptor con buen acceso al sitio.

    Se puntua por el MINIMO, no por la media: en un bucle que se repite, el
    peor instante se ve una y otra vez.
    """
    dg = bpy.context.evaluated_depsgraph_get()
    mejor = None
    for el in elevaciones:
        v = [visibilidad(dianas, posicion(pivote, az, el, dist), dg)
             for az in range(0, 360, paso_az)]
        cand = {"elevacion": float(el), "minimo": round(min(v), 4),
                "media": round(sum(v) / len(v), 4)}
        if mejor is None or cand["minimo"] > mejor["minimo"]:
            mejor = cand
    return mejor or {"elevacion": 12.0, "minimo": 0.0, "media": 0.0}
