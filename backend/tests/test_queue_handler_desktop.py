"""
Tests de regresión para el hallazgo de auditoría F-02.

F-02: queue_handler mantenía una rama Celery (run_full_evaluation.apply_async)
y un import lazy de api.celery_app, aunque el runtime desktop usa
_submit_evaluation_desktop() exclusivamente. Antes de eliminar esa rama,
estos tests CONGELAN el contrato del dispatcher local:

- submit_evaluation_job registra el job en _desktop_jobs (estado PENDING
  persistido) y devuelve un _DesktopTask con task_id.
- El job transiciona a SUCCESS y persiste el resultado del pipeline.
- get_job_status consulta el estado del job registrado.
- Cancelar (endpoint real POST /evaluation/cancel) mata únicamente los
  subprocesses MM-GBSA/selectividad de su task y marca el job FAILURE +
  "Cancelado por el usuario" (semántica real del módulo: no se inventa un
  estado CANCELLED).
- Recuperación: jobs stale (más de 24h) se purgan del registro y, tras un
  restart del backend (registro vacío), el estado se recupera desde DB
  (EVALUATED → SUCCESS, FAILED → FAILURE, sin fila → PENDING).
- El contrato público (submit_evaluation_job / get_job_status) conserva su
  firma y la superficie Celery desaparece del módulo.

Los internals científicos pesados (_run_full_evaluation_async) se reemplazan
con fakes inyectados (monkeypatch): nunca se lanza docking real.
"""
from __future__ import annotations

import asyncio
import inspect
import socket
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

import services.docking.queue_handler as qh
from services.docking.desktop_process_registry import (
    clear_registered_processes,
    register_process,
)
from utils.cache import LocalRuntimeStore


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _await_job(task_id: str, timeout_s: float = 15.0) -> dict:
    """Espera a que un job DESKTOP llegue a un estado terminal (SUCCESS/FAILURE)."""
    import time

    deadline = time.monotonic() + timeout_s
    while True:
        with qh._desktop_lock:
            job = dict(qh._desktop_jobs.get(task_id) or {})
        if job.get("status") in ("SUCCESS", "FAILURE"):
            return job
        if time.monotonic() > deadline:
            raise AssertionError(f"job {task_id} no terminó a tiempo: {job}")
        await asyncio.sleep(0.01)


def _fake_eval_result(**kwargs) -> dict:
    """Resultado sintético del pipeline (sin docking real)."""
    return {
        "task_id": kwargs["task_id"],
        "molecule_id": None,
        "smiles_hash": "hash_fake",
        "target_pdb_id": kwargs["target_pdb_id"],
        "total_score": 88.0,
        "best_affinity": -9.4,
        "evaluation_result_id": None,
    }


async def _seed_two_runs_for_same_molecule():
    """Dos corridas inmutables y una proyeccion mutable que apunta a la ultima."""
    from core.database import get_db_session
    from core.models import MoleculeORM, MoleculeStatus, TargetORM, UserORM
    from db.repository import Repository

    owner = UserORM(email=f"owner-{uuid4()}@example.com", username=f"owner-{uuid4()}")
    foreign = UserORM(email=f"foreign-{uuid4()}@example.com", username=f"foreign-{uuid4()}")
    target = TargetORM(
        pdb_id="7E2Y",
        name="Target Test",
        chain="A",
        grid_center_x=0.0,
        grid_center_y=0.0,
        grid_center_z=0.0,
    )
    async with get_db_session() as db:
        db.add_all([owner, foreign, target])
        await db.flush()
        molecule = MoleculeORM(
            smiles="CCO",
            user_id=owner.id,
            target_id=target.id,
            smiles_hash=f"hash-{uuid4()}",
            status=MoleculeStatus.EVALUATED,
        )
        db.add(molecule)
        await db.flush()
        repository = Repository(db)
        await repository.upsert_evaluation_result(
            molecule_id=molecule.id,
            scores={"total_score": 71.0},
            task_id="same-molecule-run-1",
        )
        await repository.snapshot_evaluation_run(molecule.id, "same-molecule-run-1")
        await repository.upsert_evaluation_result(
            molecule_id=molecule.id,
            scores={"total_score": 92.0},
            task_id="same-molecule-run-2",
        )
        await repository.snapshot_evaluation_run(molecule.id, "same-molecule-run-2")
        return molecule.id, owner.id, foreign.id


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_desktop_state(monkeypatch):
    """Estado DESKTOP limpio por test: registro de jobs, procs y cache."""
    with qh._desktop_lock:
        qh._desktop_jobs.clear()
    clear_registered_processes()
    qh.cache._memory.clear()

    # Fake de dependencia: el seed de job_status usa set_json (que no
    # existe en LocalRuntimeStore); lo noopeamos para no ensuciar el cache en
    # memoria con un PENDING que nunca se actualizaría.
    async def _set_json_noop(self, *args, **kwargs):
        return True

    monkeypatch.setattr(LocalRuntimeStore, "set_json", _set_json_noop, raising=False)
    yield
    with qh._desktop_lock:
        qh._desktop_jobs.clear()
    clear_registered_processes()


@pytest_asyncio.fixture
async def isolated_runtime_engine():
    """SQLite efímera; el singleton se limpia incluso si el test falla."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool

    from core.database import reset_engine, set_engine
    from core.models import Base

    await reset_engine()
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    set_engine(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await reset_engine()


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Reemplaza el pipeline científico por un stub determinista."""
    async def _stub_pipeline(**kwargs):
        return _fake_eval_result(**kwargs)

    monkeypatch.setattr(qh, "_run_full_evaluation_async", _stub_pipeline)
    # Aislar la memoria IA (escribe sqlite en ~/MolDesign/data). Import
    # explícito: depender de que otro test haya cargado el submódulo volvía la
    # suite sensible al orden.
    import services.ai.memory_store as memory_store

    monkeypatch.setattr(memory_store, "store_evaluation", lambda **kwargs: None)
    return _stub_pipeline


# ── Contrato de envío ─────────────────────────────────────────────────────────


class TestSubmitEvaluationJob:
    """submit_evaluation_job: registro persistido + ejecución local."""

    @pytest.mark.asyncio
    async def test_submit_registers_job_and_completes_success(self, fake_pipeline):
        """El job queda registrado PENDING y transiciona a SUCCESS local."""
        task = qh.submit_evaluation_job(
            smiles="CCO",
            target_pdb_id="7E2Y",
            molecule_name="etanol",
        )

        # _DesktopTask con task_id es el contrato que consume el router
        assert isinstance(task, qh._DesktopTask)
        assert task.id and isinstance(task.id, str)

        # Registro persistido inmediatamente (el frontend hace polling de esto)
        with qh._desktop_lock:
            assert task.id in qh._desktop_jobs
            assert qh._desktop_jobs[task.id]["status"] == "PENDING"
            assert qh._desktop_jobs[task.id]["started_at"] is not None

        job = await _await_job(task.id)
        assert job["status"] == "SUCCESS"
        assert job["progress"] == 100
        assert job["error"] is None
        assert job["result"]["total_score"] == 88.0
        assert job["finished_at"] is not None

    @pytest.mark.asyncio
    async def test_base_dispatcher_does_not_open_external_connections(
        self, fake_pipeline, monkeypatch
    ):
        """El lifecycle desktop no puede introducir una dependencia cloud.

        El pipeline científico se reemplaza por su contrato determinista: este
        test protege el dispatcher, estado, cache y memoria local. Las
        integraciones explícitas se prueban fuera de este camino base.
        """
        original_create_connection = socket.create_connection

        def only_loopback(address, *args, **kwargs):
            host = address[0]
            if host not in {"127.0.0.1", "::1", "localhost"}:
                raise AssertionError(f"Conexión externa no permitida en desktop base: {host}")
            return original_create_connection(address, *args, **kwargs)

        monkeypatch.setattr(socket, "create_connection", only_loopback)

        task = qh.submit_evaluation_job(smiles="CCO", target_pdb_id="7E2Y")
        job = await _await_job(task.id)

        assert job["status"] == "SUCCESS"

    def test_public_contract_signature_unchanged(self):
        """El router (evaluation.py) depende de esta firma exacta."""
        sig = inspect.signature(qh.submit_evaluation_job)
        assert list(sig.parameters) == [
            "smiles",
            "target_pdb_id",
            "molecule_name",
            "is_control",
            "user_id",
            "grid_center",
            "grid_size",
            "custom_hotspots",
            "peptide_docking_engine",
            "pipeline_config",
        ]
        sig_status = inspect.signature(qh.get_job_status)
        assert list(sig_status.parameters) == ["task_id"]


# ── Consulta de estado ────────────────────────────────────────────────────────


class TestGetJobStatus:
    """get_job_status refleja el estado del job registrado."""

    @pytest.mark.asyncio
    async def test_status_pending_then_success(self, monkeypatch):
        """PENDING mientras corre; SUCCESS con resultado al terminar."""
        release = asyncio.Event()

        async def _gated_pipeline(**kwargs):
            await release.wait()
            return _fake_eval_result(**kwargs)

        monkeypatch.setattr(qh, "_run_full_evaluation_async", _gated_pipeline)
        monkeypatch.setattr(
            "services.ai.memory_store.store_evaluation", lambda **kwargs: None
        )

        task = qh.submit_evaluation_job(smiles="CCO", target_pdb_id="7E2Y")

        status = await qh.get_job_status(task.id)
        assert status.status == "PENDING"
        assert status.task_id == task.id

        release.set()
        await _await_job(task.id)

        status = await qh.get_job_status(task.id)
        # El pipeline sintetico no persiste molecule_id ni resultado. Eso ya no
        # puede publicarse como SUCCESS: para el producto seria una evaluacion
        # imposible de reabrir o informar.
        assert status.status == "FAILURE"
        assert status.progress == 100
        assert "no fue posible recuperar" in (status.error or "")


# ── Cancelación ───────────────────────────────────────────────────────────────


class TestCancelEvaluation:
    """El endpoint real /evaluation/cancel mata procs y marca el job."""

    class _FakeProc:
        def __init__(self):
            self.returncode = None
            self.killed = False

        def kill(self):
            self.killed = True

    @pytest.mark.asyncio
    async def test_cancel_kills_active_procs_and_marks_job(self):
        """Cancelar A no termina los hijos de B ni revierte su aislamiento."""
        from api.routers.evaluation import cancel_evaluation

        p1, p2, p3, other = (
            self._FakeProc(),
            self._FakeProc(),
            self._FakeProc(),
            self._FakeProc(),
        )

        task_id = "cancel-test-1"
        other_task_id = "cancel-test-2"
        register_process(task_id, "mmgbsa", p1)
        register_process(task_id, "mmgbsa", p2)
        register_process(task_id, "selectivity", p3)
        register_process(other_task_id, "mmgbsa", other)
        with qh._desktop_lock:
            qh._desktop_jobs[task_id] = {
                "status": "PENDING",
                "progress": 0,
                "result": None,
                "error": None,
                "started_at": datetime.now(UTC).isoformat(),
            }

        result = await cancel_evaluation(task_id=task_id)

        assert result["cancelled"] is True
        assert result["mmgbsa_killed"] == 3
        assert p1.killed and p2.killed and p3.killed
        assert not other.killed

        with qh._desktop_lock:
            job = dict(qh._desktop_jobs[task_id])
        assert job["status"] == "FAILURE"
        assert job["error"] == "Cancelado por el usuario"
        assert job["finished_at"] is not None
        assert job["cancel_requested"] is True

    @pytest.mark.asyncio
    async def test_cancelled_running_job_never_transitions_back_to_success(
        self, monkeypatch
    ):
        """La llegada tardía del pipeline no puede sobrescribir FAILURE."""
        from api.routers.evaluation import cancel_evaluation

        release = asyncio.Event()
        pipeline_started = asyncio.Event()

        async def _gated_pipeline(**kwargs):
            pipeline_started.set()
            await release.wait()
            return _fake_eval_result(**kwargs)

        monkeypatch.setattr(qh, "_run_full_evaluation_async", _gated_pipeline)
        monkeypatch.setattr(
            "services.ai.memory_store.store_evaluation", lambda **kwargs: None
        )
        task = qh.submit_evaluation_job(smiles="CCO", target_pdb_id="7E2Y")
        await pipeline_started.wait()

        response = await cancel_evaluation(task_id=task.id)
        assert response["cancelled"] is True
        release.set()
        await asyncio.sleep(0.05)

        with qh._desktop_lock:
            job = dict(qh._desktop_jobs[task.id])
        assert job["status"] == "FAILURE"
        assert job["error"] == "Cancelado por el usuario"
        assert job["result"] is None

    @pytest.mark.asyncio
    async def test_cancel_ignores_terminal_jobs(self):
        """Un job SUCCESS no se re-marca (el endpoint solo toca jobs activos)."""
        from api.routers.evaluation import cancel_evaluation

        task_id = "cancel-test-2"
        with qh._desktop_lock:
            qh._desktop_jobs[task_id] = {
                "status": "SUCCESS",
                "progress": 100,
                "result": {"total_score": 88.0},
                "error": None,
                "started_at": datetime.now(UTC).isoformat(),
            }

        result = await cancel_evaluation(task_id=task_id)
        assert result["cancelled"] is False
        with qh._desktop_lock:
            job = dict(qh._desktop_jobs[task_id])
        assert job["status"] == "SUCCESS"
        assert job["error"] is None

    @pytest.mark.asyncio
    async def test_cancel_requires_a_task_id(self):
        """Una UI sin task_id no puede detener trabajos ajenos."""
        from fastapi import HTTPException

        from api.routers.evaluation import cancel_evaluation

        with pytest.raises(HTTPException) as exc_info:
            await cancel_evaluation()
        assert exc_info.value.status_code == 400


# ── Recuperación ──────────────────────────────────────────────────────────────


class TestRecovery:
    """Jobs stale y estado tras restart del backend (registro vacío)."""

    def test_stale_jobs_older_than_24h_are_purged(self):
        """_clean_old_desktop_jobs purga solo los jobs con TTL vencido."""
        now = datetime.now(UTC)
        stale_ts = (now - timedelta(hours=25)).isoformat()
        fresh_ts = now.isoformat()

        with qh._desktop_lock:
            qh._desktop_jobs["stale-1"] = {
                "status": "PENDING",
                "started_at": stale_ts,
            }
            qh._desktop_jobs["fresh-1"] = {
                "status": "SUCCESS",
                "started_at": fresh_ts,
            }

        expired = qh._clean_old_desktop_jobs()

        assert expired == 1
        with qh._desktop_lock:
            assert "stale-1" not in qh._desktop_jobs
            assert "fresh-1" in qh._desktop_jobs

    @pytest.mark.asyncio
    async def test_status_recovers_from_db_after_restart(self, isolated_runtime_engine):
        """Con _desktop_jobs vacío, el estado se recupera desde DB.

        Espeja la semántica real del módulo:
        - molécula EVALUATED → SUCCESS (con resultado)
        - molécula FAILED   → FAILURE ("recuperado desde DB")
        - sin fila          → FAILURE (tarea huerfana; no queda viva para siempre)
        """
        from core.database import (
            _patch_jsonb_for_sqlite,
            get_db_session,
        )
        from core.models import (
            EvaluationResultORM,
            MoleculeORM,
            MoleculeStatus,
            TargetORM,
            UserORM,
        )

        engine = isolated_runtime_engine
        # JSONB→TEXT para SQLite: igual que _create_engine(), idempotente.
        _patch_jsonb_for_sqlite()

        async with get_db_session() as db:
            user = UserORM(email="test@example.com", username="test")
            target = TargetORM(
                pdb_id="7E2Y",
                name="Target Test",
                chain="A",
                grid_center_x=0.0,
                grid_center_y=0.0,
                grid_center_z=0.0,
            )
            db.add_all([user, target])
            await db.flush()

            mol_ok = MoleculeORM(
                smiles="CCO",
                user_id=user.id,
                target_id=target.id,
                smiles_hash="hash_ok",
                status=MoleculeStatus.EVALUATED,
            )
            mol_bad = MoleculeORM(
                smiles="CCN",
                user_id=user.id,
                target_id=target.id,
                smiles_hash="hash_bad",
                status=MoleculeStatus.FAILED,
            )
            db.add_all([mol_ok, mol_bad])
            await db.flush()

            ev_ok = EvaluationResultORM(
                molecule_id=mol_ok.id,
                task_id="recovered-ok",
                total_score=88.5,
                affinity_kcal=-9.2,
            )
            ev_bad = EvaluationResultORM(
                molecule_id=mol_bad.id,
                task_id="recovered-bad",
            )
            db.add_all([ev_ok, ev_bad])

        # _desktop_jobs está vacío → simula backend reiniciado
        status_ok = await qh.get_job_status("recovered-ok")
        assert status_ok.status == "SUCCESS"
        assert status_ok.progress == 100
        assert status_ok.result is not None
        assert status_ok.result.total_score == 88.5

        status_bad = await qh.get_job_status("recovered-bad")
        assert status_bad.status == "FAILURE"
        assert "recuperado desde DB" in (status_bad.error or "")

        status_unknown = await qh.get_job_status("no-existe")
        assert status_unknown.status == "FAILURE"
        assert "ya no existe en el proceso local" in (status_unknown.error or "")

        # Si el usuario cancela justo al final, el resultado y archivos se
        # conservan para soporte, pero el estado durable no puede resucitar
        # como SUCCESS tras vaciar el dispatcher/cache de un reinicio.
        persisted = await qh._persist_molecule_failed(
            str(mol_ok.id),
            "Cancelado por el usuario",
            overwrite_terminal_status=True,
        )
        assert persisted is True
        qh.cache._memory.clear()

        status_cancelled_after_restart = await qh.get_job_status("recovered-ok")
        assert status_cancelled_after_restart.status == "FAILURE"
        assert "recuperado desde DB" in (status_cancelled_after_restart.error or "")

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_restart_recovers_each_immutable_run_for_the_same_molecule(
        self, isolated_runtime_engine
    ):
        """El task_id historico no puede abrir la proyeccion de una corrida nueva."""
        molecule_id, _owner_id, _foreign_id = await _seed_two_runs_for_same_molecule()

        with qh._desktop_lock:
            qh._desktop_jobs.clear()
        qh.cache._memory.clear()

        first = await qh.get_job_status("same-molecule-run-1")
        second = await qh.get_job_status("same-molecule-run-2")

        assert first.status == "SUCCESS"
        assert first.result is not None
        assert first.result.molecule_id == molecule_id
        assert first.result.total_score == 71.0
        assert second.status == "SUCCESS"
        assert second.result is not None
        assert second.result.total_score == 92.0

    @pytest.mark.asyncio
    async def test_cancelled_snapshot_does_not_resurrect_after_restart(
        self, isolated_runtime_engine
    ):
        """El terminal FAILURE prevalece aunque ya exista evidencia congelada."""
        from core.database import get_db_session
        from db.repository import Repository

        await _seed_two_runs_for_same_molecule()
        async with get_db_session() as db:
            repository = Repository(db)
            changed = await repository.mark_evaluation_run_failed(
                "same-molecule-run-1", "Cancelado por el usuario"
            )
        assert changed is True

        with qh._desktop_lock:
            qh._desktop_jobs.clear()
        qh.cache._memory.clear()

        recovered = await qh.get_job_status("same-molecule-run-1")

        assert recovered.status == "FAILURE"
        assert recovered.result is None
        assert recovered.error == "Cancelado por el usuario"

    @pytest.mark.asyncio
    async def test_status_after_restart_authorizes_owner_and_rejects_other_account(
        self, isolated_runtime_engine
    ):
        """La autorizacion durable usa la corrida aunque la proyeccion haya avanzado."""
        from types import SimpleNamespace

        from fastapi import HTTPException
        from starlette.requests import Request

        from api.routers import evaluation
        from core.database import get_db_session

        _molecule_id, owner_id, foreign_id = await _seed_two_runs_for_same_molecule()
        qh.cache._memory.clear()

        request = Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/evaluation/status/same-molecule-run-1",
                "raw_path": b"/evaluation/status/same-molecule-run-1",
                "query_string": b"",
                "headers": [],
                "client": ("10.20.30.40", 43210),
                "server": ("testserver", 80),
            }
        )

        async with get_db_session() as db:
            own_status = await evaluation.get_evaluation_status(
                "same-molecule-run-1", request, SimpleNamespace(id=owner_id), db
            )
        assert own_status.status == "SUCCESS"
        assert own_status.result is not None
        assert own_status.result.total_score == 71.0

        async with get_db_session() as db:
            with pytest.raises(HTTPException) as forbidden:
                await evaluation.get_evaluation_status(
                    "same-molecule-run-1",
                    request,
                    SimpleNamespace(id=foreign_id),
                    db,
                )
        assert forbidden.value.status_code == 403

    @pytest.mark.asyncio
    async def test_result_endpoint_can_read_the_exact_run_snapshot(
        self, isolated_runtime_engine
    ):
        """El fallback por molecule_id recibe task_id y no sustituye evidencia."""
        from types import SimpleNamespace

        from starlette.requests import Request

        from api.routers import evaluation
        from core.database import get_db_session

        molecule_id, owner_id, _foreign_id = await _seed_two_runs_for_same_molecule()
        request = Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": f"/evaluation/result/{molecule_id}",
                "raw_path": f"/evaluation/result/{molecule_id}".encode(),
                "query_string": b"task_id=same-molecule-run-1",
                "headers": [],
                "client": ("10.20.30.40", 43210),
                "server": ("testserver", 80),
            }
        )

        async with get_db_session() as db:
            historical = await evaluation.get_evaluation_result(
                molecule_id,
                request,
                SimpleNamespace(id=owner_id),
                db,
                task_id="same-molecule-run-1",
            )

        assert historical.molecule_id == molecule_id
        assert historical.task_id == "same-molecule-run-1"
        assert historical.total_score == 71.0


# ── F-02: la superficie Celery desaparece ─────────────────────────────────────


class TestCelerySurfaceRemoved:
    """Guard de regresión del hallazgo F-02: no queda rama Celery viva."""

    def test_module_has_no_celery_surface(self):
        """Sin lazy import de api.celery_app ni tasks Celery registrables."""
        assert not hasattr(qh, "celery_app")
        assert not hasattr(qh, "_CELERY_AVAILABLE")
        assert not hasattr(qh, "_celery_task")
        assert not hasattr(qh, "run_full_evaluation")
        assert not hasattr(qh, "celery_ping")
        assert not hasattr(qh, "cleanup_unsaved_molecule")
        assert not hasattr(qh, "_get_celery_loop")
