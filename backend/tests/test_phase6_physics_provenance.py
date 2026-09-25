"""PHYS-005: el legacy declara plataforma y el contrato no llama ΔG a ΔE."""
from types import SimpleNamespace


def test_sin_pose_declara_plataforma_real_y_abstencion(monkeypatch):
    from services.chemistry import molchamb_v2 as engine

    monkeypatch.setattr(engine, "_get_best_platform",
                        lambda: SimpleNamespace(getName=lambda: "CPU"))
    monkeypatch.setattr(engine, "prepare_protein", lambda *_: None)
    result = engine.compute_mmgbsa_from_pose(
        "receptor.pdb", "CCO", [], ligand_sdf_path=None,
    )
    assert result["platform"] == "CPU"
    assert result["status"] == "not_evaluated"
    assert result["mmgbsa"] is None


def test_contrato_openapi_llama_al_numero_por_su_nombre():
    from core.models import EvaluationResultRead
    schema = EvaluationResultRead.model_json_schema()
    description = schema["properties"]["mmgbsa_score"]["description"]
    assert "GBn2+ACE" in description
    assert "no es ΔG" in description
    assert "Siempre null" in description
