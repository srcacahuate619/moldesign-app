"""Curvas de aparición: el valor 0..1 de un fundido en cada fotograma.

Sustituye a `horneado.curva`, que en el PRIMER fotograma de un fundido de entrada
valía 1 en vez de 0: el título y cada etiqueta salían enteros un fotograma, al
siguiente desaparecían y entonces empezaba el fundido (un destello visible en el
vídeo de Resultado de 4FK3, fotograma 11). `horneado.curva` no se corrige allí a
propósito: `nucleo/horneado.py` entra en la huella del cierre de marca y tocarlo
obligaría a volver a rendir el cierre en cada equipo.

Sin bpy: se prueba fuera de Blender.
"""
from __future__ import annotations


def _ss(x: float) -> float:
    return x * x * (3 - 2 * x)


def curva(tramos, frames) -> list[float]:
    """Valor por fotograma desde tramos (f_ini, f_fin, v_ini, v_fin), en orden.

    Antes del primer tramo, 0. En cada tramo, de `v_ini` a `v_fin` con smoothstep
    (en `f_ini` vale exactamente `v_ini`); después, `v_fin` hasta el tramo siguiente.
    """
    vals = []
    for f in frames:
        v = 0.0 if f < tramos[0][0] else float(tramos[0][2])
        for (fa, fb, va, vb) in tramos:
            if f >= fb:
                v = float(vb)
            elif f > fa:
                v = va + (vb - va) * _ss((f - fa) / (fb - fa))
            elif f == fa:
                v = float(va)
        vals.append(v)
    return vals
