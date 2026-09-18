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


def _repositorio_de_piscina():
    """El snapshot congelado de una corrida de ensemble tampoco cita un archivo.

    No es un atajo del doble: `poses_file_path` es None en la columna, así que
    es None en el snapshot. Es el camino que de verdad recorre el endpoint antes
    de intentar la recuperacion por procedencia.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    return SimpleNamespace(get_evaluation_run=AsyncMock(return_value=SimpleNamespace(
        status="SUCCESS", snapshot_json={"poses_file_path": None})))


async def _piscina_en_disco(almacen, *, romper=None):
    """Una evaluación de ensemble: sin archivo único, con procedencia por pose.

    `romper` permite invalidar una puerta concreta para comprobar que el
    endpoint se abstiene en vez de devolver la pose de otra corrida.
    """
    import hashlib
    from types import SimpleNamespace

    def sdf(z, nombre):
        return (
            f"{nombre}\n     RDKit          3D\n\n"
            "  3  0  0  0  0  0  0  0  0  0999 V2000\n"
            "    1.0000    2.0000    3.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
            "    2.0000    2.0000    3.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
            f"    3.0000    2.0000{z:10.4f} O   0  0  0  0  0  0  0  0  0  0  0  0\n"
            "M  END\n$$$$\n"
        )

    archivo = "runs/docking/h__c02/7E2Y/f/poses.sdf"
    conformero = "ligands/h__c02/conformer.sdf"
    contenido = sdf(9.0, "descartada") + sdf(3.0, "entregada")
    entrada = sdf(5.0, "conformero")
    await almacen.write_text(archivo, contenido)
    await almacen.write_text(conformero, entrada)
    bloque = (
        "ROOT\n"
        "ATOM      1  C   UNL     1       1.000   2.000   3.000  0.00  0.00    +0.000 C \n"
        "ATOM      2  C   UNL     1       2.000   2.000   3.000  0.00  0.00    +0.000 C \n"
        "ATOM      3  O   UNL     1       3.000   2.000   3.000  0.00  0.00    +0.000 OA\n"
        "ENDROOT\n"
    )
    procedencia = {
        "rank": 1 if romper == "rank" else 2,
        "poses_file_path": archivo,
        "poses_file_sha256": (
            "0" * 64 if romper == "hash"
            else hashlib.sha256(contenido.encode("utf-8")).hexdigest()
        ),
        "parsing_source": "sdf",
        "conversor_estructural": None,
        "ligand_input": {
            "conformer_path": conformero,
            "conformer_sha256": hashlib.sha256(entrada.encode("utf-8")).hexdigest(),
            "semilla_conformacional": 316,
        },
    }
    if romper == "procedencia":
        procedencia = None
    return SimpleNamespace(
        poses_file_path=None, task_id="corrida", molecule_id="molecula",
        docking_poses=[{
            "rank": 1, "affinity": -9.0, "rmsd_lb": 0.0, "rmsd_ub": 0.0,
            "pdbqt_block": bloque, "conformer_index": 2,
            "source_provenance": procedencia,
        }],
    )


@pytest.mark.asyncio
async def test_http_pose_de_piscina_se_recupera_verificada(tmp_path, monkeypatch):
    """
    Una corrida de ensemble deja de ser irrecuperable, sin dejar de ser honesta.

    `poses_file_path` es None —la piscina mezcla K archivos— y la pose se
    recupera del artefacto de SU corrida, en el rank original 2, después de
    comprobar hashes, átomos pesados y cada coordenada del bloque entregado.
    """
    import utils.local_storage as ls
    from api.routers import pro_features as api

    monkeypatch.setattr(ls.settings, "local_data_dir", str(tmp_path / "data"))
    evaluacion = await _piscina_en_disco(ls)

    mol = await api._mmgbsa_docked_pose(_repositorio_de_piscina(), evaluacion, 1)

    from rdkit import Chem
    assert mol.GetProp("_Name") == "entregada", (
        "se devolvió otro registro del archivo: la recuperación no está usando "
        "el rank de origen ni comprobando la geometría"
    )
    assert tuple(mol.GetConformer().GetAtomPosition(2)) == (3.0, 2.0, 3.0)
    assert Chem.MolToSmiles(mol)


@pytest.mark.asyncio
@pytest.mark.parametrize("romper,motivo", [
    ("hash", "SHA-256"),
    ("rank", "no aparece en el registro"),
    ("procedencia", "no conserva su pose acoplada"),
])
async def test_http_pose_de_piscina_se_abstiene_con_el_motivo(tmp_path, monkeypatch,
                                                              romper, motivo):
    """Cualquier puerta que no pase devuelve 422 diciendo cuál, no una pose."""
    from fastapi import HTTPException

    import utils.local_storage as ls
    from api.routers import pro_features as api

    monkeypatch.setattr(ls.settings, "local_data_dir", str(tmp_path / "data"))
    evaluacion = await _piscina_en_disco(ls, romper=romper)

    with pytest.raises(HTTPException) as fallo:
        await api._mmgbsa_docked_pose(_repositorio_de_piscina(), evaluacion, 1)
    assert fallo.value.status_code == 422
    assert motivo in fallo.value.detail


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
