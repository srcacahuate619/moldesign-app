"""
scripts/train_classifier_binder.py

Reentrena el clasificador binario "binder" (pKi >= 7.0 => 1) sobre el
POOL scaffold-disjoint (537 complejos) y lo evalua en el HOLDOUT congelado
(328 complejos). Reemplaza al classifier_binder de julio que fue entrenado
sobre el split random con leakage (692 train / 173 val, todos vistos).

Features: 160 (Shell=96 + ECIF=56 + 1D2D=8). Sin Vina, sin size-norm.
Label: binder = 1 if pKi >= 7.0 else 0 (umbral 100 nM, estandar literatura).
Split: scaffold_disjoint_stratified desde split_config.json (igual que Fase A).

Uso:
    cd rescoring
    python scripts/train_classifier_binder.py

Salida:
    artifacts/classifier_binder.joblib
    artifacts/classifier_binder.json
    artifacts/classifier_binder.metadata.json
    + metricas honestas impresas (CV val + holdout)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from train_families import (
    ALL_FEATURES,
    ARTIFACTS,
    CACHE_DIR,
    FAMILY_MAP_PATH,
    INDEX_PATH,
    SEED,
    build_feature_matrix,
    enrich_features_with_1d2d,
    load_cached_3d_features,
    load_family_map,
    load_frozen_test_ids,
    parse_index,
)

BINDER_THRESHOLD = 7.0  # pKi >= 7.0 (~100 nM) -> binder (literatura estandar)
CLASSIFIER_FEATURES = [
    "mw", "logp", "tpsa", "hbd", "hba", "rotatable_bonds", "qed", "log_mw",
]
# + 96 Shell + 56 ECIF. Tomamos los 160 del metadata del clasificador viejo
# (Shell+ECIF+1D2D, sin Vina ni size-norm). Reusamos ALL_FEATURES y filtramos.
# El metadata viejo lista exactamente esos 160 nombres; los derivamos aqui.


def _load_classifier_feature_names():
    """Cargar los 160 nombres desde el metadata viejo (o derivar de ALL_FEATURES)."""
    meta_path = ARTIFACTS / "classifier_binder.metadata.json"
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        names = meta.get("feature_names", [])
        if len(names) == 160:
            return names
    # Fallback: 1D2D (8) + Shell (96) + ECIF (56) de ALL_FEATURES
    shell_ecif_1d2d = [
        n for n in ALL_FEATURES
        if n.startswith("shell_") or n.startswith("ecif_") or n in {
            "mw", "logp", "tpsa", "hbd", "hba", "rotatable_bonds", "qed", "log_mw",
        }
    ]
    return shell_ecif_1d2d


def _binary_labels(labels: dict[str, float], ids: list[str]) -> np.ndarray:
    return np.array([1.0 if labels.get(pid, 0.0) >= BINDER_THRESHOLD else 0.0 for pid in ids])


def _metrics(y_true, y_prob, y_pred):
    from sklearn.metrics import roc_auc_score, f1_score, accuracy_score
    auc = float(roc_auc_score(y_true, y_prob)) if len(set(y_true)) > 1 else 0.5
    f1 = float(f1_score(y_true, y_pred))
    acc = float(accuracy_score(y_true, y_pred))
    return {"auc": round(auc, 4), "f1": round(f1, 4), "accuracy": round(acc, 4),
            "n": int(len(y_true)), "pos": int(sum(y_true)), "neg": int(len(y_true) - sum(y_true))}


def _bootstrap_ci(y_true, y_prob, n_iter=10000, seed=42):
    rng = np.random.default_rng(seed)
    n = len(y_true)
    if n < 10:
        return [float("nan"), float("nan")]
    aucs = []
    y_true = np.array(y_true); y_prob = np.array(y_prob)
    for _ in range(n_iter):
        idx = rng.integers(0, n, n)
        if len(set(y_true[idx])) < 2:
            continue
        from sklearn.metrics import roc_auc_score
        aucs.append(roc_auc_score(y_true[idx], y_prob[idx]))
    if not aucs:
        return [float("nan"), float("nan")]
    return [round(float(np.percentile(aucs, 2.5)), 4), round(float(np.percentile(aucs, 97.5)), 4)]


def main() -> int:
    import xgboost as xgb
    from logger import get_logger
    log = get_logger(__name__)

    log.info("=" * 60)
    log.info("  FOLLOWUP 1 - CLASSIFIER BINDER (Fase A honest retrain)")
    log.info("  Pool scaffold-disjoint: 537 | Holdout: 328 | features: 160")
    log.info("  Label: binder = 1 if pKi >= %.1f (~100nM) else 0", BINDER_THRESHOLD)
    log.info("=" * 60)

    # 1. Labels + features
    labels = parse_index(INDEX_PATH)
    features_3d = load_cached_3d_features(CACHE_DIR)
    valid_ids = [pid for pid in features_3d if pid in labels]
    log.info("Complexes features+labels: %d", len(valid_ids))

    # 2. Exclude frozen holdout (SAME split as regression Fase A)
    frozen = load_frozen_test_ids(ARTIFACTS / "split_config.json")
    pool_ids = [pid for pid in valid_ids if pid.lower() not in frozen]
    holdout_ids = [pid for pid in valid_ids if pid.lower() in frozen]
    log.info("Pool (train): %d | Holdout: %d | Frozen total: %d", len(pool_ids), len(holdout_ids), len(frozen))
    assert set(pool_ids) & set(holdout_ids) == set(), "LEAKAGE: pool y holdout comparten IDs!"

    # 3. Enrich + feature matrix (160 features)
    features = enrich_features_with_1d2d(pool_ids, features_3d)
    feat_names = _load_classifier_feature_names()
    log.info("Classifier features: %d", len(feat_names))

    X_pool, kept_pool, _ = build_feature_matrix(pool_ids, features, feat_names)
    y_pool = _binary_labels(labels, kept_pool)
    log.info("Pool labels: pos=%d neg=%d (%.1f%% binder)", int(y_pool.sum()), int(len(y_pool) - y_pool.sum()), 100 * y_pool.mean())

    # 4. Stratified 80/20 split (semilla 42) dentro del pool para validacion
    np.random.seed(SEED)
    pos_idx = np.where(y_pool == 1)[0]
    neg_idx = np.where(y_pool == 0)[0]
    np.random.shuffle(pos_idx); np.random.shuffle(neg_idx)
    n_pos_train = int(len(pos_idx) * 0.8)
    n_neg_train = int(len(neg_idx) * 0.8)
    train_idx = np.concatenate([pos_idx[:n_pos_train], neg_idx[:n_neg_train]])
    val_idx = np.concatenate([pos_idx[n_pos_train:], neg_idx[n_neg_train:]])
    np.random.shuffle(train_idx); np.random.shuffle(val_idx)

    X_train, y_train = X_pool[train_idx], y_pool[train_idx]
    X_val, y_val = X_pool[val_idx], y_pool[val_idx]
    log.info("Train: %d (pos=%d) | Val: %d (pos=%d)", len(X_train), int(y_train.sum()), len(X_val), int(y_val.sum()))

    # 5. XGBoost binary
    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=feat_names)
    dval = xgb.DMatrix(X_val, label=y_val, feature_names=feat_names)
    params = {"objective": "binary:logistic", "eval_metric": "auc",
              "max_depth": 6, "eta": 0.1, "subsample": 0.8, "colsample_bytree": 0.8,
              "seed": SEED, "tree_method": "hist", "n_jobs": -1}
    model = xgb.train(params, dtrain, num_boost_round=500,
                      evals=[(dtrain, "train"), (dval, "val")],
                      early_stopping_rounds=30, verbose_eval=False)
    log.info("Best iteration: %d | best val AUC: %.4f", model.best_iteration, model.best_score)

    # 6. Val metrics
    val_prob = model.predict(dval)
    val_pred = (val_prob >= 0.5).astype(int)
    val_metrics = _metrics(y_val, val_prob, val_pred)
    val_ci = _bootstrap_ci(y_val, val_prob)
    log.info("VAL (internal 80/20 of pool): AUC=%.4f F1=%.4f acc=%.4f CI95=[%s,%s]",
             val_metrics["auc"], val_metrics["f1"], val_metrics["accuracy"], val_ci[0], val_ci[1])

    # 7. HOLDOUT evaluation (the honest number)
    features_h = enrich_features_with_1d2d(holdout_ids, features_3d)
    X_hold, kept_hold, _ = build_feature_matrix(holdout_ids, features_h, feat_names)
    y_hold = _binary_labels(labels, kept_hold)
    dhold = xgb.DMatrix(X_hold, feature_names=feat_names)
    hold_prob = model.predict(dhold)
    hold_pred = (hold_prob >= 0.5).astype(int)
    hold_metrics = _metrics(y_hold, hold_prob, hold_pred)
    hold_ci = _bootstrap_ci(y_hold, hold_prob)
    log.info("HOLDOUT (328 frozen): AUC=%.4f F1=%.4f acc=%.4f CI95=[%s,%s]  pos=%d neg=%d",
             hold_metrics["auc"], hold_metrics["f1"], hold_metrics["accuracy"],
             hold_ci[0], hold_ci[1], hold_metrics["pos"], hold_metrics["neg"])

    val_metrics["auc_ci95"] = val_ci
    hold_metrics["auc_ci95"] = hold_ci

    # 8. Save artifacts
    joblib_path = ARTIFACTS / "classifier_binder.joblib"
    json_path = ARTIFACTS / "classifier_binder.json"
    meta_path = ARTIFACTS / "classifier_binder.metadata.json"
    import joblib
    joblib.dump({"booster": model, "feature_names": feat_names, "metrics": val_metrics,
                 "train_samples": len(X_train), "val_samples": len(X_val),
                 "pos_samples": int(y_train.sum() + y_val.sum()),
                 "neg_samples": int(len(y_train) + len(y_val) - y_train.sum() - y_val.sum()),
                 "best_iteration": model.best_iteration, "binder_threshold": BINDER_THRESHOLD},
                joblib_path)
    model.save_model(str(json_path))
    meta = {"feature_names": feat_names, "n_features": len(feat_names),
            "feature_set": "Shell(96)+ECIF(56)+1D2D(8)=160",
            "metrics": val_metrics, "holdout_metrics": hold_metrics,
            "train_samples": len(X_train), "val_samples": len(X_val),
            "pos_samples_pool": val_metrics["pos"], "neg_samples_pool": val_metrics["neg"],
            "best_iteration": model.best_iteration,
            "binder_threshold": BINDER_THRESHOLD,
            "split": "scaffold_disjoint_stratified (Fase A)",
            "train_timestamp": "2026-08-10T02:10:00"}
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Saved: %s, %s, %s", joblib_path.name, json_path.name, meta_path.name)

    # 9. Comparison print
    print("\n" + "=" * 60)
    print("  FOLLOWUP 1 - CLASSIFIER BINDER (honest)")
    print("=" * 60)
    print(f"  OLD (leakage, july):  AUC 0.8584  n_train 692  n_val 173 (todos vistos)")
    print(f"  NEW VAL  (pool 80/20): AUC {val_metrics['auc']}  CI {val_ci}  n_val {len(X_val)}")
    print(f"  NEW HOLD (328 frozen): AUC {hold_metrics['auc']}  CI {hold_ci}  n {len(X_hold)}")
    print(f"  Binder label: pKi >= {BINDER_THRESHOLD} ({100*hold_metrics['pos']/max(1,hold_metrics['pos']+hold_metrics['neg']):.1f}% positives en holdout)")
    print(f"  Features: {len(feat_names)} (Shell+ECIF+1D2D, sin Vina)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
