"""
api/routers/colabfold.py — Endpoints para ColabFold (AlphaFold-Multimer).

ColabFold predice la estructura de complejos proteina-peptido usando AlphaFold-Multimer.
Este router actua como proxy HTTP hacia el servicio externo de ColabFold.

Seguridad:
  - No expone credenciales ni URLs internas en errores.
  - Solo extrae la secuencia de aminoacidos del PDB, no envia el archivo completo.
  - Timeout de 900s para requests largas (AlphaFold es computacionalmente intensivo).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from utils.logger import get_logger
from services.colabfold.service import get_colabfold_service

log = get_logger(__name__)

router = APIRouter(prefix="/docking/colabfold", tags=["ColabFold"])


# ── Request / Response Models ────────────────────────────────────────────────


class ColabFoldRequest(BaseModel):
    protein_pdb_id: str = Field(
        ...,
        min_length=4,
        max_length=10,
        description="PDB ID del receptor (ej: 7E2Y). Solo se extrae la secuencia de aminoacidos.",
    )
    peptide_smiles: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="SMILES del peptido a acoplar.",
    )


class ColabFoldPoseResponse(BaseModel):
    rank: int
    iptm: float
    ptm: float
    plddt: float
    complex_pdb: str


class ColabFoldResponse(BaseModel):
    success: bool
    poses: list[ColabFoldPoseResponse]
    best_plddt: float | None
    best_iptm: float | None
    execution_time_s: float | None
    warnings: list[str]
    error: str | None


# ── Helper ───────────────────────────────────────────────────────────────────


def _sanitize_colabfold_result(result: any) -> ColabFoldResponse:
    """Convierte ColabFoldResult del servicio a ColabFoldResponse seguro."""
    if not result or not hasattr(result, "success"):
        return ColabFoldResponse(
            success=False, poses=[], best_plddt=None, best_iptm=None,
            execution_time_s=None, warnings=[], error="Servicio no disponible.",
        )
    return ColabFoldResponse(
        success=result.success,
        poses=[
            ColabFoldPoseResponse(
                rank=p.rank,
                iptm=p.iptm,
                ptm=p.ptm,
                plddt=p.plddt,
                complex_pdb=p.complex_pdb[:3000] if p.complex_pdb else "",
            )
            for p in (result.poses or [])
        ],
        best_plddt=result.best_plddt,
        best_iptm=result.best_iptm,
        execution_time_s=result.execution_time_s,
        warnings=result.warnings or [],
        error=result.error,
    )


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post(
    "/predict",
    response_model=ColabFoldResponse,
    summary="Prediccion de complejo peptido (ColabFold)",
    description=(
        "Predice la estructura 3D de un complejo proteina-peptido usando AlphaFold-Multimer "
        "via ColabFold. La proteina se descarga de RCSB y se extrae su secuencia. "
        "El peptido se construye desde SMILES. Timeout: 15 minutos."
    ),
    status_code=status.HTTP_200_OK,
)
async def predict_colabfold(request: ColabFoldRequest) -> ColabFoldResponse:
    """
    Prediccion de complejo peptido (ColabFold).

    Args:
        request: ColabFoldRequest con protein_pdb_id y peptide_smiles.

    Returns:
        ColabFoldResponse con las poses predichas o error graceful.
    """
    service = get_colabfold_service()
    if not service.is_configured:
        return ColabFoldResponse(
            success=False, poses=[], best_plddt=None, best_iptm=None,
            execution_time_s=None, warnings=[],
            error="ColabFold no configurado. Define COLABFOLD_API_URL en el entorno.",
        )

    # Descargar PDB del receptor
    try:
        from utils.file_handlers import download_pdb_from_rcsb
        pdb_content = await download_pdb_from_rcsb(request.protein_pdb_id)
    except Exception:
        return ColabFoldResponse(
            success=False, poses=[], best_plddt=None, best_iptm=None,
            execution_time_s=None, warnings=[],
            error=f"No se pudo descargar el PDB {request.protein_pdb_id}.",
        )

    # Escribir PDB temporal
    temp_pdb = tempfile.NamedTemporaryFile(suffix=".pdb", delete=False, mode="w", encoding="utf-8")
    try:
        temp_pdb.write(pdb_content)
        temp_pdb.close()

        result = await service.predict(temp_pdb.name, request.peptide_smiles)
        return _sanitize_colabfold_result(result)

    except Exception as e:
        log.error("colabfold_predict_failed", error=str(e))
        return ColabFoldResponse(
            success=False, poses=[], best_plddt=None, best_iptm=None,
            execution_time_s=None, warnings=[],
            error="Error interno al ejecutar ColabFold.",
        )
    finally:
        try:
            Path(temp_pdb.name).unlink(missing_ok=True)
        except Exception:
            pass


@router.get(
    "/health",
    summary="Estado del servicio ColabFold",
    description="Verifica si el servicio ColabFold externo esta configurado y responde.",
)
async def colabfold_health() -> dict:
    """Health check del proxy ColabFold."""
    service = get_colabfold_service()
    if not service.is_configured:
        return {"status": "not_configured", "message": "ColabFold no configurado."}
    try:
        health = await service.check_health()
        return {
            "status": health.get("status", "unknown"),
            "message": health.get("error") or "Servicio respondiendo.",
        }
    except Exception:
        return {"status": "unreachable", "message": "ColabFold no responde."}
