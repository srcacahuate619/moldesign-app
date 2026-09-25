"""PHYS-001/002/010: el motor legacy no produce ni publica una energia."""
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


def test_configuracion_rechaza_mmgbsa_antes_de_ejecutar():
    from pydantic import ValidationError
    from api.routers.evaluation import PipelineConfigRequest

    with pytest.raises(ValidationError, match="MM-GBSA no disponible"):
        PipelineConfigRequest(pro_mmgbsa=True)


@pytest.mark.asyncio
async def test_endpoint_se_abstiene_con_422_sin_ejecutar_worker(monkeypatch):
    from api.routers import pro_features

    async def owned(**kwargs):
        return None

    monkeypatch.setattr(pro_features, "require_owned_molecule", owned)
    with pytest.raises(HTTPException) as error:
        await pro_features.run_mmgbsa_endpoint(
            str(uuid.uuid4()), pose_rank=1, num_steps=1000,
            current_user=None, db=object(),
        )
    assert error.value.status_code == 422
    assert "MMGBSA_CONDICION" in error.value.detail


def test_resultado_legacy_no_sale_como_energia():
    from services.blockchain.evidence_summary import build_evidence_summary

    result = SimpleNamespace(mmgbsa_score=-192.47, docking_poses=[], scientific_warnings=[])
    signal = build_evidence_summary(result)["ml_signals"]["mmgbsa"]
    assert signal["salida_kcal_mol"] is None
    assert signal["status"] == "legacy_invalidado"


def test_score_legacy_no_modifica_el_indice():
    from core.models import DockingPose, DockingResult, PhysicochemicalProperties
    from scoring.engine import calculate_score_breakdown

    docking = DockingResult(
        best_affinity=-8.0,
        poses=[DockingPose(rank=1, affinity=-8.0, rmsd_lb=None, rmsd_ub=None)],
    )
    props = PhysicochemicalProperties(
        molecular_weight=300.0, log_p=2.0, tpsa=60.0, hbd=1, hba=4,
        rotatable_bonds=3, heavy_atom_count=21, ring_count=2,
        qed=0.7, sa_score=2.5, lipinski_pass=True, veber_pass=True,
    )
    sin_legacy = calculate_score_breakdown(docking, props, target_family="default")
    con_legacy = calculate_score_breakdown(
        docking, props, target_family="default", mmgbsa_score=-192.47,
    )
    assert con_legacy.total_score == sin_legacy.total_score
    assert con_legacy.mmgbsa_score is None
