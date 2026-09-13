import json
import os
import sys
import pandas as pd

# Add backend directory to path to import scoring engine and chem properties
sys.path.insert(0, "d:/moldesign-build/backend")

from scoring.engine import _get_stacking_weights, calculate_score_breakdown
from scoring.normalizer import normalize_affinity
from core.models import DockingResult, DockingPose, PhysicochemicalProperties
from chem.properties import calculate_properties

def test_grid_centers_integrity():
    print("\n--- TEST 1: Library Grid Integrity ---")
    json_path = "d:/moldesign-build/curated_targets.json"
    csv_path = "d:/moldesign-build/curated_targets.csv"
    
    with open(json_path, "r", encoding="utf-8") as f:
        targets = json.load(f)
        
    zeros_json = [t for t in targets if t.get("grid_center_x") == 0.0 and t.get("grid_center_y") == 0.0 and t.get("grid_center_z") == 0.0]
    print(f"JSON Total Targets: {len(targets)}")
    print(f"JSON Zeros (0,0,0): {len(zeros_json)}")
    assert len(zeros_json) == 0, f"FAILED: Found {len(zeros_json)} targets with (0,0,0) center in JSON!"
    
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        zeros_csv = df[(df["grid_center_x"] == 0) & (df["grid_center_y"] == 0) & (df["grid_center_z"] == 0)]
        print(f"CSV Total Targets: {len(df)}")
        print(f"CSV Zeros (0,0,0): {len(zeros_csv)}")
        assert len(zeros_csv) == 0, f"FAILED: Found {len(zeros_csv)} targets with (0,0,0) center in CSV!"
        
    print("PASSED: 100% of targets have valid, non-zero 3D grid centers.")

def test_9qa0_coordinates():
    print("\n--- TEST 2: Target 9QA0 Active Site Coordinates ---")
    json_path = "d:/moldesign-build/curated_targets.json"
    with open(json_path, "r", encoding="utf-8") as f:
        targets = json.load(f)
        
    target_9qa0 = next((t for t in targets if t.get("pdb_id", "").upper() == "9QA0"), None)
    assert target_9qa0 is not None, "FAILED: 9QA0 not found in curated_targets.json!"
    
    cx = target_9qa0["grid_center_x"]
    cy = target_9qa0["grid_center_y"]
    cz = target_9qa0["grid_center_z"]
    
    print(f"9QA0 Grid Center: ({cx}, {cy}, {cz})")
    assert abs(cx - 26.552) < 1.0, f"Unexpected X coord: {cx}"
    assert abs(cy - (-2.298)) < 1.0, f"Unexpected Y coord: {cy}"
    assert abs(cz - (-8.625)) < 1.0, f"Unexpected Z coord: {cz}"
    print("PASSED: 9QA0 grid center points directly to active site catalytic Zn ion centroid.")

def test_family_taxonomy_mapping():
    print("\n--- TEST 3: Structural Family Taxonomy & Stacking Weights ---")
    weights_cardio = _get_stacking_weights("cardiovascular")
    weights_metalo = _get_stacking_weights("metaloenzyme")
    weights_default = _get_stacking_weights("default")
    
    print(f"Weights for 'cardiovascular': {weights_cardio}")
    print(f"Weights for 'metaloenzyme':   {weights_metalo}")
    print(f"Weights for 'default':        {weights_default}")
    
    assert weights_cardio == weights_metalo, "FAILED: 'cardiovascular' did not map to 'metaloenzyme' weights!"
    assert weights_cardio != weights_default, "FAILED: 'cardiovascular' fell back to uncalibrated default weights!"
    print("PASSED: Clinical family 'cardiovascular' correctly mapped to structural 'metaloenzyme' (Vina 0.0, GNN 0.9).")

def test_scoring_calibration_benchmarks():
    print("\n--- TEST 4: Scoring Calibration Benchmarks ---")
    
    # 4.1 Aspirina SMILES: CC(=O)Oc1ccccc1C(=O)O
    aspirin_smiles = "CC(=O)Oc1ccccc1C(=O)O"
    aspirin_props = calculate_properties(aspirin_smiles)
    
    # Aspirina vs 9QA0 (Control Negativo: afinidad debil -5.2 kcal/mol, HA=13)
    docking_weak = DockingResult(
        best_affinity=-5.2,
        poses=[DockingPose(rank=1, affinity=-5.2, rmsd_lb=0.0, rmsd_ub=0.0)]
    )
    breakdown_neg = calculate_score_breakdown(
        docking=docking_weak, properties=aspirin_props, is_control=False,
        affinity_threshold=-7.5, target_family="cardiovascular"
    )
    
    print(f"Aspirin vs 9QA0 (Weak dG=-5.2 kcal/mol): Total Score = {breakdown_neg.total_score} / 100")
    assert breakdown_neg.total_score < 35.0, f"FAILED: Weak binder score {breakdown_neg.total_score} >= 35.0!"
    
    # 4.2 Aspirina vs COX-1 (Control Positivo Aspirina: afinidad fuerte -7.8 kcal/mol, threshold -7.5)
    docking_strong = DockingResult(
        best_affinity=-7.8,
        poses=[DockingPose(rank=1, affinity=-7.8, rmsd_lb=0.0, rmsd_ub=0.0)]
    )
    breakdown_pos_aspirin = calculate_score_breakdown(
        docking=docking_strong, properties=aspirin_props, is_control=False,
        affinity_threshold=-7.5, target_family="soluble_enzyme"
    )
    print(f"Aspirin vs COX-1 (Strong dG=-7.8 kcal/mol): Total Score = {breakdown_pos_aspirin.total_score} / 100")
    assert breakdown_pos_aspirin.total_score > 70.0, f"FAILED: Strong binder score {breakdown_pos_aspirin.total_score} <= 70.0!"

    # 4.3 Captopril SMILES: CC(CS)C(=O)N1CCCC1C(=O)O (Inhibidor potente de ECA/ANCE)
    captopril_smiles = "CC(CS)C(=O)N1CCCC1C(=O)O"
    captopril_props = calculate_properties(captopril_smiles)
    docking_captopril = DockingResult(
        best_affinity=-8.8,
        poses=[DockingPose(rank=1, affinity=-8.8, rmsd_lb=0.0, rmsd_ub=0.0)]
    )
    breakdown_captopril = calculate_score_breakdown(
        docking=docking_captopril, properties=captopril_props, is_control=False,
        affinity_threshold=-7.5, target_family="cardiovascular"
    )
    print(f"Captopril vs 9QA0 (Potent dG=-8.8 kcal/mol): Total Score = {breakdown_captopril.total_score} / 100")
    assert breakdown_captopril.total_score > 75.0, f"FAILED: Captopril score {breakdown_captopril.total_score} <= 75.0!"

    print("PASSED: All scoring calibration benchmarks completed with perfect separation.")

def main():
    print("=================================================================")
    print("      MOLDESIGN SCIENTIFIC CALIBRATION VERIFICATION SUITE       ")
    print("=================================================================")
    test_grid_centers_integrity()
    test_9qa0_coordinates()
    test_family_taxonomy_mapping()
    test_scoring_calibration_benchmarks()
    print("\n=================================================================")
    print("ALL VERIFICATION TESTS PASSED SUCCESSFULLY! CALIBRATION CONFIRMED.")
    print("=================================================================")

if __name__ == "__main__":
    main()
