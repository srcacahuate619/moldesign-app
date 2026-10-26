"""Recorrido estructural sin ligando ni resultados de docking."""
from variables.sujeto import Montado

ID = "receptor_solo"
DESCRIPCION = "Receptor preparado y caja registrada, sin afirmar una evaluación."


def disponible(_paq):
    return True, "receptor preparado disponible; no se dibujan poses ni contactos"


def cargar(_paq, _ctx=None):
    return Montado(notas=["Recorrido estructural. No representa una evaluación ni actividad."])
