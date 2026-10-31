"""La huella identifica lo que se ejecuta, también para campos raíz de la API."""

import json

import pytest

from api.routers import evaluation
from services.docking.preflight import canonical_input_document


def _documento(preparado):
    return canonical_input_document(
        smiles_for_hash="CCO", target_pdb_id="USR_ABC123", chain="A",
        grid_center=(1, 2, 3), grid_size=(20, 20, 20), custom_hotspots=[],
        docking_engine="vina", exhaustiveness=8, num_poses=9, seed=42,
        source_sha256=None, prepared_sha256=preparado,
    )


def test_huella_incluye_pdbqt_que_el_usuario_subio():
    primero = "sha256:" + "a" * 64
    segundo = "sha256:" + "b" * 64
    assert json.loads(_documento(primero))["prepared_sha256"] == primero
    assert _documento(primero) != _documento(segundo)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("campo", "valor", "etapa"),
    [("ph", 6.5, "conformer"), ("peptide_docking_engine", "esmfold", None)],
)
async def test_preflight_de_submit_incluye_campos_raiz(monkeypatch, campo, valor, etapa):
    from core.config import get_settings

    capturas = []

    async def preflight(*, data, **_kwargs):
        capturas.append(data.pipeline_config)
        return {}

    monkeypatch.setattr(evaluation, "evaluation_preflight", preflight)
    request = evaluation.EvaluationSubmitRequest(smiles="CCO", **{campo: valor})
    await evaluation.comprobar_preparacion(data=request, canonical_smiles="CCO", db=None, current_user=None)
    config = capturas[0]
    assert config is not None
    # Cuando no se envía pipeline_config, el runner construye estas mismas
    # etapas y parámetros por defecto antes de aplicar los campos raíz.
    assert config.stage_params["properties"] == {"run_admet_ai": False}
    assert config.stage_params["docking"] == {
        "exhaustiveness": get_settings().vina_exhaustiveness,
        "num_poses": get_settings().vina_num_poses,
    }
    assert config.stage_params["xgb"] == {"run_gnn": True}
    if etapa:
        assert config.stage_params[etapa][campo] == valor
    else:
        assert config.peptide_docking_engine == valor


@pytest.mark.asyncio
async def test_preflight_publico_y_submit_con_raiz_tienen_la_misma_huella(monkeypatch):
    from core.config import get_settings
    from services.docking import preflight, preparer
    from services.docking.protocolo import configuracion_pipeline_predeterminada

    async def sin_receptor(*_args, **_kwargs):
        return None

    monkeypatch.setattr(evaluation, "Repository", lambda _db: None)
    monkeypatch.setattr(evaluation, "get_target_for_user", sin_receptor)
    monkeypatch.setattr(preparer, "residuos_con_plantilla", lambda: {})
    monkeypatch.setattr(preflight, "_source_pdb_path", lambda _pdb_id: None)
    monkeypatch.setattr(preflight, "_prepared_pdbqt_path", lambda _pdb_id, recipe_hash=None: None)

    config = configuracion_pipeline_predeterminada(get_settings())
    config.pop("execution_profile")
    config["stage_params"]["conformer"] = {"ph": 6.5}
    config["peptide_docking_engine"] = "esmfold"
    solicitud = evaluation.PreflightRequest(smiles="CCO", target_pdb_id="1ABC", pipeline_config=config,
                                            exhaustiveness=get_settings().vina_exhaustiveness,
                                            num_poses=get_settings().vina_num_poses)
    publicado = await evaluation.evaluation_preflight(data=solicitud, db=None, current_user=None)
    submit = evaluation.EvaluationSubmitRequest(smiles="CCO", target_pdb_id="1ABC", ph=6.5,
                                                 peptide_docking_engine="esmfold")
    comprobado = await evaluation.comprobar_preparacion(data=submit, canonical_smiles="CCO", db=None, current_user=None)
    assert publicado["input_fingerprint"] == comprobado["input_fingerprint"]
    cambiado = submit.model_copy(update={"ph": 7.4})
    otro = await evaluation.comprobar_preparacion(data=cambiado, canonical_smiles="CCO", db=None, current_user=None)
    assert otro["input_fingerprint"] != publicado["input_fingerprint"]
