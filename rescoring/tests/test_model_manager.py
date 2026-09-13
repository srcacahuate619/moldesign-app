"""
tests/test_model_manager.py

Tests unitarios para el model manager.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model_manager import ModelManager


class TestModelManagerInit:
    """Tests de inicialización del model manager."""

    def test_init_not_loaded(self):
        """Al instanciarse, el modelo no está cargado."""
        mm = ModelManager()
        assert mm.is_loaded is False

    def test_init_no_version(self):
        """Al instanciarse, no hay versión de modelo."""
        mm = ModelManager()
        assert mm.model_version is None

    def test_models_are_none(self):
        """Al instanciarse, todos los modelos son None."""
        mm = ModelManager()
        assert mm.model_a is None
        assert mm.model_null is None
        assert mm.delta_distribution is None
        assert mm.applicability_domain is None


class TestLoadModelsWithoutArtifacts:
    """Tests de carga cuando NO existen artefactos (estado Fase 1)."""

    def test_load_without_artifacts_stays_degraded(self, tmp_path, monkeypatch):
        """
        Sin artefactos, load_models() debe completarse sin error
        y dejar el manager en modo degradado.
        """
        # Apuntar los settings a paths inexistentes
        monkeypatch.setattr(
            "model_manager.settings.model_a_path",
            str(tmp_path / "nonexistent_model_a.joblib"),
        )
        monkeypatch.setattr(
            "model_manager.settings.model_null_path",
            str(tmp_path / "nonexistent_model_null.joblib"),
        )

        mm = ModelManager()
        mm.load_models()

        assert mm.is_loaded is False
        assert mm.model_a is None
        assert mm.model_null is None


class TestGetInfo:
    """Tests del endpoint de metadata."""

    def test_info_without_model(self):
        """Sin modelo cargado, get_info devuelve defaults vacíos."""
        mm = ModelManager()
        info = mm.get_info()
        assert info["model_version"] is None
        assert info["training_date"] is None
        assert info["training_samples"] is None
        assert info["ndcg_at_10"] is None
        assert info["spearman"] is None
        assert info["applicability_domain_threshold"] is None
        assert info["families_trained"] == []

    def test_info_with_mock_report(self):
        """Con training report cargado, get_info devuelve datos correctos."""
        mm = ModelManager()
        mm._is_loaded = True
        mm.training_report = {
            "status": "v0.1.0",
            "timestamp": "2026-04-05",
            "pdbbind_loaded": 1000,
            "cross_validation": {
                "model_a": {
                    "ndcg@10": {"mean": 0.85},
                    "spearman": {"mean": 0.65},
                }
            },
            "families_trained": ["aminergic_GPCR", "kinase"],
        }
        mm._families_trained = ["aminergic_GPCR", "kinase"]
        mm.applicability_domain = {
            "threshold": 8.7,
        }
        info = mm.get_info()
        assert info["model_version"] == "v0.1.0"
        assert info["training_samples"] == 1000
        assert info["applicability_domain_threshold"] == 8.7
        assert "aminergic_GPCR" in info["families_trained"]


class TestPrepareFeatureVector:
    """Tests de preparación del vector de features (contrato A2)."""

    _REPORT = {"feature_order_a": ["c_feat", "a_feat", "b_feat"]}

    def test_raises_without_feature_order(self):
        """Sin artifact ni training_report NO hay orden de features: falla
        firme (un orden alfabético adivinado desalinearía el vector)."""
        mm = ModelManager()
        with pytest.raises(ValueError):
            mm._prepare_feature_vector({"a": 1.0}, model="A")

    def test_uses_training_report_order(self):
        """Con training report, usa el orden especificado."""
        mm = ModelManager()
        mm.training_report = self._REPORT
        features = {"a_feat": 1.0, "b_feat": 2.0, "c_feat": 3.0}
        vector = mm._prepare_feature_vector(features, model="A")
        # Orden del report: c=3, a=1, b=2
        assert list(vector) == [3.0, 1.0, 2.0]

    def test_missing_feature_imputed_with_mean(self):
        """[A2] Feature faltante con media de entrenamiento disponible →
        imputación por media (nunca 0.0 fabricado)."""
        mm = ModelManager()
        mm.training_report = {
            "feature_order_a": ["existing", "missing"],
        }
        mm._feature_means = {"missing": 2.5}
        features = {"existing": 5.0}
        vector = mm._prepare_feature_vector(features, model="A")
        assert list(vector) == [5.0, 2.5]

    def test_missing_feature_without_mean_raises(self):
        """[A2] Feature faltante SIN media imputable → FeatureContractViolation
        (el caller excluye la molécula explícitamente)."""
        mm = ModelManager()
        mm.training_report = {
            "feature_order_a": ["existing", "missing"],
        }
        mm._feature_means = {}
        with pytest.raises(Exception) as exc:
            mm._prepare_feature_vector({"existing": 5.0}, model="A")
        assert "missing" in str(exc.value)

    def test_non_finite_feature_raises_without_mean(self):
        """[A2] Feature NaN/Inf sin media → violación de contrato."""
        mm = ModelManager()
        mm.training_report = self._REPORT
        mm._feature_means = {}
        with pytest.raises(Exception):
            mm._prepare_feature_vector(
                {"a_feat": 1.0, "b_feat": 2.0, "c_feat": float("nan")},
                model="A",
            )

    def test_vector_dtype_float64(self):
        """El vector debe ser float64."""
        import numpy as np

        mm = ModelManager()
        mm.training_report = self._REPORT
        features = {"a_feat": 1.0, "b_feat": 2.0, "c_feat": 0.0}
        vector = mm._prepare_feature_vector(features, model="A")
        assert vector.dtype == np.float64
