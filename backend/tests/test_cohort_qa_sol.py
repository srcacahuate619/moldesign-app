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

