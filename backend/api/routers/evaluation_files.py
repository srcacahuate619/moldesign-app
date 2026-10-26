"""Descargas de estructuras asociadas a una evaluación.

Este router conserva las rutas de evaluación, pero separa la entrega y el
cacheo local de archivos de la orquestación de jobs, resultados y SSE.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_optional
from core.database import get_db
from core.models import UserORM
from db.repository import Repository
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(tags=["Evaluación científica"])


async def _sdf_de_la_corrida(selected):
    from services.docking.result_sdf import ResultSdfUnavailable, read_result_sdf
    try:
        return await read_result_sdf(selected)
    except ResultSdfUnavailable as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


async def _receptor_pdb_de_la_corrida(selected) -> tuple[str, str]:
    """Convierte sólo el receptor preparado con hash verificable de la corrida."""
    import hashlib

    from services.docking.preparer_propio import pdbqt_como_pdb
    from utils.local_storage import exists, read_text

    receptor_path = getattr(selected, "receptor_path", None)
    expected_hash = getattr(selected, "receptor_sha256", None)
    if not receptor_path or not expected_hash:
        raise HTTPException(409, "La corrida no conserva receptor preparado verificable.")
    if not await exists(receptor_path):
        raise HTTPException(404, "Falta el receptor preparado de esta corrida.")
    try:
        contents = await read_text(receptor_path)
    except Exception as exc:
        raise HTTPException(404, "No se pudo leer el receptor preparado de esta corrida.") from exc
    actual_hash = hashlib.sha256(contents.encode("utf-8")).hexdigest()
    if actual_hash != expected_hash:
        raise HTTPException(409, "El hash del receptor preparado no coincide con la corrida.")
    pdb = pdbqt_como_pdb(contents, con_hidrogenos=True)
    if not pdb:
        raise HTTPException(409, "El receptor preparado no contiene átomos analizables.")
    return pdb + "END\n", actual_hash


@router.get(
    "/files/protein/{molecule_id}",
    response_class=PlainTextResponse,
    summary="Descargar receptor preparado de una corrida",
)
async def get_protein_file(
    molecule_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    task_id: str | None = None,
) -> PlainTextResponse:
    """Sirve el receptor preparado verificable de la evaluación seleccionada."""
    from api.routers.evaluation_access import require_owned_molecule, result_for_task
    from services.targets.access import require_target_object_access

    repository = Repository(db)
    await require_owned_molecule(
        repository=repository, db=db, molecule_id=molecule_id, current_user=current_user,
        forbidden_detail="No tienes permiso para acceder a este receptor.",
        missing_detail=f"No existe molécula con id={molecule_id}",
    )
    molecule = await repository.get_molecule(molecule_id)
    if molecule is None or molecule.target is None:
        raise HTTPException(404, "La molécula no tiene un target asociado.")
    require_target_object_access(molecule.target, current_user)
    selected = await result_for_task(repository, molecule_id, task_id)
    pdb, receptor_hash = await _receptor_pdb_de_la_corrida(selected)
    return PlainTextResponse(
        content=pdb, media_type="chemical/x-pdb",
        headers={
            "Content-Disposition": f'inline; filename="{molecule.target.pdb_id}.pdb"',
            "X-MolDesign-Receptor-Sha256": receptor_hash,
            **({"X-MolDesign-Task-Id": str(selected.task_id)} if getattr(selected, "task_id", None) else {}),
        },
    )


@router.get(
    "/files/poses/{molecule_id}",
    response_class=PlainTextResponse,
    summary="Descargar SDF de poses de docking",
)
async def get_pose_file(
    molecule_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    task_id: str | None = None,
) -> PlainTextResponse:
    """Retorna el SDF real de las poses exportadas por el motor de docking."""
    from api.routers.evaluation_access import require_owned_molecule, result_for_task

    repository = Repository(db)
    result = await repository.get_evaluation_result(molecule_id)
    if result is None and task_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe resultado para molecule_id={molecule_id}",
        )

    await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=molecule_id,
        current_user=current_user,
        forbidden_detail="No tienes permiso para acceder a estos archivos.",
    )
    selected = await result_for_task(repository, molecule_id, task_id, projection=result)
    artifact = await _sdf_de_la_corrida(selected)

    return PlainTextResponse(
        content=artifact.content,
        media_type="chemical/x-mdl-sdfile",
        headers={"Content-Disposition": f'inline; filename="poses_{molecule_id}.sdf"',
                 **artifact.headers(getattr(selected, "task_id", None))},
    )


@router.get(
    "/files/complex/{molecule_id}",
    response_class=PlainTextResponse,
    summary="Complejo proteína-ligando fusionado (un único PDB para visualización 3D correcta)",
)
async def get_complex_file(
    molecule_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    task_id: str | None = None,
) -> PlainTextResponse:
    """Fusiona receptor PDB y primera pose SDF en un PDB único para el visor."""
    from api.routers.evaluation_access import require_owned_molecule, result_for_task
    from services.docking.pdb_assembly import merge_protein_ligand_pdb

    repository = Repository(db)
    result = await repository.get_evaluation_result(molecule_id)
    if result is None and task_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe resultado de evaluación para molecule_id={molecule_id}",
        )

    await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=molecule_id,
        current_user=current_user,
        forbidden_detail="No tienes permiso para acceder al complejo fusionado.",
    )
    molecule = await repository.get_molecule(molecule_id)
    if molecule is None or molecule.target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el target asociado a esta evaluación.",
        )

    from services.targets.access import require_target_object_access
    require_target_object_access(molecule.target, current_user)
    from api.routers.evaluation_access import result_for_task

    selected = await result_for_task(repository, molecule_id, task_id, projection=result)
    protein_pdb, _receptor_hash = await _receptor_pdb_de_la_corrida(selected)

    artifact = await _sdf_de_la_corrida(selected)
    complex_pdb = merge_protein_ligand_pdb(protein_pdb, artifact.content)
    if not complex_pdb:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No se pudo fusionar el PDB del receptor con el ligando docked.",
        )

    return PlainTextResponse(
        content=complex_pdb,
        media_type="chemical/x-pdb",
        headers={"Content-Disposition": f'inline; filename="complex_{molecule_id}.pdb"',
                 **artifact.headers(getattr(selected, "task_id", None))},
    )
