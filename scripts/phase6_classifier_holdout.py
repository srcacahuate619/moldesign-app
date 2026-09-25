#!/usr/bin/env python3
"""Fase 6: matriz nativa Fase A y evaluación del clasificador congelado.

Uso:
  python scripts/phase6_classifier_holdout.py prepare --pdbbind D:/.../pdbbind --output D:/.../evidencia
  python scripts/phase6_classifier_holdout.py evaluate --matrix matrix_native_faseA.npz --model classifier_binder.json --output resultados
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_NAME = "INDEX_refined_data.2020.faseA_20260813_184439"
EXPECTED = {
    "index": "1c52a9b7631cc11a31c6b3344ececa3de8a9087c86ab3e6c5a30dc69861de02d",
    "split": "bbc57126e2306e087dcddb76478a8cddfbd36fb7de3f350806b6366ee3534f6f",
    "groups": "9756211324d16cdafb0dc6a4c473ff2bedeff8a38aa81e4f7b9144d687033568",
    "model": "b83a936564036b196b53919c707250c441d49fbd1b9427b15f7ebe48850ea636",
    "metadata": "e8b5de0feea62e3c571d0b1936ba6ac80f19709277f3ab9b2e1cfdfee3bb128b",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_hash(path: Path, name: str) -> None:
    actual = sha256(path)
    if actual != EXPECTED[name]:
        raise ValueError(f"{name}: SHA-256 inesperado: {actual}")


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")


def prepare(args: argparse.Namespace) -> None:
    import numpy as np

    pdbbind = Path(args.pdbbind).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    index = pdbbind / INDEX_NAME
    split_path = ROOT / "rescoring/artifacts/split_config.json"
    groups_path = ROOT / "scripts/artifacts_science/FEP-03-PDBBIND/grupos.json"
    model_path = ROOT / "rescoring/artifacts/classifier_binder.json"
    metadata_path = ROOT / "rescoring/artifacts/classifier_binder.metadata.json"
    for name, path in (("index", index), ("split", split_path), ("groups", groups_path),
                       ("model", model_path), ("metadata", metadata_path)):
        require_hash(path, name)

    sys.path.insert(0, str(ROOT / "rescoring"))
    import train_families as tf

    tf.PDBBIND_DIR = pdbbind
    labels = tf.parse_index(index)
    cached = tf.load_cached_3d_features(pdbbind / "feature_cache_v4")
    split = json.loads(split_path.read_text(encoding="utf-8"))
    frozen = {str(pid).upper() for pid in split["frozen_test_set"]}
    ids = sorted(set(labels) & set(cached))
    pool_ids = [pid for pid in ids if pid not in frozen]
    hold_ids = [pid for pid in ids if pid in frozen]
    if (len(ids), len(pool_ids), len(hold_ids)) != (865, 537, 328):
        raise ValueError(f"Cohorte inesperada: {len(ids)}/{len(pool_ids)}/{len(hold_ids)}")

    cluster_data = json.loads(groups_path.read_text(encoding="utf-8"))
    cluster = {str(pid).upper(): i for i, group in enumerate(cluster_data["grupos"])
               for pid in group}
    if any(pid not in cluster for pid in ids):
        raise ValueError("Hay complejos sin clúster proteico")
    pool_groups = {cluster[pid] for pid in pool_ids}
    seen = sum(cluster[pid] in pool_groups for pid in hold_ids)
    if seen != 233:
        raise ValueError(f"Solapamiento inesperado: {seen}/328")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    feature_names = metadata["feature_names"]
    if len(feature_names) != 160:
        raise ValueError("El contrato del modelo no tiene 160 features")
    enriched = tf.enrich_features_with_1d2d(ids, cached)
    x_pool, kept_pool, excluded_pool = tf.build_feature_matrix(
        pool_ids, enriched, feature_names)
    x_hold, kept_hold, excluded_hold = tf.build_feature_matrix(
        hold_ids, enriched, feature_names)

    cache_paths = {p.stem.upper(): p for p in (pdbbind / "feature_cache_v4").glob("*.json")}
    file_hashes = {}
    for pid in ids:
        file_hashes[f"feature_cache_v4/{cache_paths[pid].name}"] = sha256(cache_paths[pid])
        for suffix in ("sdf", "mol2"):
            rel = f"{pid.lower()}/{pid.lower()}_ligand.{suffix}"
            path = pdbbind / rel
            if path.is_file():
                file_hashes[rel] = sha256(path)
    write_json(output / "input_file_hashes.json", file_hashes)

    np.savez_compressed(
        output / "matrix_native_faseA.npz",
        x_pool=x_pool, x_hold=x_hold,
        id_pool=np.asarray(kept_pool), id_hold=np.asarray(kept_hold),
        y_pool=np.asarray([int(labels[pid] >= 7.0) for pid in kept_pool]),
        y_hold=np.asarray([int(labels[pid] >= 7.0) for pid in kept_hold]),
        group_pool=np.asarray([cluster[pid] for pid in kept_pool]),
        group_hold=np.asarray([cluster[pid] for pid in kept_hold]),
        feature_names=np.asarray(feature_names),
    )
    write_json(output / "matrix_manifest.json", {
        "cohort": "Fase A PDBBind v2020, native crystal poses",
        "source_hashes": EXPECTED,
        "script_sha256": sha256(Path(__file__)),
        "input_file_hashes_sha256": sha256(output / "input_file_hashes.json"),
        "matrix_sha256": sha256(output / "matrix_native_faseA.npz"),
        "input_ids": len(ids), "pool": len(kept_pool), "holdout": len(kept_hold),
        "holdout_seen_clusters": seen,
        "holdout_unseen_clusters": len(hold_ids) - seen,
        "excluded_pool": excluded_pool, "excluded_holdout": excluded_hold,
        "python": platform.python_version(), "numpy": np.__version__,
        "preparation": "train_families.enrich_features_with_1d2d + build_feature_matrix",
    })
    print(json.dumps({"matrix_sha256": sha256(output / "matrix_native_faseA.npz"),
                      "pool": len(kept_pool), "holdout": len(kept_hold),
                      "excluded": len(excluded_pool) + len(excluded_hold)}))


def ece_10(y, p) -> float:
    import numpy as np

    edges = np.linspace(0.0, 1.0, 11)
    total = 0.0
    for i in range(10):
        mask = (p >= edges[i]) & (p <= edges[i + 1] if i == 9 else p < edges[i + 1])
        if mask.any():
            total += float(mask.mean() * abs(y[mask].mean() - p[mask].mean()))
    return total


def summary(y, p) -> dict:
    import numpy as np
    from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

    prevalence = float(np.mean(y))
    return {
        "n": int(len(y)), "positive": int(np.sum(y)), "negative": int(len(y) - np.sum(y)),
        "prevalence": prevalence,
        "roc_auc": float(roc_auc_score(y, p)) if len(set(y.tolist())) == 2 else None,
        "average_precision": float(average_precision_score(y, p)) if len(set(y.tolist())) == 2 else None,
        "brier": float(brier_score_loss(y, p)),
        "brier_prevalence_baseline": prevalence * (1.0 - prevalence),
        "ece_10_equal_width": ece_10(y, p),
    }


def cluster_bootstrap(y, p, group, seed: int = 42, iterations: int = 2000) -> dict:
    import numpy as np
    from sklearn.metrics import brier_score_loss, roc_auc_score

    rng = np.random.default_rng(seed)
    unique = np.unique(group)
    by_group = {g: np.flatnonzero(group == g) for g in unique}
    aucs, briers = [], []
    skipped = 0
    for _ in range(iterations):
        chosen = rng.choice(unique, size=len(unique), replace=True)
        rows = np.concatenate([by_group[g] for g in chosen])
        if len(np.unique(y[rows])) < 2:
            skipped += 1
            continue
        aucs.append(float(roc_auc_score(y[rows], p[rows])))
        briers.append(float(brier_score_loss(y[rows], p[rows])))
    def interval(values):
        return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))] if values else None
    return {"iterations": iterations, "valid": len(aucs), "skipped_one_class": skipped,
            "roc_auc_ci95": interval(aucs), "brier_ci95": interval(briers)}


def evaluate(args: argparse.Namespace) -> None:
    import numpy as np
    import xgboost as xgb

    matrix = Path(args.matrix)
    model_path = Path(args.model)
    if sha256(model_path) != EXPECTED["model"]:
        raise ValueError("El modelo remoto no coincide con el preregistro")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    data = np.load(matrix, allow_pickle=False)
    booster = xgb.Booster()
    booster.load_model(str(model_path))
    feature_names = data["feature_names"].tolist()
    x_hold = data["x_hold"]
    y = data["y_hold"].astype(int)
    groups = data["group_hold"].astype(int)
    pool_groups = set(data["group_pool"].astype(int).tolist())
    seen = np.array([int(g in pool_groups) for g in groups], dtype=bool)
    if (len(y), int(seen.sum())) != (328, 233):
        raise ValueError("La matriz no conserva el split preregistrado")
    prob = booster.predict(xgb.DMatrix(x_hold, feature_names=feature_names))
    if not np.isfinite(prob).all() or ((prob < 0) | (prob > 1)).any():
        raise ValueError("Probabilidades fuera de [0, 1]")
    all_metrics = summary(y, prob)
    discrepancy = abs(all_metrics["roc_auc"] - 0.8818)
    metrics = {
        "pose_source": "crystal_native", "model_sha256": sha256(model_path),
        "script_sha256": sha256(Path(__file__)),
        "matrix_sha256": sha256(matrix),
        "reproduces_metadata_auc": discrepancy <= 0.005,
        "metadata_auc_absolute_difference": discrepancy,
        "all_holdout": {**all_metrics, "bootstrap_by_protein_cluster": cluster_bootstrap(y, prob, groups)},
        "seen_protein_cluster": {**summary(y[seen], prob[seen]),
                                 "bootstrap_by_protein_cluster": cluster_bootstrap(y[seen], prob[seen], groups[seen])},
        "unseen_protein_cluster": {**summary(y[~seen], prob[~seen]),
                                   "bootstrap_by_protein_cluster": cluster_bootstrap(y[~seen], prob[~seen], groups[~seen])},
        "python": platform.python_version(), "numpy": np.__version__,
        "xgboost": xgb.__version__,
    }
    write_json(output / "metrics.json", metrics)
    with (output / "predictions.jsonl").open("w", encoding="utf-8") as handle:
        for pid, yi, pi, gi, si in zip(data["id_hold"].tolist(), y, prob, groups, seen):
            handle.write(json.dumps({"pdb_id": pid, "binder": int(yi),
                                     "probability": float(pi), "protein_cluster": int(gi),
                                     "cluster_seen_in_pool": bool(si)}, sort_keys=True) + "\n")
    print(json.dumps({"auc": all_metrics["roc_auc"],
                      "auc_difference": discrepancy,
                      "unseen_auc": metrics["unseen_protein_cluster"]["roc_auc"],
                      "unseen_n": metrics["unseen_protein_cluster"]["n"]}))
    if discrepancy > 0.005:
        raise SystemExit(2)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--pdbbind", required=True)
    prep.add_argument("--output", required=True)
    ev = sub.add_parser("evaluate")
    ev.add_argument("--matrix", required=True)
    ev.add_argument("--model", required=True)
    ev.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args)
    else:
        evaluate(args)


if __name__ == "__main__":
    main()
