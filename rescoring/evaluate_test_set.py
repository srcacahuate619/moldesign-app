"""
evaluate_test_set.py — Evaluacion del modelo universal en el frozen test set.

Evalua el modelo universal (model_a_universal.json, 167 features) en los
327 complejos del test set holdout definidos en split_config.json.

Los complejos del test set fueron separados ANTES de cualquier entrenamiento
y NUNCA fueron vistos por el modelo. Esta evaluacion complementa las metricas
de validacion cruzada (CV) con una metrica independiente.

Uso:
    cd rescoring
    python evaluate_test_set.py

Salida: Spearman rho, Pearson r, RMSE, MAE + Bootstrap 95% CI (10,000 iter)
        + desglose por familia proteica (si family_map.json disponible).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import pearsonr, spearmanr

# ── Paths (relativos a rescoring/) ──────────────────────────────────────────
SPLIT_CONFIG = Path("artifacts/split_config.json")
FEATURE_CACHE = Path("../data/pdbbind/feature_cache_v4")
PDBBIND_DIR = Path("../data/pdbbind")
INDEX_PATH = Path("../data/pdbbind/INDEX_refined_data.2020")
MODEL_JSON = Path("artifacts/model_a_universal.json")
MODEL_META = Path("artifacts/model_a_universal.metadata.json")
FAMILY_MAP = Path("artifacts/family_map.json")

# ── Feature names (deben matchear train_pipeline.ALL_FEATURES) ────────────────
FEATURE_GROUP_A_EXT = [
    "mw", "logp", "tpsa", "hbd", "hba", "rotatable_bonds", "qed", "log_mw",
]
FEATURE_GROUP_B = [
    "vina_best_score", "pose_score_variance", "pose_score_range", "poses_passing_ratio",
]
FEATURE_GROUP_C_EXT = [
    "heavy_atom_count", "contacts_per_ha_4A", "contacts_per_ha_6A",
]
SHELL_PROTEIN_ELEMS = ["C", "N", "O", "S"]
SHELL_LIGAND_ELEMS = ["C", "N", "O", "S", "F", "P", "Cl", "Br"]
SHELL_DISTANCES = ["0_4", "4_8", "8_12"]
FEATURE_GROUP_D = [
    f"shell_{pe}_{le}_{d}"
    for pe in SHELL_PROTEIN_ELEMS
    for le in SHELL_LIGAND_ELEMS
    for d in SHELL_DISTANCES
]
ECIF_PROTEIN_TYPES = [
    "C_ali", "C_aro", "N_don", "N_acc", "O_don", "O_acc", "S", "other",
]
ECIF_LIGAND_ELEMS = ["C", "N", "O", "S", "F", "Hal", "other"]
FEATURE_GROUP_E = [
    f"ecif_{pt}_{le}"
    for pt in ECIF_PROTEIN_TYPES
    for le in ECIF_LIGAND_ELEMS
]

ALL_FEATURES = (
    FEATURE_GROUP_A_EXT
    + FEATURE_GROUP_B
    + FEATURE_GROUP_C_EXT
    + FEATURE_GROUP_D
    + FEATURE_GROUP_E
)
assert len(ALL_FEATURES) == 167, f"Expected 167 features, got {len(ALL_FEATURES)}"

# ── Bootstrap CI helper ──────────────────────────────────────────────────────

def bootstrap_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_iter: int = 10_000,
    alpha: float = 0.05,
    statistic: str = "spearman",
) -> tuple[float, float]:
    """Bootstrap percentile CI para Spearman rho o Pearson r."""
    rng = np.random.default_rng(42)
    n = len(y_true)
    stats = np.empty(n_iter, dtype=np.float64)
    for i in range(n_iter):
        idx = rng.integers(0, n, n)
        t = y_true[idx]
        p = y_pred[idx]
        if statistic == "spearman":
            stats[i] = spearmanr(t, p).correlation
        elif statistic == "pearson":
            stats[i] = pearsonr(t, p)[0]
    lo = np.percentile(stats, 100 * alpha / 2)
    hi = np.percentile(stats, 100 * (1 - alpha / 2))
    return float(lo), float(hi)


# ── Data loading ─────────────────────────────────────────────────────────────

def load_test_ids(config_path: Path) -> list[str]:
    with open(config_path) as f:
        config = json.load(f)
    ids = config["frozen_test_set"]
    print(f"  Test set IDs: {len(ids)}")
    return ids


def parse_index(index_path: Path) -> dict[str, float]:
    pki_map: dict[str, float] = {}
    if not index_path.exists():
        print(f"  ERROR: INDEX not found at {index_path}")
        return pki_map
    with open(index_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 6:
                pdb_id = parts[0].upper()
                try:
                    pki_map[pdb_id] = float(parts[-1])
                except ValueError:
                    pass
    print(f"  pKi labels loaded: {len(pki_map)}")
    return pki_map


def load_3d_features(cache_dir: Path) -> dict[str, dict[str, float]]:
    features: dict[str, dict[str, float]] = {}
    json_files = sorted(cache_dir.glob("*.json"))
    if not json_files:
        print(f"  ERROR: No cache files in {cache_dir}")
        return features
    for cache_file in json_files:
        try:
            with open(cache_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        pdb_id = cache_file.stem.upper()
        feats = data.get("features", data)
        if isinstance(feats, dict):
            features[pdb_id] = {k: float(v) for k, v in feats.items()}
    print(f"  3D features loaded: {len(features)} complexes")
    return features


def load_family_map() -> dict[str, str] | None:
    if not FAMILY_MAP.exists():
        return None
    with open(FAMILY_MAP) as f:
        return json.load(f)


# ── 1D/2D feature computation from SMILES ────────────────────────────────────

def extract_smiles(pdb_id: str) -> str | None:
    from rdkit import Chem
    pdb_lower = pdb_id.lower()
    complex_dir = PDBBIND_DIR / pdb_lower
    if not complex_dir.is_dir():
        return None
    for ext in [".sdf", ".mol2"]:
        ligand_path = complex_dir / f"{pdb_lower}_ligand{ext}"
        if not ligand_path.exists():
            continue
        try:
            if ext == ".sdf":
                supplier = Chem.SDMolSupplier(str(ligand_path), sanitize=True)
                for mol in supplier:
                    if mol is not None:
                        return Chem.MolToSmiles(mol)
            elif ext == ".mol2":
                mol = Chem.MolFromMol2File(str(ligand_path), sanitize=True)
                if mol is not None:
                    return Chem.MolToSmiles(mol)
        except Exception:
            continue
    return None


def compute_1d2d(smiles: str) -> dict[str, float]:
    from rdkit import Chem
    from rdkit.Chem import QED as QEDModule
    from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {}
    mw = float(Descriptors.MolWt(mol))
    return {
        "mw": mw,
        "logp": float(Crippen.MolLogP(mol)),
        "tpsa": float(rdMolDescriptors.CalcTPSA(mol)),
        "hbd": float(rdMolDescriptors.CalcNumHBD(mol)),
        "hba": float(rdMolDescriptors.CalcNumHBA(mol)),
        "rotatable_bonds": float(rdMolDescriptors.CalcNumRotatableBonds(mol)),
        "qed": float(QEDModule.qed(mol)),
        "log_mw": math.log(max(mw, 1.0)),
        "heavy_atom_count": float(Descriptors.HeavyAtomCount(mol)),
    }


def enrich_features(
    pdb_ids: list[str], features_3d: dict[str, dict[str, float]]
) -> dict[str, dict[str, float]]:
    enriched: dict[str, dict[str, float]] = {}
    missing = 0
    for pid in pdb_ids:
        feats = dict(features_3d.get(pid, {}))
        smiles = extract_smiles(pid)
        if smiles:
            feats.update(compute_1d2d(smiles))
        else:
            missing += 1
        ha = feats.get("heavy_atom_count", 1.0)
        if ha > 0:
            feats.setdefault("contacts_per_ha_4A", feats.get("close_contacts_4A", 0.0) / ha)
            feats.setdefault("contacts_per_ha_6A", feats.get("close_contacts_6A", 0.0) / ha)
        else:
            feats.setdefault("contacts_per_ha_4A", 0.0)
            feats.setdefault("contacts_per_ha_6A", 0.0)
        enriched[pid] = feats
    if missing:
        print(f"  Missing SMILES for {missing} complexes (features will be incomplete)")
    return enriched


# ── Prediction ──────────────────────────────────────────────────────────────

def build_matrix(
    pdb_ids: list[str], features: dict[str, dict[str, float]], feature_names: list[str]
) -> np.ndarray:
    """Construir matriz de features (n, m).
    [A2] SIN zero-padding (era feats.get(fname, 0.0)): valores ausentes/
    no-finitos se imputan con la media de la columna sobre los presentes.
    Columna completa ausente → ValueError (contrato roto, no fabricación)."""
    n, m = len(pdb_ids), len(feature_names)
    X = np.zeros((n, m), dtype=np.float64)
    miss_rows: list[list[int]] = [[] for _ in range(m)]
    present_vals: list[list[float]] = [[] for _ in range(m)]

    for i, pid in enumerate(pdb_ids):
        feats = features.get(pid, {})
        for j, fname in enumerate(feature_names):
            val = feats.get(fname)
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
                f"build_matrix_contract_violation: columna '{fname}' ausente en "
                "todos los complejos; no imputable (config rota, no zero-pad)."
            )
        col_mean = float(np.mean(present_vals[j]))
        for i in miss_rows[j]:
            X[i, j] = col_mean
        print(f"  [WARN build_matrix_imputation] feature={fname} "
              f"n_missing={len(miss_rows[j])} n_present={len(present_vals[j])} mean={col_mean:.4f}")

    return X


def load_model(model_path: Path) -> tuple:
    import xgboost as xgb
    model = xgb.Booster()
    model.load_model(str(model_path))
    with open(model_path.with_suffix(".metadata.json")) as f:
        meta = json.load(f)
    feature_names = meta.get("feature_names", ALL_FEATURES)
    # Delta-learning detection: metadata params first, then booster attr/params
    # fallback (the trainer injects is_delta_model=True before save_model).
    is_delta = meta.get("params", {}).get("is_delta_model", False)
    if not is_delta:
        try:
            is_delta = bool(model.attr("is_delta_model")) or str(
                model.params.get("is_delta_model", "")
            ).lower() in ("1", "true", "yes")
        except Exception:
            is_delta = False
    return model, feature_names, is_delta


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 60)
    print("  EVALUACION DEL TEST SET HOLDOUT")
    print("  Modelo: model_a_universal (167 features, delta-learning)")
    print("=" * 60)

    # 1. Load test set IDs
    print("\n[1/7] Cargando test set IDs...")
    test_ids = load_test_ids(SPLIT_CONFIG)

    # 2. Load pKi labels
    print("\n[2/7] Cargando pKi labels...")
    labels = parse_index(INDEX_PATH)

    # 3. Load 3D features
    print("\n[3/7] Cargando features 3D del cache...")
    features_3d = load_3d_features(FEATURE_CACHE)

    # 4. Cross-reference
    test_ids_upper = [pid.upper() for pid in test_ids]
    valid_ids = [pid for pid in test_ids_upper if pid in features_3d and pid in labels]
    missing_feats = [pid for pid in test_ids_upper if pid not in features_3d]
    missing_labels = [pid for pid in test_ids_upper if pid in features_3d and pid not in labels]
    print(f"\n  Test IDs: {len(test_ids)}")
    print(f"  Con features + labels: {len(valid_ids)}")
    print(f"  Sin features: {len(missing_feats)}")
    if missing_feats:
        print(f"    IDs: {', '.join(sorted(missing_feats))}")
    print(f"  Sin pKi: {len(missing_labels)}")

    if len(valid_ids) < 10:
        print("  ERROR: Muy pocos complejos validos (< 10). Abortando.")
        return 1

    # 5. Enrich with 1D/2D features
    print("\n[4/7] Enriqueciendo con features 1D/2D desde SMILES...")
    features = enrich_features(valid_ids, features_3d)

    # 6. Load model
    print("\n[5/7] Cargando modelo...")
    model, model_feature_names, is_delta = load_model(MODEL_JSON)
    print(f"  Features del modelo: {len(model_feature_names)}")
    print(f"  Delta-learning: {is_delta}")

    # 7. Build matrix and predict
    print("\n[6/7] Construyendo matriz y prediciendo...")
    X = build_matrix(valid_ids, features, model_feature_names)
    dmatrix = __import__("xgboost").DMatrix(X, feature_names=model_feature_names)
    delta_preds = model.predict(dmatrix)

    # Delta-learning reconstruction: pKi = vina_pKi + delta
    y_pred = np.zeros(len(valid_ids))
    y_true = np.zeros(len(valid_ids))
    for i, pid in enumerate(valid_ids):
        y_true[i] = labels[pid]
        if is_delta:
            vina_score = features[pid].get("vina_best_score", 0.0)
            vina_pki = -vina_score / 1.36
            y_pred[i] = vina_pki + delta_preds[i]
        else:
            y_pred[i] = delta_preds[i]

    # 8. Global Metrics + Bootstrap CI
    print("\n[7/7] Calculando metricas + Bootstrap 95% CI (10,000 iter)...")
    rho, pval = spearmanr(y_true, y_pred)
    pearson_r, pearson_p = pearsonr(y_true, y_pred)
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    mae = float(np.mean(np.abs(y_true - y_pred)))

    rho_lo, rho_hi = bootstrap_ci(y_true, y_pred, n_iter=10_000, statistic="spearman")
    pearson_lo, pearson_hi = bootstrap_ci(y_true, y_pred, n_iter=10_000, statistic="pearson")

    print(f"\n{'=' * 60}")
    print(f"  RESULTADOS -- TEST SET HOLDOUT ({len(valid_ids)} complejos)")
    print(f"{'=' * 60}")
    print(f"  Spearman rho: {rho:.4f}  (p={pval:.6f})")
    print(f"    95% CI: [{rho_lo:.4f}, {rho_hi:.4f}]")
    print(f"  Pearson r:    {pearson_r:.4f}  (p={pearson_p:.6f})")
    print(f"    95% CI: [{pearson_lo:.4f}, {pearson_hi:.4f}]")
    print(f"  RMSE:         {rmse:.4f} pKi")
    print(f"  MAE:          {mae:.4f} pKi")
    print(f"  y_true range: [{y_true.min():.2f}, {y_true.max():.2f}]")
    print(f"  y_pred range: [{y_pred.min():.2f}, {y_pred.max():.2f}]")
    print()

    # Comparacion con CV
    print("  --- COMPARACION CV vs TEST SET ---")
    try:
        with open(MODEL_JSON.with_suffix(".metadata.json")) as _f:
            _cv_meta = json.load(_f)
        cv_spearman = float(_cv_meta.get("metrics", {}).get("spearman", float("nan")))
    except Exception:
        cv_spearman = float("nan")
    print(f"  CV (validation):    Spearman {cv_spearman:.4f} (reportado en metadata)")
    print(f"  Test set (holdout): Spearman {rho:.4f} [{rho_lo:.4f}, {rho_hi:.4f}]")
    if rho >= 0.7:
        print("  Veredicto: OK -- Buena generalizacion. El modelo transfiere al test set.")
    elif rho >= 0.5:
        print("  Veredicto: WARN -- Generalizacion moderada. Puede haber sobreajuste parcial.")
    else:
        print("  Veredicto: FAIL -- Generalizacion pobre. El modelo no transfiere a datos no vistos.")

    # Per-family breakdown
    family_map = load_family_map()
    if family_map:
        print("\n  --- DESGLOSE POR FAMILIA PROTEICA ---")
        families = {}
        for i, pid in enumerate(valid_ids):
            fam = family_map.get(pid, "unknown")
            families.setdefault(fam, {"y_true": [], "y_pred": [], "ids": []})
            families[fam]["y_true"].append(y_true[i])
            families[fam]["y_pred"].append(y_pred[i])
            families[fam]["ids"].append(pid)

        for fam, data in sorted(families.items()):
            n_fam = len(data["y_true"])
            if n_fam < 3:
                continue
            yt = np.array(data["y_true"])
            yp = np.array(data["y_pred"])
            rho_f, p_f = spearmanr(yt, yp)
            rmse_f = float(np.sqrt(np.mean((yt - yp) ** 2)))
            print(f"  {fam:20s} n={n_fam:3d}  rho={rho_f:.4f} (p={p_f:.4f})  RMSE={rmse_f:.3f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())