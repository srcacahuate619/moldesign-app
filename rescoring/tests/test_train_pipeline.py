"""
tests/test_train_pipeline.py

Tests para el pipeline de entrenamiento ML.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from train_pipeline import (
    ALL_FEATURES,
    FEATURE_GROUP_A,
    FEATURE_GROUP_A_EXT,
    FEATURE_GROUP_B,
    FEATURE_GROUP_C,
    FEATURE_GROUP_C_EXT,
    FEATURE_GROUP_D,
    FEATURE_GROUP_E,
    NULL_FEATURES,
    AblationResult,
    MLTrainer,
    _compute_ndcg,
    _ndcg_single,
)


class TestFeatureGroups:
    """Tests para definición de grupos de features."""

    def test_groups_are_disjoint(self):
        """Los 3 grupos no se solapan."""
        a = set(FEATURE_GROUP_A)
        b = set(FEATURE_GROUP_B)
        c = set(FEATURE_GROUP_C)
        assert a.isdisjoint(b)
        assert a.isdisjoint(c)
        assert b.isdisjoint(c)

    def test_all_features_is_union(self):
        """ALL_FEATURES (v4.1) = A_EXT ∪ B ∪ C_EXT ∪ D ∪ E = 167.
        [fix #3 Spearman] ProLIF interaction counts removidos — ρ=-0.035 en 5-HT1A."""
        expected = set(FEATURE_GROUP_A_EXT + FEATURE_GROUP_B + FEATURE_GROUP_C_EXT + FEATURE_GROUP_D + FEATURE_GROUP_E)
        assert set(ALL_FEATURES) == expected
        assert len(ALL_FEATURES) == 167

    def test_null_features_is_group_a_ext(self):
        """NULL_FEATURES (v4) = solo grupo A_EXT (1D/2D + log_mw)."""
        assert NULL_FEATURES == FEATURE_GROUP_A_EXT

    def test_group_a_has_drug_properties(self):
        """Grupo A_EXT tiene propiedades drug-like + log_mw (v4)."""
        assert "mw" in FEATURE_GROUP_A_EXT
        assert "logp" in FEATURE_GROUP_A_EXT
        assert "qed" in FEATURE_GROUP_A_EXT
        assert "log_mw" in FEATURE_GROUP_A_EXT

    def test_group_b_has_vina(self):
        """Grupo B tiene features de Vina."""
        assert "vina_best_score" in FEATURE_GROUP_B
        assert "pose_score_variance" in FEATURE_GROUP_B

    def test_group_c_has_3d(self):
        """Grupo C tiene features 3D."""
        assert "hbond_donor_count" in FEATURE_GROUP_C
        assert "hydrophobic_contacts" in FEATURE_GROUP_C
        assert "pi_stacking" in FEATURE_GROUP_C


class TestNDCG:
    """Tests para cálculo de NDCG."""

    def test_perfect_ranking(self):
        """Ranking perfecto → NDCG = 1.0."""
        y_true = np.array([3.0, 2.0, 1.0, 0.0])
        y_pred = np.array([3.0, 2.0, 1.0, 0.0])
        ndcg = _ndcg_single(y_true, y_pred, k=4)
        assert abs(ndcg - 1.0) < 1e-6

    def test_worst_ranking(self):
        """Ranking inverso → NDCG < 1.0."""
        y_true = np.array([3.0, 2.0, 1.0, 0.0])
        y_pred = np.array([0.0, 1.0, 2.0, 3.0])
        ndcg = _ndcg_single(y_true, y_pred, k=4)
        assert ndcg < 1.0

    def test_single_item(self):
        """Un solo item → NDCG = 1.0."""
        ndcg = _ndcg_single(np.array([5.0]), np.array([3.0]), k=1)
        assert ndcg == 1.0

    def test_ndcg_at_k(self):
        """NDCG@k solo considera top k items."""
        y_true = np.array([3.0, 0.0, 0.0, 0.0, 0.0])
        y_pred = np.array([3.0, 0.0, 0.0, 0.0, 0.0])  # Best at top
        ndcg = _ndcg_single(y_true, y_pred, k=1)
        assert abs(ndcg - 1.0) < 1e-6

    def test_ndcg_range(self):
        """NDCG está en [0, 1]."""
        rng = np.random.RandomState(42)
        for _ in range(20):
            y_true = rng.rand(10)
            y_pred = rng.rand(10)
            ndcg = _ndcg_single(y_true, y_pred, k=5)
            assert 0.0 <= ndcg <= 1.0

    def test_compute_ndcg_no_groups(self):
        """NDCG global sin grupos."""
        y_true = np.array([3.0, 1.0, 2.0])
        y_pred = np.array([3.0, 1.0, 2.0])
        ndcg = _compute_ndcg(y_true, y_pred, groups=None, k=3)
        assert ndcg > 0.5


class TestMLTrainer:
    """Tests para MLTrainer."""

    def test_trainer_init_defaults(self):
        """Trainer tiene parámetros XGBoost por defecto (v4: reg:squarederror)."""
        trainer = MLTrainer()
        assert trainer._xgb_params["objective"] == "reg:squarederror"
        assert trainer._xgb_params["eval_metric"] == "rmse"

    def test_prepare_features(self):
        """Preparar features retorna numpy array correcto."""
        trainer = MLTrainer()
        cpx1 = MagicMock(pdb_id="a")
        cpx1.features = {"mw": 300.0, "logp": 2.5}
        cpx2 = MagicMock(pdb_id="b")
        cpx2.features = {"mw": 400.0, "logp": 3.0}

        X = trainer.prepare_features([cpx1, cpx2], ["a", "b"], ["mw", "logp"])
        assert X.shape == (2, 2)
        assert X[0, 0] == 300.0
        assert X[1, 1] == 3.0

    def test_prepare_features_missing_imputed_with_mean(self):
        """[A2] Features faltantes se imputan con la media de la columna
        (valores presentes del mismo conjunto); nunca 0.0 fabricado."""
        trainer = MLTrainer()
        cpx1 = MagicMock(pdb_id="a")
        cpx1.features = {"mw": 300.0, "logp": 2.5}
        cpx2 = MagicMock(pdb_id="b")
        cpx2.features = {"mw": 400.0}  # logp missing → media de la columna

        X = trainer.prepare_features([cpx1, cpx2], ["a", "b"], ["mw", "logp"])
        assert X.shape == (2, 2)
        assert X[0, 0] == 300.0
        assert X[1, 0] == 400.0
        assert X[0, 1] == 2.5
        assert X[1, 1] == 2.5  # única media disponible (columna con 1 valor)

    def test_prepare_features_column_fully_missing_raises(self):
        """[A2] Columna completa ausente → ValueError (contrato roto;
        jamás zero-pad silencioso)."""
        trainer = MLTrainer()
        cpx = MagicMock(pdb_id="a")
        cpx.features = {"mw": 300.0}

        with pytest.raises(ValueError):
            trainer.prepare_features([cpx], ["a"], ["mw", "logp"])

    def test_prepare_labels(self):
        """Labels son pKi."""
        trainer = MLTrainer()
        cpx1 = MagicMock(pdb_id="a", pki=7.0)
        cpx2 = MagicMock(pdb_id="b", pki=8.0)

        y = trainer.prepare_labels([cpx1, cpx2], ["a", "b"])
        assert y[0] == 7.0
        assert y[1] == 8.0

    def test_compute_metrics(self):
        """Métricas calculan correctamente."""
        y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y_pred = np.array([1.1, 2.2, 2.8, 4.1, 5.0])

        metrics = MLTrainer._compute_metrics(y_true, y_pred)
        assert "spearman" in metrics
        assert "ndcg@10" in metrics
        assert "r2_reference_only" in metrics
        assert metrics["spearman"] > 0.5  # Correlación positiva

    def test_compute_metrics_prefect(self):
        """Predicción perfecta → Spearman = 1.0."""
        y = np.array([1.0, 2.0, 3.0, 4.0])
        metrics = MLTrainer._compute_metrics(y, y)
        assert abs(metrics["spearman"] - 1.0) < 1e-4

    def test_delta_distribution_structure(self):
        """build_delta_distribution retorna estructura correcta."""
        trainer = MLTrainer()
        deltas = {f"c{i}": float(np.random.randn()) for i in range(100)}
        dist = trainer.build_delta_distribution(deltas)

        assert "mean" in dist
        assert "std" in dist
        assert "percentiles" in dist
        assert "semaphore_thresholds" in dist
        assert "green_above" in dist["semaphore_thresholds"]
        assert "red_below" in dist["semaphore_thresholds"]

    def test_delta_semaphore_thresholds_ordered(self):
        """green_above > red_below."""
        trainer = MLTrainer()
        deltas = {f"c{i}": float(np.random.randn()) for i in range(200)}
        dist = trainer.build_delta_distribution(deltas)

        green = dist["semaphore_thresholds"]["green_above"]
        red = dist["semaphore_thresholds"]["red_below"]
        assert green > red

    def test_acceptance_criteria_structure(self):
        """evaluate_acceptance_criteria retorna dict con todas las claves."""
        trainer = MLTrainer()

        ablation = [
            AblationResult("A_ext_only", FEATURE_GROUP_A_EXT, 8, {"spearman": 0.3}),
            AblationResult("ALL_v4", ALL_FEATURES, 176, {"spearman": 0.5}),
        ]
        shap = {
            "hbond_donor_count": 0.5,
            "hydrophobic_contacts": 0.4,
            "mw": 0.3,
            "logp": 0.2,
            "vina_best_score": 0.1,
        }
        delta = {"mean": 0.3, "std": 0.5}
        model_metrics = {"spearman": 0.4, "ndcg@10": 0.7}

        criteria = trainer.evaluate_acceptance_criteria(
            ablation, shap, delta, model_metrics,
        )

        assert "ablation_3d_contributes" in criteria
        assert "scaffold_split_spearman_positive" in criteria
        assert "shap_3d_in_top5" in criteria
        assert "delta_mean_positive" in criteria
        assert "all_passed" in criteria

    def test_acceptance_criteria_positive(self):
        """Criterios pasan con datos buenos."""
        trainer = MLTrainer()

        ablation = [
            AblationResult("A_ext_only", FEATURE_GROUP_A_EXT, 8, {"spearman": 0.3}),
            AblationResult("ALL_v4", ALL_FEATURES, 176, {"spearman": 0.5}),
        ]
        shap = {
            "contacts_per_ha_4A": 0.5,
            "contacts_per_ha_6A": 0.4,
            "vina_best_score": 0.35,
            "mw": 0.3,
            "logp": 0.2,
        }
        delta = {"mean": 0.3}
        model_metrics = {"spearman": 0.4, "ndcg@10": 0.7}

        criteria = trainer.evaluate_acceptance_criteria(
            ablation, shap, delta, model_metrics,
        )

        assert criteria["ablation_3d_contributes"] is True
        assert criteria["scaffold_split_spearman_positive"] is True
        assert criteria["shap_3d_in_top5"] is True
        assert criteria["delta_mean_positive"] is True
        assert criteria["all_passed"] is True

    def test_acceptance_fails_ligand_bias(self):
        """Criterios fallan si A_only ≈ A+B+C (sesgo de ligando)."""
        trainer = MLTrainer()

        ablation = [
            AblationResult("A_ext_only", FEATURE_GROUP_A_EXT, 8, {"spearman": 0.45}),
            AblationResult("ALL_v4", ALL_FEATURES, 176, {"spearman": 0.46}),
        ]
        shap = {f"f{i}": 0.1 for i in range(5)}
        delta = {"mean": 0.3}
        model_metrics = {"spearman": 0.4, "ndcg@10": 0.7}

        criteria = trainer.evaluate_acceptance_criteria(
            ablation, shap, delta, model_metrics,
        )

        assert criteria["ablation_3d_contributes"] is False
        assert criteria["all_passed"] is False


class TestApplicabilityDomain:
    """Tests para construcción del Applicability Domain."""

    def test_ad_structure(self):
        """AD tiene la estructura correcta."""
        trainer = MLTrainer()

        complexes = []
        for i in range(50):
            cpx = MagicMock(pdb_id=f"c{i}")
            cpx.features = {f: float(np.random.randn()) for f in ["mw", "logp"]}
            complexes.append(cpx)

        ad = trainer.build_applicability_domain(
            complexes, [f"c{i}" for i in range(50)], ["mw", "logp"],
        )

        assert "mean" in ad
        assert "cov_inv" in ad
        assert "threshold_p99" in ad
        assert "n_training_samples" in ad
        assert ad["n_training_samples"] == 50
        assert ad["n_features"] == 2

    def test_ad_threshold_positive(self):
        """Umbral de Mahalanobis es positivo."""
        trainer = MLTrainer()

        complexes = []
        for i in range(100):
            cpx = MagicMock(pdb_id=f"c{i}")
            cpx.features = {"mw": float(300 + np.random.randn() * 50)}
            complexes.append(cpx)

        ad = trainer.build_applicability_domain(
            complexes, [f"c{i}" for i in range(100)], ["mw"],
        )

        assert ad["threshold_p99"] > 0
