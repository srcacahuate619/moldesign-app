"""
valid_spearman.py — Spearman benchmark LIVIANO (CV wrapper) sobre feature_cache_v4.

Diferencia con evaluate_test_set.py (canónico):
- Este script usa feature_cache_v4/ con split="test" (validación cruzada interna).
- evaluate_test_set.py usa split_config.json frozen_test_set (327 holdout, delta-learning).
- Este es un sanity check rápido (~30s). El benchmark canónico para paper es evaluate_test_set.py.

Mejoras vs versión anterior:
- Sin cap arbitrario [:200] — usa TODAS las entradas test disponibles.
- Bootstrap 95% CI (10,000 iter) para Spearman rho y Pearson r.
- Sin clasificación binaria EXCELENTE/BUENO/... — reporte cuantitativo con CI + effect size.
- Reporta Pearson r + CI además de Spearman (más informativo para regresión).
"""
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import pearsonr, spearmanr

random.seed(42)
np.random.seed(42)

# Path absoluto al cache (relativo al raíz del repo, no al cwd del script).
# Esto permite ejecutar el script desde `rescoring/` o desde la raíz del repo.
FEATURE_CACHE = Path(__file__).resolve().parent.parent / "data" / "pdbbind" / "feature_cache_v4"
MODELS_DIR = Path(__file__).resolve().parent / "artifacts"

# ── Bootstrap CI helper ──────────────────────────────────────────────────────

def bootstrap_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_iter: int = 10_000,
    alpha: float = 0.05,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Retorna (spearman_ci_lo, spearman_ci_hi), (pearson_ci_lo, pearson_ci_hi)."""
    rng = np.random.default_rng(42)
    n = len(y_true)
    spearman_vals = np.empty(n_iter, dtype=np.float64)
    pearson_vals = np.empty(n_iter, dtype=np.float64)
    for i in range(n_iter):
        idx = rng.integers(0, n, n)
        t = y_true[idx]
        p = y_pred[idx]
        spearman_vals[i] = spearmanr(t, p).correlation
        pearson_vals[i] = pearsonr(t, p)[0]
    lo_s, hi_s = np.percentile(spearman_vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    lo_p, hi_p = np.percentile(pearson_vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return (float(lo_s), float(hi_s)), (float(lo_p), float(hi_p))


def effect_size_interpretation(rho: float) -> str:
    """Interpretación cualitativa del effect size (Cohen-like para correlación)."""
    abs_rho = abs(rho)
    if abs_rho >= 0.7:
        return "large"
    elif abs_rho >= 0.5:
        return "medium"
    elif abs_rho >= 0.3:
        return "small"
    else:
        return "negligible"


# ── Data loading ─────────────────────────────────────────────────────────────

INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "pdbbind" / "INDEX_refined_data.2020"
SPLIT_CONFIG = MODELS_DIR / "split_config.json"


def _load_pki_labels() -> dict[str, float]:
    """Carga pKi del INDEX_refined_data.2020 (formato PDBbind)."""
    labels: dict[str, float] = {}
    if not INDEX_PATH.exists():
        print(f"  [warn] INDEX no encontrado en {INDEX_PATH}")
        return labels
    with open(INDEX_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 6:
                try:
                    labels[parts[0].upper()] = float(parts[-1])
                except ValueError:
                    pass
    return labels


def _load_test_set() -> list[dict[str, Any]]:
    """Carga entries de test referenciando el cache externo + split_config."""
    entries: list[dict[str, Any]] = []
    if not FEATURE_CACHE.exists():
        print(f"[SKIP] feature_cache_v4/ no encontrada en {FEATURE_CACHE}")
        return entries

    # 1) Identificar los pdb_id del frozen_test_set
    if not SPLIT_CONFIG.exists():
        print(f"[SKIP] split_config.json no encontrado en {SPLIT_CONFIG}")
        return entries
    with open(SPLIT_CONFIG) as f:
        split_data = json.load(f)
    test_ids = [pid.upper() for pid in split_data.get("frozen_test_set", [])]
    if not test_ids:
        print("[FAIL] split_config.json sin frozen_test_set.")
        return entries

    # 2) Cargar pKi labels del INDEX
    labels = _load_pki_labels()

    # 3) Iterar cache y armar entries solo para los test_ids
    n_missing_cache = 0
    n_missing_pki = 0
    for pid in test_ids:
        cache_path = FEATURE_CACHE / f"{pid.lower()}.json"
        if not cache_path.exists():
            n_missing_cache += 1
            continue
        try:
            with open(cache_path) as f:
                data = json.load(f)
        except Exception:
            continue
        feats = data.get("features", data)
        if not isinstance(feats, dict):
            continue
        pki = labels.get(pid)
        if pki is None:
            n_missing_pki += 1
            continue
        # Construir feature_vector en el orden ALL_FEATURES (evalúa consistencia
        # con el modelo; el script espera features_vector o features dict)
        entries.append({"pdb_id": pid, "features": feats, "pKi": float(pki)})

    print(f"  Test set IDs en split_config: {len(test_ids)}")
    print(f"  Con features cache:           {len(entries)}")
    if n_missing_cache:
        print(f"  Sin cache:                   {n_missing_cache}")
    if n_missing_pki:
        print(f"  Sin pKi label:                {n_missing_pki}")
    return entries


def _load_model() -> Any | None:
    import joblib
    model_path = MODELS_DIR / "model_a_universal.joblib"
    if not model_path.exists():
        print(f"[SKIP] Modelo no encontrado en {model_path}")
        return None
    return joblib.load(model_path)


# ── Main ─────────────────────────────────────────────────────────────────────

def run_valid_spearman():
    print("=" * 70)
    print("SPEARMAN BENCHMARK VALIDO (CV wrapper) — PDBbind v2020 test split")
    print("=" * 70)
    print("NOTA: Para benchmark canónico (holdout 327 complejos, delta-learning),")
    print("      usa: python evaluate_test_set.py")
    print("=" * 70)

    entries = _load_test_set()
    if not entries:
        print("[FAIL] Sin datos de test. Asegurate de tener feature_cache_v4/ con split=test.")
        return

    # Cargar feature_names del modelo (si es XGBoost sklearn o booster)
    import joblib
    model_path = MODELS_DIR / "model_a_universal.joblib"
    if not model_path.exists():
        print(f"[SKIP] Modelo no encontrado en {model_path}")
        return
    loaded = joblib.load(model_path)

    # El .joblib es un dict con keys: booster, feature_names, params, metrics, ...
    if isinstance(loaded, dict) and "booster" in loaded:
        model = loaded["booster"]
        feature_names = loaded.get("feature_names")
        is_delta = loaded.get("params", {}).get("is_delta_model", False)
    else:
        model = loaded
        feature_names = None
        is_delta = False

    # Fallback: leer metadata.json si no hay feature_names
    if not feature_names:
        meta_path = model_path.with_suffix("").with_suffix(".metadata.json")
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            feature_names = meta.get("feature_names")
            is_delta = meta.get("params", {}).get("is_delta_model", is_delta)
    if not feature_names and hasattr(model, "feature_names_in_"):
        feature_names = list(model.feature_names_in_)
    if not feature_names:
        print("[FAIL] No se pudieron obtener feature_names. Abortando.")
        return
    print(f"Test set entries: {len(entries)} moleculas del PDBbind v2020 (frozen test)")
    print(f"Modelo: {type(model).__name__}, {len(feature_names)} features, delta={is_delta}")

    y_true = []
    y_pred = []

    for entry in entries:
        feats_dict = entry.get("features", {})
        pki_true = entry.get("pKi")
        if not feats_dict or pki_true is None:
            continue
        try:
            # Construir feature vector en el orden esperado por el modelo
            feat_array = np.array(
                [float(feats_dict.get(fn, 0.0)) for fn in feature_names],
                dtype=np.float32,
            ).reshape(1, -1)
            # Modelo Booster → DMatrix; modelo sklearn → array directo
            if hasattr(model, "predict") and "DMatrix" in type(model).__mro__[0].__name__:
                pass  # sklearn style
            try:
                import xgboost as xgb
                dmat = xgb.DMatrix(feat_array, feature_names=feature_names)
                pred_raw = float(model.predict(dmat)[0])
            except (ImportError, Exception):
                pred_raw = float(model.predict(feat_array)[0])
            # Delta-learning: pKi = -vina_best/1.36 + delta
            if is_delta:
                vina_score = float(feats_dict.get("vina_best_score", 0.0))
                vina_pki = -vina_score / 1.36
                pki_pred = vina_pki + pred_raw
            else:
                pki_pred = pred_raw
            y_true.append(float(pki_true))
            y_pred.append(pki_pred)
        except Exception as e:
            print(f"  [skip] {entry.get('pdb_id','?')}: {e}")
            continue

    n = len(y_true)
    if n < 10:
        print(f"[FAIL] Solo {n} predicciones validas. Se necesitan >= 10.")
        return

    y_true_arr = np.array(y_true, dtype=np.float64)
    y_pred_arr = np.array(y_pred, dtype=np.float64)

    rho, p_val = spearmanr(y_true_arr, y_pred_arr)
    r, p_pearson = pearsonr(y_true_arr, y_pred_arr)
    rmse = float(np.sqrt(np.mean((y_true_arr - y_pred_arr) ** 2)))
    mae = float(np.mean(np.abs(y_true_arr - y_pred_arr)))

    # Bootstrap 95% CI
    (rho_lo, rho_hi), (r_lo, r_hi) = bootstrap_ci(y_true_arr, y_pred_arr)
    es = effect_size_interpretation(rho)

    print(f"\nResultados (n={n}, TODAS las entradas test, sin cap):")
    print(f"  Spearman rho: {rho:.4f}  (p={p_val:.6f})")
    print(f"    95% CI:     [{rho_lo:.4f}, {rho_hi:.4f}]")
    print(f"    Effect:     {es} (|rho|={abs(rho):.2f})")
    print(f"  Pearson r:    {r:.4f}  (p={p_pearson:.6f})")
    print(f"    95% CI:     [{r_lo:.4f}, {r_hi:.4f}]")
    print(f"  RMSE:         {rmse:.4f} pKi")
    print(f"  MAE:          {mae:.4f} pKi")
    print(f"  y_true range: [{y_true_arr.min():.2f}, {y_true_arr.max():.2f}]")
    print(f"  y_pred range: [{y_pred_arr.min():.2f}, {y_pred_arr.max():.2f}]")

    # Significance statement (evita binario EXCELENTE/BUENO)
    sig = "significativo" if p_val < 0.05 else "NO significativo"
    print(f"\nInterpretacion: rho={rho:.3f} [{rho_lo:.3f}, {rho_hi:.3f}] "
          f"(effect={es}, p={p_val:.3g}, {sig}). "
          f"CI no incluye 0: {'SÍ' if rho_lo > 0 or rho_hi < 0 else 'NO'}.")

    return rho, p_val, n


if __name__ == "__main__":
    run_valid_spearman()