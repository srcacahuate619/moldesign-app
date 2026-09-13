"""
Tests del payload F-21: transparencia del modelo usado.

F-21 (auditoría): la API/UI debe mostrar familia, aplicabilidad, fallback
usado, incertidumbre y warning de dominio. Aquí probamos el contrato de
serialización de los 4 campos nuevos de EvaluationResultRead:

- engine_used (motor hardware del router; None en el pipeline de evaluación)
- fallback_reason (motivo del fallback a modelo universal)
- in_applicability_domain (dominio de aplicabilidad, dist. Mahalanobis)
- model_used ("family" | "universal" | None)

Reglas del contrato:
1. Los 4 campos son opcionales: un payload viejo (sin ellos) se valida y
   serializa con None — nunca debe explotar la API.
2. Cuando llegan poblados, model_dump() los conserva tal cual (round-trip).
3. La validación from_attributes (ORM de SQLite) tolera filas viejas cuyas
   columnas no existían todavía (Pydantic cae al default None).

Sin DB, sin RDKit, sin IO — test ligero y rápido.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from core.models import EvaluationResultRead


def _base_payload() -> dict:
    """Campos REQUERIDOS de EvaluationResultRead con valores None válidos."""
    return {
        "id": uuid.uuid4(),
        "molecule_id": uuid.uuid4(),
        # Docking
        "affinity_kcal": None,
        "affinity_score": None,
        "docking_poses": None,
        "poses_file_path": None,
        "parsing_source": None,
        "vina_version": None,
        "vina_random_seed": None,
        "scientific_warnings": None,
        "celery_task_id": None,
        # Propiedades
        "molecular_weight": None,
        "log_p": None,
        "tpsa": None,
        "hbd": None,
        "hba": None,
        "rotatable_bonds": None,
        "heavy_atom_count": None,
        "ring_count": None,
        "lipinski_pass": None,
        "veber_pass": None,
        "qed": None,
        "sa_score": None,
        "sa_reasons": None,
        # Scores
        "adme_score": None,
        "druglikeness_score": None,
        "total_score": None,
        "target_name": None,
        # Reporte / Blockchain / metadatos
        "ai_report": None,
        "blockchain_tx_id": None,
        "error_message": None,
        "evaluated_at": datetime.now(timezone.utc),
    }


class TestF21PayloadFields:
    """Los 4 campos F-21 serializan con default None (payloads viejos)."""

    def test_fields_serialize_default_none(self):
        payload = EvaluationResultRead.model_validate(_base_payload())
        dumped = payload.model_dump()

        for field in ("engine_used", "fallback_reason", "in_applicability_domain", "model_used"):
            assert field in dumped, f"{field} debe existir en model_dump()"
            assert dumped[field] is None, f"{field} debe serializar None por defecto"

    def test_fields_roundtrip_when_populated(self):
        payload = EvaluationResultRead.model_validate({
            **_base_payload(),
            "engine_used": "cpu",
            "fallback_reason": "Familia 'kinase' sin modelo validado — modelo universal usado.",
            "in_applicability_domain": False,
            "model_used": "universal",
        })
        dumped = payload.model_dump()

        assert dumped["engine_used"] == "cpu"
        assert "kinase" in dumped["fallback_reason"]
        assert dumped["in_applicability_domain"] is False
        assert dumped["model_used"] == "universal"

    def test_from_attributes_old_orm_row_does_not_crash(self):
        """Filas viejas de SQLite (sin las columnas F-21) validan con None.

        model_config from_attributes + default None → atributo faltante en el
        ORM cae al default, sin AttributeError. Este es el comportamiento que
        garantiza que evaluaciones cacheadas antes de F-21 sigan sirviéndose.
        """
        orm_row = SimpleNamespace(**_base_payload())
        payload = EvaluationResultRead.model_validate(orm_row)

        assert payload.engine_used is None
        assert payload.fallback_reason is None
        assert payload.in_applicability_domain is None
        assert payload.model_used is None

    def test_boolean_domain_is_not_coerced_to_string(self):
        """in_applicability_domain conserva el tipo bool (no str de SQLite).

        El frontend compara estrictamente (=== false / === true); un "False"
        string rompería las alertas derivadas de ProAlertsTab.
        """
        payload = EvaluationResultRead.model_validate({
            **_base_payload(),
            "in_applicability_domain": False,
        })
        assert payload.in_applicability_domain is False
        assert isinstance(payload.in_applicability_domain, bool)
