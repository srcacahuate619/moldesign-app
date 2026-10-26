"""FORMATO: la previsualizacion al pasar el cursor sobre un receptor.

Manda el coste y el bucle, no la narrativa. Sin texto: a este tamano no se lee,
y una etiqueta ilegible es ruido. Sin pausas, porque sin etiquetas una pausa es
tiempo muerto: el reparto las descarta solo.

A 90 fotogramas y 720p son ~2 min por receptor, o unas 13 h para los 380,
frente a las 174 h que costaria el formato `biblioteca`.

La escena es un bucle (la orbita cierra sobre si misma), pero EL VIDEO no: como todo video de MolDesign termina con el cierre de la marca
(3,6 s). Eso no es opcional ni hay mando que lo quite.
"""
from variables.formato import Formato

FORMATO = Formato(
    nombre="previsualizacion",
    descripcion="Escena corta 1:1 sin texto (en bucle) mas el cierre de marca. ~2 min.",
    ancho=720, alto=720, fps=30, segundos=3.0,
    muestras=48, escala_render=100,
    bucle=True, etiquetas_3d=False, rotulos_pantalla=False,
    desenfoque_movimiento=True, profundidad_de_campo=False,
    sello_procedencia=False, escala_texto=1.0, cierre_s=3.6,
    # Solo la orbita. Un push-in rompe el bucle: el video acabaria en primer
    # plano y el corte de vuelta al fotograma 1 seria un salto.
    papeles=("establecer",),
)
