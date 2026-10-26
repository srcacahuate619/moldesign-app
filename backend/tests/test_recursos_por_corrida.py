"""A004/A009/A010: identidad de recursos y acciones sin cálculo científico nuevo.

Se usan routers/repositorio reales con almacenamiento y analizadores controlados.
El analizador de contactos y cualquier motor científico se sustituyen explícitamente.
"""
from __future__ import annotations

import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.routers import evaluation, evaluation_files, interactions, pro_features
from api.routers.evaluation_access import result_for_task
from tests.test_evaluation_files import RECEPTOR, _Database
# Importar antes del fixture evita que el motor retenga el almacenamiento controlado.
from services.docking import vina_service as vina_service_under_test


class RepositoryDouble:
    def __init__(self, molecule_id, owner):
        self.mid = molecule_id
        self.molecule = SimpleNamespace(user_id=owner.id, target=SimpleNamespace(
            pdb_id="7E2Y", name="Catalogo posterior", hotspots={}, spearman_rho=0.9), smiles="CCO")
        self.a = {"molecule_id": str(molecule_id), "task_id": "run-A",
            "poses_file_path": "runs/A/poses.sdf", "receptor_path": "runs/A/receptor.pdbqt",
            "receptor_sha256": hashlib.sha256(RECEPTOR.encode()).hexdigest()}
        self.b = dict(self.a, task_id="run-B", poses_file_path="runs/B/poses.sdf",
            receptor_path="runs/B/receptor.pdbqt", molecule=self.molecule)
        self.storage = {self.a["receptor_path"]: RECEPTOR,
            self.b["receptor_path"]: RECEPTOR.replace("20.000", "30.000")}
        self.reads = []

    async def get_or_create_test_user(self):
        return SimpleNamespace(id=uuid4())

    async def get_molecule(self, _mid):
        return self.molecule

    async def get_evaluation_result(self, _mid):
        return SimpleNamespace(**self.b)

    async def get_evaluation_run(self, task_id, molecule_id):
        return SimpleNamespace(task_id=task_id, status="SUCCESS") if task_id == "run-A" and molecule_id == self.mid else None

    async def materialize_run_snapshot(self, _run):
        return self.a.copy()

    async def exists(self, path):
        return path in self.storage

    async def read_text(self, path):
        self.reads.append(path)
        return self.storage[path]


@pytest.fixture
def controlled(monkeypatch):
    mid, owner = uuid4(), SimpleNamespace(id=uuid4())
    repo = RepositoryDouble(mid, owner)
    for router in (evaluation, evaluation_files, interactions, pro_features):
        monkeypatch.setattr(router, "Repository", lambda _db: repo)
    import utils.local_storage as storage
    monkeypatch.setattr(storage, "exists", repo.exists)
    monkeypatch.setattr(storage, "read_text", repo.read_text)
    monkeypatch.setattr(interactions, "exists", repo.exists)
    monkeypatch.setattr(interactions, "read_text", repo.read_text)
    return mid, owner, _Database(repo.molecule), repo


@pytest.mark.asyncio
async def test_receptor_A_usa_snapshot_hash_y_no_el_catalogo_ni_B(controlled):
    mid, owner, db, repo = controlled
    response = await evaluation_files.get_protein_file(mid, owner, db, task_id="run-A")
    assert response.status_code == 200
    assert response.headers["x-moldesign-task-id"] == "run-A"
    assert response.headers["x-moldesign-receptor-sha256"] == repo.a["receptor_sha256"]
    assert "20.000" in response.body.decode() and "30.000" not in response.body.decode()
    assert repo.reads == ["runs/A/receptor.pdbqt"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fault, expected", [("missing", 404), ("hash", 409), ("metadata", 409)])
async def test_receptor_A_ausente_o_ilegible_se_abstiene_sin_fallback(controlled, fault, expected):
    mid, owner, db, repo = controlled
    if fault == "missing":
        repo.storage.pop(repo.a["receptor_path"])
    elif fault == "hash":
        repo.a["receptor_sha256"] = "0" * 64
    else:
        repo.a["receptor_path"] = None
    with pytest.raises(HTTPException) as error:
        await evaluation_files.get_protein_file(mid, owner, db, task_id="run-A")
    assert error.value.status_code == expected
    assert not any("targets/" in path or "/B/" in path for path in repo.reads)


@pytest.mark.asyncio
async def test_snapshot_receptor_conserva_heteroatomos_e_hidrogenos(controlled):
    mid, owner, db, repo = controlled
    text = RECEPTOR + "HETATM    2  O   HOH A   2       5.000   0.000   0.000  1.00 20.00     0.000 OA\n" + "ATOM      3  H   ALA A   1       4.000   0.000   0.000  1.00 20.00     0.000 HD\n"
    repo.storage[repo.a["receptor_path"]] = text
    repo.a["receptor_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    response = await evaluation_files.get_protein_file(mid, owner, db, task_id="run-A")
    atom_lines = [line for line in response.body.decode().splitlines() if line.startswith(("ATOM", "HETATM"))]
    assert len(atom_lines) == 3
    assert any("HOH" in line for line in atom_lines)
    assert any(line[12:16].strip() == "H" for line in atom_lines)


@pytest.mark.asyncio
async def test_corrida_ajena_al_resultado_no_cae_a_proyeccion(controlled):
    mid, _owner, _db, repo = controlled
    with pytest.raises(HTTPException) as error:
        await result_for_task(repo, mid, "run-desconocida", projection=SimpleNamespace(**repo.b))
    assert error.value.status_code == 404
    assert repo.reads == []


@pytest.mark.asyncio
async def test_poses_y_complejo_A_usan_los_dos_recursos_de_A(controlled, monkeypatch):
    mid, owner, db, repo = controlled
    repo.storage[repo.a["poses_file_path"]] = "pose-A\nM  END\n"
    import services.docking.pdb_assembly as assembly
    merged = Mock(return_value="COMPLEJO-A")
    monkeypatch.setattr(assembly, "merge_protein_ligand_pdb", merged)
    poses = await evaluation_files.get_pose_file(mid, owner, db, task_id="run-A")
    complex_ = await evaluation_files.get_complex_file(mid, owner, db, task_id="run-A")
    assert poses.body == b"pose-A\nM  END\n" and complex_.body == b"COMPLEJO-A"
    protein_arg, ligand_arg = merged.call_args.args
    assert "20.000" in protein_arg and ligand_arg == "pose-A\nM  END\n"
    assert not any("/B/" in path or "targets/" in path for path in repo.reads)


@pytest.mark.asyncio
async def test_poses_historicas_no_dependen_de_que_exista_proyeccion_actual(controlled):
    mid, owner, db, repo = controlled
    repo.storage[repo.a["poses_file_path"]] = "pose-A\nM  END\n"
    repo.get_evaluation_result = AsyncMock(return_value=None)
    response = await evaluation_files.get_pose_file(mid, owner, db, task_id="run-A")
    assert response.body == b"pose-A\nM  END\n"
    assert repo.reads == [repo.a["poses_file_path"]]


@pytest.mark.asyncio
async def test_contactos_A_usan_pose_y_receptor_de_A(controlled, monkeypatch):
    mid, owner, db, repo = controlled
    from tests.test_interacciones_pose_corrida import _sdf_tres_poses
    from services.interactions.analyzer import InteractionReport
    import services.interactions.analyzer as analyzer
    repo.storage[repo.a["poses_file_path"]] = _sdf_tres_poses()
    observed = {}
    def analyze_complex(**kwargs):
        observed["protein"] = kwargs["protein_pdb_path"].read_text()
        return InteractionReport(str(mid), "7E2Y", kwargs["pose_rank"])
    monkeypatch.setattr(analyzer, "analyze_complex", analyze_complex)
    response = await interactions.get_interactions(str(mid), pose_rank=2, current_user=owner, db=db, task_id="run-A")
    assert response["task_id"] == "run-A" and response["pose_rank"] == 2
    assert response["pose_source_path"] == repo.a["poses_file_path"]
    assert response["protein_source_path"] == repo.a["receptor_path"]
    assert response["protein_source_sha256"] == repo.a["receptor_sha256"]
    assert "20.000" in observed["protein"] and "30.000" not in observed["protein"]
    assert not any("/B/" in path or "targets/" in path for path in repo.reads)


@pytest.mark.asyncio
@pytest.mark.parametrize("has_metadata", [True, False])
async def test_result_A_no_sobrescribe_metadata_historica_con_catalogo(controlled, has_metadata):
    mid, owner, db, repo = controlled
    from tests.test_report_contract import _canonical_result_payload
    payload = _canonical_result_payload()
    payload.update(repo.a)
    for key in ("target_name", "target_hotspots", "target_spearman_rho", "target_calibracion"):
        payload.pop(key, None)
    if has_metadata:
        payload.update(target_name="Historico A", target_hotspots=[{"name": "ALA1"}], target_spearman_rho=0.1, target_calibracion={"nivel": "historico"})
    repo.a = payload
    response = await evaluation.get_evaluation_result(mid, object(), owner, db, task_id="run-A")
    assert response.task_id == "run-A"
    assert response.target_name == ("Historico A" if has_metadata else None)
    assert response.target_spearman_rho == (0.1 if has_metadata else None)
    assert response.target_hotspots == ([{"name": "ALA1"}] if has_metadata else None)
    assert response.target_calibracion == ({"nivel": "historico"} if has_metadata else None)
    assert response.target_name != repo.molecule.target.name


@pytest.mark.asyncio
async def test_nuevo_snapshot_congela_metadata_una_sola_vez(monkeypatch):
    from core.models import EvaluationResultORM
    from db.repository import Repository
    import services.targets.calibracion as calibration
    mid, rid = uuid4(), uuid4()
    columns = {column.name: None for column in EvaluationResultORM.__table__.columns}
    columns.update(id=rid, molecule_id=mid, task_id="run-A")
    target = SimpleNamespace(name="Historico A", hotspots={"residues": ["ALA1"]}, spearman_rho=0.1)
    result = SimpleNamespace(**columns, molecule=SimpleNamespace(target=target))
    db = SimpleNamespace(add=Mock(), flush=AsyncMock())
    repository = Repository(db)
    repository.get_evaluation_run = AsyncMock(return_value=None)
    repository.get_evaluation_result = AsyncMock(return_value=result)
    monkeypatch.setattr(calibration, "estado_de_calibracion", lambda _target: SimpleNamespace(to_dict=lambda: {"estado": "sin_calibrar"}))
    snapshot = await repository.snapshot_evaluation_run(mid, "run-A")
    target.name = "Cambio posterior"
    target.hotspots["residues"].append("SER2")
    assert snapshot.snapshot_json["target_name"] == "Historico A"
    assert snapshot.snapshot_json["target_hotspots"] == {"residues": ["ALA1"]}
    repository.get_evaluation_run.return_value = snapshot
    assert await repository.snapshot_evaluation_run(mid, "run-A") is snapshot
    assert db.add.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["selectivity", "admet"])
async def test_acciones_historicas_rechazan_antes_de_computar(controlled, monkeypatch, action):
    mid, owner, db, _repo = controlled
    run_vina = AsyncMock(side_effect=AssertionError("No debe ejecutarse otra corrida"))
    monkeypatch.setattr(vina_service_under_test, "run_vina_docking", run_vina)
    monkeypatch.setattr(pro_features, "get_target_for_user", AsyncMock())
    with pytest.raises(HTTPException) as error:
        if action == "selectivity":
            await pro_features.dock_single_anti_target(str(mid), "5VA1", owner, db, task_id="run-A")
        else:
            await pro_features.run_admet_endpoint(str(mid), False, owner, db, task_id="run-A")
    assert error.value.status_code == 409
    run_vina.assert_not_awaited()
