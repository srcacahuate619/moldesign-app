import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from urllib.error import URLError

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_alphafold_network_failure_is_503_without_local_details(monkeypatch):
    from api.routers import targets
    from services.alphafold import client

    async def unavailable(_id):
        raise URLError("private/path/secret")

    monkeypatch.setattr(client, "lookup_uniprot", unavailable)
    with pytest.raises(HTTPException) as error:
        await targets.alphafold_lookup("P08908", current_user=None)
    assert error.value.status_code == 503
    assert "private/path" not in str(error.value.detail)


@pytest.mark.asyncio
async def test_community_download_network_failure_is_503(monkeypatch):
    from api.routers import targets
    from services.targets import ingestion_manager

    async def unavailable(**_kwargs):
        raise RuntimeError("private/path/secret")

    monkeypatch.setattr(ingestion_manager, "ingest_new_target", unavailable)
    with pytest.raises(HTTPException) as error:
        await targets.download_community_target(
            "7E2Y", db=None, current_user=SimpleNamespace(id=uuid.uuid4())
        )
    assert error.value.status_code == 503
    assert "private/path" not in str(error.value.detail)


@pytest.mark.asyncio
async def test_batch_records_each_item_before_waiting(monkeypatch):
    from api.routers import batch
    from core import database
    from services.docking import queue_handler
    from utils.cache import cache

    actions = []
    task_id = str(uuid.uuid4())
    molecule_id = str(uuid.uuid4())

    @asynccontextmanager
    async def fake_db():
        actions.append("db")
        yield object()

    async def submit(**kwargs):
        assert kwargs["user_id"] == "alice"
        actions.append("record")
        return SimpleNamespace(id=task_id)

    async def wait(identifier):
        assert identifier == task_id
        actions.append("wait")
        return SimpleNamespace(status="SUCCESS", result=SimpleNamespace(molecule_id=molecule_id))

    async def set_cache(*_args, **_kwargs):
        actions.append("owner")

    monkeypatch.setattr(database, "get_db_session", fake_db)
    monkeypatch.setattr(queue_handler, "submit_recorded_evaluation", submit)
    monkeypatch.setattr(queue_handler, "await_recorded_evaluation", wait)
    monkeypatch.setattr(cache, "set", set_cache)
    assert await batch._evaluate_one_recorded("CCO", "7E2Y", "ethanol", "alice") == (
        task_id, molecule_id
    )
    assert actions == ["db", "record", "owner", "wait"]


def test_batch_no_longer_advertises_worker_count():
    from api.main import app

    params = app.openapi()["paths"]["/evaluation/batch"]["post"]["parameters"]
    assert all(item["name"] != "num_workers" for item in params)

def test_alphafold_routes_have_declared_network_destination():
    from api.main import app
    from services.ai.red import DESTINOS

    routes = {route.path for route in app.routes}
    assert {
        "/targets/alphafold/lookup/{uniprot_id}",
        "/targets/alphafold/search",
    } <= routes
    destinations = {(item.servicio, item.host) for item in DESTINOS}
    assert ("alphafold", "alphafold.ebi.ac.uk") in destinations

@pytest.mark.asyncio
async def test_foreign_blockchain_molecule_is_indistinguishable_from_missing():
    from api.routers import blockchain

    alice = uuid.uuid4()
    bob = SimpleNamespace(id=uuid.uuid4())
    molecule = SimpleNamespace(user_id=alice)
    db = SimpleNamespace(execute=None)

    class FakeDB:
        async def execute(self, _statement):
            return SimpleNamespace(scalar_one_or_none=lambda: molecule)

    with pytest.raises(HTTPException) as prepare:
        await blockchain.prepare_certification(
            molecule_id=uuid.uuid4(), user_wallet="invalid",
            current_user=bob, db=FakeDB(),
        )
    assert prepare.value.status_code == 404

    with pytest.raises(HTTPException) as link:
        await blockchain.link_certification(
            request=blockchain.LinkRequest(
                molecule_id=uuid.uuid4(), signature="irrelevant"
            ),
            current_user=bob, db=FakeDB(),
        )
    assert link.value.status_code == 404


@pytest.mark.asyncio
async def test_rcsb_download_error_never_exposes_cache_path(monkeypatch, tmp_path):
    import httpx
    from utils import file_handlers
    from services.ai import red

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, _url):
            raise httpx.ConnectError("offline")

    monkeypatch.setenv("MOLDESIGN_PDB_CACHE", str(tmp_path / "private" / "cache"))
    monkeypatch.setattr(red, "exigir_permiso", lambda *_args: None)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: Client())
    with pytest.raises(RuntimeError) as error:
        await file_handlers.download_pdb_from_rcsb("7E2Y")
    assert str(tmp_path) not in str(error.value)

@pytest.mark.asyncio
async def test_sync_sse_uses_recorded_result_snapshot(monkeypatch):
    from api.routers import evaluation
    from services.docking import queue_handler
    from utils.cache import cache
    from starlette.requests import Request

    recorded = []

    async def no_target(*_args, **_kwargs):
        return None

    async def gates(**_kwargs):
        return None

    async def submit(**kwargs):
        recorded.append(kwargs)
        return SimpleNamespace(id="phase7-task")

    fields = {
        name: None for name in (
            "affinity_kcal", "total_score", "molecular_weight", "log_p",
            "tpsa", "lipinski_pass", "veber_pass", "ghose_pass", "egan_pass",
            "muegge_pass", "muegge_score", "fsp3", "is_pains",
            "blood_viability_score", "qed", "sa_score",
        )
    }
    fields["docking_poses"] = []
    fields["molecule_id"] = uuid.uuid4()

    async def wait(task_id):
        assert task_id == "phase7-task"
        return SimpleNamespace(status="SUCCESS", result=SimpleNamespace(**fields))

    async def set_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(evaluation, "Repository", lambda _db: object())
    monkeypatch.setattr(evaluation, "get_target_for_user", no_target)
    monkeypatch.setattr(evaluation, "_enforce_submission_gates", gates)
    monkeypatch.setattr(queue_handler, "submit_recorded_evaluation", submit)
    monkeypatch.setattr(queue_handler, "await_recorded_evaluation", wait)
    monkeypatch.setattr(cache, "set", set_cache)

    request = Request({
        "type": "http", "method": "POST", "path": "/evaluation/evaluate",
        "headers": [], "query_string": b"", "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80), "scheme": "http",
    })
    response = await evaluation.evaluate_sync(
        data=evaluation.EvaluationSubmitRequest(smiles="CC(=O)Oc1ccccc1C(=O)O", target_pdb_id="7E2Y"),
        request=request, current_user=None, db=object(),
    )
    events = [chunk async for chunk in response.body_iterator]
    assert recorded and recorded[0]["smiles"] == "CC(=O)Oc1ccccc1C(=O)O"
    assert "type" in events[0] and "start" in events[0]
    assert "done" in events[-1] and "db_saved" in events[-1]
    assert "phase7-task" in events[-1]

@pytest.mark.asyncio
async def test_batch_cancel_stops_active_job_and_skips_remaining_rows(monkeypatch):
    from api.routers import batch
    from services.docking import queue_handler

    batch_id = str(uuid.uuid4())
    active_task = str(uuid.uuid4())
    batch._batches[batch_id] = {
        "id": batch_id, "owner_id": "demo", "status": "running",
        "active_task_id": active_task, "total": 2, "completed": 0,
        "results": [], "failed": 0,
    }
    cancelled = []
    called = []

    async def persist(*_args, **_kwargs):
        return None

    async def unexpected(*_args, **_kwargs):
        called.append(True)

    monkeypatch.setattr(batch, "_persist_batch", persist)
    monkeypatch.setattr(batch, "_evaluate_one_recorded", unexpected)
    monkeypatch.setattr(
        queue_handler, "request_desktop_job_cancellation",
        lambda identifier: cancelled.append(identifier),
    )
    try:
        response = await batch.cancel_batch(batch_id, current_user=None)
        assert response["cancelled"] is True
        assert cancelled == [active_task]
        await batch._process_batch(
            batch_id, [{"name": "first", "smiles": "CCO"}], ["7E2Y"],
            num_workers=1, early_exit=False, has_labels=False,
        )
        assert batch._batches[batch_id]["status"] == "cancelled"
        assert called == []
    finally:
        batch._batches.pop(batch_id, None)
