"""Contratos de archivos extraídos del router de evaluación (C-09)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from api.routers import evaluation_files


class _Database:
    def __init__(self, molecule):
        self.molecule = molecule

    async def get(self, _model, _molecule_id):
        return self.molecule


class _Repository:
    def __init__(self, *, result, molecule, demo_user):
        self.result = result
        self.molecule = molecule
        self.demo_user = demo_user

    async def get_evaluation_result(self, _molecule_id):
        return self.result

    async def get_molecule(self, _molecule_id):
        return self.molecule

    async def get_or_create_test_user(self):
        return self.demo_user


def _files_fixture(monkeypatch):
    molecule_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    molecule = SimpleNamespace(
        user_id=owner_id,
        target=SimpleNamespace(pdb_id="7E2Y"),
    )
    result = SimpleNamespace(poses_file_path="poses/example/7E2Y/poses.sdf")
    repository = _Repository(
        result=result,
        molecule=molecule,
        demo_user=SimpleNamespace(id=uuid.uuid4()),
    )
    monkeypatch.setattr(evaluation_files, "Repository", lambda _db: repository)
    return molecule_id, SimpleNamespace(id=owner_id), _Database(molecule)


@pytest.mark.asyncio
async def test_pose_file_preserves_sdf_response_contract_after_extraction(monkeypatch):
    molecule_id, current_user, db = _files_fixture(monkeypatch)
    import utils.local_storage as local_storage

    sdf = "pose-1\nM  END\n"

    async def read_text(object_name):
        assert object_name == "poses/example/7E2Y/poses.sdf"
        return sdf

    monkeypatch.setattr(local_storage, "read_text", read_text)

    response = await evaluation_files.get_pose_file(molecule_id, current_user, db)

    assert response.status_code == 200
    assert response.media_type == "chemical/x-mdl-sdfile"
    assert response.body == sdf.encode()
    assert response.headers["content-disposition"] == f'inline; filename="poses_{molecule_id}.sdf"'


@pytest.mark.asyncio
async def test_complex_file_preserves_pdb_response_contract_after_extraction(monkeypatch):
    molecule_id, current_user, db = _files_fixture(monkeypatch)
    import services.docking.pdb_assembly as pdb_assembly
    import utils.local_storage as local_storage

    raw_path = "targets/7E2Y/raw.pdb"
    sdf_path = "poses/example/7E2Y/poses.sdf"

    async def exists(object_name):
        return object_name == raw_path

    async def read_text(object_name):
        return {
            raw_path: "ATOM      1  N   ALA A   1\nEND\n",
            sdf_path: "pose-1\nM  END\n",
        }[object_name]

    async def write_text(_object_name, _content):
        raise AssertionError("No debe escribirse cuando el PDB raw ya está en cache")

    monkeypatch.setattr(local_storage, "exists", exists)
    monkeypatch.setattr(local_storage, "read_text", read_text)
    monkeypatch.setattr(local_storage, "write_text", write_text)
    monkeypatch.setattr(
        pdb_assembly,
        "merge_protein_ligand_pdb",
        lambda protein, sdf: f"MERGED\n{protein}{sdf}",
    )

    response = await evaluation_files.get_complex_file(molecule_id, current_user, db)

    assert response.status_code == 200
    assert response.media_type == "chemical/x-pdb"
    assert response.body.startswith(b"MERGED\nATOM")
    assert response.headers["content-disposition"] == f'inline; filename="complex_{molecule_id}.pdb"'


def test_all_file_routes_remain_under_evaluation_prefix_once():
    from api.routers.evaluation import router

    paths = [route.path for route in router.routes]
    for path in (
        "/evaluation/files/protein/{molecule_id}",
        "/evaluation/files/poses/{molecule_id}",
        "/evaluation/files/complex/{molecule_id}",
    ):
        assert paths.count(path) == 1

