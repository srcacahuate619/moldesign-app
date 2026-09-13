"""
Qué se puede afirmar de un ΔG de MM-GBSA, y con qué moléculas se puede calcular.

`molchamb_v2::_amber_atom_type` tipa el ligando con la biblioteca de PROTEÍNA
de AMBER14: cada carbono acaba en `protein-CT` / `protein-CA` / `protein-C`, y
de ahí salen los parámetros de enlace, ángulo y torsión que se aplican a una
molécula orgánica que no es un péptido. La interfaz, mientras tanto, prometía
«reporta ΔG = G(complejo) − G(receptor) − G(ligando)», que describe la
aritmética y no el modelo.

Y los halógenos —cotidianos en química médica— no tienen tipo de proteína, así
que el cálculo los rechazaba… después de preparar el receptor y construir el
sistema, con un `Unsupported elements: {'Cl'}` en inglés.
"""

import pytest

from services.chemistry.mmgbsa_contrato import (
    ELEMENTOS_PARAMETRIZABLES,
    MMGBSA_CONDICION,
    elementos_no_parametrizables,
    motivo_de_no_parametrizable,
)

# Fármacos reales. Los tres primeros llevan halógeno.
CLOROQUINA = "CCN(CC)CCCC(C)Nc1ccnc2cc(Cl)ccc12"
FLUOXETINA = "CNCCC(Oc1ccc(cc1)C(F)(F)F)c1ccccc1"
LEVOTIROXINA = "N[C@@H](Cc1cc(I)c(Oc2cc(I)c(O)c(I)c2)c(I)c1)C(O)=O"
ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"
CAFEINA = "Cn1cnc2c1c(=O)n(C)c(=O)n2C"


@pytest.mark.parametrize(
    ("smiles", "esperado"),
    [
        (CLOROQUINA, {"Cl"}),
        (FLUOXETINA, {"F"}),
        (LEVOTIROXINA, {"I"}),
        (ASPIRINA, set()),
        (CAFEINA, set()),
    ],
)
def test_se_detecta_antes_de_calcular_lo_que_no_se_puede_parametrizar(smiles, esperado):
    assert elementos_no_parametrizables(smiles) == esperado


def test_un_smiles_ilegible_no_se_confunde_con_un_elemento_raro():
    """Nombrar la causa equivocada es peor que no nombrarla."""
    assert elementos_no_parametrizables("esto no es un smiles((") == set()


def test_el_motivo_nombra_los_elementos_y_la_causa():
    motivo = motivo_de_no_parametrizable({"Cl", "Br"})
    assert "Br, Cl" in motivo
    assert "AMBER14" in motivo
    # Y dice que el resto de la evaluación no depende de esto, que es lo que
    # el usuario necesita saber para no tirar la corrida entera.
    assert "no depende de MM-GBSA" in motivo


def test_los_elementos_soportados_son_los_que_tienen_tipo_de_proteina():
    assert ELEMENTOS_PARAMETRIZABLES == frozenset({"C", "H", "O", "N", "S", "P"})


def test_la_condicion_dice_para_que_sirve_y_para_que_no():
    # Lo que el método sostiene…
    assert "ORDENAR poses del mismo ligando" in MMGBSA_CONDICION
    # …y lo que no.
    assert "No es comparable entre" in MMGBSA_CONDICION
    assert "experimental" in MMGBSA_CONDICION
    # La causa, nombrada: el tipado con biblioteca de proteína.
    assert "AMBER14" in MMGBSA_CONDICION


def test_la_condicion_viaja_con_el_numero_al_resumen_de_evidencia():
    from services.blockchain.evidence_summary import build_evidence_summary

    class _Eval:
        mmgbsa_score = -21.4
        docking_poses = []
        scientific_warnings = []

    resumen = build_evidence_summary(_Eval())
    mmgbsa = resumen["ml_signals"]["mmgbsa"]
    assert mmgbsa["salida_kcal_mol"] == -21.4
    assert mmgbsa["condicion_de_validez"] == MMGBSA_CONDICION


def test_sin_numero_no_hay_condicion_que_declarar():
    from services.blockchain.evidence_summary import build_evidence_summary

    class _Eval:
        mmgbsa_score = None
        docking_poses = []
        scientific_warnings = []

    resumen = build_evidence_summary(_Eval())
    assert resumen["ml_signals"]["mmgbsa"]["condicion_de_validez"] is None


def test_el_modulo_muerto_ya_no_ofrece_un_calculo_falso():
    """`scoring/mmgbsa.py` minimizaba la proteína SIN el ligando y repartía la
    energía no enlazada con 65/35 escritos a mano, bajo nombres de campo que
    parecían una descomposición medida. No lo llamaba nadie."""
    import scoring.mmgbsa as modulo

    assert not hasattr(modulo, "run_mmgbsa")
    assert not hasattr(modulo, "MMGBSAResult")
    assert hasattr(modulo, "is_gpu_available")
