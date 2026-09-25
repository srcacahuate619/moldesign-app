"""pH solicitado llega a las dos rutas de preparación."""

import pytest
from pydantic import ValidationError

from api.routers.evaluation import EvaluationSubmitRequest, PipelineConfigRequest
from chem import router as chem_router


def test_api_rechaza_ph_fuera_de_dominio_o_conflictivo():
    with pytest.raises(ValidationError):
        EvaluationSubmitRequest(smiles="CCO", ph=13.0)
    with pytest.raises(ValidationError):
        EvaluationSubmitRequest(
            smiles="CCO", ph=3.0,
            pipeline_config=PipelineConfigRequest(stage_params={"conformer": {"ph": 7.4}}),
        )
    request = EvaluationSubmitRequest(smiles="CCO", ph=3.0)
    assert request.ph == 3.0


@pytest.mark.asyncio
async def test_endpoint_conformer_pasa_ph_y_expone_estado(monkeypatch):
    calls = []
    async def fake(smiles, ph):
        calls.append((smiles, ph))
        return {
            "canonical_smiles": smiles, "smiles_hash": "a" * 64,
            "conformer_path": "ligand.sdf", "num_atoms_3d": 3,
            "optimization_converged": True, "had_macrocycle": False,
            "molecular_formula": "C2H6O", "sdf_content": "SDF",
            "estado_del_ligando": {"protonacion": {"ph": ph}},
        }
    monkeypatch.setattr(chem_router, "generate_conformer", fake)
    response = await chem_router.conformer_endpoint(
        chem_router.ConformerRequest(smiles="CCO", ph=3.0), cache=None
    )
    assert calls == [("CCO", 3.0)]
    assert response.estado_del_ligando["protonacion"]["ph"] == 3.0
    assert response.from_cache is False
