"""
api/routers/interactions.py

Endpoints for protein-ligand interaction analysis (PLIF).
Returns detailed interaction data: H-bonds, hydrophobic contacts,
pi-stacking, salt bridges, cation-pi, halogen bonds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import UserORM
from db.repository import Repository
from api.dependencies import get_current_user_optional
from api.routers.evaluation_access import require_owned_molecule
from services.targets.access import require_target_object_access
from utils.local_storage import exists, read_text
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/evaluation", tags=["Interaction Analysis"])


def _pdbqt_receptor_a_pdb(contenido: str) -> str:
    """Extrae los ATOM del receptor Vina sin inferir contactos con heteroátomos."""
    atomos = []
    tipos = {"A": "C", "C": "C", "OA": "O", "NA": "N", "SA": "S", "HD": "H"}
    for linea in contenido.splitlines():
        if not linea.startswith("ATOM  "):
            continue
        campos = linea.split()
        tipo = campos[-1].upper() if campos else ""
        elemento = tipos.get(tipo, tipo[:1] if tipo else "")
        if not elemento:
            continue
        atomos.append(linea[:66].ljust(76) + f"{elemento:>2}")
    return "\n".join(atomos) + "\nEND\n" if atomos else ""


class InteractionResponse(BaseModel):
    molecule_id: str
    target_pdb_id: str
    pose_rank: int
    pose_source_path: str
    pose_source_sha256: str
    protein_source_path: str
    protein_source_sha256: str
    protein_filter: str
    engine: str
    hydrogen_model: str | None
    total_interactions: int
    summary: dict[str, int]
    interactions_by_type: dict[str, list[dict[str, Any]]]
    pharmacophore_features: dict[str, Any]
    interactions: list[dict[str, Any]]


@router.get("/interactions/{molecule_id}", response_model=InteractionResponse)
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
    # La pose pertenece a la corrida. Una ruta compartida o el confórmero de
    # entrada representarían otra geometría y producirían contactos falsos.
    poses_path = evaluation.poses_file_path
    if not poses_path or not await exists(poses_path):
        raise HTTPException(status_code=404, detail="La corrida no conserva poses SDF acopladas.")
    try:
        sdf_content = await read_text(poses_path)
    except Exception as exc:
        log.warning("poses_sdf_not_available", path=poses_path, error=str(exc))
        raise HTTPException(status_code=404, detail="No se pudo leer la pose de esta corrida.") from exc
    pose_sha256 = hashlib.sha256(sdf_content.encode("utf-8")).hexdigest()

    # El receptor que se analiza debe ser el snapshot preparado que entró a
    # Vina, no el PDB crudo mutable del catálogo.
    receptor_path = evaluation.receptor_path
    receptor_sha256 = evaluation.receptor_sha256
    if not receptor_path or not receptor_sha256:
        raise HTTPException(status_code=409, detail="La corrida no conserva receptor preparado verificable.")
    if not await exists(receptor_path):
        raise HTTPException(status_code=404, detail="Falta el receptor preparado de esta corrida.")
    try:
        receptor_pdbqt = await read_text(receptor_path)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="No se pudo leer el receptor de esta corrida.") from exc
    protein_sha256 = hashlib.sha256(receptor_pdbqt.encode("utf-8")).hexdigest()
    if protein_sha256 != receptor_sha256:
        raise HTTPException(status_code=409, detail="El hash del receptor preparado no coincide con la corrida.")
    pdb_content = _pdbqt_receptor_a_pdb(receptor_pdbqt)
    if not pdb_content:
        raise HTTPException(status_code=409, detail="El receptor preparado no contiene átomos analizables.")

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
            "pose_source_path": poses_path,
            "pose_source_sha256": pose_sha256,
            "protein_source_path": receptor_path,
            "protein_filter": "ATOM_only",
            "protein_source_sha256": protein_sha256,
            "engine": report.engine,
            "hydrogen_model": report.hydrogen_model,
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
