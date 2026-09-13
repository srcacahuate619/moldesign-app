"""
utils/local_storage.py

Abstracción de almacenamiento local en disco para MolDesign Desktop (F-03).

MolDesign es desktop-only: los archivos moleculares (.pdb, .pdbqt, .sdf,
.mol2) se guardan SIEMPRE en el filesystem local, bajo
`settings.local_data_dir` (por defecto ~/MolDesign/data).

Convención de nombres de objeto (fuente única: StoragePath en
utils/file_handlers.py):

    targets/{pdb_id}/raw.pdb                    → proteína raw del RCSB PDB
    targets/{pdb_id}/prepared.pdbqt             → proteína preparada para Vina
    ligands/{smiles_hash}/conformer.sdf         → conformer 3D del ligando
    ligands/{smiles_hash}/vina_input.pdbqt      → ligando preparado para Vina
    poses/{smiles_hash}/{target_pdb_id}/poses.sdf → poses de docking
    poses/{smiles_hash}/{target_pdb_id}/vina.log  → log de Vina

IMPORTANTE: los prefijos lógicos (`targets/`, `ligands/`, `poses/`) son parte
del contrato de datos. NO cambiarlos — romperían los archivos ya guardados
en discos de usuarios existentes.
"""

from __future__ import annotations

import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from core.config import get_settings
from core.exceptions import LocalFileNotFound
from utils.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


def data_dir() -> Path:
    """Directorio raíz de datos local (settings.local_data_dir)."""
    d = Path(getattr(settings, "local_data_dir", str(Path.home() / "MolDesign" / "data")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def path_for(object_name: str) -> Path:
    """Resuelve un nombre de objeto lógico a su ruta real en disco."""
    return data_dir() / object_name


# ── Lectura ────────────────────────────────────────────────────────────────────


async def read_bytes(object_name: str) -> bytes:
    """
    Lee un objeto del almacenamiento local y retorna sus bytes.

    Lanza LocalFileNotFound si la ruta lógica no existe en disco.
    """
    path = path_for(object_name)
    if not path.exists():
        raise LocalFileNotFound(
            filename=object_name,
            detail=f"Archivo no encontrado en disco local: {path}"
        )
    return path.read_bytes()


async def read_text(object_name: str, encoding: str = "utf-8") -> str:
    """Lee un objeto del almacenamiento local y retorna su contenido como string."""
    data = await read_bytes(object_name)
    return data.decode(encoding)


# ── Escritura ──────────────────────────────────────────────────────────────────


async def write_bytes(data: bytes, object_name: str) -> str:
    """
    Escribe bytes en el almacenamiento local y retorna el object_name.

    Crea los directorios intermedios necesarios (ej. ligands/{hash}/).
    """
    path = path_for(object_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    log.debug("archivo guardado en disco local", object_name=object_name, size=len(data))
    return object_name


async def write_text(object_name: str, content: str, encoding: str = "utf-8") -> str:
    """Escribe un string en el almacenamiento local (conveniencia sobre write_bytes)."""
    return await write_bytes(content.encode(encoding), object_name)


async def write_file(local_path: str | Path, object_name: str) -> str:
    """
    Copia un archivo del filesystem al almacenamiento local.

    Usado después de que AutoDock Vina escribe su output (.sdf de poses)
    en un directorio temporal.
    """
    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"Archivo local no encontrado: {local_path}")

    return await write_bytes(local_path.read_bytes(), object_name)


# ── Consultas de existencia / eliminación ─────────────────────────────────────


async def exists(object_name: str) -> bool:
    """
    Verifica si un objeto existe en disco sin leerlo.

    Usado en services/docking/preparer.py para saber si la proteína
    ya fue preparada (y no repetir el proceso):
        if await exists(StoragePath.target_prepared(pdb_id)):
            return  # ya está listo
    """
    return path_for(object_name).exists()


async def delete(object_name: str) -> bool:
    """Elimina un objeto del almacenamiento local. Retorna True si se eliminó
    (o no existía) y False ante un error del filesystem."""
    path = path_for(object_name)
    try:
        path.unlink(missing_ok=True)
        return True
    except Exception as e:
        log.warning("error eliminando objeto local", object_name=object_name, error=str(e))
        return False


# ── Archivos temporales ────────────────────────────────────────────────────────


@asynccontextmanager
async def temp_file(object_name: str, suffix: str = "") -> AsyncGenerator[Path, None]:
    """
    Materializa un objeto del almacenamiento local a un archivo temporal.

    Úsalo cuando necesitas pasar un archivo a un proceso externo
    (como AutoDock Vina) que requiere una ruta en el filesystem.

    El archivo temporal se elimina automáticamente al salir del bloque.

    Uso en vina_service.py:
        async with temp_file(StoragePath.target_prepared("7E2Y"), suffix=".pdbqt") as receptor_path:
            await _run_vina(receptor_path, ligand_path, output_path)
        # el archivo ya fue eliminado aquí
    """
    data = await read_bytes(object_name)

    with tempfile.NamedTemporaryFile(
        suffix=suffix,
        delete=False,
        dir=settings.vina_temp_dir,
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        yield tmp_path
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as e:
            log.warning(
                "no se pudo eliminar archivo temporal",
                path=str(tmp_path),
                error=str(e),
            )
