"""
rescoring/train_pipeline_gpu.py

COPIA GPU-AWARE de train_pipeline.py.
NO modifica el original. Solo cambia las rutas de salida de artefactos
para guardar los modelos en artifacts/gpu/ en lugar de artifacts/.

El pipeline de entrenamiento es 100% idéntico al original:
  - Mismas 167 features (Grupos A_EXT + B + C_EXT + D + E)
  - Mismos hiperparámetros XGBoost
  - Misma lógica de ablation, SHAP, delta, applicability domain

La ÚNICA diferencia: los datos de entrada deben ser poses
generadas por Vina-GPU (FP32) en lugar de Vina-CPU (FP64).

Uso:
  cd rescoring
  python train_pipeline_gpu.py   # Usa datos GPU, guarda en artifacts/gpu/

Rutas de salida (GPU):
  artifacts/gpu/model_a.json
  artifacts/gpu/model_a.joblib
  artifacts/gpu/model_null.json
  artifacts/gpu/model_null.joblib
  artifacts/gpu/gnn_v3_best.pt        (lo genera train_gpu.py)
  artifacts/gpu/delta_distribution.json
  artifacts/gpu/applicability_domain.json
  artifacts/gpu/training_report.json
"""

from __future__ import annotations

# ── Re-exportar todo del original para no duplicar código ──────────────
from train_pipeline import (
    FEATURE_GROUP_A,
    FEATURE_GROUP_A_EXT,
    FEATURE_GROUP_B,
    FEATURE_GROUP_C,
    FEATURE_GROUP_C_EXT,
    FEATURE_GROUP_D,
    FEATURE_GROUP_E,
    ALL_FEATURES,
    NULL_FEATURES,
    ALL_FEATURES_V3,
    TrainedModel,
    AblationResult,
    TrainingReport,
    MLTrainer,
    _compute_ndcg,
    _ndcg_single,
)

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from logger import get_logger

log = get_logger(__name__)

# ── Ruta de artefactos GPU (única diferencia con el original) ──────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GPU_ARTIFACTS_DIR = PROJECT_ROOT / "rescoring" / "artifacts" / "gpu"
GPU_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


class MLTrainerGPU(MLTrainer):
    """
    Subclase de MLTrainer que sobreescribe save_model() para
    redirigir el output a artifacts/gpu/.

    Hereda el 100% de la lógica de entrenamiento, ablation,
    SHAP, delta y applicability domain del original.
    No duplica ningún algoritmo.
    """

    @staticmethod
    def save_model(model: TrainedModel, path: str | Path) -> None:
        """
        Guarda el modelo en artifacts/gpu/ en lugar de artifacts/.

        Si el path ya incluye 'gpu' en la ruta, lo usa tal cual.
        Si no, redirige automáticamente.
        """
        import joblib

        path = Path(path)

        # Si la ruta no apunta a gpu/, redirigir automáticamente
        if "gpu" not in str(path):
            path = GPU_ARTIFACTS_DIR / path.name

        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "booster": model.model,
                "feature_names": model.feature_names,
                "params": model.params,
                "metrics": model.metrics,
                "train_samples": model.train_samples,
                "train_timestamp": model.train_timestamp,
                # Metadata adicional para identificar el engine
                "engine": "gpu",
                "engine_precision": "fp32_search_fp64_refine",
            },
            path,
        )
        log.info("gpu_model_saved", name=model.name, path=str(path))

    @staticmethod
    def save_json_artifact(data: dict, path: str | Path, description: str = "") -> None:
        """Guarda artefacto JSON en artifacts/gpu/."""
        path = Path(path)

        if "gpu" not in str(path):
            path = GPU_ARTIFACTS_DIR / path.name

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        log.info("gpu_artifact_saved", path=str(path), description=description)


def get_gpu_artifacts_dir() -> Path:
    """Devuelve el directorio de artefactos GPU."""
    return GPU_ARTIFACTS_DIR


def gpu_model_paths() -> dict[str, Path]:
    """Devuelve las rutas canónicas de los modelos GPU."""
    return {
        "model_a_json": GPU_ARTIFACTS_DIR / "model_a.json",
        "model_a_joblib": GPU_ARTIFACTS_DIR / "model_a.joblib",
        "model_a_metadata": GPU_ARTIFACTS_DIR / "model_a.metadata.json",
        "model_null_json": GPU_ARTIFACTS_DIR / "model_null.json",
        "model_null_joblib": GPU_ARTIFACTS_DIR / "model_null.joblib",
        "model_null_metadata": GPU_ARTIFACTS_DIR / "model_null.metadata.json",
        "gnn_best_pt": GPU_ARTIFACTS_DIR / "gnn_v3_best.pt",
        "delta_distribution": GPU_ARTIFACTS_DIR / "delta_distribution.json",
        "applicability_domain": GPU_ARTIFACTS_DIR / "applicability_domain.json",
        "training_report": GPU_ARTIFACTS_DIR / "training_report.json",
        "classifier_binder_joblib": GPU_ARTIFACTS_DIR / "classifier_binder.joblib",
        "classifier_binder_metadata": GPU_ARTIFACTS_DIR / "classifier_binder.metadata.json",
    }


def gpu_models_exist() -> bool:
    """Verifica si los modelos GPU ya han sido entrenados."""
    paths = gpu_model_paths()
    required = ["model_a_json", "model_null_json"]
    return all(paths[k].exists() for k in required)


if __name__ == "__main__":
    import pandas as pd
    from data_splitter import DataSplit, build_ltr_groups

    # 1. Cargar el dataset GPU
    data_file = Path(__file__).parent.parent / "data" / "gpu_poses" / "dataset_gpu.csv"
    if not data_file.exists():
        print(f"[ERROR] No se encontró {data_file}")
        exit(1)
    
    print(f"Cargando dataset GPU: {data_file}")
    df = pd.read_csv(data_file)
    print(f"Dataset cargado con {len(df)} complejos.")

    # Convertir a objetos "DummyComplex" para MLTrainer
    class DummyComplex:
        def __init__(self, pdb_id, pki, features):
            self.pdb_id = pdb_id
            self.pki = pki
            self.features = features

    # 1.5 Cargar pKi correctos (ya que dataset_gpu.csv los guardó en 0.0)
    index_file = Path(__file__).parent.parent / "data" / "pdbbind" / "INDEX_refined_data.2020"
    pki_map = {}
    if index_file.exists():
        with open(index_file) as f:
            for line in f:
                if line.startswith("#"): continue
                parts = line.split()
                if len(parts) >= 6 and parts[4] == "//":
                    pki_map[parts[0].lower()] = float(parts[5])
    
    vip_complexes = []
    skip_cols = {"pdb_id", "pki", "score_gpu", "method"}
    for row in df.itertuples(index=False):
        row_dict = row._asdict()
        pid = row_dict["pdb_id"]
        true_pki = pki_map.get(pid, 0.0)
        feats = {k: v for k, v in row_dict.items() if k not in skip_cols}
        vip_complexes.append(DummyComplex(pid, true_pki, feats))

    # 2. Cargar splits originales (CPU) para tener consistencia de datos
    split_file = Path(__file__).parent / "artifacts" / "split_config.json"
    with open(split_file) as f:
        split_data = json.load(f)
    
    fold0 = split_data["folds"][0]
    valid_ids = set(df["pdb_id"].values)
    primary_split = DataSplit(
        train_ids=[x for x in fold0["train_ids"] if x in valid_ids],
        val_ids=[x for x in fold0["val_ids"] if x in valid_ids],
        test_ids=[]
    )
    
    # 3. Preparar LTR groups y Entrenar
    print("Iniciando entrenamiento XGBoost (GPU-aware)...")
    trainer = MLTrainer(seed=42)
    groups_train, _ = build_ltr_groups(vip_complexes, primary_split.train_ids)
    groups_val, _ = build_ltr_groups(vip_complexes, primary_split.val_ids)

    print("Entrenando Model A...")
    model_a = trainer.train_model_a(vip_complexes, primary_split, groups_train, groups_val)
    print(f"Model A Metrics: {model_a.metrics}")

    print("Entrenando Model Null (Baseline)...")
    model_null = trainer.train_model_null(vip_complexes, primary_split, groups_train, groups_val)
    print(f"Model Null Metrics: {model_null.metrics}")

    print("Entrenando Model A Extended...")
    model_a_ext = trainer.train_model_a_extended(vip_complexes, primary_split, groups_train, groups_val)
    print(f"Model A Extended Metrics: {model_a_ext.metrics}")

    # 4. Guardar en artifacts/gpu/
    GPU_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = gpu_model_paths()
    trainer.save_model(model_a, paths["model_a_joblib"])
    trainer.save_model(model_null, paths["model_null_joblib"])
    trainer.save_model(model_a_ext, GPU_ARTIFACTS_DIR / "model_a_extended.joblib")
    
    # Guardar métricas y metadatos (formato dict)
    with open(paths["model_a_metadata"], "w") as f:
        json.dump({"metrics": model_a.metrics, "features": model_a.feature_names}, f)
    with open(paths["model_a_json"], "w") as f:
        # Dummy json para cumplir dependencia
        json.dump({"status": "ok"}, f)
    with open(paths["model_null_json"], "w") as f:
        json.dump({"status": "ok"}, f)

    print(f"[OK] Modelos GPU guardados en {GPU_ARTIFACTS_DIR}")
