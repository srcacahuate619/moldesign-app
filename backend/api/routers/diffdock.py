"""
api/routers/diffdock.py — Endpoints para DiffDock (docking por difusion).

DiffDock es un motor de docking generativo basado en difusion (Corso et al. ICLR 2023).
Este router actua como proxy HTTP hacia el servicio externo de DiffDock.

Seguridad:
  - No expone credenciales ni URLs internas en errores.
  - Los archivos temporales se limpian al finalizar.
  - Timeout de 300s para requests largas (docking generativo es lento).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from utils.logger import get_logger
from services.diffdock.service import get_diffdock_service

log = get_logger(__name__)

router = APIRouter(prefix="/docking/diffdock", tags=["DiffDock"])


# ── Request / Response Models ────────────────────────────────────────────────


class DiffDockRequest(BaseModel):
    protein_pdb_id: str = Field(
        ...,
        min_length=4,
        max_length=10,
        description="PDB ID del receptor (ej: 7E2Y). Se descargara automaticamente si no existe en cache.",
    )
    ligand_smiles: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="SMILES del ligando a dockear.",
    )
    num_poses: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Numero de poses a generar (1-50).",
    )


class DiffDockPoseResponse(BaseModel):
    rank: int
    confidence: float
    affinity_predicted: float | None
    ligand_pdb: str
    rmsd_from_input: float | None


class DiffDockResponse(BaseModel):
    success: bool
    poses: list[DiffDockPoseResponse]
    best_confidence: float | None
    execution_time_s: float | None
    warnings: list[str]
    error: str | None


# ── Helper ───────────────────────────────────────────────────────────────────


def _sanitize_diffdock_result(result: Any) -> DiffDockResponse:
    """Convierte DiffDockResult del servicio a DiffDockResponse seguro."""
    if not result or not hasattr(result, "success"):
        return DiffDockResponse(
            success=False, poses=[], best_confidence=None,
            execution_time_s=None, warnings=[], error="Servicio no disponible."
        )
    return DiffDockResponse(
        success=result.success,
        poses=[
            DiffDockPoseResponse(
                rank=p.rank,
                confidence=p.confidence,
                affinity_predicted=p.affinity_predicted,
                ligand_pdb=p.ligand_pdb[:2000] if p.ligand_pdb else "",
                rmsd_from_input=p.rmsd_from_input,
            )
            for p in (result.poses or [])
        ],
        best_confidence=result.best_confidence,
        execution_time_s=result.execution_time_s,
        warnings=result.warnings or [],
        error=result.error,
    )


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post(
    "/predict",
    response_model=DiffDockResponse,
    summary="Docking por difusion (DiffDock)",
    description=(
        "Ejecuta docking generativo con DiffDock sobre una proteina y ligando. "
        "El PDB se descarga de RCSB si no esta en cache local. "
        "El ligando se prepara como SDF desde el SMILES proporcionado."
    ),
    status_code=status.HTTP_200_OK,
)
async def predict_diffdock(request: DiffDockRequest) -> DiffDockResponse:
    """
    Docking por difusion (DiffDock).

    Args:
        request: DiffDockRequest con protein_pdb_id, ligand_smiles y num_poses.

    Returns:
        DiffDockResponse con las poses generadas o error graceful.
    """
    service = get_diffdock_service()
    if not service.is_configured:
        return DiffDockResponse(
            success=False, poses=[], best_confidence=None,
            execution_time_s=None, warnings=[],
            error="DiffDock no configurado. Define DIFFDOCK_API_URL en el entorno.",
        )

    # Descargar PDB del receptor
    try:
        from utils.file_handlers import download_pdb_from_rcsb
        pdb_content = await download_pdb_from_rcsb(request.protein_pdb_id)
    except Exception as e:
        log.warning("diffdock_pdb_download_failed", pdb_id=request.protein_pdb_id, error=str(e))
        return DiffDockResponse(
            success=False, poses=[], best_confidence=None,
            execution_time_s=None, warnings=[],
            error=f"No se pudo descargar el PDB {request.protein_pdb_id}.",
        )

    # Escribir PDB temporal
    temp_pdb = tempfile.NamedTemporaryFile(suffix=".pdb", delete=False, mode="w", encoding="utf-8")
    try:
        temp_pdb.write(pdb_content)
        temp_pdb.close()

        # Generar SDF del ligando desde SMILES
        from rdkit import Chem
        mol = Chem.MolFromSmiles(request.ligand_smiles)
        if mol is None:
            return DiffDockResponse(
                success=False, poses=[], best_confidence=None,
                execution_time_s=None, warnings=[],
                error="SMILES invalido.",
            )
        mol = Chem.AddHs(mol)
        from rdkit.Chem import AllChem
        AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        AllChem.MMFFOptimizeMolecule(mol)

        temp_sdf = tempfile.NamedTemporaryFile(suffix=".sdf", delete=False, mode="w")
        from rdkit.Chem import rdMolWriter
        writer = rdMolWriter.SDWriter(temp_sdf.name)
        writer.write(mol)
        writer.close()
        temp_sdf.close()

        # Ejecutar DiffDock
        result = await service.predict(temp_pdb.name, temp_sdf.name, request.num_poses)
        return _sanitize_diffdock_result(result)

    except Exception as e:
        log.error("diffdock_predict_failed", error=str(e))
        return DiffDockResponse(
            success=False, poses=[], best_confidence=None,
            execution_time_s=None, warnings=[],
            error="Error interno al ejecutar DiffDock.",
        )
    finally:
        for f_path in [temp_pdb.name, temp_sdf.name]:
            try:
                Path(f_path).unlink(missing_ok=True)
            except Exception:
                pass


@router.get(
    "/health",
    summary="Estado del servicio DiffDock",
    description="Verifica si el servicio DiffDock externo esta configurado y responde.",
)
async def diffdock_health() -> dict:
    """Health check del proxy DiffDock."""
    service = get_diffdock_service()
    if not service.is_configured:
        return {"status": "not_configured", "message": "DiffDock no configurado."}
    try:
        health = await service.check_health()
        return {
            "status": health.get("status", "unknown"),
            "message": health.get("error") or "Servicio respondiendo.",
        }
    except Exception:
        return {"status": "unreachable", "message": "DiffDock no responde."}
