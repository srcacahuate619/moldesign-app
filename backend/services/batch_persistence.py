"""Atomic checkpoints for legacy batches; the workspace lock owns execution."""
from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update

from core.database import get_db_session
from core.models import BatchRunORM


async def save_batch(batch, *, create=False):
    payload = deepcopy(batch)
    async with get_db_session() as db:
        if create:
            db.add(BatchRunORM(batch_id=payload["id"], owner_id=payload["owner_id"],
                               status=payload["status"], payload_json=payload))
        else:
            result = await db.execute(update(BatchRunORM).where(
                BatchRunORM.batch_id == payload["id"],
                BatchRunORM.owner_id == payload["owner_id"],
            ).values(status=payload["status"], payload_json=payload))
            if result.rowcount != 1:
                raise RuntimeError("No existe el checkpoint del batch para su propietario")
        await db.commit()


async def load_inactive_batch(batch_id):
    """Called only when no in-memory worker owns this ID, under the batch lock.

    The backend holds the OS workspace lock, so another instance cannot still
    own these tasks. Never replay scientific work automatically after a crash.
    """
    try:
        canonical = str(UUID(batch_id))
    except (ValueError, TypeError):
        return None
    async with get_db_session() as db:
        row = (await db.execute(select(BatchRunORM).where(
            BatchRunORM.batch_id == canonical))).scalar_one_or_none()
        if row is None:
            return None
        payload = deepcopy(row.payload_json)
        if row.status == "running":
            payload.update(status="interrupted", error="El backend se interrumpiÃ³; se conservan los resultados confirmados.",
                           finished_at=datetime.now(UTC).isoformat())
            row.status = payload["status"]
            row.payload_json = payload
            await db.commit()
        return payload


async def read_run_result(repository, molecule_id, task_id):
    """Prefer immutable evidence; a newer projection must not hide this result."""
    from core.models import EvaluationResultRead
    run = await repository.get_evaluation_run(task_id, molecule_id)
    if run is not None:
        if run.status != "SUCCESS" or run.error_message:
            return None
        result = EvaluationResultRead.model_validate(run.snapshot_json)
    else:
        projection = await repository.get_evaluation_result(molecule_id)
        if projection is None or projection.task_id != task_id:
            return None
        result = EvaluationResultRead.model_validate(projection)
    return None if result.error_message else result
