"""Dónde va cada etiqueta en pantalla: texto y guía con restricciones DURAS.

El colocador anterior sumaba penalizaciones (solape, cruce, cercanía…) y se
quedaba con el mínimo: cuando no cabía todo, aceptaba un solape a cambio de
bajar el coste, y en vertical las etiquetas acababan unas encima de otras y
sobre el rótulo del sujeto. Aquí un solape NUNCA es una solución:

- ninguna caja de texto se acerca a otra a menos de `separacion`;
- ninguna guía cruza otra guía, ni pasa por encima de un texto ajeno;
- ninguna caja invade una zona reservada (texto de pantalla, el propio ligando);
- ninguna guía atraviesa un texto de pantalla (`zonas_texto`);
- ningún texto tapa una línea de interacción (`lineas`), y con `cruzar_lineas`
  falso tampoco una guía cruza la línea de OTRA interacción: el rótulo está
  para explicar la línea punteada, no para taparla.

Si no hay solución, `disponer` lo dice (`SinEspacio`) y quien llama decide:
achicar o rotular menos, y dejarlo en el acta. No hay plan B silencioso.

Todo en NDC (-1..1 en los dos ejes, como `world_to_camera_view * 2 - 1`); las
cajas son las MEDIDAS de los glifos, no estimaciones por longitud de texto. Sin
bpy: se prueba fuera de Blender (`pruebas/test_disposicion.py`).
"""
from __future__ import annotations

import math


class SinEspacio(ValueError):
    """No hay sitio para todas las etiquetas sin solaparlas."""


def separacion(a, b) -> float:
    """Distancia de borde a borde entre dos cajas (0 si se tocan o se invaden)."""
    return math.hypot(max(a[0] - b[2], b[0] - a[2], 0.0),
                      max(a[1] - b[3], b[1] - a[3], 0.0))


def cruza(a, b, c, d) -> bool:
    """¿Se tocan los segmentos ab y cd? Cruce, tramo superpuesto o contacto en T."""
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def contiene(p, q, r):
        return (min(p[0], q[0]) - 1e-9 <= r[0] <= max(p[0], q[0]) + 1e-9
                and min(p[1], q[1]) - 1e-9 <= r[1] <= max(p[1], q[1]) + 1e-9)

    ac, ad, ca, cb = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    if ac * ad < -1e-12 and ca * cb < -1e-12:
        return True
    return ((abs(ac) < 1e-9 and contiene(a, b, c)) or (abs(ad) < 1e-9 and contiene(a, b, d))
            or (abs(ca) < 1e-9 and contiene(c, d, a)) or (abs(cb) < 1e-9 and contiene(c, d, b)))


def toca_caja(a, b, caja, margen: float = 0.018) -> bool:
    """¿Pasa el segmento ab por la caja (ampliada en `margen`)? Recorte de Liang–Barsky."""
    x0, y0, x1, y1 = caja[0] - margen, caja[1] - margen, caja[2] + margen, caja[3] + margen
    dx, dy = b[0] - a[0], b[1] - a[1]
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return False
        elif p < 0:
            lo = max(lo, q / p)
        else:
            hi = min(hi, q / p)
    return lo <= hi


#: Aire entre la caja del texto y la punta de su guía, y tramo inicial de la guía
#: que se deja libre junto al ancla (para no tapar el átomo o la línea que señala).
AIRE_PUNTA, ARRANQUE = 0.018, 0.06


def candidato(ancla, centro, ancho, alto):
    """(caja, guía) de una etiqueta centrada en `centro`; None si tapa su propia ancla."""
    x, y = centro
    caja = (x - ancho / 2, y - alto / 2, x + ancho / 2, y + alto / 2)
    dx, dy = ancla[0] - x, ancla[1] - y
    t = min((ancho / 2 + AIRE_PUNTA) / max(abs(dx), 1e-9),
            (alto / 2 + AIRE_PUNTA) / max(abs(dy), 1e-9))
    if t >= 1.0:
        return None          # el ancla queda debajo del texto: la guía no tendría por dónde ir
    punta = (x + dx * t, y + dy * t)
    inicio = (ancla[0] + (punta[0] - ancla[0]) * ARRANQUE,
              ancla[1] + (punta[1] - ancla[1]) * ARRANQUE)
    return caja, (inicio, punta)


#: Coste de una guía que pasa por encima de una zona reservada (el ligando): lo
#: que costaría alejar el texto otro medio cuadro.
PENALIZA_CRUCE = 0.5

#: Anillos de búsqueda alrededor del ancla (NDC) y direcciones por anillo.
RADIOS = (0.22, 0.30, 0.40, 0.52, 0.66, 0.82, 1.0, 1.2, 1.45, 1.75)
DIRECCIONES = 24


def disponer(etiquetas, reservados=(), *, zonas_texto=(), lineas=(),
             cruzar_lineas: bool = False, margen: float = 0.05,
             separacion_min: float = 0.035, haz: int = 24) -> dict:
    """id → (caja, guía) para cada `(id, ancla, ancho, alto)`; `SinEspacio` si no caben.

    Determinista. Las anclas más alejadas del centro del grupo se colocan antes
    (son las que menos sitio tienen para elegir); un pequeño haz de soluciones
    permite cambiar la elección de las primeras cuando impiden colocar las
    siguientes, cosa que un colocador voraz no puede hacer. Entre las válidas
    gana la más cercana a su ancla y más apartada del centro del grupo: la guía
    corta se lee mejor y el sitio activo queda despejado.

    `lineas` son `(id, (p0, p1))`: el segmento en pantalla de cada línea de
    interacción y el id del rótulo que la explica (su guía sí puede tocarla).
    """
    if not etiquetas:
        return {}
    cx = sum(a[0] for _, a, _, _ in etiquetas) / len(etiquetas)
    cy = sum(a[1] for _, a, _, _ in etiquetas) / len(etiquetas)
    orden = sorted(etiquetas, key=lambda e: (-math.hypot(e[1][0] - cx, e[1][1] - cy), e[0]))
    lim = 1.0 - margen
    opciones = {}
    for ident, ancla, ancho, alto in orden:
        if ancho >= 2 * lim or alto >= 2 * lim:
            raise SinEspacio(f"la etiqueta {ident} no cabe en el cuadro")
        ang0 = math.atan2(ancla[1] - cy, ancla[0] - cx)
        centros = []
        for radio in RADIOS:
            for paso in range(DIRECCIONES):
                th = ang0 + paso * math.tau / DIRECCIONES
                centros.append((ancla[0] + radio * math.cos(th), ancla[1] + radio * math.sin(th)))
        # Carriles junto a los bordes: con anclas en el centro de un cuadro
        # angosto, el único sitio libre suele estar pegado al margen.
        for k in range(17):
            u = -lim + k * 2 * lim / 16
            centros += [(-lim + ancho / 2, u), (lim - ancho / 2, u),
                        (u, -lim + alto / 2), (u, lim - alto / 2)]
        validas = []
        for centro in centros:
            par = candidato(ancla, centro, ancho, alto)
            if par is None:
                continue
            caja, guia = par
            if caja[0] < -lim or caja[1] < -lim or caja[2] > lim or caja[3] > lim:
                continue
            if any(separacion(caja, r) < separacion_min for r in reservados):
                continue
            # Las zonas reservadas pueden contener el propio ligando, y la guía
            # tiene que salir de él: sólo el TEXTO de pantalla le cierra el paso.
            if any(toca_caja(*guia, z) for z in zonas_texto):
                continue
            if any(toca_caja(*seg, caja, margen=0.01) for _id, seg in lineas):
                continue
            if not cruzar_lineas and any(cruza(*guia, *seg) for otro, seg in lineas
                                         if otro != ident):
                continue
            cerca = math.hypot(centro[0] - ancla[0], centro[1] - ancla[1])
            fuera = math.hypot(centro[0] - cx, centro[1] - cy)
            # Una guía que atraviesa el ligando (una zona reservada) se lee como
            # otra línea de la molécula: se permite, pero sólo si no hay otra.
            cruza_sujeto = sum(toca_caja(*guia, r, margen=0.0) for r in reservados)
            validas.append((round(cerca - 0.12 * fuera + PENALIZA_CRUCE * cruza_sujeto, 9),
                            caja, guia))
        validas.sort(key=lambda v: v[0])
        opciones[ident] = validas
    estados = [(0.0, {})]
    for ident, _ancla, _ancho, _alto in orden:
        siguientes = []
        for coste, puestas in estados:
            aceptadas = 0
            for nota, caja, guia in opciones[ident]:
                if any(separacion(caja, c) < separacion_min or cruza(*guia, *g)
                       or toca_caja(*guia, c) or toca_caja(*g, caja)
                       for c, g in puestas.values()):
                    continue
                siguientes.append((coste + nota, {**puestas, ident: (caja, guia)}))
                aceptadas += 1
                if aceptadas >= 8:
                    break
        if not siguientes:
            raise SinEspacio(f"no hay sitio sin solapes para {len(etiquetas)} etiquetas "
                             f"(falla {ident})")
        siguientes.sort(key=lambda s: s[0])
        estados = siguientes[:haz]
    return estados[0][1]
