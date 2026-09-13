"""
tests/test_applicability_domain.py

Tests unitarios para el verificador de Applicability Domain (Mahalanobis).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from applicability_domain import AD_DESCRIPTORS, ApplicabilityDomainChecker

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


def _make_sample_descriptors(**overrides) -> dict[str, float]:
    """Crear descriptores típicos de una molécula drug-like."""
    base = {
        "mw": 300.0,
        "logp": 2.5,
        "tpsa": 60.0,
        "hbd": 2.0,
        "hba": 4.0,
        "rotatable_bonds": 5.0,
        "qed": 0.7,
    }
    base.update(overrides)
    return base


def _make_ad_artifact(n_samples: int = 100) -> dict:
    """Crear artefacto de AD sintético para tests."""
    rng = np.random.RandomState(42)
    # Training data: distribución normal centrada en valores drug-like
    means = [300, 2.5, 60, 2, 4, 5, 0.7]
    stds = [100, 1.5, 30, 1, 2, 3, 0.15]
    training_data = np.column_stack([
        rng.normal(m, s, n_samples) for m, s in zip(means, stds)
    ])

    return ApplicabilityDomainChecker.build_from_training_data(
        training_data, AD_DESCRIPTORS, percentile=99
    )


# ─────────────────────────────────────────────
# Tests — Modo permisivo (sin artefacto)
# ─────────────────────────────────────────────


class TestPermissiveMode:
    """Tests cuando no hay artefacto cargado (Fase 1)."""

    def test_no_artifact_returns_in_domain(self):
        """Sin artefacto, toda molécula pasa."""
        checker = ApplicabilityDomainChecker(ad_data=None)
        result = checker.check(_make_sample_descriptors())
        assert result.in_domain is True

    def test_no_artifact_distance_is_zero(self):
        """Sin artefacto, la distancia reportada es 0."""
        checker = ApplicabilityDomainChecker(ad_data=None)
        result = checker.check(_make_sample_descriptors())
        assert result.mahalanobis_distance == 0.0

    def test_no_artifact_threshold_is_zero(self):
        """Sin artefacto, el umbral reportado es 0."""
        checker = ApplicabilityDomainChecker(ad_data=None)
        result = checker.check(_make_sample_descriptors())
        assert result.threshold == 0.0

    def test_no_artifact_no_out_of_range(self):
        """Sin artefacto, no hay descriptores fuera de rango."""
        checker = ApplicabilityDomainChecker(ad_data=None)
        result = checker.check(_make_sample_descriptors())
        assert result.out_of_range_descriptors == []


# ─────────────────────────────────────────────
# Tests — Con artefacto cargado
# ─────────────────────────────────────────────


class TestWithArtifact:
    """Tests con artefacto de AD cargado."""

    @pytest.fixture
    def ad_artifact(self):
        return _make_ad_artifact()

    @pytest.fixture
    def checker(self, ad_artifact):
        # Convertir los arrays del artefacto de listas a numpy (como lo haría model_manager)
        ad_data = {
            "mean": np.array(ad_artifact["mean"]),
            "cov_inv": np.array(ad_artifact["cov_inv"]),
            "threshold": ad_artifact["threshold"],
            "feature_names": ad_artifact["feature_names"],
            "feature_ranges": ad_artifact["feature_ranges"],
        }
        return ApplicabilityDomainChecker(ad_data=ad_data)

    def test_typical_molecule_in_domain(self, checker):
        """
        Una molécula con descriptores típicos debe estar dentro del dominio.
        """
        result = checker.check(_make_sample_descriptors())
        assert result.in_domain is True
        assert result.mahalanobis_distance < result.threshold

    def test_extreme_molecule_out_of_domain(self, checker):
        """
        Una molécula con peso molecular extremo (10000) debe estar fuera.
        """
        result = checker.check(_make_sample_descriptors(mw=10000.0, logp=20.0))
        assert result.in_domain is False
        assert result.mahalanobis_distance > result.threshold

    def test_out_of_range_descriptors_reported(self, checker):
        """
        Cuando la molécula está fuera del dominio, los descriptores
        fuera de rango deben indicarse.
        """
        result = checker.check(_make_sample_descriptors(mw=10000.0))
        # MW debería estar fuera de rango
        has_mw_warning = any("mw" in d for d in result.out_of_range_descriptors)
        assert has_mw_warning

    def test_distance_is_positive(self, checker):
        """La distancia de Mahalanobis siempre es no-negativa."""
        result = checker.check(_make_sample_descriptors())
        assert result.mahalanobis_distance >= 0.0

    def test_threshold_from_artifact(self, ad_artifact, checker):
        """El umbral del checker debe coincidir con el del artefacto."""
        result = checker.check(_make_sample_descriptors())
        assert result.threshold == ad_artifact["threshold"]


# ─────────────────────────────────────────────
# Tests — build_from_training_data (offline)
# ─────────────────────────────────────────────


class TestBuildFromTrainingData:
    """Tests del constructor offline de artefactos de AD."""

    def test_artifact_has_required_keys(self):
        """El artefacto generado debe tener todas las keys requeridas."""
        artifact = _make_ad_artifact()
        required = {"mean", "cov_inv", "threshold", "feature_names", "feature_ranges"}
        assert required.issubset(set(artifact.keys()))

    def test_mean_dimensions(self):
        """mean debe tener la dimensión correcta."""
        artifact = _make_ad_artifact()
        assert len(artifact["mean"]) == len(AD_DESCRIPTORS)

    def test_cov_inv_is_square(self):
        """cov_inv debe ser una matriz cuadrada."""
        artifact = _make_ad_artifact()
        cov_inv = np.array(artifact["cov_inv"])
        n = len(AD_DESCRIPTORS)
        assert cov_inv.shape == (n, n)

    def test_threshold_is_positive(self):
        """El umbral debe ser positivo."""
        artifact = _make_ad_artifact()
        assert artifact["threshold"] > 0

    def test_feature_ranges_complete(self):
        """feature_ranges debe tener un rango por cada descriptor."""
        artifact = _make_ad_artifact()
        for desc in AD_DESCRIPTORS:
            assert desc in artifact["feature_ranges"]
            rng = artifact["feature_ranges"][desc]
            assert "min" in rng
            assert "max" in rng
            assert rng["min"] <= rng["max"]

    def test_singular_covariance_uses_pinv(self):
        """
        Covarianza singular (features idénticas) debe usar pseudo-inversa
        sin hacer crash.
        """
        # Crear data con columnas colineales
        rng = np.random.RandomState(42)
        n = 50
        col1 = rng.normal(300, 50, n)
        # col2 = col1 (colineal)
        data = np.column_stack([col1, col1, rng.normal(0, 1, n)])
        artifact = ApplicabilityDomainChecker.build_from_training_data(
            data, ["feat1", "feat2", "feat3"]
        )
        # No debe crashear y debe producir un artefacto válido
        assert "threshold" in artifact
        assert artifact["threshold"] > 0

    def test_percentile_customizable(self):
        """Cambiar el percentil debe cambiar el umbral."""
        rng = np.random.RandomState(42)
        data = rng.normal(0, 1, (200, 3))
        names = ["a", "b", "c"]
        art_95 = ApplicabilityDomainChecker.build_from_training_data(data, names, percentile=95)
        art_99 = ApplicabilityDomainChecker.build_from_training_data(data, names, percentile=99)
        assert art_95["threshold"] < art_99["threshold"]
