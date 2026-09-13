"""
services/rescoring_service.py

Bridge directo al modulo de rescoring ML sin HTTP sidecar.

═══════════════════════════════════════════════════════════════════════
Antes (v1.2):
  Backend :8000 → HTTP POST → Rescoring :8001
  → 2 procesos Python, rdkit duplicado, +1.8 GB RAM idle

Ahora (v1.3):
  Backend :8000 → model_manager.predict() [llamada directa]
  → 1 proceso Python, rdkit compartido, ~600 MB RAM idle
═══════════════════════════════════════════════════════════════════════

Dependencias: xgboost, numpy, scipy, pandas, rdkit, prolif, MDAnalysis
(todas ya en environment-desktop.yml + requirements-desktop.txt)

torch + PyG (GNN): opcionales, se importan lazy via gnn_service.py
solo cuando run_gnn=True en el primer request.

F-14 (encapsulación): este módulo es ahora una capa de compatibilidad.
Toda la resolución de paths, la mutación de sys.path, los defaults
RESCORING_*_PATH y el import del sidecar viven en UN solo módulo:
services/rescoring_bridge.py. Este wrapper mantiene la API pública que
los callers (rescoring_client, api/routers/rescoring, analog_generator,
api/main) ya consumen: _get_model_manager(), is_available(),
get_model_info(), predict_rescore(), predict_batch_rescore(),
get_current_ram_usage_mb().
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from services.rescoring_bridge import get_model_manager as _bridge_get_model_manager
from utils.logger import get_logger

log = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_model_manager():
    """
    Compat wrapper: delega la carga única de ModelManager al bridge
    services/rescoring_bridge.py (único punto autorizado a mutar
    sys.path e inicializar RESCORING_*_PATH).

    Devuelve la misma tupla de siempre:
    (ModelManager, RescoreRequest, RescoreResponse, PoseData)
    o (None, None, None, None) si el import/load falla.
    """
    return _bridge_get_model_manager()


def is_available() -> bool:
    """True si el modulo de rescoring se cargo correctamente."""
    mm, _, _, _ = _get_model_manager()
    return mm is not None and bool(mm.is_loaded)


def get_model_info() -> dict[str, Any]:
    """Metadata del modelo cargado."""
    mm, _, _, _ = _get_model_manager()
    if mm is None or not mm.is_loaded:
        return {"model_version": None, "status": "unavailable"}
    return mm.get_info()


def predict_rescore(
    smiles: str,
    poses: list[dict],
    target_pdb_path: str,
    molecular_weight: float,
    logp: float,
    tpsa: float,
    hbd: int,
    hba: int,
    rotatable_bonds: int,
    qed: float,
    target_family: str | None = None,
    grid_center: list[float] | None = None,
    grid_size: list[float] | None = None,
    run_gnn: bool = False,
) -> dict[str, Any] | None:
    """
    Predecir score de rescoring para una molecula.

    v1.3: Soporta GNN RTMScore (Nivel 2) via run_gnn=True.
    """
    mm, Req, Res, PoseDataCls = _get_model_manager()
    if mm is None or not mm.is_loaded:
        log.warning("rescoring_not_available")
        return None

    try:
        pose_objects = []
        for p in poses:
            pose_objects.append(PoseDataCls(
                vina_score=p.get("vina_score", 0.0),
                pdbqt_block=p.get("pdbqt_block", p.get("pdbqt", "")),
            ))

        request = Req(
            smiles=smiles, poses=pose_objects,
            target_pdb_path=target_pdb_path,
            molecular_weight=molecular_weight, logp=logp, tpsa=tpsa,
            hbd=hbd, hba=hba, rotatable_bonds=rotatable_bonds, qed=qed,
            target_family=target_family, grid_center=grid_center, grid_size=grid_size,
            run_gnn=run_gnn,
        )

        import time
        start = time.monotonic()

        response = mm.predict(request)

        elapsed = (time.monotonic() - start) * 1000

        result = {
            "score_a": response.score_a,
            "score_null": response.score_null,
            "delta": {
                "delta": response.delta.delta if response.delta else 0,
                "semaphore": response.delta.semaphore if response.delta else "YELLOW",
                "interpretation": response.delta.interpretation if response.delta else "",
            },
            "classifier_prob": response.classifier_prob,
            "gnn_score": response.gnn_score,
            "model_version": response.model_version,
            "inference_time_ms": round(elapsed, 1),
            "warnings": response.warnings,
            "shap_values": response.shap_values,
            "features_used": response.features_used,
            # F-21: transparencia del modelo usado. El sidecar rellena
            # model_used/fallback_reason en el quality gate; in_domain viene
            # del ApplicabilityDomainChecker. getattr para tolerar sidecars
            # previos sin estos campos. engine_used no existe en este path
            # (model_manager no usa el router gpu/cpu) → siempre None.
            "in_applicability_domain": (
                response.applicability_domain.in_domain
                if response.applicability_domain is not None else None
            ),
            "model_used": getattr(response, "model_used", None),
            "fallback_reason": getattr(response, "fallback_reason", None),
            "engine_used": getattr(response, "engine_used", None),
        }
        return result

    except Exception as e:
        log.error("rescoring_predict_failed", error=str(e), smiles=smiles[:50])
        return None


def predict_batch_rescore(molecules: list[dict]) -> list[dict[str, Any]] | None:
    """
    Prediccion vectorizada para multiples moleculas (v1.3).

    En vez de llamar predict_rescore() N veces (HTTP o funcion),
    procesa todas en una sola llamada XGBoost.predict().
    Speedup: ~10-50x en batch de N ≥ 10 moleculas.

    Args:
        molecules: Lista de dicts, cada uno con:
            smiles, target_pdb_path, poses, molecular_weight,
            logp, tpsa, hbd, hba, rotatable_bonds, qed

    Returns:
        Lista de dicts con score_a, score_null, classifier_prob, delta.
        None si el modulo no esta disponible.
    """
    mm, Req, _, PoseDataCls = _get_model_manager()
    if mm is None or not mm.is_loaded:
        log.warning("rescoring_not_available_for_batch")
        return None

    try:
        # Construir requests compatibles con RescoreRequest
        requests = []
        for mol in molecules:
            pose_objects = []
            for p in mol.get("poses", []):
                pose_objects.append(PoseDataCls(
                    vina_score=p.get("vina_score", p.get("affinity", 0.0)),
                    pdbqt_block=p.get("pdbqt_block", p.get("pdbqt", "")),
                ))
            requests.append(Req(
                smiles=mol.get("smiles", ""),
                poses=pose_objects,
                target_pdb_path=mol.get("target_pdb_path", ""),
                molecular_weight=mol.get("molecular_weight", 300),
                logp=mol.get("logp", 3.0),
                tpsa=mol.get("tpsa", 60),
                hbd=mol.get("hbd", 0),
                hba=mol.get("hba", 0),
                rotatable_bonds=mol.get("rotatable_bonds", 0),
                qed=mol.get("qed", 0.5),
                run_gnn=False,
            ))

        import time
        start = time.monotonic()
        results = mm.predict_batch(requests)
        elapsed = (time.monotonic() - start) * 1000

        log.info("batch_rescore_complete", n=len(molecules), time_ms=round(elapsed, 1))
        return results

    except Exception as e:
        log.error("batch_rescore_failed", error=str(e), n_mols=len(molecules))
        return None


def get_current_ram_usage_mb() -> float:
    """
    Retornar uso de RAM actual del proceso en MB.

    Util para benchmarking de memoria del usuario final.
    """
    try:
        import psutil
        proc = psutil.Process()
        return round(proc.memory_info().rss / (1024 * 1024), 1)
    except Exception:
        return -1.0
