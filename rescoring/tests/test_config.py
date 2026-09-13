"""
tests/test_config.py

Tests para la configuración del microservicio de rescoring.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import RescoringSettings


class TestRescoringSettings:
    """Tests de la configuración por defecto."""

    def test_default_model_paths(self):
        """Las rutas por defecto de modelos son coherentes."""
        s = RescoringSettings()
        assert "model_a" in s.model_a_path
        assert "model_null" in s.model_null_path

    def test_default_thresholds(self):
        """Umbrales de Delta tienen valores por defecto razonables."""
        s = RescoringSettings()
        assert s.delta_green_threshold > 0
        assert s.delta_red_threshold < 0
        assert s.delta_green_threshold > s.delta_red_threshold

    def test_pose_filter_defaults(self):
        """Configuración del pose filter tiene valores razonables."""
        s = RescoringSettings()
        assert s.pose_filter_max_distance > 0
        assert 0 < s.pose_filter_min_atoms_in_box <= 1.0
        assert s.pose_filter_max_clashes > 0

    def test_pose_variance_thresholds(self):
        """Umbrales de varianza: low < high."""
        s = RescoringSettings()
        assert s.pose_variance_low < s.pose_variance_high

    def test_env_prefix(self):
        """El prefijo de env es RESCORING_."""
        assert RescoringSettings.model_config["env_prefix"] == "RESCORING_"
