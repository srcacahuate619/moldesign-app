"""
api/routers/interactions.py

Endpoints for protein-ligand interaction analysis (PLIF).
Returns detailed interaction data: H-bonds, hydrophobic contacts,
pi-stacking, salt bridges, cation-pi, halogen bonds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import asyncio
import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import UserORM
from db.repository import Repository
from api.dependencies import get_current_user_optional
from api.routers.evaluation_access import require_owned_molecule, result_for_task
from services.targets.access import require_target_object_access
from utils.local_storage import exists, read_text
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/evaluation", tags=["Interaction Analysis"])


def _pdbqt_receptor_a_pdb(contenido: str) -> str:
    """Extrae los ATOM del receptor Vina sin inferir contactos con heteroátomos.

    El elemento sale del tipo AutoDock con la tabla de `preparer_propio`. Antes se
    tomaba la primera letra de cualquier tipo que no fuera de proteína: con la receta
    del catálogo no hay metales, pero un receptor propio (camino B o C) los conserva y
    Meeko los escribe como ATOM, así que el Zn pasaba a «Z», el Mg a «M» y el calcio
    a carbono, que cuenta como contacto hidrófobo (FEP-09, 2026-10-11).
    """
    from services.docking.preparer_propio import elemento_de_tipo

    atomos = []
    for linea in contenido.splitlines():
        if not linea.startswith("ATOM  "):
            continue
        campos = linea.split()
        tipo = campos[-1] if campos else ""
        elemento = elemento_de_tipo(tipo) or tipo[:1].upper()
        if not elemento:
            continue
        atomos.append(linea[:66].ljust(76) + f"{elemento:>2}")
    return "\n".join(atomos) + "\nEND\n" if atomos else ""


class InteractionResponse(BaseModel):
    molecule_id: str
    task_id: str | None = None
    target_pdb_id: str
    pose_rank: int
    pose_source_path: str | None
    pose_source_kind: str = "stored"
    pose_source_manifest: dict[str, Any] | None = None
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
    analysis_ligand_sha256: str | None = None
    contact_coverage: str = "not_declared"
    computed_at: str | None = None
    contact_map: dict[str, Any] | None = None
    pose_identity_verification: str = "not_declared"


@router.get("/interactions/{molecule_id}", response_model=InteractionResponse)
async def get_interactions(
    molecule_id: str,
    pose_rank: int = Query(1, ge=1, le=20, description="Which docking pose to analyze (1=best)"),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    task_id: str | None = None,
    include_map: bool = False,
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
    if include_map and not task_id:
        raise HTTPException(status_code=409, detail="El mapa requiere identificar explícitamente la corrida guardada.")
    projection = await repository.get_evaluation_result(mol_uuid)
    evaluation = await result_for_task(repository, mol_uuid, task_id, projection=projection)
    molecule = getattr(projection, "molecule", None)
    if molecule is None:
        molecule = await repository.get_molecule(mol_uuid)
    if molecule is None or molecule.target is None:
        raise HTTPException(status_code=404, detail="Molecule or target data missing")

    target = require_target_object_access(molecule.target, current_user)
    # La pose pertenece a la corrida. Una ruta compartida o el confórmero de
    # entrada representarían otra geometría y producirían contactos falsos.
    from services.docking.result_sdf import ResultSdfUnavailable, read_result_sdf
    try:
        artifact = await read_result_sdf(evaluation, reader=read_text)
    except ResultSdfUnavailable as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    poses_path, sdf_content, pose_sha256 = artifact.source_path, artifact.content, artifact.sha256

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
        if mols[pose_rank - 1] is None:
            raise HTTPException(status_code=409, detail="La pose solicitada no se puede interpretar; no se sustituye por otra.")
        writer = Chem.SDWriter(str(ligand_path))
        writer.write(mols[pose_rank - 1])
        writer.close()

        # ── Run interaction analysis ─────────────────────────────────
        from services.interactions.analyzer import analyze_complex

        # En un hilo: con un receptor grande el análisis tarda segundos y en el bucle de eventos congelaba el backend al
        # enseñar el resultado de una evaluación (3 s con 8HFI, medido el 2026-10-10).
        report = await asyncio.to_thread(
            analyze_complex,
            protein_pdb_path=protein_path,
            ligand_sdf_path=ligand_path,
            molecule_id=molecule_id,
            target_pdb_id=target.pdb_id,
            pose_rank=pose_rank,
        )

        contact_map = None
        if include_map:
            from services.interactions.contact_map import build_contact_map
            contact_map = await asyncio.to_thread(build_contact_map, ligand_path, report)

        def atom_metadata(interaction):
            return {"ligand_atom_indices": list(interaction.ligand_atom_indices),
                    "protein_atom_indices": list(interaction.protein_atom_indices),
                    "definition": interaction.definition, "geometry": interaction.geometry}

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
                **atom_metadata(inter),
            })

        return {
            "molecule_id": molecule_id,
            "task_id": getattr(evaluation, "task_id", None),
            "target_pdb_id": target.pdb_id,
            "pose_rank": pose_rank,
            "pose_source_path": poses_path,
            "pose_source_kind": artifact.source_kind,
            "pose_identity_verification": "verified_ensemble_geometry" if artifact.source_kind == "verified_ensemble" else "stored_run_path_and_current_file_hash",
            "pose_source_manifest": artifact.manifest,
            "pose_source_sha256": pose_sha256,
            "protein_source_path": receptor_path,
            "protein_filter": "ATOM_only",
            "protein_source_sha256": protein_sha256,
            "engine": report.engine,
            "hydrogen_model": report.hydrogen_model,
            "analysis_ligand_sha256": report.ligand_source_sha256,
            "contact_coverage": report.coverage,
            "computed_at": datetime.now(UTC).isoformat(),
            "contact_map": contact_map,
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
                **atom_metadata(i),
            } for i in report.interactions],
        }

    finally:
        # Cleanup temp files
        try:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
