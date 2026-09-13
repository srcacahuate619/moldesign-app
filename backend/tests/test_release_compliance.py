from pathlib import Path
import importlib.util

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("moldesign_bundle_helper", ROOT / "scripts" / "bundle_helper.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
validate_legal_release = MODULE.validate_legal_release
copy_git_tracked_tree = MODULE.copy_git_tracked_tree


def test_rtmscore_sin_licencia_bloquea_el_release(tmp_path: Path) -> None:
    (tmp_path / "rescoring" / "RTMScore").mkdir(parents=True)
    with pytest.raises(RuntimeError, match="BLOQUEO LEGAL"):
        validate_legal_release(tmp_path)


def test_rtmscore_con_licencia_explicita_supera_el_gate(tmp_path: Path) -> None:
    component = tmp_path / "rescoring" / "RTMScore"
    component.mkdir(parents=True)
    (component / "LICENSE").write_text("permiso de prueba", encoding="utf-8")
    validate_legal_release(tmp_path)


def test_tabpfn_desactiva_telemetria_antes_de_importar_fastapi() -> None:
    source = (ROOT / "backend" / "api" / "main.py").read_text(encoding="utf-8")
    telemetry = source.index('os.environ.setdefault("TABPFN_DISABLE_TELEMETRY", "1")')
    fastapi_import = source.index("from fastapi import FastAPI")
    assert telemetry < fastapi_import

# ── La raíz de rescoring/ es sys.path del runtime instalado ──────────────────
#
# Auditoría de backend del 2026-09-04, §4.1. `bundle_helper` ya excluye del
# instalador los directorios `tests/`, `data/`, `deprecated/` y `scripts/`, los
# `*.log` y los `scratch_*`. Lo que NO excluía es lo que estaba suelto en la
# raíz de `rescoring/` sin encajar en ningún patrón, y esa raíz se copia entera
# a `resources/rescoring`, que es sys.path del backend empaquetado:
#
#   feature_extractor_oddt_backup.py   respaldo de julio, 11 KB
#   feature_extractor_v2_backup.py     respaldo de julio, 28 KB
#   test_gnn_e2e.py y otros cinco      diagnósticos con rutas absolutas de esta
#                                      máquina — `D:\moldesign-app\rescoring`,
#                                      `d:\molecular-design\data\pdbbind`, y uno
#                                      con rutas de dentro de un contenedor
#
# Ninguno lo importaba nadie. Se retiraron. El coste no era el tamaño —53 KB—
# sino que un archivo llamado `test_*.py` en sys.path lo recoge cualquier
# recolección de pytest hecha sobre el árbol instalado, y un `*_backup.py` al
# lado del módulo real invita a leer el que no es.
#
# Los patrones de `bundle_helper` no bastan para impedir que vuelvan: `*.bak` no
# casa con `_backup.py`, y `scratch_*` no casa con `test_*`. Por eso la regla
# vive aquí, sobre el árbol fuente, en vez de en la lista de exclusiones.

_PATRONES_QUE_NO_VIAJAN = ("*_backup.py", "test_*.py", "scratch_*.py", "*.log")


def test_la_raiz_de_rescoring_no_lleva_sueltos_al_instalador() -> None:
    raiz = ROOT / "rescoring"
    encontrados = sorted(
        ruta.name
        for patron in _PATRONES_QUE_NO_VIAJAN
        for ruta in raiz.glob(patron)
        if ruta.is_file()
    )
    assert not encontrados, (
        "Archivos sueltos en la raíz de rescoring/, que se copia al instalador y "
        f"queda en sys.path del backend empaquetado: {encontrados}. "
        "Las pruebas de verdad van en rescoring/tests/; los diagnósticos, fuera "
        "del árbol."
    )


def test_rescoring_tests_sigue_siendo_el_sitio_de_las_pruebas() -> None:
    """La regla de arriba no puede cumplirse borrando la carpeta correcta."""
    oficial = ROOT / "rescoring" / "tests"
    assert oficial.is_dir(), "rescoring/tests/ desapareció"
    assert list(oficial.glob("test_*.py")), (
        "rescoring/tests/ se quedó sin pruebas: si se movieron, actualiza esta "
        "regla; si se borraron, es una pérdida de cobertura, no una limpieza."
    )


def test_bundle_rescoring_copia_solo_archivos_versionados(tmp_path: Path) -> None:
    """Un checkpoint local ignorado nunca puede colarse en el instalador."""
    import subprocess

    root = tmp_path / "repo"
    source = root / "rescoring"
    destination = root / "bundle" / "rescoring"
    source.mkdir(parents=True)
    (source / "model.json").write_text("{}", encoding="utf-8")
    (source / "checkpoint-local.pt").write_bytes(b"privado")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "rescoring/model.json"], check=True)

    copied = copy_git_tracked_tree(root, source, destination)

    assert copied == 1
    assert (destination / "model.json").is_file()
    assert not (destination / "checkpoint-local.pt").exists()
