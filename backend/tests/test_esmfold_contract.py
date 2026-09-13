from __future__ import annotations

from services.esmfold.service import ESMFoldService


def test_parse_response_conserva_plddt_del_resultado_y_no_de_las_poses_vina():
    service = ESMFoldService()
    parsed = service._parse_response(
        {
            "success": True,
            "best_confidence": 0.72,
            "poses": [
                {
                    "rank": 1,
                    "confidence": 0.0,
                    "peptide_pdb": "ATOM test",
                    "vina_affinity_kcal_mol": -5.4,
                    "origen": "vina_docked",
                }
            ],
        },
        elapsed=0.1,
    )

    assert parsed.best_confidence == 0.72
    assert parsed.poses[0].confidence == 0.0
    assert parsed.poses[0].vina_affinity_kcal_mol == -5.4


def test_parse_response_usa_fallback_legacy_si_no_llega_plddt():
    service = ESMFoldService()
    parsed = service._parse_response(
        {
            "success": True,
            "poses": [
                {"rank": 1, "confidence": 0.61, "peptide_pdb": "ATOM test"},
                {"rank": 2, "confidence": 0.48, "peptide_pdb": "ATOM test"},
            ],
        },
        elapsed=0.1,
    )

    assert parsed.best_confidence == 0.61