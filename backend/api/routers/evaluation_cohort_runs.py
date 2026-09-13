"""
Superficie HTTP de las corridas de cohorte.

    POST /evaluation/cohorts/{cohort_id}/runs   abrir (202)
    GET  /evaluation/cohort-runs/{run_id}       estado, progreso, procedencia, filas
    POST /evaluation/cohort-runs/{run_id}/resume
    POST /evaluation/cohort-runs/{run_id}/cancel

# Por qué `202` y no `200`

Abrir una corrida no la termina. El 202 dice exactamente eso: se aceptó el
trabajo, está persistido, y el resultado se consulta después. Un 200 sugeriría
que ya hay algo que leer.

# Qué se comprueba ANTES de escribir nada

Propiedad, que la cohorte siga `ready`, que haya filas elegibles y que la caja
se pueda resolver. Si falta el PDBQT, se prepara una vez con esa configuración
antes del primer `INSERT`; sólo después se congela su SHA-256 y se abre la
corrida. Un fallo de Meeko deja cero corridas, no una corrida parcial.

# Qué NO hace

No prepara por molécula, no reinterpreta el archivo de la cohorte, no modifica
la cohorte congelada y no devuelve ningún score. Terminar un docking **no
demuestra actividad**, y esta superficie no dice lo contrario en ninguna parte.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_optional
from services.targets.access import get_target_for_user
from core.database import get_db
from core.models import CohortORM, UserORM
from services.cohort import execution as ex
from services.cohort import repository as cohort_repo
from services.cohort import dossier as cohort_dossier
from services.cohort import evidence as cohort_evidence
from services.cohort import runs as run_repo
from services.cohort.schemas import COHORT_STATUS_READY
from utils.logger import get_logger

log = get_logger(__name__)

#: Las tres rutas que cuelgan de la corrida, no de la cohorte.
router = APIRouter(prefix="/cohort-runs", tags=["Cohortes"])

#: La de apertura cuelga de la cohorte: es una acción SOBRE ella.
cohort_router = APIRouter(prefix="/cohorts", tags=["Cohortes"])


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CohortRunRowRead(_Base):
    """Una fila de la corrida. Sin scores: el estado no es una medida."""

    source_row_index: int
    canonical_smiles: str
    source_name: str | None = None
    control_role: str
    active_label: bool | None = None
    #: Del snapshot: qué fila del ARCHIVO repite esta molécula.
    duplicate_of_row: int | None = None
    status: str
    molecule_id: uuid.UUID | None = None
    result_id: uuid.UUID | None = None
    #: De ejecución: qué fila acopló de verdad el resultado que ésta reutiliza.
    reused_from_row: int | None = None
    error_code: str | None = None
    error_detail: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class CohortRunProgress(_Base):
    """
    Progreso, con los denominadores dichos en voz alta.

    `total_rows` es el del ARCHIVO y `eligible_rows` el del trabajo: la
    diferencia son las filas que el preflight declaró no elegibles y que nunca
    van a ejecutarse. No desaparecen del recuento porque desaparecer del
    recuento es cómo una cobertura del 60 % se cuenta como del 100 %.
    """

    total_rows: int
    eligible_rows: int
    completed_rows: int
    failed_rows: int
    not_evaluated_rows: int
    pending_rows: int
    running_rows: int
    duplicate_reused_rows: int
    cancelled_rows: int
    interrupted_rows: int


class CohortRunRead(_Base):
    id: uuid.UUID
    cohort_id: uuid.UUID
    status: str
    cohort_fingerprint: str
    run_fingerprint: str
    cancel_requested: bool
    effective_config: dict[str, Any]
    receptor_provenance: dict[str, Any]
    progress: CohortRunProgress
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    last_error: str | None = None
    rows: list[CohortRunRowRead] = Field(default_factory=list)


class CohortRunAccepted(_Base):
    """Lo que devuelve una apertura o una reanudación aceptada."""

    run_id: uuid.UUID
    cohort_id: uuid.UUID
    status: str
    run_fingerprint: str
    eligible_rows: int
    workers: int


def _iso(valor) -> str | None:
    if valor is None:
        return None
    from datetime import timezone

    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc).isoformat()
    return valor.astimezone(timezone.utc).isoformat()


async def _leer(db: AsyncSession, corrida) -> CohortRunRead:
    filas = await run_repo.list_rows(db, corrida.id)
    conteo: dict[str, int] = {}
    for fila in filas:
        conteo[fila.status] = conteo.get(fila.status, 0) + 1

    return CohortRunRead(
        id=corrida.id,
        cohort_id=corrida.cohort_id,
        status=corrida.status,
        cohort_fingerprint=corrida.cohort_fingerprint,
        run_fingerprint=corrida.run_fingerprint,
        cancel_requested=bool(corrida.cancel_requested),
        effective_config=corrida.effective_config_json,
        receptor_provenance=corrida.receptor_provenance_json,
        progress=CohortRunProgress(
            total_rows=corrida.total_rows,
            eligible_rows=corrida.eligible_rows,
            completed_rows=conteo.get(ex.ROW_COMPLETED, 0),
            failed_rows=conteo.get(ex.ROW_FAILED, 0),
            not_evaluated_rows=conteo.get(ex.ROW_NOT_EVALUATED, 0),
            pending_rows=conteo.get(ex.ROW_PENDING, 0),
            running_rows=conteo.get(ex.ROW_RUNNING, 0),
            duplicate_reused_rows=conteo.get(ex.ROW_DUPLICATE_REUSED, 0),
            cancelled_rows=conteo.get(ex.ROW_CANCELLED, 0),
            interrupted_rows=conteo.get(ex.ROW_INTERRUPTED, 0),
        ),
        created_at=_iso(corrida.created_at),
        started_at=_iso(corrida.started_at),
        finished_at=_iso(corrida.finished_at),
        last_error=corrida.last_error,
        rows=[
            CohortRunRowRead(
                source_row_index=fila.source_row_index,
                canonical_smiles=fila.canonical_smiles,
                source_name=fila.source_name,
                control_role=fila.control_role,
                active_label=fila.active_label,
                duplicate_of_row=fila.duplicate_of_row,
                status=fila.status,
                molecule_id=fila.molecule_id,
                result_id=fila.result_id,
                reused_from_row=fila.reused_from_row,
                error_code=fila.error_code,
                error_detail=fila.error_detail,
                started_at=_iso(fila.started_at),
                finished_at=_iso(fila.finished_at),
            )
            for fila in filas
        ],
    )


@cohort_router.post(
    "/{cohort_id}/runs",
    summary="Abrir una corrida sobre una cohorte congelada",
    response_model=CohortRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def open_run(
    cohort_id: uuid.UUID,
    workers: int = Query(
        ex.DEFAULT_RUN_WORKERS,
        ge=1,
        le=ex.MAX_RUN_WORKERS,
        description="Paralelismo. Operacional: NO entra en el `run_fingerprint`.",
    ),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> CohortRunAccepted:
    """
    Congela el CÓMO y encola el trabajo. No ejecuta nada de forma síncrona.

    Todo lo científico sale del snapshot de la cohorte. El archivo original no
    se vuelve a leer y la elegibilidad no se recalcula: se ejecuta lo que se
    aceptó, no lo que hoy parecería aceptable.
    """
    owner_id = await cohort_repo.resolve_owner_id(db, current_user)
    cohorte = await db.get(CohortORM, cohort_id)
    if cohorte is None or cohorte.user_id != owner_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe la cohorte solicitada.")

    if cohorte.status != COHORT_STATUS_READY:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": ex.BLOQUEO_COHORTE_NO_LISTA,
                "message": f"La cohorte está en estado `{cohorte.status}` y no se puede ejecutar.",
            },
        )

    activa = await run_repo.active_run_for(db, cohort_id)
    if activa is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": ex.BLOQUEO_CORRIDA_ACTIVA,
                "message": (
                    "Esta cohorte ya tiene una corrida en marcha. Dos corridas simultáneas "
                    "competirían por el mismo motor local y ninguna de las dos sería "
                    "reproducible."
                ),
                "run_id": str(activa.id),
                "run_status": activa.status,
            },
        )

    snapshot = cohorte.preflight_snapshot_json or {}
    estudio = cohorte.normalized_study_json or {}
    planificadas = ex.plan_rows(snapshot)
    if not planificadas:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": ex.BLOQUEO_SIN_FILAS_ELEGIBLES,
                "message": "La cohorte congelada no tiene ninguna fila elegible que ejecutar.",
            },
        )

    receptor_declarado = (estudio.get("receptor") or {})
    pdb_id = str(receptor_declarado.get("pdb_id") or "")
    from db.repository import Repository

    target = (
        await get_target_for_user(
            Repository(db), pdb_id, current_user, allow_missing=True
        )
        if pdb_id else None
    )
    try:
        # La configuración se resuelve una vez y gobierna también la eventual
        # preparación automática; luego el PDBQT queda congelado por su hash.
        config = ex.resolve_effective_config(estudio, target)
        try:
            receptor = ex.resolve_receptor(
                pdb_id, receptor_declarado.get("chain"), target
            )
        except ex.ExecutionBlocked as receptor_ausente:
            if receptor_ausente.code != ex.BLOQUEO_RECEPTOR_AUSENTE:
                raise
            from services.docking.preparer import prepare_target

            chain = str(
                receptor_declarado.get("chain")
                or (getattr(target, "chain", None) if target is not None else "")
                or "A"
            )
            try:
                await prepare_target(
                    pdb_id=pdb_id,
                    chain_id=chain,
                    center=config.grid_center,
                    size=config.grid_size,
                    force_reprepare=False,
                    cofactors_whitelist=(
                        list(getattr(target, "cofactors_whitelist", None) or [])
                        if target is not None else None
                    ),
                )
            except Exception as exc:
                raise ex.ExecutionBlocked(
                    ex.BLOQUEO_RECEPTOR_AUSENTE,
                    f"No se pudo preparar el receptor {pdb_id}: {exc}",
                ) from exc
            receptor = ex.resolve_receptor(pdb_id, chain, target)
    except ex.ExecutionBlocked as bloqueo:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": bloqueo.code, "message": bloqueo.message},
        ) from bloqueo

    huella = ex.run_fingerprint(
        cohort_fingerprint=cohorte.cohort_fingerprint, config=config, receptor=receptor
    )
    corrida = await run_repo.create_run(
        db,
        cohort=cohorte,
        owner_id=owner_id,
        config=config,
        receptor=receptor,
        planned=planificadas,
        snapshot_total_rows=int((snapshot.get("summary") or {}).get("total_rows", 0)),
        fingerprint=huella,
    )

    efectivos = ex.clamp_workers(workers)
    run_id = corrida.id

    # ── La frontera que hace segura la ejecución ──────────────────────
    # El `commit` es EXPLÍCITO aquí, en contra de la costumbre de dejárselo a
    # `get_db`, porque el orden es parte del contrato: la corrida y sus filas
    # tienen que estar en disco antes de que nadie las ejecute. El ejecutor abre
    # su propia sesión; una corrida sin confirmar no existe para él.
    #
    # `BackgroundTasks` NO sirve para esto: en esta versión de FastAPI las
    # tareas de fondo corren ANTES de que se cierren las dependencias con
    # `yield`, es decir, antes del commit. Se comprobó, no se supuso.
    #
    # Si algo fallara después de este commit, queda una corrida `queued` que el
    # arranque reconcilia a `interrupted` y se puede reanudar. Es el fallo
    # barato; el caro sería ejecutar sobre algo que no está guardado.
    await db.commit()
    await run_repo.schedule(run_id, workers=efectivos)

    log.info(
        "cohort_run_opened",
        run_id=str(run_id),
        cohort_id=str(cohort_id),
        run_fingerprint=huella,
        eligible_rows=len(planificadas),
        receptor=pdb_id,
        prepared_sha256=receptor.prepared_sha256,
        workers=efectivos,
    )
    return CohortRunAccepted(
        run_id=run_id,
        cohort_id=cohort_id,
        status=ex.RUN_QUEUED,
        run_fingerprint=huella,
        eligible_rows=len(planificadas),
        workers=efectivos,
    )


@cohort_router.get(
    "/{cohort_id}/runs/latest",
    summary="Última corrida durable de una cohorte",
    response_model=CohortRunRead,
)
async def read_latest_run(
    cohort_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> CohortRunRead:
    owner_id = await cohort_repo.resolve_owner_id(db, current_user)
    corrida = await run_repo.latest_run_for(
        db, cohort_id=cohort_id, owner_id=owner_id
    )
    if corrida is None:
        # Cohorte inexistente, ajena o todavía no ejecutada: no se revela cuál.
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No existe una corrida para la cohorte solicitada.",
        )
    return await _leer(db, corrida)


@router.get(
    "/{run_id}",
    summary="Estado, progreso, configuración efectiva, procedencia y filas",
    response_model=CohortRunRead,
)
async def read_run(
    run_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> CohortRunRead:
    owner_id = await cohort_repo.resolve_owner_id(db, current_user)
    corrida = await run_repo.get_run(db, run_id=run_id, owner_id=owner_id)
    if corrida is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe la corrida solicitada.")
    return await _leer(db, corrida)


@router.post(
    "/{run_id}/resume",
    summary="Reanudar una corrida interrumpida o con excepciones",
    response_model=CohortRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resume_run(
    run_id: uuid.UUID,
    workers: int = Query(ex.DEFAULT_RUN_WORKERS, ge=1, le=ex.MAX_RUN_WORKERS),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> CohortRunAccepted:
    """
    Retoma lo que quedó pendiente. **No repite lo que ya terminó.**

    No reinterpreta la cohorte: las filas ya están en la base desde que se abrió
    la corrida, con su molécula congelada. Reanudar es volver a recorrer las
    `pending` e `interrupted`, nada más.
    """
    owner_id = await cohort_repo.resolve_owner_id(db, current_user)
    corrida = await run_repo.get_run(db, run_id=run_id, owner_id=owner_id)
    if corrida is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe la corrida solicitada.")

    reanudables = (ex.RUN_INTERRUPTED, ex.RUN_COMPLETED_WITH_EXCEPTIONS)
    if corrida.status not in reanudables:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "message": (
                    f"Una corrida en estado `{corrida.status}` no se reanuda. Sólo se "
                    "reanuda lo que quedó a medias: `interrupted` o "
                    "`completed_with_exceptions`."
                ),
                "status": corrida.status,
            },
        )

    filas = await run_repo.list_rows(db, run_id)
    reintentables = [fila for fila in filas if fila.status in ex.ROW_RESUMABLE]
    if not reintentables:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "message": (
                    "No queda ninguna fila pendiente ni interrumpida. Las que fallaron no "
                    "se reintentan en silencio: eso convertiría un fallo declarado en un "
                    "resultado nuevo sin que nadie lo pidiera."
                ),
                "status": corrida.status,
            },
        )

    corrida.status = ex.RUN_QUEUED
    corrida.cancel_requested = False
    corrida.finished_at = None
    corrida.last_error = None

    efectivos = ex.clamp_workers(workers)
    # Misma frontera que al abrir: primero el estado en disco, luego el trabajo.
    await db.commit()
    await run_repo.schedule(run_id, workers=efectivos)
    log.info(
        "cohort_run_resumed",
        run_id=str(run_id),
        pendientes=len(reintentables),
        workers=efectivos,
    )
    return CohortRunAccepted(
        run_id=corrida.id,
        cohort_id=corrida.cohort_id,
        status=ex.RUN_QUEUED,
        run_fingerprint=corrida.run_fingerprint,
        eligible_rows=len(reintentables),
        workers=efectivos,
    )


@router.post(
    "/{run_id}/cancel",
    summary="Pedir la cancelación de una corrida",
    response_model=CohortRunRead,
)
async def cancel_run(
    run_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> CohortRunRead:
    """
    Marca la INTENCIÓN de cancelar. No mata nada a medio acoplar.

    El ejecutor la consulta antes de empezar cada fila: no se inician filas
    nuevas, y las que ya terminaron se conservan con su resultado. Interrumpir
    un docking en curso no ahorraría nada y dejaría una fila cuyo estado nadie
    puede afirmar.
    """
    owner_id = await cohort_repo.resolve_owner_id(db, current_user)
    corrida = await run_repo.get_run(db, run_id=run_id, owner_id=owner_id)
    if corrida is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe la corrida solicitada.")

    corrida.cancel_requested = True
    if corrida.status == ex.RUN_QUEUED:
        # Todavía no había empezado: se puede cerrar aquí mismo, sin dejar
        # filas colgando.
        corrida.status = ex.RUN_CANCELLED
        corrida.finished_at = ex.utc_now()

    log.info("cohort_run_cancel_requested", run_id=str(run_id), status=corrida.status)
    return await _leer(db, corrida)


# ── Evidencia y dossier ──────────────────────────────────────────────


async def _run_y_cohorte(db: AsyncSession, run_id: uuid.UUID, current_user):
    """Corrida y cohorte del dueño, o 404. Nunca 403: ver `repository.py`."""
    owner_id = await cohort_repo.resolve_owner_id(db, current_user)
    corrida = await run_repo.get_run(db, run_id=run_id, owner_id=owner_id)
    if corrida is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe la corrida solicitada.")
    cohorte = await db.get(CohortORM, corrida.cohort_id)
    if cohorte is None or cohorte.user_id != owner_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe la cohorte de esta corrida.")
    return corrida, cohorte


#: Estados en los que la corrida ya no va a cambiar por sí sola. Un dossier de
#: una corrida a medias documentaría un progreso, no un resultado.
_TERMINALES = (
    ex.RUN_COMPLETED,
    ex.RUN_COMPLETED_WITH_EXCEPTIONS,
    ex.RUN_FAILED,
    ex.RUN_CANCELLED,
    ex.RUN_INTERRUPTED,
)


def _exigir_terminal(corrida) -> None:
    if corrida.status in _TERMINALES:
        return
    raise HTTPException(
        status.HTTP_409_CONFLICT,
        {
            "code": "CORRIDA_NO_TERMINAL",
            "message": (
                f"La corrida está en `{corrida.status}` y todavía puede cambiar. Un dossier "
                "de una corrida en marcha documentaría un progreso, no un resultado: espera "
                "a que termine o cancélala."
            ),
            "status": corrida.status,
        },
    )


@router.get(
    "/{run_id}/evidence",
    summary="Resumen científico de la corrida (cobertura, evidencia y métricas)",
)
async def read_evidence(
    run_id: uuid.UUID,
    sort: str | None = Query(
        None,
        description=(
            "Único orden ofrecido: `afinidad_vina_observada`. Es un ORDEN, no un "
            "veredicto: no significa «mejores fármacos» ni probabilidad de éxito."
        ),
    ),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Cobertura con denominadores, evidencia por molécula y métricas etiquetadas.

    La única magnitud por molécula es la **afinidad Vina observada**. No hay
    `total_score`, ni ranking de candidatos, ni puntuación agregada: completar
    un acoplamiento no demuestra actividad.
    """
    if sort is not None and sort != cohort_evidence.SORT_BY_OBSERVED_AFFINITY:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            (
                f"`sort` sólo admite `{cohort_evidence.SORT_BY_OBSERVED_AFFINITY}`. "
                "No hay ningún otro criterio de orden en esta superficie."
            ),
        )
    corrida, cohorte = await _run_y_cohorte(db, run_id, current_user)
    return await cohort_evidence.build_run_evidence(db, run=corrida, cohort=cohorte, sort=sort)


async def _dossier(db: AsyncSession, run_id: uuid.UUID, current_user):
    corrida, cohorte = await _run_y_cohorte(db, run_id, current_user)
    _exigir_terminal(corrida)
    evidencia = await cohort_evidence.build_run_evidence(
        db, run=corrida, cohort=cohorte, sort=cohort_evidence.SORT_BY_OBSERVED_AFFINITY
    )
    return corrida, cohorte, evidencia


@router.post(
    "/{run_id}/dossier/preview",
    summary="Dossier de cohorte en PDF (inline)",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def dossier_preview(
    run_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    corrida, cohorte, evidencia = await _dossier(db, run_id, current_user)
    pdf = cohort_dossier.render_cohort_dossier_pdf(evidencia)
    nombre = f"dossier_cohorte_{cohort_repo.sanitize_source_filename(cohorte.name, maximo=60)}.pdf"
    log.info("cohort_dossier_preview", run_id=str(run_id), cohort_id=str(cohorte.id))
    return StreamingResponse(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{nombre}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post(
    "/{run_id}/dossier/package",
    summary="Paquete verificable de la cohorte (ZIP con manifiesto y hashes)",
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}}},
)
async def dossier_package(
    run_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    corrida, cohorte, evidencia = await _dossier(db, run_id, current_user)
    pdf = cohort_dossier.render_cohort_dossier_pdf(evidencia).getvalue()
    datos, entradas, raiz = cohort_dossier.construir_paquete_cohorte(
        evidencia=evidencia, pdf_bytes=pdf, cohort=cohorte, run=corrida
    )
    ausentes = [e.path for e in entradas if e.estado != "REGISTRADO"]
    log.info(
        "cohort_dossier_package",
        run_id=str(run_id),
        archivos=len(entradas),
        ausentes=len(ausentes),
        bytes=len(datos),
    )
    return Response(
        content=datos,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{raiz}.zip"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
