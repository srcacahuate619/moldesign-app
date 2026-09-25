"""PROV-002 / PHYS-009: ninguna solicitud puede activar la etapa destructiva."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.routers.evaluation import PipelineConfigRequest
from services.pipeline.runner import run_pipeline


@pytest.mark.parametrize("campo", ["enabled_stages", "stage_order", "stage_params"])
def test_api_rechaza_openmm_en_cualquier_ruta_de_configuracion(campo):
    valores = {"enabled_stages": ["openmm"]} if campo == "enabled_stages" else (
        {"stage_order": ["openmm"]} if campo == "stage_order" else {"stage_params": {"openmm": {}}}
    )
    with pytest.raises(ValidationError, match="retirada"):
        PipelineConfigRequest(**valores)


@pytest.mark.asyncio
async def test_runner_rechaza_openmm_antes_de_tocar_archivos():
    with pytest.raises(ValueError, match="retirada"):
        await run_pipeline(
            task_id="audit-refinement",
            smiles="CCO",
            target_pdb_id="1CBS",
            enabled_stages=["openmm"],
        )
