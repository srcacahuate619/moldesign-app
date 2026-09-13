"""
rescoring/model_router.py

Dynamic Model Router — Hardware-Aware Inference.

ADICIÓN PURA al proyecto. No modifica model_manager.py ni ningún archivo original.

Encapsula la lógica de enrutamiento:
  engine="cpu" → Carga modelos de artifacts/       (entrenados con Vina-CPU FP64)
  engine="gpu" → Carga modelos de artifacts/gpu/   (entrenados con Vina-GPU FP32)

Si los modelos GPU no existen todavía (pre-entrenamiento),
el router hace fallback transparente a los modelos CPU sin lanzar ningún error.

Uso (desde cualquier módulo del proyecto):
    from model_router import ModelRouter

    router = ModelRouter()
    result = router.predict(features_dict, engine="gpu")
    # result.score, result.engine_used, result.fallback
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

_log = logging.getLogger("rescoring.model_router")

# ── Contrato de features (A2) ───────────────────────────────────────────────
# El Model A (universal y familia) se entrena EXACTAMENTE con 167 features
# (8 + 4 + 3 + 96 + 56, ver train_pipeline.ALL_FEATURES). Un artifact con un
# conteo distinto (p. ej. el legacy artifacts/model_a.json de 176 features)
# NO debe cargarse nunca: configurarlo apuntaría a features fuera de contrato
# que el runtime no puede proveer.
EXPECTED_MODEL_A_FEATURES = 167

# ── Rutas canónicas ───────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CPU_ARTIFACTS_DIR = PROJECT_ROOT / "rescoring" / "artifacts"
GPU_ARTIFACTS_DIR = CPU_ARTIFACTS_DIR / "gpu"

CPU_MODEL_A_JSON = CPU_ARTIFACTS_DIR / "model_a_universal.json"
CPU_MODEL_NULL_JSON = CPU_ARTIFACTS_DIR / "model_null.json"
CPU_CLASSIFIER_JSON = CPU_ARTIFACTS_DIR / "classifier_binder.json"
CPU_CLASSIFIER_META = CPU_ARTIFACTS_DIR / "classifier_binder.metadata.json"
CPU_GNN_PT = CPU_ARTIFACTS_DIR / "gnn_v3_best.pt"

GPU_MODEL_A_JSON = GPU_ARTIFACTS_DIR / "model_a.json"
GPU_MODEL_NULL_JSON = GPU_ARTIFACTS_DIR / "model_null.json"
GPU_CLASSIFIER_JSON = GPU_ARTIFACTS_DIR / "classifier_binder.json"
GPU_CLASSIFIER_META = GPU_ARTIFACTS_DIR / "classifier_binder.metadata.json"
GPU_GNN_PT = GPU_ARTIFACTS_DIR / "gnn_v3_best.pt"


@dataclass
class RouterResult:
    """Resultado del enrutamiento adaptativo."""
    score: float                   # Score XGBoost predicho
    prob: float                    # Probabilidad del clasificador binario
    engine_used: str               # "gpu" o "cpu"
    fallback: bool = False         # True si se cayó a CPU desde GPU
    fallback_reason: str = ""      # Motivo del fallback
    in_applicability_domain: bool = True
    delta: float = 0.0             # model_a - model_null


@dataclass
class ModelSet:
    """Conjunto de modelos para un motor específico."""
    engine: str                    # "cpu" o "gpu"
    model_a: Any = None
    model_null: Any = None
    classifier: Any = None
    classifier_meta: dict = field(default_factory=dict)
    gnn: Any = None
    is_loaded: bool = False


class ModelRouter:
    """
    Router adaptativo Hardware-Aware.

    Mantiene dos ModelSets en memoria (lazy loading):
      - _cpu_set: modelos entrenados con poses Vina-CPU (FP64)
      - _gpu_set: modelos entrenados con poses Vina-GPU (FP32)

    predict(features, engine="gpu") → RouterResult
      Si engine="gpu" y los modelos GPU no existen → fallback a CPU (transparente).
      Si engine="cpu" → siempre usa CPU (el original, siempre disponible).
    """

    def __init__(self) -> None:
        self._cpu_set = ModelSet(engine="cpu")
        self._gpu_set = ModelSet(engine="gpu")
        self._xgb = None  # lazy import

    # ── Lazy import de XGBoost ──────────────────────────────────────────
    def _get_xgb(self):
        if self._xgb is None:
            import xgboost as xgb
            self._xgb = xgb
        return self._xgb

    # ── Carga de modelos ─────────────────────────────────────────────────
    def _load_set(self, model_a_json: Path, model_null_json: Path,
                  classifier_json: Path, classifier_meta: Path,
                  engine: str) -> ModelSet:
        """Carga un ModelSet desde las rutas dadas. Silencioso si no existen."""
        xgb = self._get_xgb()
        ms = ModelSet(engine=engine)

        if not model_a_json.exists() or not model_null_json.exists():
            return ms  # is_loaded = False

        try:
            ms.model_a = xgb.Booster()
            ms.model_a.load_model(str(model_a_json))

            # [A2] Validación del contrato de features: un Model A fuera del
            # contrato (p. ej. artifact legacy de 176 features) se rechaza en
            # carga, NUNCA en predicción con features fabricadas.
            n_model_a = len(ms.model_a.feature_names or [])
            if n_model_a != EXPECTED_MODEL_A_FEATURES:
                ms.is_loaded = False
                ms.engine = (
                    f"{engine}_load_failed: "
                    f"FeatureContractViolation model a={n_model_a} "
                    f"!= {EXPECTED_MODEL_A_FEATURES} ({model_a_json.name})"
                )
                return ms

            ms.model_null = xgb.Booster()
            ms.model_null.load_model(str(model_null_json))

            if classifier_json.exists():
                ms.classifier = xgb.Booster()
                ms.classifier.load_model(str(classifier_json))

            if classifier_meta.exists():
                with open(classifier_meta) as f:
                    ms.classifier_meta = json.load(f)

            ms.is_loaded = True
        except Exception as e:
            ms.is_loaded = False
            ms.engine = f"{engine}_load_failed: {e}"

        return ms

    def _ensure_cpu_loaded(self) -> None:
        if not self._cpu_set.is_loaded:
            self._cpu_set = self._load_set(
                CPU_MODEL_A_JSON, CPU_MODEL_NULL_JSON,
                CPU_CLASSIFIER_JSON, CPU_CLASSIFIER_META,
                engine="cpu",
            )

    def _ensure_gpu_loaded(self) -> None:
        if not self._gpu_set.is_loaded:
            self._gpu_set = self._load_set(
                GPU_MODEL_A_JSON, GPU_MODEL_NULL_JSON,
                GPU_CLASSIFIER_JSON, GPU_CLASSIFIER_META,
                engine="gpu",
            )

    # ── Predicción ───────────────────────────────────────────────────────
    def predict(
        self,
        features: dict[str, float],
        engine: str = "cpu",
        feature_names: list[str] | None = None,
    ) -> RouterResult:
        """
        Predice el score usando el motor especificado.

        Args:
            features: dict {feature_name: value} con las 167 features.
            engine: "gpu" o "cpu". Si "gpu" no disponible, fallback a "cpu".
            feature_names: lista ordenada de features. Si None, se infiere.

        Returns:
            RouterResult con score, prob, engine_used y metadatos.
        """
        xgb = self._get_xgb()

        # Seleccionar ModelSet
        fallback = False
        fallback_reason = ""

        if engine == "gpu":
            self._ensure_gpu_loaded()
            if self._gpu_set.is_loaded:
                active_set = self._gpu_set
            else:
                # GPU models not trained yet → transparent CPU fallback
                self._ensure_cpu_loaded()
                active_set = self._cpu_set
                fallback = True
                fallback_reason = "GPU models not trained yet, using CPU fallback"
        else:
            self._ensure_cpu_loaded()
            active_set = self._cpu_set

        if not active_set.is_loaded:
            return RouterResult(
                score=0.0,
                prob=0.0,
                engine_used="none",
                fallback=True,
                fallback_reason="No models available (pre-training mode)",
            )

        # Construir vector de features usando los feature_names del modelo cargado
        if feature_names is None:
            feature_names = active_set.model_a.feature_names
        if not feature_names:
            return RouterResult(
                score=float("nan"),
                prob=float("nan"),
                engine_used="none",
                fallback=True,
                fallback_reason="FeatureContractViolation: model without feature_names",
            )

        # [A2] Sin cero-padding silencioso. Features faltantes o no finitas =
        # violación de contrato → resultado explícito NaN + warning con nombres,
        # para que el caller decida exclusión en vez de una predicción fabricada.
        missing = [f for f in feature_names if f not in features]
        non_finite = [
            f for f in feature_names
            if f in features and not np.isfinite(features[f])
        ]
        if missing or non_finite:
            _log.warning(
                "feature_contract_violation: %d missing, %d non-finite of %d (preview: %s)",
                len(missing), len(non_finite), len(feature_names), missing[:20],
            )
            return RouterResult(
                score=float("nan"),
                prob=float("nan"),
                engine_used=active_set.engine,
                fallback=True,
                fallback_reason=(
                    f"FeatureContractViolation: {len(missing)} missing, "
                    f"{len(non_finite)} non-finite of {len(feature_names)}"
                ),
            )

        X = np.array(
            [features[f] for f in feature_names],
            dtype=np.float32,
        ).reshape(1, -1)

        dmat = xgb.DMatrix(X, feature_names=feature_names)

        # [A2] Sub-vectores (model_null y clasificador) sobre subconjuntos del
        # contrato ya validado. Si el subconjunto pide una feature fuera del
        # contrato 167 → NaN explícito, nunca 0.0.
        def _subvector(sub_names: list[str]) -> np.ndarray | None:
            missing_sub = [f for f in sub_names if f not in features]
            if missing_sub:
                _log.warning(
                    "feature_contract_violation_subset: %d missing (preview: %s)",
                    len(missing_sub), missing_sub[:10],
                )
                return None
            return np.array(
                [features[f] for f in sub_names], dtype=np.float32
            ).reshape(1, -1)

        # Score model_a
        score_a = float(active_set.model_a.predict(dmat)[0])

        # Score model_null (para delta)
        score_null = 0.0
        if active_set.model_null is not None:
            from train_pipeline import NULL_FEATURES
            sub_null = _subvector(NULL_FEATURES)
            if sub_null is None:
                score_null = float("nan")
            else:
                dmat_null = xgb.DMatrix(sub_null, feature_names=NULL_FEATURES)
                score_null = float(active_set.model_null.predict(dmat_null)[0])

        delta = round(score_a - score_null, 4)

        # Probabilidad del clasificador binario
        prob = 0.0
        if active_set.classifier is not None:
            try:
                # Usar las features del clasificador (puede ser subconjunto)
                clf_features = active_set.classifier_meta.get(
                    "feature_names", feature_names
                )
                sub_clf = _subvector(clf_features)
                if sub_clf is None:
                    prob = float("nan")
                else:
                    dmat_clf = xgb.DMatrix(sub_clf, feature_names=clf_features)
                    prob = float(active_set.classifier.predict(dmat_clf)[0])
            except Exception as e:
                _log.warning(
                    "clf_predict_failed, engine=%s: %s",
                    active_set.engine, str(e)[:200],
                )
                prob = float("nan")

        return RouterResult(
            score=round(score_a, 4),
            prob=round(prob, 4),
            engine_used=active_set.engine,
            fallback=fallback,
            fallback_reason=fallback_reason,
            delta=delta,
        )

    # ── Estado ───────────────────────────────────────────────────────────
    def status(self) -> dict:
        """Devuelve el estado de los modelos cargados."""
        self._ensure_cpu_loaded()
        self._ensure_gpu_loaded()
        return {
            "cpu_models_available": self._cpu_set.is_loaded,
            "gpu_models_available": self._gpu_set.is_loaded,
            "gpu_artifacts_dir": str(GPU_ARTIFACTS_DIR),
            "gpu_model_a_exists": GPU_MODEL_A_JSON.exists(),
            "gpu_model_null_exists": GPU_MODEL_NULL_JSON.exists(),
            "gpu_classifier_exists": GPU_CLASSIFIER_JSON.exists(),
            "gpu_gnn_exists": GPU_GNN_PT.exists(),
        }

    def gpu_models_trained(self) -> bool:
        """True si los modelos GPU ya fueron entrenados."""
        return GPU_MODEL_A_JSON.exists() and GPU_MODEL_NULL_JSON.exists()


# ── Instancia singleton (importable por cualquier módulo) ─────────────────
_router_instance: ModelRouter | None = None


def get_router() -> ModelRouter:
    """Devuelve la instancia singleton del router."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ModelRouter()
    return _router_instance
