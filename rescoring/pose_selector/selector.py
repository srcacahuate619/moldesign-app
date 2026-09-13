# -*- coding: utf-8 -*-
"""
rescoring/pose_selector/selector.py — PoseSelector v0.6 (Ruta C, Fase 4).

Port de produccion de scripts/ruta_c_fase3_calibracion.py::puntuar_complejo:
  1. 224 features raw por pose (extractor v0.5, ver feature_extractor.py).
  2. features de conjunto: pose_score_variance/range sobre las N poses del
     request (semantica v0.5: varianza/rango dentro del MISMO run de
     docking) y cluster_density intra-complejo (pares de poses con RMSD
     pocket-frame < 2.0 A sin alinear, umbral UMBRAL_CLUSTER del dataset
     builder).
  3. Transformacion por complejo: z-score por columna (std == 0 -> z = 0)
     + rango percentil 0-100 (empates -> rango promedio) de las 9 features
     de orden_pct (complejo de 1 pose -> 50.0). NaN -> 0 despues de
     transformar. Matriz final (N, 233).
  4. Predict del booster v0.6 (52 arboles, early stopping) y margen de
     confianza top1 - top2 con regla de abstencion t = 0.097663 (punto de
     operacion de Fase 3).

Degradacion: cualquier fallo devuelve (None, motivo) — el caller NUNCA debe
romper su flujo por este modulo. cluster_density se degrada a 0 con un
warning si los seriales de los bloques no se alinean entre poses.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from pose_selector.feature_extractor import (
    FEATURES_TOTAL,
    coords_por_serial,
    extraer_features_224,
)

# Punto de operacion de Fase 3 (barrido sobre val, regla pre-registrada).
UMBRAL_ABSTENCION_DEFECTO = 0.097663
UMBRAL_CLUSTER = 2.0  # A — vecino de cluster (dataset builder)
NOMBRE_MODELO = "pose_selector_v06"


def _z_por_complejo(X: np.ndarray) -> np.ndarray:
    """Z-score por columna dentro del complejo (filas contiguas).
    std == 0 -> z = 0. NaN permanece NaN (se rellena a 0 despues).
    Copia exacta de la transformacion de Fase 1.6 (uso de produccion)."""
    Z = np.full_like(X, np.nan, dtype=np.float64)
    cols = X
    m = np.nanmean(cols, axis=0)
    s = np.nanstd(cols, axis=0)
    z = np.zeros_like(cols)
    ok = s > 0
    z[:, ok] = (cols[:, ok] - m[ok]) / s[ok]
    z[np.isnan(cols)] = np.nan
    Z[:] = z
    return Z


def _pct_por_complejo(X: np.ndarray, indices: list[int]) -> np.ndarray:
    """Rango percentil 0-100 por complejo (empates -> rango promedio)
    para las columnas indicadas. Complejo de 1 pose -> 50.0.
    Copia exacta de la transformacion de Fase 1.6 (uso de produccion)."""
    from scipy.stats import rankdata
    n = X.shape[0]
    P = np.full((n, len(indices)), np.nan, dtype=np.float64)
    for j, col in enumerate(indices):
        x = X[:, col]
        if n == 1:
            P[:, j] = 50.0
            continue
        r = rankdata(x)
        P[:, j] = 100.0 * (r - 1.0) / (n - 1.0)
    return P


def _cluster_density_por_serials(bloques: list[str]) -> tuple:
    """Densidad de cluster intra-complejo (pares pose-pose con RMSD
    pocket-frame < 2.0 A, sin alinear) con correspondencia de atomos por
    SERIAL de los bloques PDBQT. Devuelve (densidades, warning):
      densidades: np.ndarray (N,) — cuenta de vecinos por pose.
      warning: str | None — si los seriales no se alinean entre bloques se
        degrada todo a 0 y se reporta el motivo."""
    mapas = [coords_por_serial(b) for b in bloques]
    comun = None
    for m in mapas:
        if not m:
            return np.zeros(len(bloques), dtype=np.float64), \
                "pose sin atomos pesados para cluster_density"
        if comun is None:
            comun = set(m.keys())
        else:
            comun &= set(m.keys())
    for i, m in enumerate(mapas):
        if set(m.keys()) != comun:
            return np.zeros(len(bloques), dtype=np.float64), \
                ("seriales de atomos no alineados entre bloques "
                 f"(bloque {i}); cluster_density degradada a 0")
    orden = sorted(comun)
    if not orden:
        return np.zeros(len(bloques), dtype=np.float64), \
            "sin seriales comunes entre poses; cluster_density degradada a 0"
    coords = np.array([[m[s] for s in orden] for m in mapas],
                      dtype=np.float64)
    n = len(bloques)
    dens = np.zeros(n, dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            dd = float(np.sqrt(np.mean((coords[i] - coords[j]) ** 2)))
            if dd < UMBRAL_CLUSTER:
                dens[i] += 1
                dens[j] += 1
    return dens, None


class PoseSelector:
    """Selector de la pose tipo-cristal v0.6 (XGBRanker de produccion)."""

    def __init__(self, model_path: str, meta_path: str,
                 abstention_threshold: float = UMBRAL_ABSTENCION_DEFECTO):
        """Carga el booster y la meta de produccion.

        La carga es TOLERANTE: si el modelo o la meta faltan o son
        invalidos, el error queda en self.load_error (str) y el booster en
        None — seleccionar_pose() degrada a (None, motivo) en ese caso.
        El sidecar asi nunca se cae por un artefacto roto.
        """
        import xgboost

        self.model_path = str(model_path)
        self.meta_path = str(meta_path)
        self.abstention_threshold = float(abstention_threshold)
        self.load_error: str | None = None
        self.booster = None
        self.meta: dict = {}
        self.nombres_233: list[str] = []
        self.nombres_224: list[str] = []
        self.orden_pct: list[str] = []
        self.indices_pct: list[int] = []
        self.nombre_modelo = NOMBRE_MODELO

        try:
            booster = xgboost.Booster()
            booster.load_model(self.model_path)
            with open(self.meta_path, encoding="utf-8") as fh:
                self.meta = json.load(fh)

            self.nombres_233 = list(self.meta.get("feature_names_233", []))
            self.nombres_224 = list(self.meta.get("feature_names_raw_224", []))
            self.orden_pct = list(self.meta.get("orden_pct", []))
            if len(self.nombres_224) != len(FEATURES_TOTAL):
                raise ValueError(
                    f"meta del pose selector con {len(self.nombres_224)} "
                    f"features raw (se esperaban {len(FEATURES_TOTAL)})")
            if self.nombres_224 != list(FEATURES_TOTAL):
                raise ValueError(
                    "el orden de features raw de la meta no coincide con el "
                    "contrato FEATURES_TOTAL del extractor")
            self.indices_pct = [self.nombres_224.index(f) for f in self.orden_pct]
            if len(self.indices_pct) != 9:
                raise ValueError(
                    f"orden_pct con {len(self.indices_pct)} features "
                    "(se esperaban 9)")
            self.booster = booster
            self.nombre_modelo = str(self.meta.get("modelo", NOMBRE_MODELO))
        except Exception as e:
            self.load_error = (
                f"pose_selector_load_failed: {type(e).__name__}: {e}"
            )
            self.booster = None

    # ───────────────────────── seleccion de pose ─────────────────────────

    def seleccionar_pose(self, pose_blocks: list[str],
                         vina_scores: list[float],
                         target_pdb_path: str):
        """Selecciona la pose tipo-cristal de un complejo.

        Args:
            pose_blocks: N bloques PDBQT (una pose por bloque).
            vina_scores: N scores de Vina en el mismo orden.
            target_pdb_path: ruta al PDB de la proteina.

        Returns:
            (resultado, motivo):
              resultado: dict con pose_scores (N), selected_pose_rank
                (0-based), pose_confidence (margen top1 - top2; 0 si N==1),
                pose_abstained (margen < umbral; True si N==1),
                pose_selector_model, warnings (list).
              motivo: str — cadena vacia si todo OK.
            En cualquier fallo: (None, motivo_con_explicacion). El caller
            debe degradar con elegancia, nunca romper su flujo.
        """
        try:
            if self.load_error is not None or self.booster is None:
                return None, (self.load_error or "modelo no cargado")
            n = len(pose_blocks)
            if n == 0:
                return None, "sin poses de entrada"
            if len(vina_scores) != n:
                return None, (f"{len(vina_scores)} scores para {n} poses "
                              "(las listas deben coincidir)")

            feats_ok: list[np.ndarray] = []
            warnings: list[str] = []
            for i, bloque in enumerate(pose_blocks):
                feats, valido = extraer_features_224(bloque, target_pdb_path)
                if not valido:
                    return None, (f"pose {i} ilegible o PDB no disponible "
                                  f"({target_pdb_path})")
                feats_ok.append(np.asarray(feats, dtype=np.float64))

            X = np.vstack(feats_ok)
            assert X.shape == (n, len(FEATURES_TOTAL))

            # ── features de conjunto (v0.5 semantics) ──
            vinas = np.array([float(v) for v in vina_scores],
                             dtype=np.float64)
            if n > 1:
                # round(..., 4): contrato del dataset builder (los valores
                # congelados se guardaron redondeados a 4 decimales).
                var_score = round(float(np.var(vinas)), 4)
                rango_score = round(float(max(vinas) - min(vinas)), 4)
            else:
                var_score, rango_score = 0.0, 0.0
            dens, warn_cluster = _cluster_density_por_serials(pose_blocks)
            if warn_cluster:
                warnings.append(warn_cluster)
            i_var = FEATURES_TOTAL.index("pose_score_variance")
            i_rango = FEATURES_TOTAL.index("pose_score_range")
            i_cluster = FEATURES_TOTAL.index("cluster_density")
            i_vina = FEATURES_TOTAL.index("vina_score")
            X[:, i_vina] = vinas
            X[:, i_var] = var_score
            X[:, i_rango] = rango_score
            X[:, i_cluster] = dens

            # ── transformacion por complejo: z + percentiles ──
            Z = _z_por_complejo(X)
            Z[np.isnan(Z)] = 0.0
            P = _pct_por_complejo(X, self.indices_pct)
            P[np.isnan(P)] = 0.0
            X_B = np.hstack([Z, P])
            assert X_B.shape == (n, len(self.nombres_233))

            import xgboost
            scores = self.booster.predict(xgboost.DMatrix(X_B))
            scores = np.asarray(scores, dtype=np.float64)

            rank = int(np.argmax(scores))
            if n > 1:
                ordenados = np.sort(scores)[::-1]
                margen = float(ordenados[0] - ordenados[1])
            else:
                margen = 0.0
            abstained = (margen < self.abstention_threshold) if n > 1 else True

            resultado = {
                "pose_scores": [float(s) for s in scores],
                "selected_pose_rank": rank,
                "pose_confidence": margen,
                "pose_abstained": abstained,
                "pose_selector_model": self.nombre_modelo,
                "warnings": warnings,
            }
            return resultado, ""
        except Exception as e:
            import traceback
            motivo = (f"pose_selector_failed: {type(e).__name__}: {e}")
            try:
                detail = traceback.format_exc(limit=3)
            except Exception:
                detail = ""
            if detail:
                motivo += f" [{detail.strip().splitlines()[-1]}]"
            return None, motivo
