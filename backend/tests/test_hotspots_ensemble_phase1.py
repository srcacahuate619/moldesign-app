"""DOCK-005/011/015: el resultado agrupado conserva la evidencia de la pose 1."""

from __future__ import annotations

import pytest

from core.models import DockingPose, DockingResult
from services.docking.ensemble import run_ensemble_docking
from services.docking.vina_service import _analyze_hotspot_interactions


def _partial(affinity: float, hits):
    pose = DockingPose(rank=1, affinity=affinity, rmsd_lb=0.0, rmsd_ub=0.0)
    return DockingResult(
        best_affinity=affinity, poses=[pose], parsing_source="sdf",
        hotspots_hit=hits,
    )


@pytest.mark.asyncio
async def test_ensemble_hereda_hotspots_de_la_pose_ganadora():
    results = {"c0": _partial(-7.0, ["A:TYR10"]),
               "c1": _partial(-9.0, ["B:ASP42"])}
    async def dock_una(*, smiles_hash, smiles):
        return results[smiles_hash]
    combined = await run_ensemble_docking(
        smiles="CCOCC", conformeros=[
            {"indice": 0, "smiles_hash": "c0"},
            {"indice": 1, "smiles_hash": "c1"},
        ], num_poses=2, dock_una=dock_una,
    )
    assert combined.poses[0].conformer_index == 1
    assert combined.hotspots_hit == ["B:ASP42"]


def _atom(serial, chain, x):
    return (
        f"ATOM  {serial:5d}  CG  TYR {chain}  10    "
        f"{x:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 20.00           C"
    )


def test_hotspot_con_cadena_no_usa_otra_cadena(tmp_path):
    receptor = tmp_path / "receptor.pdbqt"
    receptor.write_text(_atom(1, "A", 100.0) + "\n" + _atom(2, "B", 0.0))
    ligand = _atom(3, "X", 0.0)
    assert _analyze_hotspot_interactions(
        receptor, ligand, [{"name": "A:TYR10"}],
    ) == []
    assert _analyze_hotspot_interactions(
        receptor, ligand, [{"name": "B:TYR10"}],
    ) == ["B:TYR10"]


def test_hotspots_no_calculados_son_distintos_de_cero():
    assert DockingResult(
        best_affinity=-7.0,
        poses=[DockingPose(rank=1, affinity=-7.0, rmsd_lb=0.0, rmsd_ub=0.0)],
    ).hotspots_hit is None
