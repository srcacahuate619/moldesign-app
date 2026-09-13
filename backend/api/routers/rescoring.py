"""
api/routers/rescoring.py (v1.3)

Endpoints de rescoring ML — ahora integrados directamente en el backend.

═══════════════════════════════════════════════════════════════════════
Antes: sidecar HTTP separado en :8001.
Ahora: llamada directa a model_manager.predict() dentro del mismo proceso.

Endpoints:
  GET  /rescoring/health  → health check del modulo
  GET  /rescoring/info    → metadata del modelo
  GET  /rescoring/ram     → uso de memoria del proceso (MB)
  POST /rescoring/score   → prediccion directa (opcional, sin HTTP)
═══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/rescoring", tags=["ML Rescoring"])


class RescoringHealthResponse(BaseModel):
    mode: str
    available: bool
    model_version: str | None = None
    families_trained: list[str] = []
    ram_mb: float = 0.0


class RescoringRAMResponse(BaseModel):
    mode: str
    process_ram_mb: float
    estimated_idle_ram_mb: float
    note: str


@router.get("/health", response_model=RescoringHealthResponse)
async def rescoring_health():
    """
    Estado del modulo de rescoring ML integrado.

    Responde si el model_manager esta cargado y disponible.
    """
    try:
        from services.rescoring_service import is_available, get_model_info, get_current_ram_usage_mb

        ok = is_available()
        info = get_model_info() if ok else {}
        ram = get_current_ram_usage_mb()

        return RescoringHealthResponse(
            mode="direct (in-process, unified v1.3)",
            available=ok,
            model_version=info.get("model_version"),
            families_trained=info.get("families_trained", []),
            ram_mb=ram,
        )
    except Exception:
        return RescoringHealthResponse(
            mode="direct (import failed)",
            available=False,
            ram_mb=-1.0,
        )


@router.get("/info")
async def rescoring_info():
    """
    Metadata del modelo de rescoring (version, metricas, training).
    """
    try:
        from services.rescoring_service import get_model_info
        return get_model_info()
    except Exception as e:
        return {"error": str(e), "status": "unavailable"}


@router.get("/ram", response_model=RescoringRAMResponse)
async def rescoring_ram():
    """
    Medicion de RAM actual del proceso.

    Util para entender el impacto del rescoring unificado en la memoria
    del usuario final.

    La memoria reportada es la RSS (Resident Set Size) del proceso Python
    completo (backend + rescoring juntos).
    """
    try:
        from services.rescoring_service import get_current_ram_usage_mb

        ram = get_current_ram_usage_mb()

        return RescoringRAMResponse(
            mode="unified (backend + rescoring in-process)",
            process_ram_mb=ram,
            estimated_idle_ram_mb=ram,  # sin carga de trabajo activa
            note=(
                "RAM total del proceso Python (backend + rescoring unificados). "
                "Sin torch cargado: ~600 MB idle esperado. "
                "Con torch + GNN: ~1.3 GB. "
                "Comparado con arquitectura anterior (2 procesos separados): ahorro ~1.8 GB."
            ),
        )
    except Exception as e:
        return RescoringRAMResponse(
            mode="error",
            process_ram_mb=-1,
            estimated_idle_ram_mb=-1,
            note=str(e),
        )
