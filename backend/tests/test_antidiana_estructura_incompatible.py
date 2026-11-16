"""OPRK1 / 7UL2: una estructura de otra proteína no se ofrece como anti-diana (D-09, revisión final §10).

7UL2 es NTSR1 con un segmento de OPRK1 insertado. El redocking de su ligando (Q6Q) pasó, pero sólo prueba que la caja
describe la cavidad de ese ligando, no que la cavidad sea del receptor kappa. El panel la daba por `validada`; ahora la
marca `estructura_incompatible` y conserva `sitio_adjudicado: false` para que las corridas históricas que la usaron sigan
declarando su límite. La caja con la que se acoplaron se conserva como registro (la geometría que prueba la incompatibilidad
se mide a partir de ella, `docs/auditorias/revision-final-1.0.4/comprobar_d09.py`); lo que impide acoplarla es el estado.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from services.docking.selectivity import (
    anti_dianas_seleccionables_de_bowes,
    panel_bowes_2012,
    sitio_adjudicado_de,
)

RAIZ = Path(__file__).resolve().parents[2]


def _fila_oprk1() -> dict:
    return next(f for f in panel_bowes_2012() if f.get("gen") == "OPRK1")


def test_7ul2_no_se_ofrece_como_la_anti_diana_kappa():
    fila = _fila_oprk1()
    assert fila["pdb_id"] == "7UL2"
    assert fila["estado"] == "estructura_incompatible"
    assert "NTSR1" in fila["motivo"] and "OPRK1" in fila["motivo"]
    # La caja histórica se conserva como registro, pero la fila no sale entre las seleccionables: sólo las `validada` se ofrecen.
    assert fila["center"] and fila["size"] and fila["chain"] == "R"
    assert "7UL2" not in anti_dianas_seleccionables_de_bowes()


def test_ninguna_fila_incompatible_o_sin_validar_se_ofrece_aunque_conserve_su_caja():
    seleccionables = anti_dianas_seleccionables_de_bowes()
    for fila in panel_bowes_2012():
        if fila.get("estado") != "validada":
            assert str(fila.get("pdb_id") or "").upper() not in seleccionables, fila.get("assay")


def test_las_corridas_historicas_con_7ul2_siguen_declarando_el_sitio_sin_adjudicar():
    assert sitio_adjudicado_de("7UL2") is False
    assert _fila_oprk1()["redock"]["ligando"] == "Q6Q"


def test_ninguna_validada_conserva_un_titulo_de_otra_proteina_del_panel():
    """Guardián de identidad por título: una fila `validada` no puede llamarse como OTRA diana del panel.

    Es una comprobación parcial (el título del depósito no siempre nombra la proteína) y no sustituye adjudicar la
    identidad; detecta el caso que ya pasó: título de NTSR1 bajo el gen OPRK1.
    """
    otros_nombres = {"NTSR1", "NEUROTENSIN"}
    for fila in panel_bowes_2012():
        if fila.get("estado") != "validada":
            continue
        titulo = str(fila.get("titulo") or "").upper()
        proteina = str(fila.get("nombre_proteina") or "").upper()
        for nombre in otros_nombres:
            if nombre in titulo and nombre not in proteina:
                pytest.fail(f"{fila['assay']} ({fila.get('pdb_id')}): el título del depósito nombra {nombre} "
                            f"y la proteína del ensayo es {proteina!r}")


def test_control_negativo_sin_la_marca_la_fila_vuelve_a_ser_validada(monkeypatch):
    """El generador es el que decide: sin la marca, 7UL2 vuelve a salir `validada` (y el guardián de arriba la vería)."""
    ruta = RAIZ / "scripts" / "build_bowes44_panel.py"
    spec = importlib.util.spec_from_file_location("build_bowes44_panel_inc", ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("build_bowes44_panel_inc", modulo)
    spec.loader.exec_module(modulo)
    if not modulo.VALIDACION.is_file():
        pytest.skip("la validación del panel no está en esta copia")

    con = next(d for d in modulo.construir()["dianas"] if d.get("gen") == "OPRK1")
    assert con["estado"] == "estructura_incompatible"

    monkeypatch.setattr(modulo, "ESTRUCTURA_INCOMPATIBLE", {})
    sin = next(d for d in modulo.construir()["dianas"] if d.get("gen") == "OPRK1")
    assert sin["estado"] == "validada" and "NTSR1" in sin["titulo"].upper()
