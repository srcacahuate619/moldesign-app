import sys
import json
import asyncio
from uuid import uuid4

# Add backend directory
sys.path.insert(0, "d:/moldesign-build/backend")

from core.database import get_db_session, create_all_tables
from db.repository import Repository
from core.models import DockingResult, DockingPose
from chem.properties import calculate_properties
from scoring.engine import calculate_score_breakdown

async def test_sar_and_mmgbsa_flow():
    print("=== TESTING SAR AND MM-GBSA ENDPOINT LOGIC ===")
    async with get_db_session() as db:
        repo = Repository(db)
        target = await repo.ensure_default_target()
        print(f"Target: {target.pdb_id} - {target.name}")

        smiles1 = "CC(=O)Oc1ccccc1C(=O)O"  # Aspirin
        smiles2 = "CC(CS)C(=O)N1CCCC1C(=O)O" # Captopril

        mol1 = await repo.create_or_get_molecule(smiles=smiles1, target_pdb_id=target.pdb_id)
        mol2 = await repo.create_or_get_molecule(smiles=smiles2, target_pdb_id=target.pdb_id)

        props1 = calculate_properties(smiles1)
        props2 = calculate_properties(smiles2)

        docking1 = DockingResult(best_affinity=-7.8, poses=[DockingPose(rank=1, affinity=-7.8, rmsd_lb=0, rmsd_ub=0)])
        docking2 = DockingResult(best_affinity=-8.8, poses=[DockingPose(rank=1, affinity=-8.8, rmsd_lb=0, rmsd_ub=0)])

        breakdown1 = calculate_score_breakdown(docking1, props1, is_control=False, affinity_threshold=-7.5, target_family="soluble_enzyme")
        breakdown2 = calculate_score_breakdown(docking2, props2, is_control=False, affinity_threshold=-7.5, target_family="cardiovascular")

        eval1 = await repo.upsert_evaluation_result(
            molecule_id=mol1.id,
            properties=props1,
            docking=docking1,
            scores={
                "affinity_score": breakdown1.affinity_score,
                "adme_score": breakdown1.adme_score,
                "druglikeness_score": breakdown1.druglikeness_score,
                "total_score": breakdown1.total_score,
            }
        )

        eval2 = await repo.upsert_evaluation_result(
            molecule_id=mol2.id,
            properties=props2,
            docking=docking2,
            scores={
                "affinity_score": breakdown2.affinity_score,
                "adme_score": breakdown2.adme_score,
                "druglikeness_score": breakdown2.druglikeness_score,
                "total_score": breakdown2.total_score,
            }
        )

        await db.commit()

        # Test SAR router logic
        from api.routers.sar import get_sar_table
        sar_res = await get_sar_table(molecule_id=str(mol1.id), current_user=None, db=db)
        print("\n--- GET /sar/{molecule_id} Output ---")
        print(f"Total analogs: {sar_res['total_analogs']}")
        print(f"Contains 'analogs' key: {'analogs' in sar_res}")
        print(f"Contains 'results' key: {'results' in sar_res}")
        if sar_res["analogs"]:
            first_analog = sar_res["analogs"][0]
            print("First Analog Keys:", list(first_analog.keys()))
            print(f"Similarity: {first_analog.get('similarity')}")
            print(f"Total Score: {first_analog.get('total_score')}")
            print(f"Affinity Kcal: {first_analog.get('affinity_kcal')}")
            print(f"ML Prob: {first_analog.get('ml_prob')}")
            assert "similarity" in first_analog, "FAILED: missing 'similarity' in analog item!"
            assert "analogs" in sar_res, "FAILED: missing 'analogs' key in top-level SAR response!"

        # Test MM-GBSA router logic
        from api.routers.pro_features import run_mmgbsa_endpoint
        print("\n--- POST /pro/mmgbsa/{molecule_id} Output ---")
        mm_res = await run_mmgbsa_endpoint(molecule_id=str(mol1.id), pose_rank=1, num_steps=100, current_user=None, db=db)
        print("MM-GBSA Response Keys:", list(mm_res.keys()))
        print(f"delta_g_total_kcal: {mm_res.get('delta_g_total_kcal')}")
        print(f"delta_g_vdw: {mm_res.get('delta_g_vdw')}")
        print(f"delta_g_electrostatic: {mm_res.get('delta_g_electrostatic')}")
        assert "delta_g_total_kcal" in mm_res, "FAILED: missing 'delta_g_total_kcal'!"
        assert "delta_g_vdw" in mm_res, "FAILED: missing 'delta_g_vdw'!"

        print("\nALL SAR AND MM-GBSA ENDPOINT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_sar_and_mmgbsa_flow())
