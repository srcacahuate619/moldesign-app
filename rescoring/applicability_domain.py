"""
rescoring/applicability_domain.py

Verificación de Applicability Domain con distancia de Mahalanobis.

Origen: Banca / Basilea III (Population Stability Index).
Adaptado a cheminformatics: detectar automáticamente moléculas fuera del
dominio de entrenamiento del modelo ANTES de predecir.

Lógica:
  1. Calcular distancia de Mahalanobis de la molécula al centroide del training set
  2. Comparar con umbral (percentil 99 de distancias en training set)
  3. Si distancia > umbral → molécula fuera de dominio → NO predecir con ML

Artefacto requerido: artifacts/applicability_domain.json
  {
    "mean": [...],           # media de cada descriptor en training set
    "cov_inv": [[...],...],  # inversa de la matriz de covarianza
    "threshold": 8.7,        # percentil 99 de distancias de Mahalanobis en training
    "feature_names": [...],  # nombres de los descriptores usados
    "feature_ranges": {      # rangos observados por descriptor (para reportar al usuario)
      "mw": {"min": 150, "max": 750},
      "logp": {"min": -2.0, "max": 6.0},
      ...
    }
  }

Este artefacto se genera en Fase 2 de entrenamiento.
En Fase 1 (sin artefacto), el check es permisivo (todo pasa).

Referencia:
  - Sahlin U. "The Applicability Domain in QSAR Modeling." QSAR & Comb Sci, 2008.
  - Yurdakul B. "Statistical Properties of Population Stability Index." WMU, 2018.
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

    Si no hay artefacto cargado (Fase 1), es permisivo: todo pasa.
    Si hay artefacto (post-Fase 2), verifica contra el training set.
    """

    def __init__(self, ad_data: dict[str, Any] | None = None):
        """
        Args:
            ad_data: dict with keys 'mean', 'cov_inv', 'threshold', 'feature_names', 'feature_ranges'
                     o None si no hay artefacto (modo permisivo)
        """
        self._loaded = ad_data is not None
        self._mean = ad_data["mean"] if ad_data else None
        self._cov_inv = ad_data["cov_inv"] if ad_data else None
        self._threshold = ad_data["threshold"] if ad_data else 0.0
        self._feature_ranges = ad_data.get("feature_ranges", {}) if ad_data else {}

        # [A2] El artefacto applicability_domain.json tiene 172 feature_names
        # (167 contrato - 4 pose features siempre presentes + 9 interacciones
        # ProLIF). _align_feature_names subsetea a AD_DESCRIPTORS para la
        # distancia (legacy): la inferencia siempre provee esos 8 descriptores.
        # En check() un descriptor ausente NO se pone en 0.0: la molécula
        # queda FUERA de dominio (conservador, sin fabricación).
        artifact_names = ad_data.get("feature_names", AD_DESCRIPTORS) if ad_data else AD_DESCRIPTORS
        self._feature_names = self._align_feature_names(artifact_names)

    def _align_feature_names(self, artifact_names: list[str]) -> list[str]:
        """Subsetea el artefacto para usar solo AD_DESCRIPTORS si el artefacto fue
        construido con más features de las que tenemos en inferencia."""
        if len(artifact_names) <= len(AD_DESCRIPTORS) or not self._loaded:
            return artifact_names

        # Encontrar los indices de AD_DESCRIPTORS dentro del artefacto
        common = [i for i, name in enumerate(artifact_names) if name in AD_DESCRIPTORS]
        if len(common) < 3:
            # Si no hay suficientes matches, no podemos subsetear de forma confiable
            log.warning(
                "ad_feature_mismatch",
                msg=f"Solo {len(common)} de {len(AD_DESCRIPTORS)} AD_DESCRIPTORS "
                    f"encontrados en el artefacto ({len(artifact_names)} features). "
                    "Usando las primeras features del artefacto como fallback."
            )
            return artifact_names[: len(AD_DESCRIPTORS)]

        # Subsetear mean, cov_inv y feature_ranges
        mean_arr = np.array(self._mean)
        cov_inv_arr = np.array(self._cov_inv)
        self._mean = mean_arr[common].tolist()
        self._cov_inv = cov_inv_arr[np.ix_(common, common)].tolist()
        self._feature_ranges = {
            name: self._feature_ranges[name]
            for name in artifact_names
            if name in self._feature_ranges and name in AD_DESCRIPTORS
        }
        return AD_DESCRIPTORS

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
            # Sin artefacto → modo permisivo (Fase 1)
            log.debug(
                "ad_check_permissive",
                msg="Sin artefacto de Applicability Domain. Modo permisivo (Fase 1).",
            )
            return ApplicabilityDomainResult(
                in_domain=True,
                mahalanobis_distance=0.0,
                threshold=0.0,
                out_of_range_descriptors=[],
            )

        # Construir vector de descriptores en el orden correcto.
        # [A3] SIN zero-padding (era descriptors.get(feat, 0.0)): un descriptor
        # ausente significa que la molécula no puede verificarse → fuera de
        # dominio (conservador, igual que el fallo de cálculo de Mahalanobis).
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
                in_domain=False,
                mahalanobis_distance=float("inf"),
                threshold=self._threshold,
                out_of_range_descriptors=[
                    f"{f} (ausente)" for f in missing_feats
                ],
            )
        mol_vector = np.array(mol_vector, dtype=float)

        # Calcular distancia de Mahalanobis
        try:
            distance = mahalanobis(mol_vector, self._mean, self._cov_inv)
        except Exception as e:
            log.error("mahalanobis_error", error=str(e))
            # Si falla el cálculo, ser conservador → fuera de dominio
            return ApplicabilityDomainResult(
                in_domain=False,
                mahalanobis_distance=float("inf"),
                threshold=self._threshold,
                out_of_range_descriptors=["Error en cálculo de distancia"],
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
        n_samples, n_features = training_descriptors.shape

        mean = training_descriptors.mean(axis=0)
        cov = np.cov(training_descriptors.T)

        # Manejar covarianza singular (features colineales)
        try:
            cov_inv = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            log.warning(
                "ad_singular_covariance",
                msg="Covarianza singular. Usando pseudo-inversa (Moore-Penrose).",
            )
            cov_inv = np.linalg.pinv(cov)

        # Vectorized Mahalanobis distances for all training points
        # Formula: d_i = sqrt((x_i - mu)^T * Sigma^-1 * (x_i - mu))
        # Using broadcasting: diff shape (n, d), cov_inv shape (d, d)
        diff = training_descriptors - mean  # shape (n, d)
        # (n, d) @ (d, d) -> (n, d), then element-wise multiply with diff and sum
        distances = np.sqrt(np.einsum("ij,jk,ik->i", diff, cov_inv, diff)).tolist()

        threshold = float(np.percentile(distances, percentile))

        # Rangos por descriptor
        feature_ranges = {}
        for i, name in enumerate(feature_names):
            col = training_descriptors[:, i]
            feature_ranges[name] = {
                "min": round(float(col.min()), 4),
                "max": round(float(col.max()), 4),
                "mean": round(float(col.mean()), 4),
                "std": round(float(col.std()), 4),
            }

        artifact = {
            "mean": mean.tolist(),
            "cov_inv": cov_inv.tolist(),
            "threshold": round(threshold, 4),
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
