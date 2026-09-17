from types import SimpleNamespace

import pytest

from core.models import EvaluationRequestORM
from tests import test_sqlite_roundtrip as sqlite_fixtures

engine = sqlite_fixtures.engine
session_factory = sqlite_fixtures.session_factory


@pytest.mark.asyncio
async def test_request_is_committed_before_dispatch(session_factory, monkeypatch):
    import services.docking.queue_handler as qh
    captured = {}
    def enqueue(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=kwargs["task_id"])
    monkeypatch.setattr(qh, "_submit_evaluation_desktop", enqueue)
    config = {"smiles": "CCO", "target_pdb_id": "7E2Y", "user_id": "owner",
              "pipeline_config": {"pro_mmgbsa": True}, "grid_center": [1, 2, 3]}
    async with session_factory() as db:
        task = await qh.submit_recorded_evaluation(db=db, client_ip="127.0.0.1", **config)
        await db.rollback()  # acceptance must already have committed
    async with session_factory() as db:
        record = await db.get(EvaluationRequestORM, task.id)
        assert record.configuration_json == config
        assert record.owner_id == "owner" and record.client_ip == "127.0.0.1"
        assert record.status == "PENDING"
        assert captured["task_id"] == task.id


@pytest.mark.asyncio
async def test_failed_commit_never_dispatches(monkeypatch):
    import services.docking.queue_handler as qh
    from unittest.mock import AsyncMock, Mock
    db = SimpleNamespace(add=Mock())
    enqueue = Mock()
    monkeypatch.setattr(qh, "_submit_evaluation_desktop", enqueue)
    monkeypatch.setattr(qh, "commit_with_retry", AsyncMock(side_effect=OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        await qh.submit_recorded_evaluation(db=db, smiles="CCO", target_pdb_id="7E2Y")
    enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_failure_leaves_durable_error(session_factory, monkeypatch):
    from sqlalchemy import select
    import services.docking.queue_handler as qh
    def fail(**kwargs):
        raise RuntimeError("dispatcher unavailable")
    monkeypatch.setattr(qh, "_submit_evaluation_desktop", fail)
    async with session_factory() as db:
        with pytest.raises(RuntimeError, match="dispatcher unavailable"):
            await qh.submit_recorded_evaluation(db=db, smiles="CCO", target_pdb_id="7E2Y")
    async with session_factory() as db:
        record = (await db.execute(select(EvaluationRequestORM))).scalar_one()
        assert record.status == "FAILURE"
        assert "dispatcher unavailable" in record.error_message


@pytest.mark.asyncio
async def test_interrupted_request_recovers_without_memory_or_result(session_factory, monkeypatch):
    from contextlib import asynccontextmanager
    import threading
    from unittest.mock import AsyncMock
    from services.docking import desktop_job_status as status_module
    async with session_factory() as db:
        db.add(EvaluationRequestORM(task_id="interrupted", owner_id="demo",
               configuration_json={"smiles": "CCO"}, status="PENDING"))
        await db.commit()
    @asynccontextmanager
    async def sessions():
        async with session_factory() as db:
            yield db
    monkeypatch.setattr(status_module, "get_db_session", sessions)
    cache = SimpleNamespace(get=AsyncMock(return_value=None), set=AsyncMock())
    result = await status_module.get_desktop_job_status("interrupted", jobs={}, lock=threading.Lock(), cache=cache)
    assert result.status == "FAILURE"
    assert "interrumpió" in result.error
    async with session_factory() as db:
        request = await db.get(EvaluationRequestORM, "interrupted")
        assert request.status == "FAILURE"
        assert request.configuration_json == {"smiles": "CCO"}


@pytest.mark.asyncio
async def test_durable_request_preserves_owner_after_cache_loss(session_factory, monkeypatch):
    import uuid
    from fastapi import HTTPException
    from api.routers.evaluation import _autorizar_corrida
    from utils.cache import cache
    from unittest.mock import AsyncMock
    owner = uuid.uuid4()
    monkeypatch.setattr(cache, "get", AsyncMock(return_value=None))
    async with session_factory() as db:
        db.add(EvaluationRequestORM(task_id="owned", owner_id=str(owner),
               configuration_json={"smiles": "CCO"}, status="PENDING"))
        await db.commit()
        await _autorizar_corrida("owned", current_user=SimpleNamespace(id=owner), db=db, client_ip=None)
        with pytest.raises(HTTPException) as error:
            await _autorizar_corrida("owned", current_user=SimpleNamespace(id=uuid.uuid4()), db=db, client_ip=None)
        assert error.value.status_code == 403
