"""Construcción determinista del contexto científico para reportes IA.

Los transportes síncrono y SSE comparten exactamente este view-model. Mantenerlo
fuera del router evita que un reporte cambie su contexto científico según el
proveedor o el modo de entrega.
"""

from __future__ import annotations

from typing import Any

from core.models import AIReportRequest, DockingPose, DockingResult, PhysicochemicalProperties
from scoring.engine import calculate_score_breakdown


def build_evaluation_report_request(
    *,
    result: Any,
    molecule_smiles: str,
    target_name: str,
    mutation_type: Any,
    target_hotspots: list[dict] | None,
    user_id: str | None = None,
) -> AIReportRequest:
    """Reconstruye el contrato ``AIReportRequest`` desde un resultado persistido.

    Las dos rutas de reporte conservan sus propios permisos, cache, streaming y
    persistencia. Esta función sólo concentra la traducción determinista de los
    resultados científicos al contexto que recibe el intérprete.
    """
    properties = PhysicochemicalProperties(
        molecular_weight=result.molecular_weight,
        log_p=result.log_p,
        tpsa=result.tpsa,
        hbd=result.hbd,
        hba=result.hba,
        rotatable_bonds=result.rotatable_bonds,
        heavy_atom_count=result.heavy_atom_count,
        ring_count=result.ring_count,
        lipinski_pass=result.lipinski_pass,
        veber_pass=result.veber_pass,
        qed=result.qed,
        sa_score=result.sa_score if result.sa_score is not None else 0.0,
        sa_reasons=result.sa_reasons if result.sa_reasons is not None else [],
    )
    poses = [
        DockingPose(
            rank=pose["rank"],
            affinity=pose["affinity"],
            rmsd_lb=pose["rmsd_lb"],
            rmsd_ub=pose["rmsd_ub"],
        )
        for pose in (result.docking_poses or [])
    ]
    docking = DockingResult(best_affinity=result.affinity_kcal, poses=poses)
    is_control = bool(result.is_control)
    score_breakdown = calculate_score_breakdown(
        docking,
        properties,
        is_control=is_control,
        gnn_score=result.gnn_score,
        xgb_prob=result.xgb_score,
        clgnn_prob=result.clgnn_score,
        quantum_score=result.quantum_score,
        ums_score=result.ums_score,
        mmgbsa_score=result.mmgbsa_score,
        target_family=result.target_family,
    )

    return AIReportRequest(
        molecule_smiles=molecule_smiles,
        target_name=target_name,
        affinity_kcal=result.affinity_kcal,
        affinity_score=result.affinity_score,
        properties=properties,
        score_breakdown=score_breakdown,
        parent_smiles=None,
        mutation_type=mutation_type,
        is_control=is_control,
        hotspots_hit=result.hotspots_hit,
        target_hotspots=target_hotspots,
        delta_a_null=getattr(result, "delta_a_null", None),
        user_id=user_id,
    )
