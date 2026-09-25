"""ENG-A16: la frontera y el sello deben rechazar nombres sin motor ejecutable."""

import pytest
from pydantic import ValidationError

from api.routers.evaluation import EvaluationSubmitRequest
from core.models import DockingPose, DockingResult
from services.docking.protocolo import construir_protocolo


@pytest.mark.parametrize(
    "datos",
    [
        {"peptide_docking_engine": "esmfold-pro"},
        {"pipeline_config": {"docking_engine": "quickvina"}},
        {"pipeline_config": {"docking_engine": "qvina2"}},
        {"pipeline_config": {"stage_params": {"docking": {"engine": "diffdock"}}}},
        {"pipeline_config": {"peptide_docking_engine": "colabfold"}},
    ],
)
def test_solicitud_no_acepta_motor_que_no_ejecuta_la_build(datos):
    with pytest.raises(ValidationError):
        EvaluationSubmitRequest.model_validate({"smiles": "CCO", **datos})


def test_el_sello_usa_el_motor_efectivo_aunque_se_pidio_esmfold():
    docking = DockingResult(
        best_affinity=-5.0,
        poses=[DockingPose(rank=1, affinity=-5.0, rmsd_lb=0.0, rmsd_ub=0.0)],
        engine_efectivo="vina",
    )
    protocolo = construir_protocolo(
        docking=docking, peptide_engine="esmfold", docking_engine="vina"
    )
    assert protocolo["engine"] == "vina"
    assert protocolo["solicitado"]["engine"] == "esmfold"


def test_el_sello_rechaza_un_motor_sin_ejecucion_demostrada():
    docking = DockingResult(
        best_affinity=-5.0,
        poses=[DockingPose(rank=1, affinity=-5.0, rmsd_lb=0.0, rmsd_ub=0.0)],
    )
    with pytest.raises(ValueError, match="motor"):
        construir_protocolo(docking=docking, docking_engine="diffdock")


@pytest.mark.parametrize(
    "datos",
    [
        {"peptide_docking_engine": "esmfold-pro"},
        {"pipeline_config": {"docking_engine": "quickvina"}},
        {"pipeline_config": {"stage_params": {"docking": {"engine": "diffdock"}}}},
    ],
)
def test_submit_http_rechaza_motor_inexistente_antes_de_encolar(datos):
    from fastapi.testclient import TestClient
    from api.main import app
    from api.dependencies import get_current_user_optional
    from core.database import get_db

    # Una petición inválida no debe abrir la base de datos real del usuario.
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user_optional] = lambda: None
    try:
        respuesta = TestClient(app).post("/evaluation/submit", json={"smiles": "CCO", **datos})
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user_optional, None)
    assert respuesta.status_code == 422


@pytest.mark.asyncio
async def test_runner_pro_rechaza_diffdock_antes_de_crear_una_corrida():
    from services.pipeline.runner import run_pipeline

    with pytest.raises(ValueError, match="motor"):
        await run_pipeline(
            task_id="eng-a16", smiles="CCO", target_pdb_id="7E2Y",
            docking_engine="diffdock",
        )


@pytest.mark.asyncio
async def test_helper_peptidico_rechaza_servicio_no_publicado_antes_de_tocar_db():
    from services.docking.peptide_docking import run_peptide_docking_helper

    with pytest.raises(ValueError, match="motor"):
        await run_peptide_docking_helper(
            task_id="eng-a16", smiles="CCO", target_pdb_id="7E2Y",
            peptide_docking_engine="esmfold-pro",
        )


def test_inventario_no_publica_motores_que_el_backend_rechaza():
    from api.routers.evaluation import inventario_de_motores
    from services.docking.protocolo import (
        MOTORES_DOCKING_EJECUTABLES, MOTORES_PEPTIDICOS_EJECUTABLES,
    )

    inventario = inventario_de_motores()
    disponibles = {
        item["id"] for grupo in inventario.values() for item in grupo if item["disponible"]
    }
    assert disponibles <= MOTORES_DOCKING_EJECUTABLES | MOTORES_PEPTIDICOS_EJECUTABLES


def test_runner_no_contiene_rama_que_fabrica_afinidad_diffdock():
    from pathlib import Path
    fuente = (Path(__file__).resolve().parents[1] / "services/pipeline/runner.py").read_text(
        encoding="utf-8"
    )
    assert "fake_affinity" not in fuente
    assert 'if engine == "diffdock"' not in fuente


def test_no_se_ignora_el_motor_peptidico_anidado():
    with pytest.raises(ValidationError):
        EvaluationSubmitRequest.model_validate({
            "smiles": "CCO",
            "pipeline_config": {"peptide_docking_engine": "esmfold"},
        })


@pytest.mark.asyncio
async def test_dispatcher_legacy_rechaza_motor_no_publicado_antes_de_crear_corrida():
    from services.docking.queue_handler import _run_full_evaluation_async

    with pytest.raises(ValueError, match="motor"):
        await _run_full_evaluation_async(
            task_id="eng-a16", smiles="CCO", target_pdb_id="7E2Y",
            peptide_docking_engine="esmfold-pro",
        )
