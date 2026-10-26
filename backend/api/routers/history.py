"""
api/routers/history.py

Endpoints para consultar el historial de evaluaciones.

Permite a un usuario (autenticado u opcionalmente anónimo en dev)
ver sus evaluaciones pasadas con toda la trazabilidad científica.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from core.database import get_db
from core.models import (
    EvaluationRunORM,
    EvaluationResultORM,
    MoleculeORM,
    MoleculeStatus,
    TargetORM,
    UserORM,
)
from services.docking.protocolo_de_producto import describir_protocolo
from services.history import history_rows, render_history_receipt
from db.repository import Repository
from utils.instantes import instante_utc
from utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/history", tags=["Historial de evaluaciones"])


# ── Response schemas ──────────────────────────────────────────────────────────

class EvaluationSummary(BaseModel):
    """Resumen de una evaluación para la lista de historial."""
    molecule_id: str
    smiles: str
    name: str | None
    status: str
    target_pdb_id: str
    total_score: float | None
    affinity_kcal: float | None
    affinity_score: float | None
    adme_score: float | None
    druglikeness_score: float | None
    molecular_weight: float | None
    log_p: float | None
    lipinski_pass: bool | None
    qed: float | None
    sa_score: float | None
    blockchain_tx_id: str | None
    evaluated_at: str | None
    created_at: str
    #: HIST-INT-004. Identidad de la corrida que produjo estas cifras. `evaluation_runs`
    #: guarda el snapshot inmutable por `task_id` (EVAL-P0-02) y es la unica forma de
    #: reabrir ESTA corrida y no la ultima evaluacion de la misma molecula. Nullable: las
    #: filas anteriores al schema v11 no lo tienen.
    task_id: str | None
    #: Promovida a Moldex. La lista muestra todas las evaluaciones; sin este campo, una
    #: molecula que esta en Moldex y otra que no se veian identicas en el historial.
    is_saved: bool
    #: `False` si la corrida usó otra receta de receptor u otra calibración del
    #: ranking que las de hoy; `None` si no lo registró (p. ej. 1.0.1). Ver
    #: `services/docking/protocolo_de_producto.py`.
    protocolo_vigente: bool | None = None


class HistoryResponse(BaseModel):
    """Respuesta paginada del historial."""
    items: list[EvaluationSummary]
    total: int
    page: int
    page_size: int
    has_next: bool


class StatsResponse(BaseModel):
    """Estadísticas del usuario."""
    total_evaluations: int
    completed_evaluations: int
    failed_evaluations: int
    best_score: float | None
    avg_score: float | None
    unique_targets: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/evaluations",
    response_model=HistoryResponse,
    summary="Listar evaluaciones del usuario",
)
async def list_evaluations(
    page: int = Query(default=1, ge=1, description="Página"),
    page_size: int = Query(default=20, ge=1, le=100, description="Elementos por página"),
    status_filter: MoleculeStatus | None = Query(
        default=None, alias="status", description="Filtrar por estado"
    ),
    sort_by: str = Query(
        default="created_at",
        description=(
            "Campo de orden: created_at, total_score, affinity_kcal, "
            "molecular_weight, log_p, tpsa, qed, adme_score, "
            "druglikeness_score, affinity_score, gnn_score, sa_score"
        ),
    ),
    sort_order: str = Query(default="desc", description="asc o desc"),
    # ── Filtros ampliados: cualquier combinación que el usuario pida ──
    target_pdb_id: str | None = Query(
        default=None, description="Receptor (ej. 5HT1A, 7E2Y, CDK2)"
    ),
    min_score: float | None = Query(default=None, ge=0, le=100, description="total_score mínimo"),
    max_score: float | None = Query(default=None, ge=0, le=100, description="total_score máximo"),
    min_affinity: float | None = Query(default=None, description="afinidad mínima (kcal/mol, más negativo = mejor)"),
    max_affinity: float | None = Query(default=None, description="afinidad máxima (kcal/mol)"),
    min_mw: float | None = Query(default=None, description="peso molecular mínimo (Da)"),
    max_mw: float | None = Query(default=None, description="peso molecular máximo (Da)"),
    min_logp: float | None = Query(default=None, description="logP mínimo"),
    max_logp: float | None = Query(default=None, description="logP máximo"),
    min_tpsa: float | None = Query(default=None, description="TPSA mínima (A²)"),
    max_tpsa: float | None = Query(default=None, description="TPSA máxima (A²)"),
    lipinski_pass: bool | None = Query(default=None, description="Filtrar por Lipinski"),
    is_pains: bool | None = Query(default=None, description="Filtrar por alertas PAINS"),
    qed_min: float | None = Query(default=None, ge=0, le=1, description="QED mínimo"),
    adme_min: float | None = Query(default=None, ge=0, le=100, description="ADME score mínimo"),
    druglikeness_min: float | None = Query(default=None, ge=0, le=100, description="Drug-likeness score mínimo"),
    name_contains: str | None = Query(default=None, description="Subcadena en el nombre de la molécula"),
    smiles_contains: str | None = Query(default=None, description="Subcadena en el SMILES"),
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HistoryResponse:
    """
    Devuelve el historial de evaluaciones del usuario autenticado.

    POLÍTICA NUEVA: todas las evaluaciones se registran automáticamente
    (sin botón de guardar). is_saved solo significa "promovido a moldex".
    Filtros combinables: receptor, rangos de score/afinidad/MW/logP/TPSA,
    Lipinski, PAINS, QED, ADME, drug-likeness, nombre, SMILES, estado.
    """
    rows = history_rows(current_user.id)
    columns = rows.c
    query = select(rows)
    if status_filter:
        query = query.where(columns.status == status_filter.value)
    for key, value in (("target_pdb_id", target_pdb_id), ("name", name_contains), ("smiles", smiles_contains)):
        if value:
            query = query.where(columns[key].ilike(f"%{value}%"))
    bounds = (
        ("total_score", min_score, max_score), ("molecular_weight", min_mw, max_mw),
        ("log_p", min_logp, max_logp), ("tpsa", min_tpsa, max_tpsa),
        ("qed", qed_min, None), ("adme_score", adme_min, None),
        ("druglikeness_score", druglikeness_min, None),
    )
    for key, lower, upper in bounds:
        if lower is not None:
            query = query.where(columns[key] >= lower)
        if upper is not None:
            query = query.where(columns[key] <= upper)
    # Se conserva el contrato de afinidad: 'min' exige energía <= al umbral.
    if min_affinity is not None:
        query = query.where(columns.affinity_kcal <= min_affinity)
    if max_affinity is not None:
        query = query.where(columns.affinity_kcal >= max_affinity)
    for key, value in (("lipinski_pass", lipinski_pass), ("is_pains", is_pains)):
        if value is not None:
            query = query.where(columns[key] == value)
    total = (await db.scalar(select(func.count()).select_from(query.subquery()))) or 0
    sortable = {"created_at", "total_score", "affinity_kcal", "molecular_weight", "log_p", "tpsa",
                "qed", "adme_score", "druglikeness_score", "affinity_score", "gnn_score", "sa_score"}
    sort_column = columns[sort_by if sort_by in sortable else "created_at"]
    order = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    offset = (page - 1) * page_size
    query = query.order_by(order.nullslast(), columns.task_id.asc(), columns.molecule_id.asc()).offset(offset).limit(page_size)
    page_rows = (await db.execute(query)).mappings().all()
    # Los recibos añadidos posteriormente también pertenecen a su task_id.
    run_ids = [row["run_id"] for row in page_rows if row["run_id"] is not None]
    receipts = {}
    if run_ids:
        runs = (await db.execute(select(EvaluationRunORM).where(EvaluationRunORM.id.in_(run_ids)))).scalars()
        repo = Repository(db)
        for run in runs:
            receipts[run.id] = (await repo.materialize_run_snapshot(run)).get("blockchain_tx_id")
    items = []
    for row in page_rows:
        data = {key: row[key] for key in EvaluationSummary.model_fields if key not in {"protocolo_vigente"}}
        data["molecule_id"] = str(data["molecule_id"])
        # Con su zona (UTC): sin ella el Historial enseñaba la hora desplazada
        # (B03). `evaluated_at` viene escrito en la instantánea, sin zona.
        for key in ("created_at", "evaluated_at"):
            data[key] = instante_utc(data[key])
        data["created_at"] = data["created_at"] or ""
        if row["run_id"] is not None:
            data["blockchain_tx_id"] = receipts.get(row["run_id"])
        data["protocolo_vigente"] = describir_protocolo(
            row["docking_protocol"], row["weights_calibration_id"], row["target_family"],
        )["vigente"]
        items.append(EvaluationSummary(**data))
    return HistoryResponse(items=items, total=total, page=page, page_size=page_size,
                           has_next=(offset + page_size) < total)


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Estadísticas del usuario",
)
async def get_stats(
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    """Devuelve estadísticas agregadas de las evaluaciones del usuario."""

    rows = history_rows(current_user.id)
    c = rows.c
    from sqlalchemy import case
    result = (await db.execute(select(
        func.count(), func.sum(case((c.status == "evaluated", 1), else_=0)),
        func.sum(case((c.status == "failed", 1), else_=0)),
        func.max(c.total_score), func.avg(c.total_score), func.count(func.distinct(c.target_id)),
    ))).one()
    return StatsResponse(
        total_evaluations=result[0], completed_evaluations=result[1] or 0,
        failed_evaluations=result[2] or 0, best_score=result[3],
        avg_score=round(result[4], 2) if result[4] is not None else None,
        unique_targets=result[5],
    )


def _require_molecule_owner(mol: MoleculeORM | None, current_user: UserORM) -> None:
    """HIST-BE-002. Guardar exige ser el dueño, y nada más.

    La condición anterior era ``mol.user_id is not None and mol.user_id != current_user.id``
    y, en la rama siguiente, ``if mol.user_id is None: mol.user_id = current_user.id``: una
    molécula sin dueño la adoptaba cualquier cuenta que supiera su id. Mover trabajo del
    invitado a una cuenta registrada es ``POST /auth/traspaso`` —selectivo, transaccional e
    idempotente—, y esto era una segunda puerta que se lo saltaba.

    404 y no 403, como ya decidió BATCH-BE-002: el 403 confirma que la molécula existe.
    """
    if mol is None or mol.user_id is None or mol.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Molécula no encontrada")


@router.post(
    "/save/{molecule_id}",
    summary="Guardar molécula explícitamente en la cuenta",
)
async def save_molecule(
    molecule_id: uuid.UUID,
    name: str | None = Query(None, description="Nombre personalizado"),
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    task_id: str | None = Query(
        None,
        description=(
            "Corrida que se guarda. Una molécula se reevalúa muchas veces y cada "
            "evaluación guardada es una ficha propia en Moldex. Sin él se guarda "
            "la evaluación vigente de la molécula."
        ),
    ),
):
    """Guarda una evaluación en Moldex sin tocar las demás de la misma molécula."""
    mol = await db.get(MoleculeORM, molecule_id)
    _require_molecule_owner(mol, current_user)

    try:
        run = await Repository(db).save_evaluation_run(molecule_id, task_id, name)
    except LookupError:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada.") from None
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail="Sólo puede guardarse una evaluación terminada con éxito",
        ) from None
    await db.commit()
    return {
        "status": "saved",
        "molecule_id": str(molecule_id),
        "task_id": run.task_id if run is not None else None,
        "name": (run.saved_name if run is not None else None) or mol.name,
    }

class RunReceiptResponse(BaseModel):
    filename: str
    pdf_base64: str


@router.get('/receipts/{task_id}', response_model=RunReceiptResponse,
            summary='Recibo PDF de una corrida conservada')
async def get_run_receipt(task_id: str, current_user: UserORM = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)) -> RunReceiptResponse:
    import asyncio
    import base64
    from sqlalchemy.orm import selectinload
    pair = (await db.execute(select(EvaluationRunORM, MoleculeORM).join(
        MoleculeORM, EvaluationRunORM.molecule_id == MoleculeORM.id,
    ).options(selectinload(MoleculeORM.target)).where(
        EvaluationRunORM.task_id == task_id, MoleculeORM.user_id == current_user.id,
    ))).first()
    if pair is None:
        pair = (await db.execute(select(EvaluationRunORM, MoleculeORM).join(
            MoleculeORM, EvaluationRunORM.molecule_id == MoleculeORM.id,
        ).options(selectinload(MoleculeORM.target)).where(
            EvaluationRunORM.task_id.like('projection-archive:%'),
            EvaluationRunORM.snapshot_json['task_id'].as_string() == task_id,
            MoleculeORM.user_id == current_user.id,
        ).order_by(EvaluationRunORM.created_at.desc()))).first()
    if pair is None:
        # Una corrida heredada puede no tener snapshot. Sólo sirve su proyección
        # cuando ésta conserva exactamente el task_id solicitado y el dueño.
        legacy = (await db.execute(select(EvaluationResultORM, MoleculeORM).join(
            MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id,
        ).options(selectinload(MoleculeORM.target)).where(
            EvaluationResultORM.task_id == task_id, MoleculeORM.user_id == current_user.id,
        ))).first()
        if legacy is None:
            raise HTTPException(404, detail='Corrida no encontrada')
        evaluation, molecule = legacy
        snapshot = {}
        for column in EvaluationResultORM.__table__.columns:
            value = getattr(evaluation, column.name)
            snapshot[column.name] = value.isoformat() if hasattr(value, 'isoformat') else str(value) if isinstance(value, uuid.UUID) else value
        receipt_id = evaluation.id
    else:
        run, molecule = pair
        snapshot = await Repository(db).materialize_run_snapshot(run)
        receipt_id = run.id
    if not snapshot.get('blockchain_tx_id'):
        raise HTTPException(409, detail='Esta corrida no conserva un recibo')
    snapshot['task_id'] = task_id
    raw = await asyncio.to_thread(render_history_receipt, molecule, snapshot)
    return RunReceiptResponse(filename=f'MolDesign_Recibo_{receipt_id}.pdf',
                              pdf_base64=base64.b64encode(raw).decode('ascii'))
