"""
La caja del catálogo no se atribuye a la investigadora (QA1-007).

Medido en la cápsula de QA con un caso nuevo y sin tocar «Opciones»: el preflight
decía «Centro (5.43, 1.67, -21.01) · origen: elegido por ti; tamaño (30, 30, 30) Å ·
origen: elegido por ti», y esa caja es la calibrada del catálogo para 4AZY.

La causa: la interfaz guarda en el caso la caja del catálogo al elegir el receptor
(para no reutilizar las coordenadas de otra proteína) y la envía en cada
comprobación. El preflight tomaba cualquier valor recibido por «override del
usuario». Si el valor es el del catálogo, el origen es el catálogo.
"""

from __future__ import annotations

import pytest

from tests.conftest import rdkit_available

from services.docking.preflight import build_preflight

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
CENTRO_CATALOGO = (5.427, 1.673, -21.014)
TAMANO_CATALOGO = (30.0, 30.0, 30.0)


def _build(**overrides):
    kwargs = dict(
        smiles=ASPIRIN,
        target_pdb_id="4AZY",
        chain="A",
        target_origin="curado",
        target_reference="ref-4azy",
        grid_center=None,
        grid_size=None,
        custom_hotspots=None,
        catalog_grid_center=CENTRO_CATALOGO,
        catalog_grid_size=TAMANO_CATALOGO,
        catalog_hotspots=["A:ASP32", "A:ASP228"],
        cofactors_whitelist=None,
        docking_engine="vina",
    )
    kwargs.update(overrides)
    return build_preflight(**kwargs)


def _control(report: dict, code: str) -> dict:
    for control in report["controls"]:
        if control["code"] == code:
            return control
    raise AssertionError(f"El informe no incluye el control {code}")


@rdkit_available
def test_la_caja_enviada_igual_a_la_del_catalogo_declara_el_catalogo():
    report = _build(grid_center=CENTRO_CATALOGO, grid_size=TAMANO_CATALOGO)
    config = report["effective_config"]

    assert config["grid_center_origin"] == "catalogo_target"
    assert config["grid_size_origin"] == "catalogo_target"
    observacion = _control(report, "GRID_EFECTIVO")["observation"]
    assert "elegido por ti" not in observacion
    assert observacion.count("catálogo del receptor") == 2


@rdkit_available
def test_el_ruido_de_coma_flotante_no_convierte_el_catalogo_en_decision():
    # El frontend serializa a 3 decimales y el catálogo guarda más: 5.4270000001 ≠ 5.427
    # en bruto, pero es la misma caja.
    report = _build(grid_center=(5.4270000001, 1.6730000002, -21.0139999999), grid_size=(30.0000001, 30.0, 30.0))
    assert report["effective_config"]["grid_center_origin"] == "catalogo_target"
    assert report["effective_config"]["grid_size_origin"] == "catalogo_target"


@rdkit_available
def test_una_caja_distinta_sigue_siendo_del_usuario():
    """El control positivo: lo que de verdad cambia la investigadora, es suyo."""
    report = _build(grid_center=(6.5, 1.673, -21.014), grid_size=TAMANO_CATALOGO)
    config = report["effective_config"]

    assert config["grid_center_origin"] == "override_usuario"
    # El tamaño no lo tocó: sigue siendo el del catálogo.
    assert config["grid_size_origin"] == "catalogo_target"
    observacion = _control(report, "GRID_EFECTIVO")["observation"]
    assert observacion.count("elegido por ti") == 1


@rdkit_available
def test_sin_catalogo_cualquier_caja_enviada_es_del_usuario():
    """Sin caja de catálogo con la que comparar no hay otro dueño posible."""
    report = _build(
        grid_center=(1.0, 2.0, 3.0),
        grid_size=(20.0, 20.0, 20.0),
        catalog_grid_center=None,
        catalog_grid_size=None,
    )
    assert report["effective_config"]["grid_center_origin"] == "override_usuario"
    assert report["effective_config"]["grid_size_origin"] == "override_usuario"


@rdkit_available
def test_la_huella_no_depende_de_quien_se_atribuya_la_caja():
    """Cambiar la etiqueta de origen no puede mover el fingerprint: describe la misma corrida."""
    con_caja_explicita = _build(grid_center=CENTRO_CATALOGO, grid_size=TAMANO_CATALOGO)
    sin_caja = _build()
    assert con_caja_explicita["input_fingerprint"] == sin_caja["input_fingerprint"]
