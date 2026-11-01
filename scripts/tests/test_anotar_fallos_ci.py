"""Las anotaciones dicen qué prueba cayó, porque los registros de Actions piden sesión."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import anotar_fallos_ci as anotar

INFORME = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="3">
  <testcase classname="tests.test_a" name="test_pasa"/>
  <testcase classname="tests.test_a" name="test_cae"><failure message="assert 1 == 2&#10;otra linea 100%">traza</failure></testcase>
  <testcase classname="tests.test_b" name="test_rompe"><error message="">fallo al preparar</error></testcase>
  <testcase classname="tests.test_c" name="test_saltada"><skipped message="sin pypdf"/></testcase>
</testsuite></testsuites>
"""


def _informe(tmp_path: Path, texto: str = INFORME) -> Path:
    ruta = tmp_path / "junit.xml"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def test_nombra_cada_fallo_y_error_y_nada_mas(tmp_path):
    lineas = anotar.anotaciones([_informe(tmp_path)])
    assert len(lineas) == 2
    assert lineas[0] == "::error title=tests.test_a%3A%3Atest_cae::assert 1 == 2%0Aotra linea 100%25"
    assert lineas[1] == "::error title=tests.test_b%3A%3Atest_rompe::fallo al preparar"


def test_control_negativo_un_informe_verde_no_anota(tmp_path):
    verde = '<testsuites><testsuite tests="1"><testcase classname="t" name="ok"/></testsuite></testsuites>'
    assert anotar.anotaciones([_informe(tmp_path, verde)]) == []


def test_un_informe_ausente_se_dice(tmp_path):
    lineas = anotar.anotaciones([tmp_path / "no-existe.xml"])
    assert len(lineas) == 1
    assert lineas[0].startswith("::error title=Sin informe::")


def test_un_informe_a_medias_se_dice(tmp_path):
    lineas = anotar.anotaciones([_informe(tmp_path, "<testsuites><testsuite>")])
    assert len(lineas) == 1
    assert lineas[0].startswith("::error title=Sin informe::")


def test_un_simbolo_fuera_de_cp1252_no_tumba_el_paso(tmp_path):
    ruta = _informe(tmp_path, '<testsuites><testsuite><testcase classname="t" name="n"><failure message="ρ ≤ 0,3 → cae"/></testcase></testsuite></testsuites>')
    salida = subprocess.run([sys.executable, anotar.__file__, str(ruta)], capture_output=True,
                            env={**os.environ, "PYTHONIOENCODING": "cp1252"})
    assert salida.returncode == 0, salida.stderr
    assert "ρ ≤ 0,3 → cae".encode() in salida.stdout


def test_los_fallos_que_no_caben_se_nombran_en_una_sola_anotacion(tmp_path):
    casos = "".join(f'<testcase classname="t" name="n{i}"><failure message="m"/></testcase>' for i in range(anotar.TOPE + 3))
    lineas = anotar.anotaciones([_informe(tmp_path, f"<testsuites><testsuite>{casos}</testsuite></testsuites>")])
    assert len(lineas) == anotar.TOPE + 1
    assert lineas[-1].startswith("::error title=Otros 3 fallos::")
    assert f"t::n{anotar.TOPE + 2}" in lineas[-1]
