from types import SimpleNamespace

from services.blockchain.evidence_summary import build_evidence_summary, derive_target_readiness


def _target(**overrides):
    data = {
        "pdb_id": "7E2Y",
        "is_prepared": True,
        "is_private": False,
        "grid_center_x": 1.0,
        "grid_center_y": 2.0,
        "grid_center_z": 3.0,
        "grid_size_x": 20.0,
        "grid_size_y": 20.0,
        "grid_size_z": 20.0,
        "hotspots": [object() for _ in range(5)],
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _result(**overrides):
    data = {
        "affinity_kcal": -7.4,
        "docking_poses": [
            {"rank": 1, "affinity": -7.6},
            {"rank": 2, "affinity": -7.2},
            {"rank": 3, "affinity": -6.1},
        ],
        "vina_version": "1.2.5",
        "vina_random_seed": 42,
        "parsing_source": "sdf",
        "scientific_warnings": [],
        "engine_used": "vina",
        "model_used": "pose_selector_v06",
        "in_applicability_domain": True,
        "fallback_reason": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_ready_target_requires_preparation_grid_and_hotspots():
    assert derive_target_readiness(_target()) == "listo"
    assert derive_target_readiness(_target(hotspots=[])) == "sin_datos"


def test_summary_reports_pose_separation_without_calling_it_confidence():
    summary = build_evidence_summary(_result(), _target())
    assert summary["status"] == "ready"
    assert summary["pose_gap"] == 0.4
    assert summary["near_tie_count"] == 2
    assert summary["physical_validity"]["status"] == "not_evaluated"
    assert summary["next_action"]["status"] == "review"
    sampling = next(item for item in summary["dimensions"] if item["id"] == "sampling")
    assert sampling["status_label"] == "AMBIGUO"


def test_out_of_domain_result_requires_review():
    summary = build_evidence_summary(_result(in_applicability_domain=False), _target())
    assert summary["status"] == "review"


def test_result_without_poses_is_incomplete():
    summary = build_evidence_summary(_result(docking_poses=[]), _target())
    assert summary["status"] == "incomplete"
    assert summary["next_action"]["status"] == "abstain"


def test_result_can_proceed_only_after_physical_controls_pass():
    summary = build_evidence_summary(
        _result(
            docking_poses=[
                {"rank": 1, "affinity": -7.6},
                {"rank": 2, "affinity": -6.2},
            ],
            # El contrato REAL es `structural_evidence` (P0-A). Esta prueba
            # alimentaba `pose_validation`, un atributo que el backend no ha
            # emitido nunca: pasaba en verde mientras el dossier declaraba «no
            # evaluada» en cada corrida de producción.
            structural_evidence={
                "stage_status": "passed",
                "poses_produced": 2,
                "poses_evaluated": 2,
                "validation_engine": "posebusters:1.0:dock",
                "reason_code": None,
                "poses": [
                    {"rank": 1, "status": "passed", "observed_vina_affinity_kcal_mol": -7.6,
                     "checks": [{"check": "sanitization", "estado": "PASA"}],
                     "checks_que_fallan": []},
                    {"rank": 2, "status": "passed", "observed_vina_affinity_kcal_mol": -6.2,
                     "checks": [{"check": "sanitization", "estado": "PASA"}],
                     "checks_que_fallan": []},
                ],
            },
            pose_selection={
                "status": "selected", "vina_top1_rank": 1, "selected_pose_rank": 1,
                "confidence": 0.42, "strategy_is_fallback": False,
                "suggested_pose_physical_status": "passed", "physical_review": False,
                "model": {"name": "pose_selector_v06", "model_sha256": "b" * 64,
                          "abstention_threshold": 0.097663},
                "physically_valid_alternatives": [{"rank": 2, "physical_status": "passed"}],
                "pose_scores": [{"rank": 1, "score": 0.6}, {"rank": 2, "score": 0.1}],
                "warnings": [],
            },
        ),
        _target(),
    )
    assert summary["physical_validity"]["status"] == "passed"
    assert summary["physical_validity"]["engine"] == "posebusters:1.0:dock"
    assert summary["next_action"]["status"] == "proceed"
    # Y el bloque de selección viaja con el resumen, para que PDF, JSON y
    # manifiesto lean del mismo objeto y no puedan discrepar.
    assert summary["pose_selection"]["status"] == "selected"
    assert summary["pose_selection"]["diverges_from_vina_top1"] is False
    assert [p["rank"] for p in summary["pose_evidence"]] == [1, 2]
    assert all(p["physically_valid"] for p in summary["pose_evidence"])
