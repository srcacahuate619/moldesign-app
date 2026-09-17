"""Regresiones de aislamiento para status, stream y cancelación de evaluaciones."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.routers import evaluation


class _Cache:
    def __init__(self, values=None):
        self.values = values or {}
        self.requested = []

    async def get(self, key):
        self.requested.append(key)
        return self.values.get(key)


class _Result:
    def __init__(self, molecule):
        self.molecule = molecule

    def scalar_one_or_none(self):
        return self.molecule


class _Database:
    def __init__(self, molecule=None):
        self.molecule = molecule
        self.execute_calls = 0

    async def get(self, _model, _key):
        # Estas pruebas ejercitan el fallback legacy sin solicitud durable.
        return None

    async def execute(self, _statement):
        self.execute_calls += 1
        return _Result(self.molecule)


def _request(ip="10.20.30.40"):
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/evaluation/status/task-1",
            "raw_path": b"/evaluation/status/task-1",
            "query_string": b"",
            "headers": [],
            "client": (ip, 43210),
            "server": ("testserver", 80),
        }
    )


@pytest.fixture
def install_cache(monkeypatch):
    def _install(values=None):
        fake = _Cache(values)
        monkeypatch.setattr("utils.cache.cache", fake)
        return fake

    return _install


def _install_repository(monkeypatch, demo_user_id):
    class _Repository:
        def __init__(self, _db):
            pass

        async def get_or_create_test_user(self):
            return SimpleNamespace(id=demo_user_id)

    monkeypatch.setattr(evaluation, "Repository", _Repository)


@pytest.mark.asyncio
async def test_cached_task_allows_only_its_authenticated_owner(install_cache):
    owner_id = uuid.uuid4()
    install_cache({"task_owner:task-1": str(owner_id)})
    database = _Database()

    await evaluation._authorize_task_access(
        "task-1", _request(), SimpleNamespace(id=owner_id), database
    )

    assert database.execute_calls == 0


@pytest.mark.asyncio
async def test_cached_task_rejects_a_different_account(install_cache):
    install_cache({"task_owner:task-1": str(uuid.uuid4())})

    with pytest.raises(HTTPException) as error:
        await evaluation._authorize_task_access(
            "task-1", _request(), SimpleNamespace(id=uuid.uuid4()), _Database()
        )

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_anonymous_cached_task_is_bound_to_its_origin_ip(install_cache):
    install_cache(
        {
            "task_owner:task-1": "demo",
            "task_owner_ip:task-1": "10.20.30.40",
        }
    )
    await evaluation._authorize_task_access("task-1", _request(), None, _Database())

    with pytest.raises(HTTPException) as error:
        await evaluation._authorize_task_access(
            "task-1", _request("10.20.30.99"), None, _Database()
        )

    assert error.value.status_code == 403
    assert "anónima" in error.value.detail


@pytest.mark.asyncio
async def test_database_fallback_restores_access_for_the_owner(
    monkeypatch, install_cache
):
    owner_id = uuid.uuid4()
    molecule = SimpleNamespace(id=uuid.uuid4(), user_id=owner_id)
    database = _Database(molecule)
    install_cache()
    _install_repository(monkeypatch, uuid.uuid4())

    await evaluation._authorize_task_access(
        "task-persisted", _request(), SimpleNamespace(id=owner_id), database
    )

    assert database.execute_calls == 1


@pytest.mark.asyncio
async def test_database_fallback_rejects_a_foreign_persisted_result(
    monkeypatch, install_cache
):
    molecule = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    install_cache()
    _install_repository(monkeypatch, uuid.uuid4())

    with pytest.raises(HTTPException) as error:
        await evaluation._authorize_task_access(
            "task-persisted",
            _request(),
            SimpleNamespace(id=uuid.uuid4()),
            _Database(molecule),
        )

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_database_fallback_returns_404_for_an_unknown_task(
    monkeypatch, install_cache
):
    install_cache()
    _install_repository(monkeypatch, uuid.uuid4())

    with pytest.raises(HTTPException) as error:
        await evaluation._authorize_task_access(
            "task-missing", _request(), SimpleNamespace(id=uuid.uuid4()), _Database()
        )

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_persisted_anonymous_result_remains_bound_to_its_ip(
    monkeypatch, install_cache
):
    demo_id = uuid.uuid4()
    molecule = SimpleNamespace(id=uuid.uuid4(), user_id=demo_id)
    install_cache({f"mol_owner_ip:{molecule.id}": "10.20.30.40"})
    _install_repository(monkeypatch, demo_id)

    await evaluation._authorize_task_access(
        "task-demo", _request("10.20.30.40"), None, _Database(molecule)
    )

    with pytest.raises(HTTPException) as error:
        await evaluation._authorize_task_access(
            "task-demo", _request("10.20.30.99"), None, _Database(molecule)
        )

    assert error.value.status_code == 403
    assert "anónima" in error.value.detail


@pytest.mark.asyncio
async def test_direct_legacy_invocation_without_request_remains_compatible():
    database = _Database()

    await evaluation._authorize_task_access(
        "task-direct", None, SimpleNamespace(id=uuid.uuid4()), database
    )

    assert database.execute_calls == 0


@pytest.mark.asyncio
async def test_status_authorizes_only_once_per_poll(monkeypatch, install_cache):
    owner_id = uuid.uuid4()
    cache = install_cache({"task_owner:task-1": str(owner_id)})
    database = _Database()

    import services.docking.queue_handler as queue_handler

    async def _status(_task_id):
        return SimpleNamespace(result=None)

    monkeypatch.setattr(queue_handler, "get_job_status", _status)

    await evaluation.get_evaluation_status(
        "task-1", _request(), SimpleNamespace(id=owner_id), database
    )

    assert cache.requested == ["task_owner:task-1", "task_owner_ip:task-1"]
    assert database.execute_calls == 0


@pytest.mark.asyncio
async def test_status_never_reads_the_pose_sdf_during_polling(monkeypatch, install_cache):
    owner_id = uuid.uuid4()
    install_cache({"task_owner:task-1": str(owner_id)})

    import services.docking.queue_handler as queue_handler

    async def _status(_task_id):
        return SimpleNamespace(
            result=SimpleNamespace(
                gnn_attention_svg=None,
                poses_file_path="runs/private/poses.sdf",
            )
        )

    async def _unexpected_read(_object_name):
        raise AssertionError("el polling no debe abrir el SDF")

    monkeypatch.setattr(queue_handler, "get_job_status", _status)
    monkeypatch.setattr("utils.local_storage.read_text", _unexpected_read)

    response = await evaluation.get_evaluation_status(
        "task-1", _request(), SimpleNamespace(id=owner_id), _Database()
    )

    assert response.result.poses_file_path == "runs/private/poses.sdf"
