"""Las corridas guardadas sin nombre siguen siendo fuentes verificables de Molcy."""
import asyncio
import uuid
from types import SimpleNamespace
import pytest
from api.routers import molcy

@pytest.mark.parametrize("name", [None, "", "Diseño propio"])
def test_fuentes_sin_nombre_conservan_identidad_y_disponibilidad(monkeypatch, name):
    molecule_id=uuid.uuid4()
    task_id=str(uuid.uuid4())
    run=SimpleNamespace(molecule_id=molecule_id, task_id=task_id, snapshot_json={
        "receptor_path":"receptor.pdbqt", "receptor_sha256":"receptor-hash", "poses_file_path":"poses.sdf",
        "docking_protocol":{"execution_provenance":{"poses_sha256":"poses-hash", "box_center":[0,0,0],"box_size":[20,20,20]}}
    })
    class DB:
        async def execute(self, _statement): return SimpleNamespace(all=lambda:[(run,name,"1HSG")])
    class Repo:
        def __init__(self, _db): pass
        async def get_all_targets(self): return []
    monkeypatch.setattr(molcy,"Repository",Repo)
    value=asyncio.run(molcy.fuentes(SimpleNamespace(id=uuid.uuid4()),DB()))["moldex"][0]
    assert isinstance(value["nombre"],str) and value["nombre"]
    assert value["nombre"] == (name or f"MOL-{str(molecule_id)[:8]}")
    assert value["id"] == str(molecule_id)
    assert value["task_id"] == task_id
    assert value["disponible"] is True
    assert value["motivo"] is None
