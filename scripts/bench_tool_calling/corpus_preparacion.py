"""Corpus de `corpus.py` más cinco casos de la pestaña Preparación.

Escritos para esta prueba el 2026-10-10 a partir de lo que la pestaña enseña
(bloqueantes, advertencias, metales retirados, receptor listo o no). No son
tráfico real. Sirven para dos cosas: que el modelo elija `check_preparation`
cuando toca, y que añadir la herramienta 22 no estropee la elección de las 21.
"""
from corpus import CASOS as _BASE
from corpus import DESC_EN as _DESC_EN

CASOS = _BASE + [
    ("prep_bloqueado",
     "¿por qué está bloqueado el receptor 8HFI?",
     "why is receptor 8HFI blocked?",
     "check_preparation"),
    ("prep_listo",
     "¿está listo 7E2Y para acoplar?",
     "is 7E2Y ready for docking?",
     "check_preparation"),
    ("prep_avisos",
     "qué advertencias tiene la preparación de 6LU7",
     "what warnings does the preparation of 6LU7 have",
     "check_preparation"),
    ("prep_ligando",
     "revisa la preparación de CC(=O)Oc1ccccc1C(=O)O contra 1AJ6 antes de lanzar",
     "check the preparation of CC(=O)Oc1ccccc1C(=O)O against 1AJ6 before launching",
     "check_preparation"),
    ("prep_metales",
     "¿el receptor 2ZJ5 pierde metales al prepararse?",
     "does receptor 2ZJ5 lose metals when it is prepared?",
     "check_preparation"),
]

DESC_EN = {
    **_DESC_EN,
    "check_preparation": (
        "Read the Preparation tab: the REAL pre-run check of a receptor (PDB ID) and, if given, a "
        "ligand (SMILES), without running docking. Returns which controls block the run, which warn "
        "and which could not be evaluated (gaps near the site, removed metals, chains, protonation, "
        "box, calibration), with the reason."
    ),
}
