"""
LogD por Henderson-Hasselbalch, y el sexto término del MPO de Pfizer.

# Lo que había

    # 6. logD (approximated as logP - 0.5 for neutral compounds)
    logd_est = logp - 0.5

Un desplazamiento constante, con el propio comentario admitiendo que sólo vale
para compuestos neutros y aplicándose a todos. En fármacos del SNC eso es al
revés del caso típico: la mayoría llevan una amina básica que a pH 7.4 está
protonada en más del 95 % y pierde entre 1.5 y 2.5 unidades de lipofilia.

Y el sexto término del MPO de Pfizer es el **pKa del centro más básico**; aquí
estaba el número de aceptores de enlace de hidrógeno ocupando su sitio.

Medido contra LogD7.4 experimental de literatura:

                  exp     −0.5 constante     Henderson-Hasselbalch
    aspirina     −2.0         +0.81                 −1.89
    fluoxetina   +1.9         +3.94                 +2.03
    levodopa     −2.4         −0.45                 −3.21

El error pasa de 2-2.8 unidades logarítmicas a menos de 0.9.
"""

import pytest

from chem.ionizacion import (
    PH_FISIOLOGICO,
    analizar_ionizacion,
    desirabilidad_pka,
)

# (nombre, SMILES, LogD7.4 experimental de referencia)
FARMACOS = [
    ("aspirina", "CC(=O)Oc1ccccc1C(=O)O", -2.0),
    ("fluoxetina", "CNCCC(Oc1ccc(cc1)C(F)(F)F)c1ccccc1", 1.9),
    ("difenhidramina", "CN(C)CCOC(c1ccccc1)c1ccccc1", 1.3),
    ("cafeina", "Cn1cnc2c1c(=O)n(C)c(=O)n2C", -0.1),
    ("ibuprofeno", "CC(C)Cc1ccc(cc1)C(C)C(O)=O", 0.6),
]


def _logp(smiles: str) -> float:
    from rdkit import Chem
    from rdkit.Chem import Crippen

    return Crippen.MolLogP(Chem.MolFromSmiles(smiles))


@pytest.mark.parametrize(("nombre", "smiles", "experimental"), FARMACOS)
def test_el_logd_estimado_se_acerca_al_experimental(nombre, smiles, experimental):
    estado = analizar_ionizacion(smiles, _logp(smiles))
    assert estado.logd is not None
    assert abs(estado.logd - experimental) < 1.0, (
        f"{nombre}: LogD estimado {estado.logd} frente a {experimental} experimental"
    )


@pytest.mark.parametrize(("nombre", "smiles", "experimental"), FARMACOS)
def test_es_mejor_que_el_desplazamiento_constante(nombre, smiles, experimental):
    """La comparación directa con la fórmula que se retiró."""
    logp = _logp(smiles)
    nuevo = abs(analizar_ionizacion(smiles, logp).logd - experimental)
    viejo = abs((logp - 0.5) - experimental)
    assert nuevo <= viejo + 1e-9, f"{nombre}: el método nuevo no mejora al constante"


def test_una_base_pierde_lipofilia_y_un_neutro_no():
    base = analizar_ionizacion("CN(C)CCOC(c1ccccc1)c1ccccc1", 3.35)
    neutro = analizar_ionizacion("Cn1cnc2c1c(=O)n(C)c(=O)n2C", -1.03)
    assert base.logd < 3.35 - 2.0, "una amina de pKa ~9.8 pierde más de 2 unidades"
    assert neutro.logd == pytest.approx(-1.03), "sin centro ionizable, LogD = LogP"


def test_la_carga_neta_es_la_de_la_especie_dominante():
    assert analizar_ionizacion("CC(=O)Oc1ccccc1C(=O)O", 1.31).carga_neta == -1
    assert analizar_ionizacion("CN(C)CCOC(c1ccccc1)c1ccccc1", 3.35).carga_neta == 1
    assert analizar_ionizacion("Cn1cnc2c1c(=O)n(C)c(=O)n2C", -1.03).carga_neta == 0


def test_el_zwitterion_usa_un_solo_denominador():
    """Sumar dos logaritmos multiplicaba los denominadores.

    Con levodopa la forma multiplicativa daba LogD −5.6 frente al −2.4
    experimental; con las microespecies en un único denominador queda cerca de
    −3.2, que es lo que esta aproximación puede sostener.
    """
    import math

    levodopa = "N[C@@H](Cc1ccc(O)c(O)c1)C(O)=O"
    logp = _logp(levodopa)
    estado = analizar_ionizacion(levodopa, logp)

    a = 10 ** (9.8 - PH_FISIOLOGICO)
    b = 10 ** (PH_FISIOLOGICO - 4.2)
    multiplicativa = logp - (math.log10(1 + a) + math.log10(1 + b))

    assert estado.logd > multiplicativa + 1.0
    assert abs(estado.logd - (-2.4)) < 1.2


def test_se_declaran_los_centros_reconocidos():
    """El pKa es representativo de la clase, no calculado: hay que poder verlo."""
    estado = analizar_ionizacion("CN(C)CCOC(c1ccccc1)c1ccccc1", 3.35)
    nombres = {c[0] for c in estado.centros}
    assert "amina_alifatica" in nombres
    assert estado.pka_mas_basico == 9.8


def test_una_amida_no_se_confunde_con_una_amina_basica():
    """El nitrógeno amídico no se protona a pH 7.4."""
    estado = analizar_ionizacion("CC(=O)Nc1ccc(O)cc1", 1.0)  # paracetamol
    assert estado.carga_neta == 0
    assert estado.pka_mas_basico is None


def test_un_smiles_ilegible_no_inventa_ionizacion():
    estado = analizar_ionizacion("esto((no es", 2.0)
    assert estado.logd == 2.0
    assert estado.centros == []


# ── El término de pKa del MPO ──────────────────────────────────────────────

@pytest.mark.parametrize(
    ("pka", "esperado"),
    [(None, 1.0), (7.0, 1.0), (8.0, 1.0), (9.0, 0.5), (10.0, 0.0), (12.0, 0.0)],
)
def test_la_desirabilidad_de_pka_penaliza_las_bases_fuertes(pka, esperado):
    """Wager et al.: un pKa alto significa cargado en sangre, y cargado no difunde."""
    assert desirabilidad_pka(pka) == pytest.approx(esperado)


def test_el_mpo_usa_pka_y_logd_cuando_recibe_el_smiles():
    from chem.blood_viability import _calculate_cns_mpo

    # Base fuerte: el término de pKa la penaliza y el LogD real baja.
    con_smiles = _calculate_cns_mpo(
        mw=255.4, logp=3.35, tpsa=12.5, hbd=0, hba=2,
        smiles="CN(C)CCOC(c1ccccc1)c1ccccc1",
    )
    sin_smiles = _calculate_cns_mpo(mw=255.4, logp=3.35, tpsa=12.5, hbd=0, hba=2)
    assert con_smiles < sin_smiles, (
        "una amina de pKa 9.8 debe puntuar peor cuando se tiene en cuenta que "
        "en sangre está protonada"
    )
