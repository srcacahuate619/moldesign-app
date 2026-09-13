"""
rescoring/model_manager.py

Gestión de carga y predicción de los modelos ML de rescoring.

Carga al arranque:
  - Modelo A (XGBoost rank:pairwise, features completas)
  - Modelo NULL (XGBoost rank:pairwise, solo features 1D/2D)
  - Distribución de Delta (para umbrales de semáforo)
  - Applicability Domain (media, cov_inv, threshold)

Si los artefactos no existen (Fase 1 — antes de entrenamiento),
el servicio arranca en modo degradado: health = degraded, /rescore = 503.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from config import get_rescoring_settings
from logger import get_logger
from train_pipeline import ALL_FEATURES

log = get_logger(__name__)
settings = get_rescoring_settings()

# [A2] Contrato de features: el Model A (universal y familia) se entrena con
# EXACTAMENTE 167 features. Un artifact con otro conteo (p. ej. el legacy
# artifacts/model_a.json de 176 features) es una violación de contrato y debe
# rechazarse en carga, no en predicción.
EXPECTED_MODEL_A_FEATURES = 167


class FeatureContractViolation(Exception):
    """[A2] Features faltantes o no finitas que NO pueden imputarse con la
    media de entrenamiento (applicability_domain). El caller debe excluir la
    molécula explícitamente — nunca fabricar un valor (0.0 / 0.5 / neutral)."""

    def __init__(self, missing: list[str], context: str = ""):
        self.missing = missing
        self.context = context
        super().__init__(
            f"FeatureContractViolation: {len(missing)} features no imputables"
            f"{(' (' + context + ')') if context else ''}: {missing[:20]}"
        )


class ModelManager:
    """Gestor de modelos de rescoring."""

    def __init__(self):
        self.model_a = None
        self.model_null = None
        self.model_a_artifact: dict | None = None
        self.model_null_artifact: dict | None = None
        self.delta_distribution: dict[str, Any] | None = None
        self.applicability_domain: dict[str, Any] | None = None
        self.training_report: dict[str, Any] | None = None
        self._is_loaded = False
        self._model_version: str | None = None
        # Family-specific models
        self.family_models: dict[str, Any] = {}
        self.family_metadata: dict[str, dict] = {}
        self._families_trained: list[str] = []
        # Binder classifier
        self.classifier_binder: Any = None
        self.classifier_metadata: dict | None = None
        # Pose selector (Ruta C v0.6, Fase 4) — opcional y aditivo: None
        # implica que el rescoring funciona exactamente igual que antes.
        self.pose_selector: Any = None
        self.pose_selector_load_error: str | None = None
        # The docked pose is part of the scientific input. Reusing coordinates
        # merely because SMILES + target coincide can score another pose with
        # stale 3D features.
        self._feature_cache: dict[tuple[str, str, str], dict[str, float]] = {}
        self._feature_cache_max: int = 256
        # [A2] Medias de entrenamiento (desde applicability_domain) para
        # imputación explícita de features faltantes. Se llena en load_models.
        self._feature_means: dict[str, float] = {}

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def model_version(self) -> str | None:
        return self._model_version

    @staticmethod
    def _auto_convert_joblib(
        model_a_path: Path,
        model_null_path: Path,
    ) -> None:
        """Auto-convert .joblib artifacts to XGBoost .json + .metadata.json.

        The training pipeline saves models as .joblib, but inference expects .json.
        If .joblib exists but .json doesn't, convert automatically.
        """
        import joblib as _joblib

        for json_path in [p for p in (model_a_path, model_null_path) if p is not None]:
            joblib_path = json_path.with_suffix(".joblib")
            if not joblib_path.exists() or json_path.exists():
                continue  # Nothing to convert or JSON already exists
            try:
                data = _joblib.load(joblib_path)
                booster = data.get("booster") or data.get("model")
                if booster is None:
                    log.warning("joblib_no_booster", path=str(joblib_path))
                    continue
                booster.save_model(str(json_path))
                # Save metadata
                metadata = {
                    "feature_names": data.get("feature_names", []),
                    "metrics": data.get("metrics", {}),
                    "train_samples": data.get("train_samples", 0),
                    "train_timestamp": data.get("train_timestamp", ""),
                    "params": data.get("params", {}),
                }
                meta_path = json_path.with_suffix(".metadata.json")
                with open(meta_path, "w") as f:
                    json.dump(metadata, f, indent=2)
                log.info("joblib_converted", from_path=str(joblib_path), to=str(json_path))
            except Exception as e:
                log.error("joblib_conversion_failed", path=str(joblib_path), error=str(e))

    def load_models(self) -> None:
        """
        Intentar cargar todos los artefactos del modelo.

        Si no existen (pre-entrenamiento), el servicio arranca en modo degradado.
        Esto es esperado en Fase 1 — el servicio existe pero no tiene modelo todavía.
        """
        model_a_path = Path(settings.model_a_path)
        model_null_path = Path(settings.model_null_path)
        ad_path = Path(settings.applicability_domain_path)
        delta_path = Path(settings.delta_distribution_path)
        report_path = Path(settings.training_report_path)

        # Verificar si existen los artefactos mínimos
        # [FIX] Auto-detectar y convertir joblib → JSON si es necesario
        self._auto_convert_joblib(model_a_path, model_null_path)

        if not model_a_path.exists() or not model_null_path.exists():
            log.warning(
                "models_not_found",
                msg=(
                    "Artefactos de modelo no encontrados. "
                    "El servicio arranca en modo degradado. "
                    "Ejecute el entrenamiento (Fase 2) para generar los modelos."
                ),
                model_a_exists=model_a_path.exists(),
                model_null_exists=model_null_path.exists(),
            )
            return

        try:
            import xgboost as xgb

            # Cargar Modelo A (JSON)
            self.model_a = xgb.Booster()
            self.model_a.load_model(str(model_a_path))

            # [A2] Guard de contrato: Model A fuera de 167 features (p. ej.
            # legacy de 176) → modo degradado explícito, jamás predicción.
            n_model_a = len(self.model_a.feature_names or [])
            if n_model_a != EXPECTED_MODEL_A_FEATURES:
                log.error(
                    "model_a_contract_violation",
                    path=str(model_a_path),
                    n_features=n_model_a,
                    expected=EXPECTED_MODEL_A_FEATURES,
                )
                self.model_a = None
                return

            # Cargar Modelo NULL (JSON)
            self.model_null = xgb.Booster()
            self.model_null.load_model(str(model_null_path))

            # Intentar cargar metadatos (nombres de features) desde archivos .metadata.json
            meta_a_path = model_a_path.with_suffix(".metadata.json")
            meta_null_path = model_null_path.with_suffix(".metadata.json")

            if meta_a_path.exists():
                with open(meta_a_path) as f:
                    self.model_a_artifact = json.load(f)
            else:
                self.model_a_artifact = {"feature_names": []}

            if meta_null_path.exists():
                with open(meta_null_path) as f:
                    self.model_null_artifact = json.load(f)
            else:
                self.model_null_artifact = {"feature_names": []}

            log.info(
                "models_loaded_json",
                model_a=str(model_a_path),
                model_null=str(model_null_path),
                model_a_features=len(self.model_a_artifact.get("feature_names", [])),
                model_null_features=len(self.model_null_artifact.get("feature_names", [])),
            )
        except Exception as e:
            import traceback
            log.error("model_load_error", error=str(e), traceback=traceback.format_exc())
            return

        # [F-19] Modelo A Extended RETIRADO (2026-08-13): era byte-idéntico
        # al legacy model_a_legacy_176.json (167 + 9 ProLIF), el huérfano de
        # 176 features rechazado por el contrato A2. Ya no se carga, no se
        # interpola y no se imputan sus medias ProLIF.

        # ── Cargar modelos por familia estructural ──
        family_model_dir = Path(settings.model_a_path).parent
        for family in ["kinase", "protease", "gpcr", "nuclear_receptor", "soluble_enzyme"]:
            fam_json = family_model_dir / f"model_a_{family}.json"
            fam_joblib = fam_json.with_suffix(".joblib")

            # Preferir .joblib y auto-convertir si es necesario
            if fam_joblib.exists() and not fam_json.exists():
                self._auto_convert_joblib(fam_json, fam_json)

            if not fam_json.exists():
                continue
            try:
                model = xgb.Booster()
                model.load_model(str(fam_json))

                # [A2] Guard de contrato para modelos familiares (167 features).
                n_fam = len(model.feature_names or [])
                if n_fam != EXPECTED_MODEL_A_FEATURES:
                    log.error(
                        "family_model_contract_violation",
                        family=family,
                        n_features=n_fam,
                        expected=EXPECTED_MODEL_A_FEATURES,
                    )
                    continue

                self.family_models[family] = model
                self._families_trained.append(family)

                meta_path = fam_json.with_suffix(".metadata.json")
                if meta_path.exists():
                    with open(meta_path) as f:
                        self.family_metadata[family] = json.load(f)
                else:
                    self.family_metadata[family] = {"feature_names": ALL_FEATURES}
                log.info("family_model_loaded", family=family)
            except Exception as e:
                log.warning("family_model_load_failed", family=family, error=str(e))

        # ── Cargar clasificador binario de binding quality ──
        classifier_path = family_model_dir / "classifier_binder.json"
        if classifier_path.exists():
            try:
                self.classifier_binder = xgb.Booster()
                self.classifier_binder.load_model(str(classifier_path))
                meta_path = classifier_path.with_suffix(".metadata.json")
                if meta_path.exists():
                    with open(meta_path) as f:
                        self.classifier_metadata = json.load(f)
                log.info("classifier_loaded", path=str(classifier_path))
            except Exception as e:
                log.warning("classifier_load_failed", error=str(e))

        # Cargar Applicability Domain
        if ad_path.exists():
            try:
                with open(ad_path) as f:
                    ad_data = json.load(f)
                    threshold_val = ad_data.get("threshold", ad_data.get("threshold_p99"))
                    self.applicability_domain = {
                        "mean": np.array(ad_data["mean"]),
                        "cov_inv": np.array(ad_data["cov_inv"]),
                        "threshold": threshold_val,
                        "feature_names": ad_data.get("feature_names", []),
                        "feature_ranges": ad_data.get("feature_ranges", {}),
                    }
                    log.info("applicability_domain_loaded", threshold=threshold_val)
            except Exception as e:
                log.error("ad_load_error", error=str(e))

        # Cargar distribución de Delta
        if delta_path.exists():
            try:
                with open(delta_path) as f:
                    self.delta_distribution = json.load(f)
                log.info("delta_distribution_loaded")
            except Exception as e:
                log.error("delta_load_error", error=str(e))

        # Cargar training report
        if report_path.exists():
            try:
                with open(report_path) as f:
                    self.training_report = json.load(f)
                self._model_version = self.training_report.get("version", "unknown")
                log.info("training_report_loaded", version=self._model_version)
            except Exception as e:
                log.error("report_load_error", error=str(e))

        # [A2] Medias de entrenamiento para imputación explícita: se usan
        # únicamente las del AD core (167 features). Nunca se usará 0.0 como
        # imputación silenciosa.
        self._feature_means = {}
        ad = self.applicability_domain
        if ad:
            ad_fn = ad.get("feature_names", [])
            ad_mean = ad.get("mean")
            if ad_mean is not None and len(ad_mean) == len(ad_fn):
                self._feature_means.update(
                    {n: float(v) for n, v in zip(ad_fn, ad_mean)}
                )
        if self._feature_means:
            log.info("feature_means_ready", n_features=len(self._feature_means))

        # ── Pose selector (Ruta C v0.6, Fase 4): carga aditiva y opcional ──
        # No participa del contrato A2: si sus artefactos faltan o fallan,
        # self.pose_selector queda None y predict() continúa sin tocar los
        # campos de pose_scores/selected_pose_rank (degradación elegante).
        self.pose_selector = None
        self.pose_selector_load_error = None
        if settings.pose_selector_enabled:
            ps_model_path = Path(settings.pose_selector_model_path)
            ps_meta_path = Path(settings.pose_selector_meta_path)
            if ps_model_path.exists() and ps_meta_path.exists():
                try:
                    from pose_selector.selector import PoseSelector
                    selector = PoseSelector(
                        str(ps_model_path),
                        str(ps_meta_path),
                        abstention_threshold=(
                            settings.pose_selector_abstention_threshold
                        ),
                    )
                    if getattr(selector, "load_error", None):
                        self.pose_selector_load_error = selector.load_error
                        log.warning(
                            "pose_selector_load_failed",
                            error=self.pose_selector_load_error,
                        )
                    else:
                        self.pose_selector = selector
                        log.info(
                            "pose_selector_loaded",
                            model=str(ps_model_path),
                            meta=str(ps_meta_path),
                        )
                except Exception as e:
                    self.pose_selector_load_error = str(e)
                    log.warning("pose_selector_load_failed", error=str(e))
            else:
                self.pose_selector_load_error = (
                    "artefactos del pose selector ausentes: "
                    f"{ps_model_path} / {ps_meta_path}"
                )
                log.warning(
                    "pose_selector_artifacts_missing",
                    model_exists=ps_model_path.exists(),
                    meta_exists=ps_meta_path.exists(),
                )

        self._is_loaded = True
        log.info(
            "rescoring_ready",
            model_version=self._model_version,
            has_ad=self.applicability_domain is not None,
            has_delta_dist=self.delta_distribution is not None,
        )

    def get_info(self) -> dict[str, Any]:
        """Metadata del modelo para el endpoint /info."""
        if not self._is_loaded or self.training_report is None:
            return {
                "model_version": None,
                "training_date": None,
                "training_samples": None,
                "ndcg_at_10": None,
                "spearman": None,
                "applicability_domain_threshold": None,
                "families_trained": list(self._families_trained),
            }

        report = self.training_report
        model_a_cv = report.get("cross_validation", {}).get("model_a", {})
        spearman_val = model_a_cv.get("spearman", {}).get("mean")
        ndcg_val = model_a_cv.get("ndcg@10", {}).get("mean")

        return {
            "model_version": report.get("status", "unknown"),
            "training_date": report.get("timestamp"),
            "training_samples": report.get("pdbbind_loaded", report.get("data_curation", {}).get("output_curated")),
            "ndcg_at_10": ndcg_val,
            "spearman": spearman_val,
            "applicability_domain_threshold": (
                self.applicability_domain["threshold"] if self.applicability_domain else None
            ),
            "families_trained": list(self._families_trained),
        }

    def predict(self, request) -> Any:
        """
        Pipeline completo de predicción.

        1. Filtro geométrico de poses
        2. Calcular varianza de poses (9 poses existentes)
        3. Extraer features
        4. Check Applicability Domain
        5. Predecir con Modelo A y Modelo NULL
        6. Calcular Delta
        """
        from applicability_domain import ApplicabilityDomainChecker
        from feature_extractor import InteractionFeatureExtractor
        from pose_filter import PoseFilter

        # Import response models from schemas module
        from schemas import (
            DeltaResult,
            PoseVarianceResult,
            RescoreResponse,
        )

        warnings: list[str] = []

        # ── 1. Filtro geométrico de poses ────────────────────────────
        pose_filter = PoseFilter(settings)
        
        # Override grid config from request if available (multitarget support)
        if request.grid_center and request.grid_size:
            pose_filter.config.grid_center = request.grid_center
            pose_filter.config.grid_size = request.grid_size
            
        filter_results = pose_filter.filter_poses(request.poses, request.target_pdb_path)
        valid_poses = filter_results["valid_poses"]
        poses_passing = filter_results["poses_passing"]
        total_poses = len(request.poses)

        if not valid_poses:
            warnings.append(
                "Ninguna pose pasó el filtro geométrico. "
                "Usando pose de menor energía como fallback."
            )
            # Fallback: usar la pose con mejor score de Vina
            best_pose = min(request.poses, key=lambda p: p.vina_score)
            valid_poses = [best_pose]

        # ── 2. Varianza de poses (feature de incertidumbre, 0 CPU extra) ─
        vina_scores = [p.vina_score for p in request.poses]
        score_var = float(np.var(vina_scores)) if len(vina_scores) > 1 else 0.0
        score_range = float(max(vina_scores) - min(vina_scores)) if len(vina_scores) > 1 else 0.0

        if score_var < settings.pose_variance_low**2:
            stability = "ALTA"
        elif score_var > settings.pose_variance_high**2:
            stability = "BAJA"
            warnings.append(
                f"Varianza alta entre poses ({score_range:.1f} kcal/mol). "
                "El modo de unión no es único — la predicción es menos confiable."
            )
        else:
            stability = "MEDIA"

        pose_variance = PoseVarianceResult(
            score_variance=round(score_var, 4),
            score_range=round(score_range, 2),
            poses_analyzed=total_poses,
            poses_passing_filter=poses_passing,
            stability=stability,
        )

        # ── 2b. Pose selector v0.6 (opcional, aditivo) ──────────────────
        # Punto de enganche elegido: DESPUÉS del filtro de poses y ANTES de
        # la extracción de features del Model A. Motivos:
        #   (a) opera sobre TODAS las poses del request (request.poses),
        #       no sobre el subconjunto filtrado: su trabajo es rankear el
        #       set completo de poses dockeadas;
        #   (b) es independiente del pipeline Model A/NULL — sus campos en
        #       la respuesta son opcionales y su fallo jamás altera los
        #       scores existentes (try/except interno + warning);
        #   (c) comparte el costo de I/O del PDB con la extracción 3D
        #       siguiente, sin modificar ninguna variable del flujo core.
        pose_sel_result = None
        if (self.pose_selector is not None and total_poses >= 2
                and getattr(request, "target_pdb_path", "")):
            pose_sel_result = self._run_pose_selector(
                request, request.target_pdb_path
            )
            if pose_sel_result is None:
                warnings.append(
                    "Pose selector v0.6 no disponible para este complejo "
                    "(poses sin bloque PDBQT o PDB ilegible); se continúa "
                    "con el rescoring estándar."
                )

        # ── 3. Extraer features ──────────────────────────────────────
        extractor = InteractionFeatureExtractor()

        # SMILES + target alone is insufficient when docking is re-run with a
        # different pose. Include the selected pose coordinates in the key.
        pose_digest = hashlib.sha256(
            valid_poses[0].pdbqt_block.encode("utf-8")
        ).hexdigest()
        cache_key = (request.smiles, request.target_pdb_path, pose_digest)
        features_3d = self._feature_cache.get(cache_key)

        if features_3d is not None:
            log.debug("feature_cache_hit", smiles=request.smiles[:30])
        else:
            features_3d = extractor.extract_from_pose(
                valid_poses[0].pdbqt_block,
                request.target_pdb_path,
                smiles=request.smiles,
                skip_prolif=True,
            )
            if len(self._feature_cache) >= self._feature_cache_max:
                first_key = next(iter(self._feature_cache))
                del self._feature_cache[first_key]
            self._feature_cache[cache_key] = features_3d.copy()

        # Features 1D/2D (del request, pre-calculadas por backend)
        descriptors_1d2d = {
            "mw": request.molecular_weight,
            "logp": request.logp,
            "tpsa": request.tpsa,
            "hbd": float(request.hbd),
            "hba": float(request.hba),
            "rotatable_bonds": float(request.rotatable_bonds),
            "qed": request.qed,
        }

        # Agregar vina_best_score como feature
        features_3d["vina_best_score"] = valid_poses[0].vina_score

        # Features de varianza de poses
        pose_features = {
            "pose_score_variance": score_var,
            "pose_score_range": score_range,
            "poses_passing_ratio": poses_passing / total_poses if total_poses > 0 else 0.0,
        }

        # Combinar todas las features
        all_features = {**descriptors_1d2d, **features_3d, **pose_features}
        
        # Debug interacciones
        n_interactions = sum(1 for v in features_3d.values() if v > 0)
        log.debug("interaction_stats", smiles=request.smiles, n_interactions=n_interactions, interaction_sum=sum(features_3d.values()))

        log.debug("rescoring_features", smiles=request.smiles, n_features=len(all_features))
        if features_3d.get("hbond_donor_count", 0) == 0 and features_3d.get("close_contacts_4A", 0) == 0:
            log.warning("zero_3d_features_detected", smiles=request.smiles, msg="Todas las features 3D son 0. ¿Archivo PDB legible?")

        # Compute derived features needed by v4
        all_features["log_mw"] = math.log(max(request.molecular_weight, 1.0))

        # ── 4. Check Applicability Domain ────────────────────────────
        ad_checker = ApplicabilityDomainChecker(self.applicability_domain)
        ad_result = ad_checker.check(descriptors_1d2d)

        # ── 5. Predicción de Modelos e Interpolación Dinámica (Consenso) ─
        import xgboost as xgb

        # Seleccionar modelo según familia estructural del target
        # Quality gate: solo usar modelo familiar si Spearman >= 0.5 y p < 0.05
        target_family = getattr(request, 'target_family', None)
        model_used: str | None = None
        fallback_reason: str | None = None
        if target_family and target_family in self.family_models:
            fam_meta = self.family_metadata.get(target_family, {})
            fam_metrics = fam_meta.get("metrics", {})
            fam_spearman = fam_metrics.get("spearman", 0)
            fam_pval = fam_metrics.get("spearman_pval", 1.0)
            if fam_spearman >= 0.5 and fam_pval < 0.05:
                model_a_for_core = self.family_models[target_family]
                artifact_a_for_core = fam_meta
                model_used = "family"
                log.info("using_family_model", family=target_family, spearman=fam_spearman)
            else:
                model_a_for_core = self.model_a
                artifact_a_for_core = self.model_a_artifact
                model_used = "universal"
                fallback_reason = (
                    f"Familia '{target_family}' sin modelo validado "
                    f"(quality gate: Spearman {fam_spearman:.3f} < 0.5 "
                    f"o p {fam_pval:.3g} >= 0.05) — modelo universal usado."
                )
                log.info("family_model_fallback_universal",
                         family=target_family, family_spearman=fam_spearman,
                         family_pval=fam_pval)
        else:
            model_a_for_core = self.model_a
            artifact_a_for_core = self.model_a_artifact
            if target_family:
                model_used = "universal"
                fallback_reason = (
                    f"Familia '{target_family}' sin modelo entrenado "
                    f"disponible — modelo universal usado."
                )
            else:
                # Sin concepto de familia: el modelo universal ES el default
                # (no es un fallback, no hay motivo que reportar).
                model_used = "universal"

        # Cargar predicción de Modelo A (Core).
        # [A2/A3] Contract-safe: si la imputación es imposible, el score se
        # marca NaN (no disponible) — el engine re-normaliza o degrada; jamás
        # se fabrica 0.0 / 0.5.
        context = getattr(request, "smiles", "") or ""
        features_a, contract_msg = self._contract_safe_vector(
            all_features, "A", context=context
        )
        feature_names_a = artifact_a_for_core.get("feature_names", [])
        if features_a is None:
            warnings.append(
                f"⚠️ Violación de contrato de features (Model A). "
                f"Score no disponible: {contract_msg}"
            )
            score_a_core = float("nan")
        else:
            dm_a = xgb.DMatrix(features_a.reshape(1, -1), feature_names=feature_names_a)
            score_a_core = float(model_a_for_core.predict(dm_a)[0])
            if np.isnan(score_a_core) or np.isinf(score_a_core):
                log.error("nan_inf_score_a_core", score=score_a_core, context=context)
                warnings.append(
                    "⚠️ Modelo A Core produjo NaN/Inf. "
                    "Score marcado como no disponible (sin reemplazo fabricado)."
                )

        # Delta-learning: si el modelo predice delta (pKi - Vina_pKi), reconstruir pKi
        is_delta = artifact_a_for_core.get("params", {}).get("is_delta_model", False)
        if is_delta:
            vina_pKi = -all_features.get("vina_best_score", 0.0) / 1.36
            score_a_core = vina_pKi + score_a_core
            log.debug("delta_model_reconstruction", vina_pKi=round(vina_pKi, 3),
                      delta=round(score_a_core - vina_pKi, 4), final=round(score_a_core, 4))

        score_a = score_a_core

        # ── Dominio de aplicabilidad: score core + advertencia honesta ──
        # [F-19] El modelo Extended fue retirado (2026-08-13): era byte-idéntico
        # al legacy de 176 features (167 + 9 ProLIF) rechazado por el contrato
        # A2. Las moléculas fuera de dominio se puntúan con el modelo CORE
        # (universal, o de familia si pasó el quality gate) y reciben la
        # advertencia honesta de baja confianza — sin interpolación.
        dist = ad_result.mahalanobis_distance
        core_threshold = ad_result.threshold if ad_result.threshold is not None else 16.2

        if dist > core_threshold:
            warnings.append(
                f"⚠️ XGBOOST FUERA DEL DOMINIO DE APLICABILIDAD. "
                f"Distancia de Mahalanobis: {dist:.1f} (umbral: {core_threshold:.1f}). "
                f"Aunque la confianza es baja, el modelo proveerá valores explicativos con fines de auditoría científica."
            )

        # Modelo NULL: solo features 1D/2D (sin info 3D ni Vina)
        # [A2] Solo se pasan claves REALMENTE presentes (sin relleno 0.0);
        # _prepare_feature_vector imputa con media o excluye explícitamente.
        null_names = self.model_null_artifact.get("feature_names", [])
        null_features_dict = {
            k: all_features[k] for k in null_names if k in all_features
        }
        features_null, contract_msg_null = self._contract_safe_vector(
            null_features_dict, "NULL", context=context
        )
        feature_names_null = null_names
        if features_null is None:
            warnings.append(
                f"⚠️ Violación de contrato de features (Model NULL). "
                f"Delta de especificidad no disponible: {contract_msg_null}"
            )
            score_null = float("nan")
        else:
            dm_null = xgb.DMatrix(features_null.reshape(1, -1), feature_names=feature_names_null)
            score_null = float(self.model_null.predict(dm_null)[0])
            if np.isnan(score_null) or np.isinf(score_null):
                log.error("nan_inf_score_null", score=score_null, context=context)
                warnings.append(
                    "⚠️ Modelo NULL produjo NaN/Inf. "
                    "Delta de especificidad marcado como no disponible."
                )

        # ── 6. Delta de Especificidad 3D ─────────────────────────────
        delta_val = score_a - score_null

        # [FIX] Usar thresholds entrenados del delta_distribution si están disponibles,
        # con fallback a los valores hardcodeados de config.
        if self.delta_distribution and "semaphore_thresholds" in self.delta_distribution:
            st = self.delta_distribution["semaphore_thresholds"]
            green_threshold = st.get("green_above", settings.delta_green_threshold)
            red_threshold = st.get("red_below", settings.delta_red_threshold)
        else:
            green_threshold = settings.delta_green_threshold
            red_threshold = settings.delta_red_threshold

        if delta_val > green_threshold:
            semaphore = "GREEN"
            interpretation = (
                f"ENCAJE ESPECÍFICO (Δ = {delta_val:+.2f}). "
                "La molécula tiene interacciones específicas con el receptor "
                "más allá de sus propiedades fisicoquímicas."
            )
        elif delta_val < red_threshold:
            semaphore = "RED"
            interpretation = (
                f"INCOMPATIBILIDAD GEOMÉTRICA (Δ = {delta_val:+.2f}). "
                "La geometría 3D es incompatible con el bolsillo del receptor. "
                "Las propiedades fisicoquímicas son favorables pero la forma impide buen encaje."
            )
        else:
            semaphore = "YELLOW"
            interpretation = (
                f"UNIÓN INESPECÍFICA (Δ = {delta_val:+.2f}). "
                "El score depende principalmente de propiedades fisicoquímicas genéricas. "
                "Riesgo de promiscuidad y off-targets."
            )

        # ── 7. SHAP (XAI) ─────────────────────────────────────────────
        # [A2] Solo si el vector de features del Model A pasó el contrato.
        top_shap = None
        if features_a is not None and feature_names_a:
            try:
                # SHAP nativo de XGBoost (pred_contribs=True) evita incompatibilidades entre librerías
                shap_contribs = model_a_for_core.predict(dm_a, pred_contribs=True)[0]
                shap_vals = shap_contribs[:-1]  # El último elemento es el bias (base_score)

                shap_dict = {feat: float(val) for feat, val in zip(feature_names_a, shap_vals) if abs(val) > 0.0001}
                # Top 10 features by absolute contribution
                top_shap = dict(sorted(shap_dict.items(), key=lambda item: abs(item[1]), reverse=True)[:10])
            except Exception as e:
                import traceback
                log.warning("shap_calculation_failed", error=str(e), traceback=traceback.format_exc())
                top_shap = None

        delta = DeltaResult(
            delta=round(delta_val, 4),
            semaphore=semaphore,
            interpretation=interpretation,
        )

        # ── 8. Classifier: binder probability ──────────────────────────
        classifier_prob = None
        if self.classifier_binder is not None and self.classifier_metadata is not None:
            try:
                clf_features = self.classifier_metadata.get("feature_names", [])
                if clf_features:
                    # [A2] Misma regla de contrato: imputación por media o
                    # exclusión explícita, nunca 0.0.
                    clf_missing = [
                        f for f in clf_features
                        if f not in all_features
                        or not math.isfinite(float(all_features[f]))
                    ]
                    clf_imputable = [f for f in clf_missing if f in self._feature_means]
                    clf_unimputable = [f for f in clf_missing if f not in self._feature_means]
                    if clf_unimputable:
                        log.warning(
                            "clf_feature_contract_violation",
                            n=len(clf_unimputable),
                            names=clf_unimputable[:20],
                            context=context or None,
                        )
                    else:
                        if clf_imputable:
                            log.info(
                                "clf_feature_imputation",
                                n=len(clf_imputable),
                                names=clf_imputable[:20],
                                context=context or None,
                            )
                        clf_vec = np.array([
                            all_features.get(fn, self._feature_means.get(fn, 0.0))
                            for fn in clf_features
                        ]).reshape(1, -1)
                        clf_dm = xgb.DMatrix(clf_vec, feature_names=clf_features)
                        classifier_prob = float(self.classifier_binder.predict(clf_dm)[0])
            except Exception as e:
                classifier_prob = None
                log.warning("clf_predict_failed", error=str(e)[:200], context=context or None)

        return RescoreResponse(
            score_a=round(score_a, 4),
            score_null=round(score_null, 4),
            gnn_score=None,
            delta=delta,
            applicability_domain=ad_result,
            pose_variance=pose_variance,
            features_used=all_features,
            model_version=self._model_version or "unknown",
            inference_time_ms=0.0,  # se sobreescribe en app.py
            warnings=warnings,
            shap_values=top_shap,
            classifier_prob=round(classifier_prob, 4) if classifier_prob is not None else None,
            model_used=model_used,
            fallback_reason=fallback_reason,
            pose_scores=(
                pose_sel_result["pose_scores"] if pose_sel_result else None
            ),
            selected_pose_rank=(
                pose_sel_result["selected_pose_rank"] if pose_sel_result else None
            ),
            pose_confidence=(
                pose_sel_result["pose_confidence"] if pose_sel_result else None
            ),
            pose_abstained=(
                pose_sel_result["pose_abstained"] if pose_sel_result else None
            ),
            pose_selector_model=(
                pose_sel_result["pose_selector_model"] if pose_sel_result else None
            ),
        )

    def _run_pose_selector(self, request, target_pdb_path: str) -> dict | None:
        """Ejecuta el selector v0.6 sobre las poses del request.

        Devuelve el dict del selector (pose_scores, selected_pose_rank,
        pose_confidence, pose_abstained, pose_selector_model) o None si no
        aplica o degrada. NUNCA lanza: todo fallo se reporta en el log y
        devuelve None para que predict() continúe intacto."""
        if self.pose_selector is None:
            return None
        try:
            poses = getattr(request, "poses", None) or []
            if len(poses) < 2:
                return None
            bloques: list[str] = []
            vinas: list[float] = []
            for p in poses:
                bloque = getattr(p, "pdbqt_block", "") or ""
                if not bloque.strip():
                    log.warning(
                        "pose_selector_missing_block",
                        msg="pose sin pdbqt_block; selector no aplica",
                    )
                    return None
                bloques.append(bloque)
                vinas.append(float(p.vina_score))
            resultado, motivo = self.pose_selector.seleccionar_pose(
                bloques, vinas, str(target_pdb_path)
            )
            if resultado is None:
                log.warning("pose_selector_degraded", motivo=motivo)
                return None
            if resultado.get("warnings"):
                for w in resultado["warnings"]:
                    log.warning("pose_selector_warning", detalle=w)
            return resultado
        except Exception as e:
            log.warning("pose_selector_run_failed", error=str(e))
            return None

    def predict_null(self, request) -> tuple[float, bool]:
        """
        Predicción rápida usando solo Modelo NULL (features 1D/2D).
        """
        import xgboost as xgb
        from applicability_domain import ApplicabilityDomainChecker

        descriptors_1d2d = {
            "mw": request.molecular_weight,
            "logp": request.logp,
            "tpsa": request.tpsa,
            "hbd": float(request.hbd),
            "hba": float(request.hba),
            "rotatable_bonds": float(request.rotatable_bonds),
            "qed": request.qed,
        }

        # Check domain
        ad_checker = ApplicabilityDomainChecker(self.applicability_domain)
        ad_result = ad_checker.check(descriptors_1d2d)

        # [A2] Solo claves presentes (sin relleno 0.0); imputación por media o
        # exclusión explícita en _prepare_feature_vector.
        null_names = self.model_null_artifact.get("feature_names", [])
        null_features_dict = {
            k: descriptors_1d2d[k] for k in null_names if k in descriptors_1d2d
        }

        # Derived features
        if "log_mw" in null_names:
            null_features_dict["log_mw"] = math.log(max(request.molecular_weight, 1.0))

        features_null, contract_msg_null = self._contract_safe_vector(
            null_features_dict, "NULL", context=getattr(request, "smiles", "")
        )
        if features_null is None:
            log.warning(
                "predict_null_contract_violation",
                error=contract_msg_null,
                context=getattr(request, "smiles", ""),
            )
            return float("nan"), False

        feature_names_null = null_names
        dm_null = xgb.DMatrix(features_null.reshape(1, -1), feature_names=feature_names_null)

        score_null = float(self.model_null.predict(dm_null)[0])
        if np.isnan(score_null) or np.isinf(score_null):
            log.error("nan_inf_score_null_predict_null", score=score_null)
            # [A3] NaN explícito (no disponible), sin reemplazo fabricado.

        return score_null, ad_result.in_domain

    def predict_batch(self, requests: list) -> list[dict[str, Any]]:
        """
        Prediccion vectorizada para multiples moleculas (v1.3).
        """
        import xgboost as xgb
        from feature_extractor import InteractionFeatureExtractor

        extractor = InteractionFeatureExtractor()
        n = len(requests)

        # ── Extraer features de todas las moleculas ──────────────
        all_features_list = []

        for req in requests:
            # Normalizar request — acepta pydantic objects y dicts
            def _v(obj, attr, default=None):
                val = getattr(obj, attr, None)
                if val is not None:
                    return val
                if isinstance(obj, dict):
                    return obj.get(attr, default)
                return default

            mw = float(_v(req, "molecular_weight", 300))
            features_3d = {}

            # Best pose — extraer features if possible
            poses_raw = _v(req, "poses", [])
            if poses_raw:
                p0 = poses_raw[0]
                best_vina = float(_v(p0, "vina_score", 0.0))
                best_pdbqt = _v(p0, "pdbqt_block", "")
                target_pdb = _v(req, "target_pdb_path", "")
                smiles = _v(req, "smiles", "")
                if best_pdbqt and target_pdb:
                    features_3d = extractor.extract_from_pose(
                        best_pdbqt, target_pdb, smiles=smiles, skip_prolif=True,
                    )
                features_3d["vina_best_score"] = best_vina

            # Combine all features
            all_feats = {
                "mw": mw,
                "logp": float(_v(req, "logp", 3.0)),
                "tpsa": float(_v(req, "tpsa", 60.0)),
                "hbd": float(_v(req, "hbd", 0)),
                "hba": float(_v(req, "hba", 0)),
                "rotatable_bonds": float(_v(req, "rotatable_bonds", 0)),
                "qed": float(_v(req, "qed", 0.5)),
                **features_3d,
            }
            all_feats["log_mw"] = math.log(max(mw, 1.0))
            all_feats["pose_score_variance"] = 0.0
            all_feats["pose_score_range"] = 0.0
            all_feats["poses_passing_ratio"] = 0.0
            all_feats["smiles"] = str(smiles) if smiles else ""
            all_features_list.append(all_feats)

        # ── Construir DMatrix vectorizada ────────────────────────
        # v1.3: Usar los feature_names del modelo serializado (176 features).
        # Despues del retrain con 167 features (Fase 0), esto coincidira
        # con ALL_FEATURES y no habra padding.
        feature_names = list(self.model_a_artifact.get("feature_names", [])) if self.model_a_artifact else []
        if not feature_names:
            return [{"score_a": 0.0, "score_null": 0.0, "classifier_prob": None}] * n

        n_features = len(feature_names)

        # [A2] Sin zero-padding: features faltantes/no finitas → imputación por
        # media de entrenamiento; si no es imputable → fila excluida (NaN) con
        # log + identificador (smiles).
        excluded_rows: list[int] = []
        matrix = np.zeros((n, n_features), dtype=np.float64)
        for i, feats in enumerate(all_features_list):
            row_problem = [
                f for f in feature_names
                if f not in feats or not math.isfinite(float(feats[f]))
            ]
            unimputable = [f for f in row_problem if f not in self._feature_means]
            if unimputable:
                excluded_rows.append(i)
                log.warning(
                    "batch_feature_contract_violation",
                    row=i,
                    n=len(unimputable),
                    names=unimputable[:20],
                    smiles=all_features_list[i].get("smiles", ""),
                )
                continue
            for j, fn in enumerate(feature_names):
                val = feats.get(fn)
                if val is None or not math.isfinite(float(val)):
                    matrix[i, j] = self._feature_means.get(fn, 0.0)
                else:
                    matrix[i, j] = float(val)

        dm = xgb.DMatrix(matrix, feature_names=feature_names)

        # ── Predecir ────────────────────────────────────────────
        scores_a = self.model_a.predict(dm)
        scores_null = self.model_null.predict(dm) if self.model_null else np.zeros(n)

        # ── Classifier ───────────────────────────────────────────
        clf_probs = [None] * n
        if self.classifier_binder is not None and self.classifier_metadata is not None:
            clf_feature_names = self.classifier_metadata.get("feature_names", [])
            if clf_feature_names:
                clf_matrix = np.zeros((n, len(clf_feature_names)), dtype=np.float64)
                for i, feats in enumerate(all_features_list):
                    for j, fn in enumerate(clf_feature_names):
                        val = feats.get(fn)
                        if val is None or not math.isfinite(float(val)):
                            clf_matrix[i, j] = self._feature_means.get(fn, 0.0)
                        else:
                            clf_matrix[i, j] = float(val)
                clf_dm = xgb.DMatrix(clf_matrix, feature_names=clf_feature_names)
                clf_raw = self.classifier_binder.predict(clf_dm)
                clf_probs = [round(float(p), 4) for p in clf_raw]

        # ── Construir resultados ─────────────────────────────────
        results = []
        for i in range(n):
            if i in excluded_rows:
                # [A3] Exclusión explícita: NaN en vez de un score fabricado.
                results.append({
                    "score_a": float("nan"),
                    "score_null": float("nan"),
                    "classifier_prob": None,
                    "delta": float("nan"),
                    "excluded": True,
                })
                continue
            score_a = float(scores_a[i]) if i < len(scores_a) else 0.0
            score_null = float(scores_null[i]) if i < len(scores_null) else 0.0
            # [A3] NaN/Inf de predicción se propagan como NaN (no 0.0)
            if np.isnan(score_a) or np.isinf(score_a):
                log.warning("batch_nan_score_a", row=i, smiles=all_features_list[i].get("smiles", ""))
            results.append({
                "score_a": round(score_a, 4),
                "score_null": round(score_null, 4),
                "classifier_prob": clf_probs[i],
                "delta": round(score_a - score_null, 4),
                "excluded": False,
            })
        return results

    def _contract_safe_vector(
        self, features: dict[str, float], model: str, context: str = ""
    ) -> tuple[np.ndarray | None, str | None]:
        """[A2] Envuelve _prepare_feature_vector para rutas no críticas.

        Returns (vector, warning_msg). Si la imputación no es posible →
        (None, warning explícito) para que el caller degrade SIN fabricar.
        """
        try:
            return self._prepare_feature_vector(features, model, context=context), None
        except FeatureContractViolation as e:
            return None, str(e)

    def _prepare_feature_vector(
        self, features: dict[str, float], model: str, context: str = ""
    ) -> np.ndarray:
        """
        Convertir dict de features a vector numpy en el orden esperado por el modelo.

        Uses the feature_names stored in the model artifact (saved during training).
        Each model stores its own feature list so ordering is guaranteed to match.

        [A2] Contrato de features — sin zero-padding silencioso:
          - Feature faltante o no finita → se imputa con la media de
            entrenamiento (applicability_domain) SI está disponible, y se
            registra el evento en el log.
          - Feature faltante SIN media disponible (imputación imposible) →
            excepción FeatureContractViolation. El caller excluye la molécula
            de forma explícita; jamás se fabrica un valor (0.0 / 0.5).
        """
        if model == "A":
            artifact = self.model_a_artifact
        elif model == "NULL":
            artifact = self.model_null_artifact
        else:
            # [F-19] "A_extended" dejó de existir: nombres desconocidos se
            # rechazan en vez de caer silenciosamente al artifact NULL.
            raise ValueError(
                f"Modelo desconocido: '{model}'. Válidos: 'A' (core/universal) "
                "y 'NULL' (ablación 1D/2D)."
            )

        if artifact and "feature_names" in artifact:
            feature_order = artifact["feature_names"]
        elif self.training_report and f"feature_order_{model.lower()}" in self.training_report:
            feature_order = self.training_report[f"feature_order_{model.lower()}"]
        else:
            raise ValueError(
                f"No se encontró feature_order para el modelo '{model}'. "
                "El artefacto del modelo no contiene 'feature_names' ni hay training_report. "
                "Re-entrene el modelo o verifique los artefactos en artifacts/."
            )

        missing = [f for f in feature_order if f not in features or features[f] is None]
        non_finite = [
            f for f in feature_order
            if f in features and features[f] is not None
            and not math.isfinite(float(features[f]))
        ]
        problem = missing + non_finite

        imputable = [f for f in problem if f in self._feature_means]
        unimputable = [f for f in problem if f not in self._feature_means]

        if imputable:
            log.info(
                "feature_imputation",
                model=model,
                n=len(imputable),
                names=imputable[:20],
                context=context or None,
            )
        if unimputable:
            log.error(
                "feature_contract_violation",
                model=model,
                n=len(unimputable),
                names=unimputable[:20],
                context=context or None,
            )
            raise FeatureContractViolation(unimputable, context=context)

        vector = []
        for feat_name in feature_order:
            val = features.get(feat_name, None)
            if val is None or not math.isfinite(float(val)):
                vector.append(self._feature_means[feat_name])
            else:
                vector.append(float(val))

        return np.array(vector, dtype=np.float64)
