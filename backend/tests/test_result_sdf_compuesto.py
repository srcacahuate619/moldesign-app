"""Composición SDF auténtica: orden, seis puertas y aislamiento A/B, sin cálculo nuevo."""
import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from api.routers import evaluation_files
from services.docking.result_sdf import ResultSdfUnavailable, read_result_sdf
from tests.test_recuperacion_de_pose_agrupada import almacen, _escenario, _pdbqt, OTRA_GEOMETRIA
from tests.test_recursos_por_corrida import controlled


async def pool(almacen):
    first, path, conformer = await _escenario(almacen)
    second = first.model_copy(deep=True, update={"rank": 2,
        "pdbqt_block": _pdbqt([(x, y, z) for _, x, y, z in OTRA_GEOMETRIA])})
    second.source_provenance["rank"] = 1
    return [second, first], path, conformer


@pytest.mark.asyncio
async def test_compone_registros_exactos_en_rank_global_y_declara_procedencia(almacen):
    poses, _path, _conformer = await pool(almacen)
    snapshot = SimpleNamespace(task_id="run-A", poses_file_path=None, docking_poses=poses)
    artifact = await read_result_sdf(snapshot)
    records = artifact.content.split("$$$$")
    assert records[0].startswith("pose2\n") and records[1].lstrip().startswith("pose1\n")
    assert artifact.content.count("$$$$") == 2
    assert artifact.source_path is None and artifact.source_kind == "verified_ensemble"
    assert artifact.sha256 == hashlib.sha256(artifact.content.encode()).hexdigest()
    assert [source["original_rank"] for source in artifact.manifest["poses"]] == [2, 1]
    assert [source["global_rank"] for source in artifact.manifest["poses"]] == [1, 2]
    assert all(source["max_displacement_A"] == 0 for source in artifact.manifest["poses"])
    assert artifact.manifest["geometry_modified"] is False
    assert artifact.content.count("MOLDESIGN_SOURCE_PROVENANCE_JSON") == 2
    assert snapshot.poses_file_path is None  # no rellena el histórico
    assert snapshot.docking_poses[0].rank == 2  # tampoco lo reordena en memoria


@pytest.mark.asyncio
async def test_hash_modificado_no_entrega_ni_una_pose_parcial(almacen):
    poses, path, _conformer = await pool(almacen)
    await almacen.write_text(path, (await almacen.read_text(path)) + "cambio\n")
    with pytest.raises(ResultSdfUnavailable, match="SHA-256"):
        await read_result_sdf(SimpleNamespace(poses_file_path=None, docking_poses=poses))


@pytest.mark.asyncio
async def test_una_pose_sin_procedencia_abstiene_toda_la_composicion(almacen):
    poses, _path, _conformer = await pool(almacen)
    poses[0].source_provenance = None
    with pytest.raises(ResultSdfUnavailable, match="pose global 2"):
        await read_result_sdf(SimpleNamespace(poses_file_path=None, docking_poses=poses))


@pytest.mark.asyncio
async def test_ranks_duplicados_no_se_inventan_ni_se_renumeran(almacen):
    poses, _path, _conformer = await pool(almacen)
    poses[0].rank = 1
    with pytest.raises(ResultSdfUnavailable, match="rangos globales"):
        await read_result_sdf(SimpleNamespace(poses_file_path=None, docking_poses=poses))


@pytest.mark.asyncio
async def test_endpoint_A_compone_solo_snapshot_A_aunque_proyeccion_B_tenga_archivo(controlled, almacen):
    mid, owner, db, repo = controlled
    poses, _path, _conformer = await pool(almacen)
    repo.a.update(poses_file_path=None, docking_poses=[pose.model_dump() for pose in poses])
    response = await evaluation_files.get_pose_file(mid, owner, db, task_id="run-A")
    assert response.status_code == 200
    assert response.headers["x-moldesign-task-id"] == "run-A"
    assert response.headers["x-moldesign-poses-assembly"] == "verified_ensemble"
    assert response.headers["x-moldesign-poses-sha256"] == hashlib.sha256(response.body).hexdigest()
    assert response.body.startswith(b"pose2\n")
    assert b'"run-A"' in response.body and b'"run-B"' not in response.body
    assert repo.a["poses_file_path"] is None
    assert repo.reads == []  # no consulta archivo de B


@pytest.mark.asyncio
async def test_complejo_A_usa_composicion_y_receptor_A(controlled, almacen, monkeypatch):
    mid, owner, db, repo = controlled
    poses, _path, _conformer = await pool(almacen)
    repo.a.update(poses_file_path=None, docking_poses=[pose.model_dump() for pose in poses])
    import services.docking.pdb_assembly as assembly
    merge = Mock(return_value="COMPLEJO-A")
    monkeypatch.setattr(assembly, "merge_protein_ligand_pdb", merge)
    response = await evaluation_files.get_complex_file(mid, owner, db, task_id="run-A")
    assert response.body == b"COMPLEJO-A"
    assert merge.call_args.args[1].startswith("pose2\n")
    assert "20.000" in merge.call_args.args[0] and "30.000" not in merge.call_args.args[0]
    assert response.headers["x-moldesign-poses-assembly"] == "verified_ensemble"


@pytest.mark.asyncio
async def test_contactos_A_declaran_composicion_sin_inventar_archivo(controlled, almacen, monkeypatch):
    mid, owner, db, repo = controlled
    poses, _path, _conformer = await pool(almacen)
    repo.a.update(poses_file_path=None, docking_poses=[pose.model_dump() for pose in poses])
    from api.routers import interactions
    from services.interactions.analyzer import InteractionReport
    import services.interactions.analyzer as analyzer
    observed = {}
    def analyze_complex(**kwargs):
        from rdkit import Chem
        ligand = Chem.SDMolSupplier(str(kwargs["ligand_sdf_path"]), removeHs=False)[0]
        observed["z"] = ligand.GetConformer().GetAtomPosition(2).z
        return InteractionReport(str(mid), "7E2Y", kwargs["pose_rank"])
    monkeypatch.setattr(analyzer, "analyze_complex", analyze_complex)
    response = await interactions.get_interactions(str(mid), pose_rank=1, current_user=owner, db=db, task_id="run-A")
    assert response["task_id"] == "run-A"
    assert response["pose_source_path"] is None
    assert response["pose_source_kind"] == "verified_ensemble"
    assert response["pose_source_manifest"]["task_id"] == "run-A"
    assert response["pose_source_manifest"]["geometry_modified"] is False
    assert observed["z"] == 7.125  # pose global1=registrooriginal2; no la pose1 del archivo
