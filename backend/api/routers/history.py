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
from sqlalchemy.orm import selectinload

from api.dependencies import get_current_user
from core.database import get_db
from core.models import (
    EvaluationResultORM,
    MoleculeORM,
    MoleculeStatus,
    TargetORM,
    UserORM,
)
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
    # Base query — TODAS las moléculas del usuario (sin gate de is_saved)
    base_query = (
        select(MoleculeORM)
        .options(
            selectinload(MoleculeORM.target),
            selectinload(MoleculeORM.evaluation_result),
        )
        .where(MoleculeORM.user_id == current_user.id)
    )

    if status_filter is not None:
        base_query = base_query.where(MoleculeORM.status == status_filter)

    # ── Filtros por receptor (join a targets) ──
    if target_pdb_id:
        base_query = base_query.join(MoleculeORM.target).where(
            TargetORM.pdb_id.ilike(f"%{target_pdb_id.strip()}%")
        )

    # ── Filtros por nombre / SMILES ──
    if name_contains:
        base_query = base_query.where(MoleculeORM.name.ilike(f"%{name_contains.strip()}%"))
    if smiles_contains:
        base_query = base_query.where(MoleculeORM.smiles.ilike(f"%{smiles_contains.strip()}%"))

    # ── Filtros sobre evaluation_result (join outer para no perder sin resultado) ──
    _result_filters = any([
        min_score is not None, max_score is not None,
        min_affinity is not None, max_affinity is not None,
        min_mw is not None, max_mw is not None,
        min_logp is not None, max_logp is not None,
        min_tpsa is not None, max_tpsa is not None,
        lipinski_pass is not None, is_pains is not None,
        qed_min is not None, adme_min is not None,
        druglikeness_min is not None,
    ])
    if _result_filters:
        base_query = base_query.outerjoin(EvaluationResultORM)

    if min_score is not None:
        base_query = base_query.where(EvaluationResultORM.total_score >= min_score)
    if max_score is not None:
        base_query = base_query.where(EvaluationResultORM.total_score <= max_score)
    if min_affinity is not None:
        base_query = base_query.where(EvaluationResultORM.affinity_kcal <= min_affinity)
    if max_affinity is not None:
        base_query = base_query.where(EvaluationResultORM.affinity_kcal >= max_affinity)
    if min_mw is not None:
        base_query = base_query.where(EvaluationResultORM.molecular_weight >= min_mw)
    if max_mw is not None:
        base_query = base_query.where(EvaluationResultORM.molecular_weight <= max_mw)
    if min_logp is not None:
        base_query = base_query.where(EvaluationResultORM.log_p >= min_logp)
    if max_logp is not None:
        base_query = base_query.where(EvaluationResultORM.log_p <= max_logp)
    if min_tpsa is not None:
        base_query = base_query.where(EvaluationResultORM.tpsa >= min_tpsa)
    if max_tpsa is not None:
        base_query = base_query.where(EvaluationResultORM.tpsa <= max_tpsa)
    if lipinski_pass is not None:
        base_query = base_query.where(EvaluationResultORM.lipinski_pass == lipinski_pass)
    if is_pains is not None:
        base_query = base_query.where(EvaluationResultORM.is_pains == is_pains)
    if qed_min is not None:
        base_query = base_query.where(EvaluationResultORM.qed >= qed_min)
    if adme_min is not None:
        base_query = base_query.where(EvaluationResultORM.adme_score >= adme_min)
    if druglikeness_min is not None:
        base_query = base_query.where(EvaluationResultORM.druglikeness_score >= druglikeness_min)

    # Count total
    count_query = select(func.count()).select_from(
        base_query.with_only_columns(MoleculeORM.id).subquery()
    )
    total = (await db.execute(count_query)).scalar() or 0

    # ── Sorting ampliado ──
    _SORT_COLUMNS = {
        "created_at": MoleculeORM.created_at,
        "total_score": EvaluationResultORM.total_score,
        "affinity_kcal": EvaluationResultORM.affinity_kcal,
        "affinity_score": EvaluationResultORM.affinity_score,
        "molecular_weight": EvaluationResultORM.molecular_weight,
        "log_p": EvaluationResultORM.log_p,
        "tpsa": EvaluationResultORM.tpsa,
        "qed": EvaluationResultORM.qed,
        "adme_score": EvaluationResultORM.adme_score,
        "druglikeness_score": EvaluationResultORM.druglikeness_score,
        "gnn_score": EvaluationResultORM.gnn_score,
        "sa_score": EvaluationResultORM.sa_score,
    }
    if sort_by not in _SORT_COLUMNS:
        sort_by = "created_at"

    needs_join = _SORT_COLUMNS[sort_by] != MoleculeORM.created_at
    if needs_join and not _result_filters:
        base_query = base_query.outerjoin(EvaluationResultORM)

    sort_column = _SORT_COLUMNS[sort_by]
    if sort_order == "asc":
        base_query = base_query.order_by(sort_column.asc().nullslast())
    else:
        base_query = base_query.order_by(sort_column.desc().nullslast())

    # Pagination
    offset = (page - 1) * page_size
    base_query = base_query.offset(offset).limit(page_size)

    result = await db.execute(base_query)
    molecules = list(result.scalars().all())

    items = []
    for mol in molecules:
        ev = mol.evaluation_result
        items.append(EvaluationSummary(
            molecule_id=str(mol.id),
            smiles=mol.smiles,
            name=mol.name,
            status=mol.status.value if hasattr(mol.status, "value") else str(mol.status),
            target_pdb_id=mol.target.pdb_id if mol.target else "unknown",
            total_score=ev.total_score if ev else None,
            affinity_kcal=ev.affinity_kcal if ev else None,
            affinity_score=ev.affinity_score if ev else None,
            adme_score=ev.adme_score if ev else None,
            druglikeness_score=ev.druglikeness_score if ev else None,
            molecular_weight=ev.molecular_weight if ev else None,
            log_p=ev.log_p if ev else None,
            lipinski_pass=ev.lipinski_pass if ev else None,
            qed=ev.qed if ev else None,
            sa_score=ev.sa_score if ev else None,
            blockchain_tx_id=ev.blockchain_tx_id if ev else None,
            evaluated_at=ev.evaluated_at.isoformat() if ev and ev.evaluated_at else None,
            created_at=mol.created_at.isoformat() if mol.created_at else "",
            task_id=ev.task_id if ev else None,
            is_saved=bool(mol.is_saved),
        ))

    return HistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + page_size) < total,
    )


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

    # HIST-BE-001. La poblacion es la MISMA que lista /history/evaluations: todas las
    # moleculas de la cuenta. Estos agregados filtraban ademas por `is_saved`, que es el
    # filtro de Moldex (db/repository.py) y no el del historial, de modo que el marcador
    # contaba una poblacion y la tabla de debajo otra: veinte filas bajo un "Total 0".
    total_q = select(func.count()).where(MoleculeORM.user_id == current_user.id)
    total = (await db.execute(total_q)).scalar() or 0

    # Completed
    completed_q = select(func.count()).where(
        MoleculeORM.user_id == current_user.id,
        MoleculeORM.status == MoleculeStatus.EVALUATED,
    )
    completed = (await db.execute(completed_q)).scalar() or 0

    # Failed
    failed_q = select(func.count()).where(
        MoleculeORM.user_id == current_user.id,
        MoleculeORM.status == MoleculeStatus.FAILED,
    )
    failed = (await db.execute(failed_q)).scalar() or 0

    # Best and avg score
    score_q = (
        select(
            func.max(EvaluationResultORM.total_score),
            func.avg(EvaluationResultORM.total_score),
        )
        .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
        .where(MoleculeORM.user_id == current_user.id)
        .where(EvaluationResultORM.total_score.isnot(None))
    )
    score_result = (await db.execute(score_q)).one()
    best_score = float(score_result[0]) if score_result[0] is not None else None
    avg_score = round(float(score_result[1]), 2) if score_result[1] is not None else None

    # Unique targets
    targets_q = (
        select(func.count(func.distinct(MoleculeORM.target_id)))
        .where(MoleculeORM.user_id == current_user.id)
    )
    unique_targets = (await db.execute(targets_q)).scalar() or 0

    return StatsResponse(
        total_evaluations=total,
        completed_evaluations=completed,
        failed_evaluations=failed,
        best_score=best_score,
        avg_score=avg_score,
        unique_targets=unique_targets,
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
):
    """Marca una molécula como 'guardada' para que aparezca en el listado de Guardado."""
    mol = await db.get(MoleculeORM, molecule_id)
    _require_molecule_owner(mol, current_user)

    mol.is_saved = True
    if name:
        mol.name = name
    await db.commit()
    return {"status": "saved", "molecule_id": str(molecule_id), "name": mol.name}
