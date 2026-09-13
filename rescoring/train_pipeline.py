"""
rescoring/train_pipeline.py

Pipeline de entrenamiento para Model A y Model NULL.

Implementa los requisitos de ML_RESCORING_ARCHITECTURE.md Fase 2:
  1. Entrenar Model A (XGBoost rank:pairwise, TODAS las features)
  2. Entrenar Model NULL (XGBoost rank:pairwise, solo features 1D/2D escalares)
  3. Ablation testing por grupo de features (A, B, C)
  4. SHAP values para Model A
  5. Métricas: NDCG@10 + Spearman (NO R² ni RMSE como decisión)
  6. Calcular Delta para todos los complejos VIP
  7. Generar distribución Delta → artifacts/delta_distribution.json
  8. Construir Applicability Domain → artifacts/applicability_domain.json
  9. Performance por familia de proteínas
  10. Evaluar criterios de aceptación

REGLA: Este módulo NO inventa datos. Todo sale de PDBbind + XGBoost + SHAP.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from logger import get_logger
from scipy import stats

log = get_logger(__name__)


# ─── Feature groups para ablation testing ───
# Grupo A: Descriptores 1D/2D escalares puros
FEATURE_GROUP_A = [
    "mw", "logp", "tpsa", "hbd", "hba", "rotatable_bonds", "qed",
]

# Grupo A_EXT: Grupo A + size-aware features (v4)
FEATURE_GROUP_A_EXT = FEATURE_GROUP_A + ["log_mw"]

# Grupo B: Score Vina + pose variance
FEATURE_GROUP_B = [
    "vina_best_score",
    "pose_score_variance", "pose_score_range", "poses_passing_ratio",
]

# Grupo C: Features de interacción 3D (ProLIF)
FEATURE_GROUP_C = [
    "hbond_donor_count", "hbond_acceptor_count",
    "hydrophobic_contacts", "salt_bridges",
    "pi_stacking", "pi_cation", "metal_coordination",
    "close_contacts_4A", "close_contacts_6A",
]

# Grupo C_EXT: Grupo C (ProLIF interaction counts) + size-normalized contacts (v4)
# [fix #3 Spearman] ProLIF interaction counts excluidos de features ML:
#   - ρ=-0.035 en benchmark 5-HT1A (ruido puro para GPCRs)
#   - Las interacciones específicas (ASP116) importan más que el conteo total
#   - Se mantienen en features_used para visualización en frontend 3D viewer
FEATURE_GROUP_C_EXT = [
    "heavy_atom_count", "contacts_per_ha_4A", "contacts_per_ha_6A",
]

# Grupo D: Shell atom counts — RF-Score style (v4)
# Ref: Li et al., BMC Bioinformatics 2014;15:291
from feature_extractor import ECIF_FEATURES, SHELL_FEATURES

FEATURE_GROUP_D = SHELL_FEATURES  # 96 features

# Grupo E: ECIF-lite — Extended Connectivity Interaction Features (v4)
# Ref: Sánchez-Cruz et al., Bioinformatics 2021;37(10):1376
FEATURE_GROUP_E = ECIF_FEATURES  # 56 features

# Todas las features (Model A v4.1): 8 + 4 + 3 + 96 + 56 = 167
# [fix #3 Spearman] ProLIF interaction counts (9 features) removidos:
#   - Grupo C pasó de 12 a 3 features (solo size-norm: hac, contacts_per_ha_4A/6A)
#   - INTERACTION_FEATURES se mantienen en respuesta API para frontend
# FEATURE_GROUP_B (Vina) está incluido porque el modelo serializado ya
# lo usa y la inferencia (model_manager.py) siempre provee estos valores.
ALL_FEATURES = (
    FEATURE_GROUP_A_EXT
    + FEATURE_GROUP_B
    + FEATURE_GROUP_C_EXT
    + FEATURE_GROUP_D
    + FEATURE_GROUP_E
)

# Features del Model NULL (solo 1D/2D escalares puros — no 3D info)
NULL_FEATURES = FEATURE_GROUP_A_EXT

# ─── v3 feature sets (for backward compat / ablation) ───
ALL_FEATURES_V3 = FEATURE_GROUP_A + FEATURE_GROUP_B + FEATURE_GROUP_C


@dataclass
class TrainedModel:
    """Wrapper de un modelo entrenado con metadata."""
    name: str  # "model_a" o "model_null"
    model: Any  # XGBoost Booster
    feature_names: list[str]
    metrics: dict[str, float] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    train_samples: int = 0
    train_timestamp: str = ""


@dataclass
class AblationResult:
    """Resultado de una configuración de ablation testing."""
    feature_set_name: str  # e.g., "A_only", "B+C", "A+B+C"
    feature_names: list[str]
    n_features: int
    metrics: dict[str, float]  # {ndcg@10, spearman, ...}


@dataclass
class TrainingReport:
    """Reporte completo del entrenamiento."""
    model_a: TrainedModel | None = None
    model_null: TrainedModel | None = None
    ablation_results: list[AblationResult] = field(default_factory=list)
    shap_summary: dict[str, float] = field(default_factory=dict)
    delta_distribution: dict[str, float] = field(default_factory=dict)
    family_performance: dict[str, dict[str, float]] = field(default_factory=dict)
    acceptance_criteria: dict[str, bool] = field(default_factory=dict)
    timestamp: str = ""
    duration_seconds: float = 0.0


class MLTrainer:
    """
    Pipeline de entrenamiento para ML rescoring.

    Entrena Model A y Model NULL con XGBoost rank:pairwise,
    ejecuta ablation testing, calcula SHAP values, y evalúa
    criterios de aceptación.
    """

    def __init__(
        self,
        xgb_params: dict[str, Any] | None = None,
        n_estimators: int = 500,
        early_stopping_rounds: int = 50,
        seed: int = 42,
    ):
        self._seed = seed
        self._n_estimators = n_estimators
        self._early_stopping_rounds = early_stopping_rounds

        # ── Reproducibilidad cientifica ────────────────────────
        random.seed(seed)
        np.random.seed(seed)

        try:
            import xgboost as _xgb_setup
            _xgb_setup.set_config(verbosity=0)
        except Exception:
            pass

        # Parámetros por defecto para XGBoost
        #
        # NOTA CIENTÍFICA: El diseño original usa rank:pairwise (LTR) que
        # requiere grupos de múltiples ligandos por target. Con PDBbind sin
        # mapping de UniProt, cada complejo es su propio grupo (tamaño 1),
        # lo que hace que pairwise loss sea trivialmente 0.
        #
        # Por eso usamos reg:squarederror para predecir pKi directamente.
        # Esta es una aproximación HONESTA al problema: regresión de afinidad
        # sin pretender ranking intra-target.
        #
        # Cuando se integre UniProt mapping para agrupar ligandos del mismo
        # target, se puede cambiar a objective="rank:pairwise" con
        # eval_metric="ndcg@10" y labels discretizados.
        self._xgb_params = xgb_params or {
            "objective": "reg:squarederror",
            "eval_metric": "rmse",
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 5,
            "gamma": 0.1,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "seed": seed,
            "verbosity": 0,
        }

    def prepare_features(
        self,
        complexes: list[Any],
        pdb_ids: list[str],
        feature_names: list[str],
    ) -> np.ndarray:
        """
        Preparar matriz de features para los IDs dados.

        Asume que cada complejo tiene un dict `features` con los valores
        ya extraídos por feature_extractor.

        [A2] SIN zero-padding (era features.get(fname, 0.0)): los valores
        ausentes/no-finitos se imputan con la media de la columna calculada
        sobre los valores presentes del mismo conjunto/partición, y se
        registra warning con conteos. Si una columna completa está ausente
        no imputable, se lanza ValueError (contrato roto, no fabricación).

        Args:
            complexes: todos los complejos
            pdb_ids: IDs a incluir (en orden)
            feature_names: features a usar (columnas)

        Returns:
            numpy array (n_samples, n_features)
        """
        cpx_map = {c.pdb_id: c for c in complexes}
        X = np.zeros((len(pdb_ids), len(feature_names)))
        n_features = len(feature_names)
        miss_rows: list[list[int]] = [[] for _ in range(n_features)]
        present_vals: list[list[float]] = [[] for _ in range(n_features)]

        for i, pid in enumerate(pdb_ids):
            cpx = cpx_map.get(pid)
            if cpx is None:
                for j in range(n_features):
                    miss_rows[j].append(i)
                continue
            features = getattr(cpx, "features", {}) or {}
            for j, fname in enumerate(feature_names):
                val = features.get(fname)
                if val is None:
                    miss_rows[j].append(i)
                    continue
                try:
                    fv = float(val)
                except (TypeError, ValueError):
                    miss_rows[j].append(i)
                    continue
                if not math.isfinite(fv):
                    miss_rows[j].append(i)
                    continue
                X[i, j] = fv
                present_vals[j].append(fv)

        for j, fname in enumerate(feature_names):
            if not miss_rows[j]:
                continue
            if not present_vals[j]:
                raise ValueError(
                    f"train_feature_contract_violation: columna '{fname}' ausente en "
                    "todos los complejos; no imputable (config rota, no zero-pad)."
                )
            col_mean = float(np.mean(present_vals[j]))
            for i in miss_rows[j]:
                X[i, j] = col_mean
            log.warning(
                "train_feature_imputation",
                feature=fname,
                n_missing=len(miss_rows[j]),
                n_present=len(present_vals[j]),
                mean=col_mean,
            )

        return X

    def prepare_labels(
        self,
        complexes: list[Any],
        pdb_ids: list[str],
    ) -> np.ndarray:
        """Obtener labels (pKi) para los IDs dados."""
        cpx_map = {c.pdb_id: c for c in complexes}
        return np.array([cpx_map[pid].pki for pid in pdb_ids if pid in cpx_map])

    def train_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        groups_train: list[int],
        X_val: np.ndarray,
        y_val: np.ndarray,
        groups_val: list[int],
        feature_names: list[str],
        model_name: str = "model",
    ) -> TrainedModel:
        """
        Entrenar un modelo XGBoost.

        Soporta tanto regresión (reg:squarederror) como ranking (rank:pairwise).
        Groups se usan solo si el objective es ranking.

        Args:
            X_train, y_train, groups_train: datos de entrenamiento
            X_val, y_val, groups_val: datos de validación
            feature_names: nombres de features
            model_name: identificador del modelo

        Returns:
            TrainedModel con modelo entrenado y métricas
        """
        import xgboost as xgb

        is_ranking = "rank:" in self._xgb_params.get("objective", "")

        dtrain = xgb.DMatrix(
            X_train, label=y_train, feature_names=feature_names
        )
        dval = xgb.DMatrix(
            X_val, label=y_val, feature_names=feature_names
        )

        # Solo asignar grupos si es un objetivo de ranking
        if is_ranking:
            dtrain.set_group(groups_train)
            dval.set_group(groups_val)

        watchlist = [(dtrain, "train"), (dval, "val")]

        log.info(
            "training_start",
            model=model_name,
            n_train=X_train.shape[0],
            n_val=X_val.shape[0],
            n_features=X_train.shape[1],
        )

        booster = xgb.train(
            self._xgb_params,
            dtrain,
            num_boost_round=self._n_estimators,
            evals=watchlist,
            early_stopping_rounds=self._early_stopping_rounds,
            verbose_eval=False,
        )

        # Predecir
        preds_val = booster.predict(dval)
        metrics = self._compute_metrics(y_val, preds_val, groups_val)

        from datetime import datetime, timezone
        trained = TrainedModel(
            name=model_name,
            model=booster,
            feature_names=feature_names,
            metrics=metrics,
            params=dict(self._xgb_params),
            train_samples=X_train.shape[0],
            train_timestamp=datetime.now(timezone.utc).isoformat(),
        )

        log.info(
            "training_complete",
            model=model_name,
            metrics=metrics,
            best_iteration=booster.best_iteration if hasattr(booster, "best_iteration") else None,
        )

        return trained

    def train_model_a(
        self,
        complexes: list[Any],
        split: Any,
        groups_train: list[int],
        groups_val: list[int],
    ) -> TrainedModel:
        """Entrenar Model A con TODAS las features."""
        X_train = self.prepare_features(complexes, split.train_ids, ALL_FEATURES)
        y_train = self.prepare_labels(complexes, split.train_ids)
        X_val = self.prepare_features(complexes, split.val_ids, ALL_FEATURES)
        y_val = self.prepare_labels(complexes, split.val_ids)

        return self.train_model(
            X_train, y_train, groups_train,
            X_val, y_val, groups_val,
            ALL_FEATURES, "model_a",
        )

    def train_model_null(
        self,
        complexes: list[Any],
        split: Any,
        groups_train: list[int],
        groups_val: list[int],
    ) -> TrainedModel:
        """
        Entrenar Model NULL con SOLO features 1D/2D escalares.

        PER ARCHITECTURE:
          "Restricción del Modelo NULL: Solo puede usar propiedades
          escalares puras. NO puede usar fingerprints topológicos ni
          descriptores que codifiquen forma indirectamente."
        """
        X_train = self.prepare_features(complexes, split.train_ids, NULL_FEATURES)
        y_train = self.prepare_labels(complexes, split.train_ids)
        X_val = self.prepare_features(complexes, split.val_ids, NULL_FEATURES)
        y_val = self.prepare_labels(complexes, split.val_ids)

        return self.train_model(
            X_train, y_train, groups_train,
            X_val, y_val, groups_val,
            NULL_FEATURES, "model_null",
        )

    def train_model_a_extended(
        self,
        complexes: list[Any],
        split: Any,
        groups_train: list[int],
        groups_val: list[int],
    ) -> TrainedModel:
        """
        Entrenar Model A Extended con las mismas features que Core pero
        con hiperparámetros diferentes para un consenso dual real.

        Estrategia:
          - Core (train_model_a): max_depth=6, lr=0.05, subsample=0.8, reg_alpha=0.1
          - Extended:             max_depth=8, lr=0.03, subsample=0.7, reg_alpha=0.5

        El modelo Extended es más profundo pero más regularizado y
        estocástico. Esto produce predicciones diferentes (no idénticas
        a Core) que el consenso Mahalanobis puede interpolar con valor real.
        """
        X_train = self.prepare_features(complexes, split.train_ids, ALL_FEATURES)
        y_train = self.prepare_labels(complexes, split.train_ids)
        X_val = self.prepare_features(complexes, split.val_ids, ALL_FEATURES)
        y_val = self.prepare_labels(complexes, split.val_ids)

        # Parámetros diferentes para el modelo Extended
        extended_params = dict(self._xgb_params)
        extended_params.update({
            "max_depth": 8,
            "learning_rate": 0.03,
            "subsample": 0.7,
            "colsample_bytree": 0.7,
            "reg_alpha": 0.5,
            "reg_lambda": 2.0,
            "gamma": 0.2,
            "min_child_weight": 8,
        })

        # Guardar params originales, inyectar los nuevos, restaurar después
        original_params = self._xgb_params
        self._xgb_params = extended_params
        try:
            return self.train_model(
                X_train, y_train, groups_train,
                X_val, y_val, groups_val,
                ALL_FEATURES, "model_a_extended",
            )
        finally:
            self._xgb_params = original_params

    def run_ablation(
        self,
        complexes: list[Any],
        split: Any,
        groups_train: list[int],
        groups_val: list[int],
    ) -> list[AblationResult]:
        """
        Ablation testing por grupo de features.

        Configuraciones:
          - A only: solo descriptores 1D/2D
          - B only: solo Vina score/variance
          - C only: solo interacciones 3D
          - A+B: 1D/2D + Vina
          - A+C: 1D/2D + 3D
          - B+C: Vina + 3D
          - A+B+C: todas (= Model A)

        Criterio de aceptación:
          Si A_only ≈ A+B+C → RECHAZAR modelo (sesgo de ligando)
          Grupo C debe contribuir mejora significativa sobre Grupo A.
        """
        configurations = {
            "A_ext_only": FEATURE_GROUP_A_EXT,
            "B_only": FEATURE_GROUP_B,
            "C_ext_only": FEATURE_GROUP_C_EXT,
            "D_only_shell": FEATURE_GROUP_D,
            "E_only_ecif": FEATURE_GROUP_E,
            "A_ext+C_ext": FEATURE_GROUP_A_EXT + FEATURE_GROUP_C_EXT,
            "A_ext+D": FEATURE_GROUP_A_EXT + FEATURE_GROUP_D,
            "A_ext+E": FEATURE_GROUP_A_EXT + FEATURE_GROUP_E,
            "A_ext+D+E": FEATURE_GROUP_A_EXT + FEATURE_GROUP_D + FEATURE_GROUP_E,
            "A_ext+C_ext+D+E": (
                FEATURE_GROUP_A_EXT + FEATURE_GROUP_C_EXT
                + FEATURE_GROUP_D + FEATURE_GROUP_E
            ),
            "ALL_v4": ALL_FEATURES,
        }

        results = []
        for name, features in configurations.items():
            log.info("ablation_config", name=name, n_features=len(features))

            try:
                X_train = self.prepare_features(complexes, split.train_ids, features)
                y_train = self.prepare_labels(complexes, split.train_ids)
                X_val = self.prepare_features(complexes, split.val_ids, features)
                y_val = self.prepare_labels(complexes, split.val_ids)

                trained = self.train_model(
                    X_train, y_train, groups_train,
                    X_val, y_val, groups_val,
                    features, f"ablation_{name}",
                )

                results.append(AblationResult(
                    feature_set_name=name,
                    feature_names=features,
                    n_features=len(features),
                    metrics=trained.metrics,
                ))

            except Exception as e:
                log.error("ablation_failed", name=name, error=str(e))
                results.append(AblationResult(
                    feature_set_name=name,
                    feature_names=features,
                    n_features=len(features),
                    metrics={"error": str(e)},
                ))

        return results

    def compute_shap_values(
        self,
        model: TrainedModel,
        X: np.ndarray,
        max_samples: int = 1000,
    ) -> dict[str, float]:
        """
        Calcular SHAP values globales para el modelo.

        Retorna mean(|SHAP|) por feature — importancia promedio.

        SHAP es model-agnostic y mide contribución marginal de cada
        feature a la predicción, no solo correlación.

        Criterio de aceptación:
          Top-5 features deben incluir ≥ 2 features de interacción 3D.
        """
        import shap

        # Limitar samples para eficiencia
        if X.shape[0] > max_samples:
            rng = np.random.RandomState(self._seed)
            idx = rng.choice(X.shape[0], max_samples, replace=False)
            X_sample = X[idx]
        else:
            X_sample = X

        try:
            explainer = shap.TreeExplainer(model.model)
            shap_values = explainer.shap_values(X_sample)

            # Mean absolute SHAP por feature
            mean_abs_shap = np.mean(np.abs(shap_values), axis=0)

            shap_dict = {}
            for i, fname in enumerate(model.feature_names):
                shap_dict[fname] = round(float(mean_abs_shap[i]), 6)
        except Exception as shap_err:
            log.warning("shap_explainer_failed_falling_back_to_gain", error=str(shap_err))
            importance_gain = model.model.get_score(importance_type="gain")
            total_gain = sum(importance_gain.values()) if importance_gain else 1.0
            shap_dict = {}
            for fname in model.feature_names:
                gain = importance_gain.get(fname, 0.0)
                shap_dict[fname] = round(float((gain / total_gain) * 0.5 if total_gain > 0 else 0.0), 6)

        # Ordenar por importancia
        shap_sorted = dict(
            sorted(shap_dict.items(), key=lambda x: x[1], reverse=True)
        )

        log.info(
            "shap_computed",
            model=model.name,
            top_5=list(shap_sorted.keys())[:5],
            top_5_values=list(shap_sorted.values())[:5],
        )

        return shap_sorted

    def compute_delta(
        self,
        model_a: TrainedModel,
        model_null: TrainedModel,
        complexes: list[Any],
        pdb_ids: list[str],
    ) -> dict[str, float]:
        """
        Calcular Delta = pred_A - pred_NULL para cada complejo.

        Delta > 0: features 3D aportan (interacción específica)
        Delta ≈ 0: solo propiedades fisicoquímicas (binding inespecífico)
        Delta < 0: choque estérico (propiedades OK, geometría mala)
        """
        import xgboost as xgb

        X_a = self.prepare_features(complexes, pdb_ids, model_a.feature_names)
        X_null = self.prepare_features(complexes, pdb_ids, model_null.feature_names)

        d_a = xgb.DMatrix(X_a, feature_names=model_a.feature_names)
        d_null = xgb.DMatrix(X_null, feature_names=model_null.feature_names)

        pred_a = model_a.model.predict(d_a)
        pred_null = model_null.model.predict(d_null)

        deltas = {}
        for i, pid in enumerate(pdb_ids):
            deltas[pid] = round(float(pred_a[i] - pred_null[i]), 4)

        return deltas

    def build_delta_distribution(
        self,
        deltas: dict[str, float],
    ) -> dict[str, Any]:
        """
        Construir distribución de Delta para calibrar el semáforo.

        Per architecture:
          - Percentiles 25 y 60 como umbrales del semáforo
          - green > p60 (Delta alto → interacción 3D específica)
          - yellow entre p25 y p60
          - red < p25 (Delta bajo → binding inespecífico o choque)

        Returns:
            dict con estadísticas y percentiles,
            listo para guardar en artifacts/delta_distribution.json
        """
        values = np.array(list(deltas.values()))

        distribution = {
            "n_complexes": len(values),
            "mean": round(float(np.mean(values)), 4),
            "std": round(float(np.std(values)), 4),
            "min": round(float(np.min(values)), 4),
            "max": round(float(np.max(values)), 4),
            "median": round(float(np.median(values)), 4),
            "percentiles": {
                str(p): round(float(np.percentile(values, p)), 4)
                for p in [5, 10, 25, 50, 60, 75, 90, 95]
            },
            "semaphore_thresholds": {
                "green_above": round(float(np.percentile(values, 60)), 4),
                "red_below": round(float(np.percentile(values, 25)), 4),
            },
        }

        log.info(
            "delta_distribution",
            mean=distribution["mean"],
            std=distribution["std"],
            green_threshold=distribution["semaphore_thresholds"]["green_above"],
            red_threshold=distribution["semaphore_thresholds"]["red_below"],
        )

        return distribution

    def build_applicability_domain(
        self,
        complexes: list[Any],
        pdb_ids: list[str],
        feature_names: list[str],
    ) -> dict[str, Any]:
        """
        Construir Applicability Domain desde el training set.

        Calcula media, covarianza inversa y umbral (p99) para
        Mahalanobis distance. Moléculas fuera del AD reciben
        degradación explícita.

        Returns:
            dict listo para guardar en artifacts/applicability_domain.json
        """
        X = self.prepare_features(complexes, pdb_ids, feature_names)

        mean = np.mean(X, axis=0)
        # Ensure mean is always 1D array (scalar for 1 feature)
        mean = np.atleast_1d(mean)

        cov = np.cov(X.T)

        # np.cov returns scalar for 1 feature — ensure 2D
        if cov.ndim == 0:
            cov = np.array([[float(cov)]])
        elif cov.ndim == 1:
            cov = cov.reshape(1, 1)

        # Regularización para evitar singularidad
        cov += np.eye(cov.shape[0]) * 1e-6

        try:
            cov_inv = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            log.warning("cov_singular", msg="Covarianza singular, usando pseudoinversa")
            cov_inv = np.linalg.pinv(cov)

        # Calcular Mahalanobis para todos los puntos de training
        diffs = X - mean
        mahal_dists = np.sqrt(np.sum(diffs @ cov_inv * diffs, axis=1))

        # Umbral = percentil 99 (1% de training queda fuera)
        threshold = float(np.percentile(mahal_dists, 99))

        ad_data = {
            "n_training_samples": len(pdb_ids),
            "n_features": len(feature_names),
            "feature_names": feature_names,
            "mean": mean.tolist(),
            "cov_inv": cov_inv.tolist(),
            "threshold_p99": round(threshold, 4),
            "training_mahal_stats": {
                "mean": round(float(np.mean(mahal_dists)), 4),
                "std": round(float(np.std(mahal_dists)), 4),
                "max": round(float(np.max(mahal_dists)), 4),
                "p95": round(float(np.percentile(mahal_dists, 95)), 4),
                "p99": round(threshold, 4),
            },
        }

        log.info(
            "applicability_domain_built",
            n_samples=len(pdb_ids),
            n_features=len(feature_names),
            threshold_p99=round(threshold, 4),
        )

        return ad_data

    def evaluate_by_family(
        self,
        model: TrainedModel,
        complexes: list[Any],
        pdb_ids: list[str],
        family_classifications: dict[str, Any],
    ) -> dict[str, dict[str, float]]:
        """
        Medir performance por familia de proteínas.

        Per architecture: medir especialmente GPCRs vs kinasas
        para detectar sub-representación.
        """
        import xgboost as xgb

        cpx_map = {c.pdb_id: c for c in complexes}

        # Agrupar IDs por familia
        by_family: dict[str, list[str]] = {}
        for pid in pdb_ids:
            family = "other"
            if pid in family_classifications:
                fc = family_classifications[pid]
                family = fc.family if hasattr(fc, "family") else str(fc)
            if family not in by_family:
                by_family[family] = []
            by_family[family].append(pid)

        results = {}
        for family, fam_ids in by_family.items():
            if len(fam_ids) < 5:
                results[family] = {
                    "n": len(fam_ids),
                    "note": "Too few samples for metrics",
                }
                continue

            X = self.prepare_features(complexes, fam_ids, model.feature_names)
            y = self.prepare_labels(complexes, fam_ids)

            d = xgb.DMatrix(X, feature_names=model.feature_names)
            preds = model.model.predict(d)

            rho, pval = stats.spearmanr(y, preds)

            results[family] = {
                "n": len(fam_ids),
                "spearman": round(float(rho), 4) if not np.isnan(rho) else 0.0,
                "spearman_pval": round(float(pval), 6) if not np.isnan(pval) else 1.0,
                "y_mean": round(float(np.mean(y)), 3),
                "y_std": round(float(np.std(y)), 3),
            }

        return results

    def evaluate_acceptance_criteria(
        self,
        ablation_results: list[AblationResult],
        shap_summary: dict[str, float],
        delta_distribution: dict[str, Any],
        model_a_metrics: dict[str, float],
    ) -> dict[str, bool]:
        """
        Evaluar los criterios de aceptación del modelo.

        Per architecture sec 8:
        1. Ablation: grupo C aporta mejora significativa sobre grupo A
        2. Scaffold-split NDCG@10 > baseline, Spearman > 0
        3. SHAP top-5 incluye ≥ 2 features 3D
        4. Delta promedio > 0

        Returns:
            dict {criterion: passed}
        """
        criteria = {}

        # 1. Ablation: 3D features contribute significantly over A_EXT alone
        # Look for baseline (A-only variants) and full model
        a_only = next(
            (r for r in ablation_results
             if r.feature_set_name in ("A_ext_only", "A_only")),
            None,
        )
        abc = next(
            (r for r in ablation_results
             if r.feature_set_name in ("ALL_v4", "A+B+C")),
            None,
        )

        if a_only and abc:
            a_spearman = a_only.metrics.get("spearman", 0.0)
            abc_spearman = abc.metrics.get("spearman", 0.0)

            # 3D features contribute if full model > baseline by > 0.05
            improvement = abc_spearman - a_spearman
            criteria["ablation_3d_contributes"] = improvement > 0.05
            criteria["ablation_improvement"] = round(improvement, 4)
        else:
            criteria["ablation_3d_contributes"] = False

        # 2. Spearman > 0 (NDCG@10 es TRIVIAL: groups=[1]*N → ranking global, no intra-target)
        spearman = model_a_metrics.get("spearman", 0.0)
        ndcg = model_a_metrics.get("ndcg@10", 0.0)
        criteria["scaffold_split_spearman_positive"] = spearman > 0
        criteria["scaffold_split_ndcg_positive"] = ndcg > 0
        criteria["ndcg_trivial_warning"] = True  # groups=[1]*N hace NDCG ranking global vacío

        # 3. SHAP top-5 includes ≥ 2 features that are NOT in Group A_EXT
        # (i.e., 3D structural features or shell/ECIF features)
        top_5 = list(shap_summary.keys())[:5]
        non_a_features = set(ALL_FEATURES) - set(FEATURE_GROUP_A_EXT)
        n_3d_in_top5 = sum(1 for f in top_5 if f in non_a_features)
        criteria["shap_3d_in_top5"] = n_3d_in_top5 >= 2
        criteria["shap_3d_in_top5_count"] = n_3d_in_top5

        # 4. Delta mean > 0
        delta_mean = delta_distribution.get("mean", 0.0)
        criteria["delta_mean_positive"] = delta_mean > 0

        # Overall
        criteria["all_passed"] = all([
            criteria.get("ablation_3d_contributes", False),
            criteria.get("scaffold_split_spearman_positive", False),
            # criteria.get("scaffold_split_ndcg_positive", False),  # TRIVIAL — groups=[1]*N
            criteria.get("shap_3d_in_top5", False),
            criteria.get("delta_mean_positive", False),
        ])

        log.info("acceptance_criteria_evaluated", criteria=criteria)

        return criteria

    @staticmethod
    def _compute_metrics(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        groups: list[int] | None = None,
    ) -> dict[str, float]:
        """
        Calcular métricas de evaluación.

        Per architecture: NDCG@10 + Spearman como métricas principales.
        R² y RMSE se calculan solo como referencia, NO para decisión.
        """
        metrics: dict[str, float] = {}

        # Spearman rank correlation (métrica principal)
        rho, pval = stats.spearmanr(y_true, y_pred)
        metrics["spearman"] = round(float(rho), 4) if not np.isnan(rho) else 0.0
        metrics["spearman_pval"] = round(float(pval), 6) if not np.isnan(pval) else 1.0

        # Pearson (referencia)
        r, _ = stats.pearsonr(y_true, y_pred)
        metrics["pearson"] = round(float(r), 4) if not np.isnan(r) else 0.0

        # NDCG@10 (per-group si hay grupos)
        ndcg = _compute_ndcg(y_true, y_pred, groups, k=10)
        metrics["ndcg@10"] = round(ndcg, 4)

        # R² y RMSE solo como referencia (NO para decisión)
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
        metrics["r2_reference_only"] = round(float(r2), 4)
        metrics["rmse_reference_only"] = round(float(rmse), 4)

        return metrics

    @staticmethod
    def save_model(model: TrainedModel, path: str | Path) -> None:
        """Guardar modelo XGBoost entrenado."""
        import joblib
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Guardar como joblib (incluye metadata)
        joblib.dump({
            "booster": model.model,
            "feature_names": model.feature_names,
            "params": model.params,
            "metrics": model.metrics,
            "train_samples": model.train_samples,
            "train_timestamp": model.train_timestamp,
        }, path)
        log.info("model_saved", name=model.name, path=str(path))

    @staticmethod
    def save_json_artifact(data: dict, path: str | Path, description: str = "") -> None:
        """Guardar artefacto JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        log.info("artifact_saved", path=str(path), description=description)


def _compute_ndcg(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    groups: list[int] | None = None,
    k: int = 10,
) -> float:
    """
    Calcular NDCG@k (Normalized Discounted Cumulative Gain).

    Para LTR, NDCG mide la calidad del ranking: ¿los mejores ligandos
    están en las primeras posiciones?

    Si hay grupos, calcula NDCG por grupo y promedia.
    Si no hay grupos (o todos tamaño 1), calcula global.
    """
    if groups is not None and len(set(groups)) > 1 and max(groups) > 1:
        # Calcular por grupo
        ndcgs = []
        offset = 0
        for size in groups:
            if size < 2:
                offset += size
                continue
            y_g = y_true[offset:offset + size]
            p_g = y_pred[offset:offset + size]
            ndcg = _ndcg_single(y_g, p_g, k)
            ndcgs.append(ndcg)
            offset += size
        return float(np.mean(ndcgs)) if ndcgs else 0.0
    else:
        # Global NDCG
        return _ndcg_single(y_true, y_pred, k)


def _ndcg_single(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    k: int,
) -> float:
    """NDCG@k para un solo grupo/lista."""
    if len(y_true) < 2:
        return 1.0  # Trivial

    # Orden predicho
    order = np.argsort(-y_pred)[:k]
    y_sorted = y_true[order]

    # DCG
    gains = 2 ** y_sorted - 1
    discounts = np.log2(np.arange(len(gains)) + 2)
    dcg = float(np.sum(gains / discounts))

    # IDCG (orden ideal)
    ideal_order = np.argsort(-y_true)[:k]
    ideal_sorted = y_true[ideal_order]
    ideal_gains = 2 ** ideal_sorted - 1
    ideal_discounts = np.log2(np.arange(len(ideal_gains)) + 2)
    idcg = float(np.sum(ideal_gains / ideal_discounts))

    if idcg == 0:
        return 0.0

    return dcg / idcg
