"""Controles para los filtros y unidades corregidos en fase 2."""

import pytest
from rdkit import Chem
from rdkit.Chem import Crippen

from chem.properties import GhoseRule, MueggeRule, VerberRule, _calc_sa_score, sascorer
from core.models import EvaluationResultRead
from scoring.eficiencia import KCAL_POR_UNIDAD_LOG, calcular


def test_muegge_exige_los_nueve_criterios():
    todos, score = MueggeRule.evaluate(300, 2, 80, 2, 4, 3, 2, 15, 5)
    ocho, ocho_score = MueggeRule.evaluate(300, 2, 80, 2, 4, 3, 8, 15, 5)
    assert (todos, score) == (True, 9)
    assert (ocho, ocho_score) == (False, 8)


def test_ghose_incluye_refractividad_molar():
    mol = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    mr = Crippen.MolMR(mol)
    assert GhoseRule.evaluate(300, 2, 25, mr)[0] is True
    cumple, motivos = GhoseRule.evaluate(300, 2, 25, 39.9)
    assert not cumple and any("MR=" in motivo for motivo in motivos)


def test_veber_acepta_alternativa_de_puentes_h():
    assert VerberRule.evaluate(3, 145, 2, 8) == (True, [])
    assert VerberRule.evaluate(3, 145, 5, 8)[0] is False
    assert VerberRule.evaluate(11, 100, 1, 2)[0] is False


@pytest.mark.skipif(sascorer is None, reason="RDKit sascorer ausente")
def test_sa_no_anade_penalizacion_propia_por_anillo():
    mol = Chem.MolFromSmiles("C1CC1")
    score, motives = _calc_sa_score(mol)
    assert score == round(sascorer.calculateScore(mol), 2)
    assert not any("Tensión de anillo" in m for m in motives)


def test_le_y_conversion_unificadas():
    result = EvaluationResultRead.model_construct(affinity_kcal=-7.5, heavy_atom_count=25, log_p=2.0)
    metricas = calcular(-7.5, 25)
    assert result.ligand_efficiency == 0.3
    assert result.ligand_efficiency == metricas.ligand_efficiency_vina
    assert result.ligand_lipophilicity_efficiency == round(7.5 / KCAL_POR_UNIDAD_LOG - 2.0, 3)

