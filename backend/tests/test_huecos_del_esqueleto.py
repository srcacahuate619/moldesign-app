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


def test_un_hueco_junto_al_sitio_bloquea_y_se_nombra():
    huecos = huecos_del_esqueleto(CONTENIDO, FUENTE, (8.0, 0.0, 0.0), (10.0, 10.0, 10.0))
    requisito = _con_huecos(huecos)
    assert requisito["estado"] == "ABSTENCION"
    assert "1 junto al sitio" in requisito["valor"]
    assert "A: GLY 2 → LEU 6" in requisito["valor"]
    assert "3 ausente(s) en REMARK 465" in requisito["valor"]
    assert "cavidad" in requisito["razon"]
    assert requisito["imprescindible"] is True

# ── Orden del polímero: el del archivo (2026-10-11) ───────────────────────────────────────────────────────────
#
# El detector ordenaba los residuos por (número, inserción). Medido sobre las 381 entradas del catálogo, 28
# perdían cortes inventados con el orden del archivo y las que tenían algún hueco junto al sitio pasaban de 137 a
# 126: numeración de quimotripsina con la inserción antes del número base (1KLI, 4JYV, 5L2Y…), numeración que
# no crece (1M6D) y GPCR con una proteína de fusión numerada 1001+ en mitad de la cadena (4NC3, 5WIU…). El único
# hueco que aparece es real: 6CM4 TYR 1161 → SER 364, C–N 4,56 Å, que el orden numérico no veía.


def _serie(residuos, rupturas=()):
    """Residuos (número, inserción) en el orden dado, enlazados salvo antes de los índices de `rupturas`."""
    lineas, x = [], 0.0
    for indice, (numero, insercion) in enumerate(residuos):
        if indice in rupturas:
            x += 10.0
        lineas.extend(linea[:26] + insercion + linea[27:]
                      for linea in _residuo("ATOM", "ALA", "H", numero, x, 1 + indice * 3))
        x += 3.8
    return "\n".join(lineas)


def test_insercion_depositada_antes_del_numero_base_no_inventa_huecos():
    """1KLI deposita 184A antes de 184: ordenarlos alfabéticamente inventaba cortes."""
    fuente = _serie(((183, " "), (184, "A"), (184, " "), (185, " ")))
    assert huecos_del_esqueleto(fuente, fuente, (8.0, 0.0, 0.0), (30.0,) * 3) == []


def test_insercion_inversa_sigue_detectando_una_ruptura_fisica_real():
    fuente = _serie(((183, " "), (184, "A"), (184, " "), (185, " ")), rupturas=(2,))
    huecos = huecos_del_esqueleto(fuente, fuente, (8.0, 0.0, 0.0), (30.0,) * 3)
    assert [(h["after"], h["before"], h["c_n_distance_A"], h["site_critical"]) for h in huecos] == [
        ("ALA 184A", "ALA 184", 11.3, True),
    ]


def test_una_numeracion_que_no_crece_en_el_archivo_no_es_un_hueco():
    """1M6D (catepsina F): 152, 153, 154A, 155A, 156A, 152B, 153A, 154… con C–N de 1,33 Å en todo el tramo."""
    fuente = _serie(((152, " "), (153, " "), (154, "A"), (155, "A"), (156, "A"), (152, "B"), (153, "A"),
                     (154, " "), (155, " "), (156, " ")))
    assert huecos_del_esqueleto(fuente, fuente, (8.0, 0.0, 0.0), (60.0,) * 3) == []


def test_una_proteina_de_fusion_en_mitad_de_la_cadena_no_inventa_cortes_y_su_union_rota_se_ve():
    """GPCR con lisozima o BRIL numerada 1001+ entre dos hélices; la unión C-terminal está rota."""
    residuos = ((229, " "), (230, " "), (1001, " "), (1002, " "), (1003, " "), (240, " "), (241, " "))
    continuo = _serie(residuos)
    assert huecos_del_esqueleto(continuo, continuo, (8.0, 0.0, 0.0), (60.0,) * 3) == []
    roto = _serie(residuos, rupturas=(5,))
    huecos = huecos_del_esqueleto(roto, roto, (8.0, 0.0, 0.0), (60.0,) * 3)
    assert [(h["after"], h["before"]) for h in huecos] == [("ALA 1003", "ALA 240")]
