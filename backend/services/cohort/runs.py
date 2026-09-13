"""
Persistencia y bucle de una corrida de cohorte.

# El orden importa, y es el único que sobrevive a un corte

    1. se persiste la corrida y TODAS sus filas, en una transacción;
    2. sólo entonces se encola la ejecución.

Al revés —encolar y luego escribir— dejaría trabajo corriendo sobre una corrida
que no existe en disco, y un corte a mitad produciría dockings huérfanos que
nadie puede atribuir a nada.

Dentro del bucle, la misma regla por fila: `running` se escribe y se confirma
ANTES de llamar al pipeline. Si el proceso muere durante el docking, al
arrancar queda una fila en `running` que el arranque convierte en
`interrupted`. Escribirlo después dejaría una fila `pending` indistinguible de
una que nunca empezó.

# Cada fila tiene su propia sesión

El pipeline de una molécula puede tardar minutos. Mantener una sesión de
SQLite abierta todo ese tiempo bloquea a los demás escritores —es el fallo que
`queue_handler` documenta con detalle—. Aquí cada escritura de estado abre su
sesión, escribe y la cierra.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import CohortORM, CohortRunORM, CohortRunRowORM
from services.cohort import execution as ex
from utils.logger import get_logger

log = get_logger(__name__)

#: Tareas vivas por corrida. Es una conveniencia del proceso —para no encolar
#: dos veces la misma corrida—, NO la fuente de verdad: esa está en la base, y
#: es la que sobrevive al reinicio.
_TAREAS: dict[str, asyncio.Task] = {}


# ── Creación ─────────────────────────────────────────────────────────


async def active_run_for(db: AsyncSession, cohort_id: uuid.UUID) -> CohortRunORM | None:
    """Una corrida viva de esta cohorte, si la hay."""
    return await db.scalar(
        select(CohortRunORM)
        .where(
            CohortRunORM.cohort_id == cohort_id,
            CohortRunORM.status.in_(ex.RUN_ACTIVE_STATUSES),
        )
        .limit(1)
    )


async def latest_run_for(
    db: AsyncSession, *, cohort_id: uuid.UUID, owner_id: uuid.UUID
) -> CohortRunORM | None:
    """Última corrida durable de una cohorte del dueño, si existe."""
    return await db.scalar(
        select(CohortRunORM)
        .where(
            CohortRunORM.cohort_id == cohort_id,
            CohortRunORM.user_id == owner_id,
        )
        .order_by(CohortRunORM.created_at.desc(), CohortRunORM.id.desc())
        .limit(1)
    )


async def create_run(
    db: AsyncSession,
    *,
    cohort: CohortORM,
    owner_id: uuid.UUID,
    config: ex.EffectiveConfig,
    receptor: ex.ReceptorProvenance,
    planned: list[ex.PlannedRow],
    snapshot_total_rows: int,
    fingerprint: str,
) -> CohortRunORM:
    """
    Crea la corrida y sus filas. **Una transacción, o nada.**

    No hace `commit`: lo cierra `get_db`. Si algo falla después —construir la
    respuesta, por ejemplo— el `rollback` se lleva la corrida entera y no queda
    una corrida sin filas fingiendo que tiene trabajo.
    """
    from core.database import flush_with_retry

    ahora = ex.utc_now()
    corrida = CohortRunORM(
        id=uuid.uuid4(),
        cohort_id=cohort.id,
        user_id=owner_id,
        status=ex.RUN_QUEUED,
        cohort_fingerprint=cohort.cohort_fingerprint,
        run_fingerprint=fingerprint,
        effective_config_json=config.as_dict(),
        receptor_provenance_json=receptor.as_dict(),
        receptor_prepared_bytes=receptor.prepared_bytes,
        # `total_rows` es el del ARCHIVO, no el del trabajo: es lo que permite
        # ver cuántas quedaron fuera por no ser elegibles.
        total_rows=snapshot_total_rows,
        eligible_rows=len(planned),
        completed_rows=0,
        failed_rows=0,
        not_evaluated_rows=0,
        cancel_requested=False,
        created_at=ahora,
    )
    db.add(corrida)
    await flush_with_retry(db)

    for fila in planned:
        db.add(
            CohortRunRowORM(
                id=uuid.uuid4(),
                run_id=corrida.id,
                source_row_index=fila.source_row_index,
                canonical_smiles=fila.canonical_smiles,
                source_name=fila.source_name,
                control_role=fila.control_role,
                active_label=fila.active_label,
                duplicate_of_row=fila.duplicate_of_row,
                status=ex.ROW_PENDING,
                reused_from_row=(
                    fila.reused_from_row
                    if fila.reused_from_row is not None
                    and fila.reused_from_row != fila.source_row_index
                    else None
                ),
            )
        )
    await flush_with_retry(db)
    return corrida


# ── Lectura ──────────────────────────────────────────────────────────


async def get_run(
    db: AsyncSession, *, run_id: uuid.UUID, owner_id: uuid.UUID
) -> CohortRunORM | None:
    """
    Una corrida del dueño, o `None`.

    Como en 5B: ajena e inexistente contestan lo mismo. Un 403 confirmaría que
    ese identificador existe en esta máquina.
    """
    return await db.scalar(
        select(CohortRunORM).where(
            CohortRunORM.id == run_id, CohortRunORM.user_id == owner_id
        )
    )


async def list_rows(db: AsyncSession, run_id: uuid.UUID) -> list[CohortRunRowORM]:
    resultado = await db.execute(
        select(CohortRunRowORM)
        .where(CohortRunRowORM.run_id == run_id)
        .order_by(CohortRunRowORM.source_row_index.asc())
    )
    return list(resultado.scalars().all())


async def count_by_status(db: AsyncSession, run_id: uuid.UUID) -> dict[str, int]:
    resultado = await db.execute(
        select(CohortRunRowORM.status, func.count())
        .where(CohortRunRowORM.run_id == run_id)
        .group_by(CohortRunRowORM.status)
    )
    return {estado: int(total) for estado, total in resultado.all()}


# ── Escrituras de estado, cada una en su sesión ──────────────────────


async def _set_row(row_id: uuid.UUID, **campos: Any) -> None:
    from core.database import get_db_session

    async with get_db_session() as db:
        await db.execute(
            update(CohortRunRowORM).where(CohortRunRowORM.id == row_id).values(**campos)
        )


async def _set_run(run_id: uuid.UUID, **campos: Any) -> None:
    from core.database import get_db_session

    async with get_db_session() as db:
        await db.execute(
            update(CohortRunORM).where(CohortRunORM.id == run_id).values(**campos)
        )


async def refresh_counters(run_id: uuid.UUID) -> dict[str, int]:
    """
    Recalcula los contadores DESDE las filas y los persiste.

    Los contadores son derivados, siempre. Un contador que se incrementa a mano
    y sobrevive a un corte a mitad afirma un progreso que las filas no
    respaldan; recalcularlos desde la única fuente que sí sobrevivió es lo que
    permite que el arranque diga la verdad.
    """
    from core.database import get_db_session

    async with get_db_session() as db:
        conteo = await count_by_status(db, run_id)
        await db.execute(
            update(CohortRunORM)
            .where(CohortRunORM.id == run_id)
            .values(
                completed_rows=conteo.get(ex.ROW_COMPLETED, 0)
                + conteo.get(ex.ROW_DUPLICATE_REUSED, 0),
                failed_rows=conteo.get(ex.ROW_FAILED, 0),
                not_evaluated_rows=conteo.get(ex.ROW_NOT_EVALUATED, 0),
            )
        )
    return conteo


async def _cancel_requested(run_id: uuid.UUID) -> bool:
    from core.database import get_db_session

    async with get_db_session() as db:
        return bool(
            await db.scalar(
                select(CohortRunORM.cancel_requested).where(CohortRunORM.id == run_id)
            )
        )


# ── El bucle ─────────────────────────────────────────────────────────


async def execute_run(run_id: uuid.UUID, *, workers: int) -> None:
    """
    Ejecuta las filas pendientes de una corrida. Idempotente por diseño.

    Sólo toca filas `pending` o `interrupted`: las `completed` de un intento
    anterior no se repiten. Por eso esta misma función sirve para arrancar y
    para reanudar — no hay dos caminos que puedan divergir.
    """
    from core.database import get_db_session

    async with get_db_session() as db:
        corrida = await db.get(CohortRunORM, run_id)
        if corrida is None:
            return
        config = ex.EffectiveConfig(
            grid_center=tuple(corrida.effective_config_json["grid_center"]),  # type: ignore[arg-type]
            grid_size=tuple(corrida.effective_config_json["grid_size"]),  # type: ignore[arg-type]
            grid_origin=corrida.effective_config_json.get("grid_origin", "cohorte"),
            docking_engine=corrida.effective_config_json["docking_engine"],
            engine_version=corrida.effective_config_json.get("engine_version"),
            exhaustiveness=int(corrida.effective_config_json["exhaustiveness"]),
            num_poses=int(corrida.effective_config_json["num_poses"]),
            seed=corrida.effective_config_json.get("seed"),
        )
        receptor = ex.ReceptorProvenance(
            pdb_id=corrida.receptor_provenance_json["pdb_id"],
            chain=corrida.receptor_provenance_json.get("chain"),
            prepared_sha256=corrida.receptor_provenance_json["prepared_sha256"],
            prepared_size_bytes=corrida.receptor_provenance_json.get("prepared_size_bytes", 0),
            prepared_object=corrida.receptor_provenance_json.get("prepared_object", ""),
            source_sha256=corrida.receptor_provenance_json.get("source_sha256"),
            catalog_target_id=corrida.receptor_provenance_json.get("catalog_target_id"),
            prepared_bytes=bytes(corrida.receptor_prepared_bytes or b""),
        )
        owner = str(corrida.user_id)
        todas = await list_rows(db, run_id)

    if not receptor.prepared_bytes:
        await _set_run(
            run_id,
            status=ex.RUN_INTERRUPTED,
            last_error=(
                "La corrida fue creada antes de que MolDesign conservara el receptor "
                "preparado inmutable. No se reanuda contra el archivo mutable del catálogo."
            ),
        )
        return

    await _set_run(run_id, status=ex.RUN_RUNNING, started_at=ex.utc_now())

    pendientes = [fila for fila in todas if fila.status in ex.ROW_RESUMABLE]
    # Las que ejecutan de verdad van primero: una fila que reutiliza sólo puede
    # copiar un resultado que ya exista.
    ejecutoras = [fila for fila in pendientes if fila.reused_from_row is None]
    reutilizadoras = [fila for fila in pendientes if fila.reused_from_row is not None]

    semaforo = asyncio.Semaphore(max(1, workers))
    #: `source_row_index` → `(molecule_id, result_id, estado)` de lo ya ejecutado.
    resultados: dict[int, tuple[uuid.UUID | None, uuid.UUID | None, str]] = {
        fila.source_row_index: (fila.molecule_id, fila.result_id, fila.status)
        for fila in todas
        if fila.status == ex.ROW_COMPLETED
    }

    async def _una(fila: CohortRunRowORM) -> None:
        if await _cancel_requested(run_id):
            await _set_row(
                fila.id,
                status=ex.ROW_CANCELLED,
                error_code=ex.ERROR_CANCELADA,
                finished_at=ex.utc_now(),
            )
            return

        async with semaforo:
            # Cancelación comprobada otra vez: entre la cola y el turno de esta
            # fila pueden pasar minutos.
            if await _cancel_requested(run_id):
                await _set_row(
                    fila.id,
                    status=ex.ROW_CANCELLED,
                    error_code=ex.ERROR_CANCELADA,
                    finished_at=ex.utc_now(),
                )
                return

            # `running` ANTES de ejecutar, y confirmado. Ver el docstring.
            await _set_row(fila.id, status=ex.ROW_RUNNING, started_at=ex.utc_now())
            try:
                resultado = await ex._evaluate_one(
                    canonical_smiles=fila.canonical_smiles,
                    molecule_name=fila.source_name,
                    receptor=receptor,
                    config=config,
                    user_id=owner,
                )
                estado, codigo, detalle = ex.classify_outcome(resultado)
                molecule_id = resultado.get("molecule_id") if resultado else None
                # El resultado de ESTA ejecución, por su identificador. NO se
                # busca «el más reciente de esta molécula»: dos corridas de la
                # misma cohorte, o una molécula compartida con una evaluación
                # individual, harían que esa búsqueda devolviera el resultado de
                # otra corrida y la evidencia describiría algo que no ocurrió.
                # Corridas nuevas apuntan al snapshot inmutable. El fallback
                # conserva compatibilidad con evaluadores antiguos y tests de
                # integración que sólo devuelven ``evaluation_result_id``.
                result_id = (
                    resultado.get("evaluation_run_id")
                    or resultado.get("evaluation_result_id")
                ) if resultado else None
            except Exception as exc:  # una fila que revienta NO tumba la cohorte
                log.warning(
                    "cohort_run_row_failed",
                    run_id=str(run_id),
                    row=fila.source_row_index,
                    error=str(exc)[:200],
                )
                estado, codigo, detalle = ex.ROW_FAILED, ex.ERROR_PIPELINE, str(exc)[:2000]
                molecule_id = None
                result_id = None

            identificador = uuid.UUID(str(molecule_id)) if molecule_id else None
            identificador_resultado = uuid.UUID(str(result_id)) if result_id else None
            await _set_row(
                fila.id,
                status=estado,
                molecule_id=identificador,
                result_id=identificador_resultado,
                error_code=codigo,
                error_detail=detalle,
                finished_at=ex.utc_now(),
            )
            resultados[fila.source_row_index] = (identificador, identificador_resultado, estado)

    # Las ejecutoras, en paralelo acotado. `gather` con `return_exceptions` para
    # que una excepción escapada no cancele a las hermanas.
    await asyncio.gather(*(_una(fila) for fila in ejecutoras), return_exceptions=True)

    # Y ahora las que reutilizan: heredan el resultado de su ejecutora.
    for fila in reutilizadoras:
        # `or -1` sería un fallo silencioso: la fila 0 es un índice válido y
        # `0 or -1` vale -1. La comprobación es contra None, explícita.
        indice_origen = fila.reused_from_row
        origen = resultados.get(indice_origen) if indice_origen is not None else None
        if origen and origen[2] == ex.ROW_COMPLETED:
            await _set_row(
                fila.id,
                status=ex.ROW_DUPLICATE_REUSED,
                molecule_id=origen[0],
                result_id=origen[1],
                finished_at=ex.utc_now(),
            )
        elif await _cancel_requested(run_id):
            await _set_row(
                fila.id,
                status=ex.ROW_CANCELLED,
                error_code=ex.ERROR_CANCELADA,
                finished_at=ex.utc_now(),
            )
        else:
            # Su ejecutora no produjo resultado. NO se reintenta la molécula por
            # la puerta de atrás: se declara con el mismo motivo.
            await _set_row(
                fila.id,
                status=ex.ROW_FAILED,
                error_code=ex.ERROR_SIN_RESULTADO,
                error_detail=(
                    f"La fila {fila.reused_from_row}, que acopla esta misma molécula, "
                    "no produjo un resultado utilizable."
                ),
                finished_at=ex.utc_now(),
            )

    conteo = await refresh_counters(run_id)
    cancelada = await _cancel_requested(run_id)
    estado_final = ex.decide_run_status(
        completed=conteo.get(ex.ROW_COMPLETED, 0) + conteo.get(ex.ROW_DUPLICATE_REUSED, 0),
        failed=conteo.get(ex.ROW_FAILED, 0),
        not_evaluated=conteo.get(ex.ROW_NOT_EVALUATED, 0),
        cancelled=conteo.get(ex.ROW_CANCELLED, 0),
        cancel_requested=cancelada,
    )
    await _set_run(run_id, status=estado_final, finished_at=ex.utc_now())
    log.info(
        "cohort_run_finished",
        run_id=str(run_id),
        status=estado_final,
        completed=conteo.get(ex.ROW_COMPLETED, 0),
        reused=conteo.get(ex.ROW_DUPLICATE_REUSED, 0),
        failed=conteo.get(ex.ROW_FAILED, 0),
        not_evaluated=conteo.get(ex.ROW_NOT_EVALUATED, 0),
    )


async def schedule(run_id: uuid.UUID, *, workers: int) -> None:
    """
    Encola la ejecución. **Sólo se llama después de persistir.**

    Es `async` a propósito: `BackgroundTasks` ejecuta las funciones síncronas en
    un hilo del pool, donde no hay bucle de eventos y `create_task` no existe.
    Siendo corrutina, Starlette la espera dentro del bucle y la tarea nace donde
    tiene que nacer.

    La tarea vive en el proceso; la corrida vive en la base. Si el proceso
    muere, la tarea desaparece y la corrida queda `running` en disco — que es
    justo lo que el arranque sabe reconciliar.
    """
    clave = str(run_id)
    viva = _TAREAS.get(clave)
    if viva is not None and not viva.done():
        return

    async def _envoltura() -> None:
        try:
            await execute_run(run_id, workers=workers)
        except Exception as exc:
            log.error("cohort_run_crashed", run_id=clave, error=str(exc)[:300])
            await _set_run(
                run_id,
                status=ex.RUN_INTERRUPTED,
                last_error=str(exc)[:2000],
                finished_at=ex.utc_now(),
            )
        finally:
            _TAREAS.pop(clave, None)

    _TAREAS[clave] = asyncio.create_task(_envoltura())


# ── Reconciliación al arrancar ───────────────────────────────────────


async def reconcile_interrupted_runs() -> int:
    """
    Ninguna corrida puede fingir que sigue.

    Al arrancar, todo lo que quedó `queued` o `running` en disco pertenece a un
    proceso que ya no existe. Se marca `interrupted` —que dice lo único cierto:
    no sabemos cómo acabó— y se recalculan los contadores desde las filas.

    Lo `completed` se conserva intacto. Reanudar después no repetirá ese
    trabajo.
    """
    from core.database import get_db_session

    async with get_db_session() as db:
        corridas = list(
            (
                await db.execute(
                    select(CohortRunORM).where(
                        CohortRunORM.status.in_(ex.RUN_ACTIVE_STATUSES)
                    )
                )
            )
            .scalars()
            .all()
        )
        if not corridas:
            return 0

        for corrida in corridas:
            await db.execute(
                update(CohortRunRowORM)
                .where(
                    CohortRunRowORM.run_id == corrida.id,
                    CohortRunRowORM.status == ex.ROW_RUNNING,
                )
                .values(status=ex.ROW_INTERRUPTED, finished_at=ex.utc_now())
            )
            conteo = await count_by_status(db, corrida.id)
            corrida.status = ex.RUN_INTERRUPTED
            corrida.completed_rows = conteo.get(ex.ROW_COMPLETED, 0) + conteo.get(
                ex.ROW_DUPLICATE_REUSED, 0
            )
            corrida.failed_rows = conteo.get(ex.ROW_FAILED, 0)
            corrida.not_evaluated_rows = conteo.get(ex.ROW_NOT_EVALUATED, 0)
            corrida.last_error = (
                "La aplicación se cerró mientras esta corrida estaba en marcha. "
                "Las filas que estaban acoplando quedan como interrumpidas; las "
                "terminadas se conservan."
            )

    log.info("cohort_runs_reconciled", count=len(corridas))
    return len(corridas)
