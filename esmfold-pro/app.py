"""
app.py — Servidor FastAPI para ESMFold-Pro (RFdiffusion experimental).

Endpoint:
  GET  /health   → health check (GPU status, modelo cargado)
  POST /predict  → recibe {protein_pdb, peptide_smiles, num_poses, ...}

Puerto default: 8300
Modo: RFdiffusion (Baker Lab) — requiere GPU NVIDIA >=8 GB VRAM.
"""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from config import ServiceConfig, get_config
from logger import get_logger, setup_logging
from predictor import (
    BasePredictor,
    PredictionResult,
    PredictedPose,
    make_predictor,
)

_cfg: ServiceConfig = get_config()
setup_logging(_cfg.log_dir, _cfg.log_level)
log = get_logger("esmfold-pro.app")

_predictor: BasePredictor | None = None
_last_activity: float = time.monotonic()
_start_time: float = time.monotonic()
_total_predictions: int = 0
_total_errors: int = 0


# ── Schemas ───────────────────────────────────────────────────────────


class PredictRequest(BaseModel):
    protein_pdb: str = Field(..., description="Contenido del archivo PDB del receptor.")
    peptide_smiles: str = Field(..., description="SMILES del péptido a acoplar.")
    num_poses: int = Field(default=5, ge=1, le=20)
    grid_center: tuple[float, float, float] | None = None
    grid_size: tuple[float, float, float] | None = None


class PoseResponse(BaseModel):
    rank: int
    confidence: float
    peptide_pdb: str
    rmsd: float | None = None


class PredictResponse(BaseModel):
    success: bool
    method: str
    poses: list[PoseResponse]
    best_confidence: float | None
    execution_time_s: float
    warnings: list[str]
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    mode: str
    uptime_seconds: float
    gpu_available: bool
    total_predictions: int
    total_errors: int


# ── Helpers ───────────────────────────────────────────────────────────


def _touch_activity() -> None:
    global _last_activity
    _last_activity = time.monotonic()


def _result_to_response(r: PredictionResult) -> PredictResponse:
    return PredictResponse(
        success=r.success,
        method=r.method,
        poses=[
            PoseResponse(rank=p.rank, confidence=p.confidence,
                         peptide_pdb=p.ligand_pdb, rmsd=p.rmsd)
            for p in r.poses
        ],
        best_confidence=r.best_confidence,
        execution_time_s=r.execution_time_s,
        warnings=r.warnings,
        error=r.error,
    )


# ── Lifespan ──────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _predictor

    log.info("=" * 60)
    log.info("ESMFold-Pro (RFdiffusion) arrancando")
    log.info(f"  host   : {_cfg.host}")
    log.info(f"  port   : {_cfg.port}")
    log.info(f"  mode   : rfdiffusion")
    log.info(f"  models : {_cfg.model_dir}")
    log.info(f"  timeout: {_cfg.predict_timeout_seconds}s")
    log.info("=" * 60)

    try:
        _predictor = make_predictor(
            mode="rfdiffusion",
            model_dir=str(_cfg.model_dir),
            rfdiffusion_path=str(_cfg.rfdiffusion_path),
            device=_cfg.device,
            predict_timeout=_cfg.predict_timeout_seconds,
        )
        await _predictor.load()
    except Exception as e:
        log.error(f"Fallo cargando predictor RFdiffusion: {e}")
        _predictor = make_predictor(mode="stub", model_dir=".")
        await _predictor.load()
        log.warning("Usando StubPredictor como fallback. GPU no disponible.")

    _touch_activity()
    yield
    log.info("Cerrando ESMFold-Pro...")


# ── App ───────────────────────────────────────────────────────────────


app = FastAPI(
    title="ESMFold-Pro — RFdiffusion Peptide Docking",
    version="0.1.0",
    description="Sidecar experimental para docking peptídico con RFdiffusion (Baker Lab). Requiere GPU NVIDIA >=8 GB.",
    lifespan=lifespan,
)


@app.middleware("http")
async def activity_middleware(request: Request, call_next):
    _touch_activity()
    return await call_next(request)


# ── Endpoints ─────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    gpu_ok = False
    try:
        import torch
        gpu_ok = torch.cuda.is_available()
    except ImportError:
        pass

    status = "healthy" if _predictor is not None else "degraded"
    if not gpu_ok and _predictor is not None:
        status = "degraded_gpu_unavailable"

    return HealthResponse(
        status=status,
        mode="rfdiffusion",
        uptime_seconds=round(time.monotonic() - _start_time, 2),
        gpu_available=gpu_ok,
        total_predictions=_total_predictions,
        total_errors=_total_errors,
    )


@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest) -> PredictResponse:
    global _total_predictions, _total_errors

    if _predictor is None:
        raise HTTPException(status_code=503, detail="Predictor no inicializado")

    size_mb = len(req.protein_pdb.encode("utf-8")) / (1024 * 1024)
    if size_mb > _cfg.max_protein_pdb_mb:
        raise HTTPException(
            status_code=413,
            detail=f"PDB excede {_cfg.max_protein_pdb_mb} MB",
        )

    num_poses = min(req.num_poses, _cfg.max_poses)

    log.info(f"POST /predict  peptide={req.peptide_smiles[:40]!r}  poses={num_poses}")

    try:
        result = await asyncio.wait_for(
            _predictor.predict(
                protein_pdb=req.protein_pdb,
                peptide_smiles=req.peptide_smiles,
                num_poses=num_poses,
                grid_center=req.grid_center,
                grid_size=req.grid_size,
            ),
            timeout=_cfg.predict_timeout_seconds,
        )
    except asyncio.TimeoutError:
        _total_errors += 1
        raise HTTPException(status_code=504, detail="Timeout en predicción RFdiffusion")
    except Exception as e:
        _total_errors += 1
        log.error(f"Error en predict: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    _total_predictions += 1
    if not result.success:
        _total_errors += 1

    return _result_to_response(result)


# ── Arranque ──────────────────────────────────────────────────────────


def main() -> None:
    import uvicorn
    uvicorn.run(
        "app:app", host=_cfg.host, port=_cfg.port,
        log_level=_cfg.log_level.lower(), access_log=False,
    )


if __name__ == "__main__":
    main()
