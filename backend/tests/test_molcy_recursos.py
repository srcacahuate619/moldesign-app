"""Guardas de recursos y descarga explícita, sin red ni Blender real."""
from __future__ import annotations

import subprocess
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.molcy import addon, disk, renderer


def test_eta_se_calibra_con_fotogramas_reales_y_no_se_reinicia_al_codificar(tmp_path: Path):
    job_id = "12345678-1234-1234-1234-123456789012"
    suffix = job_id.replace("-", "")[:12]
    output = tmp_path / "salida"
    frames = output / f"render_previsualizacion_{suffix}"
    frames.mkdir(parents=True)
    parcial = output / f"build_previsualizacion_{suffix}.parcial.json"
    parcial.write_text(json.dumps({"fotogramas": 90}), encoding="utf-8")
    state = {"id": job_id, "formato": "previsualizacion"}
    for i in range(1, 6):
        png = frames / f"f_{i:04d}.png"
        png.write_bytes(b"png")
        os.utime(png, (1000 + i * 5, 1000 + i * 5))
        progress = renderer._progreso(tmp_path, state)
        if i < 5:
            assert "restante_render_principal_s" not in progress
    assert progress == {"progreso": {"fotogramas": 5, "total": 90},
                        "restante_render_principal_s": 425}
    final = output / f"build_previsualizacion_{suffix}.json"
    final.write_text(json.dumps({"fotogramas": 90}), encoding="utf-8")
    for png in frames.glob("*.png"):
        png.unlink()
    assert renderer._progreso(tmp_path, state) == {"progreso": {"fotogramas": 90, "total": 90}}


@pytest.mark.parametrize("name,dimensions", [
    ("previsualizacion", (720, 720, 90)),
    ("social_vertical", (1080, 1920, 360)),
    ("biblioteca", (1920, 1080, 681)),
])
def test_presupuesto_incluye_png_titulo_mp4_y_reserva(name, dimensions):
    width, height, frames = dimensions
    assert disk.FORMATS[name] == dimensions
    assert disk.required_bytes(name) > width * height * 4 * frames + disk.GIB


def test_cambio_de_formato_bloquea_presupuesto_obsoleto(tmp_path: Path):
    formats = tmp_path / "scripts" / "formatos"
    formats.mkdir(parents=True)
    values = {"previsualizacion": (720, 720, 3.0, 3.6),
              "social_vertical": (1080, 1920, 12.0, 3.6),
              "biblioteca": (1920, 1080, 22.7, 4.4)}
    for name, (width, height, seconds, ending) in values.items():
        (formats / f"{name}.py").write_text(
            f'FORMATO = Formato(nombre="{name}", ancho={width}, alto={height}, fps=30, segundos={seconds}, cierre_s={ending})')
    disk.validate_engine(tmp_path)
    (formats / "biblioteca.py").write_text(
        'FORMATO = Formato(nombre="biblioteca", ancho=3840, alto=2160, fps=30, segundos=22.7)')
    with pytest.raises(ValueError, match="cambió"):
        disk.validate_engine(tmp_path)


def test_espacio_insuficiente_bloquea_antes_del_render(monkeypatch, tmp_path: Path):
    need = disk.required_bytes("biblioteca")
    monkeypatch.setattr(disk.shutil, "disk_usage", lambda _: SimpleNamespace(free=need - 1))
    with pytest.raises(OSError, match="Espacio insuficiente"):
        disk.assert_budget(tmp_path / "aun_no_existe", "biblioteca")
    monkeypatch.setattr(disk.shutil, "disk_usage", lambda _: SimpleNamespace(free=need))
    assert disk.assert_budget(tmp_path / "aun_no_existe", "biblioteca")["disponible"]


def test_trabajo_no_lanza_subproceso_si_el_disco_se_llena_en_cola(monkeypatch, tmp_path: Path):
    root = tmp_path / "trabajo"
    root.mkdir()
    job_id = "12345678-1234-1234-1234-123456789012"
    estado = {"id": job_id, "estado": "en_cola", "formato": "biblioteca",
              "dispositivo": "gpu",
              "renderizador": {"motor": str(tmp_path), "blender": str(tmp_path / "blender.exe")},
              "sujeto": "receptor_solo"}
    # `platform` identifica la CPU con un subproceso la primera vez: no es Blender, pero esta prueba los prohíbe todos.
    monkeypatch.setattr(renderer.cpu, "recursos", lambda: {"cpu_hilos": 2, "cpu_logicos": 8, "cpu_hilos_disponibles": 8,
                                                           "cpu_hilos_maximos": 6})
    monkeypatch.setattr(disk, "assert_budget", lambda *_: (_ for _ in ()).throw(OSError("Espacio insuficiente")))
    monkeypatch.setattr(renderer.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("no debe lanzar Blender"))
    renderer._ejecutar(root, estado, "1HSG")
    assert estado["estado"] == "fallido"
    assert "Espacio insuficiente" in estado["motivo"]


def test_instalador_solo_usa_repositorio_oficial_y_blender_absoluto(monkeypatch, tmp_path: Path):
    blender = tmp_path / "blender.exe"
    blender.write_bytes(b"fake")
    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        if "repo-list" in cmd:
            return subprocess.CompletedProcess(cmd, 0, f'blender_org:\n    directory: "{tmp_path}"\n    {addon.OFFICIAL_REPOSITORY}\n', "")
        assert addon.estado()["fase"] == "descargando"
        return subprocess.CompletedProcess(cmd, 0, "installed", "")

    monkeypatch.setattr(addon.subprocess, "run", fake_run)
    monkeypatch.setattr(addon.disk, "free_bytes", lambda _: 2 * disk.GIB)
    def fake_detect(*, forzar=False):
        assert forzar is True, "tras instalar hay que comprobar de verdad, no reutilizar un sondeo anterior"
        assert addon.estado()["fase"] == "verificando"
        return {"disponible": True, "molecular_nodes": "520.2.0"}
    monkeypatch.setattr(renderer, "detectar", fake_detect)
    addon._instalar(blender)
    estado = addon.estado()
    # Cada intento deja su registro completo (VM-MOLCY-01); el resto del estado es el de siempre.
    assert estado.pop("registro").endswith(".log")
    assert estado == {"estado": "completo", "motivo": None, "version": "520.2.0"}
    assert calls[1] == [str(blender), "--online-mode", "--command", "extension",
                        "install", "-s", "-e", "blender_org.molecularnodes"]


def test_instalador_rechaza_repositorio_sustituido(monkeypatch, tmp_path: Path):
    blender = tmp_path / "blender.exe"
    blender.write_bytes(b"fake")
    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, 'url: "https://otro.example/ext"', "")

    monkeypatch.setattr(addon.subprocess, "run", fake_run)
    addon._instalar(blender)
    assert addon.estado()["estado"] == "fallido"
    assert len(calls) == 1


def test_instalador_bloquea_si_perfil_blender_no_tiene_espacio(monkeypatch, tmp_path: Path):
    blender = tmp_path / "blender.exe"
    blender.write_bytes(b"fake")
    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0,
            f'blender_org:\n    directory: "{tmp_path}"\n    {addon.OFFICIAL_REPOSITORY}\n', "")

    monkeypatch.setattr(addon.subprocess, "run", fake_run)
    monkeypatch.setattr(addon.disk, "free_bytes", lambda _: disk.GIB - 1)
    addon._instalar(blender)
    assert "Espacio insuficiente" in addon.estado()["motivo"]
    assert len(calls) == 1


def test_detector_distingue_addon_ausente_de_blender_ausente(monkeypatch, tmp_path: Path):
    blender = tmp_path / "blender.exe"
    blender.write_bytes(b"fake")
    monkeypatch.setenv("MOLCY_PERMITIR_MOTOR_PROPIO", "1")  # un motor propio sólo se acepta con el permiso de desarrollo
    engine = tmp_path / "motor"
    (engine / "scripts").mkdir(parents=True)
    (engine / "moldesign" / "assets" / "blender").mkdir(parents=True)
    (engine / "scripts" / "maestro.py").write_text("MOLCY_OUTPUT_DIR para_dispositivo")
    (engine / "scripts" / "correr_caso.ps1").write_text("Sujeto")
    (engine / "moldesign" / "assets" / "blender" / "plantilla_arte.blend").write_bytes(b"blend")
    monkeypatch.setattr(renderer, "_blender_candidatos", lambda: [blender])
    monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_engine_dir=str(engine)))
    monkeypatch.setattr(renderer.subprocess, "run", lambda *_args, **_kwargs:
                        subprocess.CompletedProcess([], 1,
                            'MOLCY_BLENDER_VERSION:[5,2,2]\n',
                            "ModuleNotFoundError: No module named 'bl_ext.blender_org.molecularnodes'"))
    capability = renderer.detectar()
    assert not capability["disponible"]
    assert capability["motivo_codigo"] == "falta_addon"
    assert capability["blender"] == str(blender)
    monkeypatch.setattr(renderer.subprocess, "run", lambda *_args, **_kwargs:
                        subprocess.CompletedProcess([], 1,
                            'MOLCY_BLENDER_VERSION:[5,2,2]\n',
                            "Cycles context unavailable"))
    capability = renderer.detectar()
    assert capability["motivo_codigo"] == "addon_no_carga"


@pytest.mark.parametrize("con_fotos", [True, False])
def test_detector_ofrece_fotos_con_cpu_si_eevee_falla(monkeypatch, tmp_path: Path, con_fotos):
    blender = tmp_path / "blender.exe"
    blender.write_bytes(b"fake")
    monkeypatch.setenv("MOLCY_PERMITIR_MOTOR_PROPIO", "1")  # un motor propio sólo se acepta con el permiso de desarrollo
    engine = tmp_path / "motor"
    (engine / "scripts").mkdir(parents=True)
    (engine / "moldesign" / "assets" / "blender").mkdir(parents=True)
    (engine / "scripts" / "maestro.py").write_text("MOLCY_OUTPUT_DIR" + (' "--fotos"' if con_fotos else ""))
    (engine / "scripts" / "correr_caso.ps1").write_text("Sujeto")
    if con_fotos:
        (engine / "scripts" / "correr_foto.py").write_text("# lanzador de fotos")
        (engine / "scripts" / "foto.py").write_text("# foto en Blender")
    (engine / "moldesign" / "assets" / "blender" / "plantilla_arte.blend").write_bytes(b"blend")
    monkeypatch.setattr(renderer, "_blender_candidatos", lambda: [blender])
    monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_engine_dir=str(engine)))
    monkeypatch.setattr(renderer.disk, "validate_engine", lambda _: None)
    calls = 0
    def fake_run(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess([], 0,
                'MOLCY_BLENDER_VERSION:[5,2,2]\nMOLCY_CPU_OK\n'
                'MOLCY_CAPS:{"version":[5,2,2],"molecular_nodes":"520.2.0"}\n', "")
        return subprocess.CompletedProcess([], 1, "", "GPU context unavailable")
    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    capability = renderer.detectar()
    # Sin EEVEE no hay vídeo; con un motor que sabe tomar fotos, la CPU sigue sirviendo para fotos.
    assert capability["disponible"] is con_fotos
    assert capability["foto_disponible"] is con_fotos
    assert capability["gpu_disponible"] is False
    assert capability["foto_gpu_disponible"] is False
    assert "cpu_disponible" not in capability and "cpu_limite_s" not in capability


def test_con_pausas_el_progreso_cuenta_los_png_distintos_no_los_del_video(tmp_path: Path):
    """Una pausa de lectura repite un PNG ya rendido: el render termina con menos PNG que fotogramas de vídeo."""
    job_id = "12345678-1234-1234-1234-123456789012"
    suffix = job_id.replace("-", "")[:12]
    output = tmp_path / "salida"
    frames = output / f"render_social_vertical_{suffix}"
    frames.mkdir(parents=True)
    parcial = output / f"build_social_vertical_{suffix}.parcial.json"
    parcial.write_text(json.dumps({"fotogramas": 438, "fotogramas_render_unicos": 287}), encoding="utf-8")
    for i in range(1, 288):
        (frames / f"f_{i:04d}.png").write_bytes(b"png")
    state = {"id": job_id, "formato": "social_vertical"}
    assert renderer._progreso(tmp_path, state) == {"progreso": {"fotogramas": 287, "total": 287}}


def test_el_limite_de_tres_segundos_de_la_cpu_ya_no_existe():
    """Era del vídeo por CPU, retirado el 2026-10-08: la CPU toma fotos de la escena entera."""
    assert not hasattr(renderer, "segundos_de_escena")
