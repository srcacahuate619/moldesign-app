"""Fallos reales de recursos, instalación y ciclo de vida; sin red ni GPU."""
from __future__ import annotations
import hashlib
import io
import json
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.dependencies import get_current_user
from api.routers import molcy
from services.molcy import disk, installation, renderer
from services.molcy.process import run_owned


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(installation, "data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(renderer, "data_dir", lambda: tmp_path / "data")
    # El índice de trabajos lo resuelve `storage`: sin esto el trabajo se escribía en los datos REALES del usuario.
    monkeypatch.setattr(renderer.storage, "data_dir", lambda: tmp_path / "data")
    (tmp_path / "data").mkdir()
    # Una carpeta de instalación de sólo lectura (WindowsApps) NO debe afectar al Blender administrado.
    monkeypatch.setenv("MOLDESIGN_INSTALL_DIR", str(tmp_path / "instalacion-de-solo-lectura"))
    return tmp_path


def test_managed_path_is_in_user_data_and_existing_blender_is_unchanged(isolated):
    own = isolated / "personal" / "blender.exe"
    own.parent.mkdir(); own.write_bytes(b"personal")
    installation.configure("existente", str(own), None)
    assert renderer._blender_candidatos() == [own]
    assert installation.environment(own).get("BLENDER_USER_CONFIG") is None
    installation.configure("administrado", None, None)
    managed = installation.blender_path()
    assert managed.is_relative_to(isolated / "data" / "molcy" / "blender")
    assert not managed.is_relative_to(isolated / "instalacion-de-solo-lectura")
    assert renderer._blender_candidatos() == [managed]
    assert "perfil_blender" in installation.environment(managed)["BLENDER_USER_CONFIG"]
    assert own.read_bytes() == b"personal"


def test_config_rejects_relative_and_missing_blender(isolated):
    with pytest.raises(ValueError): installation.configure("existente", "blender.exe", None)
    with pytest.raises(ValueError): installation.configure("existente", str(isolated / "missing.exe"), None)
    with pytest.raises(ValueError): installation.configure("administrado", None, "motor")


def test_download_rejects_corruption_even_if_server_size_matches(monkeypatch, isolated):
    content = b"corrupt official-sized archive"
    monkeypatch.setattr(installation, "DOWNLOAD_BYTES", len(content))
    monkeypatch.setattr(disk, "free_bytes", lambda _: 10 * disk.GIB)
    class Response(io.BytesIO):
        url = installation.URL
    monkeypatch.setattr(installation.urllib.request, "urlopen", lambda *_a, **_k: Response(content))
    installation._cancel.clear()
    with pytest.raises(ValueError, match="SHA-256"):
        installation._download(isolated / "blender.zip")


def test_download_can_cancel_without_touching_installation(monkeypatch, isolated):
    class Response(io.BytesIO):
        url = installation.URL
    monkeypatch.setattr(installation.urllib.request, "urlopen", lambda *_a, **_k: Response(b"download"))
    installation._cancel.set()
    try:
        with pytest.raises(InterruptedError): installation._download(isolated / "blender.zip")
        assert not installation.blender_path().exists()
    finally:
        installation._cancel.clear()


def test_zip_rejects_traversal_and_excess_space(monkeypatch, isolated):
    archive = isolated / "bad.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr(installation.ARCHIVE_ROOT + "/../../escape.exe", b"x")
    with pytest.raises(ValueError, match="ruta"): installation._validate_zip(archive)
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr(installation.ARCHIVE_ROOT + "/blender.exe", b"123")
    monkeypatch.setattr(installation, "MAX_UNPACKED", 2)
    with pytest.raises(ValueError, match="tamaño"): installation._validate_zip(archive)


def _zip_de_blender(ruta: Path, *, con_exe: bool = True) -> str:
    """ZIP mínimo con la estructura del oficial; devuelve su SHA-256 para fijarlo en la prueba."""
    with zipfile.ZipFile(ruta, "w") as package:
        package.writestr(installation.ARCHIVE_ROOT + "/license/COPYING.txt", b"gpl")
        if con_exe:
            package.writestr(installation.ARCHIVE_ROOT + "/blender.exe", b"MZ fake blender")
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def test_promotion_rechecks_pinned_hash_before_extracting(isolated):
    archive = isolated / "blender.zip"
    _zip_de_blender(archive)  # ZIP válido, pero NO el oficial: su hash no es el fijado
    with pytest.raises(ValueError, match="SHA-256"):
        installation._promote(archive, installation.blender_path().parent)
    assert not installation.blender_path().parent.exists()
    assert not any(p.name.startswith(".blender-") for p in installation.blender_path().parent.parent.glob("*"))


def test_promotion_extracts_into_user_data_without_powershell_or_elevation(monkeypatch, isolated):
    archive = isolated / "blender.zip"
    monkeypatch.setattr(installation, "SHA256", _zip_de_blender(archive))
    destino = installation.blender_path().parent
    installation._promote(archive, destino)
    assert (destino / "blender.exe").read_bytes() == b"MZ fake blender"
    assert (destino / "license" / "COPYING.txt").is_file()
    # sin carpeta temporal olvidada
    assert [p.name for p in destino.parent.iterdir()] == [installation.ARCHIVE_ROOT]
    assert destino.is_relative_to(isolated / "data")


def test_installer_has_no_elevation_path():
    """La elevación (Start-Process -Verb RunAs) y PowerShell salieron del instalador: no hay nada que elevar."""
    import ast
    arbol = ast.parse(Path(installation.__file__).read_text(encoding="utf-8"))
    docstring = ast.get_docstring(arbol, clean=False)
    cadenas = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and n.value != docstring]
    codigo = " ".join(cadenas).lower()
    assert "runas" not in codigo and "powershell" not in codigo and "expand-archive" not in codigo
    assert not [n for n in ast.walk(arbol) if isinstance(n, ast.Name) and n.id == "subprocess"]
    assert not hasattr(installation, "subprocess")
    assert not hasattr(installation, "install_root")


def test_promotion_rejects_a_destination_outside_the_managed_folder(monkeypatch, isolated):
    archive = isolated / "blender.zip"
    monkeypatch.setattr(installation, "SHA256", _zip_de_blender(archive))
    with pytest.raises(ValueError, match="no pertenece"):
        installation._promote(archive, isolated / "otra-carpeta")
    assert not (isolated / "otra-carpeta").exists()


def test_promotion_failure_never_claims_success_and_cleans_its_stage(monkeypatch, isolated):
    archive = isolated / "blender.zip"
    monkeypatch.setattr(installation, "SHA256", _zip_de_blender(archive, con_exe=False))
    destino = installation.blender_path().parent
    with pytest.raises(RuntimeError, match="no se instaló"):
        installation._promote(archive, destino)
    assert not destino.exists()
    assert not any(p.name.startswith(".blender-") for p in destino.parent.glob("*"))


def test_promotion_never_overwrites_an_existing_installation(monkeypatch, isolated):
    archive = isolated / "blender.zip"
    monkeypatch.setattr(installation, "SHA256", _zip_de_blender(archive))
    destino = installation.blender_path().parent
    destino.mkdir(parents=True)
    (destino / "blender.exe").write_bytes(b"la del usuario")
    with pytest.raises(RuntimeError, match="ya existe"):
        installation._promote(archive, destino)
    assert (destino / "blender.exe").read_bytes() == b"la del usuario"


def test_status_always_reports_a_path_even_without_an_install_folder(monkeypatch, isolated):
    monkeypatch.delenv("MOLDESIGN_INSTALL_DIR", raising=False)
    estado = installation.status()
    assert estado["ruta"] and estado["ruta"].startswith(str(isolated / "data"))
    assert estado["instalado"] is False


def test_installer_blocks_insufficient_disk_before_network(monkeypatch, isolated):
    monkeypatch.setattr(disk, "free_bytes", lambda _: disk.GIB)
    with installation._lock: installation._state.update(estado="inactivo")
    monkeypatch.setattr(installation._pool, "submit", lambda *_: pytest.fail("no network"))
    with pytest.raises(ValueError, match="Espacio insuficiente"): installation.start()


def test_every_video_budgets_its_outro_and_photos_budget_by_resolution():
    # The MolDesign outro closes EVERY video; video is GPU-only since 2026-10-08 (the CPU takes photos).
    assert all(frames > 0 for frames in disk.BRAND_FRAMES.values())
    assert disk.BRAND_FRAMES == {"previsualizacion": 108, "social_vertical": 108, "biblioteca": 132}
    assert disk.required_bytes("previsualizacion") < disk.required_bytes("social_vertical") < disk.required_bytes("biblioteca")
    fotos = [disk.photo_required_bytes(r) for r in ("720p", "1080p", "1440p", "4k")]
    assert fotos == sorted(fotos) and len(set(fotos)) == 4
    # A 4K photo is bounded by its own frames, far below any video.
    assert disk.RESERVE_BYTES < fotos[-1] < disk.required_bytes("previsualizacion")


def test_single_active_job_prevents_double_submit():
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    with renderer.reservar(first):
        with pytest.raises(ValueError, match="activo"):
            with renderer.reservar(second): pytest.fail("parallel render")
    with renderer.reservar(second): pass


def test_restart_reports_interrupted_and_preserves_completed_history(isolated):
    user, job = str(uuid.uuid4()), str(uuid.uuid4())
    root = renderer.raiz_trabajo(user, job); root.mkdir(parents=True)
    renderer.guardar_estado(root, {"id": job, "estado": "renderizando"})
    assert renderer.leer_estado(user, job)["estado"] == "fallido"
    assert renderer.listar(str(uuid.uuid4())) == []
    assert renderer.listar(user)[0]["id"] == job
    assert renderer.eliminar(user, job)
    assert not root.exists()


def test_active_job_cannot_be_deleted(isolated):
    user, job = str(uuid.uuid4()), str(uuid.uuid4())
    root = renderer.raiz_trabajo(user, job); root.mkdir(parents=True)
    renderer.guardar_estado(root, {"id": job, "estado": "en_cola"})
    with renderer.reservar(job):
        with pytest.raises(ValueError): renderer.eliminar(user, job)
    assert root.exists()


def test_api_ownership_expiring_media_and_range_requests(monkeypatch, isolated):
    user = SimpleNamespace(id=uuid.uuid4())
    app = FastAPI(); app.include_router(molcy.router)
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    job = str(uuid.uuid4()); root = renderer.raiz_trabajo(str(user.id), job)
    (root / "salida").mkdir(parents=True)
    content = b"test media with range requests"
    (root / "salida" / "test.mp4").write_bytes(content)
    (root / "salida" / "build.json").write_text('{}')
    renderer.guardar_estado(root, {"id": job, "estado": "completo", "video": "test.mp4",
        "video_sha256": hashlib.sha256(content).hexdigest(), "acta": "build.json"})
    access = client.post(f"/molcy/trabajos/{job}/acceso")
    assert access.status_code == 200
    route = access.json()["ruta"]
    response = client.get(route, headers={"Range": "bytes=0-3"})
    assert response.status_code == 206 and response.content == content[:4]
    assert client.get(f"/molcy/trabajos/{job}/procedencia").json()["schema"] == "molcy.procedencia/1"
    other = SimpleNamespace(id=uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.post(f"/molcy/trabajos/{job}/acceso").status_code == 404
    assert client.delete(f"/molcy/trabajos/{job}").status_code == 404
    token = route.rsplit('/',1)[-1]
    expiry, uid, jid = molcy._media[token]
    molcy._media[token] = (time.monotonic()-1,uid,jid)
    assert client.get(route).status_code == 404


def test_process_cancel_stops_owned_process_tree(tmp_path):
    event = threading.Event()
    timer = threading.Timer(0.7, event.set)
    timer.start()
    started = []
    try:
        with (tmp_path / "process.log").open("w") as output:
            with pytest.raises(InterruptedError):
                run_owned([sys.executable, "-c", "import time; time.sleep(60)"],
                          env=dict(__import__('os').environ), stdout=output,
                          cancel=event, on_start=started.append, timeout=10, cwd=str(tmp_path))
        assert started[0].poll() is not None
    finally:
        timer.cancel()


def test_non_object_state_is_reported_as_damaged(isolated):
    user, job = str(uuid.uuid4()), str(uuid.uuid4())
    root = renderer.raiz_trabajo(user, job); root.mkdir(parents=True)
    for malformed in ["null", "[]", '{"id":"otro"}']:
        (root / "estado.json").write_text(malformed)
        assert renderer.leer_estado(user, job)["estado"] == "fallido"


def test_configuration_is_blocked_during_addon_install(monkeypatch, isolated):
    app = FastAPI(); app.include_router(molcy.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    monkeypatch.setattr(molcy.addon, "estado", lambda: {"estado": "instalando"})
    monkeypatch.setattr(installation, "configure", lambda *_: pytest.fail("configuration race"))
    with TestClient(app) as client:
        assert client.put("/molcy/configuracion", json={"modo":"administrado"}).status_code == 409
        assert client.post("/molcy/blender").status_code == 409


def test_cancellation_kills_a_real_descendant(tmp_path):
    import os
    pid_file = tmp_path / "child.pid"
    event = threading.Event()
    failures = []
    def cancel_after_child():
        deadline = time.monotonic() + 8
        while not pid_file.exists() and time.monotonic() < deadline: time.sleep(.05)
        if not pid_file.exists(): failures.append("child was not started")
        event.set()
    thread = threading.Thread(target=cancel_after_child); thread.start()
    script = "import subprocess,sys,pathlib,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
    try:
        with (tmp_path / "tree.log").open("w") as output:
            with pytest.raises(InterruptedError):
                run_owned([sys.executable,"-c",script,str(pid_file)],env=dict(os.environ),
                          stdout=output,cancel=event,on_start=lambda _: None,timeout=15,cwd=str(tmp_path))
        assert not failures
        pid = int(pid_file.read_text())
        if os.name == "nt":
            import ctypes
            api = ctypes.WinDLL("kernel32", use_last_error=True)
            api.OpenProcess.restype = ctypes.c_void_p
            handle = api.OpenProcess(0x1000, False, pid)
            if handle:
                from ctypes import wintypes
                api.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
                api.CloseHandle.argtypes = [ctypes.c_void_p]
                code = wintypes.DWORD()
                try:
                    assert api.GetExitCodeProcess(handle,ctypes.byref(code))
                    assert code.value != 259
                finally: api.CloseHandle(handle)
        else:
            with pytest.raises(ProcessLookupError): os.kill(pid, 0)
    finally:
        thread.join(timeout=10)
