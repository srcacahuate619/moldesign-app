#!/usr/bin/env python3
"""
Test 1: ML Rescoring of 5-HT1A BindingDB Panel (40 molecules)
=============================================================

Prueba de fuego: ¿El modelo ML v4 mejora el Spearman=0.020
del Vina crudo contra datos experimentales de 5-HT1A?

Pipeline per molecule:
  1. SMILES → RDKit Mol → 3D conformer (ETKDG)
  2. Mol → meeko → PDBQT ligand
  3. Vina docking (7E2Y, exhaustiveness=32, seed=42)
  4. Output PDBQT pose → v4 feature extraction (164 3D features)
  5. ML prediction (Model A + Model NULL)
  6. Spearman(experimental_pActivity, ML_score) vs Spearman with raw Vina

Scientific limitations:
  - Docking is re-run from scratch (not original calibration poses)
  - Vina seed=42 should reproduce, but conformer generation may differ
  - PDBQT inference path uses MDAnalysis (different from training SDF path)
  - This measures the crystal-to-docked degradation implicitly

Author: MolDesign automated validation
"""

import json
import math
import os
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

import numpy as np

# ── Paths ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if os.path.exists("/app/artifacts"):
    # Inside container
    RESCORING_DIR = PROJECT_ROOT
    BACKEND_ARTIFACTS = PROJECT_ROOT / "artifacts"
    DATA_DIR = PROJECT_ROOT / "data" / "7e2y"
else:
    # On host
    PROJECT_ROOT = PROJECT_ROOT.parent # Go up to actual project root
    RESCORING_DIR = PROJECT_ROOT / "rescoring"
    BACKEND_ARTIFACTS = PROJECT_ROOT / "backend" / "artifacts"
    DATA_DIR = PROJECT_ROOT / "data" / "7e2y"
VINA_EXE = os.environ.get("VINA_EXECUTABLE_PATH")
if not VINA_EXE:
    if os.name == 'nt':
        VINA_EXE = PROJECT_ROOT / "tools" / "vina" / "vina.exe"
    else:
        VINA_EXE = PROJECT_ROOT / "tools" / "vina"
else:
    VINA_EXE = Path(VINA_EXE)

# Grid box for 7E2Y (from grid_box_7e2y_sro.json)
GRID_CENTER = (103.03, 114.79, 108.36)
GRID_SIZE = (15.9, 15.9, 13.5)
# Use 25x25x25 like the calibration script for consistency
GRID_SIZE_OVERRIDE = (25.0, 25.0, 25.0)

RECEPTOR_PDBQT = DATA_DIR / "receptor.pdbqt"
RECEPTOR_PDB = DATA_DIR / "receptor.pdb"
CALIBRATION_REPORT = BACKEND_ARTIFACTS / "external_calibration_report.json"

VINA_EXHAUSTIVENESS = 32
VINA_SEED = 42
VINA_NUM_MODES = 9


import rdkit

try:
    from rdkit import six
except ImportError:
    import io
    # Monkeypatch rdkit.six for meeko compatibility
    six = type('six', (), {'StringIO': io.StringIO})
    rdkit.six = six
    sys.modules['rdkit.six'] = six

def smiles_to_pdbqt(smiles: str, output_path: str) -> bool:
    """Convert SMILES to PDBQT using RDKit + meeko."""
    import os
    import sys

    from meeko import MoleculePreparation
    from rdkit import Chem
    from rdkit.Chem import AllChem
    
    # SA Scorer setup
    _sa_scorer_path = "/opt/conda/share/RDKit/Contrib/SA_Score/"
    if os.path.exists(_sa_scorer_path) and _sa_scorer_path not in sys.path:
        sys.path.append(_sa_scorer_path)
    try:
        import sascorer
    except ImportError:
        sascorer = None

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print(f"  [ERROR] Cannot parse SMILES: {smiles[:50]}")
        return False

    mol = Chem.AddHs(mol)

    # Generate 3D conformer with ETKDG
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    params.numThreads = 1
    result = AllChem.EmbedMolecule(mol, params)
    if result < 0:
        # Fallback: use random coordinates
        params.useRandomCoords = True
        result = AllChem.EmbedMolecule(mol, params)
        if result < 0:
            print("  [ERROR] Cannot generate 3D conformer")
            return False

    # Optimize with MMFF
    try:
        AllChem.MMFFOptimizeMolecule(mol, maxIters=500)
    except Exception:
        pass  # Non-critical

    # Meeko preparation (v0.7+ API: PDBQTWriterLegacy)
    try:
        from meeko import PDBQTWriterLegacy
        preparator = MoleculePreparation()
        mol_setups = preparator.prepare(mol)
        pdbqt_result = PDBQTWriterLegacy.write_string(mol_setups[0])
        # write_string returns a tuple (pdbqt_string, is_ok, error_msg)
        pdbqt_string = pdbqt_result[0] if isinstance(pdbqt_result, tuple) else pdbqt_result
        with open(output_path, "w") as f:
            f.write(pdbqt_string)
        return True
    except Exception as e:
        print(f"  [ERROR] Meeko preparation failed: {e}")
        return False


def run_vina(
    ligand_pdbqt: str,
    receptor_pdbqt: str,
    output_pdbqt: str,
    log_path: str,
) -> float | None:
    """Run AutoDock Vina and return best score."""
    cmd = [
        str(VINA_EXE),
        "--receptor", receptor_pdbqt,
        "--ligand", ligand_pdbqt,
        "--center_x", str(GRID_CENTER[0]),
        "--center_y", str(GRID_CENTER[1]),
        "--center_z", str(GRID_CENTER[2]),
        "--size_x", str(GRID_SIZE_OVERRIDE[0]),
        "--size_y", str(GRID_SIZE_OVERRIDE[1]),
        "--size_z", str(GRID_SIZE_OVERRIDE[2]),
        "--exhaustiveness", str(VINA_EXHAUSTIVENESS),
        "--num_modes", str(VINA_NUM_MODES),
        "--seed", str(VINA_SEED),
        "--out", output_pdbqt,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max per molecule
        )

        # Save log
        with open(log_path, "w") as f:
            f.write(result.stdout)
            if result.stderr:
                f.write("\n--- STDERR ---\n")
                f.write(result.stderr)

        if result.returncode != 0:
            print(f"  [ERROR] Vina returned code {result.returncode}")
            print(f"  stderr: {result.stderr[:300]}")
            return None

        # Parse best score from output PDBQT
        best_score = None
        if os.path.exists(output_pdbqt):
            with open(output_pdbqt) as f:
                for line in f:
                    if line.startswith("REMARK VINA RESULT"):
                        parts = line.split()
                        if len(parts) >= 4:
                            score = float(parts[3])
                            if best_score is None or score < best_score:
                                best_score = score
                            break  # First REMARK is best pose
        return best_score

    except subprocess.TimeoutExpired:
        print("  [ERROR] Vina timed out (600s)")
        return None
    except Exception as e:
        print(f"  [ERROR] Vina execution failed: {e}")
        return None


def extract_all_vina_scores(output_pdbqt: str) -> list[float]:
    """Extract all Vina scores from multi-model PDBQT output."""
    scores = []
    if os.path.exists(output_pdbqt):
        with open(output_pdbqt) as f:
            for line in f:
                if line.startswith("REMARK VINA RESULT"):
                    parts = line.split()
                    if len(parts) >= 4:
                        scores.append(float(parts[3]))
    return scores


def split_pdbqt_models(pdbqt_path: str) -> list[str]:
    """Split multi-model PDBQT into individual model blocks."""
    models = []
    current = []
    with open(pdbqt_path) as f:
        for line in f:
            current.append(line)
            if line.startswith("ENDMDL"):
                models.append("".join(current))
                current = []
    if current:
        models.append("".join(current))
    return models


def extract_v4_features(
    full_pdbqt_content: str,
    target_pdb_path: str,
    smiles: str,
) -> dict[str, float]:
    """
    Extract v4 features from a docking pose.

    Strategy: Full PDBQT output → meeko → RDKit Mol (pose 0) → SDF → training-path extraction.
    This uses the exact same code path as training (extract_from_files)
    avoiding the fragile MDAnalysis PDBQT parser.

    Args:
        full_pdbqt_content: Complete Vina output PDBQT (all poses/models).
        target_pdb_path: Path to receptor PDB file.
        smiles: SMILES string (for fallback/logging).
    """
    from meeko import PDBQTMolecule, RDKitMolCreate
    from rdkit import Chem

    # Add rescoring dir to path
    if str(RESCORING_DIR) not in sys.path:
        sys.path.insert(0, str(RESCORING_DIR))

    from feature_extractor import InteractionFeatureExtractor

    extractor = InteractionFeatureExtractor()

    # Convert PDBQT → RDKit Mol via meeko (needs full multi-model PDBQT)
    try:
        pdbqt_mol = PDBQTMolecule(full_pdbqt_content, is_dlg=False, skip_typing=True)
        next(pdbqt_mol)  # Navigate to first pose (best Vina score)
        rdkit_mols = RDKitMolCreate.from_pdbqt_mol(pdbqt_mol)
        if not rdkit_mols:
            print("  [WARN] meeko could not create RDKit mol")
            return extractor.extract_from_pose(full_pdbqt_content, target_pdb_path, smiles)

        mol = rdkit_mols[0]

        # Write as SDF
        sdf_block = Chem.MolToMolBlock(mol)
        fd, sdf_path = tempfile.mkstemp(suffix=".sdf")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(sdf_block)
            # Use training path (PDB + SDF) — proven and robust
            features = extractor.extract_from_files(target_pdb_path, sdf_path)
        finally:
            if os.path.exists(sdf_path):
                os.unlink(sdf_path)

        return features

    except Exception as e:
        print(f"  [WARN] meeko conversion failed ({e}), falling back to PDBQT path")
        return extractor.extract_from_pose(full_pdbqt_content, target_pdb_path, smiles)


def ml_predict(
    features_3d: dict[str, float],
    mol_properties: dict[str, float],
    vina_best_score: float,
    vina_scores: list[float],
    model_a_artifact: dict,
    model_null_artifact: dict,
) -> dict:
    """Run ML prediction using v4 models."""
    import xgboost as xgb

    # 1D/2D features
    all_features = {
        "mw": mol_properties["mw"],
        "logp": mol_properties["logp"],
        "tpsa": mol_properties["tpsa"],
        "hbd": mol_properties["hbd"],
        "hba": mol_properties["hba"],
        "rotatable_bonds": mol_properties["rotatable_bonds"],
        "qed": mol_properties["qed"],
    }

    # 3D features from feature extractor
    all_features.update(features_3d)

    # Vina best score
    all_features["vina_best_score"] = vina_best_score

    # Pose variance features
    score_var = float(np.var(vina_scores)) if len(vina_scores) > 1 else 0.0
    score_range = float(max(vina_scores) - min(vina_scores)) if len(vina_scores) > 1 else 0.0
    total_poses = len(vina_scores)
    all_features["pose_score_variance"] = score_var
    all_features["pose_score_range"] = score_range
    all_features["poses_passing_ratio"] = 1.0  # Assume all pass for simplicity

    # Derived feature
    all_features["log_mw"] = math.log(max(mol_properties["mw"], 1.0))

    # Model A prediction
    fn_a = model_a_artifact["feature_names"]
    vec_a = np.array([all_features.get(f, 0.0) for f in fn_a], dtype=np.float64)
    dm_a = xgb.DMatrix(vec_a.reshape(1, -1), feature_names=fn_a)
    score_a = float(model_a_artifact["booster"].predict(dm_a)[0])

    # Model NULL prediction
    fn_null = model_null_artifact["feature_names"]
    vec_null = np.array([all_features.get(f, 0.0) for f in fn_null], dtype=np.float64)
    dm_null = xgb.DMatrix(vec_null.reshape(1, -1), feature_names=fn_null)
    score_null = float(model_null_artifact["booster"].predict(dm_null)[0])

    return {
        "score_a": score_a,
        "score_null": score_null,
        "delta": score_a - score_null,
        "all_features": all_features,
    }


def compute_mol_properties(smiles: str) -> dict[str, float] | None:
    """Compute 1D/2D molecular properties using RDKit."""
    from rdkit import Chem
    from rdkit.Chem import QED, Descriptors, rdMolDescriptors

    mol = Chem.MolFromSmiles(smiles)
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


def compute_sa_score(mol) -> float:
    """Compute SA Score with ring strain penalty (v4 logic)."""
    import os
    import sys
    _sa_scorer_path = "/opt/conda/share/RDKit/Contrib/SA_Score/"
    if os.path.exists(_sa_scorer_path) and _sa_scorer_path not in sys.path:
        sys.path.append(_sa_scorer_path)
    
    try:
        import sascorer
        raw_score = sascorer.calculateScore(mol)
        
        # Penalización por tensión de anillo
        strain_penalty = 0.0
        ri = mol.GetRingInfo()
        for ring in ri.AtomRings():
            if len(ring) == 3:
                strain_penalty += 1.5
            elif len(ring) == 4:
                strain_penalty += 1.0
        
        return round(min(10.0, raw_score + strain_penalty), 2)
    except Exception:
        return 5.0


def main():
    """Main test execution."""
    from scipy.stats import spearmanr

    print("=" * 70)
    print("TEST 1: ML Rescoring of 5-HT1A BindingDB Panel")
    print("=" * 70)
    print("Receptor: 7E2Y (serotonin 1A receptor)")
    print(f"Grid center: {GRID_CENTER}")
    print(f"Grid size: {GRID_SIZE_OVERRIDE}")
    print(f"Vina: {VINA_EXE}")
    print(f"Exhaustiveness: {VINA_EXHAUSTIVENESS}, Seed: {VINA_SEED}")
    print()

    # ── Validate paths ───────────────────────────────────────
    assert RECEPTOR_PDBQT.exists(), f"Receptor PDBQT not found: {RECEPTOR_PDBQT}"
    assert RECEPTOR_PDB.exists(), f"Receptor PDB not found: {RECEPTOR_PDB}"
    assert VINA_EXE.exists(), f"Vina not found: {VINA_EXE}"
    assert CALIBRATION_REPORT.exists(), "Calibration report not found"

    # ── Load calibration data ────────────────────────────────
    with open(CALIBRATION_REPORT) as f:
        report = json.load(f)
    molecules = report["accepted"]
    print(f"Loaded {len(molecules)} molecules from calibration panel")

    # ── Load ML models ───────────────────────────────────────
    import joblib
    model_a_artifact = joblib.load(BACKEND_ARTIFACTS / "model_a.joblib")
    model_null_artifact = joblib.load(BACKEND_ARTIFACTS / "model_null.joblib")
    print(f"Model A: {len(model_a_artifact['feature_names'])} features")
    print(f"Model NULL: {len(model_null_artifact['feature_names'])} features")
    print()

    # ── Create output directory ──────────────────────────────
    output_dir = PROJECT_ROOT / "data" / "test_5ht1a_rescore"
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Process each molecule ────────────────────────────────
    results = []
    start_time = time.time()

    for i, mol_data in enumerate(molecules):
        mol_id = mol_data["molecule_id"]
        smiles = mol_data["canonical_smiles"]
        pactivity = mol_data["activity_value"]
        vina_original = mol_data["predicted_affinity_kcal"]

        print(f"[{i+1:02d}/{len(molecules)}] mol_id={mol_id} pActivity={pactivity:.3f}")

        mol_dir = output_dir / str(mol_id)
        mol_dir.mkdir(exist_ok=True)

        result = {
            "molecule_id": mol_id,
            "smiles": smiles,
            "experimental_pactivity": pactivity,
            "original_vina_kcal": vina_original,
            "success": False,
        }

        # Step 1: Compute molecular properties
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            print("  [FAIL] Cannot parse SMILES")
            results.append(result)
            continue

        sa_score = compute_sa_score(mol)
        result["sa_score"] = sa_score
        
        # Hard filter SA > 7.0
        if sa_score > 7.0:
            print(f"  [SKIP] Unfeasible molecule (SA Score {sa_score} > 7.0)")
            result["success"] = False
            result["error"] = f"SA Score {sa_score} > 7.0"
            results.append(result)
            continue

        props = compute_mol_properties(smiles)
        if props is None:
            print("  [FAIL] Cannot compute properties")
            results.append(result)
            continue
        result["mol_properties"] = props

        # Step 2: Generate PDBQT ligand
        ligand_pdbqt = str(mol_dir / "ligand.pdbqt")
        if not os.path.exists(ligand_pdbqt):
            ok = smiles_to_pdbqt(smiles, ligand_pdbqt)
            if not ok:
                print("  [FAIL] PDBQT preparation failed")
                results.append(result)
                continue
        else:
            ok = True

        # Step 3: Run Vina docking
        output_pdbqt = str(mol_dir / "output.pdbqt")
        log_path = str(mol_dir / "vina.log")

        if not os.path.exists(output_pdbqt):
            t0 = time.time()
            vina_score = run_vina(ligand_pdbqt, str(RECEPTOR_PDBQT), output_pdbqt, log_path)
            dock_time = time.time() - t0
            print(f"  Vina: {vina_score} kcal/mol ({dock_time:.1f}s)")
        else:
            # Already docked - read score
            all_scores = extract_all_vina_scores(output_pdbqt)
            vina_score = all_scores[0] if all_scores else None
            print(f"  Vina (cached): {vina_score} kcal/mol")

        if vina_score is None:
            print("  [FAIL] Docking failed")
            results.append(result)
            continue

        result["new_vina_kcal"] = vina_score

        # Get all Vina scores from multi-model output
        all_vina_scores = extract_all_vina_scores(output_pdbqt)
        result["all_vina_scores"] = all_vina_scores

        # Step 4: Extract v4 features from best pose
        # Read full PDBQT output (meeko needs all models)
        with open(output_pdbqt) as f:
            full_pdbqt_content = f.read()

        if not full_pdbqt_content.strip():
            print("  [FAIL] Empty output PDBQT")
            results.append(result)
            continue

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            features_3d = extract_v4_features(full_pdbqt_content, str(RECEPTOR_PDB), smiles)

        n_nonzero = sum(1 for v in features_3d.values() if v != 0.0)
        print(f"  Features: {len(features_3d)} total, {n_nonzero} non-zero")

        # Step 5: ML prediction
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            prediction = ml_predict(
                features_3d, props, vina_score, all_vina_scores,
                model_a_artifact, model_null_artifact,
            )

        result["ml_score_a"] = prediction["score_a"]
        result["ml_score_null"] = prediction["score_null"]
        result["ml_delta"] = prediction["delta"]
        result["success"] = True

        print(
            f"  ML: A={prediction['score_a']:.3f} "
            f"NULL={prediction['score_null']:.3f} "
            f"Δ={prediction['delta']:+.3f}"
        )

        # Save per-molecule results
        mol_result_path = mol_dir / "result.json"
        with open(mol_result_path, "w") as f:
            json.dump({
                k: v for k, v in result.items()
                if k != "mol_properties"  # Don't clutter individual files
            }, f, indent=2)

        results.append(result)

    elapsed = time.time() - start_time
    print(f"\n{'=' * 70}")
    print(f"COMPLETED in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"{'=' * 70}\n")

    # ── Analysis ─────────────────────────────────────────────
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    print(f"Successful: {len(successful)}/{len(results)}")
    print(f"Failed: {len(failed)}")

    if len(successful) < 5:
        print("[ERROR] Too few successful dockings for meaningful analysis")
        return

    # Extract arrays
    exp_pactivity = np.array([r["experimental_pactivity"] for r in successful])
    vina_original = np.array([r["original_vina_kcal"] for r in successful])
    vina_new = np.array([r["new_vina_kcal"] for r in successful])
    ml_score_a = np.array([r["ml_score_a"] for r in successful])
    ml_score_null = np.array([r["ml_score_null"] for r in successful])

    # Positive versions (higher = better binding)
    vina_original_pos = -vina_original
    vina_new_pos = -vina_new

    print("\n" + "─" * 70)
    print("SPEARMAN CORRELATIONS WITH EXPERIMENTAL pActivity")
    print("─" * 70)

    # 1. Original Vina raw scores (from calibration)
    rho_orig, p_orig = spearmanr(exp_pactivity, vina_original_pos)
    print(f"Original Vina (calibration):  ρ = {rho_orig:.4f}  (p = {p_orig:.4f})")

    # 2. New Vina raw scores (fresh docking)
    rho_new, p_new = spearmanr(exp_pactivity, vina_new_pos)
    print(f"New Vina (fresh docking):     ρ = {rho_new:.4f}  (p = {p_new:.4f})")

    # 3. ML Model A (full 3D features)
    rho_ml_a, p_ml_a = spearmanr(exp_pactivity, ml_score_a)
    print(f"ML Model A (3D features):     ρ = {rho_ml_a:.4f}  (p = {p_ml_a:.4f})")

    # 4. ML Model NULL (1D/2D only)
    rho_ml_null, p_ml_null = spearmanr(exp_pactivity, ml_score_null)
    print(f"ML Model NULL (1D/2D only):   ρ = {rho_ml_null:.4f}  (p = {p_ml_null:.4f})")

    # 5. Delta (specificity signal)
    ml_delta = ml_score_a - ml_score_null
    rho_delta, p_delta = spearmanr(exp_pactivity, ml_delta)
    print(f"ML Delta (A - NULL):          ρ = {rho_delta:.4f}  (p = {p_delta:.4f})")

    print("\n" + "─" * 70)
    print("INTERPRETATION")
    print("─" * 70)

    improvement = rho_ml_a - rho_orig
    print(f"Improvement (ML A vs Original Vina): {improvement:+.4f}")

    if rho_ml_a > rho_orig + 0.05:
        print("✓ ML rescoring IMPROVES ranking over raw Vina")
    elif abs(rho_ml_a - rho_orig) <= 0.05:
        print("≈ ML rescoring shows SIMILAR performance to raw Vina")
    else:
        print("✗ ML rescoring DOES NOT improve ranking (honest assessment)")

    # Check Vina reproducibility
    print("\nVina reproducibility (new vs original):")
    rho_repro, _ = spearmanr(vina_original, vina_new)
    mae_vina = np.mean(np.abs(vina_original - vina_new))
    print(f"  Spearman(old, new): {rho_repro:.4f}")
    print(f"  MAE: {mae_vina:.3f} kcal/mol")

    # Feature analysis: how many non-zero 3D features on average?
    nonzero_counts = []
    for r in successful:
        # Count from saved ml results
        pass

    # Score distributions
    print("\nScore distributions:")
    print(f"  Vina (new):  mean={np.mean(vina_new):.2f} ± {np.std(vina_new):.2f}")
    print(f"  ML A:        mean={np.mean(ml_score_a):.2f} ± {np.std(ml_score_a):.2f}")
    print(f"  ML NULL:     mean={np.mean(ml_score_null):.2f} ± {np.std(ml_score_null):.2f}")
    print(f"  pActivity:   mean={np.mean(exp_pactivity):.2f} ± {np.std(exp_pactivity):.2f}")

    # ── Save comprehensive results ───────────────────────────
    summary = {
        "test_name": "5-HT1A ML Rescoring Panel",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_molecules": len(molecules),
        "n_successful": len(successful),
        "n_failed": len(failed),
        "failed_mol_ids": [r["molecule_id"] for r in failed],
        "vina_config": {
            "exhaustiveness": VINA_EXHAUSTIVENESS,
            "seed": VINA_SEED,
            "num_modes": VINA_NUM_MODES,
            "grid_center": GRID_CENTER,
            "grid_size": list(GRID_SIZE_OVERRIDE),
        },
        "spearman_results": {
            "original_vina_vs_pactivity": {
                "rho": round(rho_orig, 4),
                "p_value": round(p_orig, 4),
            },
            "new_vina_vs_pactivity": {
                "rho": round(rho_new, 4),
                "p_value": round(p_new, 4),
            },
            "ml_model_a_vs_pactivity": {
                "rho": round(rho_ml_a, 4),
                "p_value": round(p_ml_a, 4),
            },
            "ml_model_null_vs_pactivity": {
                "rho": round(rho_ml_null, 4),
                "p_value": round(p_ml_null, 4),
            },
            "ml_delta_vs_pactivity": {
                "rho": round(rho_delta, 4),
                "p_value": round(p_delta, 4),
            },
        },
        "vina_reproducibility": {
            "spearman_old_vs_new": round(rho_repro, 4),
            "mae_kcal": round(mae_vina, 3),
        },
        "score_distributions": {
            "vina_new_mean": round(float(np.mean(vina_new)), 3),
            "vina_new_std": round(float(np.std(vina_new)), 3),
            "ml_a_mean": round(float(np.mean(ml_score_a)), 3),
            "ml_a_std": round(float(np.std(ml_score_a)), 3),
            "ml_null_mean": round(float(np.mean(ml_score_null)), 3),
            "ml_null_std": round(float(np.std(ml_score_null)), 3),
            "pactivity_mean": round(float(np.mean(exp_pactivity)), 3),
            "pactivity_std": round(float(np.std(exp_pactivity)), 3),
        },
        "per_molecule": [
            {
                "molecule_id": r["molecule_id"],
                "smiles": r["smiles"],
                "experimental_pactivity": r["experimental_pactivity"],
                "original_vina_kcal": r["original_vina_kcal"],
                "new_vina_kcal": r.get("new_vina_kcal"),
                "ml_score_a": r.get("ml_score_a"),
                "ml_score_null": r.get("ml_score_null"),
                "ml_delta": r.get("ml_delta"),
                "success": r["success"],
            }
            for r in results
        ],
        "elapsed_seconds": round(elapsed, 1),
    }

    report_path = output_dir / "test_5ht1a_rescore_report.json"
    with open(report_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nFull report saved to: {report_path}")


if __name__ == "__main__":
    main()
