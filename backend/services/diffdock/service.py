"""
services/diffdock/service.py

Capa de servicio para DiffDock con degradación elegante.

DiffDock puede ejecutarse de dos formas:
1. **API externa**: Llamada a un servidor DiffDock (recomendado en producción)
2. **Local**: Ejecución directa si se tiene el modelo instalado + GPU

Si DiffDock no está disponible, el sistema continúa con Vina solamente.
La ausencia de DiffDock NUNCA bloquea la evaluación.

Referencia:
  Corso, G., Stärk, H., Jing, B., Barzilay, R., & Jaakkola, T.
  "DiffDock: Diffusion Steps, Twists, and Turns for Molecular Docking"
  ICLR 2023. arXiv:2210.01776
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.config import get_settings
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class DiffDockPose:
    """Una pose predicha por DiffDock."""
    rank: int
    confidence: float  # Score de confianza del modelo (-∞ a +∞, mayor = mejor)
    affinity_predicted: float | None  # Si el modelo LBAP está disponible
    ligand_pdb: str  # Coordenadas del ligando en formato PDB
    rmsd_from_input: float | None = None


@dataclass
class DiffDockResult:
    """Resultado completo de una predicción DiffDock."""
    success: bool
    poses: list[DiffDockPose] = field(default_factory=list)
    best_confidence: float | None = None
    method: str = "DiffDock"
    version: str | None = None
    execution_time_s: float | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def scientific_context(self) -> str:
        """Contexto científico que acompaña al resultado."""
        return (
            "DiffDock usa un modelo generativo de difusión entrenado en PDBBind. "
            "El score de confianza NO es directamente comparable con afinidades de Vina (kcal/mol). "
            "Los resultados de DiffDock deben interpretarse como poses alternativas "
            "para validación cruzada, no como reemplazo de Vina."
        )


class DiffDockService:
    """
    Servicio de DiffDock con degradación elegante.

    Si DiffDock no está configurado o no responde, devuelve un resultado
    vacío con warning explícito. Nunca bloquea el pipeline principal.
    """

    def __init__(self):
        self._api_url: str | None = None
        self._available: bool | None = None  # None = no checkeado aún
        self._load_config()

    def _load_config(self):
        """Intenta cargar configuración de DiffDock desde settings."""
        try:
            settings = get_settings()
            self._api_url = settings.diffdock_api_url
        except Exception:
            self._api_url = None

    @property
    def is_configured(self) -> bool:
        """True si hay una URL de API configurada."""
        return self._api_url is not None and len(self._api_url) > 0

    async def check_health(self) -> dict[str, Any]:
        """Verifica si el servicio DiffDock está disponible."""
        if not self.is_configured:
            return {
                "status": "not_configured",
                "message": "DiffDock API URL no configurada. "
                           "El sistema usa solo AutoDock Vina para docking.",
            }

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._ping_api)
            self._available = result
            return {
                "status": "healthy" if result else "unhealthy",
                "api_url": self._api_url,
            }
        except Exception as e:
            self._available = False
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    def _ping_api(self) -> bool:
        """Ping síncrono al servicio DiffDock."""
        if not self._api_url:
            return False
        try:
            req = Request(f"{self._api_url}/health", method="GET")
            with urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except (HTTPError, URLError, OSError):
            return False

    async def predict(
        self,
        protein_pdb_path: str,
        ligand_sdf_path: str,
        num_poses: int = 5,
    ) -> DiffDockResult:
        """
        Ejecuta DiffDock para predecir poses de docking.

        Si DiffDock no está disponible, devuelve un resultado vacío
        con warning explícito — NUNCA simula resultados.

        Args:
            protein_pdb_path: Ruta al archivo PDB de la proteína
            ligand_sdf_path: Ruta al archivo SDF/MOL del ligando
            num_poses: Número de poses a generar

        Returns:
            DiffDockResult con las poses predichas o error explícito.
        """
        if not self.is_configured:
            return DiffDockResult(
                success=False,
                error="DiffDock no está configurado",
                warnings=[
                    "DiffDock no está configurado en este servidor. "
                    "Solo se usó AutoDock Vina para el docking. "
                    "Configure DIFFDOCK_API_URL para habilitar validación cruzada."
                ],
            )

        if self._available is False:
            return DiffDockResult(
                success=False,
                error="DiffDock no está disponible actualmente",
                warnings=[
                    "El servicio DiffDock no respondió. "
                    "Solo se usó AutoDock Vina para esta evaluación."
                ],
            )

        try:
            import time
            start = time.monotonic()

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._call_api,
                protein_pdb_path,
                ligand_sdf_path,
                num_poses,
            )

            elapsed = time.monotonic() - start

            if result is None:
                return DiffDockResult(
                    success=False,
                    error="DiffDock API no devolvió resultados",
                    warnings=["DiffDock no pudo generar poses para esta molécula."],
                )

            poses = []
            for i, pose_data in enumerate(result.get("poses", [])):
                poses.append(DiffDockPose(
                    rank=i + 1,
                    confidence=pose_data.get("confidence", 0.0),
                    affinity_predicted=pose_data.get("affinity"),
                    ligand_pdb=pose_data.get("ligand_pdb", ""),
                    rmsd_from_input=pose_data.get("rmsd"),
                ))

            best_conf = max((p.confidence for p in poses), default=None)

            log.info(
                "DiffDock predicción completada",
                num_poses=len(poses),
                best_confidence=best_conf,
                elapsed_s=round(elapsed, 2),
            )

            return DiffDockResult(
                success=True,
                poses=poses,
                best_confidence=best_conf,
                version=result.get("version"),
                execution_time_s=round(elapsed, 2),
                warnings=[
                    "Los scores de confianza de DiffDock NO son comparables "
                    "con las afinidades (kcal/mol) de AutoDock Vina.",
                ],
            )

        except Exception as e:
            log.warning("DiffDock falló, continuando con Vina", error=str(e))
            return DiffDockResult(
                success=False,
                error=str(e),
                warnings=[
                    f"DiffDock falló ({type(e).__name__}). "
                    "Solo se usó AutoDock Vina para esta evaluación."
                ],
            )

    def _call_api(
        self,
        protein_pdb_path: str,
        ligand_sdf_path: str,
        num_poses: int,
    ) -> dict | None:
        """Llamada síncrona a la API de DiffDock."""
        if not self._api_url:
            return None

        # Leer archivos
        protein_content = Path(protein_pdb_path).read_text()
        ligand_content = Path(ligand_sdf_path).read_text()

        payload = json.dumps({
            "protein_pdb": protein_content,
            "ligand_sdf": ligand_content,
            "num_poses": num_poses,
        }).encode("utf-8")

        req = Request(
            f"{self._api_url}/predict",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError) as e:
            log.warning("DiffDock API error", error=str(e))
            return None


# Singleton
_diffdock_service: DiffDockService | None = None


def get_diffdock_service() -> DiffDockService:
    """Obtiene la instancia singleton del servicio DiffDock."""
    global _diffdock_service
    if _diffdock_service is None:
        _diffdock_service = DiffDockService()
    return _diffdock_service
