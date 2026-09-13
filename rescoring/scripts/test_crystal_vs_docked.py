#!/usr/bin/env python3
"""
Test 2: Crystal-vs-Docked Feature Degradation
==============================================

Core question: The ML model was trained on crystal-pose features
(PDBbind X-ray structures). In production, features come from
Vina-docked poses. How much does prediction quality degrade?

Pipeline per complex:
  1. Load experimental pKd from PDBbind INDEX
  2. Extract crystal features: pocket PDB + crystal ligand SDF → v4 3D features
  3. Prepare receptor PDBQT (OpenBabel from protein PDB)
  4. Prepare ligand PDBQT (meeko from crystal SDF via RDKit)
  5. Compute grid box from crystal ligand centroid
  6. Dock with Vina (exhaustiveness=8 for speed)
  7. Convert Vina best pose to SDF (meeko)
  8. Extract docked features: pocket PDB + docked SDF → v4 3D features
  9. Predict pKd with Model A using both crystal and docked features
  10. Compare Spearman correlations

Scientific limitations:
  - Receptor preparation via OpenBabel (less rigorous than ADFRsuite)
  - Grid box auto-computed from crystal ligand centroid (may differ from optimal)
  - Exhaustiveness=8 (lower than calibration) for throughput
  - Only tests holdout set complexes (not seen during training)
  - Feature extraction path identical for both (extract_from_files)

Author: MolDesign automated validation
"""

import json
import math
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

# ── Paths ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESCORING_DIR = PROJECT_ROOT / "rescoring"
BACKEND_ARTIFACTS = PROJECT_ROOT / "backend" / "artifacts"
PDBBIND_DIR = PROJECT_ROOT / "data" / "pdbbind"
VINA_EXE = PROJECT_ROOT / "tools" / "vina" / "vina.exe"
OUTPUT_DIR = PROJECT_ROOT / "data" / "test_crystal_vs_docked"

VINA_EXHAUSTIVENESS = 8   # Lower for throughput (50 complexes)
VINA_SEED = 42
VINA_NUM_MODES = 9
GRID_PADDING = 12.0  # Å padding around ligand centroid
N_COMPLEXES = 50       # Number of holdout complexes to test


def load_holdout_set() -> list[tuple[str, float]]:
    """Load frozen test set IDs and experimental pKd from PDBbind."""
    # Get holdout IDs from training split config
    split_config = PDBBIND_DIR / "artifacts" / "split_config.json"
    with open(split_config) as f:
        cfg = json.load(f)
    holdout_ids = set(cfg["frozen_test_set"])

    # Get pKd labels from INDEX file
    idx_file = PDBBIND_DIR / "INDEX_refined_data.2020"
    labels = {}
    with open(idx_file) as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.strip().split()
            if len(parts) >= 6:
                pdb_id = parts[0]
                pkd = float(parts[-1])
                labels[pdb_id] = pkd

    # Intersect holdout set with available complexes
    available = []
    for pdb_id in holdout_ids:
        if pdb_id not in labels:
            continue
        pdir = PDBBIND_DIR / pdb_id
        pocket = pdir / f"{pdb_id}_pocket.pdb"
        protein = pdir / f"{pdb_id}_protein.pdb"
        ligand = pdir / f"{pdb_id}_ligand.sdf"
        if pocket.exists() and protein.exists() and ligand.exists():
            available.append((pdb_id, labels[pdb_id]))

    print(f"Holdout set: {len(holdout_ids)} IDs, {len(available)} with all files")
    return available


def get_ligand_centroid(sdf_path: str) -> tuple[float, float, float] | None:
    """Compute centroid of ligand heavy atoms from SDF file."""
    from rdkit import Chem

    suppl = Chem.SDMolSupplier(sdf_path, removeHs=True)
    mol = next(suppl, None)
    if mol is None or mol.GetNumConformers() == 0:
        return None
    conf = mol.GetConformer()
    coords = np.array([conf.GetAtomPosition(i) for i in range(mol.GetNumAtoms())])
    centroid = coords.mean(axis=0)
    return tuple(centroid.tolist())


def prepare_receptor_pdbqt(protein_pdb: str, output_pdbqt: str) -> bool:
    """Convert protein PDB to PDBQT using OpenBabel."""
    from openbabel import openbabel

    conv = openbabel.OBConversion()
    conv.SetInFormat("pdb")
    conv.SetOutFormat("pdbqt")
    conv.AddOption("r", openbabel.OBConversion.OUTOPTIONS)  # rigid, no torsion tree

    mol = openbabel.OBMol()
    conv.ReadFile(mol, protein_pdb)
    if mol.NumAtoms() == 0:
        return False
    mol.AddHydrogens()
    conv.WriteFile(mol, output_pdbqt)
    return os.path.exists(output_pdbqt) and os.path.getsize(output_pdbqt) > 0


def prepare_ligand_pdbqt(sdf_path: str, output_pdbqt: str) -> bool:
    """Convert ligand SDF to PDBQT using RDKit + meeko."""
    from meeko import MoleculePreparation, PDBQTWriterLegacy
    from rdkit import Chem

    suppl = Chem.SDMolSupplier(sdf_path, removeHs=False)
    mol = next(suppl, None)
    if mol is None:
        return False

    # Ensure 3D coordinates are present
    if mol.GetNumConformers() == 0:
        return False

    # Add hydrogens if needed
    if not any(a.GetAtomicNum() == 1 for a in mol.GetAtoms()):
        mol = Chem.AddHs(mol, addCoords=True)

    try:
        preparator = MoleculePreparation()
        mol_setups = preparator.prepare(mol)
        pdbqt_result = PDBQTWriterLegacy.write_string(mol_setups[0])
        pdbqt_string = pdbqt_result[0] if isinstance(pdbqt_result, tuple) else pdbqt_result
        with open(output_pdbqt, "w") as f:
            f.write(pdbqt_string)
        return True
    except Exception as e:
        print(f"  [ERROR] meeko ligand prep failed: {e}")
        return False


def run_vina(
    ligand_pdbqt: str,
    receptor_pdbqt: str,
    output_pdbqt: str,
    log_path: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
) -> float | None:
    """Run AutoDock Vina and return best score."""
    cmd = [
        str(VINA_EXE),
        "--receptor", receptor_pdbqt,
        "--ligand", ligand_pdbqt,
        "--center_x", str(center[0]),
        "--center_y", str(center[1]),
        "--center_z", str(center[2]),
        "--size_x", str(size[0]),
        "--size_y", str(size[1]),
        "--size_z", str(size[2]),
        "--exhaustiveness", str(VINA_EXHAUSTIVENESS),
        "--num_modes", str(VINA_NUM_MODES),
        "--seed", str(VINA_SEED),
        "--out", output_pdbqt,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
        )
        with open(log_path, "w") as f:
            f.write(result.stdout)
            if result.stderr:
                f.write("\n--- STDERR ---\n")
                f.write(result.stderr)

        if result.returncode != 0:
            return None

        # Parse best score
        if os.path.exists(output_pdbqt):
            with open(output_pdbqt) as f:
                for line in f:
                    if line.startswith("REMARK VINA RESULT"):
                        return float(line.split()[3])
        return None
    except (subprocess.TimeoutExpired, Exception):
        return None


def extract_all_vina_scores(output_pdbqt: str) -> list[float]:
    """Extract all Vina scores from multi-model PDBQT output."""
    scores = []
    if os.path.exists(output_pdbqt):
        with open(output_pdbqt) as f:
            for line in f:
                if line.startswith("REMARK VINA RESULT"):
                    scores.append(float(line.split()[3]))
    return scores


def vina_output_to_sdf(full_pdbqt_content: str) -> str | None:
    """Convert Vina output PDBQT to SDF string (best pose via meeko)."""
    from meeko import PDBQTMolecule, RDKitMolCreate
    from rdkit import Chem

    try:
        pdbqt_mol = PDBQTMolecule(full_pdbqt_content, is_dlg=False, skip_typing=True)
        next(pdbqt_mol)  # Navigate to first pose (best score)
        rdkit_mols = RDKitMolCreate.from_pdbqt_mol(pdbqt_mol)
        if not rdkit_mols:
            return None
        return Chem.MolToMolBlock(rdkit_mols[0])
    except Exception as e:
        print(f"  [WARN] PDBQT→SDF failed: {e}")
        return None


def extract_features(pocket_pdb: str, sdf_path: str) -> dict[str, float]:
    """Extract v4 3D features using the training path."""
    if str(RESCORING_DIR) not in sys.path:
        sys.path.insert(0, str(RESCORING_DIR))
    from feature_extractor import InteractionFeatureExtractor
    extractor = InteractionFeatureExtractor()
    return extractor.extract_from_files(pocket_pdb, sdf_path)


def ml_predict(
    features_3d: dict[str, float],
    mol_properties: dict[str, float],
    vina_best_score: float,
    vina_scores: list[float],
    model_a_artifact: dict,
) -> float:
    """Run ML prediction with Model A. Returns predicted pKd."""
    import xgboost as xgb

    all_features = {
        "mw": mol_properties["mw"],
        "logp": mol_properties["logp"],
        "tpsa": mol_properties["tpsa"],
        "hbd": mol_properties["hbd"],
        "hba": mol_properties["hba"],
        "rotatable_bonds": mol_properties["rotatable_bonds"],
        "qed": mol_properties["qed"],
    }
    all_features.update(features_3d)
    all_features["vina_best_score"] = vina_best_score

    score_var = float(np.var(vina_scores)) if len(vina_scores) > 1 else 0.0
    score_range = float(max(vina_scores) - min(vina_scores)) if len(vina_scores) > 1 else 0.0
    all_features["pose_score_variance"] = score_var
    all_features["pose_score_range"] = score_range
    all_features["poses_passing_ratio"] = 1.0
    all_features["log_mw"] = math.log(max(mol_properties["mw"], 1.0))

    fn = model_a_artifact["feature_names"]
    vec = np.array([all_features.get(f, 0.0) for f in fn], dtype=np.float64)
    dm = xgb.DMatrix(vec.reshape(1, -1), feature_names=fn)
    return float(model_a_artifact["booster"].predict(dm)[0])


def compute_mol_properties(sdf_path: str) -> dict[str, float] | None:
    """Compute 1D/2D molecular properties from SDF."""
    from rdkit import Chem
    from rdkit.Chem import QED, Descriptors, rdMolDescriptors

    suppl = Chem.SDMolSupplier(sdf_path, removeHs=True)
    mol = next(suppl, None)
    if mol is None:
        return None

    return {
        "mw": Descriptors.MolWt(mol),
        "logp": Descriptors.MolLogP(mol),
        "tpsa": Descriptors.TPSA(mol),
        "hbd": float(rdMolDescriptors.CalcNumHBD(mol)),
        "hba": float(rdMolDescriptors.CalcNumHBA(mol)),
        "rotatable_bonds": float(rdMolDescriptors.CalcNumRotatableBonds(mol)),
        "qed": QED.qed(mol),
    }


def feature_rmsd(feat_a: dict, feat_b: dict, feature_names: list[str]) -> float:
    """Compute RMSD between two feature vectors (only 3D features)."""
    vals_a = np.array([feat_a.get(f, 0.0) for f in feature_names])
    vals_b = np.array([feat_b.get(f, 0.0) for f in feature_names])
    return float(np.sqrt(np.mean((vals_a - vals_b) ** 2)))


def count_nonzero_features(features: dict, feature_names: list[str]) -> int:
    """Count non-zero 3D features."""
    return sum(1 for f in feature_names if features.get(f, 0.0) != 0.0)


def main():
    """Main test execution."""
    from scipy.stats import spearmanr

    print("=" * 70)
    print("TEST 2: Crystal-vs-Docked Feature Degradation")
    print("=" * 70)
    print("Source: PDBbind v2020 holdout set")
    print(f"Complexes to test: {N_COMPLEXES}")
    print(f"Vina: exhaustiveness={VINA_EXHAUSTIVENESS}, seed={VINA_SEED}")
    print(f"Grid padding: {GRID_PADDING} Å")
    print()

    # ── Validate paths ───────────────────────────────────────
    assert VINA_EXE.exists(), f"Vina not found: {VINA_EXE}"

    # ── Load holdout set ─────────────────────────────────────
    available = load_holdout_set()
    print(f"Available complexes: {len(available)}")

    # Select subset: stratified by pKd range for diversity
    rng = np.random.RandomState(42)
    available_sorted = sorted(available, key=lambda x: x[1])
    # Take evenly spaced samples + some random
    n = min(N_COMPLEXES, len(available_sorted))
    indices = np.linspace(0, len(available_sorted) - 1, n, dtype=int)
    selected = [available_sorted[i] for i in indices]
    print(f"Selected {len(selected)} complexes (stratified by pKd: "
          f"{selected[0][1]:.2f} - {selected[-1][1]:.2f})")
    print()

    # ── Load ML model ────────────────────────────────────────
    import joblib
    model_a = joblib.load(BACKEND_ARTIFACTS / "model_a.joblib")
    feature_names = model_a["feature_names"]
    # Identify 3D-only features (exclude 1D/2D, vina, log_mw)
    exclude_1d2d = {"mw", "logp", "tpsa", "hbd", "hba", "rotatable_bonds", "qed",
                     "vina_best_score", "pose_score_variance", "pose_score_range",
                     "poses_passing_ratio", "log_mw"}
    feature_names_3d = [f for f in feature_names if f not in exclude_1d2d]
    print(f"Model A: {len(feature_names)} features total, {len(feature_names_3d)} 3D features")
    print()

    # ── Create output directory ──────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Process each complex ─────────────────────────────────
    results = []
    start_time = time.time()

    for i, (pdb_id, exp_pkd) in enumerate(selected):
        elapsed = time.time() - start_time
        print(f"[{i+1}/{len(selected)}] {pdb_id} (pKd={exp_pkd:.2f}) "
              f"[{elapsed:.0f}s elapsed]")

        pdir = PDBBIND_DIR / pdb_id
        pocket_pdb = str(pdir / f"{pdb_id}_pocket.pdb")
        protein_pdb = str(pdir / f"{pdb_id}_protein.pdb")
        ligand_sdf = str(pdir / f"{pdb_id}_ligand.sdf")

        # Create working directory
        work_dir = OUTPUT_DIR / pdb_id
        work_dir.mkdir(exist_ok=True)

        entry = {
            "pdb_id": pdb_id,
            "exp_pkd": exp_pkd,
            "crystal_pred": None,
            "docked_pred": None,
            "vina_score": None,
            "crystal_nonzero_3d": 0,
            "docked_nonzero_3d": 0,
            "feature_rmsd": None,
            "status": "started",
            "error": None,
        }

        try:
            # ── Step 1: Compute mol properties ───────────────
            mol_props = compute_mol_properties(ligand_sdf)
            if mol_props is None:
                entry["error"] = "Cannot compute mol properties"
                entry["status"] = "failed"
                results.append(entry)
                print(f"  FAIL: {entry['error']}")
                continue

            # ── Step 2: Extract crystal features ─────────────
            crystal_features = extract_features(pocket_pdb, ligand_sdf)
            crystal_nz = count_nonzero_features(crystal_features, feature_names_3d)
            entry["crystal_nonzero_3d"] = crystal_nz

            if crystal_nz == 0:
                entry["error"] = "Crystal features all zero"
                entry["status"] = "failed"
                results.append(entry)
                print("  FAIL: crystal features all zero")
                continue

            # ── Step 3: Compute ligand centroid → grid box ───
            centroid = get_ligand_centroid(ligand_sdf)
            if centroid is None:
                entry["error"] = "Cannot compute ligand centroid"
                entry["status"] = "failed"
                results.append(entry)
                print(f"  FAIL: {entry['error']}")
                continue

            grid_size = (GRID_PADDING * 2, GRID_PADDING * 2, GRID_PADDING * 2)

            # ── Step 4: Prepare receptor PDBQT ───────────────
            receptor_pdbqt = str(work_dir / "receptor.pdbqt")
            if not os.path.exists(receptor_pdbqt):
                ok = prepare_receptor_pdbqt(protein_pdb, receptor_pdbqt)
                if not ok:
                    entry["error"] = "Receptor PDBQT preparation failed"
                    entry["status"] = "failed"
                    results.append(entry)
                    print(f"  FAIL: {entry['error']}")
                    continue

            # ── Step 5: Prepare ligand PDBQT ─────────────────
            ligand_pdbqt = str(work_dir / "ligand.pdbqt")
            if not os.path.exists(ligand_pdbqt):
                ok = prepare_ligand_pdbqt(ligand_sdf, ligand_pdbqt)
                if not ok:
                    entry["error"] = "Ligand PDBQT preparation failed"
                    entry["status"] = "failed"
                    results.append(entry)
                    print(f"  FAIL: {entry['error']}")
                    continue

            # ── Step 6: Run Vina docking ─────────────────────
            output_pdbqt = str(work_dir / "output.pdbqt")
            log_path = str(work_dir / "vina.log")

            if not os.path.exists(output_pdbqt):
                t0 = time.time()
                vina_score = run_vina(
                    ligand_pdbqt, receptor_pdbqt, output_pdbqt,
                    log_path, centroid, grid_size,
                )
                dt = time.time() - t0
                print(f"  Vina: {vina_score} kcal/mol ({dt:.1f}s)")
            else:
                # Re-read existing result
                with open(output_pdbqt) as f:
                    for line in f:
                        if line.startswith("REMARK VINA RESULT"):
                            vina_score = float(line.split()[3])
                            break
                    else:
                        vina_score = None
                print(f"  Vina (cached): {vina_score} kcal/mol")

            if vina_score is None:
                entry["error"] = "Vina docking failed"
                entry["status"] = "failed"
                results.append(entry)
                print(f"  FAIL: {entry['error']}")
                continue

            entry["vina_score"] = vina_score
            vina_scores = extract_all_vina_scores(output_pdbqt)

            # ── Step 7: Convert Vina output to SDF ───────────
            with open(output_pdbqt) as f:
                full_pdbqt = f.read()

            sdf_block = vina_output_to_sdf(full_pdbqt)
            if sdf_block is None:
                entry["error"] = "PDBQT→SDF conversion failed"
                entry["status"] = "failed"
                results.append(entry)
                print(f"  FAIL: {entry['error']}")
                continue

            # Write docked SDF
            docked_sdf = str(work_dir / "docked.sdf")
            with open(docked_sdf, "w") as f:
                f.write(sdf_block)

            # ── Step 8: Extract docked features ──────────────
            docked_features = extract_features(pocket_pdb, docked_sdf)
            docked_nz = count_nonzero_features(docked_features, feature_names_3d)
            entry["docked_nonzero_3d"] = docked_nz

            # ── Step 9: Compute feature RMSD ─────────────────
            frmsd = feature_rmsd(crystal_features, docked_features, feature_names_3d)
            entry["feature_rmsd"] = frmsd

            # ── Step 10: ML predictions ──────────────────────
            # Crystal prediction: crystal features + docking vina/pose info
            crystal_pred = ml_predict(
                crystal_features, mol_props, vina_score, vina_scores, model_a,
            )
            entry["crystal_pred"] = crystal_pred

            # Docked prediction: docked features + same docking info
            docked_pred = ml_predict(
                docked_features, mol_props, vina_score, vina_scores, model_a,
            )
            entry["docked_pred"] = docked_pred

            entry["status"] = "success"
            print(f"  Crystal: {crystal_nz} nz-3D features → pred={crystal_pred:.2f}")
            print(f"  Docked:  {docked_nz} nz-3D features → pred={docked_pred:.2f}")
            print(f"  Feature RMSD: {frmsd:.4f}, |Δpred|={abs(crystal_pred - docked_pred):.3f}")

        except Exception as e:
            entry["error"] = str(e)
            entry["status"] = "error"
            print(f"  ERROR: {e}")

        results.append(entry)

    # ── Analysis ─────────────────────────────────────────────
    elapsed = time.time() - start_time
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)

    success = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] != "success"]
    print(f"Success: {len(success)}/{len(results)}")
    print(f"Failed: {len(failed)}")

    if len(success) < 5:
        print("TOO FEW SUCCESSES — cannot compute statistics")
        # Save whatever we have
        report = {"results": results, "n_success": len(success)}
        report_path = OUTPUT_DIR / "test_crystal_vs_docked_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        return

    # Extract arrays
    exp_vals = np.array([r["exp_pkd"] for r in success])
    crystal_preds = np.array([r["crystal_pred"] for r in success])
    docked_preds = np.array([r["docked_pred"] for r in success])
    vina_scores_arr = np.array([r["vina_score"] for r in success])
    feature_rmsds = np.array([r["feature_rmsd"] for r in success])
    crystal_nz_arr = np.array([r["crystal_nonzero_3d"] for r in success])
    docked_nz_arr = np.array([r["docked_nonzero_3d"] for r in success])

    # Spearman correlations
    rho_crystal, p_crystal = spearmanr(exp_vals, crystal_preds)
    rho_docked, p_docked = spearmanr(exp_vals, docked_preds)
    rho_vina, p_vina = spearmanr(exp_vals, -vina_scores_arr)  # Negate: more negative = better

    print()
    print("Spearman correlations with experimental pKd:")
    print(f"  Crystal features (Model A): ρ = {rho_crystal:.4f}  (p = {p_crystal:.4f})")
    print(f"  Docked features (Model A):  ρ = {rho_docked:.4f}  (p = {p_docked:.4f})")
    print(f"  Raw Vina score:             ρ = {rho_vina:.4f}  (p = {p_vina:.4f})")
    print()
    print(f"Degradation (Δρ): {rho_docked - rho_crystal:.4f} "
          f"({'improvement' if rho_docked > rho_crystal else 'degradation'})")

    # RMSE
    rmse_crystal = np.sqrt(np.mean((exp_vals - crystal_preds) ** 2))
    rmse_docked = np.sqrt(np.mean((exp_vals - docked_preds) ** 2))
    print("\nRMSE:")
    print(f"  Crystal: {rmse_crystal:.3f} pKd units")
    print(f"  Docked:  {rmse_docked:.3f} pKd units")

    # Feature quality stats
    print("\n3D Feature quality:")
    print(f"  Crystal non-zero: {crystal_nz_arr.mean():.1f} ± {crystal_nz_arr.std():.1f}")
    print(f"  Docked non-zero:  {docked_nz_arr.mean():.1f} ± {docked_nz_arr.std():.1f}")
    print(f"  Feature RMSD:     {feature_rmsds.mean():.4f} ± {feature_rmsds.std():.4f}")

    # Prediction agreement
    pred_corr, pred_p = spearmanr(crystal_preds, docked_preds)
    pred_rmsd = np.sqrt(np.mean((crystal_preds - docked_preds) ** 2))
    print("\nCrystal-vs-Docked prediction agreement:")
    print(f"  Spearman(crystal_pred, docked_pred): ρ = {pred_corr:.4f} (p = {pred_p:.6f})")
    print(f"  Prediction RMSD: {pred_rmsd:.3f} pKd units")

    # Distribution info
    print(f"\nExperimental pKd: mean={exp_vals.mean():.2f} ± {exp_vals.std():.2f} "
          f"[{exp_vals.min():.2f}, {exp_vals.max():.2f}]")
    print(f"Crystal preds:    mean={crystal_preds.mean():.2f} ± {crystal_preds.std():.2f}")
    print(f"Docked preds:     mean={docked_preds.mean():.2f} ± {docked_preds.std():.2f}")
    print(f"Vina scores:      mean={vina_scores_arr.mean():.2f} ± {vina_scores_arr.std():.2f}")

    print(f"\nTotal time: {elapsed:.0f}s ({elapsed/60:.1f} min)")

    # Failure analysis
    if failed:
        print("\nFailure breakdown:")
        error_counts = {}
        for r in failed:
            err = r.get("error", "unknown")
            error_counts[err] = error_counts.get(err, 0) + 1
        for err, count in sorted(error_counts.items(), key=lambda x: -x[1]):
            print(f"  {count}x: {err}")

    # ── Save report ──────────────────────────────────────────
    report = {
        "test": "crystal_vs_docked_degradation",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_selected": len(selected),
        "n_success": len(success),
        "n_failed": len(failed),
        "vina_config": {
            "exhaustiveness": VINA_EXHAUSTIVENESS,
            "seed": VINA_SEED,
            "num_modes": VINA_NUM_MODES,
            "grid_padding_A": GRID_PADDING,
        },
        "spearman_crystal": {"rho": rho_crystal, "p": p_crystal},
        "spearman_docked": {"rho": rho_docked, "p": p_docked},
        "spearman_vina": {"rho": rho_vina, "p": p_vina},
        "degradation_rho": rho_docked - rho_crystal,
        "rmse_crystal": rmse_crystal,
        "rmse_docked": rmse_docked,
        "feature_quality": {
            "crystal_nonzero_mean": float(crystal_nz_arr.mean()),
            "crystal_nonzero_std": float(crystal_nz_arr.std()),
            "docked_nonzero_mean": float(docked_nz_arr.mean()),
            "docked_nonzero_std": float(docked_nz_arr.std()),
            "feature_rmsd_mean": float(feature_rmsds.mean()),
            "feature_rmsd_std": float(feature_rmsds.std()),
        },
        "prediction_agreement": {
            "spearman_rho": pred_corr,
            "spearman_p": pred_p,
            "rmsd": pred_rmsd,
        },
        "results": results,
        "elapsed_seconds": elapsed,
    }

    report_path = OUTPUT_DIR / "test_crystal_vs_docked_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
