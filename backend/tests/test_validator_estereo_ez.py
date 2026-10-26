"""QA-030: el aviso de E/Z sin definir tiene que leer los '/' y '\\' del SMILES.

`_parse_smiles` parseaba con `sanitize=False` y no asignaba la estereoquímica,
así que `FindPotentialStereo` veía todo doble enlace como «sin especificar»: el
validador avisaba de E/Z sin definir en el tamoxifeno (Z), el ácido fumárico o
un macrociclo con los tres dobles enlaces declarados, y un CXSMILES de Ketcher
sin E/Z legible no se distinguía de uno bien escrito.
"""
from __future__ import annotations

import pytest

from chem.validator import validate_smiles

GELDANAMICINA = (
    r"COC1=C2C[C@@H](C)C[C@H](OC)[C@H](O)[C@@H](C)/C=C(\C)[C@H](OC(N)=O)"
    r"[C@@H](OC)/C=C\C=C(\C)C(=O)NC(=CC1=O)C2=O"
)


def _avisos_ez(smiles: str) -> list[str]:
    return [w for w in validate_smiles(smiles).warnings if "E/Z" in w]


@pytest.mark.parametrize("smiles", [
    r"C/C=C/C",
    r"OC(=O)/C=C/C(=O)O",
    r"CC/C(c1ccccc1)=C(/c1ccc(OCCN(C)C)cc1)c1ccccc1",  # tamoxifeno (Z)
    GELDANAMICINA,  # macrociclo de 19: tres dobles enlaces declarados
])
def test_e_z_declarada_no_se_avisa(smiles: str) -> None:
    assert _avisos_ez(smiles) == []


def test_e_z_sin_declarar_se_avisa() -> None:
    avisos = _avisos_ez("CC=CC")
    assert len(avisos) == 1 and avisos[0].startswith("Se detectaron 1 doble")


def test_el_canonico_conserva_la_e_z_declarada() -> None:
    from rdkit import Chem

    canonico = validate_smiles(GELDANAMICINA).canonical_smiles
    assert canonico is not None
    especificados = [
        c for c in Chem.FindPotentialStereo(Chem.MolFromSmiles(canonico))
        if c.type == Chem.StereoType.Bond_Double
        and c.specified == Chem.StereoSpecified.Specified
    ]
    assert len(especificados) == 3


def test_la_quiralidad_sigue_leyendose() -> None:
    assert not [w for w in validate_smiles("C[C@H](N)C(=O)O").warnings if "estereocentro" in w]
    assert [w for w in validate_smiles("CC(N)C(=O)O").warnings if "estereocentro" in w]
