"""VARIABLE: cuándo se detiene el vídeo para leer.

Una etiqueta anclada en 3D sólo se lee si la imagen está quieta. En vez de
alargar el guion (más fotogramas que rendir) el vídeo se CONGELA: el mismo PNG
—escena y capa de rótulos— se repite durante la pausa. Rendir otra vez una
imagen idéntica es tiempo perdido; repetirla al montar no cuesta nada.

La pausa existe sólo en el MONTAJE: `montar()` devuelve `fuentes`, el fotograma
fuente (el del `.blend`) que se ve en cada fotograma de salida, y `codificar.py`
lo sigue al pie de la letra. El `.blend`, la cámara y los keyframes no cambian.

Dos clases de pausa:

- `lectura`: un grupo de etiquetas ya entró entero. Se repite ese fotograma.
- un tramo FIJO del guion (cámara quieta, nada que aparezca ni desaparezca) se
  rinde una vez y se acorta: `omitir_hasta` salta los fotogramas fuente que
  serían idénticos al congelado. Así una espera muerta deja de costar render.

Sin bpy: se prueba fuera de Blender (`pruebas/test_pausas.py`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: Lectura de un grupo de etiquetas en Resultado: dos segundos para la primera y
#: un poco más por cada una de las siguientes, con un tope de tres. Una sola
#: etiqueta no necesita tres segundos; seis interacciones de dos renglones, sí.
LECTURA_MIN_S, LECTURA_MAX_S, LECTURA_POR_ETIQUETA_S = 2.0, 3.0, 0.2


def segundos_de_lectura(n_etiquetas: int, minimo: float = LECTURA_MIN_S,
                        maximo: float = LECTURA_MAX_S,
                        por_etiqueta: float = LECTURA_POR_ETIQUETA_S) -> float:
    """Cuánto se congela la imagen para leer `n_etiquetas` a la vez."""
    return round(min(maximo, minimo + por_etiqueta * max(0, n_etiquetas - 1)), 3)


@dataclass(frozen=True)
class Congelado:
    """Un fotograma fuente que se repite durante `segundos` en la salida."""
    fuente: int
    segundos: float
    tipo: str = "lectura"
    etiquetas: tuple = field(default_factory=tuple)
    #: Último fotograma fuente que se salta después del congelado (los que van de
    #: `fuente + 1` a éste son idénticos a `fuente`: no se rinden ni se ven).
    omitir_hasta: int | None = None


def montar(n: int, fps: int, congelados=()) -> dict:
    """Mapa fotograma de salida → fotograma fuente, con el índice de pausas.

    Los fotogramas fuente se recorren en orden y ninguno se reordena: una pausa
    sólo REPITE el fotograma en el que cae, y `omitir_hasta` sólo SALTA hacia
    delante. Todo rango es inclusivo y empieza en 1, como en Blender.
    """
    if n < 1 or fps < 1:
        raise ValueError("montar: hacen falta fotogramas y fps positivos")
    por_fuente: dict[int, Congelado] = {}
    for c in congelados:
        if not 1 <= c.fuente <= n:
            raise ValueError(f"pausa fuera del guion: fotograma {c.fuente} de {n}")
        if c.segundos <= 0:
            raise ValueError(f"pausa sin duración en el fotograma {c.fuente}")
        if c.omitir_hasta is not None and not c.fuente <= c.omitir_hasta <= n:
            raise ValueError(f"omitir_hasta {c.omitir_hasta} no sigue a {c.fuente}")
        if c.fuente in por_fuente:
            raise ValueError(f"dos pausas en el mismo fotograma {c.fuente}")
        por_fuente[c.fuente] = c
    ordenados = sorted(por_fuente.values(), key=lambda c: c.fuente)
    for a, b in zip(ordenados, ordenados[1:]):
        if a.omitir_hasta is not None and a.omitir_hasta >= b.fuente:
            raise ValueError(f"la pausa de {a.fuente} salta por encima de la de {b.fuente}")

    fuentes: list[int] = []
    pausas: list[dict] = []
    omitidos = 0
    f = 1
    while f <= n:
        c = por_fuente.get(f)
        if c is None:
            fuentes.append(f)
            f += 1
            continue
        inicio = len(fuentes) + 1
        fuentes.extend([f] * max(1, int(round(c.segundos * fps))))
        pausas.append({"fuente": f, "salida": [inicio, len(fuentes)],
                       "segundos": round((len(fuentes) - inicio + 1) / fps, 3),
                       "tipo": c.tipo, "etiquetas": list(c.etiquetas)})
        if c.omitir_hasta is not None and c.omitir_hasta > f:
            omitidos += c.omitir_hasta - f
            pausas[-1]["omitidos"] = [f + 1, c.omitir_hasta]
            f = c.omitir_hasta + 1
        else:
            f += 1
    unicos = len(set(fuentes))
    return {"fuentes": fuentes, "pausas": pausas,
            "fotogramas_fuente": n, "fotogramas_salida": len(fuentes),
            "fotogramas_render_unicos": unicos, "fotogramas_omitidos": omitidos,
            "fotogramas_repetidos": len(fuentes) - unicos}


def indice(montaje: dict, fps: int) -> list[dict]:
    """Las pausas en segundos del vídeo final (antes del cierre), para el acta."""
    return [{"inicio_s": round((p["salida"][0] - 1) / fps, 3),
             "fin_s": round(p["salida"][1] / fps, 3),
             "tipo": p["tipo"], "etiquetas": len(p["etiquetas"])}
            for p in montaje["pausas"]]


def representantes(frames, firma, vecinos: bool = True, propios=()) -> dict:
    """fotograma -> el fotograma ya rendido que se verá exactamente igual.

    Todo lo que se mueve en estas escenas está horneado por fotograma, así que dos
    fotogramas con la misma `firma` (los valores de todas sus curvas) dan la misma
    imagen: EEVEE es determinista. Con desenfoque de movimiento (`vecinos`) el
    render de `f` depende también de `f-1` y `f+1`, así que sólo se reutiliza un
    fotograma QUIETO (los tres iguales). `propios` se rinden siempre (los que el
    montaje congela, que van sin desenfoque). Devuelve sólo los que cambian.
    """
    vistos: dict = {}
    out: dict = {}
    for f in sorted(frames):
        if f in propios:
            continue
        clave = firma(f)
        if vecinos and not (firma(f - 1) == clave == firma(f + 1)):
            continue
        if clave in vistos:
            out[f] = vistos[clave]
        else:
            vistos[clave] = f
    return out

