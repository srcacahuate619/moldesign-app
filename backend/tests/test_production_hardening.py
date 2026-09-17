"""Fallos operativos reales: no recalibran ni sustituyen la ciencia."""
from __future__ import annotations

import asyncio
import sys
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.mark.parametrize("name", ["../outside", "a/../../outside", r"a\..\..\outside",
                                  "/outside", "C:/outside", "C:relative", r"\\host\share\x",
                                  "a:stream", "", "a/./x", "a/.. /outside",
                                  "NUL", "folder/CON.txt", "COM1", "folder/file. "])
def test_storage_rejects_unsafe_paths(name, tmp_path, monkeypatch):
    from utils import local_storage as storage
    monkeypatch.setattr(storage, "settings", SimpleNamespace(local_data_dir=str(tmp_path / "data")))
    with pytest.raises(ValueError):
        storage.path_for(name)


@pytest.mark.asyncio
async def test_atomic_write_preserves_previous_artifact_on_publish_failure(tmp_path, monkeypatch):
    from utils import local_storage as storage
    monkeypatch.setattr(storage, "settings", SimpleNamespace(local_data_dir=str(tmp_path)))
    await storage.write_bytes(b"complete previous evidence", "poses/run.sdf")

    def fail(*args):
        raise OSError("disk publish failed")

    monkeypatch.setattr(storage.os, "replace", fail)
    with pytest.raises(OSError, match="disk publish"):
        await storage.write_bytes(b"replacement", "poses/run.sdf")
    assert await storage.read_bytes("poses/run.sdf") == b"complete previous evidence"
    assert not list(tmp_path.rglob(".writing-*"))


@pytest.mark.asyncio
@pytest.mark.parametrize("manual", [False, True])
async def test_sqlite_locked_commit_never_reports_empty_success(tmp_path, monkeypatch, manual):
    import core.database as database
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite'}",
                                 connect_args={"timeout": 0.01})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(database, "get_session_factory", lambda: factory)

    class Base(DeclarativeBase):
        pass

    class Item(Base):
        __tablename__ = "items"
        id: Mapped[int] = mapped_column(primary_key=True)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with engine.connect() as blocker:
            await blocker.execute(text("BEGIN IMMEDIATE"))
            if manual:
                with pytest.raises(OperationalError, match="locked"):
                    async with database.get_db_session() as session:
                        session.add(Item(id=1))
            else:
                dependency = database.get_db()
                session = await anext(dependency)
                session.add(Item(id=1))
                with pytest.raises(OperationalError, match="locked"):
                    await anext(dependency)
            await blocker.rollback()
        async with factory() as session:
            assert (await session.execute(text("SELECT count(*) FROM items"))).scalar() == 0
            session.add(Item(id=2))
            await database.commit_with_retry(session)
        async with factory() as session:
            assert (await session.execute(text("SELECT id FROM items"))).scalars().all() == [2]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_managed_real_child_is_reaped_on_timeout_or_cancel(cancel):
    from utils.procesos import BANDERAS_SIN_VENTANA, communicate_managed
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", "import time; time.sleep(30)",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        creationflags=BANDERAS_SIN_VENTANA,
    )
    task = asyncio.create_task(communicate_managed(process, timeout=0.1 if not cancel else 30))
    if cancel:
        await asyncio.sleep(0.05)
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
        await task
    assert process.returncode is not None
    assert await asyncio.wait_for(process.wait(), 1) != 0


@pytest.mark.asyncio
async def test_managed_process_drains_both_pipes_without_deadlock():
    from utils.procesos import BANDERAS_SIN_VENTANA, communicate_managed
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c",
        "import sys; sys.stdout.write('x'*200000); sys.stderr.write('y'*200000)",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        creationflags=BANDERAS_SIN_VENTANA,
    )
    stdout, stderr = await communicate_managed(process, timeout=10)
    assert len(stdout) == len(stderr) == 200000
    assert process.returncode == 0


@pytest.mark.parametrize("model_name", ["EvaluationSubmitRequest", "PreflightRequest"])
@pytest.mark.parametrize("field,value", [("grid_center", (float("nan"), 0, 0)),
                                        ("grid_center", (0, float("inf"), 0)),
                                        ("grid_size", (20, -1, 20)),
                                        ("grid_size", (20, 0, 20))])
def test_invalid_geometry_is_rejected_before_execution(model_name, field, value):
    from api.routers import evaluation
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        getattr(evaluation, model_name)(smiles="CCO", target_pdb_id="7E2Y", **{field: value})


@pytest.mark.asyncio
async def test_cohort_upload_reads_only_limit_plus_one(monkeypatch):
    from api.routers import evaluation_cohorts as router
    from fastapi import HTTPException
    monkeypatch.setattr(router, "MAX_COHORT_FILE_BYTES", 10)
    upload = SimpleNamespace(read=AsyncMock(return_value=b"x" * 11), filename="test.csv")
    with pytest.raises(HTTPException) as exc:
        await router._leer_archivo(upload)
    assert exc.value.status_code == 422
    upload.read.assert_awaited_once_with(11)


@pytest.mark.asyncio
async def test_ligand_lock_serializes_same_input_but_allows_other_ligands():
    from services.docking.evaluation_lock import serialize_ligand_evaluation, _locks
    release = asyncio.Event()
    started = []

    @serialize_ligand_evaluation()
    async def run(smiles, label):
        started.append(label)
        await release.wait()

    first = asyncio.create_task(run("CCO", "a"))
    await asyncio.sleep(0)
    second = asyncio.create_task(run("CCO", "b"))
    other = asyncio.create_task(run("CC", "c"))
    await asyncio.sleep(0.02)
    assert started == ["a", "c"]
    second.cancel()
    with pytest.raises(asyncio.CancelledError):
        await second
    release.set()
    await asyncio.gather(first, other)
    await run("CCO", "d")
    assert started == ["a", "c", "d"]
    assert not _locks


@pytest.mark.asyncio
async def test_watchdog_cancels_pipeline_persists_failure_and_releases_slot(monkeypatch):
    from services.docking import queue_handler as qh
    from utils.cache import LocalRuntimeStore
    stopped = asyncio.Event()

    async def blocked(**kwargs):
        qh.register_job_molecule(kwargs["task_id"], "molecule-test")
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    semaphore = threading.Semaphore(1)
    persist = AsyncMock(return_value=True)
    monkeypatch.setattr(qh, "_desktop_jobs", {})
    monkeypatch.setattr(qh, "cache", LocalRuntimeStore())
    monkeypatch.setattr(qh, "_desktop_eval_semaphore", semaphore)
    monkeypatch.setattr(qh, "EVAL_WATCHDOG_TIMEOUT_S", 0.03)
    monkeypatch.setattr(qh, "_run_full_evaluation_async", blocked)
    monkeypatch.setattr(qh, "_persist_molecule_failed", persist)
    task = qh.submit_evaluation_job(smiles="CCO", target_pdb_id="7E2Y")
    await asyncio.wait_for(stopped.wait(), 2)
    for _ in range(100):
        if "async_task" not in qh._desktop_jobs[task.id]:
            break
        await asyncio.sleep(0.01)
    assert qh._desktop_jobs[task.id]["status"] == "FAILURE"
    assert "Timeout" in qh._desktop_jobs[task.id]["error"]
    assert persist.await_args.args[0] == "molecule-test"
    assert semaphore.acquire(blocking=False)
    semaphore.release()


@pytest.mark.asyncio
async def test_cancel_waiting_job_never_steals_semaphore(monkeypatch):
    from services.docking import queue_handler as qh
    from utils.cache import LocalRuntimeStore
    semaphore = threading.Semaphore(0)
    pipeline = AsyncMock()
    monkeypatch.setattr(qh, "_desktop_jobs", {})
    monkeypatch.setattr(qh, "cache", LocalRuntimeStore())
    monkeypatch.setattr(qh, "_desktop_eval_semaphore", semaphore)
    monkeypatch.setattr(qh, "_run_full_evaluation_async", pipeline)
    monkeypatch.setattr(qh, "_persist_molecule_failed", AsyncMock())
    task = qh.submit_evaluation_job(smiles="CCO", target_pdb_id="7E2Y")
    await asyncio.sleep(0.02)
    assert qh.request_desktop_job_cancellation(task.id)
    await asyncio.sleep(0.06)
    semaphore.release()
    await asyncio.sleep(0.06)
    assert semaphore.acquire(blocking=False)
    pipeline.assert_not_awaited()
    assert qh._desktop_jobs[task.id]["status"] == "FAILURE"


@pytest.mark.asyncio
async def test_nonfinite_request_error_returns_422_json():
    import json
    from fastapi.exceptions import RequestValidationError
    from api.main import handle_invalid_request
    error = RequestValidationError([{
        "type": "value_error", "loc": ("body", "grid_center"),
        "msg": "finite numbers required", "input": [float("nan"), float("inf"), 0],
        "ctx": {"error": ValueError("finite numbers required")},
    }])
    response = await handle_invalid_request(None, error)
    assert response.status_code == 422
    body = json.loads(response.body)
    assert body["detail"][0]["input"] == ["nan", "inf", 0]


@pytest.mark.asyncio
async def test_cancelling_parent_also_kills_real_grandchild(tmp_path):
    import psutil
    from utils.procesos import BANDERAS_SIN_VENTANA, communicate_managed
    pid_file = tmp_path / "child.pid"
    code = (
        "import subprocess,sys,time,pathlib; "
        f"p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],creationflags={BANDERAS_SIN_VENTANA}); "
        "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(30)"
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", code, str(pid_file),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        creationflags=BANDERAS_SIN_VENTANA,
    )
    task = asyncio.create_task(communicate_managed(process, timeout=10))
    try:
        for _ in range(200):
            if pid_file.exists() and pid_file.read_text():
                break
            await asyncio.sleep(0.01)
        child = psutil.Process(int(pid_file.read_text()))
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert process.returncode is not None
        await asyncio.to_thread(child.wait, timeout=3)
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_process_failure_returns_actual_stderr_and_exit_code():
    from utils.procesos import BANDERAS_SIN_VENTANA, communicate_managed
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", "import sys; sys.stderr.write('broken tool'); sys.exit(7)",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        creationflags=BANDERAS_SIN_VENTANA,
    )
    stdout, stderr = await communicate_managed(process, timeout=10)
    assert stdout == b""
    assert stderr == b"broken tool"
    assert process.returncode == 7


@pytest.mark.asyncio
async def test_private_complex_never_downloads_internal_id(monkeypatch):
    from tests.test_evaluation_files import _files_fixture
    from api.routers import evaluation_files
    from utils import local_storage, file_handlers
    from fastapi import HTTPException
    molecule_id, owner, db = _files_fixture(monkeypatch)
    db.molecule.target = SimpleNamespace(pdb_id="USR_TEST", is_private=True, creator_id=owner.id)
    monkeypatch.setattr(local_storage, "exists", AsyncMock(return_value=False))
    download = AsyncMock()
    monkeypatch.setattr(file_handlers, "download_pdb_from_rcsb", download)
    with pytest.raises(HTTPException) as exc:
        await evaluation_files.get_complex_file(molecule_id, owner, db)
    assert exc.value.status_code == 404
    download.assert_not_awaited()


@pytest.mark.asyncio
async def test_redock_keeps_old_artifacts_and_uses_hashed_receptor(tmp_path, monkeypatch):
    import hashlib
    from pathlib import Path
    from services.docking import vina_service as vina
    from utils import local_storage as storage
    from utils.cache import LocalRuntimeStore
    data = tmp_path / "data"
    temporary = tmp_path / "temp"
    temporary.mkdir()
    monkeypatch.setattr(storage.settings, "local_data_dir", str(data))
    monkeypatch.setattr(storage.settings, "vina_temp_dir", str(temporary))
    monkeypatch.setattr(vina, "cache", LocalRuntimeStore())
    source = "targets/7E2Y/prepared.pdbqt"
    ligand = "ligands/test/vina_input.pdbqt"
    original = b"original receptor bytes"
    await storage.write_bytes(original, source)
    await storage.write_bytes(b"ligand", ligand)
    monkeypatch.setattr(vina, "prepare_target", AsyncMock(return_value=source))
    monkeypatch.setattr(vina, "resolve_effective_docking_box", lambda **kw: ((1, 2, 3), (20, 20, 20)))
    monkeypatch.setattr(vina, "_resolve_executable", lambda path: "available")
    monkeypatch.setattr(vina, "_is_valid_sdf", lambda content: True)
    monkeypatch.setattr(vina, "parse_vina_output_sdf", lambda content: [
        {"rank": 1, "affinity": -8.0, "rmsd_lb": 0.0, "rmsd_ub": 0.0}])
    monkeypatch.setattr(vina, "_parse_vina_stdout", lambda content: [])
    monkeypatch.setattr(vina, "_check_ligand_fits_box", lambda *args: None)

    async def prepare_ligand(*args, **kwargs):
        # Simular otra preparación entre el hash y el lanzamiento de Vina.
        await storage.write_bytes(b"replaced by another preparation", source)
        return ligand

    async def run_vina(**kwargs):
        assert kwargs["receptor_path"].read_bytes() == original
        kwargs["output_path"].write_text("MODEL 1\nENDMDL\n")
        kwargs["log_path"].write_text("real run log")
        return ""

    async def export(*args, **kwargs):
        Path(args[-1]).write_text("complete exported SDF")
        return SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(b"", b"")))

    monkeypatch.setattr(vina, "_prepare_ligand_pdbqt", prepare_ligand)
    monkeypatch.setattr(vina, "_run_vina_subprocess", run_vina)
    monkeypatch.setattr(vina.asyncio, "create_subprocess_exec", export)
    first = await vina.run_vina_docking("test", "7E2Y", force_redock=True)
    old_bytes = await storage.read_bytes(first.poses_file_path)
    await storage.write_bytes(original, source)
    second = await vina.run_vina_docking("test", "7E2Y", force_redock=True)
    assert first.receptor_sha256 == hashlib.sha256(original).hexdigest()
    assert second.poses_file_path != first.poses_file_path
    assert await storage.read_bytes(first.poses_file_path) == old_bytes
    assert not list(temporary.iterdir())


@pytest.mark.asyncio
async def test_failure_before_new_projection_closes_current_run_not_another(monkeypatch):
    from contextlib import asynccontextmanager
    from uuid import uuid4
    from core.models import MoleculeStatus
    from services.docking import queue_handler as qh
    molecule_id = uuid4()
    molecule = SimpleNamespace(id=molecule_id, status=MoleculeStatus.VALIDATED)
    repo = SimpleNamespace(
        get_molecule=AsyncMock(return_value=molecule),
        get_evaluation_result=AsyncMock(return_value=SimpleNamespace(task_id="previous")),
        mark_evaluation_run_failed=AsyncMock(), upsert_evaluation_result=AsyncMock(),
    )
    db = SimpleNamespace(commit=AsyncMock(), flush=AsyncMock())

    @asynccontextmanager
    async def session():
        yield db

    monkeypatch.setattr(qh, "get_db_session", session)
    monkeypatch.setattr(qh, "Repository", lambda session: repo)
    monkeypatch.setattr(qh, "_desktop_jobs", {"current": {}, "newer": {}})
    monkeypatch.setattr(qh, "_molecule_job_owners", {})
    qh.register_job_molecule("current", molecule_id)
    assert await qh._persist_molecule_failed(str(molecule_id), "failed early", task_id="current")
    assert molecule.status == MoleculeStatus.FAILED
    repo.upsert_evaluation_result.assert_awaited_once()
    molecule.status = MoleculeStatus.DOCKING
    qh.register_job_molecule("newer", molecule_id)
    assert not await qh._persist_molecule_failed(str(molecule_id), "late failure", task_id="current")
    assert molecule.status == MoleculeStatus.DOCKING


@pytest.mark.asyncio
async def test_external_output_limit_fails_and_reaps_process():
    from utils.procesos import BANDERAS_SIN_VENTANA, communicate_managed
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", "import sys,time; sys.stdout.write('x'*4000000); sys.stdout.flush(); time.sleep(60)",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        creationflags=BANDERAS_SIN_VENTANA,
    )
    with pytest.raises(RuntimeError, match="excedió"):
        await communicate_managed(process, timeout=10, max_output_bytes=4096)
    await asyncio.wait_for(process.wait(), 5)
    assert process.returncode is not None
