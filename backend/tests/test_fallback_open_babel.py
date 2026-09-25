"""Regresión de la abstención cuando Meeko no exporta un SDF válido.

Open Babel permanece disponible como herramienta externa para usos históricos;
no puede reconstruir la identidad química perdida en el PDBQT de Vina.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from services.docking import vina_service

RAIZ_BACKEND = Path(__file__).resolve().parents[1]


def test_docking_se_abstiene_si_meeko_no_exporta_poses_sdf():
    fuente = inspect.getsource(vina_service.run_vina_docking)
    assert 'if not poses:' in fuente
    assert 'raise DockingFailed(' in fuente
    assert 'No se reconstruye la molécula desde el PDBQT de Vina.' in fuente
    assert 'convertir_pdbqt_a_sdf(' not in fuente
    assert 'parsing_source = "sdf_openbabel_cli"' not in fuente


def test_docking_conserva_el_sdf_y_la_correspondencia_de_poses():
    fuente = inspect.getsource(vina_service.run_vina_docking)
    assert 'await write_file(output_sdf, poses_path)' in fuente
    assert 'len(poses) != len(pdbqt_pose_blocks)' in fuente
    assert 'fusionar_rmsd_desde_pdbqt(' in fuente
    assert 'parsing_source = "sdf"' in fuente


def test_docking_no_resuelve_open_babel_por_path():
    fuente = inspect.getsource(vina_service.run_vina_docking)
    assert 'obabel' not in fuente.lower()
    assert 'open_babel' not in fuente.lower()


@pytest.mark.skipif(
    not (
        RAIZ_BACKEND.parent / "tools" / "openbabel" / "bin" / "obabel.exe"
    ).is_file(),
    reason="tools/openbabel/ no está staged",
)
def test_open_babel_sdf_conserva_las_poses_y_sus_metadatos():
    """Open Babel conserva las moléculas y los metadatos de Vina en el SDF.

    MEDIDO el 2026-09-05 sobre un PDBQT de salida de Vina real, de seis poses:
    el conversor escribe una propiedad REMARK por molécula; el parser extrae
    esos tres valores y el servicio puede persistir exactamente el SDF que
    respalda el informe. Los valores se comparan con el parser PDBQT original.
"""
    import asyncio

    from services.external_tools import open_babel
    from utils.file_handlers import parse_vina_output_pdbqt, parse_vina_output_sdf

    muestra = (
        RAIZ_BACKEND.parent
        / "data"
        / "dmfhard_curve_work"
        / "1aaq"
        / "curve30_conf0.out.pdbqt"
    )
    if not muestra.is_file():
        pytest.skip("no está el PDBQT de referencia de 1aaq")
    pdbqt = muestra.read_text(encoding="utf-8", errors="replace")

    conversion = asyncio.run(open_babel.convertir_pdbqt_a_sdf(pdbqt))
    assert open_babel.sdf_es_valido(conversion.contenido)
    assert conversion.contenido.count("$$$$") == 6, "las seis poses se convierten"
    # Y ninguna ruta del disco de quien corrió viaja dentro del archivo.
    assert "AppData" not in conversion.contenido
    assert ":\\" not in conversion.contenido
    assert conversion.contenido.splitlines()[0] == open_babel.TITULO_DE_LA_POSE
    assert ">  <REMARK>" in conversion.contenido
    assert "VINA RESULT" in conversion.contenido

    desde_sdf = parse_vina_output_sdf(conversion.contenido)
    assert len(desde_sdf) == 6, "el SDF convertido conserva las seis poses"
    assert [round(p["affinity"], 3) for p in desde_sdf] == [
        -5.693, -5.086, -4.775, -4.660, -4.074, -2.926
    ]
    assert [p["rank"] for p in desde_sdf] == list(range(1, 7))

    desde_pdbqt = parse_vina_output_pdbqt(pdbqt)
    assert [round(p["affinity"], 3) for p in desde_pdbqt] == [
        -5.693, -5.086, -4.775, -4.660, -4.074, -2.926
    ], "las afinidades del camino real no cambian"
    assert [p["affinity"] for p in desde_sdf] == [p["affinity"] for p in desde_pdbqt]


def test_no_se_fabrican_poses_ni_afinidades_en_el_respaldo():
    """El respaldo convierte un archivo; no inventa números.

    Las afinidades del camino de Open Babel salen del mismo parser que las del
    camino de Meeko (`parse_vina_output_sdf`), y los bloques PDBQT originales se
    conservan tal cual para trazabilidad.
    """
    fuente_respaldo = inspect.getsource(vina_service.run_vina_docking)
    assert "parse_vina_output_sdf" in fuente_respaldo
    assert "pdbqt_pose_blocks" in fuente_respaldo
