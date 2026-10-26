"""La procedencia del dossier y de `run/protocol.json` lleva la caja ejecutada (FEP-06-PRE, 2026-10-24).

La evaluación individual no rellena `docking_box`: la caja que corrió vive en `execution_provenance`. La procedencia la
buscaba sólo en `docking_box`, así que los diez paquetes de FEP-06-PRE decían `grid_center: null`, `grid_size: null` y
ningún hash de configuración, con la caja efectiva escrita en el mismo fichero.
"""
from __future__ import annotations

from types import SimpleNamespace

from services.blockchain.evidence_summary import build_provenance


def _corrida(**extra):
    protocolo = {"engine": "vina", "seed": 42, "exhaustiveness": 8, "num_poses": 9,
                 "execution_provenance": {"box_center": [-3.857, 5.196, 14.831], "box_size": [22.0, 22.0, 22.0]}}
    base = dict(docking_protocol=protocolo, ligand_state={"smiles_acoplado": "CCO"}, receptor_path="r.pdbqt",
                docking_box=None, docking_poses=[{"pdbqt_block": "MODEL 1"}], vina_version="1.2.7",
                engine_used="vina", model_used="universal")
    base.update(extra)
    return SimpleNamespace(**base)


def test_sin_docking_box_la_caja_sale_de_la_procedencia_de_la_ejecucion():
    p = build_provenance(_corrida())
    assert p["configuracion"]["grid_center"] == [-3.857, 5.196, 14.831]
    assert p["configuracion"]["grid_size"] == [22.0, 22.0, 22.0]
    assert p["configuracion_sha256"] is not None
    assert "configuracion_sha256" not in p["campos_ausentes"]


def test_docking_box_declarada_sigue_mandando():
    p = build_provenance(_corrida(docking_box={"grid_center": [1, 2, 3], "grid_size": [20, 20, 20]}))
    assert p["configuracion"]["grid_center"] == [1, 2, 3]


def test_sin_ninguna_caja_se_declara_el_hueco():
    corrida = _corrida()
    corrida.docking_protocol = {"engine": "vina", "seed": 42}
    p = build_provenance(corrida)
    assert p["configuracion"]["grid_center"] is None
    assert "configuracion_sha256" in p["campos_ausentes"]
