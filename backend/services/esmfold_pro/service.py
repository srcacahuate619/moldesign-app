"""
services/esmfold_pro/service.py

Cliente HTTP al sidecar ESMFold-Pro (RFdiffusion, puerto 8300).

Contrato:
  GET  /health   → {"status": "...", "gpu_available": bool, ...}
  POST /predict  → {"success": bool, "poses": [...], ...}

Modo experimental — requiere GPU NVIDIA. Si no está disponible,
devuelve resultado fallido con mensaje claro.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from core.config import get_settings
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class ESMFoldProPose:
    rank: int
    confidence: float
    ligand_pdb: str
    rmsd: float | None = None


@dataclass
class ESMFoldProResult:
    success: bool
    poses: list[ESMFoldProPose] = field(default_factory=list)
    best_confidence: float | None = None
    method: str = "RFdiffusion"
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


class ESMFoldProService:
    HEALTH_TTL: float = 30.0
    PREDICT_TIMEOUT: float = 1200.0  # 20 min

    def __init__(self):
        self._api_url: str | None = None
        self._health_ok: bool = False
        self._health_ts: float = 0.0
        self._load_config()

    def _load_config(self) -> None:
        settings = get_settings()
        port = getattr(settings, "esmfold_pro_desktop_port", 8300)
        self._api_url = f"http://localhost:{port}"

    @property
    def is_configured(self) -> bool:
        return bool(self._api_url)

    async def check_health(self) -> bool:
        now = time.monotonic()
        if now - self._health_ts < self.HEALTH_TTL:
            return self._health_ok
        self._health_ts = now

        if not self._api_url:
            self._health_ok = False
            return False

        try:
            import httpx
        except ImportError:
            self._health_ok = False
            return False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._api_url}/health")
                data = resp.json()
                self._health_ok = data.get("status") in ("healthy", "degraded")
        except Exception:
            self._health_ok = False

        return self._health_ok

    async def predict(
        self,
        protein_pdb: str,
        peptide_smiles: str,
        num_poses: int = 5,
        grid_center: tuple[float, float, float] | None = None,
        grid_size: tuple[float, float, float] | None = None,
    ) -> ESMFoldProResult:
        if not self._api_url:
            return ESMFoldProResult(
                success=False,
                error="ESMFold-Pro (RFdiffusion) no está configurado. Requiere GPU NVIDIA >=8 GB.",
                warnings=["Servicio ESMFold-Pro no configurado (ESMFOLD_PRO_API_URL ausente)."],
            )

        try:
            import httpx
        except ImportError:
            return ESMFoldProResult(
                success=False,
                error="httpx no instalado en el backend.",
            )

        payload = {
            "protein_pdb": protein_pdb,
            "peptide_smiles": peptide_smiles,
            "num_poses": min(num_poses, 5),
        }
        if grid_center:
            payload["grid_center"] = list(grid_center)
        if grid_size:
            payload["grid_size"] = list(grid_size)

        try:
            async with httpx.AsyncClient(timeout=self.PREDICT_TIMEOUT) as client:
                resp = await client.post(
                    f"{self._api_url}/predict",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                return self._parse_response(data)

        except httpx.ConnectError:
            return ESMFoldProResult(
                success=False,
                error="Conexión rechazada: ¿Sidecar ESMFold-Pro corriendo en :8300? Requiere GPU.",
            )
        except httpx.TimeoutException:
            return ESMFoldProResult(
                success=False,
                error=f"Timeout: ESMFold-Pro no respondió en {self.PREDICT_TIMEOUT}s.",
            )
        except Exception as e:
            log.error("esmfold_pro_predict_error", error=str(e))
            return ESMFoldProResult(
                success=False,
                error=f"Error: {type(e).__name__}: {e}",
            )

    @staticmethod
    def _parse_response(data: dict) -> ESMFoldProResult:
        poses = [
            ESMFoldProPose(
                rank=p.get("rank", i + 1),
                confidence=p.get("confidence", 0.5),
                ligand_pdb=p.get("peptide_pdb", p.get("ligand_pdb", "")),
                rmsd=p.get("rmsd"),
            )
            for i, p in enumerate(data.get("poses", []))
        ]
        return ESMFoldProResult(
            success=data.get("success", False),
            poses=poses,
            best_confidence=data.get("best_confidence"),
            method=data.get("method", "RFdiffusion"),
            warnings=data.get("warnings", []),
            error=data.get("error"),
        )


# ── Singleton ──────────────────────────────────────────────────────────────

_esmfold_pro_service: ESMFoldProService | None = None


def get_esmfold_pro_service() -> ESMFoldProService:
    global _esmfold_pro_service
    if _esmfold_pro_service is None:
        _esmfold_pro_service = ESMFoldProService()
    return _esmfold_pro_service
