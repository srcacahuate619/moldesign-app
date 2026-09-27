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


def test_duplicado_con_etiqueta_en_segunda_fila_no_la_pierde():
    from services.cohort.evidence import build_labeled_metrics
    from services.cohort import execution as ex
    def row(i, canonical, label, affinity):
        return {
            "source_row_index": i,
            "source_name": str(i),
            "canonical_smiles": canonical,
            "status": ex.ROW_COMPLETED,
            "control_role": "none",
            "active_label": label,
            "observed_vina_affinity_kcal_mol": affinity,
        }
    rows = [row(0, "same", None, -10.0), row(1, "same", True, -10.0)]
    rows.extend(row(i, "mol" + str(i), i % 2 == 0, float(-10 + i)) for i in range(2, 12))
    metrics = build_labeled_metrics(rows, run_status=ex.RUN_COMPLETED)
    assert metrics["status"] == "evaluated"
    assert metrics["n_labeled_molecules"] == 11
    assert metrics["n_positive"] == 6
    assert metrics["coverage"] == 1.0

