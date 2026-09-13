"""
rescoring/app.py

Microservicio de ML Rescoring — FastAPI application.

Este servicio corre en un contenedor separado (Python 3.12) y se comunica
con el backend principal (Python 3.14) vía HTTP en puerto 8001.

Responsabilidades:
  - POST /rescore  → recibe pose(s) + SMILES, devuelve score ML + Delta + warnings
  - GET  /health   → health check (modelo cargado, dependencias OK)
  - GET  /info     → metadata del modelo (versión, métricas, fecha de entrenamiento)
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from config import get_rescoring_settings
from fastapi import FastAPI, HTTPException
from logger import get_logger
from model_manifest import ManifestVerification, verify_model_manifest
from model_manager import ModelManager
from schemas import (
    HealthResponse,
    ModelInfoResponse,
    PreScoreRequest,
    PreScoreResponse,
    RescoreRequest,
    RescoreResponse,
)

log = get_logger(__name__)
settings = get_rescoring_settings()

# ─────────────────────────────────────────────
# Pydantic models re-exported from schemas.py
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# Lifespan — carga del modelo al arrancar
# ─────────────────────────────────────────────

model_manager = ModelManager()
manifest_verification: ManifestVerification | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cargar modelo al arrancar, liberar al cerrar."""
    global manifest_verification
    log.info("rescoring_startup", msg="Iniciando microservicio de rescoring")
    manifest_verification = verify_model_manifest()
    if not manifest_verification.valid:
        log.error(
            "model_manifest_invalid",
            version=manifest_verification.version,
            errors=list(manifest_verification.errors),
        )
    model_manager.load_models()
    yield
    log.info("rescoring_shutdown", msg="Cerrando microservicio de rescoring")


# ─────────────────────────────────────────────
# App FastAPI
# ─────────────────────────────────────────────

app = FastAPI(
    title="MolDesign ML Rescoring Service",
    description=(
        "Microservicio de rescoring ML para MolDesign. "
        "Ejecuta predicción con Modelo A (completo) y Modelo NULL (control), "
        "calcula Delta de Especificidad 3D, verifica Applicability Domain, "
        "y reporta incertidumbre de poses."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check — verifica que el modelo esté cargado y las dependencias disponibles."""
    verification = manifest_verification or verify_model_manifest()
    prolif_ok = _check_prolif()
    xgboost_ok = _check_xgboost()
    gnn_ok = _check_gnn()

    status = (
        "healthy"
        if model_manager.is_loaded and prolif_ok and xgboost_ok and verification.valid
        else "degraded"
    )

    return HealthResponse(
        status=status,
        model_loaded=model_manager.is_loaded,
        model_version=model_manager.model_version,
        prolif_available=prolif_ok,
        xgboost_available=xgboost_ok,
        gnn_available=gnn_ok,
        manifest_valid=verification.valid,
        manifest_errors=list(verification.errors),
    )


@app.get("/info", response_model=ModelInfoResponse)
async def model_info():
    """Metadata del modelo cargado."""
    return model_manager.get_info()


@app.post("/pre-score", response_model=PreScoreResponse)
async def pre_score(request: PreScoreRequest):
    """
    Pre-scoring rápido usando solo descriptores 1D/2D (Modelo NULL).
    Útil para evaluar sugerencias de optimización sin poses 3D.
    """
    if not model_manager.is_loaded:
        raise HTTPException(status_code=503, detail="Modelo no cargado")

    try:
        import asyncio
        loop = asyncio.get_running_loop()
        score, in_domain = await loop.run_in_executor(None, model_manager.predict_null, request)
        return PreScoreResponse(
            score=round(score, 4),
            model_version=model_manager.model_version or "unknown",
            in_domain=in_domain
        )
    except Exception as e:
        log.error("pre_score_error", error=str(e), smiles=request.smiles)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rescore", response_model=RescoreResponse)
async def rescore(request: RescoreRequest):
    """
    Rescoring ML completo de una molécula.

    Pipeline:
    1. Filtro geométrico de poses
    2. Extracción de features (1D/2D + 3D + Vina)
    3. Check de Applicability Domain (Mahalanobis)
    4. Si fuera de dominio → devolver warning, sin predicción ML
    5. Predicción Modelo A y Modelo NULL
    6. Delta de Especificidad 3D
    7. Varianza de poses como medida de incertidumbre
    8. [NUEVO] RTMScore GNN (Nivel 2) si run_gnn=True
    """
    start_time = time.perf_counter()

    if not model_manager.is_loaded:
        raise HTTPException(
            status_code=503,
            detail=(
                "Modelo de rescoring no cargado. "
                "El microservicio arrancó sin artefactos de modelo. "
                "Ejecute el entrenamiento primero (Fase 2)."
            ),
        )

    try:
        import asyncio
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, model_manager.predict, request)
    except Exception as e:
        log.error("rescore_error", error=str(e), smiles=request.smiles)
        raise HTTPException(
            status_code=500,
            detail=f"Error en rescoring: {e!s}",
        )

    # --- [NUEVO] Nivel 2: RTMScore GNN ---
    # Se ejecuta SOLO si el cliente lo pide (run_gnn=True) y hay poses con coords 3D.
    # Falla silenciosamente si los pesos no están o las dependencias no están disponibles.
    if request.run_gnn and request.poses:
        best_pose = request.poses[0]
        if best_pose.pdbqt_block and len(best_pose.pdbqt_block.strip()) > 10:
            try:
                import asyncio

                from gnn_service import evaluate_rtmscore
                loop = asyncio.get_running_loop()
                gnn_raw, gnn_attention_raw, gnn_svg_raw, gnn_pharmacophores_raw = await loop.run_in_executor(
                    None,
                    evaluate_rtmscore,
                    request.smiles,
                    request.target_pdb_path,
                    best_pose.pdbqt_block,
                )
                result.gnn_score = round(float(gnn_raw), 4)
                result.gnn_attention = gnn_attention_raw
                result.gnn_attention_svg = gnn_svg_raw
                result.gnn_pharmacophores = gnn_pharmacophores_raw
                log.info(
                    "gnn_rescore_ok",
                    smiles=request.smiles[:50],
                    gnn_score=result.gnn_score,
                )
            except FileNotFoundError as e:
                # Pesos del modelo no encontrados — condición esperada en dev
                log.warning("gnn_weights_not_found", detail=str(e))
                result.warnings.append("RTMScore GNN: pesos del modelo no encontrados (trained_models/rtmscore_model1.pth). Instale los pesos para activar el Nivel 2.")
            except ImportError as e:
                # torch-geometric/torch-scatter no disponibles en este entorno
                log.warning("gnn_dependencies_missing", detail=str(e))
                result.warnings.append(f"RTMScore GNN: dependencias no disponibles ({e}). Instale torch-geometric para activar el Nivel 2.")
            except Exception as e:
                # Cualquier otro error — no bloquear el pipeline
                log.error("gnn_rescore_failed", error=str(e), smiles=request.smiles[:50])
                result.warnings.append(f"RTMScore GNN: error durante la inferencia ({type(e).__name__}). Score GNN no disponible para esta molécula.")
        else:
            result.warnings.append("RTMScore GNN: la pose 1 no tiene coordenadas PDBQT válidas. Score GNN omitido.")

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    result.inference_time_ms = elapsed_ms

    log.info(
        "rescore_ok",
        smiles=request.smiles[:50],
        score_a=result.score_a,
        gnn_score=result.gnn_score,
        delta=result.delta.delta,
        in_domain=result.applicability_domain.in_domain,
        time_ms=round(elapsed_ms, 1),
    )

    return result


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


def _check_prolif() -> bool:
    """Verificar que ProLIF + MDAnalysis están importables."""
    try:
        import MDAnalysis  # noqa: F401
        import prolif  # noqa: F401
        return True
    except ImportError:
        return False


def _check_xgboost() -> bool:
    """Verificar que XGBoost está importable."""
    try:
        import xgboost  # noqa: F401
        return True
    except ImportError:
        return False


def _check_gnn() -> bool:
    """Verificar que las dependencias GNN (PyG) y los pesos están disponibles."""
    try:
        import os

        import torch
        import torch_geometric
        import torch_scatter
        return os.path.exists("trained_models/rtmscore_model1.pth")
    except ImportError:
        return False
