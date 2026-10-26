"""Cuanto hay que alejarse para que algo quepa. CONSTANTE.

No sabe que esta encuadrando. Recibe puntos y devuelve distancias.
"""
from __future__ import annotations

import math

from mathutils import Vector

SENSOR = 36.0    # mm, sensor completo


def centro_recortado(puntos, recorte: float = 0.97):
    """Centro y nucleo compacto, descartando la cola dispersa.

    Medido en el caso 001: descartar el 3% de vertices mas lejanos baja la
    distancia necesaria de 13.95 a 10.79 unidades. Una cola desordenada no
    merece encoger la proteina entera en pantalla.
    """
    c0 = sum(puntos, Vector()) / len(puntos)
    orden = sorted(puntos, key=lambda p: (p - c0).length)
    nucleo = orden[:max(3, int(len(orden) * recorte))]
    return sum(nucleo, Vector()) / len(nucleo), nucleo


def distancia(puntos, centro, lente: float, aspecto: float,
              elevacion_deg: float, azimuts, margen: float = 1.08) -> float:
    """Distancia minima que encuadra `puntos` desde CUALQUIERA de esos azimuts.

    Se evalua en varios porque la silueta cambia al orbitar: basta un angulo
    mal medido para que la proteina se salga por un lado a mitad de la vuelta.
    """
    th = math.tan(math.atan(SENSOR / 2 / lente))
    tv = th / aspecto
    e = math.radians(elevacion_deg)
    peor = 0.0
    for az in azimuts:
        a = math.radians(az)
        fwd = -Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
        rg = fwd.cross(Vector((0, 0, 1))).normalized()
        uv = rg.cross(fwd).normalized()
        for p in puntos:
            d = p - centro
            need = max(abs(d.dot(rg)) / th, abs(d.dot(uv)) / tv) + d.dot(fwd)
            peor = max(peor, need)
    return peor * margen


def distancia_visible(puntos, centro, lente: float, aspecto: float,
                      elevacion_deg: float, azimuts, margen: float = 1.0,
                      cerca: float = 0.25) -> float:
    """Distancia a la que TODOS los puntos caben en el cuadro, medida bien.

    `distancia` suma la profundidad de cada punto al pivote. Para lo que queda
    DETRÁS del pivote sobra (más lejos el cuadro es más ancho); para lo que queda
    DELANTE, entre la cámara y el pivote, falta: el cuadro es más estrecho allí y
    hay que alejarse más, no menos. Con un sujeto delante del pivote —un ligando
    entre la cámara y el centro de la caja— el plano salía recortado: el vídeo de
    Búsqueda de 1J38 mostraba el ligando entero fuera de cuadro.

    Aquí la profundidad se RESTA: un punto a lateral `x` y profundidad `z` (>0 si
    está más lejos que el pivote) cabe si `D >= x / tan(fov/2) - z`. `cerca` es la
    holgura mínima entre la cámara y el punto más próximo, para que nada quede
    pegado a la lente. `margen` multiplica el resultado: 1.25 deja un 20 % de aire.
    """
    th = math.tan(math.atan(SENSOR / 2 / lente))
    tv = th / aspecto
    e = math.radians(elevacion_deg)
    peor = 0.0
    for az in azimuts:
        a = math.radians(az)
        fwd = -Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
        rg = fwd.cross(Vector((0, 0, 1))).normalized()
        uv = rg.cross(fwd).normalized()
        for p in puntos:
            d = p - centro
            z = d.dot(fwd)
            lateral = max(abs(d.dot(rg)) / th, abs(d.dot(uv)) / tv)
            peor = max(peor, lateral - z, cerca - z)
    return peor * margen


#: Aire mínimo (×distancia) que se exige a un plano de primer plano con la profundidad bien medida.
AIRE_MINIMO = 1.15


def distancia_primer_plano(puntos, centro, lente: float, aspecto: float,
                           elevacion_deg: float, azimuts, margen: float = 1.75) -> float:
    """La distancia de primer plano de siempre, sin bajar de la que cabe de verdad.

    `distancia` con su margen amplio basta cuando el sujeto está repartido
    alrededor del pivote (los guiones de ligando cocristalizado), y por eso las
    escenas existentes se calibraron con ella. Pero subestima cuando el sujeto
    queda ENTRE la cámara y el pivote: ahí `distancia_visible` pide más. Se toma
    el mayor de los dos, así que un plano que ya cabía NO cambia, y uno que
    recortaba al sujeto se abre lo justo (`AIRE_MINIMO`).
    """
    return max(distancia(puntos, centro, lente, aspecto, elevacion_deg, azimuts, margen),
               distancia_visible(puntos, centro, lente, aspecto, elevacion_deg, azimuts,
                                 AIRE_MINIMO))


def posicion(centro: Vector, azimut_deg: float, elevacion_deg: float,
             dist: float) -> Vector:
    a, e = math.radians(azimut_deg), math.radians(elevacion_deg)
    return centro + Vector((math.cos(e) * math.cos(a),
                            math.cos(e) * math.sin(a),
                            math.sin(e))) * dist


def tope_de_gradiente(distancias, factor_objetivo: float, desde: float = 0.4):
    """`From Max` tal que la MEDIANA de lo visible caiga en ese punto.

    El gradiente de color del carton va por distancia al sitio activo. Usar un
    percentil como tope manda la mitad de la geometria al extremo oscuro y la
    cinta sale negra; lo que importa es donde queda el grueso dentro de la
    rampa, no donde acaba. Depende de lo cerrado que sea el bolsillo, asi que
    no se puede derivar de la distancia de camara: hay que medirlo.
    """
    if len(distancias) < 9:
        return None
    med = sorted(distancias)[len(distancias) // 2]
    return desde + max(med - desde, 0.05) / factor_objetivo
