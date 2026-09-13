"""
app.py — Servidor FastAPI para ESMFold local.

Endpoints:
  GET  /health    → health check (usado por el server Ubuntu)
  GET  /status    → estado detallado (versión, modo, last_activity)
  POST /predict   → recibe {protein_pdb, peptide_smiles, num_poses, ...}
                    devuelve {poses: [...]}
  POST /shutdown  → apagado explícito (requiere token)

Auto-shutdown:
  Si no llega ningún request en `shutdown_idle_minutes`, el servicio
  se apaga solo. Cada request resetea el contador.

Inicio:
  uvicorn app:app --host 0.0.0.0 --port 8100
  o usar start.bat
"""

from __future__ import annotations

import asyncio
import os
import secrets
import signal
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import ServiceConfig, get_config
from logger import get_logger, setup_logging
from predictor import (
    PredictionResult,
    PredictedPose,
    make_predictor,
    BasePredictor,
)

# ── Bootstrap ─────────────────────────────────────────────────────────────

_cfg: ServiceConfig = get_config()
setup_logging(_cfg.log_dir, _cfg.log_level)
log = get_logger("esmfold.app")

# Token de shutdown (auto-generado al arranque; loggeado una vez).
SHUTDOWN_TOKEN: str = secrets.token_urlsafe(24)

# Estado global
_predictor: BasePredictor | None = None
_last_activity: float = time.monotonic()
_start_time: float = time.monotonic()
_total_predictions: int = 0
_total_errors: int = 0
_shutdown_event = asyncio.Event()


# ── Schemas ───────────────────────────────────────────────────────────────


class PredictRequest(BaseModel):
    protein_pdb: str = Field(..., description="Contenido del archivo PDB del receptor.")
    peptide_smiles: str = Field(..., description="SMILES del péptido a acoplar.")
    num_poses: int = Field(default=5, ge=1, le=20, description="Número de poses a devolver (cabeado a max_poses del config)")
    grid_center: tuple[float, float, float] | None = Field(default=None)
    grid_size: tuple[float, float, float] | None = Field(default=None)


class PoseResponse(BaseModel):
    rank: int
    #: Confianza ESTRUCTURAL del plegado (pLDDT/100). No es una afinidad.
    confidence: float
    peptide_pdb: str
    ligand_sdf: str | None = None
    #: Salida literal de Vina en kcal/mol, o `None` si esta pose no pasó por
    #: Vina. Antes no se transmitía: el sidecar la convertía en `confidence`
    #: —con el signo invertido— y la tiraba. Ver `predictor.py::PredictedPose`.
    vina_affinity_kcal_mol: float | None = None
    #: "vina_docked" | "folded_structure_only" | "stub".
    origen: str = "vina_docked"
    rmsd: float | None = None


class PredictResponse(BaseModel):
    success: bool
    method: str
    poses: list[PoseResponse]
    best_confidence: float | None
    execution_time_s: float
    warnings: list[str]
    error: str | None = None
    scientific_status: str = "EXPERIMENTAL"
    transfer_manifest: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    mode: str
    uptime_seconds: float
    last_activity_seconds_ago: float
    total_predictions: int
    total_errors: int


# ── Helpers ───────────────────────────────────────────────────────────────


def _touch_activity() -> None:
    global _last_activity
    _last_activity = time.monotonic()


def _result_to_response(r: PredictionResult) -> PredictResponse:
    return PredictResponse(
        success=r.success,
        method=r.method,
        poses=[
            PoseResponse(
                rank=p.rank,
                confidence=p.confidence,
                peptide_pdb=p.ligand_pdb,
                ligand_sdf=getattr(p, "ligand_sdf", None),
                vina_affinity_kcal_mol=getattr(p, "vina_affinity_kcal_mol", None),
                origen=getattr(p, "origen", "vina_docked"),
                rmsd=p.rmsd,
            )
            for p in r.poses
        ],
        best_confidence=r.best_confidence,
        execution_time_s=r.execution_time_s,
        warnings=r.warnings,
        error=r.error,
        scientific_status=r.scientific_status,
        transfer_manifest=r.transfer_manifest,
    )


async def _watchdog_idle_shutdown() -> None:
    """Tarea en background: apaga el servicio tras `shutdown_idle_minutes` de inactividad."""
    if _cfg.shutdown_idle_minutes <= 0:
        log.info("Auto-shutdown desactivado (shutdown_idle_minutes <= 0)")
        return

    log.info(
        "Watchdog de inactividad activo",
        extra={"idle_minutes": _cfg.shutdown_idle_minutes},
    )
    while not _shutdown_event.is_set():
        try:
            await asyncio.wait_for(
                _shutdown_event.wait(),
                timeout=_cfg.watchdog_interval_seconds,
            )
            break  # shutdown solicitado
        except asyncio.TimeoutError:
            idle = (time.monotonic() - _last_activity) / 60.0
            if idle >= _cfg.shutdown_idle_minutes:
                log.warning(
                    f"Sin actividad por {idle:.1f} min — apagando servicio",
                    extra={"idle_min": round(idle, 2)},
                )
                # Pedir cierre limpio al event loop principal
                os._exit(0)


# ── Lifespan ──────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _predictor

    log.info("=" * 60)
    log.info(f"ESMFold Local Service arrancando")
    log.info(f"  host          : {_cfg.host}")
    log.info(f"  port          : {_cfg.port}")
    log.info(f"  modo          : {_cfg.predictor_mode}")
    log.info(f"  model_dir     : {_cfg.model_dir}")
    log.info(f"  idle_shutdown : {_cfg.shutdown_idle_minutes} min")
    log.info(f"  shutdown_token: {SHUTDOWN_TOKEN}")
    log.info("=" * 60)

    # ═════════════════════════════════════════════════════════════
    # v1.3: ON-DEMAND LOADING — El modelo NO se carga al arranque.
    # Se crea el predictor pero `load()` se llama en el primer
    # /predict request, no en el lifespan. Esto ahorra ~3.7 GB RAM
    # si el usuario nunca usa peptide docking.
    #
    # Impacto: primer predict tarda 30-90s en vez de instantáneo,
    # pero el usuario no paga RAM por una feature que no usa.
    # ═════════════════════════════════════════════════════════════
    try:
        _predictor = make_predictor(
            mode=_cfg.predictor_mode,
            model_dir=str(_cfg.model_dir),
            device=_cfg.torch_device,
        )
        log.info("predictor_created",
                 mode=_cfg.predictor_mode,
                 loaded=False,
                 msg="Modelo se cargara on-demand en primer /predict")
    except Exception as e:
        log.error(f"Fallo creando predictor: {e}", exc_info=True)
        raise

    # Lanzar watchdog
    wd_task = asyncio.create_task(_watchdog_idle_shutdown())

    _touch_activity()
    yield

    log.info("Cerrando servicio ESMFold local...")
    _shutdown_event.set()
    wd_task.cancel()
    try:
        await wd_task
    except (asyncio.CancelledError, Exception):
        pass


# ── App ───────────────────────────────────────────────────────────────────


app = FastAPI(
    title="ESMFold Local Service",
    version="1.0.0",
    description="Servicio local on-demand para docking péptido-proteína (Nivel 3 MolDesign).",
    lifespan=lifespan,
)


@app.middleware("http")
async def activity_middleware(request: Request, call_next):
    _touch_activity()
    response = await call_next(request)
    return response


# ── Endpoints ─────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    if _predictor is None:
        raise HTTPException(status_code=503, detail="Predictor no inicializado")
    return HealthResponse(
        status="ok",
        mode=_cfg.predictor_mode,
        uptime_seconds=round(time.monotonic() - _start_time, 2),
        last_activity_seconds_ago=round(time.monotonic() - _last_activity, 2),
        total_predictions=_total_predictions,
        total_errors=_total_errors,
    )


@app.get("/status")
async def status_endpoint() -> dict[str, Any]:
    """Información más detallada que /health — útil para debugging."""
    return {
        "service": "esmfold-local",
        "version": "1.0.0",
        "mode": _cfg.predictor_mode,
        "model_dir": str(_cfg.model_dir),
        "torch_device": _cfg.torch_device,
        "uptime_seconds": round(time.monotonic() - _start_time, 2),
        "idle_minutes": round((time.monotonic() - _last_activity) / 60.0, 2),
        "shutdown_idle_minutes": _cfg.shutdown_idle_minutes,
        "total_predictions": _total_predictions,
        "total_errors": _total_errors,
        "pid": os.getpid(),
        "predictor_loaded": _predictor is not None and getattr(_predictor, "_model_loaded", False),
        "predictor_created": _predictor is not None,
        "loading_mode": "on-demand (v1.3)" if not getattr(_predictor, "_model_loaded", False) else "loaded",
    }


@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest) -> PredictResponse:
    global _total_predictions, _total_errors

    if _predictor is None:
        raise HTTPException(status_code=503, detail="Predictor no inicializado")

    # ═════════════════════════════════════════════════════════════
    # v1.3: ON-DEMAND LOADING — Cargar modelo en el primer request.
    # El predictor se creo en el lifespan pero load() fue diferido.
    # Esto ahorra ~3.7 GB de RAM en idle para usuarios que nunca
    # usan peptide docking.
    # ═════════════════════════════════════════════════════════════
    try:
        if not getattr(_predictor, "_model_loaded", False):
            log.info("cargando_modelo_on_demand", mode=_cfg.predictor_mode)
            await _predictor.load()
            _predictor._model_loaded = True
            log.info("modelo_cargado_on_demand", mode=_cfg.predictor_mode)
    except Exception as e:
        log.error(f"Fallo cargando modelo on-demand: {e}")
        _total_errors += 1
        raise HTTPException(status_code=503, detail=f"Modelo no disponible: {e}")

    # Validar tamaño del payload
    size_mb = len(req.protein_pdb.encode("utf-8")) / (1024 * 1024)
    if size_mb > _cfg.max_protein_pdb_mb:
        raise HTTPException(
            status_code=413,
            detail=f"PDB del receptor excede {size_mb:.1f} MB (máx {_cfg.max_protein_pdb_mb} MB)",
        )

    # Limitar num_poses
    num_poses = min(req.num_poses, _cfg.max_poses)

    log.info(
        f"POST /predict  smiles={req.peptide_smiles[:40]!r}  poses={num_poses}  pdb_size={size_mb:.2f}MB"
    )

    try:
        result: PredictionResult = await asyncio.wait_for(
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
        log.error(f"Predict timeout después de {_cfg.predict_timeout_seconds}s")
        raise HTTPException(
            status_code=504,
            detail=f"Timeout después de {_cfg.predict_timeout_seconds}s",
        )
    except Exception as e:
        _total_errors += 1
        log.error(f"Error en predict: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")

    _total_predictions += 1
    if not result.success:
        _total_errors += 1
        log.warning(f"Predict sin éxito: {result.error}")
    else:
        log.info(
            f"Predict OK  best_conf={result.best_confidence}  elapsed={result.execution_time_s}s"
        )

    return _result_to_response(result)


@app.post("/shutdown")
async def shutdown(token: str | None = None) -> dict[str, Any]:
    """
    Apagado explícito. Requiere token (devuelto al arranque en logs).
    Pensado para que el server Ubuntu pueda apagar limpiamente tras finalizar.
    """
    # Token puede venir por query (?token=) o header (X-Shutdown-Token)
    provided = token
    if provided is None:
        # FastAPI ya extrajo query; si vino por header, lo recogemos:
        from fastapi import Request  # noqa: F401

    if provided != SHUTDOWN_TOKEN:
        raise HTTPException(status_code=403, detail="Token inválido")

    log.info("Shutdown solicitado vía endpoint — cerrando...")

    async def _delayed_exit():
        await asyncio.sleep(0.5)
        os._exit(0)

    asyncio.create_task(_delayed_exit())
    return {"status": "shutting_down", "message": "Servicio cerrándose"}


# ── Arranque directo ─────────────────────────────────────────────────────


def main() -> None:
    import uvicorn

    uvicorn.run(
        "app:app",
        host=_cfg.host,
        port=_cfg.port,
        log_level=_cfg.log_level.lower(),
        access_log=False,  # ya tenemos nuestros logs estructurados
    )


if __name__ == "__main__":
    main()