"""La comprobación previa decide los cofactores con la misma regla que prepare_target.

Regresión de la auditoría de los 381 receptores (2026-10-08, rama `codex/receptores-curacion-20261008`,
`7b16531e`), medida otra vez en desarrollo el 2026-10-10: bastaba un HETATM orgánico conservado para
bloquear con COFACTOR_TEMPLATE_NO_DISPONIBLE, aunque el hemo, el FMN, el ADP y los fosforresiduos tienen
plantilla local y la MET sale de convertir una MSE. Eran 18 receptores del catálogo, en los 18 era el único
bloqueante y la corrida se rechazaba con un 409 mientras prepare_target (Meeko real) los preparaba.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.i18n_plantillas import traducir
from services.docking import preflight as pf

RAIZ = Path(__file__).resolve().parents[2]

PROTEINA = """\
ATOM      1  N   ALA A   1       1.000   0.000   0.000  1.00 20.00           N
ATOM      2  CA  ALA A   1       2.000   0.000   0.000  1.00 20.00           C
ATOM      3  C   ALA A   1       3.000   0.000   0.000  1.00 20.00           C
ATOM      4  O   ALA A   1       4.000   0.000   0.000  1.00 20.00           O
"""

#: Los 18 que bloqueaba la regla anterior (barrido del catálogo con el preflight de desarrollo, 2026-10-10).
BLOQUEADOS_SIN_MOTIVO = (
    "1HWK", "1NHY", "2NNJ", "2OA8", "2VE3", "3RW0", "4BCF", "4E4N", "4EJJ",
    "4NY4", "4O1Z", "5O65", "5TGZ", "6GUE", "6N7B", "6ZD1", "6ZDP", "7TM9",
)


def _informe(monkeypatch, tmp_path, nombre="NTP", x=1.0, cadena="A", **overrides):
    fuente = tmp_path / "1ABC.pdb"
    fuente.write_text(PROTEINA + (
        f"HETATM    5  C1  {nombre:>3} {cadena} 500    "
        f"{x:8.3f}{0.:8.3f}{0.:8.3f}  1.00 20.00           C\nEND\n"
    ), encoding="utf-8")
    monkeypatch.setattr(pf, "_source_pdb_path", lambda _: fuente)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda *args: None)
    opciones = dict(
        smiles="c1ccc(O)cc1", target_pdb_id="1ABC", chain="A",
        target_origin="curado", target_reference="1ABC",
        grid_center=(1., 0., 0.), grid_size=(10., 10., 10.),
        custom_hotspots=None, catalog_grid_center=None, catalog_grid_size=None,
        catalog_hotspots=None, cofactors_whitelist=[nombre], docking_engine="vina",
    )
    opciones.update(overrides)
    return pf.build_preflight(**opciones)


def _control(informe, codigo):
    return next(c for c in informe["controls"] if c["code"] == codigo)


@pytest.mark.parametrize("nombre", ["HEM", "FMN", "ADP", "SEP", "TPO", "PTR", "MET", "MSE"])
def test_plantilla_local_o_conversion_no_se_declara_inexistente(monkeypatch, tmp_path, nombre):
    informe = _informe(monkeypatch, tmp_path, nombre=nombre)
    assert "COFACTOR_TEMPLATE_NO_DISPONIBLE" not in informe["technical_blockers"]
    check = informe["receptor"]["cofactor_template_check"]
    assert check["state"] == "evaluado"
    assert check["missing_near_site"] == []
    # No se ha parametrizado este PDB sintético ni demostrado su química.
    assert informe["receptor"]["prepared_available"] is False


def test_plantilla_ausente_cerca_se_bloquea_con_instancia_y_distancia(monkeypatch, tmp_path):
    """Control negativo: sin plantilla de verdad, junto al sitio, sigue bloqueando."""
    informe = _informe(monkeypatch, tmp_path)
    assert "COFACTOR_TEMPLATE_NO_DISPONIBLE" in informe["technical_blockers"]
    fila, = informe["receptor"]["cofactor_template_check"]["missing_near_site"]
    assert (fila["name"], fila["chain"], fila["residue_number"], fila["distance_to_box_A"]) == (
        "NTP", "A", "500", 0.0,
    )
    assert _control(informe, "COFACTOR_TEMPLATE_NO_DISPONIBLE")["observation"] == (
        "Sin plantilla Meeko local a 6 Å o menos de la caja: NTP A:500 (0.0 Å)."
    )


def test_plantilla_ausente_lejos_se_declara_y_se_retira_del_diff(monkeypatch, tmp_path):
    informe = _informe(monkeypatch, tmp_path, x=40.)
    assert "COFACTOR_TEMPLATE_NO_DISPONIBLE" not in informe["technical_blockers"]
    assert "COFACTORES_SIN_PLANTILLA_FUERA_DEL_SITIO" in informe["warnings"]
    assert informe["preparation_diff"]["route_input"]["hetatm_records"] == 0
    assert informe["preparation_diff"]["removed_species"] == [
        {"residue_code": "NTP", "atom_count": 1, "category": "other_heteroatom"},
    ]


@pytest.mark.parametrize("x,bloquea", [(12.0, True), (12.01, False)])
def test_mismo_borde_de_seis_angstrom_que_la_preparacion(monkeypatch, tmp_path, x, bloquea):
    informe = _informe(monkeypatch, tmp_path, x=x)
    assert ("COFACTOR_TEMPLATE_NO_DISPONIBLE" in informe["technical_blockers"]) is bloquea


def test_override_de_caja_gobierna_la_comprobacion(monkeypatch, tmp_path):
    informe = _informe(monkeypatch, tmp_path, x=40., grid_center=(40., 0., 0.),
                       catalog_grid_center=(1., 0., 0.))
    assert "COFACTOR_TEMPLATE_NO_DISPONIBLE" in informe["technical_blockers"]
    assert informe["receptor"]["cofactor_template_check"]["box_center"] == [40., 0., 0.]


def test_caja_dinamica_se_resuelve_antes_de_clasificar_cofactores(monkeypatch, tmp_path):
    monkeypatch.setattr(pf, "_derive_dynamic_box", lambda _: {
        "center": (40., 0., 0.), "size": 10., "source": "HETATM_TEST",
    })
    informe = _informe(monkeypatch, tmp_path, x=40., grid_center=(0., 0., 0.))
    assert "COFACTOR_TEMPLATE_NO_DISPONIBLE" in informe["technical_blockers"]
    assert informe["receptor"]["cofactor_template_check"]["box_center"] == [40., 0., 0.]


@pytest.mark.parametrize("opciones", [{"cadena": "B"}, {"site_ligand": "NTP"}])
def test_cadena_excluida_y_ligando_referencia_no_son_cofactor_del_receptor(monkeypatch, tmp_path, opciones):
    informe = _informe(monkeypatch, tmp_path, **opciones)
    assert "COFACTOR_TEMPLATE_NO_DISPONIBLE" not in informe["technical_blockers"]


def test_sin_fuente_no_se_inventa_comprobacion(monkeypatch):
    monkeypatch.setattr(pf, "_source_pdb_path", lambda _: None)
    monkeypatch.setattr(pf, "_prepared_pdbqt_path", lambda *args: None)
    informe = pf.build_preflight(
        smiles="CCO", target_pdb_id="1ABC", chain="A", target_origin="curado",
        target_reference="1ABC", grid_center=(1., 0., 0.), grid_size=(10., 10., 10.),
        custom_hotspots=None, catalog_grid_center=None, catalog_grid_size=None,
        catalog_hotspots=None, cofactors_whitelist=[], docking_engine="vina",
    )
    assert informe["receptor"]["cofactor_template_check"]["state"] == "no_evaluado"
    assert "RECEPTOR_FUENTE_DISPONIBLE" in informe["technical_blockers"]


def test_los_dos_controles_salen_enteros_en_ingles(monkeypatch, tmp_path):
    for x, codigo in ((1.0, "COFACTOR_TEMPLATE_NO_DISPONIBLE"), (40.0, "COFACTORES_SIN_PLANTILLA_FUERA_DEL_SITIO")):
        control = _control(_informe(monkeypatch, tmp_path, x=x), codigo)
        for campo in ("title", "observation", "reason", "provenance"):
            assert traducir(control[campo], "en") != control[campo], (codigo, campo, control[campo])
    assert traducir("Sin plantilla Meeko local a 6 Å o menos de la caja: NTP A:500 (0.0 Å), HEM B:12A (3.5 Å).",
                    "en") == "No local Meeko template within 6 Å of the box: NTP A:500 (0.0 Å), HEM B:12A (3.5 Å)."


@pytest.mark.parametrize("pdb_id", BLOQUEADOS_SIN_MOTIVO)
def test_los_receptores_del_catalogo_que_bloqueaba_ya_no_bloquean(pdb_id):
    """Con su estructura depositada y la caja del catálogo, como los pide la pestaña Evaluación."""
    entrada = next(e for e in json.loads((RAIZ / "curated_targets.json").read_text(encoding="utf-8"))
                   if e["pdb_id"] == pdb_id)
    informe = pf.build_preflight(
        smiles="Oc1ccccc1", target_pdb_id=pdb_id, chain=entrada.get("chain") or "A",
        target_origin="curado", target_reference=None, grid_center=None, grid_size=None,
        custom_hotspots=None,
        catalog_grid_center=tuple(entrada[f"grid_center_{eje}"] for eje in "xyz"),
        catalog_grid_size=tuple(entrada[f"grid_size_{eje}"] for eje in "xyz"),
        catalog_hotspots=[h["name"] for h in entrada.get("hotspots") or []],
        cofactors_whitelist=entrada.get("cofactors_whitelist") or [],
        site_chains=list(entrada.get("site_chains") or []), site_ligand=entrada.get("site_ligand"),
    )
    assert "COFACTOR_TEMPLATE_NO_DISPONIBLE" not in informe["technical_blockers"]
    check = informe["receptor"]["cofactor_template_check"]
    assert check["state"] == "evaluado"
    assert check["missing_near_site"] == []
