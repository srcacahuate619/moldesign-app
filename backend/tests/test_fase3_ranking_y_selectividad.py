"""Contratos de fase 3: un ranking y un margen deben conservar su procedencia."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.models import DockingPose, DockingResult, PhysicochemicalProperties
from scoring import engine
from services.docking.selectivity import run_selectivity_panel
from services.pipeline.protocols.m5.zinc import calcular


def _breakdown(affinity: float, *, source=None, hotspots=None, hits=None, xgb=0.9):
    docking = DockingResult(
        best_affinity=affinity,
        poses=[DockingPose(rank=1, affinity=affinity, rmsd_lb=0, rmsd_ub=0)],
        hotspots_hit=hits,
    )
    props = PhysicochemicalProperties(
        molecular_weight=350, log_p=2, tpsa=60, hbd=1, hba=4,
        rotatable_bonds=4, heavy_atom_count=25, ring_count=2,
        qed=0.7, sa_score=2.5, lipinski_pass=True, veber_pass=True,
    )
    return engine.calculate_score_breakdown(
        docking, props, xgb_prob=xgb, target_hotspots=hotspots,
        target_hotspots_source=source,
    )


def test_cabeza_del_ranking_conserva_resolucion():
    assert _breakdown(-13).total_score > _breakdown(-11).total_score
    assert _breakdown(-13).total_score < 100


def test_hotspots_autogenerados_no_penalizan():
    hotspots = [{"name": "ASP123", "importance": 1.0}]
    auto = _breakdown(-9, source="auto_pocket_top15", hotspots=hotspots, hits=[])
    assert auto.specificity_multiplier == 1.0
    assert auto.total_score == _breakdown(-9).total_score
    curated = _breakdown(-9, source="curated_experimental", hotspots=hotspots, hits=[])
    assert curated.specificity_multiplier < 1.0


def test_registro_rechazado_cae_a_constantes_selladas_en_codigo(tmp_path, monkeypatch):
    path = tmp_path / "registry.json"
    data = json.loads(engine._SCI_REGISTRY_PATH.read_text(encoding="utf-8"))
    # config_hash sella valores activos; v1 es histórica desde fase 6.
    versions = data["parameters"]["stacking_default"]["versions"]
    active = next(v for v in reversed(versions) if not v.get("superseded_at"))
    active["value"]["vina"] = 0.99
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(engine, "_SCI_REGISTRY_PATH", path)
    weights, source, registry_hash, _ = engine._get_stacking_weights(
        None, with_provenance=True
    )
    assert weights == engine.STACKING_WEIGHTS["default"]
    assert source == "fallback_codigo"
    assert registry_hash is None


def test_m5_se_abstiene_si_xgb_fuera_de_dominio():
    result = calcular(
        pdb_id="1GKC", smiles="ONC(=O)CCCc1ccccc1",
        xgb_prob=0.8, xgb_in_domain=False, hay_zinc_confirmado=True,
    )
    assert result.m5_score is None
    assert "xgb" in result.componentes_ausentes


@pytest.mark.asyncio
async def test_panel_repite_protocolo_efectivo_y_declara_margen(monkeypatch):
    import services.docking.selectivity as panel
    import services.docking.vina_service as vina
    captured = {}

    async def targets(_ids, _repo):
        return ([{"pdb_id": "4NY4", "name": "CYP3A4", "chain": "A",
                  "center": (1, 2, 3), "size": (20, 20, 20),
                  "affinity_threshold": -7.0}], [])

    async def dock(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(best_affinity=-6.0, poses=[object()])

    monkeypatch.setattr(panel, "seleccionar_anti_dianas", targets)
    monkeypatch.setattr(vina, "run_vina_docking", dock)
    protocol = {"engine": "vina", "exhaustiveness": 32, "num_poses": 8,
                "seed": 91, "conformers_generated": 1}
    result = await run_selectivity_panel(
        "CCO", "ligand-hash", "1ABC", -8.0,
        anti_targets=["4NY4"], docking_protocol=protocol,
    )
    assert (captured["exhaustiveness"], captured["num_poses"], captured["seed"]) == (32, 8, 91)
    assert result.off_targets[0]["docking_protocol"]["smiles_hash"] == "ligand-hash"
    assert result.delta_delta_g_kcal == 2.0
    assert any("receptores distintos" in flag for flag in result.safety_flags)
