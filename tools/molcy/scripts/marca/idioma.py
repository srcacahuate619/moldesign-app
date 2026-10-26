"""Identidad del cierre por idioma; una opción desconocida conserva el español."""
import os

LEMAS = {"es": "EVIDENCIA ESTRUCTURAL REPRODUCIBLE", "en": "REPRODUCIBLE STRUCTURAL EVIDENCE"}


def idioma_del_cierre() -> str:
    return "en" if os.environ.get("MOLCY_IDIOMA") == "en" else "es"


def lema_del_idioma() -> str:
    return LEMAS[idioma_del_cierre()]
