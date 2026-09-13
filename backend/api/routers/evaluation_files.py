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


@router.get(
    "/files/protein/{molecule_id}",
    response_class=PlainTextResponse,
    summary="Descargar PDB del target biológico",
)
async def get_protein_file(
    molecule_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """Retorna el PDB raw local del target o lo descarga de RCSB al faltar."""
    from utils.file_handlers import StoragePath, download_pdb_from_rcsb
    from utils.local_storage import exists, read_text, write_text

    from api.routers.evaluation_access import require_owned_molecule
    from services.targets.access import is_rcsb_pdb_id, require_target_object_access

    # EVAL-BE-003. Este endpoint era el único archivo de evaluación sin
    # comprobación de propiedad. Con el id de una molécula ajena devolvía 200 y
    # el PDB de su receptor: confirmaba la existencia de la corrida y, si el
    # receptor era una estructura privada subida por otra cuenta, entregaba sus
    # bytes. Se aplica aquí la MISMA política que en poses y complejo.
    repository = Repository(db)
    await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=molecule_id,
        current_user=current_user,
        forbidden_detail="No tienes permiso para acceder a este receptor.",
        missing_detail=f"No existe molécula con id={molecule_id}",
    )
    # La lectura con `selectinload` es la que trae el receptor: la instancia que
    # devuelve la política de propiedad no lo tiene cargado y tocar la relación
    # fuera de la consulta rompería la sesión asíncrona.
    molecule = await repository.get_molecule(molecule_id)
    if molecule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe molécula con id={molecule_id}",
        )

    target = molecule.target
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La molécula no tiene un target asociado",
        )
    # Un receptor privado sólo existe para su creador, aunque la corrida que lo
    # usó sea visible: no distinguir inexistente de ajeno evita la enumeración.
    require_target_object_access(target, current_user)

    pdb_id = target.pdb_id
    raw_path = StoragePath.target_raw(pdb_id)
    try:
        if await exists(raw_path):
            pdb_content = await read_text(raw_path)
            return PlainTextResponse(
                content=pdb_content,
                media_type="chemical/x-pdb",
                headers={"Content-Disposition": f'inline; filename="{pdb_id}.pdb"'},
            )
    except Exception:
        log.warning("error leyendo PDB local, intentando RCSB", pdb_id=pdb_id)

    # Un identificador interno (`USR_*`) no existe en RCSB: pedirlo sólo
    # publicaría el nombre del receptor privado en un servicio externo.
    if not is_rcsb_pdb_id(str(pdb_id).strip().upper()):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No hay estructura local para el receptor {pdb_id} y no es un "
                "identificador público que pueda recuperarse."
            ),
        )

    try:
        pdb_content = await download_pdb_from_rcsb(pdb_id)
        try:
            await write_text(raw_path, pdb_content)
        except Exception:
            log.warning("no se pudo cachear PDB local", pdb_id=pdb_id)

        return PlainTextResponse(
            content=pdb_content,
            media_type="chemical/x-pdb",
            headers={"Content-Disposition": f'inline; filename="{pdb_id}.pdb"'},
        )
    except Exception as exc:
        log.error("no se pudo obtener PDB", pdb_id=pdb_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se pudo obtener la estructura PDB para {pdb_id}: {str(exc)}",
        ) from exc


@router.get(
    "/files/poses/{molecule_id}",
    response_class=PlainTextResponse,
    summary="Descargar SDF de poses de docking",
)
async def get_pose_file(
    molecule_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """Retorna el SDF real de las poses exportadas por el motor de docking."""
    from api.routers.evaluation_access import require_owned_molecule
    from core.exceptions import LocalFileNotFound
    from utils.local_storage import read_text

    repository = Repository(db)
    result = await repository.get_evaluation_result(molecule_id)
    if result is None:
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
    if not result.poses_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Esta evaluación no tiene archivo de poses (puede ser un resultado fallido o pendiente)",
        )

    try:
        sdf_content = await read_text(result.poses_file_path)
    except LocalFileNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo SDF de poses no se encontró en storage",
        )
    if not sdf_content or "M  END" not in sdf_content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El archivo SDF de poses está vacío o es inválido.",
        )

    return PlainTextResponse(
        content=sdf_content,
        media_type="chemical/x-mdl-sdfile",
        headers={"Content-Disposition": f'inline; filename="poses_{molecule_id}.sdf"'},
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
) -> PlainTextResponse:
    """Fusiona receptor PDB y primera pose SDF en un PDB único para el visor."""
    from api.routers.evaluation_access import require_owned_molecule
    from core.exceptions import LocalFileNotFound
    from services.docking.pdb_assembly import merge_protein_ligand_pdb
    from utils.file_handlers import StoragePath, download_pdb_from_rcsb
    from utils.local_storage import exists, read_text, write_text

    repository = Repository(db)
    result = await repository.get_evaluation_result(molecule_id)
    if result is None:
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
    if not result.poses_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Esta evaluación no tiene poses de docking guardadas.",
        )

    molecule = await repository.get_molecule(molecule_id)
    if molecule is None or molecule.target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el target asociado a esta evaluación.",
        )

    pdb_id = molecule.target.pdb_id
    raw_path = StoragePath.target_raw(pdb_id)
    try:
        if await exists(raw_path):
            protein_pdb = await read_text(raw_path)
        else:
            protein_pdb = await download_pdb_from_rcsb(pdb_id)
            try:
                await write_text(raw_path, protein_pdb)
            except Exception:
                pass
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se pudo obtener el PDB del receptor {pdb_id}: {exc}",
        )

    try:
        sdf_content = await read_text(result.poses_file_path)
    except LocalFileNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo SDF de poses no se encontró en storage.",
        )
    if not sdf_content or "M  END" not in sdf_content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El SDF de poses está vacío o es inválido.",
        )

    complex_pdb = merge_protein_ligand_pdb(protein_pdb, sdf_content)
    if not complex_pdb:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No se pudo fusionar el PDB del receptor con el ligando docked.",
        )

    return PlainTextResponse(
        content=complex_pdb,
        media_type="chemical/x-pdb",
        headers={"Content-Disposition": f'inline; filename="complex_{molecule_id}.pdb"'},
    )
