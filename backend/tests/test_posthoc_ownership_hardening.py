import pytest
from core.models import EvaluationResultORM
from db.repository import Repository
from tests.test_sqlite_roundtrip import _seed_user_target_molecule
from tests import test_sqlite_roundtrip as sqlite_fixtures

engine = sqlite_fixtures.engine
session_factory = sqlite_fixtures.session_factory


@pytest.mark.asyncio
async def test_stale_loaded_projection_cannot_overwrite_new_run(session_factory):
    async with session_factory() as db:
        _, _, molecule = await _seed_user_target_molecule(db)
        db.add(EvaluationResultORM(molecule_id=molecule.id, task_id="old", mmgbsa_score=-10))
        await db.commit()
        molecule_id = molecule.id
    async with session_factory() as stale:
        old = await Repository(stale).get_evaluation_result(molecule_id)
        assert old.task_id == "old"
        # Finish the read transaction but deliberately keep the old ORM instance.
        await stale.commit()
        async with session_factory() as fresh:
            result = await Repository(fresh).get_evaluation_result(molecule_id)
            result.task_id = "new"
            result.mmgbsa_score = -20
            await fresh.commit()
        assert not await Repository(stale).update_evaluation_for_task(
            molecule_id, old.task_id, mmgbsa_score=-999)
        await stale.commit()
    async with session_factory() as db:
        result = await Repository(db).get_evaluation_result(molecule_id)
        assert result.task_id == "new"
        assert result.mmgbsa_score == -20
        assert await Repository(db).update_evaluation_for_task(molecule_id, "new", mmgbsa_score=-21)
        await db.commit()
    async with session_factory() as db:
        assert (await Repository(db).get_evaluation_result(molecule_id)).mmgbsa_score == -21


@pytest.mark.asyncio
async def test_new_projection_preserves_all_old_fields_and_rollback(session_factory):
    from services.docking.projection_lifecycle import begin_evaluation_projection
    from core.models import EvaluationRunORM
    from sqlalchemy import select
    async with session_factory() as db:
        _, _, molecule = await _seed_user_target_molecule(db)
        previous = EvaluationResultORM(molecule_id=molecule.id, task_id="old",
            mmgbsa_score=-12, quantum_score=-3, ai_report="old report",
            structural_evidence={"preserve": True}, blockchain_tx_id="old seal",
            poses_file_path="poses/old.sdf", selectivity_ran=True)
        db.add(previous)
        await db.commit()
        molecule_id, result_id = molecule.id, previous.id
    # Failure after archiving must roll back BOTH the archive and projection.
    async with session_factory() as db:
        await begin_evaluation_projection(Repository(db), molecule_id, "new")
        await db.rollback()
    async with session_factory() as db:
        old = await Repository(db).get_evaluation_result(molecule_id)
        assert old.task_id == "old" and old.mmgbsa_score == -12
        assert (await db.execute(select(EvaluationRunORM))).scalars().all() == []
        await begin_evaluation_projection(Repository(db), molecule_id, "new")
        await db.commit()
    async with session_factory() as db:
        new = await Repository(db).get_evaluation_result(molecule_id)
        assert new.id == result_id and new.task_id == "new"
        for name in ["mmgbsa_score", "quantum_score", "ai_report", "structural_evidence",
                     "blockchain_tx_id", "poses_file_path"]:
            assert getattr(new, name) is None
        assert new.selectivity_ran is False
        archive = (await db.execute(select(EvaluationRunORM))).scalar_one()
        snapshot = archive.snapshot_json
        assert snapshot["task_id"] == "old"
        assert snapshot["mmgbsa_score"] == -12
        assert snapshot["blockchain_tx_id"] == "old seal"
        assert snapshot["structural_evidence"] == {"preserve": True}
        assert snapshot["poses_file_path"] == "poses/old.sdf"
        new.mmgbsa_score = -14
        await db.commit()
        # Re-entry into the same run must preserve already completed stages.
        await begin_evaluation_projection(Repository(db), molecule_id, "new")
        await db.commit()
        assert (await Repository(db).get_evaluation_result(molecule_id)).mmgbsa_score == -14


@pytest.mark.asyncio
@pytest.mark.parametrize("initial", [None, []])
async def test_selectivity_merge_preserves_other_writer_and_rejects_new_run(session_factory, initial):
    async with session_factory() as db:
        _, _, molecule = await _seed_user_target_molecule(db)
        molecule_id = molecule.id
        db.add(EvaluationResultORM(molecule_id=molecule_id, task_id="run", anti_target_results=initial))
        await db.commit()
    async with session_factory() as stale:
        cached = await Repository(stale).get_evaluation_result(molecule_id)
        await stale.commit()
        async with session_factory() as fresh:
            assert await Repository(fresh).merge_selectivity_for_task(
                molecule_id, "run", [{"pdb_id": "AAAA", "affinity": -8}])
            await fresh.commit()
        # The ORM cache still contains the initial value. Merging must read SQL.
        assert cached.anti_target_results == initial
        merged = await Repository(stale).merge_selectivity_for_task(
            molecule_id, "run", [{"pdb_id": "BBBB", "affinity": -7}])
        assert {x["pdb_id"] for x in merged} == {"AAAA", "BBBB"}
        await stale.commit()
        async with session_factory() as fresh:
            current = await Repository(fresh).get_evaluation_result(molecule_id)
            current.task_id = "next"
            current.anti_target_results = []
            await fresh.commit()
        assert await Repository(stale).merge_selectivity_for_task(
            molecule_id, "run", [{"pdb_id": "CCCC"}]) is None
        await stale.commit()
    async with session_factory() as db:
        row = await Repository(db).get_evaluation_result(molecule_id)
        assert row.task_id == "next" and row.anti_target_results == []


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [0.0, -7.25])
async def test_selectivity_real_reference_including_zero(value):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from api.routers.pro_features import _selectivity_reference
    repository = SimpleNamespace(get_evaluation_run=AsyncMock())
    assert await _selectivity_reference(repository, SimpleNamespace(affinity_kcal=value)) == value
    repository.get_evaluation_run.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("status,value,valid", [
    ("SUCCESS", -8.2, True), ("FAILURE", -8.2, False),
    ("SUCCESS", None, False), ("SUCCESS", float("nan"), False),
    ("SUCCESS", float("inf"), False), ("SUCCESS", True, False),
])
async def test_selectivity_recovers_only_complete_same_run(status, value, valid):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from api.routers.pro_features import _selectivity_reference
    repository = SimpleNamespace(get_evaluation_run=AsyncMock(return_value=SimpleNamespace(
        status=status, snapshot_json={"affinity_kcal": value})))
    evaluation = SimpleNamespace(affinity_kcal=None, task_id="source", molecule_id="molecule")
    if valid:
        assert await _selectivity_reference(repository, evaluation) == value
    else:
        with pytest.raises(HTTPException) as exc:
            await _selectivity_reference(repository, evaluation)
        assert exc.value.status_code == 422
    repository.get_evaluation_run.assert_awaited_once_with("source", "molecule")


@pytest.mark.parametrize("affinity", ["None", "nan", "inf", "-inf", "invalid"])
def test_selectivity_child_rejects_missing_measure_before_any_work(monkeypatch, capsys, affinity):
    import json
    import sys
    from services.docking import selectivity_subprocess as child
    monkeypatch.setattr(sys, "argv", ["worker", "not-even-a-uuid", "CCO", "hash", "target", affinity, "2"])
    assert child.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "not_evaluated"
    assert "afinidad" in result["error"]
