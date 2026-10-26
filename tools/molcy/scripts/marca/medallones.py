"""Mide los medallones hexagonales del emblema: centro, radio y giro exactos.

Sin bpy ni PIL: solo numpy, para usarlo desde Blender y desde las pruebas.

Por que medir y no poner los numeros a ojo: en el cierre, el medallon 3D que
vuela a su sitio SUSTITUYE al del logo (se recorta un hueco en el relieve). El
hueco y el medallon 3D salen de estas mismas medidas, asi que encajan por
construccion; con numeros a ojo, cualquier pixel de error dejaba dos hexagonos
superpuestos.

El marco del medallon es una linea brillante con oscuridad a ambos lados (la
placa por dentro, el fondo por fuera). Se busca el hexagono cuyo perimetro es
mas brillante que dos hexagonos paralelos, uno un poco mas adentro y otro un poco
mas afuera, muestreando solo el centro de cada lado: en los vertices llegan las
lineas de la red y ahi fuera tambien hay brillo.
"""
from __future__ import annotations

import numpy as np

#: Hexagono con un vertice arriba (como en el logo): vertices a 90 + 60 k grados.
BASE_GRADOS = 90.0


def vertices(cx: float, cy: float, r: float, giro: float = 0.0) -> np.ndarray:
    """Seis vertices en px de imagen (y hacia abajo). `giro` en grados,
    antihorario tal como se ve la imagen."""
    a = np.radians(BASE_GRADOS + giro + 60.0 * np.arange(6))
    return np.stack([cx + r * np.cos(a), cy - r * np.sin(a)], axis=-1)


def _perimetro(cx, cy, r, giro, t: np.ndarray) -> np.ndarray:
    """Puntos del perimetro: para cada lado, en las fracciones `t` (0-1)."""
    v = vertices(cx, cy, r, giro)
    w = np.roll(v, -1, axis=0)
    return (v[:, None, :] + (w - v)[:, None, :] * t[None, :, None]).reshape(-1, 2)


def _muestra(img: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Interpolacion bilineal; fuera de la imagen vale 0."""
    h, w = img.shape
    x, y = pts[..., 0], pts[..., 1]
    x0 = np.clip(np.floor(x).astype(int), 0, w - 2)
    y0 = np.clip(np.floor(y).astype(int), 0, h - 2)
    fx = np.clip(x - x0, 0, 1)
    fy = np.clip(y - y0, 0, 1)
    v = (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy)
         + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)
    fuera = (x < 0) | (y < 0) | (x > w - 1) | (y > h - 1)
    return np.where(fuera, 0.0, v)


def _perimetros(c: np.ndarray, escala: float, t: np.ndarray) -> np.ndarray:
    """Perimetros de muchos candidatos a la vez. `c` es (N, 4): cx, cy, r, giro."""
    a = np.radians(BASE_GRADOS + c[:, 3:4] + 60.0 * np.arange(6))          # (N, 6)
    r = c[:, 2:3] * escala
    v = np.stack([c[:, 0:1] + r * np.cos(a), c[:, 1:2] - r * np.sin(a)], -1)  # (N, 6, 2)
    w = np.roll(v, -1, axis=1)
    p = v[:, :, None, :] + (w - v)[:, :, None, :] * t[None, None, :, None]    # (N, 6, T, 2)
    return p.reshape(len(c), -1, 2)


def puntuaciones(brillo: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Contraste del marco para cada candidato (N, 4)."""
    t_linea = np.linspace(0.12, 0.88, 14)
    t_lado = np.linspace(0.3, 0.7, 6)              # solo el centro del lado
    linea = _muestra(brillo, _perimetros(c, 1.0, t_linea)).mean(axis=1)
    dentro = _muestra(brillo, _perimetros(c, 0.84, t_lado)).mean(axis=1)
    fuera = _muestra(brillo, _perimetros(c, 1.16, t_lado)).mean(axis=1)
    return linea - 0.5 * (dentro + fuera)


def puntuacion(brillo: np.ndarray, cx, cy, r, giro) -> float:
    return float(puntuaciones(brillo, np.array([[cx, cy, r, giro]], dtype=np.float64))[0])


def _rejilla(*ejes) -> np.ndarray:
    return np.stack(np.meshgrid(*ejes, indexing="ij"), -1).reshape(-1, len(ejes))


def ajustar(brillo: np.ndarray, centro: tuple[float, float], radio: float,
            holgura: float = 14.0) -> dict:
    """El hexagono que mejor explica el marco alrededor de `centro`.

    Busqueda en rejilla gruesa y luego fina, todos los candidatos de una vez.
    `brillo` es la imagen en gris 0-1 (el maximo de RGB), filas de arriba abajo.
    """
    brillo = np.asarray(brillo, dtype=np.float32)
    c = _rejilla(np.arange(centro[0] - holgura, centro[0] + holgura + 1, 2),
                 np.arange(centro[1] - holgura, centro[1] + holgura + 1, 2),
                 np.arange(radio * 0.8, radio * 1.2 + 1, 2),
                 np.arange(-8, 9, 2))
    cx0, cy0, r0, g0 = c[int(np.argmax(puntuaciones(brillo, c)))]
    f = np.arange(-2, 2.01, 0.5)
    c = _rejilla(cx0 + f, cy0 + f, r0 + f, g0 + f)
    s = puntuaciones(brillo, c)
    cx, cy, r, g = c[int(np.argmax(s))]
    return {"cx": float(cx), "cy": float(cy), "r": float(r), "giro": float(g),
            "contraste": round(float(s.max()), 4)}


def dentro(ancho: int, alto: int, m: dict, margen: float = 0.0) -> np.ndarray:
    """Mascara 0/1 de los pixeles dentro del hexagono (con `margen` px mas)."""
    yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
    v = vertices(m["cx"], m["cy"], m["r"] + margen, m["giro"])
    res = np.ones((alto, ancho), dtype=bool)
    for k in range(6):
        (x1, y1), (x2, y2) = v[k], v[(k + 1) % 6]
        # los vertices giran en sentido antihorario en pantalla (horario en
        # coordenadas de imagen): lo de dentro queda siempre del mismo lado
        cruz = (x2 - x1) * (yy - y1) - (y2 - y1) * (xx - x1)
        res &= cruz <= 0
    return res
