"""El motor Molcy sólo se ha ejecutado en Blender 5.2.2: con una versión anterior el detector se abstiene y lo dice.

# Qué se midió (2026-10-04, últimas LTS descargadas de download.blender.org, SHA-256 verificado)

- Blender 4.2.23 + Molecular Nodes 4.4.0: la plantilla de arte (guardada con 5.2) no se abre: «not a blend file». El motor muere
  en `arte.importar()` antes de dibujar nada.
- Blender 4.5.14 + Molecular Nodes 4.5.11: el motor ARRANCA y aborta su control de calidad («QC FATAL [dianas_dispersas]: el radio
  de las dianas (2.18) es el 348 % de la distancia del plano general»: la geometría de Molecular Nodes 4.x tiene otra escala), el
  atributo `resid 41:99` no existe y el motor EEVEE de 4.x se llama `BLENDER_EEVEE_NEXT`, así que la prueba de GPU falla.
- Hasta ahora el detector aceptaba cualquier Blender 4.2+ y dejaba que el usuario lo descubriera con un render fallido.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.molcy import renderer


def _motor_y_blender(tmp_path: Path, monkeypatch):
    blender = tmp_path / "blender.exe"
    blender.write_bytes(b"fake")
    engine = tmp_path / "motor"
    (engine / "scripts").mkdir(parents=True)
    (engine / "moldesign" / "assets" / "blender").mkdir(parents=True)
    (engine / "scripts" / "maestro.py").write_text("MOLCY_OUTPUT_DIR para_dispositivo")
    (engine / "scripts" / "correr_caso.ps1").write_text("Sujeto")
    (engine / "moldesign" / "assets" / "blender" / "plantilla_arte.blend").write_bytes(b"blend")
    monkeypatch.setattr(renderer, "_blender_candidatos", lambda: [blender])
    monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_engine_dir=str(engine)))
    monkeypatch.setattr(renderer.disk, "validate_engine", lambda _: None)
    renderer.invalidar()
    return blender


def _ejecutar_como(version: list[int], monkeypatch, llamadas: list, *, con_molecular_nodes: bool = True):
    marcador = f"MOLCY_BLENDER_VERSION:{version}\n".replace(" ", "")

    def falso(*_a, **_k):
        # `subprocess.run` está parcheado en todo el proceso: otras piezas (p. ej. el modelo de CPU) también lo usan.
        if "--python-expr" not in (_a[0] if _a else []):
            return subprocess.CompletedProcess([], 0, "", "")
        llamadas.append(1)
        if len(llamadas) == 1:
            if con_molecular_nodes:
                return subprocess.CompletedProcess([], 0, marcador + "MOLCY_CPU_OK\n"
                    f'MOLCY_CAPS:{{"version":{version},"molecular_nodes":"x"}}\n'.replace(" ", ""), "")
            return subprocess.CompletedProcess([], 1, marcador, "ModuleNotFoundError: No module named 'bl_ext.blender_org.molecularnodes'")
        return subprocess.CompletedProcess([], 0, "MOLCY_EEVEE_OK\n", "")

    monkeypatch.setattr(renderer.subprocess, "run", falso)


@pytest.mark.parametrize("version", [[4, 2, 23], [4, 5, 14], [5, 0, 3], [5, 1, 9]])
def test_un_blender_anterior_a_5_2_se_rechaza_sin_seguir_sondeando(version, monkeypatch, tmp_path):
    blender = _motor_y_blender(tmp_path, monkeypatch)
    llamadas: list = []
    _ejecutar_como(version, monkeypatch, llamadas)
    capacidad = renderer.detectar()
    assert capacidad["disponible"] is False
    assert capacidad["motivo_codigo"] == "blender_antiguo"
    assert "5.2" in capacidad["motivo"]
    assert capacidad["version_blender"] == version
    assert capacidad["blender"] == str(blender)
    assert len(llamadas) == 1, "no hay que lanzar la segunda sonda de un Blender que no se va a usar"


@pytest.mark.parametrize("version", [[5, 2, 0], [5, 2, 2], [5, 3, 0], [6, 0, 0]])
def test_5_2_o_posterior_sigue_el_camino_normal(version, monkeypatch, tmp_path):
    _motor_y_blender(tmp_path, monkeypatch)
    llamadas: list = []
    _ejecutar_como(version, monkeypatch, llamadas)
    capacidad = renderer.detectar()
    assert capacidad["disponible"] is True
    assert len(llamadas) == 2


def test_la_version_se_comprueba_antes_que_Molecular_Nodes(monkeypatch, tmp_path):
    """Un Blender 4.5 sin Molecular Nodes no debe recibir «instala Molecular Nodes»: instalarlo no lo haría válido."""
    _motor_y_blender(tmp_path, monkeypatch)
    _ejecutar_como([4, 5, 14], monkeypatch, [], con_molecular_nodes=False)
    capacidad = renderer.detectar()
    assert capacidad["motivo_codigo"] == "blender_antiguo"
    assert capacidad.get("motivo_codigo") != "falta_addon"


def test_un_resultado_de_version_antigua_no_se_guarda_en_la_cache(monkeypatch, tmp_path):
    _motor_y_blender(tmp_path, monkeypatch)
    llamadas: list = []
    _ejecutar_como([4, 5, 14], monkeypatch, llamadas)
    renderer.detectar()
    renderer.detectar()
    assert len(llamadas) == 2  # los negativos se vuelven a sondear: quien actualiza Blender ve el arreglo
