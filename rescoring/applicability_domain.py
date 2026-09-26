"""Dominio de aplicabilidad fisicoquímico 7D con Ledoit-Wolf.

El umbral combina el p99 en cinco pliegues fuera de muestra con el
referente χ² de la misma dimensión. Si falta un artefacto compatible,
el resultado es not_evaluated; nunca se presume dominio.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from logger import get_logger
from scipy.spatial.distance import mahalanobis

log = get_logger(__name__)


# Descriptores usados para el check de Applicability Domain
# Son los descriptores 1D/2D que definen el "espacio químico" del training set
AD_DESCRIPTORS = ["mw", "logp", "tpsa", "hbd", "hba", "rotatable_bonds", "qed"]


class ApplicabilityDomainChecker:
    """
    Verificador de Applicability Domain basado en distancia de Mahalanobis.

    Sin artefacto compatible devuelve no evaluado. Con un artefacto 7D
    verifica la distancia respecto al pool de entrenamiento documentado.
    """

    def __init__(self, ad_data: dict[str, Any] | None = None):
        """
        Args:
            ad_data: dict with keys 'mean', 'cov_inv', 'threshold', 'feature_names', 'feature_ranges'
                     o None si no hay artefacto (estado no evaluado)
        """
        self._unavailable_reason = None
        self._loaded = ad_data is not None
        self._feature_names = list(ad_data.get("feature_names", [])) if ad_data else []
        self._feature_ranges = ad_data.get("feature_ranges", {}) if ad_data else {}
        self._artifact_sha256 = ad_data.get("artifact_sha256") if ad_data else None
        self._mean = np.asarray(ad_data["mean"], dtype=float) if ad_data else None
        self._cov_inv = np.asarray(ad_data["cov_inv"], dtype=float) if ad_data else None
        self._threshold = ad_data.get("threshold") if ad_data else None
        if ad_data is None:
            self._unavailable_reason = "No hay artefacto de AD."
        elif self._feature_names != AD_DESCRIPTORS:
            # Un subbloque de una matriz de precisión 172D NO es la inversa
            # de la covarianza marginal 7D. Tampoco hereda su umbral 172D.
            self._loaded = False
            self._unavailable_reason = (
                "AD legacy en otro espacio de features: falta recalibración 7D "
                "sobre el pool de entrenamiento del modelo servido."
            )
        elif (self._mean.shape != (len(AD_DESCRIPTORS),)
              or self._cov_inv.shape != (len(AD_DESCRIPTORS), len(AD_DESCRIPTORS))
              or self._threshold is None
              or not np.isfinite(self._threshold)):
            self._loaded = False
            self._unavailable_reason = "Artefacto AD 7D incompleto o no finito."

    def check(self, descriptors: dict[str, float]) -> Any:
        """
        Verificar si una molécula está dentro del dominio de aplicabilidad.

        Args:
            descriptors: dict con descriptores 1D/2D de la molécula

        Returns:
            ApplicabilityDomainResult (importado de app.py)
        """
        from schemas import ApplicabilityDomainResult

        if not self._loaded:
            log.warning("ad_not_evaluated", reason=self._unavailable_reason)
            return ApplicabilityDomainResult(
                in_domain=None,
                mahalanobis_distance=None,
                threshold=None,
                status="not_evaluated",
                reason=self._unavailable_reason,
                artifact_sha256=self._artifact_sha256,
            )

        # Construir vector de descriptores en el orden correcto.
        # [A3] SIN zero-padding (era descriptors.get(feat, 0.0)): un descriptor
        # ausente significa que la molécula no puede verificarse.
        mol_vector = []
        missing_feats = []
        for feat in self._feature_names:
            val = descriptors.get(feat)
            if val is None:
                missing_feats.append(feat)
                mol_vector.append(0.0)
            else:
                mol_vector.append(val)
        if missing_feats:
            log.warning(
                "ad_missing_descriptors",
                n_missing=len(missing_feats),
                features=missing_feats,
            )
            return ApplicabilityDomainResult(
                in_domain=None,
                mahalanobis_distance=None,
                threshold=self._threshold,
                status="not_evaluated",
                reason="Descriptores ausentes: " + ", ".join(missing_feats),
                out_of_range_descriptors=[f"{f} (ausente)" for f in missing_feats],
                artifact_sha256=self._artifact_sha256,
            )
        mol_vector = np.array(mol_vector, dtype=float)

        # Calcular distancia de Mahalanobis
        try:
            distance = mahalanobis(mol_vector, self._mean, self._cov_inv)
        except Exception as e:
            log.error("mahalanobis_error", error=str(e))
            # Si falla el cálculo, el dominio queda no evaluado.
            return ApplicabilityDomainResult(
                in_domain=None,
                mahalanobis_distance=None,
                threshold=self._threshold,
                status="not_evaluated",
                reason="Error en cálculo de distancia",
                out_of_range_descriptors=["Error en cálculo de distancia"],
                artifact_sha256=self._artifact_sha256,
            )

        if not np.isfinite(distance):
            return ApplicabilityDomainResult(
                in_domain=None, mahalanobis_distance=None,
                threshold=self._threshold, status="not_evaluated",
                reason="Distancia AD no finita",
                artifact_sha256=self._artifact_sha256,
            )
        in_domain = distance <= self._threshold

        # Identificar qué descriptores están fuera de rango
        out_of_range = []
        for i, feat_name in enumerate(self._feature_names):
            if feat_name in self._feature_ranges:
                feat_range = self._feature_ranges[feat_name]
                val = mol_vector[i]
                if val < feat_range.get("min", float("-inf")) or val > feat_range.get("max", float("inf")):
                    out_of_range.append(
                        f"{feat_name}: {val:.2f} "
                        f"(rango training: {feat_range.get('min', '?')}-{feat_range.get('max', '?')})"
                    )

        if not in_domain:
            log.warning(
                "ad_out_of_domain",
                distance=round(distance, 2),
                threshold=self._threshold,
                out_of_range=out_of_range,
            )

        return ApplicabilityDomainResult(
            in_domain=in_domain,
            mahalanobis_distance=round(distance, 4),
            threshold=self._threshold,
            out_of_range_descriptors=out_of_range,
            artifact_sha256=self._artifact_sha256,
        )

    @staticmethod
    def build_from_training_data(
        training_descriptors: np.ndarray,
        feature_names: list[str],
        percentile: float = 99.0,
    ) -> dict[str, Any]:
        """
        Construir artefacto de Applicability Domain a partir del training set.

        Se usa OFFLINE durante el entrenamiento (Fase 2).
        El resultado se guarda como artifacts/applicability_domain.json.

        Args:
            training_descriptors: array (n_samples, n_features) de descriptores del training set
            feature_names: nombres de los descriptores
            percentile: percentil para el umbral (default: 99)

        Returns:
            dict serializable a JSON con mean, cov_inv, threshold, feature_names, feature_ranges
        """
        from sklearn.covariance import LedoitWolf
        from sklearn.model_selection import KFold
        from scipy.stats import chi2

        X = np.asarray(training_descriptors, dtype=float)
        n_samples, n_features = X.shape
        if len(feature_names) != n_features or len(set(feature_names)) != n_features or n_samples < 30:
            raise ValueError("AD requiere nombres únicos para cada columna y >=30 muestras")
        if not np.isfinite(X).all():
            raise ValueError("AD no admite descriptores NaN/Inf")
        full_fit = LedoitWolf().fit(X)
        mean = full_fit.location_
        cov = full_fit.covariance_
        cov_inv = np.linalg.inv(cov)

        # Cada distancia se mide con media/covarianza ajustadas SIN su fila.
        # KFold fijo hace el umbral reproducible y separa calibración de ajuste.
        distances = np.empty(n_samples, dtype=float)
        for train_idx, test_idx in KFold(n_splits=5, shuffle=True, random_state=42).split(X):
            fit = LedoitWolf().fit(X[train_idx])
            inverse = np.linalg.inv(fit.covariance_)
            diff = X[test_idx] - fit.location_
            distances[test_idx] = np.sqrt(
                np.einsum("ij,jk,ik->i", diff, inverse, diff)
            )
        oos_threshold = float(np.percentile(distances, percentile))
        gaussian_reference = float(np.sqrt(chi2.ppf(percentile / 100.0, n_features)))
        # El p99 empírico puede ser menor que el p99 de una población
        # gaussiana con la misma covarianza. El piso evita que el AD rechace
        # sistemáticamente moléculas centrales bajo ese control preregistrado.
        threshold = max(oos_threshold, gaussian_reference)

        # Rangos por descriptor
        feature_ranges = {}
        for i, name in enumerate(feature_names):
            col = X[:, i]
            feature_ranges[name] = {
                "min": round(float(col.min()), 4),
                "max": round(float(col.max()), 4),
                "mean": round(float(col.mean()), 4),
                "std": round(float(col.std()), 4),
            }

        artifact = {
            "mean": mean.tolist(),
            "cov": cov.tolist(),
            "cov_inv": cov_inv.tolist(),
            "threshold": round(threshold, 4),
            "threshold_source": (
                f"max_5fold_oos_p{percentile:g}_chi2_{n_features}_p{percentile:g}_seed42"
            ),
            "threshold_oos_p99": round(oos_threshold, 4),
            "threshold_gaussian_p99": round(gaussian_reference, 4),
            "percentile": percentile,
            "n_training_samples": n_samples,
            "n_features": n_features,
            "feature_names": feature_names,
            "feature_ranges": feature_ranges,
        }

        log.info(
            "ad_built",
            n_samples=n_samples,
            threshold=round(threshold, 4),
            percentile=percentile,
        )

        return artifact
