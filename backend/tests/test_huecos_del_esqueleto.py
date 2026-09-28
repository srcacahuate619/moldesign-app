"""Huecos del esqueleto: medidos en la preparación y declarados en Preparación.

Prueba de cierre del informe FEP-ready de GPT 6 Sol (R04): un hueco se prueba con
la distancia C(i)–N(i+1), no con un salto de numeración. Hasta el 2026-09-28 el
requisito salía siempre «no medido».
"""

from __future__ import annotations

from services.docking.preparer import MARGEN_SITIO_A, huecos_del_esqueleto
from tests.test_preparacion_auditoria import _auditar, _con_procedencia, _requisito


def _residuo(registro: str, nombre: str, cadena: str, numero: int, x0: float, serial: int) -> list[str]:
    """N, CA y C de un residuo a lo largo de x; C(i)–N(i+1) = 1,3 Å si x0 avanza 3,8."""
    lineas = []
    for i, (atomo, dx) in enumerate((("N", 0.0), ("CA", 1.46), ("C", 2.5))):
        lineas.append(
            f"{registro:<6}{serial + i:>5} {atomo:^4} {nombre:>3} {cadena}{numero:>4}    "
            f"{x0 + dx:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 20.00           {atomo[0]}"
        )
    return lineas


FUENTE = "\n".join([
    "REMARK 465 MISSING RESIDUES",
    "REMARK 465   M RES C SSSEQI",
    "REMARK 465     LYS A     3",
    "REMARK 465     GLU A     4",
    "REMARK 465     SER A     5",
])

CONTENIDO = "\n".join(
    _residuo("ATOM", "ALA", "A", 1, 0.0, 1)
    + _residuo("ATOM", "GLY", "A", 2, 3.8, 4)
    # 3, 4 y 5 no se observaron: el 6 empieza 12 Å más allá.
    + _residuo("ATOM", "LEU", "A", 6, 18.0, 7)
    # Residuo modificado en línea: sigue la cadena, no es un hueco.
    + _residuo("HETATM", "SEP", "A", 7, 21.8, 10)
    + _residuo("ATOM", "VAL", "A", 9, 29.4, 13)
    # Cadena B: salto de numeración 10 → 20 SIN hueco físico.
    + _residuo("ATOM", "ALA", "B", 10, 0.0, 16)
    + _residuo("ATOM", "GLY", "B", 20, 3.8, 19)
    # MSE escrito al final del archivo: su lugar es el 8, entre el 7 y el 9.
    + _residuo("HETATM", "MSE", "A", 8, 25.6, 22)
    # Agua: HETATM sin esqueleto, no cuenta.
    + ["HETATM   25  O   HOH A 301      40.000   0.000   0.000  1.00 20.00           O"]
)


def test_un_hueco_real_se_mide_con_sus_ausentes_declarados():
    huecos = huecos_del_esqueleto(CONTENIDO, FUENTE, (8.0, 0.0, 0.0), (10.0, 10.0, 10.0))
    assert len(huecos) == 1
    hueco = huecos[0]
    assert hueco["chain"] == "A"
    assert hueco["after"] == "GLY 2" and hueco["before"] == "LEU 6"
    assert hueco["c_n_distance_A"] > 10
    assert hueco["missing_declared"] == 3
    assert hueco["site_critical"] is True


def test_ni_el_salto_de_numeracion_ni_los_hetatm_de_la_cadena_son_huecos():
    huecos = huecos_del_esqueleto(CONTENIDO, FUENTE, (8.0, 0.0, 0.0), (10.0, 10.0, 10.0))
    assert [h["chain"] for h in huecos] == ["A"]
    assert all("SEP" not in (h["after"] + h["before"]) for h in huecos)
    assert all("MSE" not in (h["after"] + h["before"]) for h in huecos)


def test_lejos_de_la_caja_no_es_critico():
    huecos = huecos_del_esqueleto(CONTENIDO, FUENTE, (500.0, 0.0, 0.0), (10.0, 10.0, 10.0))
    assert huecos[0]["distance_to_box_A"] > MARGEN_SITIO_A
    assert huecos[0]["site_critical"] is False


def test_sin_remark_465_los_ausentes_no_se_inventan():
    huecos = huecos_del_esqueleto(CONTENIDO, "", (8.0, 0.0, 0.0), (10.0, 10.0, 10.0))
    assert huecos[0]["missing_declared"] is None


# ── En Preparación ───────────────────────────────────────────────────────


def _con_huecos(huecos):
    caso = _con_procedencia()
    prov = caso["eval_result"].docking_protocol["execution_provenance"]
    if huecos is not ...:
        prov["receptor_prep"]["backbone_gaps"] = huecos
    return _requisito(_auditar(caso), "receptor.huecos")


def test_una_preparacion_anterior_no_se_reconstruye():
    assert _con_huecos(...)["estado"] == "NO_EVALUADO"


def test_un_esqueleto_continuo_es_registrado():
    assert _con_huecos([])["estado"] == "REGISTRADO"


def test_un_hueco_junto_al_sitio_se_nombra_y_pide_revision():
    huecos = huecos_del_esqueleto(CONTENIDO, FUENTE, (8.0, 0.0, 0.0), (10.0, 10.0, 10.0))
    requisito = _con_huecos(huecos)
    assert requisito["estado"] == "REVISAR"
    assert "1 junto al sitio" in requisito["valor"]
    assert "A: GLY 2 → LEU 6" in requisito["valor"]
    assert "3 ausente(s) en REMARK 465" in requisito["valor"]
    assert "cavidad" in requisito["razon"]
    assert requisito["imprescindible"] is False
