from contextlib import asynccontextmanager
from copy import deepcopy
import uuid

import pytest
from fastapi import HTTPException
from services import batch_persistence as store
from tests import test_sqlite_roundtrip as sqlite_fixtures

engine = sqlite_fixtures.engine
session_factory = sqlite_fixtures.session_factory


@pytest.fixture
def isolated_store(monkeypatch, session_factory):
    @asynccontextmanager
    async def session():
        async with session_factory() as db:
            yield db
    monkeypatch.setattr(store, "get_db_session", session)


def record():
    return {"id": str(uuid.uuid4()), "owner_id": "owner", "status": "running",
            "configuration": {"molecules": [{"smiles": "CCO"}], "targets": ["7E2Y"]},
            "completed": 1, "total": 2, "results": [{"task_id": "first", "affinity_kcal": -7.5}]}


@pytest.mark.asyncio
async def test_restart_preserves_configuration_partial_results_and_owner(isolated_store):
    batch = record()
    await store.save_batch(batch, create=True)
    restored = await store.load_inactive_batch(batch["id"])
    assert restored["status"] == "interrupted"
    for field in ["configuration", "results", "owner_id", "completed"]:
        assert restored[field] == batch[field]
    assert await store.load_inactive_batch(batch["id"]) == restored
    from api.routers.batch import _require_own_batch
    with pytest.raises(HTTPException) as exc:
        _require_own_batch(restored, None)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_completed_survives_and_wrong_owner_cannot_checkpoint(isolated_store):
    batch = record()
    batch["status"] = "completed"
    await store.save_batch(batch, create=True)
    wrong = deepcopy(batch)
    wrong.update(owner_id="someone-else", results=[])
    with pytest.raises(RuntimeError):
        await store.save_batch(wrong)
    assert await store.load_inactive_batch(batch["id"]) == batch


@pytest.mark.asyncio
async def test_duplicate_acceptance_cannot_replace_evidence(isolated_store):
    from sqlalchemy.exc import IntegrityError
    batch = record()
    batch["status"] = "completed"
    await store.save_batch(batch, create=True)
    replacement = deepcopy(batch)
    replacement["results"] = []
    with pytest.raises(IntegrityError):
        await store.save_batch(replacement, create=True)
    assert await store.load_inactive_batch(batch["id"]) == batch


@pytest.mark.asyncio
async def test_checkpoint_failure_prevents_launch(monkeypatch):
    import io
    from unittest.mock import AsyncMock
    from fastapi import UploadFile
    from api.routers import batch
    launch = AsyncMock()
    monkeypatch.setattr(batch, "_process_batch", launch)
    monkeypatch.setattr(batch, "_persist_batch", AsyncMock(side_effect=OSError("disk full")))
    upload = UploadFile(filename="molecules.csv", file=io.BytesIO(
        b"smiles,name\nCC(=O)Oc1ccccc1C(=O)O,aspirin\n"))
    with pytest.raises(OSError, match="disk full"):
        await batch.submit_batch(upload, "7E2Y", 1, False, None, None)
    launch.assert_not_awaited()


@pytest.mark.asyncio
async def test_supervisor_records_failure_with_partial_evidence(monkeypatch, isolated_store):
    from unittest.mock import AsyncMock
    from api.routers import batch
    original = record()
    await store.save_batch(original, create=True)
    batch._batches[original["id"]] = deepcopy(original)
    monkeypatch.setattr(batch, "_process_batch", AsyncMock(side_effect=RuntimeError("native worker failed")))
    try:
        await batch._supervise_batch(original["id"], [], [], 1, False, False)
        restored = await store.load_inactive_batch(original["id"])
        assert restored["status"] == "failed"
        assert restored["results"] == original["results"]
        assert "native worker failed" in restored["error"]
    finally:
        batch._batches.pop(original["id"], None)


@pytest.mark.asyncio
async def test_batch_reads_frozen_run_after_projection_changes(session_factory):
    from tests.test_sqlite_roundtrip import _seed_user_target_molecule
    from core.models import EvaluationResultORM
    from db.repository import Repository
    async with session_factory() as db:
        _, _, molecule = await _seed_user_target_molecule(db)
        db.add(EvaluationResultORM(molecule_id=molecule.id, task_id="first", affinity_kcal=-8.0))
        await db.flush()
        repo = Repository(db)
        await repo.snapshot_evaluation_run(molecule.id, "first")
        projection = await repo.get_evaluation_result(molecule.id)
        projection.task_id = "next"
        projection.affinity_kcal = -99
        await db.commit()
        result = await store.read_run_result(repo, molecule.id, "first")
        assert result.affinity_kcal == -8.0
        assert result.task_id == "first"
        assert await store.read_run_result(repo, molecule.id, "unknown") is None
