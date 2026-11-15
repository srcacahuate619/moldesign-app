"""La PPB sólo alimenta al consenso de BBB si es un porcentaje de 0 a 100 (auditoría científica 1.0.4, S2-4).

`PPBR_AZ` es una regresión en porcentaje de unión a proteína plasmática, de dominio físico 0 a 100, y ADMET-AI no
la acota. Sobre los 2440 fármacos aprobados de DrugBank que distribuye ADMET-AI 2.0.1, 274 predicciones salen por
encima de 100 y 59 por debajo de 0. La capa 2a vetaba con cualquiera de esos valores imposibles: aripiprazol
(102,26 %, p_BBB 0,975) y pimozida (100,53 %, 0,970), antipsicóticos de acción central, salían «no permeables».

Decisión del propietario, 2026-11-14: una PPB fuera de [0, 100], no finita o ausente es un dato no disponible para el
consenso y para la categoría. No se recorta a 100, porque recortar fabricaría un valor que activa las reglas de PPB.
La misma PPB validada alimenta las dos cosas.

Los dos antipsicóticos son controles fuera del panel de 47. Dentro del panel, la sacarosa trae una PPB de −1,78 %.
"""

from __future__ import annotations

import math

import pytest
from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors

from chem import blood_viability as bv
from chem.bbb_consenso import decidir_bbb, ppb_valida
from core.models import PhysicochemicalProperties
from tests.test_bbb_consenso import REFERENCIA, _decidir, _fila

ARIPIPRAZOL = "O=C1CCc2ccc(OCCCCN3CCN(c4cccc(Cl)c4Cl)CC3)cc2N1"
PIMOZIDA = "O=C1Nc2ccccc2N1C1CCN(CCCC(c2ccc(F)cc2)c2ccc(F)cc2)CC1"

#: (SMILES, p_BBB, PPB predicha, anillos aromáticos): las salidas de ADMET-AI 2.0.1 sobre `drugbank_approved.csv`.
ARIPIPRAZOL_ADMET = (ARIPIPRAZOL, 0.974926, 102.262436, 2)
PIMOZIDA_ADMET = (PIMOZIDA, 0.969579, 100.52966, 4)


def _descriptores(smiles: str) -> dict:
    mol = Chem.MolFromSmiles(smiles)
    return dict(
        mw=Descriptors.MolWt(mol), logp=Crippen.MolLogP(mol), tpsa=rdMolDescriptors.CalcTPSA(mol),
        hbd=rdMolDescriptors.CalcNumHBD(mol), hba=rdMolDescriptors.CalcNumHBA(mol),
    )


def _decidir_con(smiles: str, p: float, ppb, aro: int):
    return decidir_bbb(smiles, p_modelo=p, ppb=ppb, anillos_aromaticos=aro, **_descriptores(smiles))


# ── El validador ───────────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("valor", [0, 0.0, 1e-9, 50.5, 92.0, 99.0, 99.9, 100, 100.0])
def test_un_porcentaje_de_0_a_100_inclusive_es_valido(valor):
    assert ppb_valida(valor) == float(valor)


@pytest.mark.parametrize(
    "valor",
    [-0.0001, -1.78, 100.0001, 100.1, 102.26, 1e6, math.nan, math.inf, -math.inf,
     None, True, False, "50", "", [], object()],
)
def test_lo_que_no_es_un_porcentaje_finito_de_0_a_100_no_esta_disponible(valor):
    assert ppb_valida(valor) is None


def test_un_numero_de_numpy_se_acepta_como_numero():
    np = pytest.importorskip("numpy")
    assert ppb_valida(np.float32(88.0)) == pytest.approx(88.0)
    assert ppb_valida(np.float64(100.5)) is None
    assert ppb_valida(np.float64("nan")) is None


# ── Los dos antipsicóticos que la capa 2a vetaba con un valor imposible ───────────────────────────────────────────


@pytest.mark.parametrize("admet", [ARIPIPRAZOL_ADMET, PIMOZIDA_ADMET], ids=["aripiprazol", "pimozida"])
def test_una_ppb_imposible_no_veta_a_un_antipsicotico(admet):
    smiles, p, ppb, aro = admet
    d = _decidir_con(smiles, p, ppb, aro)

    assert d.permeable is True
    assert d.capa == "3_modelo_confiado", d.capa


def test_el_salto_entre_100_y_100_1_es_de_disponibilidad_no_de_biologia():
    """100,0 es una PPB válida y 100,1 no lo es. Lo que cambia es si el dato existe, no la molécula.

    Se deja escrito para que nadie lo lea como un umbral biológico: con una PPB válida mayor que 92 y cuatro anillos
    aromáticos la capa 2b contradice el positivo del modelo y el consenso se abstiene, y con una inválida no hay
    regla de PPB que aplicar. Es la pimozida: con la PPB que predice el modelo (100,53) no hay PPB; con 100,0 habría.
    """
    smiles, p, _ppb, aro = PIMOZIDA_ADMET

    valida = _decidir_con(smiles, p, 100.0, aro)
    invalida = _decidir_con(smiles, p, 100.1, aro)

    assert (valida.permeable, valida.capa) == (None, "2b_conflicto_ppb_aromatico")
    assert (invalida.permeable, invalida.capa) == (True, "3_modelo_confiado")


@pytest.mark.parametrize("ppb", [math.nan, math.inf, -5.0, None])
def test_una_ppb_no_disponible_equivale_a_no_pasar_ppb(ppb):
    smiles, p, _ppb, aro = PIMOZIDA_ADMET

    sin_ppb = _decidir_con(smiles, p, None, aro)
    con = _decidir_con(smiles, p, ppb, aro)

    assert (con.permeable, con.capa) == (sin_ppb.permeable, sin_ppb.capa)


# ── Dentro del panel ──────────────────────────────────────────────────────────────────────────────────────────


def test_la_sacarosa_es_la_unica_fila_del_panel_con_ppb_fuera_de_rango():
    fuera = [f[0] for f in REFERENCIA if f[3] is not None and ppb_valida(f[3]) is None]

    assert fuera == ["sacarosa"]
    assert _fila("sacarosa")[3] == pytest.approx(-1.78)


def test_la_sacarosa_conserva_su_veredicto_sin_su_ppb():
    fila = _fila("sacarosa")
    sin_ppb = decidir_bbb(
        fila[1], p_modelo=fila[2], ppb=None, mw=fila[4], logp=fila[5], tpsa=fila[6],
        hbd=fila[7], hba=fila[8], anillos_aromaticos=fila[9],
    )

    decision = _decidir(fila)

    assert (decision.permeable, decision.capa) == (sin_ppb.permeable, sin_ppb.capa)
    assert decision.permeable is False


# ── La misma PPB validada alimenta la categoría ───────────────────────────────────────────────────────────────


def _propiedades(smiles: str) -> PhysicochemicalProperties:
    """Las propiedades con sus reglas coherentes: el modelo valida `lipinski_pass` y `veber_pass` contra los números."""
    d = _descriptores(smiles)
    mol = Chem.MolFromSmiles(smiles)
    rotables = rdMolDescriptors.CalcNumRotatableBonds(mol)
    return PhysicochemicalProperties(
        molecular_weight=d["mw"], log_p=d["logp"], tpsa=d["tpsa"], hbd=d["hbd"], hba=d["hba"],
        rotatable_bonds=rotables, heavy_atom_count=mol.GetNumHeavyAtoms(), ring_count=rdMolDescriptors.CalcNumRings(mol),
        qed=0.6, sa_score=3.0,
        lipinski_pass=d["mw"] <= 500 and d["logp"] <= 5 and d["hbd"] <= 5 and d["hba"] <= 10,
        veber_pass=rotables <= 10 and d["tpsa"] <= 140,
    )


def _calcular(monkeypatch, smiles: str, p: float, ppb):
    monkeypatch.setattr(bv, "predict_admet_ai", lambda _smi: {
        "Solubility": -4.0, "HIA": 1, "PPB": ppb, "BBB_prob": p, "hERG_prob": 0.1,
    })
    monkeypatch.setattr(bv, "predict_tabpfn_custom_toxicity", lambda _p: [])
    return bv.calculate_blood_viability(smiles, _propiedades(smiles))


@pytest.mark.parametrize("ppb", [102.262436, 100.1, -3.0, math.nan, math.inf])
def test_una_ppb_fuera_de_rango_no_es_extrema_ni_baja_en_la_categoria(monkeypatch, ppb):
    resultado = _calcular(monkeypatch, ARIPIPRAZOL, 0.974926, ppb)

    assert resultado.blood_ppb_category is None
    assert resultado.blood_bbb_permeable is True


@pytest.mark.parametrize(
    "ppb,categoria", [(0.0, "low"), (90.0, "low"), (90.01, "high"), (99.0, "high"), (99.01, "extreme"), (100.0, "extreme")]
)
def test_los_cortes_de_la_categoria_no_cambian_dentro_del_intervalo(monkeypatch, ppb, categoria):
    resultado = _calcular(monkeypatch, ARIPIPRAZOL, 0.5, ppb)

    assert resultado.blood_ppb_category == categoria


def test_ausente_y_fuera_de_rango_se_leen_igual(monkeypatch):
    """Sin PPB tampoco hay categoría: ausente y fuera de rango se leen igual."""
    ausente = _calcular(monkeypatch, ARIPIPRAZOL, 0.974926, None)
    imposible = _calcular(monkeypatch, ARIPIPRAZOL, 0.974926, 150.0)

    assert ausente.blood_ppb_category is imposible.blood_ppb_category is None
    assert ausente.blood_bbb_permeable == imposible.blood_bbb_permeable
