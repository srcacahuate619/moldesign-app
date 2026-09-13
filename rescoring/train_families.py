"""
train_families.py — Reentrenamiento XGBoost por familia estructural.

Pipeline:
  1. Carga feature_cache_v4 (features 3D: Grupos C, D, E)
  2. Extrae SMILES de ligand SDF/MOL2 → calcula features 1D/2D (Grupo A)
  3. Clasifica complejos por familia via family_map.json
  3.5. Excluye el frozen test set (holdout) del pool de entrenamiento (P0-SCI)
  4. Entrena 1 modelo universal + 5 modelos por familia (≥15 complejos)
  5. Guarda .joblib en artifacts/

Nota de protocolo: este script usa un split aleatorio 80/20 para train/val.
La exclusion del holdout (paso 3.5) garantiza disjuncion con el test set
independiente; el scaffold-split CV canónico vive en train_orchestrator.py.

Fix #3 (Julio 2026): ProLIF interaction counts (9 features) removidos del feature set.
Las features Vina (Grupo B, 4 features) se incluyen porque 540/692 complejos fueron
re-dockeados con AutoDock Vina. Los restantes usan la media del dataset.
"""

import json
import logging
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from train_pipeline import ALL_FEATURES, MLTrainer

# ALL_FEATURES = 167 features (A_EXT 8 + B 4 + C_EXT 3 + D 96 + E 56)
# Fix #3: ProLIF interaction counts (9 features) removidos.
# Incluye Vina features (Grupo B) porque la inferencia siempre las provee.

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("train_families")

CACHE_DIR = Path("../data/pdbbind/feature_cache_v4")
PDBBIND_DIR = Path("../data/pdbbind")  # Subdirectorios {pdb_id}/ con ligand SDF/MOL2
INDEX_PATH = Path("../data/pdbbind/INDEX_refined_data.2020")
ARTIFACTS = Path("artifacts")
FAMILY_MAP_PATH = ARTIFACTS / "family_map.json"
SPLIT_CONFIG_PATH = ARTIFACTS / "split_config.json"
MIN_FAMILY_SIZE = 15
SEED = 42


def load_frozen_test_ids(split_config_path: Path) -> set[str]:
    """Cargar el frozen test set (holdout) desde split_config.json.

    Estos IDs son el test set independiente (327 complejos PDBbind) creado por
    data_splitter.create_frozen_test_set. NO deben participar en el entrenamiento
    de ningun modelo: garantizar la disjuncion train/test es requisito de validez
    cientifica. Sin esta exclusion las metricas holdout quedan contaminadas por
    leakage (el modelo ya vio esos complejos al entrenar).
    """
    if not split_config_path.exists():
        log.warning("split_config.json not found at %s — holdout exclusion OMITIDA", split_config_path)
        return set()
    with open(split_config_path) as f:
        cfg = json.load(f)
    frozen = {str(pid).lower() for pid in cfg.get("frozen_test_set", [])}
    log.info("Loaded %d frozen test IDs (holdout) from split_config.json", len(frozen))
    return frozen


def parse_index(index_path: Path) -> dict[str, float]:
    """Parsear INDEX_refined_data.2020 → {pdb_id: pKi}."""
    pki_map: dict[str, float] = {}
    if not index_path.exists():
        log.warning("INDEX not found at %s", index_path)
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
                    pki = float(parts[-1])
                    pki_map[pdb_id] = pki
                except ValueError:
                    pass
    log.info("Parsed %d pKi values from INDEX", len(pki_map))
    return pki_map


def load_cached_3d_features(cache_dir: Path) -> dict[str, dict[str, float]]:
    """Cargar features 3D desde JSON cache files.

    Returns:
        {pdb_id: {feature_name: value, ...}}
    """
    features: dict[str, dict[str, float]] = {}
    json_files = sorted(cache_dir.glob("*.json"))

    if not json_files:
        log.warning("No JSON cache files found in %s", cache_dir)
        return features

    for cache_file in json_files:
        try:
            with open(cache_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Failed to read %s: %s", cache_file.name, e)
            continue

        pdb_id = cache_file.stem.upper()
        feats = data.get("features", data)
        if isinstance(feats, dict):
            features[pdb_id] = {k: float(v) for k, v in feats.items()}

    log.info("Loaded 3D features for %d complexes from %d cache files",
             len(features), len(json_files))
    return features


def extract_smiles_from_ligand(pdb_id: str) -> str | None:
    """Extraer SMILES del archivo SDF o MOL2 del ligando.

    Busca en data/pdbbind/{pdb_id}/{pdb_id}_ligand.sdf (.mol2).
    """
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


def compute_1d2d_features(smiles: str) -> dict[str, float]:
    """Calcular descriptores 1D/2D desde SMILES con RDKit.

    Retorna features del Grupo A_EXT: mw, logp, tpsa, hbd, hba,
    rotatable_bonds, qed, log_mw, heavy_atom_count.
    """
    from rdkit import Chem
    from rdkit.Chem import QED as QEDModule
    from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {}

    ha = Descriptors.HeavyAtomCount(mol)

    return {
        "mw": float(Descriptors.MolWt(mol)),
        "logp": float(Crippen.MolLogP(mol)),
        "tpsa": float(rdMolDescriptors.CalcTPSA(mol)),
        "hbd": float(rdMolDescriptors.CalcNumHBD(mol)),
        "hba": float(rdMolDescriptors.CalcNumHBA(mol)),
        "rotatable_bonds": float(rdMolDescriptors.CalcNumRotatableBonds(mol)),
        "qed": float(QEDModule.qed(mol)),
        "log_mw": math.log(max(float(Descriptors.MolWt(mol)), 1.0)),
        "heavy_atom_count": float(ha),
    }


def enrich_features_with_1d2d(
    pdb_ids: list[str],
    features_3d: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    """Enriquecer features 3D con descriptores 1D/2D extraídos de SMILES.

    También calcula features derivadas (contacts_per_ha_4A/6A).
    """
    enriched: dict[str, dict[str, float]] = {}
    missing_smiles = 0
    total = len(pdb_ids)

    for pid in pdb_ids:
        # Copiar features 3D existentes
        feats = dict(features_3d.get(pid, {}))

        # Extraer SMILES y calcular 1D/2D
        smiles = extract_smiles_from_ligand(pid)
        if smiles:
            feats_1d2d = compute_1d2d_features(smiles)
            feats.update(feats_1d2d)

            ha = feats.get("heavy_atom_count", 1.0)
            if ha > 0:
                if "close_contacts_4A" in feats:
                    feats["contacts_per_ha_4A"] = feats["close_contacts_4A"] / ha
                if "close_contacts_6A" in feats:
                    feats["contacts_per_ha_6A"] = feats["close_contacts_6A"] / ha
        else:
            missing_smiles += 1

        enriched[pid] = feats

    log.info("Enriched features: %d/%d complexes have 1D/2D features (%d missing SMILES)",
             total - missing_smiles, total, missing_smiles)

    # Report feature coverage
    from train_pipeline import (
        FEATURE_GROUP_A_EXT,
        FEATURE_GROUP_B,
        FEATURE_GROUP_C_EXT,
        FEATURE_GROUP_D,
        FEATURE_GROUP_E,
    )
    sample_keys = set()
    for feats in enriched.values():
        sample_keys.update(feats.keys())

    log.info("Feature group coverage (after enrichment):")
    for group_name, group_features in [
        ("A_ext (1D/2D)", FEATURE_GROUP_A_EXT),
        ("B (Vina)", FEATURE_GROUP_B),
        ("C_ext (size-norm, ProLIF removido fix#3)", FEATURE_GROUP_C_EXT),
        ("D (Shell)", FEATURE_GROUP_D),
        ("E (ECIF)", FEATURE_GROUP_E),
    ]:
        present = sum(1 for f in group_features if f in sample_keys)
        missing = sum(1 for f in group_features if f not in sample_keys)
        log.info("  %-25s: %d/%d present, %d missing",
                 group_name, present, len(group_features), missing)

    return enriched


def load_family_map(family_map_path: Path) -> dict[str, str]:
    """Cargar family_map.json → {pdb_id: family}."""
    if not family_map_path.exists():
        log.warning("family_map.json not found at %s", family_map_path)
        return {}
    with open(family_map_path) as f:
        family_map = json.load(f)
    log.info("Loaded family_map with %d entries", len(family_map))
    return family_map


def build_feature_matrix(
    pdb_ids: list[str],
    features: dict[str, dict[str, float]],
    feature_names: list[str],
    max_missing_frac: float = 0.25,
) -> tuple[np.ndarray, list[str], list[dict]]:
    """Construir matriz de features (n_samples, n_features) — contrato A2.

    Regla de imputación EXPLÍCITA (nunca silenciosa):
      1. Complejo que falta > `max_missing_frac` features del contrato
         (167) → EXCLUIDO del entrenamiento, logueado con su pdb_id y la
         lista de features faltantes (sale en el reporte).
      2. Features puntuales faltantes en complejos retenidos → imputadas
         con la MEDIA del dataset (regla documentada en el header del
         script, ahora implementada de verdad — antes llenaba con 0.0).
      3. Una feature ausente en TODOS los complejos viables → 0.0 con
         warning explícito (no hay distribución de dónde imputar).

    Returns:
        (X, kept_ids, excluded) donde excluded es una lista de dicts
        {"pdb_id", "n_missing", "missing": [feature_names...]}.
    """
    n = len(pdb_ids)
    m = len(feature_names)
    name_set = set(feature_names)

    kept_ids: list[str] = []
    excluded: list[dict] = []
    for pid in pdb_ids:
        feats = features.get(pid, {})
        missing = [fname for fname in feature_names if fname not in feats]
        n_missing = len(missing)
        if n_missing > max(0, int(m * max_missing_frac)):
            excluded.append({
                "pdb_id": pid,
                "n_missing": n_missing,
                "missing": missing,
            })
            log.info("complex_excluded_feature_gap | pdb_id=%s | n_missing=%d | missing=%s",
                     pid, n_missing, missing[:10])
        else:
            kept_ids.append(pid)

    if not kept_ids:
        return np.zeros((0, m), dtype=np.float64), [], excluded

    # Medias por feature sobre complejos que SÍ la tienen
    present_counts = np.zeros(m, dtype=np.float64)
    present_sums = np.zeros(m, dtype=np.float64)
    for pid in kept_ids:
        feats = features.get(pid, {})
        for j, fname in enumerate(feature_names):
            if fname in feats:
                present_counts[j] += 1
                present_sums[j] += float(feats[fname])
    feature_means = np.where(present_counts > 0, present_sums / np.maximum(present_counts, 1), 0.0)
    for j, fname in enumerate(feature_names):
        if present_counts[j] == 0:
            log.warning("feature_absent_everywhere_imputed_zero | feature=%s | n_complexes=%d",
                        fname, len(kept_ids))

    X = np.zeros((len(kept_ids), m), dtype=np.float64)
    for i, pid in enumerate(kept_ids):
        feats = features.get(pid, {})
        for j, fname in enumerate(feature_names):
            if fname in feats:
                X[i, j] = float(feats[fname])
            else:
                X[i, j] = feature_means[j]

    log.info("build_feature_matrix_contract | n_requested=%d | n_kept=%d | n_excluded=%d | n_features=%d | imputation=dataset_mean",
             len(pdb_ids), len(kept_ids), len(excluded), m)
    return X, kept_ids, excluded


def train_and_save(
    trainer: MLTrainer,
    pdb_ids: list[str],
    features: dict[str, dict[str, float]],
    labels: dict[str, float],
    family_name: str,
    feature_names: list[str] | None = None,
) -> None:
    """Entrenar y guardar un modelo para una familia especifica."""
    if feature_names is None:
        feature_names = ALL_FEATURES
    n = len(pdb_ids)
    log.info("Training %s model with %d complexes (%d features)", family_name, n, len(feature_names))

    np.random.seed(SEED)
    shuffled = list(pdb_ids)
    np.random.shuffle(shuffled)
    split = max(5, int(n * 0.8))
    train_ids = shuffled[:split]
    val_ids = shuffled[split:]

    X_train, train_kept, train_excluded = build_feature_matrix(train_ids, features, feature_names)
    if len(train_kept) == 0:
        log.warning("family_all_excluded | family=%s | reason=feature contract gap", family_name)
        return
    # Delta-learning: pKi = Vina_pKi + delta → train on delta
    y_train = np.array([
        labels.get(pid, 0.0) - (-features.get(pid, {}).get("vina_best_score", 0.0) / 1.36)
        for pid in train_kept
    ])
    X_val, val_kept, val_excluded = build_feature_matrix(val_ids, features, feature_names)
    y_val = np.array([
        labels.get(pid, 0.0) - (-features.get(pid, {}).get("vina_best_score", 0.0) / 1.36)
        for pid in val_kept
    ])
    if len(val_kept) == 0:
        log.warning("family_val_all_excluded | family=%s | reason=feature contract gap", family_name)
        val_kept = list(train_kept)
        X_val = X_train
        y_val = y_train

    model = trainer.train_model(
        X_train, y_train, [1] * len(train_kept),
        X_val, y_val, [1] * len(val_kept),
        feature_names, f"model_a_{family_name}",
    )

    out_path = ARTIFACTS / f"model_a_{family_name}.joblib"
    # Inject delta_model flag into artifact before saving
    model.params["is_delta_model"] = True
    trainer.save_model(model, out_path)

    spearman = model.metrics.get("spearman", 0.0)
    pval = model.metrics.get("spearman_pval", 1.0)
    n_excluded = len(train_excluded) + len(val_excluded)
    log.info("  %s: Spearman=%.4f (p=%.4f), %d samples (%d excluidos por gap de features)",
             family_name, spearman, pval, len(train_kept) + len(val_kept), n_excluded)
    if n_excluded:
        excluded_ids = sorted(e["pdb_id"] for e in train_excluded + val_excluded)
        log.info("  %s excluded complexes (contrato A2): %s",
                 family_name, ", ".join(excluded_ids[:20]) + ("..." if n_excluded > 20 else ""))


def main() -> int:
    log.info("=" * 60)
    log.info("  FAMILY-SPECIFIC XGBOOST TRAINING (v2 — SMILES enrichment)")
    log.info("=" * 60)

    # 1. Load pKi labels
    log.info("\nStep 1: Loading pKi labels from INDEX...")
    labels = parse_index(INDEX_PATH)
    if not labels:
        log.error("No labels found. Aborting.")
        return 1

    # 2. Load 3D features from cache
    log.info("\nStep 2: Loading 3D features from feature_cache_v4...")
    features_3d = load_cached_3d_features(CACHE_DIR)
    if not features_3d:
        log.error("No features found in cache. Aborting.")
        return 1

    # 3. Cross-reference: pdb_ids with BOTH features AND labels
    valid_ids = [pid for pid in features_3d if pid in labels]
    log.info("Complexes with 3D features + pKi labels: %d", len(valid_ids))

    # 3.5. EXCLUIR el frozen test set (holdout) del pool de entrenamiento.
    # Garantia de disjuncion train/test: el modelo nunca debe ver los complejos
    # del test set independiente. Sin esto, cualquier metrica "holdout" esta
    # contaminada por leakage. (P0-SCI fix)
    frozen_test_ids = load_frozen_test_ids(SPLIT_CONFIG_PATH)
    if frozen_test_ids:
        n_before = len(valid_ids)
        valid_ids = [pid for pid in valid_ids if pid.lower() not in frozen_test_ids]
        log.info("Excluded %d frozen-test (holdout) complexes from training pool: %d -> %d",
                 n_before - len(valid_ids), n_before, len(valid_ids))

    # 4. Enrich with 1D/2D features from ligand SMILES
    log.info("\nStep 3: Extracting SMILES + computing 1D/2D features...")
    features = enrich_features_with_1d2d(valid_ids, features_3d)

    # 5. Load family classification
    log.info("\nStep 4: Loading family classifications...")
    family_map = load_family_map(FAMILY_MAP_PATH)
    if not family_map:
        log.error("family_map.json not found. Run structural family classification first.")
        return 1

    # 6. Group by family
    by_family: dict[str, list[str]] = {}
    for pid in valid_ids:
        fam = family_map.get(pid, family_map.get(pid.lower(), "other"))
        by_family.setdefault(fam, []).append(pid)

    log.info("\nFamily distribution (with features + labels):")
    for fam, ids in sorted(by_family.items(), key=lambda x: -len(x[1])):
        viable = " [VIABLE]" if len(ids) >= MIN_FAMILY_SIZE else ""
        log.info("  %-25s: %4d complexes%s", fam, len(ids), viable)

    # 7. Initialize trainer
    trainer = MLTrainer(seed=SEED)

    # 8. Train universal model
    log.info("\nStep 5: Training UNIVERSAL model (%d complexes)...", len(valid_ids))
    try:
        train_and_save(trainer, valid_ids, features, labels, "universal")
    except Exception as e:
        log.error("UNIVERSAL training failed: %s", e, exc_info=True)

    # 9. Train per-family models
    family_order = ["kinase", "protease", "gpcr", "nuclear_receptor", "soluble_enzyme"]
    for fam in family_order:
        fam_ids = by_family.get(fam, [])
        if len(fam_ids) < MIN_FAMILY_SIZE:
            log.info("\nSKIP %s — %d < %d minimum", fam, len(fam_ids), MIN_FAMILY_SIZE)
            continue

        log.info("\nTraining %s model (%d complexes)...", fam, len(fam_ids))
        try:
            train_and_save(trainer, fam_ids, features, labels, fam)
        except Exception as e:
            log.error("%s training failed: %s", fam, e, exc_info=True)

    # 10. Summary
    log.info("\n" + "=" * 60)
    log.info("  TRAINING COMPLETE")
    saved = sorted(ARTIFACTS.glob("model_a_*.joblib"))
    for p in saved:
        size_kb = p.stat().st_size / 1024
        log.info("  %s (%.1f KB)", p.name, size_kb)
    log.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
