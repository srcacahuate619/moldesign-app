"""
tests/test_feature_contract.py

Tests del contrato de features A2/A3 en model_router:

- El contrato es EXACTAMENTE 167 features (model_a universal y familia)
- Un artifact de 176 features (model_a.json legacy huérfano) se rechaza EN
  CARGA (engine_load_failed: FeatureContractViolation), nunca en predicción
- Features faltantes / no finitas en predict() → RouterResult NaN explícito
  con fallback_reason, JAMÁS cero-padding ni 0.5 fabricado
- Sub-vectores (model_null / clasificador) fuera del contrato → NaN explícito

Usa un fake de xgboost para no depender del binario XGBoost en el test.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import model_router
from model_router import (
    EXPECTED_MODEL_A_FEATURES,
    ModelRouter,
    RouterResult,
)

from model_manager import ModelManager


# ── Fake xgboost (sin depender del binario) ─────────────────────────────────

class FakeBooster:
    """Fake de xgb.Booster: lee el tamaño del contrato desde el archivo.

    El contenido del artifact JSON dice 167 o 176 → load_model() fija
    feature_names con esa cardinalidad."""

    def __init__(self):
        self.feature_names: list[str] = []

    def load_model(self, path) -> None:
        text = Path(path).read_text().strip()
        try:
            n = int(text)
        except ValueError:
            n = 0
        self.feature_names = [f"f_{i:04d}" for i in range(n)]

    def predict(self, dmat) -> np.ndarray:  # noqa: ARG002
        return np.array([0.5])


class FakeDMatrix:
    def __init__(self, X, feature_names=None):
        self.X = X
        self.feature_names = feature_names


class FakeXGB:
    Booster = FakeBooster
    DMatrix = FakeDMatrix


CONTRACT_167 = [f"f_{i:04d}" for i in range(167)]
SUBSET_8 = CONTRACT_167[:8]  # proxy de NULL_FEATURES


@pytest.fixture
def router():
    r = ModelRouter()
    r._get_xgb = lambda: FakeXGB()
    return r


def _loaded_cpu_set(r: ModelRouter, model_a_names: int, null_names: int | None = None, clf_names: int | None = None):
    """Inyecta un ModelSet CPU cargado con boosters fake (cardinalidad = int)."""
    import model_router as mr

    def _booster(n: int) -> FakeBooster:
        b = FakeBooster()
        b.feature_names = [f"f_{i:04d}" for i in range(n)]
        return b

    ms = mr.ModelSet(engine="cpu")
    ms.model_a = _booster(model_a_names)
    ms.model_null = _booster(null_names) if null_names else None
    ms.classifier = _booster(clf_names) if clf_names else None
    ms.classifier_meta = (
        {"feature_names": [f"c_{i:04d}" for i in range(clf_names)]} if clf_names else {}
    )
    ms.is_loaded = True
    r._cpu_set = ms
    return ms


# ── Contrato estático ──────────────────────────────────────────────────────

class TestContractConstant:
    def test_expected_is_167(self):
        assert EXPECTED_MODEL_A_FEATURES == 167


# ── Modelo Extended retirado (2026-08-13) ──────────────────────────────────
# "A_extended" ya NO es un nombre de modelo válido en model_manager: el
# runtime puntúa fuera de dominio con el modelo CORE + advertencia honesta.
# El vectorizador debe RECHAZAR nombres desconocidos, nunca caer
# silenciosamente al artifact del modelo NULL.

class TestRetiredExtendedModel:
    def test_model_manager_has_no_extended_state(self):
        mm = ModelManager()
        assert not hasattr(mm, "model_a_extended")
        assert not hasattr(mm, "model_a_extended_artifact")
        assert not hasattr(mm, "applicability_domain_extended")

    def test_prepare_feature_vector_rejects_a_extended(self):
        mm = ModelManager()
        mm.model_a_artifact = {"feature_names": ["f_a"]}
        mm.model_null_artifact = {"feature_names": ["f_n"]}
        with pytest.raises(ValueError, match="A_extended"):
            mm._prepare_feature_vector({"f_a": 1.0}, model="A_extended")

    def test_contract_safe_vector_rejects_a_extended(self):
        # _contract_safe_vector solo captura FeatureContractViolation; un
        # nombre de modelo desconocido propaga ValueError (falla firme).
        mm = ModelManager()
        mm.model_a_artifact = {"feature_names": ["f_a"]}
        mm.model_null_artifact = {"feature_names": ["f_n"]}
        with pytest.raises(ValueError, match="A_extended"):
            mm._contract_safe_vector({"f_a": 1.0}, "A_extended", context="test")

    def test_null_name_still_valid(self):
        # "NULL" sigue siendo el único otro nombre válido (ablación 1D/2D).
        mm = ModelManager()
        mm.model_null_artifact = {"feature_names": ["f_n"]}
        mm._feature_means = {}
        vector = mm._prepare_feature_vector({"f_n": 2.0}, model="NULL")
        assert list(vector) == [2.0]


# ── Rechazo en carga: artifact 176 legacy ──────────────────────────────────

class TestLoadSetContract:
    def test_load_set_rejects_176_artifact(self, router, tmp_path):
        a = tmp_path / "model_a.json"
        n = tmp_path / "model_null.json"
        a.write_text("176")  # artifact legacy huérfano: 176 features
        n.write_text("8")
        router._xgb = FakeXGB
        router._get_xgb = lambda: FakeXGB()
        # Ejecutar el método real: pasa por el guard FeatureContractViolation
        ms = router._load_set(a, n, tmp_path / "clf.json", tmp_path / "clf.meta.json", engine="cpu")
        assert not ms.is_loaded
        assert "FeatureContractViolation" in ms.engine
        assert "176" in ms.engine

    def test_load_set_ok_on_167(self, router, tmp_path):
        a = tmp_path / "model_a.json"
        n = tmp_path / "model_null.json"
        a.write_text("167")
        n.write_text("8")
        router._xgb = FakeXGB
        router._get_xgb = lambda: FakeXGB()
        ms = router._load_set(a, n, tmp_path / "clf.json", tmp_path / "clf.meta.json", engine="cpu")
        assert ms.is_loaded


# ── predict(): NaN explícito, sin cero-padding ─────────────────────────────

class TestPredictContract:
    def test_missing_feature_yields_nan(self, router):
        _loaded_cpu_set(router, 167)
        features = {f: 0.5 for f in CONTRACT_167[:-1]}  # falta la última
        res = router.predict(features, engine="cpu")
        assert isinstance(res, RouterResult)
        assert np.isnan(res.score)
        assert np.isnan(res.prob)
        assert res.fallback is True
        assert res.fallback_reason.startswith("FeatureContractViolation")

    def test_non_finite_feature_yields_nan(self, router):
        _loaded_cpu_set(router, 167)
        features = {f: 0.5 for f in CONTRACT_167}
        features[CONTRACT_167[3]] = float("nan")
        res = router.predict(features, engine="cpu")
        assert np.isnan(res.score)
        assert "FeatureContractViolation" in res.fallback_reason

    def test_complete_167_predicts(self, router):
        _loaded_cpu_set(router, 167)
        features = {f: 0.5 for f in CONTRACT_167}
        res = router.predict(features, engine="cpu")
        assert res.score == 0.5
        assert res.prob == 0.0  # sin clasificador → 0.0 (sin modelo, no fabricado)

    def test_null_subset_missing_yields_nan_delta(self, router):
        # model_null presente pero la feature faltante está en su subconjunto:
        # el contrato global YA dispara NaN en predict() (nunca 0.0).
        _loaded_cpu_set(router, 167, null_names=8)
        features = {f: 0.5 for f in CONTRACT_167}
        del features[SUBSET_8[0]]  # falta en el subconjunto NULL
        res = router.predict(features, engine="cpu")
        assert np.isnan(res.score)
        assert "FeatureContractViolation" in res.fallback_reason

    def test_classifier_missing_feature_yields_nan_prob(self, router):
        # El clasificador pide features propias (c_xxx) que NO están en el
        # dict de features → sub-vector roto → prob NaN, no 0.0 fabricado.
        _loaded_cpu_set(router, 167, clf_names=2)
        features = {f: 0.5 for f in CONTRACT_167}
        res = router.predict(features, engine="cpu")
        assert res.score == 0.5  # model_a OK
        assert np.isnan(res.prob)