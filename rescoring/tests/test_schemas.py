"""
tests/test_schemas.py

Contrato de serializacion del RescoreResponse: los campos del pose selector
(Fase 4) son opcionales y su default es None — rutas viejas que construyen o
consumen la respuesta sin esos campos no se ven afectadas.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SIDECAR = Path(__file__).resolve().parent.parent  # rescoring/
sys.path.insert(0, str(_SIDECAR))

from schemas import (  # noqa: E402
    ApplicabilityDomainResult,
    DeltaResult,
    PoseVarianceResult,
    RescoreResponse,
)


def _respuesta_minima() -> RescoreResponse:
    return RescoreResponse(
        score_a=7.0,
        score_null=6.0,
        delta=DeltaResult(
            delta=1.0,
            semaphore="GREEN",
            interpretation="especifico",
        ),
        applicability_domain=ApplicabilityDomainResult(
            in_domain=True,
            mahalanobis_distance=2.0,
            threshold=16.2,
        ),
        pose_variance=PoseVarianceResult(
            score_variance=0.1,
            score_range=1.0,
            poses_analyzed=9,
            poses_passing_filter=9,
            stability="ALTA",
        ),
        model_version="1.0",
        inference_time_ms=12.0,
    )


class TestRescoreResponsePoseSelector:
    """Campos opcionales del pose selector en RescoreResponse."""

    def test_defaults_pose_selector_none(self):
        """Sin pose selector, los campos nuevos quedan en None."""
        resp = _respuesta_minima()
        assert resp.pose_scores is None
        assert resp.selected_pose_rank is None
        assert resp.pose_confidence is None
        assert resp.pose_abstained is None
        assert resp.pose_selector_model is None

    def test_serializa_con_campos_pose_selector(self):
        """Con pose selector, los campos se serializan correctamente."""
        resp = _respuesta_minima()
        resp.pose_scores = [-0.5, 0.3, 0.2]
        resp.selected_pose_rank = 1
        resp.pose_confidence = 0.1
        resp.pose_abstained = False
        resp.pose_selector_model = "pose_selector_v06"
        data = json.loads(resp.model_dump_json())
        assert data["pose_scores"] == [-0.5, 0.3, 0.2]
        assert data["selected_pose_rank"] == 1
        assert data["pose_confidence"] == 0.1
        assert data["pose_abstained"] is False
        assert data["pose_selector_model"] == "pose_selector_v06"

    def test_deserializa_viejo_sin_campos_pose_selector(self):
        """Un JSON de respuesta SIN los campos nuevos deserializa con
        defaults None (compatibilidad hacia atras)."""
        resp = _respuesta_minima()
        data = json.loads(resp.model_dump_json())
        data.pop("pose_scores", None)
        data.pop("selected_pose_rank", None)
        data.pop("pose_confidence", None)
        data.pop("pose_abstained", None)
        data.pop("pose_selector_model", None)
        resp2 = RescoreResponse.model_validate(data)
        assert resp2.pose_scores is None
        assert resp2.selected_pose_rank is None
        assert resp2.pose_abstained is None
        assert resp2.pose_selector_model is None
