"""«Archivo del receptor» en Preparación: cada decisión que se tomó al leer el archivo está dicha, en los dos idiomas."""

from __future__ import annotations

import copy

from services.dossier.localization import traducir_dossier
from services.dossier.preparacion_entrada import SEPARADOR, partes_de_entrada
from tests.fixtures_dossier import caso_completo
from tests.test_dossier_en_ingles_completo import _parece_espanol
from tests.test_preparacion_auditoria import _PROCEDENCIA, _auditar


def _requisito(auditoria: dict, clave: str) -> dict:
    return next(r for b in auditoria["bloques"] for r in b["requisitos"] if r["clave"] == clave)


def _entrada_mmcif(**cambios) -> dict:
    conversion = {
        "origen_formato": "mmcif", "modelos": {"en_el_archivo": 3, "usado": 1},
        "cadenas": [{"original": "AAA", "pdb": "B", "renombrada": True}, {"original": "A", "pdb": "A", "renombrada": False}],
        "residuos_renombrados": [{"original": "A1D5J", "pdb": "Z00", "cadena": "A", "cadena_pdb": "A",
                                  "numero": 401, "insercion": None, "atomos": 40}],
        "ensamblaje": {"estado": "unidad_asimetrica", "usado": None,
                       "motivo": "el ensamblaje 1 no cubre todos los polímeros del archivo (B quedan fuera) y "
                                 "aplicar sus operadores a todas las cadenas inventaría copias"},
        "serie_renumerada": True, "avisos": [],
    }
    return {"formato": "mmcif", "sha256": "ab" * 32, "conversion": conversion,
            "normalizacion": {"modelos": {"en_el_archivo": 2, "usado": 1}, "elementos_inferidos": 12}, **cambios}


def _prep(**extra) -> dict:
    return {"source": "meeko_report", "recipe_hash": "5" * 64, "chain": "B", "site_chains": ["B"],
            "removed_residues": [], "cofactors_outside_site": [],
            "protonation_method": "Meeko 0.7.1; asignación por plantilla, sin pH experimental declarado",
            "modo_de_preparacion": "automatico", "entrada": _entrada_mmcif(), **extra}


def _auditar_con(prep: dict) -> dict:
    caso = caso_completo()
    procedencia = copy.deepcopy(_PROCEDENCIA)
    procedencia["receptor_prep"] = prep
    caso["eval_result"].docking_protocol = {**caso["eval_result"].docking_protocol, "execution_provenance": procedencia}
    return _auditar(caso)


def test_cada_decision_de_la_conversion_tiene_su_frase_con_los_nombres_originales():
    partes = partes_de_entrada(_prep())

    assert partes[0] == "mmcif" and partes[1].startswith("modo: estructura cruda")
    assert "cadenas renombradas: AAA → B" in partes
    assert "códigos largos sustituidos: A1D5J → Z00 (A:401)" in partes
    assert "modelo 1 de 3" in partes and "modelo 1 de 2" in partes
    assert "elemento inferido del nombre en 12 átomos" in partes
    assert "números de serie de átomo repetidos (más de 99 999 átomos)" in partes
    assert any(p.startswith("unidad asimétrica: el ensamblaje 1 no cubre") for p in partes)


def test_el_catalogo_no_tiene_entrada_ni_frases():
    assert partes_de_entrada({"recipe_hash": "5" * 64, "chain": "A"}) == []


def test_en_ingles_no_queda_ninguna_frase_en_espanol_y_los_datos_se_copian():
    auditoria = _auditar_con(_prep())

    original = _requisito(auditoria, "receptor.entrada")["valor"]
    en = _requisito(traducir_dossier(auditoria, "en"), "receptor.entrada")["valor"]

    assert original.count(SEPARADOR) == en.count(SEPARADOR)
    assert not _parece_espanol(en), en
    for dato in ("AAA → B", "A1D5J → Z00 (A:401)", "ab" * 32, "mmcif"):
        assert dato in en
    assert "asymmetric unit: assembly 1 does not cover all the polymers in the file (B are left out)" in en
    assert "element inferred from the name in 12 atoms" in en and "model 1 of 3" in en


def test_con_origen_se_dicen_su_hash_su_conversion_y_la_correspondencia():
    prep = _prep(
        modo_de_preparacion="pdbqt_con_origen",
        entrada={"formato": "pdbqt", "sha256": "cd" * 32},
        origen={"formato": "mmcif", "sha256": "ef" * 32, "conversion": _entrada_mmcif()["conversion"]},
        correspondencia_con_el_origen={"residuos_del_pdbqt": 548, "residuos_que_coinciden": 548,
                                       "desplazamiento_mediano_A": 0.0},
    )

    auditoria = _auditar_con(prep)
    es = _requisito(auditoria, "receptor.entrada")["valor"]
    en = _requisito(traducir_dossier(auditoria, "en"), "receptor.entrada")["valor"]

    assert "origen: mmcif SHA-256 " + "ef" * 32 in es
    assert "el PDBQT corresponde al origen (548 de 548 residuos; desplazamiento mediano 0.0 Å)" in es
    assert "source: mmcif SHA-256 " + "ef" * 32 in en
    assert "the PDBQT matches the source (548 of 548 residues; median displacement 0.0 Å)" in en
    assert not _parece_espanol(en), en


def test_un_codigo_sustituto_se_ve_con_su_original_en_las_especies_del_sitio():
    diff = {
        "state": "evaluado", "reason": "x",
        "near_site": {"margin_A": 6.0, "protein_residues_removed": {}, "preserved": [], "removed": [
            {"chain": "A", "residue_number": "401", "insertion_code": "", "name": "Z00",
             "category": "other_heteroatom", "distance_to_box_A": 2.5},
            {"chain": "A", "residue_number": "900", "insertion_code": "", "name": "HOH",
             "category": "water", "distance_to_box_A": 3.1}]},
        "removed": {}, "preserved": {},
    }
    auditoria = _auditar_con(_prep(species_diff=diff))

    otras = _requisito(auditoria, "entorno.otras_especies")["valor"]
    aguas = _requisito(auditoria, "entorno.aguas")["valor"]

    assert "Z00 [A1D5J] A:401 (2.5 Å)" in otras
    assert "HOH A:900" in aguas and "[" not in aguas             # lo que no se renombró no se toca
