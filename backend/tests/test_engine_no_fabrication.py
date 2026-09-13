"""
tests/test_engine_no_fabrication.py

Tests A3 para scoring/engine.py: NINGÚN fallback fabricado.

- _finite_or_none: None/NaN/Inf → None; numérico finito → float
- _resolve_stacking_weights: configuración corrupta (suma 0) → TODOS los
  pesos en 0.0 (el engine cae a regresión pura con stacking_factor=1.0);
  jamás el hardcode silencioso (0.3, 0.5, 0.0, 0.2)
- ScoreBreakdown: flags stacking_degraded / degraded_missing por defecto
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scoring"))

from scoring import engine as engine_mod  # noqa: E402


class TestFiniteOrNone:
    """None/NaN/Inf nunca entran como componente de stacking."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, None),
            (float("nan"), None),
            (float("inf"), None),
            (float("-inf"), None),
            ("no-float", None),
            (True, None),
            (0.42, 0.42),
            (0.0, 0.0),
            (1.0, 1.0),
        ],
    )
    def test_values(self, value, expected):
        got = engine_mod._finite_or_none(value, "x")
        if expected is None:
            assert got is None
        else:
            assert got == expected


class TestResolveStackingWeights:
    """Sin pesos fabricados: corrupción → regresión pura (todos 0.0)."""

    def test_zero_total_returns_zeros_not_hardcode(self):
        w = engine_mod._resolve_stacking_weights(
            {"vina": 0.0, "xgb": 0.0, "gnn": 0.0, "clgnn": 0.0}
        )
        assert w["vina"] == 0.0
        assert w["xgb"] == 0.0
        assert w["gnn"] == 0.0
        assert w["clgnn"] == 0.0
        # el old hardcode (0.3, 0.5, 0.0, 0.2) NO debe aparecer
        assert not (w["vina"] == 0.3 and w["xgb"] == 0.5 and w["clgnn"] == 0.2)

    def test_negative_total_returns_zeros(self):
        w = engine_mod._resolve_stacking_weights(
            {"vina": 1.0, "xgb": -2.0, "gnn": 0.0, "clgnn": 0.0}
        )
        assert w["vina"] == 0.0
        assert w["xgb"] == 0.0

    def test_normalized_positive_weights(self):
        w = engine_mod._resolve_stacking_weights(
            {"vina": 0.2, "xgb": 0.3, "gnn": 0.0, "clgnn": 0.0}
        )
        assert w["vina"] == pytest.approx(0.4)
        assert w["xgb"] == pytest.approx(0.6)
        assert w["gnn"] == 0.0
        assert w["clgnn"] == 0.0

    def test_quantum_sign_passthrough(self):
        w = engine_mod._resolve_stacking_weights(
            {"vina": 0.0, "xgb": 0.0, "gnn": 0.0, "clgnn": 0.0, "quantum_sign": -1.0}
        )
        assert w["quantum_sign"] == -1.0


class TestScoreBreakdownDefaults:
    """El schema expone el estado de degradación del stacking."""

    def _bd(self, **overrides):
        from core.models import ScoreBreakdown

        defaults = dict(
            affinity_score=60.0,
            adme_score=60.0,
            druglikeness_score=60.0,
            total_score=60.0,
            weight_affinity=0.45,
            weight_adme=0.30,
            weight_druglikeness=0.25,
            strongest_dimension="afinidad",
            weakest_dimension="ADME",
            improvement_hint="Reduce el logP por debajo de 3.5",
        )
        defaults.update(overrides)
        return ScoreBreakdown(**defaults)

    def test_defaults_no_degradation(self):
        bd = self._bd()
        assert bd.stacking_degraded is False
        assert bd.degraded_missing == []

    def test_degradation_flags_serializable(self):
        bd = self._bd(
            stacking_degraded=True,
            degraded_missing=["clgnn", "gnn"],
        )
        data = bd.model_dump()
        assert data["stacking_degraded"] is True
        assert data["degraded_missing"] == ["clgnn", "gnn"]

def test_pesos_efectivos_reflejan_renormalizacion_real():
    """Una corrida degradada debe poder reconstruirse despues de persistirla."""
    from core.models import DockingPose, DockingResult, PhysicochemicalProperties
    from scoring.engine import calculate_score_breakdown

    docking = DockingResult(
        best_affinity=-8.0,
        poses=[DockingPose(rank=1, affinity=-8.0, rmsd_lb=0.0, rmsd_ub=0.0)],
    )
    props = PhysicochemicalProperties(
        molecular_weight=300.0, log_p=2.0, tpsa=60.0, hbd=1, hba=4,
        rotatable_bonds=3, heavy_atom_count=21, ring_count=2,
        qed=0.7, sa_score=2.5, lipinski_pass=True, veber_pass=True,
    )

    breakdown = calculate_score_breakdown(
        docking, props, xgb_prob=None, clgnn_prob=0.4,
        target_family="default",
    )

    assert breakdown.stacking_degraded is True
    assert breakdown.degraded_missing == ["xgb"]
    # El checkpoint CL-GNN incluido aún no tiene validación externa para su
    # SHA-256 exacto: produce una señal auditable, pero no decide el ranking.
    assert breakdown.stacking_effective_weights == {
        "vina": pytest.approx(1.0),
        "xgb": pytest.approx(0.0),
        "gnn": pytest.approx(0.0),
        "clgnn": pytest.approx(0.0),
    }
