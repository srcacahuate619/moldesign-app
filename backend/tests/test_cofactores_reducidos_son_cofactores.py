"""NDP (NADPH) y NAI (NADH) son cofactores: retirados junto al sitio abstienen, no piden «revisar otra especie».

Lo halló MET_datos (Sol 6.1, 2026-10-22) con 3AU9: «la receta automática no conserva NDP como uno de sus cofactores
reconocidos». La receta conserva NAP (NADP⁺) y NAD, no sus formas reducidas, y un NDP retirado se contaba como
`other_heteroatom` —lo mismo que un sulfato— y sólo pedía revisión.

Lo que se corrige es el NOMBRE de lo retirado, no la receta: conservar NDP exige una plantilla local, y la biblioteca de
plantillas entra en `receptor_recipe_hash` de los 381 receptores. Ninguna entrada del catálogo lleva NDP, NAI ni NAD
(medido el 2026-10-22 sobre `data/targets`), así que este cambio no mueve ningún receptor del catálogo. Las últimas pruebas
fijan que la receta no cambió.
"""

from __future__ import annotations

import pytest

from services.docking import preflight, preparer
from services.dossier.model import build_case_dossier
from services.dossier.preparacion import build_preparacion
from services.dossier.taxonomy import Estado
from tests.fixtures_dossier import caso_completo, resultado_completo
from tests.test_diff_de_especies_de_la_corrida import _atomo

CENTRO = (0.0, 0.0, 0.0)
CAJA = (10.0, 10.0, 10.0)


def _estructura(residuo: str, elemento: str = "P") -> str:
    return "\n".join([
        _atomo("ATOM", 1, "N", "ALA", "A", 1, 1.0, 0.0, 0.0, "N"),
        _atomo("ATOM", 2, "CA", "ALA", "A", 1, 2.0, 0.0, 0.0, "C"),
        _atomo("HETATM", 3, "P", residuo, "A", 301, 3.0, 2.0, 0.0, elemento),
        _atomo("HETATM", 4, "C1", "LIG", "A", 601, 0.0, 0.0, 1.0, "C"),
        "END",
    ]) + "\n"


def _diff(residuo: str) -> dict:
    estructura = _estructura(residuo)
    entrada = preparer.filter_pdb_content(estructura, chain_id={"A"}, keep_hetatm=True, cofactors_whitelist=[],
                                          site_ligand="LIG")
    return preflight.diff_de_especies_de_la_corrida(
        estructura, entrada, cadenas="A", center=CENTRO, size=CAJA, site_ligand="lig")


@pytest.mark.parametrize("residuo", ["NDP", "NAI"])
def test_la_forma_reducida_se_clasifica_como_cofactor(residuo):
    assert preflight._species_category(residuo) == "organic_cofactor"
    assert preflight.count_species(_estructura(residuo)).organic_cofactors == 1


@pytest.mark.parametrize("residuo", ["SO4", "GOL", "EDO"])
def test_un_aditivo_de_cristalizacion_sigue_siendo_otra_especie(residuo):
    """Control negativo: la corrección no convierte en cofactor todo lo que no se conoce."""
    assert preflight._species_category(residuo) == "other_heteroatom"
    assert preflight.count_species(_estructura(residuo)).organic_cofactors == 0


@pytest.mark.parametrize("residuo,esperado", [("NDP", Estado.ABSTENCION), ("NAI", Estado.ABSTENCION),
                                              ("NAP", Estado.REGISTRADO), ("SO4", Estado.REGISTRADO)])
def test_la_auditoria_abstiene_con_un_cofactor_retirado_y_no_con_uno_conservado(residuo, esperado):
    """NDP y NAI se retiran: abstienen. NAP la receta lo CONSERVA (no se retira, nada que abstener): ésa es la diferencia
    que escondía el defecto. SO4 retirado es un aditivo: no bloquea."""
    caso = caso_completo()
    resultado = resultado_completo()
    protocolo = dict(resultado.docking_protocol)
    protocolo["execution_provenance"] = {"receptor_prep": {"source": "meeko_report", "species_diff": _diff(residuo)}}
    resultado.docking_protocol = protocolo
    caso["eval_result"] = resultado
    dossier = build_case_dossier(**caso)
    auditoria = build_preparacion(dossier, resultado, caso["projection"], None)
    requisitos = {r["clave"]: r for b in auditoria["bloques"] for r in b["requisitos"]}
    assert requisitos["entorno.metales_cofactores"]["estado"] == esperado.value


def test_la_receta_no_cambio():
    """Conservar NDP exige plantilla y cambiaría el hash de receta de todo el catálogo: es una decisión aparte."""
    assert "NDP" not in preparer.ORGANIC_COFACTORS_KEPT and "NAI" not in preparer.ORGANIC_COFACTORS_KEPT
    assert preparer.RECEPTOR_RECIPE_VERSION == 7
    assert preparer._plantillas_sha256() == "11e19414717c112df6a7c598973d0199a7be1f590d8773fc75ce70dd94681fbd"
