"""
services/colabfold/service.py

Capa de servicio para ColabFold / AlphaFold-Multimer.
ColabFold predice la estructura 3D del complejo plegando el receptor y el péptido a partir de secuencias.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from core.config import get_settings
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class ColabFoldPose:
    """Un modelo de complejo retornado por ColabFold."""
    rank: int
    iptm: float          # Métricas de calidad de la interfaz (0 a 1)
    ptm: float           # Métrica global de plegamiento (0 a 1)
    plddt: float         # Confianza por residuo promedio (0 a 100)
    complex_pdb: str     # Coordenadas del complejo completo en PDB


@dataclass
class ColabFoldResult:
    """Resultado completo de ColabFold."""
    success: bool
    poses: list[ColabFoldPose] = field(default_factory=list)
    best_plddt: float | None = None
    best_iptm: float | None = None
    method: str = "ColabFold"
    execution_time_s: float | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def scientific_context(self) -> str:
        """Contexto científico de ColabFold."""
        return (
            "ColabFold / AlphaFold-Multimer pliega tridimensionalmente el complejo proteína-péptido "
            "de forma de novo. Ofrece la mayor precisión estructural, pero a un costo de cómputo elevado."
        )


class ColabFoldService:
    """Servicio cliente para ColabFold."""

    def __init__(self):
        self._api_url: str | None = None
        self._available: bool | None = None
        self._load_config()

    def _load_config(self):
        try:
            settings = get_settings()
            self._api_url = settings.colabfold_api_url
        except Exception:
            self._api_url = None

    @property
    def is_configured(self) -> bool:
        return self._api_url is not None and len(self._api_url) > 0

    async def check_health(self) -> dict[str, Any]:
        if not self.is_configured:
            return {
                "status": "not_configured",
                "message": "ColabFold no está configurado."
            }
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self._ping_api)
            self._available = result
            return {
                "status": "healthy" if result else "unhealthy",
                "api_url": self._api_url
            }
        except Exception as e:
            self._available = False
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    def _ping_api(self) -> bool:
        if not self._api_url:
            return False
        try:
            req = Request(f"{self._api_url}/health", method="GET")
            with urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _extract_sequence_from_pdb(self, pdb_content: str) -> str:
        """Extracts single-letter amino acid sequence from CA atoms in PDB."""
        three_to_one = {
            'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D', 'CYS': 'C',
            'GLU': 'E', 'GLN': 'Q', 'GLY': 'G', 'HIS': 'H', 'ILE': 'I',
            'LEU': 'L', 'LYS': 'K', 'MET': 'M', 'PHE': 'F', 'PRO': 'P',
            'SER': 'S', 'THR': 'T', 'TRP': 'W', 'TYR': 'Y', 'VAL': 'V'
        }
        seq = []
        seen = set()
        for line in pdb_content.splitlines():
            if line.startswith("ATOM  ") and line[12:16].strip() == "CA":
                res_name = line[17:20].strip()
                chain_id = line[21]
                res_seq = line[22:26].strip()
                key = (chain_id, res_seq)
                if key not in seen:
                    seen.add(key)
                    seq.append(three_to_one.get(res_name, 'X'))
        return "".join(seq)

    async def predict(
        self,
        protein_pdb_path: str,
        peptide_smiles: str,
    ) -> ColabFoldResult:
        """Envía el docking a ColabFold."""
        if not self.is_configured:
            return ColabFoldResult(
                success=False,
                error="ColabFold no está configurado",
                warnings=["Servicio ColabFold no configurado. Se usó AutoDock Vina."]
            )

        if self._available is False:
            return ColabFoldResult(
                success=False,
                error="ColabFold no está disponible",
                warnings=["Servicio de ColabFold fuera de línea. Se usó AutoDock Vina."]
            )

        try:
            import time
            start = time.monotonic()

            protein_pdb = Path(protein_pdb_path).read_text()
            protein_seq = self._extract_sequence_from_pdb(protein_pdb)

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                self._call_api,
                protein_seq,
                peptide_smiles,
            )

            elapsed = time.monotonic() - start

            if result is None:
                return ColabFoldResult(
                    success=False,
                    error="ColabFold no retornó ningún resultado",
                    warnings=["Fallo en el plegamiento de ColabFold."]
                )

            poses = []
            for i, p in enumerate(result.get("models", [])):
                poses.append(ColabFoldPose(
                    rank=i + 1,
                    iptm=p.get("iptm", 0.0),
                    ptm=p.get("ptm", 0.0),
                    plddt=p.get("plddt", 0.0),
                    complex_pdb=p.get("complex_pdb", ""),
                ))

            best_plddt = max((p.plddt for p in poses), default=None)
            best_iptm = max((p.iptm for p in poses), default=None)

            return ColabFoldResult(
                success=True,
                poses=poses,
                best_plddt=best_plddt,
                best_iptm=best_iptm,
                execution_time_s=round(elapsed, 2),
            )

        except Exception as e:
            log.warning("ColabFold falló", error=str(e))
            return ColabFoldResult(
                success=False,
                error=str(e),
                warnings=[f"Error en ColabFold ({type(e).__name__}). Se usó AutoDock Vina."]
            )

    def _call_api(self, protein_sequence: str, peptide_smiles: str) -> dict | None:
        if not self._api_url:
            return None

        payload = json.dumps({
            "protein_sequence": protein_sequence,
            "peptide_smiles": peptide_smiles,
        }).encode("utf-8")

        req = Request(
            f"{self._api_url}/predict",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(req, timeout=900) as resp:  # timeout más largo para ColabFold
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            log.warning("Fallo en la comunicación con ColabFold API", error=str(e))
            return None


_colabfold_service: ColabFoldService | None = None


def get_colabfold_service() -> ColabFoldService:
    global _colabfold_service
    if _colabfold_service is None:
        _colabfold_service = ColabFoldService()
    return _colabfold_service
