"""Estadísticas privadas de la cuenta; no publican datos de otros usuarios."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_optional
from core.database import get_db
from core.models import MoleculeORM, EvaluationResultORM, TargetORM, UserORM

router = APIRouter(prefix="/stats", tags=["Estadísticas"])


@router.get("/global")
async def get_global_stats(
    db: AsyncSession = Depends(get_db),
    current_user: UserORM | None = Depends(get_current_user_optional),
):
    """Conserva el contrato JSON antiguo, pero los datos son sólo de esta cuenta."""
    hot = await db.scalar(
        select(TargetORM).where(TargetORM.is_hot.is_(True), TargetORM.is_private.is_(False)).limit(1)
    )
    hot_info = None if hot is None else {
        "pdb_id": hot.pdb_id, "name": hot.name,
        "spearman_rho": hot.spearman_rho, "family": hot.structural_family,
    }
    stats = {
        "total_molecules": 0, "total_certifications": 0,
        "best_affinity": None, "best_score": None,
        "best_molecule_name": "N/A", "best_user_name": "N/A",
        "best_target_pdb": "N/A", "hot_target": hot_info,
        "community_status": "Cuenta privada",
    }
    if current_user is None:
        return stats
    owner = current_user.id
    stats["total_molecules"] = (await db.scalar(
        select(func.count(MoleculeORM.id)).where(MoleculeORM.user_id == owner)
    )) or 0
    stats["total_certifications"] = (await db.scalar(
        select(func.count(EvaluationResultORM.id))
        .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
        .where(MoleculeORM.user_id == owner, EvaluationResultORM.blockchain_tx_id.isnot(None))
    )) or 0
    # Vina no permite comparar afinidades de receptores distintos.
    target_count = (await db.scalar(
        select(func.count(func.distinct(MoleculeORM.target_id)))
        .join(EvaluationResultORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
        .where(MoleculeORM.user_id == owner,
               EvaluationResultORM.affinity_kcal.isnot(None))
    )) or 0
    if target_count != 1:
        return stats
    row = (await db.execute(
        select(EvaluationResultORM.affinity_kcal, MoleculeORM.name, MoleculeORM.smiles, TargetORM.pdb_id)
        .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
        .join(TargetORM, MoleculeORM.target_id == TargetORM.id)
        .where(MoleculeORM.user_id == owner, EvaluationResultORM.affinity_kcal.isnot(None))
        .order_by(EvaluationResultORM.affinity_kcal.asc()).limit(1)
    )).first()
    if row:
        affinity, name, smiles, pdb_id = row
        stats.update(best_affinity=round(float(affinity), 1), best_score=round(float(affinity), 1),
                     best_molecule_name=name or smiles, best_user_name=current_user.username or "Cuenta",
                     best_target_pdb=pdb_id)
    return stats


@router.get("/leaderboard", summary="Evaluaciones de esta cuenta por afinidad observada")
async def get_leaderboard(
    db: AsyncSession = Depends(get_db),
    current_user: UserORM | None = Depends(get_current_user_optional),
    limit: int = Query(default=10, ge=1, le=100),
):
    if current_user is None:
        return []
    rows = (await db.execute(
        select(EvaluationResultORM.total_score, EvaluationResultORM.affinity_kcal,
               MoleculeORM.smiles_hash)
        .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
        .where(MoleculeORM.user_id == current_user.id,
               EvaluationResultORM.affinity_kcal.isnot(None))
        .order_by(EvaluationResultORM.affinity_kcal.asc()).limit(limit)
    )).all()
    return [
        {"username": current_user.username or "Cuenta",
         "total_score": row.total_score, "affinity_kcal": row.affinity_kcal,
         "target_pdb_id": "?", "smiles_hash": (row.smiles_hash or "?")[:8]}
        for row in rows
    ]
