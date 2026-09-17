"""Cambio transaccional de proyección conservando toda la evidencia anterior."""
from datetime import UTC, datetime
from uuid import uuid4

from core.models import EvaluationResultORM, MoleculeStatus


async def begin_evaluation_projection(repository, molecule_id, task_id, *, is_control=False):
    current = await repository.get_evaluation_result(molecule_id)
    if current is None:
        await repository.upsert_evaluation_result(
            molecule_id=molecule_id, task_id=task_id, is_control=is_control)
        return
    if current.task_id == task_id:
        return
    # Se guarda la proyección completa, incluidos auxiliares llegados después
    # del snapshot final. Nunca se modifica un snapshot científico previo.
    archive_key = current.task_id
    if not archive_key or await repository.get_evaluation_run(archive_key):
        archive_key = f"projection-archive:{uuid4()}"
    archive = await repository.snapshot_evaluation_run(molecule_id, archive_key)
    if current.error_message or current.molecule.status != MoleculeStatus.EVALUATED:
        archive.status = "FAILURE"
        archive.error_message = current.error_message or "Corrida anterior interrumpida"
    # El archivo contiene una copia de CADA columna antes de reiniciar la
    # proyección. Un rollback revierte ambas operaciones; no se borran archivos.
    for column in EvaluationResultORM.__table__.columns:
        if column.name not in {"id", "molecule_id"}:
            setattr(current, column.name, None)
    current.task_id = task_id
    current.is_control = is_control
    current.selectivity_ran = False
    current.evaluated_at = datetime.now(UTC)
    await repository.db.flush()
