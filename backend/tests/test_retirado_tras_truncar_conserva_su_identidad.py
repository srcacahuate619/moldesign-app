"""Un residuo truncado y después retirado se nombra con su identidad del depósito (FEP-06-PRE, 2026-10-24).

En 1BN1 (P04), la LYS A:261 no tenía su O ni la cadena lateral entera: la receta la truncó a ALA y Meeko retiró después
el residuo. «Residuos retirados» decía «A:261 ALA», un residuo que no estaba en el origen, y la historia completa sólo se
podía reconstruir desde el backend.
"""
from __future__ import annotations

import copy

from core.i18n_plantillas import _PARECE_CASTELLANO
from services.dossier.localization import traducir_dossier
from tests.test_preparacion_auditoria import _auditar, _con_procedencia, _requisito


def _caso(truncadas: list[dict]):
    caso = _con_procedencia()
    prep = caso["eval_result"].docking_protocol["execution_provenance"]["receptor_prep"]
    prep["removed_residues"] = [{"chain": "A", "residue_number": "261", "insertion_code": "", "name": "ALA",
                                 "distance_to_box_A": 14.2, "site_critical": False}]
    prep["truncated_sidechains"] = copy.deepcopy(truncadas)
    return caso


TRUNCADA = {"chain": "A", "residue_number": "261", "insertion_code": "", "name": "LYS", "action": "truncado a ALA",
            "atoms_missing": ["CD", "CE", "NZ", "O"], "distance_to_box_A": 14.2, "site_critical": False}


def test_el_retirado_lleva_su_nombre_del_deposito():
    residuos = _requisito(_auditar(_caso([TRUNCADA])), "receptor.residuos_retirados")
    assert "A:261 LYS→ALA (14.2 Å)" in residuos["valor"]
    assert "«X→ALA» o «X→GLY»" in residuos["razon"]
    ingles = _requisito(traducir_dossier(_auditar(_caso([TRUNCADA])), "en"), "receptor.residuos_retirados")
    assert "A:261 LYS→ALA (14.2 Å)" in ingles["valor"]
    assert not _PARECE_CASTELLANO.search(ingles["razon"]), ingles["razon"]


def test_sin_truncado_el_texto_no_cambia():
    residuos = _requisito(_auditar(_caso([])), "receptor.residuos_retirados")
    assert "A:261 ALA (14.2 Å)" in residuos["valor"]
    assert "→" not in residuos["valor"] and "→" not in residuos["razon"]
