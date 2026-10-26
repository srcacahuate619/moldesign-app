"""Escenas fieles a una corrida y límites reales del proceso de render."""
import asyncio
import os
import subprocess
import sys
import threading
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.dependencies import get_current_user
from api.routers import molcy
from core.database import get_db
from core import i18n
from services.molcy import cpu, gpu, renderer
from services.molcy.package import sha256
from services.molcy.process import run_owned, WindowsJob


def test_cpu_deja_margen_y_tiene_en_cuenta_aplicaciones_abiertas(monkeypatch):
    monkeypatch.setattr(cpu.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(cpu, "_afinidad", lambda: 8)
    monkeypatch.setattr(cpu, "_carga_actual", lambda: 0)
    idle = cpu.recursos()
    assert idle["cpu_hilos_maximos"] == 6 and idle["cpu_hilos"] == 4
    with pytest.raises(ValueError): cpu.validar_hilos(8, idle)
    monkeypatch.setattr(cpu, "_carga_actual", lambda: 50)
    busy = cpu.recursos()
    assert busy["cpu_hilos_maximos"] == 2
    assert busy["cpu_uso_actual_pct"] == 50
    with pytest.raises(ValueError): cpu.validar_hilos(4, busy)
    monkeypatch.setattr(cpu, "_carga_actual", lambda: None)
    assert cpu.recursos()["cpu_hilos_maximos"] == 6


def test_gpu_solo_identifica_tarjeta_confirmada_por_blender(monkeypatch):
    card = {"uuid":"GPU-TEST", "nombre":"NVIDIA TEST", "total_mib":8192, "libre_mib":6144, "usada_mib":2048}
    monkeypatch.setattr(gpu, "_tarjetas", lambda: [dict(card)])
    info = gpu.recursos({"gpu_vendor":"NVIDIA", "gpu_nombre":"NVIDIA TEST/PCIe"})
    assert info["gpu_vram_max_mib"] == 4096
    assert info["gpu_vram_reserva_mib"] == 2048
    assert gpu.recursos({"gpu_vendor":"Intel", "gpu_nombre":"Intel"}) == {"gpu_vram_monitorizable":False}
    with pytest.raises(ValueError): gpu.validar_presupuesto(6144, info)
    budget = gpu.validar_presupuesto(1024, info)
    guard = gpu.Vigilancia(budget)
    guard()
    card.update(usada_mib=3200, libre_mib=4992)  # gasto de otro proceso también consume el presupuesto
    guard.last = -1000000
    with pytest.raises(RuntimeError, match="presupuesto"): guard()
    monkeypatch.setattr(gpu, "_tarjetas", lambda: [])
    guard.last = -1000000
    with pytest.raises(RuntimeError, match="perdió"): guard()


def test_gpu_se_detiene_si_cae_margen_aunque_no_se_supere_el_presupuesto(monkeypatch):
    info = {"gpu_vram_uuid":"GPU-TEST", "gpu_vram_usada_mib":2048,
            "gpu_vram_reserva_mib":2048, "gpu_vram_presupuesto_mib":4096}
    monkeypatch.setattr(gpu, "_tarjetas", lambda: [{"uuid":"GPU-TEST", "usada_mib":2500, "libre_mib":1024}])
    with pytest.raises(RuntimeError, match="margen"): gpu.Vigilancia(info)()


def test_superar_presupuesto_cierra_el_proceso_y_no_entrega_render(tmp_path):
    owned = []
    def monitor(): raise RuntimeError("presupuesto superado")
    with pytest.raises(RuntimeError, match="presupuesto"):
        run_owned([sys.executable, "-c", "import time; time.sleep(60)"], env=dict(os.environ),
                  stdout=subprocess.DEVNULL, cancel=threading.Event(), on_start=owned.append,
                  timeout=60, cpu_rate=5000, monitor=monitor, cwd=str(tmp_path))
    assert owned[0].poll() is not None


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Objects")
def test_windows_job_acredita_tope_cpu_nativo_y_prioridad():
    import ctypes
    from ctypes import wintypes as w
    process = subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"])
    job = None
    try:
        job = WindowsJob(process, cpu_rate=5000)
        class Rate(ctypes.Structure): _fields_ = [("flags",w.DWORD),("rate",w.DWORD)]
        rate = Rate()
        job.api.QueryInformationJobObject.argtypes = [w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p]
        assert job.api.QueryInformationJobObject(job.handle,15,ctypes.byref(rate),ctypes.sizeof(rate),None)
        assert rate.flags == 5 and rate.rate == 5000
        import psutil
        assert psutil.Process(process.pid).nice() == psutil.BELOW_NORMAL_PRIORITY_CLASS
    finally:
        if job: job.close()
        process.kill() if process.poll() is None else None
        process.wait(timeout=10)


@pytest.mark.parametrize("scene,expected", [("receptor",202),("resultado",409)])
def test_moldex_receptor_usa_bytes_de_corrida_sin_exigir_poses(monkeypatch,tmp_path,scene,expected):
    user = SimpleNamespace(id=uuid.uuid4())
    target = SimpleNamespace(id=uuid.uuid4(),pdb_id="TEST",name="Receptor",chain="A",prepared_file_path="preparacion_actual_distinta")
    mol = SimpleNamespace(id=uuid.uuid4(),target=target)
    run = SimpleNamespace(status="SUCCESS",saved_at="guardado")
    receptor = b"ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00  0.00     0.000 C\n"
    snap = {"receptor_path":"receptor_de_corrida", "receptor_sha256":sha256(receptor),
            "docking_protocol":{"execution_provenance":{"box_center":[1,2,3],"box_size":[20,20,20]}}}
    repo = SimpleNamespace(get_evaluation_run=AsyncMock(return_value=run),materialize_run_snapshot=AsyncMock(return_value=snap))
    db = AsyncMock(); db.scalar.return_value=mol
    app = FastAPI(); app.include_router(molcy.router)
    async def database(): yield db
    app.dependency_overrides[get_db]=database
    app.dependency_overrides[get_current_user]=lambda:user
    monkeypatch.setattr(molcy,"Repository",lambda _:repo)
    monkeypatch.setattr(molcy,"_instalacion_estable",lambda:None)
    monkeypatch.setattr(cpu,"recursos",lambda:{"cpu_hilos":2,"cpu_logicos":8,"cpu_hilos_disponibles":8,"cpu_hilos_maximos":6})
    monkeypatch.setattr(renderer,"detectar",lambda:{"disponible":True,"gpu_disponible":True,"cpu_hilos_configurables":True})
    monkeypatch.setattr(molcy.disk,"assert_budget",lambda *_:None)
    monkeypatch.setattr(renderer,"raiz_trabajo",lambda *_:tmp_path)
    monkeypatch.setattr(molcy.storage, "crear_raiz", lambda *a, **k: tmp_path)  # sin esto escribía en los datos reales
    read = AsyncMock(return_value=receptor); monkeypatch.setattr(molcy,"read_bytes",read)
    launched = []
    monkeypatch.setattr(renderer,"iniciar",lambda *args,**kwargs:launched.append(kwargs))
    with TestClient(app) as client:
        response=client.post("/molcy/trabajos",json={"origen":"moldex","id":str(mol.id),"task_id":"run",
            "escena":scene,"formato":"previsualizacion","dispositivo":"gpu"})
    assert response.status_code == expected, response.text
    if expected == 202:
        read.assert_awaited_once_with("receptor_de_corrida")
        assert launched[0]["sujeto"] == "receptor_solo"
        assert launched[0]["fuente"]["task_id"] == "run"
        assert (tmp_path/"escenas/TEST/geometry/prepared.pdbqt").read_bytes() == receptor
        assert not (tmp_path/"escenas/TEST/docking.json").exists()
    else: assert launched == []


def test_limites_dinamicos_tienen_traduccion():
    token=i18n.set_request_locale("en")
    try:
        with pytest.raises(ValueError) as error: cpu.validar_hilos(8,{"cpu_hilos":4,"cpu_hilos_disponibles":8,"cpu_hilos_maximos":6})
        assert i18n.translate_text(str(error.value)).startswith("With current load")
    finally: i18n.reset_request_locale(token)


@pytest.fixture
def search_client(monkeypatch, tmp_path):
    user = SimpleNamespace(id=uuid.uuid4())
    mol = SimpleNamespace(id=uuid.uuid4(), target=SimpleNamespace(id=uuid.uuid4(), pdb_id="TEST", name="Receptor", chain="A"))
    receptor, poses = b"receptor saved with run", b"poses saved with run"
    metadata = {"receptor_sha256":sha256(receptor), "poses_sdf_sha256":sha256(poses),
                "ligand_pdbqt_sha256":"ligand-run", "box_center":[1,2,3], "box_size":[20,20,20], "seed":42}
    prov = {**metadata, "poses_sha256":sha256(poses), "search_trace":{"archive_path":"trace-run"}}
    snap = {"receptor_path":"receptor-run", "receptor_sha256":sha256(receptor), "poses_file_path":"poses-run",
            "vina_random_seed":42, "docking_protocol":{"execution_provenance":prov}}
    run = SimpleNamespace(status="SUCCESS", saved_at="saved", snapshot_json=snap, molecule_id=mol.id, task_id="run")
    repo = SimpleNamespace(get_evaluation_run=AsyncMock(return_value=run),
        materialize_run_snapshot=AsyncMock(return_value=snap), get_all_targets=AsyncMock(return_value=[]))
    db = AsyncMock(); db.scalar.return_value=mol
    db.execute.return_value=SimpleNamespace(all=lambda:[(run, "Molecule", "TEST")])
    app = FastAPI(); app.include_router(molcy.router)
    async def database(): yield db
    app.dependency_overrides[get_db]=database
    app.dependency_overrides[get_current_user]=lambda:user
    monkeypatch.setattr(molcy,"Repository",lambda _:repo)
    monkeypatch.setattr(molcy,"_instalacion_estable",lambda:None)
    monkeypatch.setattr(cpu,"recursos",lambda:{"cpu_hilos":2,"cpu_logicos":8,"cpu_hilos_disponibles":8,"cpu_hilos_maximos":6})
    monkeypatch.setattr(renderer,"detectar",lambda:{"disponible":True,"gpu_disponible":True,"cpu_hilos_configurables":True})
    monkeypatch.setattr(renderer,"busqueda_disponible",lambda:True)
    monkeypatch.setattr(molcy.disk,"assert_budget",lambda *_:None)
    monkeypatch.setattr(renderer,"raiz_trabajo",lambda *_:tmp_path)
    monkeypatch.setattr(molcy.storage, "crear_raiz", lambda *a, **k: tmp_path)  # sin esto escribía en los datos reales
    monkeypatch.setattr(molcy,"read_bytes",AsyncMock(side_effect=lambda name:{"receptor-run":receptor,"poses-run":poses}[name]))
    files = {"native":"recorded geometries"}
    recovered = AsyncMock(return_value=(metadata, files))
    monkeypatch.setattr(molcy.search_trace,"recover",recovered)
    packages, launched = [], []
    monkeypatch.setattr(molcy,"construir_paquete",lambda _,**kwargs:packages.append(kwargs))
    monkeypatch.setattr(renderer,"iniciar",lambda *_,**kwargs:launched.append(kwargs))
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, mol=mol, snap=snap, metadata=metadata, files=files,
                              recovered=recovered, packages=packages, launched=launched)


@pytest.mark.parametrize("condition", ["valid", "legacy", "old_motor", "corrupt", "other_ligand"])
def test_search_launch_requires_verified_trace_from_selected_run(search_client, monkeypatch, condition):
    case = search_client
    if condition == "legacy": case.snap["docking_protocol"]["execution_provenance"].pop("search_trace")
    if condition == "old_motor": monkeypatch.setattr(renderer,"busqueda_disponible",lambda:False)
    if condition == "corrupt": case.recovered.side_effect=ValueError("archive hash mismatch")
    if condition == "other_ligand": case.metadata["ligand_pdbqt_sha256"]="different-ligand"
    response = case.client.post("/molcy/trabajos", json={"origen":"moldex", "id":str(case.mol.id), "task_id":"run",
        "escena":"busqueda", "formato":"previsualizacion", "dispositivo":"gpu"})
    assert response.status_code == (202 if condition == "valid" else 409), response.text
    if condition == "valid":
        assert case.packages[0]["search_metadata"] == case.metadata
        assert case.packages[0]["search_files"] == case.files
        assert case.launched[0]["sujeto"] == "busqueda_montecarlo"
        assert case.launched[0]["fuente"]["task_id"] == "run"
        case.recovered.assert_awaited_once_with({"archive_path":"trace-run"})
    else:
        assert case.launched == [] and case.packages == []


@pytest.mark.parametrize("mismatch", [None, "receptor_sha256", "poses_sdf_sha256", "ligand_pdbqt_sha256", "seed", "box_center", "box_size"])
def test_source_offers_search_only_for_matching_trace(search_client, mismatch):
    case = search_client
    if mismatch: case.metadata[mismatch]="different-run"
    response=case.client.get("/molcy/fuentes")
    assert response.status_code == 200, response.text
    scenes=response.json()["moldex"][0]["escenas_disponibles"]
    assert scenes == (["resultado", "receptor", "busqueda"] if mismatch is None else ["resultado", "receptor"])


def test_gpu_sin_presupuesto_no_exige_telemetria_y_conserva_corrida(search_client, monkeypatch):
    case = search_client
    monkeypatch.setattr(renderer, "detectar", lambda: {"disponible":True, "gpu_disponible":True})
    def forbidden(*_):
        raise AssertionError("La VRAM automática no necesita telemetría ni presupuesto")
    monkeypatch.setattr(gpu, "recursos", forbidden)
    monkeypatch.setattr(gpu, "validar_presupuesto", forbidden)
    response = case.client.post("/molcy/trabajos", json={"origen":"moldex", "id":str(case.mol.id),
        "task_id":"run", "escena":"busqueda", "formato":"previsualizacion", "dispositivo":"gpu"})
    assert response.status_code == 202, response.text
    assert case.launched[0]["gpu_presupuesto"] is None
    assert case.launched[0]["fuente"]["task_id"] == "run"
    assert case.launched[0]["sujeto"] == "busqueda_montecarlo"


def test_presupuesto_explicito_de_cliente_anterior_sigue_exigiendo_telemetria(search_client, monkeypatch):
    monkeypatch.setattr(renderer, "detectar", lambda: {"disponible":True, "gpu_disponible":True})
    monkeypatch.setattr(gpu, "recursos", lambda _: {"gpu_vram_monitorizable":False})
    response = search_client.client.post("/molcy/trabajos", json={"origen":"moldex", "id":str(search_client.mol.id),
        "task_id":"run", "escena":"busqueda", "formato":"previsualizacion", "dispositivo":"gpu", "gpu_vram_mib":1024})
    assert response.status_code == 409, response.text
    assert search_client.launched == []
