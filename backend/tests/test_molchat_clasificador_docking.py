"""«Acopla X contra 1AJ6» es un docking, y el receptor sale aunque no lo anuncie una palabra.

LOS FALLOS QUE VIGILA (medidos el 2026-10-10 con el arnés de herramientas).

1. El clasificador sólo reconocía «afinidad» y «docking»: «acopla la aspirina
   contra 1AJ6» acababa en `compute_properties`, que calcula propiedades y no
   propone el acoplamiento.
2. El receptor sólo se extraía detrás de «contra», «receptor», «proteína»…:
   en «la afinidad de la aspirina con 7E2Y» o «docking de CCO en 6LU7» se
   perdía. Un código PDB suelto (empieza por dígito y lleva una letra) sirve de
   respaldo; un año no.
"""
from __future__ import annotations

import pytest

from services.ai.intent_classifier import classify
from tests.conftest import rdkit_available

pytestmark = pytest.mark.skipif(not rdkit_available(), reason="RDKit no disponible")

ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"


@pytest.mark.parametrize("mensaje, receptor", [
    ("acopla la aspirina contra 1AJ6", "1AJ6"),
    ("acopla CC(=O)Oc1ccccc1C(=O)O contra 1AJ6", "1AJ6"),
    ("Acópla el ibuprofeno al receptor 7E2Y", "7E2Y"),
])
def test_acoplar_es_docking(mensaje, receptor):
    intencion = classify(mensaje)
    assert intencion.name == "docking"
    assert intencion.tool == "run_docking"
    assert intencion.target == receptor


@pytest.mark.parametrize("mensaje, receptor", [
    ("calcula la afinidad de la aspirina con 7E2Y", "7E2Y"),
    ("docking de CCO en 6LU7", "6LU7"),
])
def test_el_receptor_suelto_se_reconoce(mensaje, receptor):
    assert classify(mensaje).target == receptor


def test_un_anio_no_es_un_receptor():
    intencion = classify("afinidad de la aspirina en 2024")
    assert intencion.name == "docking"
    assert not intencion.target


def test_lo_que_no_pide_un_acoplamiento_no_cambia():
    assert classify("calcula las propiedades de la aspirina").tool == "compute_properties"
    assert classify("¿qué es el acoplamiento molecular?").name == "conceptual"
    assert classify("calcula las propiedades de la aspirina").smiles == ASPIRINA
