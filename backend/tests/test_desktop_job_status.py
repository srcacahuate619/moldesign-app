"""Contratos unitarios del servicio de estado del dispatcher desktop."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from core.models import EvaluationResultRead
from services.docking import desktop_job_status as status_service
from services.docking.desktop_job_status import get_desktop_job_status
from utils.cache import LocalRuntimeStore


class _SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def _live_success_job(molecule_id: str | None) -> dict:
    result = {"total_score": 88.0}
    if molecule_id is not None:
        result["molecule_id"] = molecule_id
    return {
        "status": "SUCCESS",
        "progress": 100,
        "result": result,
        "error": None,
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
    }


def _serialized_result(molecule_id: str) -> EvaluationResultRead:
    """Instancia minima: estas pruebas cubren el lifecycle, no el schema completo."""
    return EvaluationResultRead.model_construct(
        id=uuid4(),
        molecule_id=molecule_id,
    )


class _SequencedRepository:
    def __init__(self, outcomes: list[object]):
        self._outcomes = iter(outcomes)

    async def get_evaluation_result(self, _molecule_id):
        outcome = next(self._outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def get_evaluation_run(self, _task_id, _molecule_id=None):
        return None


def _install_repository(monkeypatch, repository: _SequencedRepository) -> None:
    monkeypatch.setattr(status_service, "get_db_session", lambda: _SessionContext())
    monkeypatch.setattr(status_service, "Repository", lambda _db: repository)


@pytest.mark.asyncio
async def test_live_terminal_job_is_serialized_and_cached_from_injected_state():
    """El servicio usa el registro compartido, sin crear estado propio."""
    cache = LocalRuntimeStore()
    jobs = {
        "terminal-live": {
            "status": "FAILURE",
            "progress": 100,
            "error": "Cancelado por el usuario",
            "started_at": "not-an-iso-date",
            "finished_at": None,
        }
    }

    status = await get_desktop_job_status(
        "terminal-live",
        jobs=jobs,
        lock=threading.Lock(),
        cache=cache,
    )

    assert status.status == "FAILURE"
    assert status.error == "Cancelado por el usuario"
    assert status.started_at is None
    assert await cache.get("job_status:terminal-live") is not None


@pytest.mark.asyncio
async def test_success_without_result_is_not_reused_as_terminal():
    """SUCCESS sin evidencia no puede quedar congelado en cache."""
    cache = LocalRuntimeStore()
    await cache.set(
        "job_status:cached-success",
        {"task_id": "cached-success", "status": "SUCCESS", "progress": 100},
        ttl=60,
    )

    status = await get_desktop_job_status(
        "cached-success",
        jobs={},
        lock=threading.Lock(),
        cache=cache,
    )

    assert status.status == "FAILURE"
    assert status.progress == 100
    assert status.result is None
    assert "no se encontro un resultado persistido" in (status.error or "")


@pytest.mark.asyncio
async def test_unknown_desktop_job_does_not_remain_pending_forever():
    """Un job perdido tras reiniciar libera el caso con un cierre explícito."""
    status = await get_desktop_job_status(
        "orphaned-after-restart",
        jobs={},
        lock=threading.Lock(),
        cache=LocalRuntimeStore(),
    )

    assert status.status == "FAILURE"
    assert status.progress == 100
    assert "ya no existe en el proceso local" in (status.error or "")


@pytest.mark.asyncio
async def test_live_success_retries_transient_hydration_then_recovers(monkeypatch):
    """Un fallo de lectura aislado no puede convertir exito durable en fallo."""
    molecule_id = str(uuid4())
    serialized = _serialized_result(molecule_id)
    repository = _SequencedRepository([RuntimeError("sqlite busy"), object()])
    _install_repository(monkeypatch, repository)
    monkeypatch.setattr(status_service, "_serialize_evaluation", lambda _row: serialized)
    jobs = {"eventual-success": _live_success_job(molecule_id)}
    lock = threading.Lock()
    cache = LocalRuntimeStore()

    first = await get_desktop_job_status(
        "eventual-success", jobs=jobs, lock=lock, cache=cache
    )

    assert first.status == "STARTED"
    assert first.progress == 99
    assert first.result is None
    assert jobs["eventual-success"]["result_hydration_attempts"] == 1
    assert await cache.get("job_status:eventual-success") is None

    second = await get_desktop_job_status(
        "eventual-success", jobs=jobs, lock=lock, cache=cache
    )

    assert second.status == "SUCCESS"
    assert second.progress == 100
    assert second.result is serialized
    assert "result_hydration_attempts" not in jobs["eventual-success"]
    assert await cache.get("job_status:eventual-success") is not None


@pytest.mark.asyncio
async def test_live_success_retries_while_result_is_not_visible(monkeypatch):
    """Una fila todavia no visible en SQLite sigue siendo estado transitorio."""
    molecule_id = str(uuid4())
    _install_repository(monkeypatch, _SequencedRepository([None]))
    jobs = {"commit-race": _live_success_job(molecule_id)}

    status = await get_desktop_job_status(
        "commit-race",
        jobs=jobs,
        lock=threading.Lock(),
        cache=LocalRuntimeStore(),
    )

    assert status.status == "STARTED"
    assert status.progress == 99
    assert status.result is None


@pytest.mark.asyncio
async def test_live_success_hydration_retries_are_bounded(monkeypatch):
    """Un resultado imposible de hidratar termina sin spinner infinito."""
    molecule_id = str(uuid4())
    attempts = status_service.RESULT_HYDRATION_MAX_ATTEMPTS
    _install_repository(monkeypatch, _SequencedRepository([None] * attempts))
    jobs = {"never-readable": _live_success_job(molecule_id)}
    lock = threading.Lock()
    cache = LocalRuntimeStore()

    statuses = [
        await get_desktop_job_status(
            "never-readable", jobs=jobs, lock=lock, cache=cache
        )
        for _ in range(attempts)
    ]

    assert all(status.status == "STARTED" for status in statuses[:-1])
    assert statuses[-1].status == "FAILURE"
    assert statuses[-1].progress == 100
    assert "persistido" in (statuses[-1].error or "")


@pytest.mark.asyncio
async def test_live_success_without_molecule_id_fails_immediately():
    """SUCCESS sin enlace durable es una violacion permanente del contrato."""
    jobs = {"invalid-success": _live_success_job(None)}

    status = await get_desktop_job_status(
        "invalid-success",
        jobs=jobs,
        lock=threading.Lock(),
        cache=LocalRuntimeStore(),
    )

    assert status.status == "FAILURE"
    assert status.progress == 100
    assert "molecule_id" in (status.error or "")
    assert "result_hydration_attempts" not in jobs["invalid-success"]


@pytest.mark.asyncio
async def test_hydration_does_not_resurrect_a_concurrent_terminal_failure(monkeypatch):
    """El estado compartido mas reciente gana sobre el snapshot de lectura."""
    molecule_id = str(uuid4())
    task_id = "cancelled-during-hydration"
    jobs = {task_id: _live_success_job(molecule_id)}
    lock = threading.Lock()
    serialized = _serialized_result(molecule_id)

    class _CancellingRepository:
        async def get_evaluation_run(self, _task_id, _molecule_id=None):
            return None

        async def get_evaluation_result(self, _molecule_id):
            with lock:
                jobs[task_id]["status"] = "FAILURE"
                jobs[task_id]["error"] = "Cancelado por el usuario"
            return object()

    _install_repository(monkeypatch, _CancellingRepository())
    monkeypatch.setattr(status_service, "_serialize_evaluation", lambda _row: serialized)

    status = await get_desktop_job_status(
        task_id,
        jobs=jobs,
        lock=lock,
        cache=LocalRuntimeStore(),
    )

    assert status.status == "FAILURE"
    assert status.result is None
    assert status.error == "Cancelado por el usuario"


@pytest.mark.asyncio
async def test_hydration_error_preserves_a_concurrent_terminal_failure(monkeypatch):
    """La rama de excepcion tampoco puede ocultar una cancelacion concurrente."""
    molecule_id = str(uuid4())
    task_id = "cancelled-while-db-errors"
    jobs = {task_id: _live_success_job(molecule_id)}
    lock = threading.Lock()

    class _FailingAfterCancellationRepository:
        async def get_evaluation_run(self, _task_id, _molecule_id=None):
            return None

        async def get_evaluation_result(self, _molecule_id):
            with lock:
                jobs[task_id]["status"] = "FAILURE"
                jobs[task_id]["error"] = "Cancelado por el usuario"
            raise RuntimeError("sqlite busy")

    _install_repository(monkeypatch, _FailingAfterCancellationRepository())

    status = await get_desktop_job_status(
        task_id,
        jobs=jobs,
        lock=lock,
        cache=LocalRuntimeStore(),
    )

    assert status.status == "FAILURE"
    assert status.result is None
    assert status.error == "Cancelado por el usuario"
