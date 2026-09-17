"""La ausencia de pose nunca produce una energía basada en otro conformador."""
import json
import sys
from types import ModuleType

import pytest

from services.docking import mmgbsa_subprocess as worker


@pytest.mark.parametrize("pose", [None, "missing.sdf", "invalid.sdf"])
def test_missing_or_invalid_pose_abstains_without_loading_engine(tmp_path, monkeypatch, capsys, pose):
    args = ["worker", "protein.pdb", "CCO"]
    if pose:
        path = tmp_path / pose
        if pose == "invalid.sdf":
            path.write_text("not a molecule", encoding="utf-8")
        args += ["--poses", str(path)]
    monkeypatch.setattr(sys, "argv", args)
    # Any attempted scientific import, including the old fallback, must fail.
    monkeypatch.setitem(sys.modules, "services.chemistry.molchamb_v2", None)
    assert worker.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "not_evaluated"
    assert result["mmgbsa"] is None
    assert result["used_pose"] is False
    assert result["error"]


def make_pose(path):
    from rdkit import Chem
    mol = Chem.MolFromSmiles("CCO")
    conf = Chem.Conformer(3)
    for index, xyz in enumerate([(1, 2, 3), (2, 2, 3), (3, 2, 3)]):
        conf.SetAtomPosition(index, xyz)
    conf.Set3D(True)
    mol.AddConformer(conf)
    with Chem.SDWriter(str(path)) as writer:
        writer.write(mol)


@pytest.mark.parametrize("energy", [-12.5, float("nan"), float("inf"), None])
def test_valid_pose_keeps_coordinates_and_parameters(tmp_path, monkeypatch, capsys, energy):
    pose = tmp_path / "pose.sdf"
    make_pose(pose)
    calls = []
    engine = ModuleType("services.chemistry.molchamb_v2")
    def calculate(*args, **kwargs):
        calls.append((args, kwargs))
        return {"mmgbsa": energy}
    engine.compute_mmgbsa_from_pose = calculate
    monkeypatch.setitem(sys.modules, engine.__name__, engine)
    monkeypatch.setattr(sys, "argv", ["worker", "protein.pdb", "CCO", "123", "--poses", str(pose)])
    assert worker.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert calls == [(("protein.pdb", "CCO", [(1., 2., 3.), (2., 2., 3.), (3., 2., 3.)]),
                      {"max_iter": 123, "ligand_sdf_path": str(pose)})]
    assert result["used_pose"] is True
    if energy == -12.5:
        assert result["mmgbsa"] == energy
        assert result["status"] == "evaluated"
    else:
        assert result["mmgbsa"] is None
        assert result["status"] == "not_evaluated"


def test_engine_failure_has_no_score(tmp_path, monkeypatch, capsys):
    pose = tmp_path / "pose.sdf"
    make_pose(pose)
    engine = ModuleType("services.chemistry.molchamb_v2")
    def calculate(*args, **kwargs):
        raise RuntimeError("optional engine unavailable")
    engine.compute_mmgbsa_from_pose = calculate
    monkeypatch.setitem(sys.modules, engine.__name__, engine)
    monkeypatch.setattr(sys, "argv", ["worker", "protein.pdb", "CCO", "--poses", str(pose)])
    assert worker.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["mmgbsa"] is None
    assert result["status"] == "not_evaluated"
    assert "unavailable" in result["error"]


@pytest.mark.asyncio
async def test_real_worker_abstains_when_pose_file_is_missing(tmp_path):
    from services.docking.mmgbsa_worker import run_mmgbsa_pose_subprocess
    result = await run_mmgbsa_pose_subprocess(
        "missing.pdb", "CCO", str(tmp_path / "missing.sdf"), max_iter=123, timeout=30,
    )
    assert result["mmgbsa"] is None
    assert result["status"] == "not_evaluated"


@pytest.mark.parametrize("failure", ["delete", "system"])
def test_subsystem_failure_never_becomes_zero_energy(monkeypatch, failure):
    from types import SimpleNamespace
    from services.chemistry import molchamb_v2 as engine
    import openmm.app
    class Modeller:
        topology = SimpleNamespace(atoms=lambda: [])
        positions = []
        def __init__(self, *args):
            pass
        def delete(self, *args):
            if failure == "delete":
                raise ValueError("bad topology")
    def create_system(*args, **kwargs):
        raise ValueError("missing template")
    monkeypatch.setattr(openmm.app, "Modeller", Modeller)
    with pytest.raises(ValueError, match="MM-GBSA no evaluado"):
        engine._compute_isolated_fast(Modeller(), [], SimpleNamespace(createSystem=create_system),
                                      [], "protein", 123, None)


def test_prepared_receptor_is_cleaned_after_preparation_failure(tmp_path, monkeypatch):
    from services.chemistry import molchamb_v2 as engine
    original = engine.tempfile.NamedTemporaryFile
    monkeypatch.setattr(engine, "_get_best_platform", lambda: None)
    monkeypatch.setattr(engine.tempfile, "NamedTemporaryFile",
                        lambda **kwargs: original(dir=tmp_path, **kwargs))
    def fail(*args):
        raise ValueError("bad receptor")
    monkeypatch.setattr(engine, "prepare_protein", fail)
    with pytest.raises(ValueError, match="bad receptor"):
        engine.compute_mmgbsa_from_pose("missing.pdb", "CCO", [], ligand_sdf_path="missing.sdf")
    assert list(tmp_path.iterdir()) == []


def test_real_pose_topology_reaches_energy_stage_without_smiles_fallback(tmp_path, monkeypatch):
    from services.chemistry import molchamb_v2 as engine
    pose = tmp_path / "valid.sdf"
    make_pose(pose)
    monkeypatch.setattr(engine, "_get_best_platform", lambda: None)
    monkeypatch.setattr(engine, "prepare_protein", lambda *args: None)
    class ReachedEnergyStage(BaseException):
        pass
    def stop_after_loading_pose(*args):
        raise ReachedEnergyStage
    monkeypatch.setattr(engine, "compute_xtb_features", stop_after_loading_pose)
    with pytest.raises(ReachedEnergyStage):
        engine.compute_mmgbsa_from_pose("protein.pdb", "CCO", [(1,2,3), (2,2,3), (3,2,3)],
                                        ligand_sdf_path=str(pose))


@pytest.mark.asyncio
@pytest.mark.parametrize("recover", [False, True])
async def test_http_pose_uses_same_run_artifact(tmp_path, monkeypatch, recover):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from api.routers import pro_features as api
    from rdkit import Chem
    pose = tmp_path / "pose.sdf"
    make_pose(pose)
    logical = "poses/hash/target/run/poses.sdf"
    reader = AsyncMock(return_value=pose.read_text())
    monkeypatch.setattr(api, "read_text", reader)
    repo = SimpleNamespace(get_evaluation_run=AsyncMock(return_value=SimpleNamespace(
        status="SUCCESS", snapshot_json={"poses_file_path": logical})))
    evaluation = SimpleNamespace(poses_file_path=None if recover else logical,
                                 task_id="source", molecule_id="molecule")
    mol = await api._mmgbsa_docked_pose(repo, evaluation, 1)
    reader.assert_awaited_once_with(logical)
    assert Chem.MolToSmiles(mol) == "CCO"
    assert tuple(mol.GetConformer().GetAtomPosition(0)) == (1., 2., 3.)
    if recover:
        repo.get_evaluation_run.assert_awaited_once_with("source", "molecule")
    else:
        repo.get_evaluation_run.assert_not_called()


@pytest.mark.asyncio
async def test_http_pose_does_not_shift_rank_past_invalid_record(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from api.routers import pro_features as api
    pose = tmp_path / "pose.sdf"
    make_pose(pose)
    monkeypatch.setattr(api, "read_text", AsyncMock(return_value="bad record\n$$$$\n" + pose.read_text()))
    evaluation = SimpleNamespace(poses_file_path="poses/run.sdf", task_id="run")
    with pytest.raises(HTTPException) as exc:
        await api._mmgbsa_docked_pose(None, evaluation, 1)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_http_missing_pose_abstains_without_generating_coordinates():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from api.routers import pro_features as api
    repo = SimpleNamespace(get_evaluation_run=AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await api._mmgbsa_docked_pose(repo, SimpleNamespace(
            poses_file_path=None, task_id="run", molecule_id="molecule"), 1)
    assert exc.value.status_code == 422
