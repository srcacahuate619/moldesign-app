"""Graph and provenance regressions for exploratory analog suggestions."""

from __future__ import annotations

import pytest
from rdkit import Chem

from services.chemistry.analog_generator import (
    AnalogStrategy,
    _compute_sa_score,
    _hop_scaffold,
    _make_candidate,
    _swap_substituents,
)
from services.chemistry.structural_alerts import alertas_estructurales
from services.denovo.generator import generate_suggestions


def test_analog_uses_rdkit_sascorer_and_rejects_alerts():
    parent = "CN1CCN(CC1)c1ccc(cc1)C(=O)Nc1ccc(Cl)cc1"
    assert _compute_sa_score(Chem.MolFromSmiles(parent)) == pytest.approx(1.63, abs=0.01)
    quinone = "O=C1C=CC(=O)C=C1"
    assert alertas_estructurales(Chem.MolFromSmiles(quinone))
    assert _make_candidate(quinone, parent, AnalogStrategy.DIVERSITY) is None


def test_scaffold_hop_requires_explicit_site_and_keeps_parent_r_group():
    assert _hop_scaffold("Cc1ccccc1", "c1ccccc1", "c1ccncc1") is None
    product = _hop_scaffold("Cc1ccccc1", "c1ccccc1", "*c1ccncc1")
    assert product == Chem.MolToSmiles(Chem.MolFromSmiles("Cc1ccncc1"))
    assert _swap_substituents("Cc1ccccc1", "*OC") == "COc1ccccc1"


@pytest.mark.parametrize("aspirin", (
    "CC(=O)Oc1ccccc1C(=O)O",
    "O=C(O)c1ccccc1OC(C)=O",
))
def test_aspirin_acid_to_amide_changes_acid_not_ester(aspirin):
    result = generate_suggestions(aspirin, max_suggestions=10)
    assert result.success
    acid_to_amide = [s for s in result.suggestions if s.name == "Ácido → Amida"]
    assert len(acid_to_amide) == 1
    suggestion = acid_to_amide[0]
    assert suggestion.smiles == Chem.MolToSmiles(Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(N)=O"))
    assert len(suggestion.transformed_atom_indices) == 3
    assert suggestion.confidence == "low"
    assert any("no se acopló" in warning for warning in suggestion.warnings)
