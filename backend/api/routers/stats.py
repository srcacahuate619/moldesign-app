from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.models import MoleculeORM, EvaluationResultORM

router = APIRouter(prefix="/stats", tags=["Estadísticas"])

@router.get("/global")
async def get_global_stats(db: AsyncSession = Depends(get_db)):
    """
    Obtiene estadísticas globales de la plataforma en tiempo real.
    """
    from utils.cache import cache
    cached_stats = await cache.get("global_stats:v2")
    if cached_stats is not None:
        return cached_stats

    from core.models import UserORM

    # 1. Total de moléculas evaluadas (excluyendo demo)
    total_mols_stmt = (
        select(func.count(MoleculeORM.id))
        .join(UserORM, MoleculeORM.user_id == UserORM.id)
        .where(UserORM.username != 'demo')
    )
    total_mols_res = await db.execute(total_mols_stmt)
    total_mols = total_mols_res.scalar() or 0

    # 2. Total de certificaciones (moléculas con TX ID, excluyendo demo)
    cert_stmt = (
        select(func.count(EvaluationResultORM.id))
        .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
        .join(UserORM, MoleculeORM.user_id == UserORM.id)
        .where(EvaluationResultORM.blockchain_tx_id.isnot(None))
        .where(UserORM.username != 'demo')
    )
    cert_res = await db.execute(cert_stmt)
    total_certs = cert_res.scalar() or 0

    # 3. Afinidad Vina observada más favorable. No es probabilidad ni score.
    from core.models import UserORM

    from core.models import TargetORM

    best_stmt = (
        select(EvaluationResultORM, MoleculeORM, UserORM, TargetORM)
        .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
        .join(UserORM, MoleculeORM.user_id == UserORM.id)
        .join(TargetORM, MoleculeORM.target_id == TargetORM.id)
        .where(EvaluationResultORM.affinity_kcal.isnot(None))
        .where(UserORM.username != 'demo')
        .where(TargetORM.is_private.is_(False))
        .order_by(EvaluationResultORM.affinity_kcal.asc())
        .limit(1)
    )
    best_res = await db.execute(best_stmt)
    best_row = best_res.first()

    best_affinity = 0.0
    best_molecule_name = "N/A"
    best_molecule_user = "Sistema"
    best_target_pdb = "N/A"

    if best_row:
        eval_res, mol, user, target = best_row
        best_affinity = float(eval_res.affinity_kcal)
        best_molecule_name = mol.name or mol.smiles
        best_molecule_user = user.username or user.email.split('@')[0]
        best_target_pdb = target.pdb_id

    # 4. Obtener información del Hot Target actual para la UI
    hot_target_stmt = (
        select(TargetORM)
        .where(TargetORM.is_hot == True)
        .where(TargetORM.is_private.is_(False))
        .limit(1)
    )
    hot_res = await db.execute(hot_target_stmt)
    hot_target = hot_res.scalar_one_or_none()

    hot_info = None
    if hot_target:
        hot_info = {
            "pdb_id": hot_target.pdb_id,
            "name": hot_target.name,
            "spearman_rho": hot_target.spearman_rho,
            "family": hot_target.structural_family
        }

    stats = {
        "total_molecules": total_mols,
        "total_certifications": total_certs,
        "best_affinity": round(best_affinity, 1),
        # Alias temporal para clientes antiguos. Ya contiene afinidad, no score.
        "best_score": round(best_affinity, 1),
        "best_molecule_name": best_molecule_name,
        "best_user_name": best_molecule_user,
        "best_target_pdb": best_target_pdb,
        "hot_target": hot_info,
        "community_status": "Global"
    }
    await cache.set("global_stats:v2", stats, ttl=60)
    return stats

@router.get("/leaderboard", summary="Evaluaciones compartidas por afinidad observada")
async def get_leaderboard(db: AsyncSession = Depends(get_db), limit: int = 10):
    """Evaluaciones compartidas ordenadas por afinidad Vina observada."""
    from core.models import UserORM

    stmt = (
        select(
            EvaluationResultORM.total_score,
            EvaluationResultORM.affinity_kcal,
            UserORM.username,
            MoleculeORM.smiles_hash,
        )
        .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
        .join(UserORM, MoleculeORM.user_id == UserORM.id)
        .where(UserORM.username != 'demo')
        .where(UserORM.username != 'Desktop User')
        .where(EvaluationResultORM.affinity_kcal.isnot(None))
        .order_by(EvaluationResultORM.affinity_kcal.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "username": row.username or "unknown",
            "total_score": row.total_score,
            "affinity_kcal": row.affinity_kcal,
            "target_pdb_id": "?",
            "smiles_hash": (row.smiles_hash or "?")[:8],
        }
        for row in rows
    ]
