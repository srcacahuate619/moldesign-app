"""Regresiones de configuración opcional en la entrada real del pipeline."""

import inspect

from api.routers.evaluation import EvaluationSubmitRequest, PipelineConfigRequest
import services.docking.queue_handler as queue_handler
from services.pipeline.registry import STAGE_REGISTRY, admet_requested
from services.pipeline.runner import (
    _int_config_or_default,
    _is_explicit_peptide_engine,
    _protocol_engine,
)


def test_pydantic_none_for_optional_mmgbsa_steps_uses_runtime_default():
    config = PipelineConfigRequest().model_dump()

    assert config["pro_mmgbsa_steps"] is None
    assert _int_config_or_default(config, "pro_mmgbsa_steps", 1000) == 1000


def test_explicit_mmgbsa_steps_is_preserved():
    config = PipelineConfigRequest(pro_mmgbsa_steps=2500).model_dump()

    assert _int_config_or_default(config, "pro_mmgbsa_steps", 1000) == 2500


def test_ordinary_submit_does_not_select_peptide_route_implicitly():
    request = EvaluationSubmitRequest(smiles="CC(=O)Oc1ccccc1C(=O)O")

    assert request.peptide_docking_engine is None
    assert _is_explicit_peptide_engine(request.peptide_docking_engine) is False


def test_explicit_peptide_engine_selects_peptide_route():
    request = EvaluationSubmitRequest(
        smiles="NCC(=O)NCC(=O)NCC(=O)O",
        peptide_docking_engine="esmfold",
    )

    assert _is_explicit_peptide_engine(request.peptide_docking_engine) is True


def test_protocol_separates_engine_name_from_vina_version():
    assert _protocol_engine(None, {}, "vina") == "vina"
    assert _protocol_engine(None, {"engine": "qvina2"}, "vina") == "qvina2"
    assert _protocol_engine("esmfold", {"engine": "vina"}, "vina") == "esmfold"


def test_experimental_admet_is_opt_in_in_both_pipeline_entry_points():
    """Omitir la opción nunca debe cargar el modelo experimental por sorpresa."""
    assert STAGE_REGISTRY["properties"].params["run_admet_ai"] is False
    assert admet_requested(None) is False
    assert admet_requested({}) is False
    assert admet_requested({"run_admet_ai": False}) is False
    assert admet_requested({"run_admet_ai": "true"}) is False
    assert admet_requested({"run_admet_ai": True}) is True
    signature = inspect.signature(queue_handler._run_full_evaluation_async)
    assert signature.parameters["run_admet_ai"].default is False
