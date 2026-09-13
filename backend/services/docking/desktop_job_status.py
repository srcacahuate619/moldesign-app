"""Consulta y recuperación de estado para jobs del dispatcher desktop.

El registro en memoria pertenece a ``queue_handler`` porque también lo usan
el envío y la cancelación. Este módulo recibe ese registro y su lock por
inyección para concentrar aquí la semántica de polling, cache y recuperación
tras reiniciar el backend, sin crear un segundo estado global.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from core.database import get_db_session
from core.models import EvaluationResultRead, JobStatus, _coerce_hotspots
from db.repository import Repository
from services.targets.calibracion import estado_de_calibracion
from utils.logger import get_logger

log = get_logger(__name__)

# El frontend consulta cada 2 s. Cinco lecturas dan a SQLite hasta ~10 s para
# hacer visible/serializable el resultado sin dejar un spinner infinito cuando
# la fila o el payload quedaron permanentemente corruptos.
RESULT_HYDRATION_MAX_ATTEMPTS = 5
_RESULT_HYDRATION_ATTEMPTS_KEY = "result_hydration_attempts"


def _parse_iso_or_none(value: str | None) -> datetime | None:
    """Convierte un timestamp ISO del registro local, o devuelve ``None``."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _status_from_job_snapshot(
    task_id: str,
    job: dict[str, Any],
    *,
    result: EvaluationResultRead | None = None,
) -> JobStatus:
    """Serializa un snapshot ya copiado sin volver a leer estado mutable."""
    return JobStatus(
        task_id=task_id,
        status=job.get("status", "PENDING"),
        progress=job.get("progress", 0),
        result=result,
        error=job.get("error"),
        started_at=_parse_iso_or_none(job.get("started_at")),
        finished_at=_parse_iso_or_none(job.get("finished_at")),
    )


def _serialize_evaluation(evaluation: Any) -> EvaluationResultRead:
    """Mantiene el enriquecimiento de target de la respuesta histórica."""
    result_payload = EvaluationResultRead.model_validate(evaluation)
    molecule = getattr(evaluation, "molecule", None)
    if molecule and molecule.target:
        result_payload.target_hotspots = _coerce_hotspots(
            molecule.target.hotspots
        )
        result_payload.target_name = molecule.target.name
        result_payload.target_spearman_rho = molecule.target.spearman_rho
        # SC-9: el respaldo del receptor viaja con el resultado, para que la
        # advertencia no dependa de que la pantalla vuelva a consultarlo.
        result_payload.target_calibracion = estado_de_calibracion(
            molecule.target
        ).to_dict()
    return result_payload


def _serialize_run_snapshot(run: Any, molecule: Any) -> EvaluationResultRead:
    """Convierte el snapshot inmutable de ``task_id`` al contrato de la API."""
    snapshot = run.snapshot_json
    if not isinstance(snapshot, dict):
        raise ValueError("El snapshot durable de la corrida no es un objeto JSON.")
    frozen = SimpleNamespace(**snapshot)
    frozen.molecule = molecule
    return _serialize_evaluation(frozen)


async def get_desktop_job_status(
    task_id: str,
    *,
    jobs: dict[str, dict[str, Any]],
    lock: Any,
    cache: Any,
) -> JobStatus:
    """Obtiene el estado preservando el contrato desktop de cache y SQLite.

    ``jobs`` es la fuente viva de verdad. Cuando no existe (por ejemplo,
    después de un reinicio), un cache terminal evita una consulta y SQLite
    permite recuperar los resultados durables.
    """
    with lock:
        live_job = jobs.get(task_id)
        # No conservar una referencia mutable fuera del lock: cancelacion y
        # watchdog comparten este registro con el endpoint de polling.
        job = dict(live_job) if live_job is not None else None

    if job is None:
        # Un PENDING cacheado se crea al enviar y puede sobrevivir al job; no
        # prueba que siga vivo. Sólo los estados terminales son autoritativos.
        cached_status = await cache.get(f"job_status:{task_id}")
        if cached_status is not None:
            try:
                parsed = JobStatus.model_validate(cached_status)
                # SUCCESS sin payload no es terminal para el producto: no hay
                # molecule_id con el que abrir la evidencia. Versiones previas
                # cacheaban ese estado incompleto y lo devolvian para siempre,
                # aunque SQLite ya tuviera el resultado durable.
                if parsed.status == "FAILURE" or (
                    parsed.status == "SUCCESS" and parsed.result is not None
                ):
                    return parsed
            except Exception:
                pass

        # Backend reiniciado: el registro local está vacío y SQLite conserva
        # el resultado científico y el estado de la molécula.
        try:
            from sqlalchemy import select as _sa_select

            from core.models import EvaluationResultORM, MoleculeORM, MoleculeStatus

            async with get_db_session() as db:
                repository = Repository(db)
                run = await repository.get_evaluation_run(task_id)
                if run is not None:
                    if (run.status or "SUCCESS") == "FAILURE":
                        failed = JobStatus(
                            task_id=task_id,
                            status="FAILURE",
                            progress=100,
                            result=None,
                            error=run.error_message or "La evaluación falló (recuperado desde DB).",
                        )
                        await cache.set(f"job_status:{task_id}", failed, ttl=86400)
                        return failed
                    molecule = await repository.get_molecule(run.molecule_id)
                    if molecule is None:
                        raise ValueError("La corrida durable referencia una molécula inexistente.")
                    result_payload = _serialize_run_snapshot(run, molecule)
                    recovered = JobStatus(
                        task_id=task_id,
                        status="SUCCESS",
                        progress=100,
                        result=result_payload,
                        error=None,
                    )
                    await cache.set(f"job_status:{task_id}", recovered, ttl=86400)
                    log.info("job_status_run_snapshot_recovered", task_id=task_id)
                    return recovered

                # Compatibilidad con evaluaciones anteriores a schema v11: la
                # proyección mutable sólo es válida si todavía conserva task_id.
                stmt = (
                    _sa_select(EvaluationResultORM, MoleculeORM)
                    .join(
                        MoleculeORM,
                        EvaluationResultORM.molecule_id == MoleculeORM.id,
                    )
                    .where(EvaluationResultORM.task_id == task_id)
                )
                res = await db.execute(stmt)
                row = res.first()
                if row:
                    _evaluation_orm, molecule = row
                    if molecule.status == MoleculeStatus.EVALUATED:
                        evaluation = await repository.get_evaluation_result(molecule.id)
                        result_payload = (
                            _serialize_evaluation(evaluation)
                            if evaluation is not None
                            else None
                        )
                        recovered = JobStatus(
                            task_id=task_id,
                            status="SUCCESS",
                            progress=100,
                            result=result_payload,
                            error=None,
                        )
                        await cache.set(f"job_status:{task_id}", recovered, ttl=86400)
                        log.info("job_status_recovered_from_db", task_id=task_id)
                        return recovered
                    if molecule.status == MoleculeStatus.FAILED:
                        failed = JobStatus(
                            task_id=task_id,
                            status="FAILURE",
                            progress=100,
                            result=None,
                            error="La evaluación falló (recuperado desde DB).",
                        )
                        await cache.set(f"job_status:{task_id}", failed, ttl=86400)
                        return failed
        except Exception as db_exc:
            log.warning(
                "job_status_db_fallback_failed", task_id=task_id, error=str(db_exc)
            )

        # En el dispatcher desktop una tarea que no existe en memoria no puede
        # seguir ejecutandose: los workers viven en este mismo proceso. Tras un
        # reinicio, devolver PENDING inventaba trabajo vivo y bloqueaba el caso
        # indefinidamente. Si tampoco hay resultado durable, el seguimiento se
        # perdio y debe cerrarse como fallo tecnico recuperable.
        orphaned = JobStatus(
            task_id=task_id,
            status="FAILURE",
            progress=100,
            result=None,
            error=(
                "La tarea ya no existe en el proceso local y no se encontro "
                "un resultado persistido. Puedes volver a ejecutar la evaluacion."
            ),
        )
        await cache.set(f"job_status:{task_id}", orphaned, ttl=86400)
        log.warning("desktop_job_orphaned", task_id=task_id)
        return orphaned

    status_value = job.get("status", "PENDING")
    result_payload: EvaluationResultRead | None = None

    if status_value == "SUCCESS":
        raw_result = job.get("result")
        molecule_id = raw_result.get("molecule_id") if isinstance(raw_result, dict) else None
        if not molecule_id:
            # Esto no es una carrera de commit: sin enlace durable ninguna
            # consulta posterior sabe que fila recuperar.
            return JobStatus(
                task_id=task_id,
                status="FAILURE",
                progress=100,
                result=None,
                error=(
                    "La evaluacion termino con SUCCESS, pero no fue posible "
                    "recuperar el resultado: falta molecule_id y no existe "
                    "un enlace durable al resultado persistido."
                ),
                started_at=_parse_iso_or_none(job.get("started_at")),
                finished_at=_parse_iso_or_none(job.get("finished_at")),
            )

        hydration_error: Exception | None = None
        try:
            molecule_uuid = UUID(str(molecule_id))
            async with get_db_session() as db:
                repository = Repository(db)
                run = await repository.get_evaluation_run(task_id, molecule_uuid)
                if run is not None:
                    if (run.status or "SUCCESS") == "FAILURE":
                        return JobStatus(
                            task_id=task_id,
                            status="FAILURE",
                            progress=100,
                            result=None,
                            error=run.error_message or "La evaluación falló.",
                            started_at=_parse_iso_or_none(job.get("started_at")),
                            finished_at=_parse_iso_or_none(job.get("finished_at")),
                        )
                    molecule = await repository.get_molecule(molecule_uuid)
                    if molecule is None:
                        raise ValueError("La corrida durable referencia una molécula inexistente.")
                    result_payload = _serialize_run_snapshot(run, molecule)
                else:
                    # Compatibilidad legacy. Si la proyección declara otro
                    # task_id, pertenece a una corrida posterior y no se usa.
                    evaluation = await repository.get_evaluation_result(molecule_uuid)
                    stored_task_id = (
                        getattr(evaluation, "task_id", None)
                        or getattr(evaluation, "celery_task_id", None)
                        if evaluation is not None
                        else None
                    )
                    if evaluation is not None and (
                        stored_task_id is None or str(stored_task_id) == str(task_id)
                    ):
                        result_payload = _serialize_evaluation(evaluation)
        except Exception as exc:
            hydration_error = exc

        if result_payload is not None:
            superseding_job: dict[str, Any] | None = None
            with lock:
                current = jobs.get(task_id)
                if current is not None and current.get("status") == "SUCCESS":
                    current.pop(_RESULT_HYDRATION_ATTEMPTS_KEY, None)
                elif current is not None:
                    # Cancelacion/watchdog pudieron ganar mientras esperaba
                    # SQLite. El estado compartido mas reciente es autoritativo.
                    superseding_job = dict(current)
            if superseding_job is not None:
                superseding_status = _status_from_job_snapshot(task_id, superseding_job)
                if superseding_status.status == "FAILURE":
                    await cache.set(
                        f"job_status:{task_id}", superseding_status, ttl=86400
                    )
                return superseding_status
        else:
            # La corrida ya termino, pero el commit/lectura/serializacion puede
            # estar en una ventana transitoria. El contador vive en el job
            # compartido y toda mutacion ocurre bajo el lock inyectado.
            superseding_job = None
            with lock:
                current = jobs.get(task_id)
                if current is not None and current.get("status") != "SUCCESS":
                    superseding_job = dict(current)
                    attempts = RESULT_HYDRATION_MAX_ATTEMPTS
                elif current is None:
                    attempts = RESULT_HYDRATION_MAX_ATTEMPTS
                else:
                    attempts = int(current.get(_RESULT_HYDRATION_ATTEMPTS_KEY, 0)) + 1
                    current[_RESULT_HYDRATION_ATTEMPTS_KEY] = attempts

            if superseding_job is not None:
                superseding_status = _status_from_job_snapshot(task_id, superseding_job)
                if superseding_status.status == "FAILURE":
                    await cache.set(
                        f"job_status:{task_id}", superseding_status, ttl=86400
                    )
                return superseding_status

            if hydration_error is not None:
                log.warning(
                    "Error al obtener resultado DESKTOP de DB",
                    task_id=task_id,
                    attempt=attempts,
                    max_attempts=RESULT_HYDRATION_MAX_ATTEMPTS,
                    error=str(hydration_error),
                )

            if attempts < RESULT_HYDRATION_MAX_ATTEMPTS:
                # STARTED ya pertenece al contrato JobStatus y el frontend lo
                # sigue consultando. 99 declara que solo falta publicar la
                # evidencia; nunca fingimos un SUCCESS sin resultado.
                return JobStatus(
                    task_id=task_id,
                    status="STARTED",
                    progress=99,
                    result=None,
                    error=None,
                    started_at=_parse_iso_or_none(job.get("started_at")),
                    finished_at=None,
                )

            return JobStatus(
                task_id=task_id,
                status="FAILURE",
                progress=100,
                result=None,
                error=(
                    "La evaluacion termino, pero el resultado persistido no "
                    f"pudo hidratarse tras {RESULT_HYDRATION_MAX_ATTEMPTS} intentos. "
                    "Revisa los logs del backend y reintenta."
                ),
                started_at=_parse_iso_or_none(job.get("started_at")),
                finished_at=_parse_iso_or_none(job.get("finished_at")),
            )

    job_status = _status_from_job_snapshot(task_id, job, result=result_payload)

    # Nunca congelar SUCCESS sin resultado: obliga a reintentar la lectura de
    # SQLite en vez de convertir un fallo transitorio de serializacion en una
    # perdida permanente de evidencia.
    if status_value == "FAILURE" or (
        status_value == "SUCCESS" and result_payload is not None
    ):
        await cache.set(f"job_status:{task_id}", job_status, ttl=86400)

    return job_status
