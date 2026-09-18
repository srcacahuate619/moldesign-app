"""Preserve coordinate/score identity and conversion provenance when pooling."""
import pytest

from core.models import DockingPose, DockingResult
from services.docking.ensemble import run_ensemble_docking
from utils.file_handlers import parse_vina_output_sdf


def record(energy=None):
    return "molecule\n" + (
        f"> <minimizedAffinity>\n{energy}\n\n" if energy is not None else ""
    ) + "$$$$\n"


@pytest.mark.parametrize("records", [
    [record(), record(-8)], [record(-8), record(), record(-6)],
    [record(-8), record()],
    ["molecule\n> <minimizedAffinity>\n$$$$\n", record(-8)],
    ["molecule\n> <meeko>\n$$$$\n", record(-8)],
])
def test_partial_sdf_metadata_cannot_shift_pose_identity(records):
    # Vina consumes list positions to pair SDF scores with PDBQT blocks.
    # A partial parser result would pair scores with another pose's coordinates.
    assert parse_vina_output_sdf("".join(records)) == []


def test_complete_sdf_keeps_original_scores_and_order():
    poses = parse_vina_output_sdf(record(-8) + record(-6))
    assert [(p["rank"], p["affinity"]) for p in poses] == [(1, -8), (2, -6)]


@pytest.mark.asyncio
@pytest.mark.parametrize("mixed", [False, True])
async def test_conversion_provenance_survives_pooling_and_json_roundtrip(mixed):
    converter = {"herramienta": "Open Babel", "sha256": "a" * 64,
                 "version_declarada": "3.1.1", "licencia_spdx": "GPL-2.0-only"}
    async def dock(smiles_hash, **kwargs):
        ob = smiles_hash == "1" or not mixed
        return DockingResult(
            best_affinity=-8 if smiles_hash == "0" else -9,
            poses=[DockingPose(rank=1, affinity=-8 if smiles_hash == "0" else -9,
                               rmsd_lb=0, rmsd_ub=0, pdbqt_block=smiles_hash)],
            poses_file_path=f"runs/{smiles_hash}/poses.sdf",
            parsing_source="sdf_openbabel_cli" if ob else "sdf",
            conversor_estructural=converter if ob else None,
        )
    result = await run_ensemble_docking(
        smiles="CCO", conformeros=[{"indice": i, "smiles_hash": str(i)} for i in range(2)],
        num_poses=2, dock_una=dock,
    )
    assert result.parsing_source == ("mixed" if mixed else "sdf_openbabel_cli")
    assert result.conversor_estructural == (None if mixed else converter)
    assert result.poses_file_path is None
    # The global rank changes; the original rank and file do not.
    reloaded = DockingResult.model_validate_json(result.model_dump_json())
    assert [p.pdbqt_block for p in reloaded.poses] == ["1", "0"]
    assert [p.rank for p in reloaded.poses] == [1, 2]
    assert reloaded.poses[0].source_provenance == {
        "rank": 1, "poses_file_path": "runs/1/poses.sdf",
        "parsing_source": "sdf_openbabel_cli", "conversor_estructural": converter,
        # These conformers carry no input identity, so it is declared absent
        # rather than filled with another run's data or a dict of Nones.
        "ligand_input": None,
        # The pose files of this double do not exist on disk, so their hash is
        # declared absent too. Pose recovery then refuses instead of trusting
        # the rank alone.
        "poses_file_sha256": None,
    }
    assert reloaded.poses[1].source_provenance["rank"] == 1
    assert reloaded.poses[1].source_provenance["poses_file_path"] == "runs/0/poses.sdf"


def test_historical_pose_loads_without_inventing_provenance():
    pose = DockingPose(rank=1, affinity=-8, rmsd_lb=0, rmsd_ub=0)
    assert pose.source_provenance is None
