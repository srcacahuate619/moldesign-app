"""Preparación nombra cada agua retirada junto al sitio, no sólo cuántas.

Prueba de cierre del informe FEP-ready de GPT 6 Sol (sección F, 1.0.2): «todas
las aguas retiradas figuran». Decidir qué aguas son estructurales y cuáles
desplazables exige saber CUÁLES eran; con un recuento no se puede decidir nada.
"""

from __future__ import annotations

import copy

from tests.test_diff_de_especies_de_la_corrida import _diff
from tests.test_preparacion_auditoria import _auditar, _con_procedencia, _requisito


def _agua(numero, distancia):
    return {"category": "water", "name": "HOH", "chain": "A", "residue_number": str(numero),
            "insertion_code": "", "distance_to_box_A": distancia}


def _con_aguas(retiradas, conservadas=()):
    diff = copy.deepcopy(_diff())
    cerca = diff["near_site"]
    cerca["removed"] = [f for f in cerca["removed"] if f["category"] != "water"] + list(retiradas)
    cerca["preserved"] = [f for f in cerca["preserved"] if f["category"] != "water"] + list(conservadas)
    return _auditar(_con_procedencia(species_diff=diff))


def test_cada_agua_retirada_figura_de_la_mas_cercana_a_la_mas_lejana():
    aguas = [_agua(412, 4.8), _agua(401, 0.0), _agua(405, 2.25)]
    requisito = _requisito(_con_aguas(aguas), "entorno.aguas")
    assert requisito["estado"] == "REVISAR"
    valor = requisito["valor"]
    assert valor.startswith("3 retirada(s)")
    posiciones = [valor.index(f"HOH A:{n}") for n in (401, 405, 412)]
    assert posiciones == sorted(posiciones)
    assert "ninguna conservada" in valor


def test_las_conservadas_tambien_se_nombran():
    requisito = _requisito(_con_aguas([_agua(401, 0.5)], [_agua(530, 3.1)]), "entorno.aguas")
    assert "1 conservada(s): HOH A:530 (3.1 Å)" in requisito["valor"]


def test_sin_aguas_retiradas_es_registrado():
    requisito = _requisito(_con_aguas([], [_agua(530, 3.1)]), "entorno.aguas")
    assert requisito["estado"] == "REGISTRADO"
