"""
La caja de docking y el receptor: la relación geométrica se declara (SOL-07).

La auditoría lo midió con la API real: para `3F75`, centro
`(9999, 9999, 9999)` Å y tamaño `(5, 5, 5)` Å, el preflight devolvía 200,
cero bloqueantes y `GRID_EFECTIVO=pasa` — con el bolsillo de referencia en
`(43, 2, 46)` Å. El control comprobaba límites numéricos, nunca que la caja
tuviera algo delante: una búsqueda en espacio vacío entraba como si nada.

La regla que este archivo fija (criterio de cierre de la auditoría:
«informar la relación geométrica caja/receptor/sitio y registrar
explícitamente la decisión de buscar fuera del sitio»):

- La caja que abarca volumen con átomos del receptor → `pasa`.
- La caja separada del receptor → `advertencia` con la distancia medida y
  el registro explícito de que la búsqueda ocurrirá lejos de la
  estructura — puede ser intencional (exploración), pero se dice.
- Sin estructura que comparar → `no_evaluado`, no se inventa.

Se prueba sobre `_effective_configuration` directamente, que es donde
viven la caja efectiva y el texto filtrado de la ruta real.
"""

from __future__ import annotations

import math

import pytest

from services.docking import preflight as pf


#: Receptor mínimo con TODOS sus átomos cerca del origen (±15 Å): la caja
#: lejana de la auditoría queda a ~9980 Å de aquí.
RECEPTOR_CERCA_DEL_ORIGEN = "\n".join(
    [
        "ATOM      1  N   ALA A   1      11.104  13.207  10.000  1.00 20.00           N",
        "ATOM      2  CA  ALA A   1      12.560  13.207  10.000  1.00 20.00           C",
        "ATOM      3  N   GLY A   2      14.400  14.700  10.000  1.00 20.00           N",
        "ATOM      4  CA  GLY A   2      15.100  15.900  10.000  1.00 20.00           C",
        "END",
    ]
)


def _control(report: dict, code: str) -> dict:
    for control in report["controls"]:
        if control["code"] == code:
            return control
    raise AssertionError(
        f"El informe no incluye el control {code}: {[c['code'] for c in report['controls']]}"
    )


def _configurar(**overrides):
    """`_effective_configuration` con el receptor cerca del origen."""
    kwargs = dict(
        grid_center=(1.0, 2.0, 3.0),
        grid_size=(20.0, 20.0, 20.0),
        catalog_grid_center=None,
        catalog_grid_size=None,
        custom_hotspots=None,
        catalog_hotspots=None,
        cofactors_whitelist=None,
        filtered_text=RECEPTOR_CERCA_DEL_ORIGEN,
        prepared_chains=["A"],
        docking_engine="vina",
        exhaustiveness=None,
        num_poses=None,
    )
    kwargs.update(overrides)
    return pf._effective_configuration(**kwargs)


# ── 1. La reproducción de la auditoría ────────────────────────────────


def test_la_caja_lejana_se_declara_como_espacio_vacio():
    """Centro (9999, 9999, 9999) contra un receptor en el origen.

    Antes: sólo `GRID_EFECTIVO=pasa`, cero reserva. Ahora la distancia se
    MIDE y se dice, con el registro explícito de la decisión.
    """
    effective, controls = _configurar(
        grid_center=(9999.0, 9999.0, 9999.0),
        grid_size=(5.0, 5.0, 5.0),
    )

    # La caja efectiva es la que se pidió: el rango numérico sigue siendo
    # válido (GRID_EFECTIVO no cambia su veredicto).
    assert effective["grid_center"] == [9999.0, 9999.0, 9999.0]

    control = _control({"controls": [{"code": c.code, "state": c.state,
                                      "observation": c.observation,
                                      "reason": c.reason} for c in controls]},
                       "CAJA_VS_RECEPTOR")
    assert control["state"] == "advertencia"
    # La observación MIDE: la distancia y la extensión del receptor.
    assert "9999" in control["observation"] or "9" in control["observation"]
    assert "Å" in control["observation"]


def test_la_caja_que_abarca_el_receptor_pasa_sin_ruido():
    # Receptor x∈[11.1, 15.1], y∈[13.2, 15.9], z∈[10, 10]: caja centrada en
    # su corazón, lado 20 → lo abarca entero.
    effective, controls = _configurar(
        grid_center=(13.0, 14.5, 10.0),
        grid_size=(20.0, 20.0, 20.0),
    )

    assert effective["grid_center"] == [13.0, 14.5, 10.0]
    report = {"controls": [{"code": c.code, "state": c.state,
                            "observation": c.observation} for c in controls]}
    control = _control(report, "CAJA_VS_RECEPTOR")
    assert control["state"] == "pasa"
    assert "receptor" in control["observation"].lower()


def test_sin_estructura_no_se_inventa_la_comprobacion():
    """Receptor privado sin fuente en disco: la geometría no se finge."""
    _, controls = _configurar(filtered_text=None)

    report = {"controls": [{"code": c.code, "state": c.state} for c in controls]}
    control = _control(report, "CAJA_VS_RECEPTOR")
    assert control["state"] == "no_evaluado"


def test_la_distancia_al_sitio_del_catalogo_se_dice_cuando_existe():
    """Criterio de cierre: la relación caja/receptor/SITIO, con el centro del
    sitio del catálogo cuando el receptor lo declara."""
    _, controls = _configurar(
        grid_center=(9999.0, 9999.0, 9999.0),
        grid_size=(5.0, 5.0, 5.0),
        catalog_grid_center=(10.0, 10.0, 10.0),
    )

    report = {"controls": [{"code": c.code, "state": c.state,
                            "observation": c.observation} for c in controls]}
    control = _control(report, "CAJA_VS_RECEPTOR")
    assert control["state"] == "advertencia"
    assert "sitio" in control["observation"].lower()


def test_la_advertencia_no_bloquea_la_corrida():
    """La caja lejana puede ser intencional (exploración): se declara, no se
    impide. El preflight informa; el investigador decide."""
    _, controls = _configurar(
        grid_center=(9999.0, 9999.0, 9999.0),
        grid_size=(5.0, 5.0, 5.0),
    )

    estados = {c.code: c.state for c in controls}
    assert estados.get("CAJA_VS_RECEPTOR") != "bloquea"
    assert all(c.code != "GRID_EFECTIVO" or c.state == "pasa" for c in controls)


def test_un_pdb_sin_coordenadas_validas_no_revienta_el_control():
    """Texto presente pero sin átomos interpretables: `no_evaluado`, no 500."""
    _, controls = _configurar(filtered_text="ESTO NO ES UN PDB")

    report = {"controls": [{"code": c.code, "state": c.state} for c in controls]}
    control = _control(report, "CAJA_VS_RECEPTOR")
    assert control["state"] == "no_evaluado"


def test_la_caja_pegada_al_borde_del_receptor_cuenta_como_interseccion():
    """Borde a borde: la caja toca la extensión del receptor → pasa. Un poco
    más lejos → advertencia. La frontera no puede ser caprichosa.

    Receptor: x∈[11.1, 15.1], y∈[13.2, 15.9], z∈[10, 10].
    """
    # Caja centro (25, 25, 10), lado 20 → x∈[15, 35] (solapa x desde 15.1),
    # y∈[15, 35] (solapa y hasta 15.9), z∈[0, 20] (contiene z=10): toca.
    _, controls = _configurar(grid_center=(25.0, 25.0, 10.0), grid_size=(20.0, 20.0, 20.0))

    report = {"controls": [{"code": c.code, "state": c.state} for c in controls]}
    assert _control(report, "CAJA_VS_RECEPTOR")["state"] == "pasa"

    # Un poco más allá: centro (26, 25, 10) → x∈[16, 36], separación real de
    # 0.9 Å con la extensión del receptor.
    _, controls = _configurar(grid_center=(26.0, 25.0, 10.0), grid_size=(20.0, 20.0, 20.0))
    report = {"controls": [{"code": c.code, "state": c.state} for c in controls]}
    assert _control(report, "CAJA_VS_RECEPTOR")["state"] == "advertencia"
