"""Preparación declara las cadenas laterales que la receta v7 truncó.

Desde el rescate (`20955f1`), una cadena lateral que el cristal no resolvía se
trunca a ALA o GLY en vez de perder el residuo entero, y el informe lo registra
en `receptor_prep.truncated_sidechains`. En el sitio, la cavidad acoplada no es
la de la proteína: Preparación tiene que decirlo, no esconderlo en un aviso.
"""

from __future__ import annotations

from tests.test_preparacion_auditoria import _auditar, _con_procedencia, _requisito


def _con_truncadas(truncadas):
    caso = _con_procedencia()
    prov = caso["eval_result"].docking_protocol["execution_provenance"]
    if truncadas is not ...:
        prov["receptor_prep"]["truncated_sidechains"] = truncadas
    return caso


def _truncada(numero, distancia, en_sitio, nombre="LYS", destino="ALA"):
    return {"chain": "A", "residue_number": str(numero), "insertion_code": "", "name": nombre,
            "action": f"truncado a {destino}", "atoms_missing": ["CE", "NZ"],
            "distance_to_box_A": distancia, "site_critical": en_sitio}


def test_una_receta_anterior_a_v7_no_se_reconstruye():
    auditoria = _auditar(_con_truncadas(...))
    requisito = _requisito(auditoria, "receptor.cadenas_truncadas")
    assert requisito["estado"] == "NO_EVALUADO"
    assert requisito["imprescindible"] is False


def test_ninguna_truncada_es_registrado():
    requisito = _requisito(_auditar(_con_truncadas([])), "receptor.cadenas_truncadas")
    assert requisito["estado"] == "REGISTRADO"


def test_truncadas_fuera_del_sitio_piden_revision():
    auditoria = _auditar(_con_truncadas([_truncada(12, 21.4, False)]))
    requisito = _requisito(auditoria, "receptor.cadenas_truncadas")
    assert requisito["estado"] == "REVISAR"
    assert "fuera del sitio" in requisito["valor"]


def test_truncadas_en_el_sitio_se_nombran_y_no_bloquean():
    auditoria = _auditar(_con_truncadas([
        _truncada(45, 1.2, True, "ARG", "ALA"), _truncada(80, 3.9, True, "GLU", "GLY"),
        _truncada(200, 18.0, False),
    ]))
    requisito = _requisito(auditoria, "receptor.cadenas_truncadas")
    assert requisito["estado"] == "REVISAR"
    assert "3 truncada(s); 2 en el sitio" in requisito["valor"]
    assert "A:45 ARG→ALA (1.2 Å)" in requisito["valor"]
    assert "cavidad pierde" in requisito["razon"]
    assert "receptor.cadenas_truncadas" in auditoria["en_revision"]
    assert "receptor.cadenas_truncadas" not in auditoria["bloqueantes"]
