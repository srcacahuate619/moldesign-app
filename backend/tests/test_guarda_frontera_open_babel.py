"""La guarda de la frontera, puesta a prueba contra muestras rotas.

# Por qué esto existe

Un guardián que no demuestra que ve no sirve. Un detector de este árbol quedó
con un carácter `0x08` dentro de su expresión regular, recorrió 167 archivos y
anunció «limpio» sobre un export sucio: no falló, aprobó.

`scripts/check_openbabel_boundary.py` lleva un autotest interno para sus dos
detectores de texto (imports y resolución por PATH), que aborta el script si no
ven lo que deben. Pero las comprobaciones que miran el **disco** —el bundle, el
manifiesto, el hash, la versión, la conversión, la licencia declarada— no se
pueden autotestear desde dentro sin romper el árbol de verdad.

Aquí se rompen COPIAS. Cada prueba fabrica exactamente un defecto y exige que la
guarda correspondiente lo marque; y cada una comprueba también el caso sano, para
que un detector que dijera «roto» siempre tampoco pasara.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GUARDA = RAIZ / "scripts" / "check_openbabel_boundary.py"
HERRAMIENTA = RAIZ / "tools" / "openbabel"


def _cargar_guarda():
    """Importa el script de guarda como módulo, sin ejecutar su `main`."""
    if not GUARDA.is_file():
        pytest.skip("no está scripts/check_openbabel_boundary.py")
    spec = importlib.util.spec_from_file_location("_guarda_openbabel", GUARDA)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_guarda_openbabel"] = modulo
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


guarda = _cargar_guarda()

hay_herramienta = (HERRAMIENTA / "openbabel-manifest.json").is_file() and (
    HERRAMIENTA / "bin" / "obabel.exe"
).is_file()
necesita_binario = pytest.mark.skipif(
    not hay_herramienta,
    reason="tools/openbabel/ no está staged; en un clon limpio es normal",
)


@pytest.fixture
def copia(tmp_path):
    """Una copia escribible de `tools/openbabel/`, dentro de una raíz falsa."""
    if not hay_herramienta:
        pytest.skip("tools/openbabel/ no está staged")
    raiz = tmp_path / "arbol"
    destino = raiz / "tools" / "openbabel"
    destino.parent.mkdir(parents=True)
    shutil.copytree(HERRAMIENTA, destino)
    return raiz


def _resultado():
    return guarda.Resultado()


# ── El autotest interno de la guarda corre, y aprueba ───────────────────


def test_el_autotest_interno_de_la_guarda_pasa():
    """Si esto lanza SystemExit, la guarda se estaría anunciando a ciegas."""
    guarda.autotest()


def test_el_detector_de_imports_ve_las_cinco_formas():
    for muestra in guarda._DEBE_VER_IMPORT:
        assert guarda.importa_prohibido(muestra), muestra


def test_el_detector_de_imports_no_marca_prosa_ni_vecinos():
    for muestra in guarda._NO_DEBE_VER_IMPORT:
        assert not guarda.importa_prohibido(muestra), muestra


def test_el_detector_de_path_ve_las_formas_de_resolver_por_entorno():
    for muestra in guarda._DEBE_VER_PATH:
        assert guarda.resuelve_por_path(muestra), muestra


def test_el_detector_de_path_no_marca_ni_comentarios_ni_otras_herramientas():
    for muestra in guarda._NO_DEBE_VER_PATH:
        assert not guarda.resuelve_por_path(muestra), muestra


# ── G4: falta el ejecutable ─────────────────────────────────────────────


@necesita_binario
def test_g4_marca_la_falta_del_ejecutable(copia):
    sano = _resultado()
    guarda.g4_g7_herramienta(copia, "muestra", sano, exigir=True)
    assert sano.ok, sano.fallos

    (copia / "tools" / "openbabel" / "bin" / "obabel.exe").unlink()
    roto = _resultado()
    guarda.g4_g7_herramienta(copia, "muestra", roto, exigir=True)
    assert not roto.ok
    assert any("G4" in f for f in roto.fallos)


def test_g4_sin_manifiesto_falla_cuando_se_exige_y_salta_cuando_no(tmp_path):
    """Un clon limpio no trae binarios: ahí saltar es correcto, aprobar no.

    La distinción importa: si la ausencia se anunciara en verde, el gate de
    release pasaría sobre un árbol donde Open Babel simplemente no está.
    """
    vacio = tmp_path / "clon-limpio"
    (vacio / "tools").mkdir(parents=True)

    salta = _resultado()
    guarda.g4_g7_herramienta(vacio, "clon", salta, exigir=False)
    assert salta.ok and salta.saltado and not salta.verificado

    falla = _resultado()
    guarda.g4_g7_herramienta(vacio, "clon", falla, exigir=True)
    assert not falla.ok


# ── G5: el hash no coincide ─────────────────────────────────────────────


@necesita_binario
def test_g5_marca_un_ejecutable_alterado(copia):
    exe = copia / "tools" / "openbabel" / "bin" / "obabel.exe"
    exe.write_bytes(exe.read_bytes() + b"\x00alterado")
    roto = _resultado()
    guarda.g4_g7_herramienta(copia, "muestra", roto, exigir=True)
    assert not roto.ok
    assert any("G5" in f for f in roto.fallos)


@necesita_binario
def test_g5_marca_un_plugin_alterado_aunque_el_exe_este_intacto(copia):
    """Un `.obf` cambiado altera lo que el programa hace sin tocar el `.exe`.

    Comprobar sólo el ejecutable dejaría fuera 12 MB de plugins y tablas: es
    justo donde vive el comportamiento de conversión.
    """
    plugin = copia / "tools" / "openbabel" / "bin" / "formats_common.obf"
    plugin.write_bytes(plugin.read_bytes() + b"\x00")
    roto = _resultado()
    guarda.g4_g7_herramienta(copia, "muestra", roto, exigir=True)
    assert not roto.ok
    assert any("formats_common.obf" in f for f in roto.fallos)


@necesita_binario
def test_g5_marca_un_archivo_de_datos_ausente(copia):
    (copia / "tools" / "openbabel" / "bin" / "data" / "UFF.prm").unlink()
    roto = _resultado()
    guarda.g4_g7_herramienta(copia, "muestra", roto, exigir=True)
    assert not roto.ok
    assert any("UFF.prm" in f for f in roto.fallos)


# ── G6: la versión no es la declarada ───────────────────────────────────


@necesita_binario
def test_g6_marca_una_version_que_no_es_la_declarada(copia):
    ruta = copia / "tools" / "openbabel" / "openbabel-manifest.json"
    manifiesto = json.loads(ruta.read_text(encoding="utf-8"))
    manifiesto["version_reportada_por_el_binario"] = "4.0.0"
    ruta.write_text(json.dumps(manifiesto, ensure_ascii=False), encoding="utf-8")
    roto = _resultado()
    guarda.g4_g7_herramienta(copia, "muestra", roto, exigir=True)
    assert not roto.ok
    assert any("G6" in f and "4.0.0" in f for f in roto.fallos)


# ── G8: el contrato de persistencia ─────────────────────────────────────


def test_g8_pasa_sobre_el_arbol_real():
    sano = _resultado()
    guarda.g8_contrato_de_persistencia(sano)
    assert sano.ok, sano.fallos


def test_g8_marca_la_vuelta_de_la_persistencia_incondicional(monkeypatch, tmp_path):
    """Se reconstruye el defecto original y se exige que la guarda lo vea."""
    falso = tmp_path / "arbol"
    servicio = falso / "backend" / "services" / "docking"
    servicio.mkdir(parents=True)
    (falso / "backend" / "core").mkdir(parents=True)
    (servicio / "vina_service.py").write_text(
        "parsing_source = \"openbabel\"\n"
        "await write_file(output_sdf, poses_path)\n",
        encoding="utf-8",
    )
    (falso / "backend" / "core" / "models.py").write_text(
        'parsing_source: Literal["sdf", "pdbqt", "vina_stdout"] = "sdf"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(guarda, "RAIZ", falso)
    roto = _resultado()
    guarda.g8_contrato_de_persistencia(roto)
    assert not roto.ok
    mensaje = "\n".join(roto.fallos)
    assert "condicionada" in mensaje
    assert "coherencia" in mensaje
    assert "sdf_openbabel_cli" in mensaje


# ── G9: la licencia declarada ───────────────────────────────────────────


def test_g9_pasa_sobre_el_arbol_real():
    sano = _resultado()
    guarda.g9_licencia_declarada(sano)
    assert sano.ok, sano.fallos


def test_g9_marca_la_vuelta_de_or_later(monkeypatch, tmp_path):
    falso = tmp_path / "arbol"
    (falso / "frontend" / "lib").mkdir(parents=True)
    (falso / "frontend" / "public" / "legal").mkdir(parents=True)
    (falso / "frontend" / "lib" / "softwareCatalog.ts").write_text(
        'name: "Open Babel",\nlicense: "GPL-2.0-or-later",\n', encoding="utf-8"
    )
    (falso / "frontend" / "public" / "legal" / "THIRD_PARTY_NOTICES.md").write_text(
        "| Open Babel | 3.1.1.23 | GPL-2.0-or-later |\n", encoding="utf-8"
    )
    monkeypatch.setattr(guarda, "RAIZ", falso)
    monkeypatch.setattr(guarda, "RESOURCES", falso / "no-existe")
    roto = _resultado()
    guarda.g9_licencia_declarada(roto)
    assert not roto.ok
    assert any("or-later" in f.lower() for f in roto.fallos)


def test_g9_no_marca_a_los_componentes_que_si_son_or_later(monkeypatch, tmp_path):
    """Meeko es LGPL-2.1-or-later y xTB LGPL-3.0-or-later, legítimamente.

    Una guarda que los marcara sería ruido, y el ruido acaba en un `--skip`.
    """
    falso = tmp_path / "arbol"
    (falso / "frontend" / "lib").mkdir(parents=True)
    (falso / "frontend" / "public" / "legal").mkdir(parents=True)
    (falso / "frontend" / "lib" / "softwareCatalog.ts").write_text(
        'name: "Open Babel",\nlicense: "GPL-2.0-only",\n'
        'name: "Meeko",\nlicense: "LGPL-2.1-or-later",\n'
        'name: "xTB",\nlicense: "LGPL-3.0-or-later",\n',
        encoding="utf-8",
    )
    (falso / "frontend" / "public" / "legal" / "THIRD_PARTY_NOTICES.md").write_text(
        "| Meeko | 0.7.1 | LGPL-2.1-or-later |\n"
        "| Open Babel | 3.1.1.23 | GPL-2.0-only |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(guarda, "RAIZ", falso)
    monkeypatch.setattr(guarda, "RESOURCES", falso / "no-existe")
    sano = _resultado()
    guarda.g9_licencia_declarada(sano)
    assert sano.ok, sano.fallos


# ── G2: los bindings en el bundle ───────────────────────────────────────


def test_g2_marca_los_bindings_dentro_del_site_packages(monkeypatch, tmp_path):
    falso = tmp_path / "resources"
    site = falso / "python" / "Lib" / "site-packages"
    site.mkdir(parents=True)
    (site / "openbabel").mkdir()
    (site / "openbabel" / "__init__.py").write_text("", encoding="utf-8")
    (site / "rdkit").mkdir()
    monkeypatch.setattr(guarda, "RESOURCES", falso)
    roto = _resultado()
    guarda.g2_bindings_en_el_bundle(roto)
    assert not roto.ok
    assert any("openbabel" in f for f in roto.fallos)


def test_g2_marca_el_lanzador_de_pip_en_scripts(monkeypatch, tmp_path):
    """`python/Scripts/obabel.exe` es un lanzador con una ruta incrustada.

    Ese archivo fue un fallo real: resolvía a un intérprete de la máquina de
    construcción que en el equipo del usuario no existe.
    """
    falso = tmp_path / "resources"
    (falso / "python" / "Lib" / "site-packages").mkdir(parents=True)
    (falso / "python" / "Scripts").mkdir(parents=True)
    (falso / "python" / "Scripts" / "obabel.exe").write_bytes(b"MZ")
    monkeypatch.setattr(guarda, "RESOURCES", falso)
    roto = _resultado()
    guarda.g2_bindings_en_el_bundle(roto)
    assert not roto.ok
    assert any("obabel" in f for f in roto.fallos)


def test_g2_marca_los_modulos_cientificos_que_se_cuelan(monkeypatch, tmp_path):
    """La autorización de G1 no se cree a ciegas: se comprueba en el artefacto.

    `generate_gpu_dataset.py` y `extract_pocket_prody.py` pueden importar los
    bindings en el árbol de trabajo porque están declarados dependencia de
    desarrollo. Si además viajaran, esa declaración sería falsa.
    """
    falso = tmp_path / "resources"
    (falso / "python" / "Lib" / "site-packages").mkdir(parents=True)
    (falso / "rescoring" / "RTMScore" / "feats").mkdir(parents=True)
    (falso / "rescoring" / "generate_gpu_dataset.py").write_text("", encoding="utf-8")
    (falso / "rescoring" / "RTMScore" / "feats" / "extract_pocket_prody.py").write_text(
        "", encoding="utf-8"
    )
    monkeypatch.setattr(guarda, "RESOURCES", falso)
    roto = _resultado()
    guarda.g2_bindings_en_el_bundle(roto)
    assert not roto.ok
    mensaje = "\n".join(roto.fallos)
    assert "generate_gpu_dataset.py" in mensaje
    assert "extract_pocket_prody.py" in mensaje


def test_g2_pasa_con_un_site_packages_limpio(monkeypatch, tmp_path):
    falso = tmp_path / "resources"
    site = falso / "python" / "Lib" / "site-packages"
    site.mkdir(parents=True)
    for nombre in ("rdkit", "numpy", "meeko"):
        (site / nombre).mkdir()
    monkeypatch.setattr(guarda, "RESOURCES", falso)
    sano = _resultado()
    guarda.g2_bindings_en_el_bundle(sano)
    assert sano.ok, sano.fallos


# ── G1/G3 sobre un árbol de producción fabricado ────────────────────────


def test_g1_marca_un_import_en_codigo_de_produccion(monkeypatch, tmp_path):
    falso = tmp_path / "arbol"
    servicios = falso / "backend" / "services"
    servicios.mkdir(parents=True)
    (servicios / "convertidor.py").write_text(
        "from openbabel import openbabel\n\n\ndef convertir():\n    return openbabel\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(guarda, "RAIZ", falso)
    roto = _resultado()
    guarda.g1_g3_codigo(falso, "muestra", roto)
    assert not roto.ok
    assert any("G1" in f for f in roto.fallos)


def test_g3_marca_una_resolucion_por_path_en_produccion(monkeypatch, tmp_path):
    falso = tmp_path / "arbol"
    servicios = falso / "backend" / "services"
    servicios.mkdir(parents=True)
    (servicios / "convertidor.py").write_text(
        'import shutil\n\n\ndef exe():\n    return shutil.which("obabel")\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(guarda, "RAIZ", falso)
    roto = _resultado()
    guarda.g1_g3_codigo(falso, "muestra", roto)
    assert not roto.ok
    assert any("G3" in f for f in roto.fallos)


def test_g1_no_marca_las_pruebas_ni_el_adaptador(monkeypatch, tmp_path):
    """El adaptador nombra Open Babel por definición, y `tests/` no es producción."""
    falso = tmp_path / "arbol"
    adaptador = falso / "backend" / "services" / "external_tools"
    adaptador.mkdir(parents=True)
    (adaptador / "open_babel.py").write_text(
        'import subprocess\nEXE = "obabel.exe"\n', encoding="utf-8"
    )
    pruebas = falso / "backend" / "tests"
    pruebas.mkdir(parents=True)
    (pruebas / "test_x.py").write_text("from openbabel import openbabel\n", encoding="utf-8")
    monkeypatch.setattr(guarda, "RAIZ", falso)
    sano = _resultado()
    guarda.g1_g3_codigo(falso, "muestra", sano)
    assert sano.ok, sano.fallos
