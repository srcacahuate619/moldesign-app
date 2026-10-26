"""El rescoring y el censo de aguas leen lo mismo en el árbol de desarrollo que en la aplicación instalada (2026-10-24).

FEP-06-PRE lo destapó en cuatro de sus diez paquetes (1BN1, 1HSG, 6HW5, 6SXC), los únicos con un PDB sin comprimir en
`data/target_library`, que no viaja en el instalador:

* `get_target_pdb_path` devolvía ese depósito entero, con el ligando del cristal y las aguas. El filtro de poses de Model A
  contaba sus átomos como choques (de 10 a 83 por pose) y escribía «Ninguna pose pasó el filtro geométrico», mientras
  PoseBusters daba las nueve válidas. Instalado, el rescoring lee la copia que escribe `prepare_target`, sin el ligando.
* El censo de aguas sólo leía `targets/<ID>/raw.pdb`, que la preparación no escribe cuando parte de `target_library`, y decía
  «No se pudo leer la estructura depositada» mientras Preparación contaba esas aguas.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_evaluacion_caminos_propios import CRUDO_UNA, PROTEINA, _avisos_de_aguas


def test_el_rescoring_prefiere_la_copia_de_la_preparacion(tmp_path, monkeypatch):
    from services.docking import preparer

    monkeypatch.setattr(preparer.settings, "local_data_dir", str(tmp_path / "data"))
    biblioteca = tmp_path / "target_library" / "1BN1.pdb"
    biblioteca.parent.mkdir(parents=True)
    biblioteca.write_text("HETATM    1  C1  AL5 A 263       0.000   0.000   0.000  1.00  0.00           C\n")
    monkeypatch.setattr(preparer, "get_target_pdb_path", lambda pdb_id: str(biblioteca))

    assert preparer.pdb_para_rescoring("1BN1") == str(biblioteca)
    copia = tmp_path / "data" / "targets" / "1BN1.pdb"
    copia.parent.mkdir(parents=True)
    copia.write_text("ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N\n")
    assert Path(preparer.pdb_para_rescoring("1BN1")) == copia


def test_el_rescoring_rechaza_un_identificador_inseguro():
    from services.docking.preparer import pdb_para_rescoring

    with pytest.raises(ValueError):
        pdb_para_rescoring("../fuera")


def test_las_llamadas_del_rescoring_usan_la_copia_de_la_preparacion():
    """Model A, MM-GBSA y el XGBoost del pipeline: ninguno vuelve a `get_target_pdb_path`."""
    raiz = Path(__file__).resolve().parents[1] / "services"
    for ruta in ("docking/queue_handler.py", "pipeline/runner.py"):
        texto = (raiz / ruta).read_text(encoding="utf-8")
        assert "get_target_pdb_path" not in texto, ruta
        assert "pdb_para_rescoring(pipeline_params.target_pdb_id)" in texto, ruta


def test_la_preparacion_escribe_su_copia_aunque_haya_otra_en_la_biblioteca():
    texto = (Path(__file__).resolve().parents[1] / "services" / "docking" / "preparer.py").read_text(encoding="utf-8")
    assert "copia_pendiente = not compartido_local.exists() or not cadenas <= cadenas_compartidas" in texto


@pytest.mark.asyncio
async def test_el_censo_lee_el_origen_de_la_preparacion_sin_raw(tmp_path, monkeypatch):
    from services.docking import preparer

    origen = tmp_path / "biblioteca" / "USR_AGUA.pdb"
    origen.parent.mkdir(parents=True)
    origen.write_text(CRUDO_UNA, encoding="utf-8")
    monkeypatch.setattr(preparer, "receptor_source_path_no_network", lambda pdb_id: origen)
    avisos = await _avisos_de_aguas(tmp_path, monkeypatch, receptor=PROTEINA, crudo=None, modo=None)
    assert [a["codigo"] for a in avisos] == ["SITIO_DESOLVATADO"]
    assert "No se pudo leer" not in avisos[0]["mensaje"]
    assert "se retiraron 1 aguas" in avisos[0]["mensaje"]
