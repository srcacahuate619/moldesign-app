import io
import uuid
import zipfile
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from api.routers import batch


def test_csv_missing_cells_are_empty_not_internal_errors():
    molecules, labels = batch._extract_from_csv("smiles,name\nCCO\n")
    assert molecules == [{"smiles": "CCO", "name": "CCO"}]
    assert labels == {}


def test_csv_extra_cells_are_rejected():
    with pytest.raises(HTTPException) as error:
        batch._extract_from_csv("smiles,name\nCCO,name,extra\n")
    assert error.value.status_code == 400


def test_excel_expansion_rejected_before_parser(monkeypatch):
    import openpyxl
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("oversized.xml", b"0" * (81 * 1024 * 1024))
    def unexpected(*args, **kwargs):
        raise AssertionError("Oversized archive reached parser")
    monkeypatch.setattr(openpyxl, "load_workbook", unexpected)
    with pytest.raises(HTTPException) as error:
        batch._extract_from_excel(buffer.getvalue())
    assert error.value.status_code == 413


def test_excel_valid_rows_and_corrupt_file():
    import openpyxl
    workbook = openpyxl.Workbook()
    workbook.active.append(["smiles", "name", "active"])
    workbook.active.append(["CCO", "ethanol", 1])
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    assert batch._extract_from_excel(buffer.getvalue()) == (
        [{"smiles": "CCO", "name": "ethanol"}], {"ethanol": True})
    with pytest.raises(HTTPException) as error:
        batch._extract_from_excel(b"broken spreadsheet")
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_batch_failure_keeps_owner_and_never_reads_old_success(monkeypatch):
    import services.docking.queue_handler as qh
    owner = str(uuid.uuid4())
    identifier = str(uuid.uuid4())
    batch._batches[identifier] = {"id": identifier, "owner_id": owner, "total": 1,
        "completed": 0, "failed": 0, "results": [], "status": "running"}
    evaluate = AsyncMock(return_value={"molecule_id": str(uuid.uuid4()), "error": "engine failed"})
    monkeypatch.setattr(qh, "_run_full_evaluation_async", evaluate)
    try:
        await batch._process_batch(identifier, [{"name": "ligand", "smiles": "CCO"}],
                                   ["7E2Y"], 1, False, False)
        state = batch._batches[identifier]
        assert evaluate.call_args.kwargs["user_id"] == owner
        assert state["failed"] == 1
        assert state["status"] == "completed"
        assert state["results"][0]["error"] == "engine failed"
        assert "total_score" not in state["results"][0]
    finally:
        batch._batches.pop(identifier, None)


@pytest.mark.asyncio
async def test_all_targets_excludes_other_owners_receptors(monkeypatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    import core.database as database
    import db.repository as repository
    owner = uuid.uuid4()
    targets = [SimpleNamespace(pdb_id="7E2Y", is_prepared=True, is_private=False),
               SimpleNamespace(pdb_id="USR_001", is_prepared=True, is_private=True, creator_id=owner),
               SimpleNamespace(pdb_id="USR_002", is_prepared=True, is_private=True, creator_id=uuid.uuid4())]
    @asynccontextmanager
    async def session():
        yield None
    monkeypatch.setattr(database, "get_db_session", session)
    monkeypatch.setattr(repository, "Repository", lambda _: SimpleNamespace(get_all_targets=AsyncMock(return_value=targets)))
    assert await batch._get_default_targets(SimpleNamespace(id=owner)) == ["7E2Y", "USR_001"]
    assert await batch._get_default_targets() == ["7E2Y"]


@pytest.fixture(autouse=True)
def _isolated_batch_checkpoints(monkeypatch):
    # These tests isolate API/scientific dispatch; real SQLite checkpoints are
    # covered by test_batch_persistence_hardening with temporary databases.
    from unittest.mock import AsyncMock
    from api.routers import batch
    monkeypatch.setattr(batch, "_persist_batch", AsyncMock())
    monkeypatch.setattr(batch, "_load_batch", AsyncMock(return_value=None))
