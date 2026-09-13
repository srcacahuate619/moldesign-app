"""
api/routers/interactions.py

Endpoints for protein-ligand interaction analysis (PLIF).
Returns detailed interaction data: H-bonds, hydrophobic contacts,
pi-stacking, salt bridges, cation-pi, halogen bonds.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db
from core.models import UserORM
from db.repository import Repository
from api.dependencies import get_current_user_optional
from api.routers.evaluation_access import require_owned_molecule
from services.targets.access import require_target_object_access
from utils.file_handlers import StoragePath
from utils.local_storage import exists, read_text
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/evaluation", tags=["Interaction Analysis"])
settings = get_settings()


@router.get("/interactions/{molecule_id}")
async def get_interactions(
    molecule_id: str,
    pose_rank: int = Query(1, ge=1, le=20, description="Which docking pose to analyze (1=best)"),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Protein-Ligand Interaction Fingerprint (PLIF) analysis.

    Returns detailed interaction data for visualization:
    - Hydrogen bonds with Donor-H...Acceptor geometry
    - Hydrophobic contacts
    - Pi-stacking (face-to-face and edge-to-face)
    - Salt bridges
    - Cation-pi interactions
    - Halogen bonds

    Each interaction includes residue info, atom-level contacts,
    distance in Angstroms, and H-bond angles.
    """
    from uuid import UUID

    try:
        mol_uuid = UUID(molecule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid molecule_id format")

    repository = Repository(db)
    await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=mol_uuid,
        current_user=current_user,
        forbidden_detail="No tienes permiso para analizar esta evaluación.",
        missing_detail="Evaluation not found",
    )
    evaluation = await repository.get_evaluation_result(mol_uuid)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    if evaluation.molecule is None or evaluation.molecule.target is None:
        raise HTTPException(status_code=404, detail="Molecule or target data missing")

    target = require_target_object_access(evaluation.molecule.target, current_user)
    smiles_hash = evaluation.molecule.smiles_hash

    # ── Get protein PDB ──────────────────────────────────────────────
    raw_path = StoragePath.target_raw(target.pdb_id)
    pdb_content = None
    try:
        if await exists(raw_path):
            pdb_content = await read_text(raw_path)
        else:
            from utils.file_handlers import download_pdb_from_rcsb
            pdb_content = await download_pdb_from_rcsb(target.pdb_id)
    except Exception as e:
        log.warning("protein_pdb_not_available", target=target.pdb_id, error=str(e))
        # Try prepared PDBQT as fallback
        try:
            prepared_path = StoragePath.target_prepared(target.pdb_id)
            if await exists(prepared_path):
                pdbqt_content = await read_text(prepared_path)
                pdb_content = pdbqt_content  # rough fallback
        except Exception:
            pass

    if pdb_content is None:
        raise HTTPException(
            status_code=503,
            detail=f"Protein structure not available for {target.pdb_id}",
        )

    # ── Get ligand SDF (poses) ───────────────────────────────────────
    poses_path = StoragePath.docking_poses(smiles_hash, target.pdb_id)
    sdf_content = None
    try:
        if await exists(poses_path):
            sdf_content = await read_text(poses_path)
    except Exception as e:
        log.warning("poses_sdf_not_available", error=str(e))

    if sdf_content is None:
        # Try to extract pose from PDBQT
        try:
            ligand_path = StoragePath.ligand_conformer(smiles_hash)
            if await exists(ligand_path):
                sdf_content = await read_text(ligand_path)
        except Exception:
            pass

    if sdf_content is None:
        raise HTTPException(
            status_code=503,
            detail="Docked poses not found. Run docking first.",
        )

    # ── Write temp files for ProLIF ──────────────────────────────────
    import tempfile

    tmp_dir = tempfile.mkdtemp()
    protein_path = Path(tmp_dir) / f"{target.pdb_id}_protein.pdb"
    ligand_path = Path(tmp_dir) / "ligand.sdf"

    try:
        protein_path.write_text(pdb_content, encoding="utf-8")

        # Extract only the requested pose from SDF
        from rdkit import Chem
        supplier = Chem.SDMolSupplier()
        supplier.SetData(sdf_content)
        mols = list(supplier)
        if pose_rank > len(mols):
            raise HTTPException(
                status_code=400,
                detail=f"Only {len(mols)} poses available. Requested pose {pose_rank}.",
            )
        writer = Chem.SDWriter(str(ligand_path))
        writer.write(mols[pose_rank - 1])
        writer.close()

        # ── Run interaction analysis ─────────────────────────────────
        from services.interactions.analyzer import analyze_complex

        report = analyze_complex(
            protein_pdb_path=protein_path,
            ligand_sdf_path=ligand_path,
            molecule_id=molecule_id,
            target_pdb_id=target.pdb_id,
            pose_rank=pose_rank,
        )

        # ── Format response ──────────────────────────────────────────
        interactions_by_type = {}
        for inter in report.interactions:
            itype = inter.type
            if itype not in interactions_by_type:
                interactions_by_type[itype] = []
            interactions_by_type[itype].append({
                "residue": f"{inter.residue_name}{inter.residue_number}{inter.residue_chain}",
                "residue_name": inter.residue_name,
                "residue_number": inter.residue_number,
                "residue_chain": inter.residue_chain,
                "ligand_atom": inter.ligand_atom,
                "protein_atom": inter.protein_atom,
                "distance": inter.distance,
                "angle": inter.angle,
                "strength": inter.strength,
                "ligand_coords": {"x": inter.lig_x, "y": inter.lig_y, "z": inter.lig_z},
                "protein_coords": {"x": inter.prot_x, "y": inter.prot_y, "z": inter.prot_z},
            })

        return {
            "molecule_id": molecule_id,
            "target_pdb_id": target.pdb_id,
            "pose_rank": pose_rank,
            "total_interactions": len(report.interactions),
            "summary": report.summary,
            "interactions_by_type": interactions_by_type,
            "pharmacophore_features": report.pharmacophore_features,
            "interactions": [{
                "type": i.type,
                "residue": f"{i.residue_name}{i.residue_number}{i.residue_chain}",
                "residue_name": i.residue_name,
                "residue_number": i.residue_number,
                "residue_chain": i.residue_chain,
                "ligand_atom": i.ligand_atom,
                "protein_atom": i.protein_atom,
                "distance": i.distance,
                "angle": i.angle,
                "strength": i.strength,
                "ligand_coords": {"x": i.lig_x, "y": i.lig_y, "z": i.lig_z},
                "protein_coords": {"x": i.prot_x, "y": i.prot_y, "z": i.prot_z},
            } for i in report.interactions],
        }

    finally:
        # Cleanup temp files
        try:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
