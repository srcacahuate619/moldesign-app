"""Executable contract for the M4 stacking distributed in the alpha."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core.models import DockingPose, DockingResult, PhysicochemicalProperties
from scoring.engine import _SCI_REGISTRY_PATH, _get_stacking_weights, _resolve_stacking_weights
from scoring.sci_config_registry import ParameterCategory, SciConfigRegistry

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "rescoring" / "artifacts" / "model-manifest.json"
CLGNN = ROOT / "rescoring" / "artifacts" / "gnn_v2_cl_best.pt"
FAMILIES = ("default", "gpcr", "protease", "kinase", "nuclear_receptor", "soluble_enzyme", "metaloenzyme", "metalloenzyme", "phosphodiesterase", "unknown")


def _clgnn_manifest_entry() -> dict:
    models = json.loads(MANIFEST.read_text(encoding="utf-8"))["models"]
    candidates = models.values() if isinstance(models, dict) else models
    return next(item for item in candidates if item.get("file") == CLGNN.name)


def test_registry_is_real_and_cwd_independent(tmp_path, monkeypatch):
    assert _SCI_REGISTRY_PATH == ROOT / "backend" / "artifacts" / "sci_config_registry.json"
    monkeypatch.chdir(tmp_path)
    registry = SciConfigRegistry.load(_SCI_REGISTRY_PATH)
    raw = json.loads(_SCI_REGISTRY_PATH.read_text(encoding="utf-8"))
    assert registry.generate_hash() == raw["config_hash"]


def test_registry_rejects_an_unsealed_edit(tmp_path):
    data = json.loads(_SCI_REGISTRY_PATH.read_text(encoding="utf-8"))
    data["parameters"]["stacking_default"]["versions"][0]["value"]["vina"] = 0.99
    altered = tmp_path / "registry.json"
    altered.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="re-sellar"):
        SciConfigRegistry.load(altered)


@pytest.mark.parametrize("family", FAMILIES)
def test_every_family_resolves_the_conservative_release_contract(family):
    registry = SciConfigRegistry.load(_SCI_REGISTRY_PATH)
    parameter = registry.get(f"stacking_{family}") or registry.get("stacking_default")
    assert parameter is not None
    assert parameter.category == ParameterCategory.SCORING_WEIGHTS
    assert _resolve_stacking_weights(_get_stacking_weights(family)) == {
        "vina": pytest.approx(0.25), "xgb": pytest.approx(0.75),
        "gnn": pytest.approx(0.0), "clgnn": pytest.approx(0.0),
        "quantum_sign": pytest.approx(1.0),
    }


def test_included_checkpoint_is_the_one_named_by_the_contract():
    entry = _clgnn_manifest_entry()
    sha = hashlib.sha256(CLGNN.read_bytes()).hexdigest()
    contract = json.loads(_SCI_REGISTRY_PATH.read_text(encoding="utf-8"))["contract"]
    assert sha == entry["sha256"] == contract["clgnn_sha256"]
    assert entry["metrics"]["external_metrics_for_exact_sha256"] is None
    assert "PENDING" in entry["scientific_status"]


def test_clgnn_is_reported_but_cannot_change_release_ranking():
    from scoring.engine import calculate_score_breakdown
    docking = DockingResult(best_affinity=-8.0, poses=[DockingPose(rank=1, affinity=-8.0, rmsd_lb=0.0, rmsd_ub=0.0)])
    props = PhysicochemicalProperties(molecular_weight=300.0, log_p=2.0, tpsa=60.0, hbd=1, hba=4, rotatable_bonds=3, heavy_atom_count=21, ring_count=2, qed=0.7, sa_score=2.5, lipinski_pass=True, veber_pass=True)
    results = [calculate_score_breakdown(docking, props, xgb_prob=0.8, clgnn_prob=value, target_family="protease") for value in (0.01, 0.99)]
    assert results[0].total_score == results[1].total_score
    assert results[0].stacking_clgnn_weight == 0.0
    assert results[0].stacking_effective_weights["clgnn"] == 0.0