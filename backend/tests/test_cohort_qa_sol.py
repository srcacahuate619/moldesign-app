import pytest
from pydantic import ValidationError
from services.cohort.schemas import CohortStudy

def test_cohorte_rechaza_motor_que_inventario_declara_no_habilitado():
    study = {
        "schema_version": 1, "name": "QA Sol", "receptor": {"pdb_id": "1XP0", "chain": "A"},
        "config": {"docking_engine": "qvina2", "exhaustiveness": 8, "num_poses": 5, "seed": 0},
    }
    with pytest.raises(ValidationError, match="docking_engine"):
        CohortStudy.model_validate(study)


def test_ef_no_publica_una_fraccion_menor_que_una_molecula():
    from services.cohort.evidence import build_labeled_metrics
    from services.cohort import execution as ex
    rows = [
        {
            "source_row_index": i,
            "source_name": str(i),
            "canonical_smiles": "m" + str(i),
            "status": ex.ROW_COMPLETED,
            "control_role": "none",
            "active_label": i < 3,
            "observed_vina_affinity_kcal_mol": float(-10 + i),
        }
        for i in range(10)
    ]
    metrics = build_labeled_metrics(rows, run_status=ex.RUN_COMPLETED)
    assert metrics["roc_auc"] == 1.0
    assert [(e["fraction"], e["n_selected"]) for e in metrics["enrichment_factors"]] == [(0.10, 1)]

