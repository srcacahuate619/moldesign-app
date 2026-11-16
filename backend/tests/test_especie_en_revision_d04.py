"""D-04 de 1.0.4: α-aminoéster y N-alquilmorfolina con el N protonado piden revisión de la especie.

El alcance es el que sostiene la evidencia medida (revisión final del 2026-11-15, §2), no el SMARTS original: amina
PRIMARIA (`NH3+`), carbono α CH o CH2 y éster de metilo o etilo; morfolina de cuatro CH2 sin fusión con CH3 o CH2 en el
N. Los 17 padres de nivel A son los únicos con medida; fuera de ellos sólo hay fronteras. Declarar no cambia lo que se
acopla ni ningún score: cambia el estado de «Especie acoplada» a REVISAR, con su motivo.
"""

from __future__ import annotations

import pytest

from chem.especie_en_revision import motivos_de_revision, revisiones_en_mol
from services.dossier.model import campos_del_estado_del_ligando
from services.dossier.taxonomy import Estado
from tests.test_especie_en_revision import CORRECTAS_VERIFICADAS, _estado

#: Los 14 α-aminoésteres y los 3 N-alquilmorfolinas con pKa medido por fuente de nivel A (medidas.json de D-04).
PADRES_A_AMINOESTER = {
    "glicina etílico": "CCOC(=O)C[NH3+]",
    "glicina metílico": "COC(=O)C[NH3+]",
    "alanina etílico": "CCOC(=O)[C@@H]([NH3+])C",
    "alanina metílico": "COC(=O)[C@@H]([NH3+])C",
    "valina etílico": "CCOC(=O)[C@@H]([NH3+])C(C)C",
    "valina metílico": "COC(=O)[C@@H]([NH3+])C(C)C",
    "leucina etílico": "CCOC(=O)[C@@H]([NH3+])CC(C)C",
    "leucina metílico": "COC(=O)[C@@H]([NH3+])CC(C)C",
    "fenilalanina etílico": "CCOC(=O)[C@@H]([NH3+])Cc1ccccc1",
    "fenilalanina metílico": "COC(=O)[C@@H]([NH3+])Cc1ccccc1",
    "serina etílico": "CCOC(=O)[C@@H]([NH3+])CO",
    "serina metílico": "COC(=O)[C@@H]([NH3+])CO",
    "metionina etílico": "CCOC(=O)[C@@H]([NH3+])CCSC",
    "metionina metílico": "COC(=O)[C@@H]([NH3+])CCSC",
}
PADRES_A_MORFOLINA = {
    "N-etilmorfolina": "CC[NH+]1CCOCC1",
    "N-metilmorfolina": "C[NH+]1CCOCC1",
    "MOPS (N protonado, sulfonato)": "O=S(=O)([O-])CCC[NH+]1CCOCC1",
}

#: Lo que el alcance acotado deja fuera a propósito (fronteras de la revisión final): ninguno marca.
FUERA_DE_ALCANCE = {
    "éster de amina secundaria": "COC(=O)C[NH2+]C",
    "éster de amina terciaria": "COC(=O)C[NH+](C)C",
    "éster con la amina neutra": "COC(=O)CN",
    "éster fenílico (4-nitrofenil glicinato y similares)": "[NH3+]CC(=O)Oc1ccccc1",
    "zwitterión con carboxilato": "COC(=O)[C@@H]([NH3+])CC(=O)[O-]",
    "morfolina con carbono sustituido": "C[NH+]1C(C)COCC1",
    "morfolina N-isopropilo (carbono exocíclico ramificado)": "CC(C)[NH+]1CCOCC1",
    "MOPS con el N sin protonar (la molécula es un anión)": "O=S(=O)([O-])CCCN1CCOCC1",
    "morfolina NH sin sustituir": "C1COCC[NH2+]1",
    "tiomorfolina": "C[NH+]1CCSCC1",
    "N-aril-morfolina": "c1ccccc1[NH+]1CCOCC1",
}


def _codigos(smiles: str) -> list[str]:
    return [m.codigo for m in motivos_de_revision(smiles)]


@pytest.mark.parametrize("nombre", sorted(PADRES_A_AMINOESTER))
def test_los_padres_a_del_aminoester_se_declaran(nombre):
    assert _codigos(PADRES_A_AMINOESTER[nombre]) == ["alfa_aminoester"]


@pytest.mark.parametrize("nombre", sorted(PADRES_A_MORFOLINA))
def test_los_padres_a_de_la_morfolina_se_declaran(nombre):
    assert _codigos(PADRES_A_MORFOLINA[nombre]) == ["n_alquilmorfolina"]


@pytest.mark.parametrize("nombre", sorted(FUERA_DE_ALCANCE))
def test_lo_que_el_alcance_deja_fuera_no_se_marca(nombre):
    codigos = _codigos(FUERA_DE_ALCANCE[nombre])
    assert "alfa_aminoester" not in codigos and "n_alquilmorfolina" not in codigos


@pytest.mark.parametrize("nombre", sorted(CORRECTAS_VERIFICADAS))
def test_las_especies_correctas_verificadas_siguen_sin_marcarse(nombre):
    """0 de 17: las especies que el producto ya acopla bien no ganan una revisión por esta regla."""
    codigos = _codigos(CORRECTAS_VERIFICADAS[nombre])
    assert "alfa_aminoester" not in codigos and "n_alquilmorfolina" not in codigos


def test_devuelve_los_atomos_que_provocan_el_motivo():
    from rdkit import Chem

    smiles = "CC[NH+]1CCOCC1"
    (motivo, atomos), = [(m, a) for m, a in revisiones_en_mol(Chem.MolFromSmiles(smiles))
                         if m.codigo == "n_alquilmorfolina"]
    # El N protonado, su metileno exocíclico y el anillo entero: 1 N + 1 C + 4 C + 1 O (el metilo terminal no entra).
    assert len(atomos) == 7 and atomos == sorted(atomos)


def test_el_control_negativo_original_sobre_marcaba():
    """Autotest: el SMARTS original de la ampliación marcaba clopidogrel y el 4-nitrofenil glicinato; el acotado no.

    Clopidogrel acoplado: amina TERCIARIA (un NH+ con un anillo y un arilo), fuera del alcance medido.
    """
    clopidogrel = "COC(=O)[C@H](c1ccccc1Cl)[NH+]1CCc2sccc2C1"
    assert _codigos(clopidogrel) == []
    assert _codigos("[NH3+]CC(=O)Oc1ccc([N+](=O)[O-])cc1") == []


# ── En el expediente: REVISAR con su motivo, en los dos idiomas ──────────────


def _especie(smiles: str):
    return dict(campos_del_estado_del_ligando(_estado(smiles)))["especie"]


@pytest.mark.parametrize("smiles, fragmento", [
    ("CCOC(=O)C[NH3+]", "α-aminoéster"),
    ("CC[NH+]1CCOCC1", "N-alquilmorfolina"),
])
def test_el_expediente_pide_revision_y_dice_que_el_ejemplo_no_es_la_molecula(smiles, fragmento):
    campo = _especie(smiles)
    assert campo.estado == Estado.REVISAR
    assert fragmento in campo.razon
    assert "no esta molécula" in campo.razon and "energía libre" in campo.razon
    # La descripción del nitrógeno: no se llama «neutra» a la forma sin protonar (en MOPS es un anión).
    assert "fracción neutra" not in campo.razon

# La lectura en inglés se comprueba en `test_especie_en_ingles.py`, que traduce la auditoría completa por el camino real.
