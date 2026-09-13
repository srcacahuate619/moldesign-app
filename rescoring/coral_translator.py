"""
coral_translator.py — CORAL: CORrelation ALignment for GPU→CPU feature translation.

Aligns GPU (FP32) features to look like CPU (FP64) features by matching their
covariance structures. Simple, linear, fast — no paired data needed.

Based on: Sun et al., "Return of Frustratingly Easy Domain Adaptation" (AAAI 2016)
Reference: https://github.com/adapt-python/adapt/blob/master/adapt/feature_based/_coral.py

Architecture:
    1. Train:  compute GPU cov → whiten → CPU cov coloring → save transform matrix
    2. Apply:  X_cpu_like = X_gpu @ transform

Integration:
    from coral_translator import CoralTranslator
    ct = CoralTranslator()
    ct.fit(feats_gpu, feats_cpu)          # train on paired domain samples
    feats_aligned = ct.transform(feats)    # apply transform

Usage:
    python rescoring/coral_translator.py --train  # train and save
    python rescoring/coral_translator.py --test   # validate on existing data
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "rescoring" / "artifacts"
CORAL_PATH = ARTIFACTS_DIR / "coral_transform.npz"


def _sqrtm(matrix: np.ndarray) -> np.ndarray:
    """Matrix square root via eigen decomposition. Stable for cov matrices."""
    eigvals, eigvecs = np.linalg.eigh(matrix)
    eigvals = np.maximum(eigvals, 1e-12)  # clip negative eigenvalues (numerical noise)
    return eigvecs @ np.diag(np.sqrt(eigvals)) @ eigvecs.T


def _inv_sqrtm(matrix: np.ndarray) -> np.ndarray:
    """Inverse square root: M^(-1/2)."""
    eigvals, eigvecs = np.linalg.eigh(matrix)
    eigvals = np.maximum(eigvals, 1e-12)
    return eigvecs @ np.diag(1.0 / np.sqrt(eigvals)) @ eigvecs.T


class CoralTranslator:
    """CORrelation ALignment translator for GPU-to-CPU feature harmonization."""
    def __init__(self):
        self._W: np.ndarray | None = None
        self._feature_names: list[str] = []
        self._gpu_cov: np.ndarray | None = None
        self._cpu_cov: np.ndarray | None = None
        self._n_gpu: int = 0
        self._n_cpu: int = 0

    def fit(self, X_gpu: np.ndarray, X_cpu: np.ndarray, feature_names=None, regularization: float = 1e-4):
        n_feat = X_gpu.shape[1]
        if X_cpu.shape[1] != n_feat:
            raise ValueError(f"Feature dimension mismatch: GPU={n_feat}, CPU={X_cpu.shape[1]}")
        cov_gpu = np.cov(X_gpu, rowvar=False) + np.eye(n_feat) * regularization
        cov_cpu = np.cov(X_cpu, rowvar=False) + np.eye(n_feat) * regularization
        W = _inv_sqrtm(cov_gpu) @ _sqrtm(cov_cpu)
        self._W = W
        self._feature_names = feature_names or []
        self._gpu_cov = cov_gpu
        self._cpu_cov = cov_cpu
        self._n_gpu = X_gpu.shape[0]
        self._n_cpu = X_cpu.shape[0]
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self._W is None:
            raise RuntimeError("Must fit() before transform()")
        return X @ self._W

    def save(self, path=None):
        p = path or CORAL_PATH
        np.savez(p, W=self._W, gpu_cov=self._gpu_cov, cpu_cov=self._cpu_cov, n_gpu=self._n_gpu, n_cpu=self._n_cpu, feature_names=json.dumps(self._feature_names) if self._feature_names else "[]")

    def load(self, path=None):
        p = path or CORAL_PATH
        if not p.exists():
            raise FileNotFoundError(f"CORAL transform not found: {p}")
        data = np.load(p, allow_pickle=True)
        self._W = data["W"]
        self._gpu_cov = data["gpu_cov"]; self._cpu_cov = data["cpu_cov"]
        self._n_gpu = int(data["n_gpu"]); self._n_cpu = int(data["n_cpu"])
        try: self._feature_names = json.loads(str(data["feature_names"]))
        except: self._feature_names = []
        return self

    @property
    def is_fitted(self): return self._W is not None

    @property
    def n_features(self): return self._W.shape[0] if self._W is not None else 0


class CoralModelHandler:
    """
    CORAL + ModelRouter wrapper: handles feature alignment automatically.

    When GPU features (167) need to feed a CPU model (176 with ProLIF),
    this handler pads missing features with zeros and applies CORAL transform.
    Works universally for any feature mismatch between GPU and CPU models.
    """

    def __init__(self):
        self._coral: CoralTranslator | None = None
        self._cpu_feature_names: list[str] = []
        self._gpu_feature_names: list[str] = []

    def load_or_train(
        self,
        gpu_ck: str | Path,
        cpu_ck: str | Path,
        cpu_model_path: str | Path | None = None,
    ) -> CoralModelHandler:
        """Load or train CORAL, detecting CPU model feature names automatically."""
        import xgboost as xgb

        coral_path = CORAL_PATH
        if coral_path.exists():
            ct = CoralTranslator().load(coral_path)
        else:
            # Train from scratch
            pass

        # Get CPU model feature names
        if cpu_model_path:
            bst = xgb.Booster()
            bst.load_model(str(cpu_model_path))
            cpu_names = bst.feature_names
        else:
            from train_pipeline import ALL_FEATURES
            cpu_names = ALL_FEATURES

        # Get GPU feature names from checkpoint
        gpu_data = json.loads(Path(gpu_ck).read_text())
        gpu_results = gpu_data.get("results", [])
        gpu_with = [r for r in gpu_results if r.get("features")]
        if gpu_with:
            sample_feats = gpu_with[0].get("features", {})
            gpu_names = sorted([k for k in sample_feats.keys() if not k.startswith("_")])
        else:
            from train_pipeline import ALL_FEATURES
            gpu_names = ALL_FEATURES

        self._coral = ct
        self._cpu_feature_names = list(cpu_names)
        self._gpu_feature_names = list(gpu_names)

        # Build alignment index: gpu_name → (cpu_index or None)
        self._alignment = []
        for cn in cpu_names:
            if cn in gpu_names:
                self._alignment.append(("gpu", gpu_names.index(cn)))
            else:
                self._alignment.append(("zero", -1))  # ProLIF features → pad with 0

        print("CoralModelHandler loaded:")
        print(f"  CPU model expects: {len(cpu_names)} features")
        print(f"  GPU features have: {len(gpu_names)} features")
        print(f"  Aligned: {sum(1 for a,_ in self._alignment if a=='gpu')}/{len(cpu_names)}")
        print(f"  Padded (zeros): {sum(1 for a,_ in self._alignment if a=='zero')}")
        return self

    def translate(self, feats_dict: dict) -> dict:
        """Translate GPU features -> CPU-like features, padded to CPU model format."""
        if self._coral is None:
            return feats_dict

        import numpy as np
        from train_pipeline import ALL_FEATURES

        # Build feature vector from ALL_FEATURES (what CORAL was trained on)
        X = np.zeros((1, len(ALL_FEATURES)), dtype=np.float64)
        for j, fn in enumerate(ALL_FEATURES):
            X[0, j] = feats_dict.get(fn, 0.0)

        # Apply CORAL transform (trained on 167 feat)
        Xt = self._coral.transform(X)

        # Map to CPU model features (176 feat)
        coral_map = {fn: float(Xt[0, j]) for j, fn in enumerate(ALL_FEATURES)}
        result = {}
        for cn in self._cpu_feature_names:
            if cn in coral_map:
                result[cn] = coral_map[cn]
            else:
                result[cn] = 0.0  # ProLIF or other extra features

        return result
    """
    CORrelation ALignment translator for GPU→CPU feature harmonization.

    Learns a linear transformation W such that:
        X_cpu_like = X_gpu @ W

    where cov(X_cpu_like) ≈ cov(X_cpu).

    This is a purely linear transform (Whiten + Re-color). No training
    epochs, no hyperparameters — just matrix operations on covariances.
    """

    def __init__(self):
        self._W: np.ndarray | None = None
        self._feature_names: list[str] = []
        self._gpu_cov: np.ndarray | None = None
        self._cpu_cov: np.ndarray | None = None
        self._n_gpu: int = 0
        self._n_cpu: int = 0

    def fit(
        self,
        X_gpu: np.ndarray,
        X_cpu: np.ndarray,
        feature_names: list[str] | None = None,
        regularization: float = 1e-4,
    ) -> CoralTranslator:
        """
        Learn CORAL transform: X_cpu_like = X_gpu @ W.

        Args:
            X_gpu: GPU features, shape (n_samples_gpu, n_features)
            X_cpu: CPU features, shape (n_samples_cpu, n_features)
            feature_names: optional list of feature names (for validation)
            regularization: added to diagonal of cov matrices for numerical stability
        """
        n_feat = X_gpu.shape[1]
        if X_cpu.shape[1] != n_feat:
            raise ValueError(
                f"Feature dimension mismatch: GPU={n_feat}, CPU={X_cpu.shape[1]}"
            )

        # Covariance matrices
        cov_gpu = np.cov(X_gpu, rowvar=False)
        cov_cpu = np.cov(X_cpu, rowvar=False)

        # Regularization: add small value to diagonal
        cov_gpu += np.eye(n_feat) * regularization
        cov_cpu += np.eye(n_feat) * regularization

        # CORAL transformation: W = cov_gpu^(-1/2) @ cov_cpu^(1/2)
        W = _inv_sqrtm(cov_gpu) @ _sqrtm(cov_cpu)

        self._W = W
        self._feature_names = feature_names or []
        self._gpu_cov = cov_gpu
        self._cpu_cov = cov_cpu
        self._n_gpu = X_gpu.shape[0]
        self._n_cpu = X_cpu.shape[0]

        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Apply CORAL transform: X_aligned = X @ W."""
        if self._W is None:
            raise RuntimeError("CoralTranslator must be fit() before transform()")
        return X @ self._W

    def fit_transform(
        self,
        X_gpu: np.ndarray,
        X_cpu: np.ndarray,
        feature_names: list[str] | None = None,
    ) -> np.ndarray:
        """Fit and transform in one call. Returns X_gpu aligned to CPU domain."""
        self.fit(X_gpu, X_cpu, feature_names)
        return self.transform(X_gpu)

    def save(self, path: Path | None = None) -> None:
        """Save transform matrix and metadata to .npz file."""
        p = path or CORAL_PATH
        np.savez(
            p,
            W=self._W,
            gpu_cov=self._gpu_cov,
            cpu_cov=self._cpu_cov,
            n_gpu=self._n_gpu,
            n_cpu=self._n_cpu,
            feature_names=json.dumps(self._feature_names) if self._feature_names else "[]",
        )

    def load(self, path: Path | None = None) -> CoralTranslator:
        """Load saved transform from .npz file."""
        p = path or CORAL_PATH
        if not p.exists():
            raise FileNotFoundError(f"CORAL transform not found: {p}")
        data = np.load(p, allow_pickle=True)
        self._W = data["W"]
        self._gpu_cov = data["gpu_cov"]
        self._cpu_cov = data["cpu_cov"]
        self._n_gpu = int(data["n_gpu"])
        self._n_cpu = int(data["n_cpu"])
        try:
            self._feature_names = json.loads(str(data["feature_names"]))
        except Exception:
            self._feature_names = []
        return self

    @property
    def is_fitted(self) -> bool:
        return self._W is not None

    @property
    def n_features(self) -> int:
        return self._W.shape[0] if self._W is not None else 0


def _extract_feature_matrix(
    results: list[dict],
    feature_names: list[str],
) -> np.ndarray:
    """Build feature matrix from benchmark results dicts.

    Args:
        results: list of result dicts with 'features' key
        feature_names: ordered feature names matching model expectations

    Returns:
        (n_samples, n_features) numpy array
    """
    X = np.zeros((len(results), len(feature_names)), dtype=np.float64)
    for i, r in enumerate(results):
        feats = r.get("features", {})
        for j, fn in enumerate(feature_names):
            X[i, j] = feats.get(fn, 0.0)
    return X


def train_from_checkpoints(
    gpu_checkpoint_path: str | Path,
    cpu_checkpoint_path: str | Path,
    save: bool = True,
) -> CoralTranslator:
    """
    Train CORAL translator from GPU and CPU benchmark checkpoints.
    Uses feature names from the CPU model to ensure compatibility.
    """
    from train_pipeline import ALL_FEATURES

    gpu_path = Path(gpu_checkpoint_path)
    cpu_path = Path(cpu_checkpoint_path)

    gpu_data = json.loads(gpu_path.read_text())
    cpu_data = json.loads(cpu_path.read_text())

    gpu_results = gpu_data.get("results", [])
    cpu_results = cpu_data.get("results", [])

    gpu_with_feats = [r for r in gpu_results if r.get("features")]
    cpu_with_feats = [r for r in cpu_results if r.get("features")]

    print(f"GPU molecules with features: {len(gpu_with_feats)}")
    print(f"CPU molecules with features: {len(cpu_with_feats)}")

    X_gpu = _extract_feature_matrix(gpu_with_feats, ALL_FEATURES)
    X_cpu = _extract_feature_matrix(cpu_with_feats, ALL_FEATURES)

    ct = CoralTranslator()
    ct.fit(X_gpu, X_cpu, feature_names=ALL_FEATURES)

    print(f"CORAL transform trained: {ct.n_features} features")
    print(f"  GPU samples: {ct._n_gpu}")
    print(f"  CPU samples: {ct._n_cpu}")

    if ct._gpu_cov is not None and ct._cpu_cov is not None:
        gpu_trace = np.trace(ct._gpu_cov)
        cpu_trace = np.trace(ct._cpu_cov)
        print(f"  GPU cov trace: {gpu_trace:.2f}")
        print(f"  CPU cov trace: {cpu_trace:.2f}")
        print(f"  Ratio GPU/CPU: {gpu_trace/cpu_trace:.3f}")

    if save:
        ct.save()
        print(f"  Saved to: {CORAL_PATH}")

    return ct


def validate_translator(
    ct: CoralTranslator,
    gpu_checkpoint_path: str | Path,
) -> dict:
    """
    Validate CORAL translator: compare GPU model (original) vs CORAL+CPU model (translated).
    Uses per-feature lookup to handle model feature name differences.
    """
    from model_router import get_router

    gpu_path = Path(gpu_checkpoint_path)
    gpu_data = json.loads(gpu_path.read_text())
    gpu_results = gpu_data.get("results", [])

    gpu_valid = [r for r in gpu_results if r.get("features") and r.get("vina_score") is not None and r["vina_score"] < 0]
    print(f"GPU valid (docked + features): {len(gpu_valid)}/{len(gpu_results)}")

    if not gpu_valid:
        return {"error": "no valid GPU results"}

    # Build feature matrix using CORAL feature names
    coral_feats = ct._feature_names if ct._feature_names else []
    if not coral_feats:
        from train_pipeline import ALL_FEATURES
        coral_feats = ALL_FEATURES

    X_gpu = _extract_feature_matrix(gpu_valid, coral_feats)

    # Apply CORAL
    X_aligned = ct.transform(X_gpu)

    # Score: compare GPU model (original) vs CPU model (translated features)
    router = get_router()
    scores_original = []
    scores_aligned = []
    vina_scores = []
    labels = []

    for i, r in enumerate(gpu_valid):
        feats_original = r.get("features", {})

        # Original GPU features → GPU model
        try:
            rr_orig = router.predict(feats_original, engine="gpu")
            scores_original.append(rr_orig.score)
        except Exception:
            scores_original.append(0.0)

        # CORAL-translated features → CPU model (use model's own feature names)
        # Build features dict from aligned array, matching CPU model's expected names
        feats_aligned = {}
        for j, fn in enumerate(coral_feats):
            feats_aligned[fn] = float(X_aligned[i, j])
        try:
            rr_cpu = router.predict(feats_aligned, engine="cpu")
            scores_aligned.append(rr_cpu.score)
        except Exception:
            scores_aligned.append(0.0)

        vina_scores.append(abs(r["vina_score"]))
        labels.append(r.get("is_active", False))

    # Filter zeros (failed predictions)
    valid_orig = [(s, l) for s, l in zip(scores_original, labels) if s != 0]
    valid_aligned = [(s, l) for s, l in zip(scores_aligned, labels) if s != 0]

    auc_vina = roc_auc_score(labels, vina_scores) if len(set(labels)) > 1 else 0.5
    auc_orig = roc_auc_score([l for _, l in valid_orig], [s for s, _ in valid_orig]) if valid_orig and len(set([l for _, l in valid_orig])) > 1 else 0.5
    auc_aligned = roc_auc_score([l for _, l in valid_aligned], [s for s, _ in valid_aligned]) if valid_aligned and len(set([l for _, l in valid_aligned])) > 1 else 0.5

    print(f"\nValidation ({len(gpu_valid)} molecules):")
    print(f"  Vina-only (GPU):       ROC-AUC = {auc_vina:.4f}")
    print(f"  GPU model (original):   ROC-AUC = {auc_orig:.4f}")
    print(f"  CORAL -> CPU model:      ROC-AUC = {auc_aligned:.4f}")
    print(f"  Delta (CORAL vs GPU):   {auc_aligned - auc_orig:+.4f}")

    return {
        "n_molecules": len(gpu_valid),
        "auc_vina": auc_vina,
        "auc_gpu_model": auc_orig,
        "auc_coral_cpu": auc_aligned,
        "delta": auc_aligned - auc_orig,
    }


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="CORAL GPU→CPU Feature Translator")
    sub = parser.add_subparsers(dest="cmd")

    train_p = sub.add_parser("train", help="Train CORAL from checkpoints")
    train_p.add_argument("--gpu-ck", type=str, default="data/benchmark_checkpoint_factor_xa.json")
    train_p.add_argument("--cpu-ck", type=str, default="data/benchmark_checkpoint_factor_xa_CPU.json")

    val_p = sub.add_parser("validate", help="Validate CORAL on a checkpoint")
    val_p.add_argument("--ck", type=str, default="data/benchmark_checkpoint_cdk2.json")

    args = parser.parse_args()

    if args.cmd == "train":
        ct = train_from_checkpoints(
            PROJECT_ROOT / args.gpu_ck,
            PROJECT_ROOT / args.cpu_ck,
        )
        # Quick validation
        if Path(PROJECT_ROOT / args.gpu_ck).exists():
            validate_translator(ct, PROJECT_ROOT / args.gpu_ck)

    elif args.cmd == "validate":
        ct = CoralTranslator().load()
        validate_translator(ct, PROJECT_ROOT / args.ck)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
