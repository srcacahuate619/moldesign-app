"""Un diff evaluado que no declara `margin_A` no puede decir «a X Å o menos»: se declara no evaluado y no revienta.

`_bloque_receptor` formateaba `margin_A` con `:g` y, sin él, lanzaba TypeError en cuanto el diff traía residuos de
proteína excluidos; `_bloque_entorno` ya lo trataba.
"""

from __future__ import annotations

import copy

from services.dossier.model import build_case_dossier
from services.dossier.preparacion import build_preparacion
from tests.test_preparacion_auditoria import _requisito
from tests.test_preparacion_desde_el_ligando import _caso


def test_sin_margen_las_dos_filas_quedan_no_evaluadas():
    caso = _caso()
    prov = copy.deepcopy(caso["eval_result"].docking_protocol["execution_provenance"])
    cerca = prov["receptor_prep"]["species_diff"]["near_site"]
    cerca.pop("margin_A", None)
    cerca["protein_residues_removed"] = {"B": 3}
    caso["eval_result"].docking_protocol = {**caso["eval_result"].docking_protocol, "execution_provenance": prov}

    auditoria = build_preparacion(build_case_dossier(**caso), caso["eval_result"], caso["projection"])

    for clave in ("receptor.cadenas_excluidas", "entorno.metales_cofactores"):
        fila = _requisito(auditoria, clave)
        assert fila["estado"] == "NO_EVALUADO", (clave, fila)
        assert "no declara el margen del sitio" in fila["razon"]
