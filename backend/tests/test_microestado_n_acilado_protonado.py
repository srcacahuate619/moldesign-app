"""Un N acilado protonado no gana un empate de carga (hERG, amoxicilina; revisión final de 1.0.4).

`elegir_microestado` comparaba sólo CUÁNTAS cargas tiene cada microestado. La amoxicilina empata en distancia 0 entre el
zwitterión de manual (NH3+ y carboxilato) y una especie con el N de la β-lactama protonado y la amina neutra, y el
orden alfabético elegía la segunda. Medido sobre 20 fármacos con amida o lactama: cambian la amoxicilina, la
ampicilina y el lisinopril (que acoplaba el N de la prolina protonado y la lisina neutra); en los otros 17 no cambia
nada. El criterio sólo desempata: no altera una elección en la que las distancias de carga difieren.
"""
from __future__ import annotations

import pytest

pytest.importorskip("dimorphite_dl")
rdkit = pytest.importorskip("rdkit")

from chem.ionizacion import _n_acilados_protonados, elegir_microestado  # noqa: E402

AMOXICILINA = "CC1(C)SC2C(NC(=O)C(N)c3ccc(O)cc3)C(=O)N2C1C(=O)O"
AMPICILINA = "CC1(C)SC2C(NC(=O)C(N)c3ccccc3)C(=O)N2C1C(=O)O"
LISINOPRIL = "NCCCCC(NC(CCc1ccccc1)C(=O)O)C(=O)N1CCCC1C(=O)O"


def _candidatos(smiles: str) -> list[str]:
    import dimorphite_dl

    return list(dimorphite_dl.protonate_smiles(smiles, ph_min=7.4, ph_max=7.4, precision=1.0, max_variants=128))


@pytest.mark.parametrize("nombre, smiles", [("amoxicilina", AMOXICILINA), ("ampicilina", AMPICILINA),
                                            ("lisinopril", LISINOPRIL)])
def test_no_se_acopla_la_especie_con_el_n_acilado_protonado(nombre, smiles):
    candidatos = _candidatos(smiles)
    # El defecto existía: dimorphite ofrece esa especie y empata en carga con la buena.
    assert any(_n_acilados_protonados(c) for c in candidatos), nombre

    elegido, criterio = elegir_microestado(smiles, candidatos, 7.4)

    assert _n_acilados_protonados(elegido) == 0, elegido
    assert "[NH3+]" in elegido, elegido           # la amina primaria es la que lleva el protón
    assert criterio["descartadas_por_n_acilado_protonado"] >= 1


def test_la_amoxicilina_queda_resuelta_y_lo_declara():
    _, criterio = elegir_microestado(AMOXICILINA, _candidatos(AMOXICILINA), 7.4)
    assert criterio["desajuste"] == 0 and criterio["empatados"] == 1
    assert criterio["quimica_resuelta"] is True


def test_la_eleccion_no_depende_del_orden_de_dimorphite():
    candidatos = _candidatos(AMOXICILINA)
    a, _ = elegir_microestado(AMOXICILINA, candidatos, 7.4)
    b, _ = elegir_microestado(AMOXICILINA, list(reversed(candidatos)), 7.4)
    assert a == b


def test_control_negativo_el_detector_ve_la_especie_equivocada():
    """El guardián tiene que demostrar que ve: la especie que se elegía antes SÍ cuenta como defectuosa."""
    antes = "CC1(C)SC2C(NC(=O)C(N)c3ccc(O)cc3)C(=O)[NH+]2C1C(=O)[O-]"
    ahora = "CC1(C)SC2C(NC(=O)C([NH3+])c3ccc(O)cc3)C(=O)N2C1C(=O)[O-]"
    assert _n_acilados_protonados(antes) == 1
    assert _n_acilados_protonados(ahora) == 0
    # Una amina cuaternaria sin carbonilo, un NH3+ junto a un carbonilo (C-N) y SMILES ilegibles no cuentan.
    assert _n_acilados_protonados("C[NH+](C)CC") == 0
    assert _n_acilados_protonados("[NH3+]CC(=O)[O-]") == 0
    assert _n_acilados_protonados("no es un smiles") == 0


@pytest.mark.parametrize("smiles", ["NCCCCC(N)C(=O)O", "CC(C)NCC(O)COc1cccc2ccccc12",
                                    "CCN(CC)CCNC(=O)c1ccc(N)cc1"])
def test_sin_candidatos_con_n_acilado_nada_cambia(smiles):
    candidatos = _candidatos(smiles)
    assert not any(_n_acilados_protonados(c) for c in candidatos)
    _, criterio = elegir_microestado(smiles, candidatos, 7.4)
    assert criterio["descartadas_por_n_acilado_protonado"] == 0
