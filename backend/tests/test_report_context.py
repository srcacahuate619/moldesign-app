"""Contratos del contexto científico compartido por reportes IA (C-09)."""

from __future__ import annotations

from types import SimpleNamespace

from services.ai.report_context import build_evaluation_report_request


def test_report_context_preserves_scientific_values_for_any_delivery_mode():
    result = SimpleNamespace(
        molecular_weight=350.0,
        log_p=2.1,
        tpsa=65.0,
        hbd=2,
        hba=5,
        rotatable_bonds=4,
        heavy_atom_count=24,
        ring_count=3,
        lipinski_pass=True,
        veber_pass=True,
        qed=0.72,
        sa_score=3.4,
        sa_reasons=["fragmento poco común"],
        docking_poses=[
            {"rank": 1, "affinity": -8.2, "rmsd_lb": 0.0, "rmsd_ub": 0.0},
        ],
        affinity_kcal=-8.2,
        is_control=False,
        gnn_score=None,
        xgb_score=0.78,
        clgnn_score=None,
        quantum_score=None,
        ums_score=None,
        mmgbsa_score=None,
        target_family="kinase",
        affinity_score=72.0,
        hotspots_hit=["ASP123"],
        delta_a_null=-0.3,
    )
    target_hotspots = [{"residue": "ASP123", "role": "catalytic"}]

    request = build_evaluation_report_request(
        result=result,
        molecule_smiles="CCO",
        target_name="Target de prueba",
        mutation_type=None,
        target_hotspots=target_hotspots,
    )

    assert request.molecule_smiles == "CCO"
    assert request.target_name == "Target de prueba"
    assert request.affinity_kcal == -8.2
    assert request.affinity_score == 72.0
    assert request.properties.sa_reasons == ["fragmento poco común"]
    assert request.is_control is False
    assert request.hotspots_hit == ["ASP123"]
    assert request.target_hotspots == target_hotspots
    assert request.delta_a_null == -0.3
    assert request.score_breakdown.target_family == "kinase"
