import httpx
from typing import Any, List
from pydantic import BaseModel
from core.config import get_settings
from utils.logger import get_logger

settings = get_settings()
log = get_logger(__name__)

# ── Bridge directo al rescoring (sin HTTP) ──────────────────────────
# En modo DESKTOP, el rescoring se importa como modulo Python directo
# en vez de llamarlo via HTTP. Esto elimina el segundo proceso Python
# y ahorra ~1.8 GB de RAM (rdkit/torch duplicados).
#
# Si el bridge directo no está disponible, usa el sidecar HTTP local.
_DIRECT_BRIDGE_AVAILABLE = None  # lazy check


def _is_direct_available() -> bool:
    """True si el modul de rescoring se puede importar directamente."""
    global _DIRECT_BRIDGE_AVAILABLE
    if _DIRECT_BRIDGE_AVAILABLE is not None:
        return _DIRECT_BRIDGE_AVAILABLE
    try:
        from services.rescoring_service import is_available
        _DIRECT_BRIDGE_AVAILABLE = is_available()
    except Exception:
        _DIRECT_BRIDGE_AVAILABLE = False
    return _DIRECT_BRIDGE_AVAILABLE

class PoseData(BaseModel):
    pdbqt_block: str
    vina_score: float
    rmsd_lb: float = 0.0
    rmsd_ub: float = 0.0

class RescoreRequest(BaseModel):
    smiles: str
    target_pdb_path: str
    poses: List[PoseData]
    molecular_weight: float
    logp: float
    tpsa: float
    hbd: int
    hba: int
    rotatable_bonds: int
    qed: float
    grid_center: List[float] | None = None
    grid_size: List[float] | None = None
    target_family: str | None = None  # Familia estructural para modelo XGBoost especifico
    run_gnn: bool = False  # Activa RTMScore GNN (Nivel 2) cuando True

async def get_ml_rescore(
    smiles: str,
    target_pdb_path: str,
    poses: List[Any],
    properties: Any,
    grid_center: List[float] | None = None,
    grid_size: List[float] | None = None,
    run_gnn: bool = True,
    target_family: str | None = None,
) -> dict:
    """
    Obtener score de rescoring ML.

    Modo DESKTOP (v1.3): llama directamente a model_manager.predict()
    sin HTTP, sin proceso separado. Ahorra ~1.8 GB RAM.

    Fallback local: llama al sidecar HTTP :8001.
    """
    # ── Intento 1: Bridge directo (DESKTOP) ─────────────────────────
    if _is_direct_available():
        from services.rescoring_service import predict_rescore

        payload_poses = []
        for p in poses:
            p_dict = p.model_dump() if hasattr(p, "model_dump") else p
            payload_poses.append({
                "vina_score": p_dict.get("affinity", 0.0),
                "pdbqt_block": p_dict.get("pdbqt_block") or "",
            })

        result = predict_rescore(
            smiles=smiles,
            poses=payload_poses,
            target_pdb_path=target_pdb_path,
            molecular_weight=properties.molecular_weight,
            logp=properties.log_p,
            tpsa=properties.tpsa,
            hbd=properties.hbd,
            hba=properties.hba,
            rotatable_bonds=properties.rotatable_bonds,
            qed=properties.qed,
            target_family=target_family,
            grid_center=grid_center,
            grid_size=grid_size,
            run_gnn=run_gnn,
        )
        if result is not None:
            return result
        # Si el bridge fallo, seguir con HTTP

    # ── Intento 2: sidecar HTTP local ──────────────────────────────────────
    url = f"{settings.rescoring_url}/rescore"

    payload_poses = []
    for p in poses:
        p_dict = p.model_dump() if hasattr(p, "model_dump") else p
        payload_poses.append(PoseData(
            pdbqt_block=p_dict.get("pdbqt_block") or "",
            vina_score=p_dict.get("affinity", 0.0),
            rmsd_lb=p_dict.get("rmsd_lb", 0.0),
            rmsd_ub=p_dict.get("rmsd_ub", 0.0),
        ))

    request_data = RescoreRequest(
        smiles=smiles,
        target_pdb_path=target_pdb_path,
        poses=payload_poses,
        molecular_weight=properties.molecular_weight,
        logp=properties.log_p,
        tpsa=properties.tpsa,
        hbd=properties.hbd,
        hba=properties.hba,
        rotatable_bonds=properties.rotatable_bonds,
        qed=properties.qed,
        grid_center=grid_center,
        grid_size=grid_size,
        run_gnn=run_gnn,
        target_family=target_family,
    )

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                url,
                json=request_data.model_dump(),
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": settings.rescoring_api_key,
                },
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        log.error("rescoring_service_error", error=str(e), url=url)
        return {"error": str(e), "fallback": True}
