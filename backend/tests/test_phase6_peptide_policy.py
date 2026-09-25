"""Regression cases for the phase-6 peptide routing and box contract."""

from __future__ import annotations

import importlib

import pytest
from pydantic import ValidationError
from rdkit import Chem

from services.ai.known_molecules import KNOWN_MOLECULES
from services.chemistry.peptides import es_peptido_lineal
from services.docking.protocolo import es_motor_peptidico


@pytest.mark.parametrize("name", ("lisinopril", "enalapril", "ampicilina"))
def test_amide_drugs_do_not_trigger_peptide_advice(name):
    assert es_peptido_lineal(KNOWN_MOLECULES[name]) is False
    assert es_motor_peptidico(None) is False


@pytest.mark.parametrize("sequence", ("AAA", "DRVYIHPF"))
def test_linear_standard_peptides_are_recognized(sequence):
    smiles = Chem.MolToSmiles(Chem.MolFromFASTA(sequence))
    assert es_peptido_lineal(smiles) is True
    assert es_motor_peptidico("esmfold") is True


@pytest.mark.asyncio
async def test_sidecar_abstains_without_declared_box(monkeypatch):
    monkeypatch.syspath_prepend("backend/sidecars/esmfold")
    app = importlib.import_module("app")
    predictor = importlib.import_module("predictor")
    request = {"protein_pdb": "ATOM      1  N   ALA A   1      0.000   0.000   0.000  1.00 20.00           N",
               "peptide_smiles": "N[C@@H](C)C(=O)O"}
    with pytest.raises(ValidationError) as error:
        app.PredictRequest.model_validate(request)
    assert {item["loc"][0] for item in error.value.errors()} == {"grid_center", "grid_size"}

    result = await predictor.ESMFoldFastPredictor.predict(
        object(), request["protein_pdb"], request["peptide_smiles"], 1, None, None,
    )
    assert result.success is False
    assert result.error == "SIN_CAJA_DECLARADA"
    assert result.poses == []
