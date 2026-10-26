"""Una corrida de Batch con un receptor propio registra su modo de preparación, y el dossier de cohorte lo usa.

Batch acopla los bytes congelados del receptor y no lee el informe de preparación, así que `receptor_prep` quedaba sin
`modo_de_preparacion` y el supuesto de aguas decía «se eliminaron todas las aguas» de un receptor que las conservaba
(auditoría de los caminos propios, 2026-10-11).
"""

from __future__ import annotations

import inspect

from services.blockchain import evidence_summary as es
from services.docking import vina_service
from services.targets import perfil_receptor


def test_el_modo_sale_del_perfil_del_receptor_propio(monkeypatch):
    perfiles = {"USR_AAA111": {"modo": "respetar"}, "USR_BBB222": {"modo": "pdbqt"}, "USR_CCC333": {"modo": "automatico"}}
    monkeypatch.setattr(perfil_receptor, "cargar", lambda pdb_id: perfiles.get(pdb_id))
    assert vina_service.modo_del_receptor_congelado("USR_AAA111") == "respetar"
    assert vina_service.modo_del_receptor_congelado("USR_BBB222") == "pdbqt"
    assert vina_service.modo_del_receptor_congelado("USR_CCC333") is None
    assert vina_service.modo_del_receptor_congelado("1M17") is None
    assert vina_service.modo_del_receptor_congelado(None) is None


def test_el_protocolo_lo_registra_cuando_no_hay_informe():
    fuente = inspect.getsource(vina_service.run_vina_docking)
    assert "modo_del_receptor_congelado(target_pdb_id)" in fuente


def test_con_ese_modo_el_supuesto_de_aguas_es_el_del_archivo():
    corrida = type("R", (), {"docking_protocol": {"execution_provenance": {"receptor_prep": {
        "modo_de_preparacion": "respetar", "modo_de_preparacion_fuente": "perfil del receptor propio"}}}})()
    assert es._supuesto_de_aguas(corrida) == es.SUPUESTO_AGUAS_DEL_ARCHIVO
