from types import SimpleNamespace

from core.i18n import reset_request_locale, set_request_locale
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


# Lo que una corrida reciente registra de sí misma (`vina_service.py`). Sin esto
# la dimensión de reproducibilidad ya no dice «REGISTRADA» (SOL-06).
PROCEDENCIA_COMPLETA = {
    "box_center": [1.0, 2.0, 3.0],
    "box_size": [20.0, 20.0, 20.0],
    "receptor_sha256": "a" * 64,
    "ligand_input_sha256": "b" * 64,
    "ligand_pdbqt_sha256": "c" * 64,
    "poses_sha256": "d" * 64,
    "log_sha256": "e" * 64,
    "app_version": "1.0.2",
}


def _result(**overrides):
    data = {
        "docking_protocol": {
            "engine": "vina",
            "exhaustiveness": 8,
            "num_poses": 9,
            "seed": 42,
            "execution_provenance": dict(PROCEDENCIA_COMPLETA),
        },
        "ligand_state": {"smiles_acoplado": "CCO", "protonacion": {"aplicada": False}},
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


# SOL-06. «COMPLETA» salía de tres metadatos. Tres escalones que no se
# confunden: trazas mínimas, elementos de reconstrucción registrados y
# reconstrucción demostrada (que esta dimensión no puede afirmar nunca).
def _reproducibilidad(**overrides):
    summary = build_evidence_summary(_result(**overrides), _target())
    dimension = next(item for item in summary["dimensions"] if item["id"] == "reproducibility")
    return summary, dimension


def test_tres_trazas_sin_caja_ni_hashes_no_se_rotulan_completas():
    summary, dimension = _reproducibilidad(docking_protocol=None, ligand_state=None)
    assert dimension["status_label"] == "PARCIAL"
    assert dimension["status"] == "review"
    assert "Trazas mínimas 3/3" in dimension["detail"]
    assert "elementos de reconstrucción 0/7" in dimension["detail"]
    for faltante in ("caja de búsqueda efectiva", "hash del receptor", "preparación del ligando"):
        assert faltante in dimension["detail"]
    assert summary["reproducibility"]["reconstruction"]["present_count"] == 0


def test_el_resumen_ya_no_promete_reproduccion_si_faltan_elementos():
    summary, _ = _reproducibilidad(docking_protocol=None, ligand_state=None)
    assert summary["status"] == "review"
    assert "suficientes para" not in summary["summary"]
    assert any(u.startswith("Faltan elementos para reconstruir") for u in summary["uncertainties"])


def test_con_todo_registrado_dice_registrada_y_declara_no_demostrada():
    summary, dimension = _reproducibilidad()
    assert dimension["status_label"] == "REGISTRADA"
    assert dimension["status"] == "available"
    assert "no demostrada" in dimension["detail"]
    assert "COMPLET" not in dimension["status_label"]
    assert summary["status"] == "ready"
    assert "no está demostrada" in summary["summary"]
    assert summary["reproducibility"]["reconstruction"]["demonstrated"] is False
    assert summary["reproducibility"]["reconstruction"]["missing"] == []


def test_el_resumen_traduce_solo_el_texto_visible_y_conserva_datos() -> None:
    aviso = (
        "Preparación en condición desolvatada: la estructura depositada no tenía aguas "
        "cristalográficas dentro de la caja de acoplamiento, así que el sitio no perdió ninguna al prepararlo."
    )
    token = set_request_locale("en")
    try:
        summary = build_evidence_summary(
            _result(scientific_warnings=[aviso]),
            _target(),
        )
    finally:
        reset_request_locale(token)

    sampling = next(item for item in summary["dimensions"] if item["id"] == "sampling")
    assert sampling["label"] == "Pose sampling"
    assert summary["assumptions"][-1].startswith("Desolvated preparation:")
    assert summary["warnings"] == [
        "Desolvated preparation: the deposited structure had no crystallographic waters inside the docking box, so none were removed from the site during preparation."
    ]
    assert summary["status"] == "review"
    assert summary["model_context"]["model"] == "pose_selector_v06"
    assert summary["provenance"]["nota"].startswith(
        "These hashes let a third party verify"
    )


import pytest  # noqa: E402


@pytest.mark.parametrize(
    ("faltante", "cambio"),
    [
        ("caja de búsqueda efectiva", {"box_size": None}),
        ("hash del receptor", {"receptor_sha256": ""}),
        ("hashes de entrada del ligando", {"ligand_pdbqt_sha256": None}),
        ("hashes de salida (poses y registro)", {"log_sha256": None}),
        ("versión de la aplicación", {"app_version": None}),
    ],
)
def test_sin_un_elemento_la_dimension_es_parcial_y_lo_nombra(faltante, cambio):
    procedencia = {**PROCEDENCIA_COMPLETA, **cambio}
    _, dimension = _reproducibilidad(
        docking_protocol={
            "engine": "vina", "exhaustiveness": 8, "num_poses": 9, "seed": 42,
            "execution_provenance": procedencia,
        }
    )
    assert dimension["status_label"] == "PARCIAL"
    assert f"faltan: {faltante}" in dimension["detail"]


def test_sin_protocolo_de_busqueda_o_preparacion_del_ligando_es_parcial():
    _, sin_protocolo = _reproducibilidad(
        docking_protocol={"engine": "vina", "execution_provenance": dict(PROCEDENCIA_COMPLETA)}
    )
    assert "faltan: protocolo de búsqueda" in sin_protocolo["detail"]
    _, sin_preparacion = _reproducibilidad(ligand_state={"smiles_acoplado": "CCO"})
    assert "faltan: preparación del ligando" in sin_preparacion["detail"]


def test_sin_ninguna_traza_ni_elemento_es_insuficiente():
    _, dimension = _reproducibilidad(
        docking_protocol=None, ligand_state=None,
        vina_version=None, vina_random_seed=None, parsing_source=None,
    )
    assert dimension["status_label"] == "INSUFICIENTE"
    assert dimension["status"] == "missing"
