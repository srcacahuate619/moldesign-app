"""SCI-B-094: el tope de 5000 automorfismos de MF-15-EXT no recorta ningún ligando de su cohorte."""
from pathlib import Path

import pytest
from rdkit import Chem

import analisis_mf15ext_tope_automorfismos as a

DATOS = Path(__file__).resolve().parents[2] / "data"


def test_el_contador_ve_un_recorte():
    benceno = Chem.MolFromSmiles("c1ccccc1")
    assert a.n_automorfismos(benceno) == 12
    assert a.n_automorfismos(benceno, tope=5) == 5          # control: con un tope bajo, recorta


@pytest.mark.skipif(not (DATOS / "pdbbind").is_dir(), reason="los SDF de PDBBind no viajan en el repo")
def test_ningun_ligando_de_la_cohorte_llega_al_tope():
    r = a.analizar(DATOS)
    assert r["n"] > 0 and r["en_el_tope"] == []
