"""Caza 1 (2026-11-12), grupo A: el documento dice lo que es y no se contradice.

Salió de leer 58 PDF de 15 corridas de la cápsula (`.tmp/pdf-capsula-2026-11-12/CAZA-1.md`, hallazgos A01–A12). Cada prueba GENERA el PDF
(o ejerce la función que escribe la frase) y falló antes del arreglo.

* A01 — el informe decía «cofactores: ninguno conservado» de un receptor que conservaba el hemo.
* A02/A03 — el supuesto de aguas decía «se eliminaron todas» junto a «no tenía ninguna»; la frase medida llevaba ejemplos fijos.
* A04 — el nombre del receptor salía cortado en la primera línea del TITLE, sin puntos suspensivos.
* A05 — las tablas enseñaban 5 poses y 7 residuos sin decir de cuántos.
* A06 — «Preparación del sistema: DOCUMENTADA» junto a una Preparación BLOQUEADA.
* A07 — «Nombre común (PubChem): N/A» sin decir que no se consultó.
* A08 — JSON crudo en celdas, `vocabulario_especies` y un id interno rotulado «PDB ID».
* A09 — un ejemplo de la literatura (cetirizina) dentro del dossier de otra molécula.
* A10 — el ligando cocristalizado, sobre la pose, descrito como «aditivo de cristalización».
* A11 — «la cohorte de este proyecto (17 431 moléculas)» sin decir cuál.
* A12 — la misma comprobación salía «PASA» en la sección 10 y «REGISTRADO» en la 11.
"""
from __future__ import annotations

import importlib.util
import re

import pytest

from tests.test_pdf_informe_figuras_y_cuadros import _informe, _texto

requiere_pypdf = pytest.mark.skipif(importlib.util.find_spec("pypdf") is None, reason="pypdf no está en este intérprete")


def _plano(texto: str) -> str:
    return re.sub(r"\s+", " ", texto)


def _en_ingles(funcion):
    from core.i18n import reset_request_locale, set_request_locale

    token = set_request_locale("en")
    try:
        return funcion()
    finally:
        reset_request_locale(token)


def _protocolo(receptor_prep: dict) -> dict:
    return {"engine": "vina", "exhaustiveness": 8, "num_poses": 9, "seed": 42,
            "execution_provenance": {"receptor_prep": receptor_prep}}


HEMO = {"category": "organic_cofactor", "chain": "A", "name": "HEM", "residue_number": "601", "insertion_code": "",
        "distance_to_box_A": 0.0}


# ── A01: «cofactores» dice lo que conservó el receptor, no sólo la lista declarada ─────────────────────────────


@requiere_pypdf
def test_el_informe_nombra_el_hemo_que_el_receptor_conserva():
    prep = {"cofactors_whitelist": [], "species_diff": {"state": "evaluado", "near_site": {"margin_A": 6.0, "preserved": [HEMO]},
                                                          "preserved": {"metals": 0, "organic_cofactors": 43, "waters": 0}}}
    texto = _plano(_texto(_informe(extra={"docking_protocol": _protocolo(prep)})))
    assert "ninguno conservado" not in texto
    assert "lista declarada" in texto and "HEM A:601" in texto
    assert "el receptor de la corrida conserva" in texto


@requiere_pypdf
def test_sin_diff_de_especies_el_informe_no_afirma_lo_que_no_sabe():
    texto = _plano(_texto(_informe(extra={"docking_protocol": _protocolo({"cofactors_whitelist": []})})))
    assert "ninguno conservado" not in texto
    assert "lista declarada" in texto and "el receptor de la corrida conserva" not in texto


@requiere_pypdf
def test_el_hemo_conservado_sale_traducido_en_el_informe_ingles():
    prep = {"cofactors_whitelist": [], "species_diff": {"state": "evaluado", "near_site": {"preserved": [HEMO]}}}
    texto = _plano(_en_ingles(lambda: _texto(_informe(extra={"docking_protocol": _protocolo(prep)}))))
    assert "HEM A:601" in texto and "declared list" in texto
    assert not re.search(r"lista de cofactores|el receptor de la corrida|cofactor orgánico", texto)


# ── A02 / A03: las aguas, medidas y sin ejemplos ajenos ─────────────────────────────────────────────────────


def test_la_frase_medida_de_las_aguas_retiradas_no_trae_ejemplos_de_otras_dianas():
    from services.chemistry.censo_de_aguas import censar_aguas, describir_censo
    from tests.test_evaluacion_caminos_propios import CAJA, CRUDO_UNA

    frase = describir_censo(censar_aguas(CRUDO_UNA, *CAJA))
    assert "se retiraron 1 aguas" in frase
    assert "proteasa del VIH-1" not in frase and "bisagra" not in frase


@requiere_pypdf
def test_el_aviso_antiguo_con_ejemplos_sigue_traduciendose():
    """Lo guardado por una corrida anterior no se reescribe: su plantilla inglesa se conserva."""
    antiguo = ("Preparación en condición desolvatada: se retiraron 2 aguas cristalográficas de la caja de acoplamiento, 1 de ellas "
               "con 3 o más contactos a menos de 3.5 Å con el receptor (la mejor coordinada, 3). Si alguna de esas aguas forma parte "
               "del reconocimiento en esta diana —la catalítica de la proteasa del VIH-1, la red de la bisagra en varias quinasas—, "
               "los contactos de esta corrida no la incluyen.")
    texto = _plano(_en_ingles(lambda: _texto(_informe(avisos=[antiguo]))))
    assert "Desolvated preparation" in texto and not re.search(r"Preparación en condición|retiraron", texto)


@requiere_pypdf
def test_el_supuesto_de_aguas_de_la_receta_se_dice_como_regla_y_no_como_hecho():
    texto = _plano(_texto(_informe()))
    assert "se eliminaron todas las aguas" not in texto
    assert "La preparación estándar retira todas las aguas cristalográficas del receptor" in texto


@requiere_pypdf
def test_el_supuesto_de_aguas_de_la_receta_sale_traducido():
    texto = _plano(_en_ingles(lambda: _texto(_informe())))
    assert "The standard preparation removes all crystallographic waters from the receptor" in texto
    assert "La preparación estándar" not in texto


@pytest.mark.asyncio
async def test_un_receptor_propio_sin_aguas_no_dice_que_se_preparo_desolvatado(tmp_path, monkeypatch):
    from tests.test_evaluacion_caminos_propios import PROTEINA, _avisos_de_aguas, _depositado

    crudo = _depositado(1, "N", "ALA", 1, (6.0, 0.0, 0.0), "N", "ATOM  ") + "\n"
    avisos = await _avisos_de_aguas(tmp_path, monkeypatch, receptor=PROTEINA, crudo=crudo, modo="respetar")
    assert [a["codigo"] for a in avisos] == ["SITIO_DESOLVATADO"]
    mensaje = avisos[0]["mensaje"]
    assert "al prepararlo" not in mensaje and "estructura depositada" not in mensaje
    assert "El receptor acoplado no trae aguas cristalográficas dentro de la caja de acoplamiento" in mensaje
    assert "su estructura de origen tampoco las tenía" in mensaje


@pytest.mark.asyncio
async def test_un_receptor_propio_al_que_se_le_quitaron_las_aguas_dice_cuantas_traia_el_origen(tmp_path, monkeypatch):
    from tests.test_evaluacion_caminos_propios import CRUDO_UNA, PROTEINA, _avisos_de_aguas

    avisos = await _avisos_de_aguas(tmp_path, monkeypatch, receptor=PROTEINA, crudo=CRUDO_UNA, modo="respetar")
    mensaje = avisos[0]["mensaje"]
    assert "su estructura de origen tiene 1 agua(s) en la caja que no están en el receptor" in mensaje
    assert "al prepararlo" not in mensaje and "retiraron" not in mensaje


# ── A04: el nombre del receptor completo (el TITLE sigue en las líneas de continuación) ───────────────────


PDB_CON_TITLE_LARGO = (
    "HEADER    LYASE                                   01-SEP-05   2AW1              \n"
    "TITLE     CARBONIC ANHYDRASE INHIBITORS: VALDECOXIB BINDS TO A DIFFERENT ACTIVE \n"
    "TITLE    2 SITE ASSOCIATED WITH CARBONIC ANHYDRASE II                           \n"
    "COMPND    MOL_ID: 1;                                                            \n"
)


def test_el_nombre_que_se_guarda_al_ingerir_une_las_lineas_del_title():
    from services.targets.titulo_del_deposito import titulo_del_deposito

    assert titulo_del_deposito(PDB_CON_TITLE_LARGO) == (
        "CARBONIC ANHYDRASE INHIBITORS: VALDECOXIB BINDS TO A DIFFERENT ACTIVE SITE ASSOCIATED WITH CARBONIC ANHYDRASE II")
    assert titulo_del_deposito("HEADER    LYASE                                   01-SEP-05   2AW1\n") is None


@requiere_pypdf
def test_el_informe_completa_un_nombre_de_receptor_cortado_con_el_title_del_deposito():
    texto = _plano(_texto(_informe(
        pdb_id="2AW1", nombre_receptor="CARBONIC ANHYDRASE INHIBITORS: VALDECOXIB BINDS TO A DIFFERENT ACTIVE",
        receptor_pdb=PDB_CON_TITLE_LARGO)))
    assert "SITE ASSOCIATED WITH CARBONIC ANHYDRASE II" in texto


TITULO_2AW1 = ("CARBONIC ANHYDRASE INHIBITORS: VALDECOXIB BINDS TO A DIFFERENT ACTIVE SITE REGION OF THE HUMAN ISOFORM II AS COMPARED TO "
               'THE STRUCTURALLY RELATED CYCLOOXYGENASE II "SELECTIVE" INHIBITOR CELECOXIB')
NOMBRE_2AW1_CORTADO = "CARBONIC ANHYDRASE INHIBITORS: VALDECOXIB BINDS TO A DIFFERENT ACTIVE"


def test_el_titulo_de_un_receptor_del_catalogo_sale_de_su_archivo_del_instalador():
    """La copia de `data/targets` que lee el informe no lleva cabecera: el título está en el `.pdb.gz` que viaja."""
    from services.targets.titulo_del_deposito import titulo_del_catalogo

    assert titulo_del_catalogo("2AW1") == TITULO_2AW1
    assert titulo_del_catalogo("USR_5D94FF") is None
    assert titulo_del_catalogo("../../etc") is None


@requiere_pypdf
def test_el_informe_completa_el_nombre_aunque_la_copia_del_receptor_no_lleve_cabecera():
    """El caso real: `receptor_pdb_content` es la copia sin HEADER ni TITLE que escribe la preparación."""
    sin_cabecera = "".join(linea for linea in PDB_CON_TITLE_LARGO.splitlines(keepends=True) if not linea.startswith(("HEADER", "TITLE")))
    texto = _plano(_texto(_informe(pdb_id="2AW1", nombre_receptor=NOMBRE_2AW1_CORTADO, receptor_pdb=sin_cabecera)))
    assert "REGION OF THE HUMAN ISOFORM II" in texto and "INHIBITOR CELECOXIB" in texto


def test_el_dossier_completa_el_nombre_del_receptor_del_catalogo_y_no_toca_el_del_usuario():
    from services.dossier.model import build_case_dossier
    from tests.fixtures_dossier import caso_completo

    caso = caso_completo()
    caso["target"].pdb_id, caso["target"].name = "2AW1", NOMBRE_2AW1_CORTADO
    campos = {c.etiqueta: c.valor for c in build_case_dossier(**caso).portada}
    assert campos["Receptor"] == f"2AW1 · {TITULO_2AW1}"

    caso = caso_completo()
    caso["target"].pdb_id, caso["target"].name = "USR_5D94FF", NOMBRE_2AW1_CORTADO
    campos = {c.etiqueta: c.valor for c in build_case_dossier(**caso).portada}
    assert campos["Receptor"] == f"USR_5D94FF · {NOMBRE_2AW1_CORTADO}"


@requiere_pypdf
def test_un_nombre_propio_del_usuario_no_se_sustituye_por_el_title():
    texto = _plano(_texto(_informe(pdb_id="USR_5D94FF", nombre_receptor="Mi receptor", receptor_pdb=PDB_CON_TITLE_LARGO)))
    assert "Nombre: Mi receptor" in texto and "SITE ASSOCIATED WITH CARBONIC" not in texto.split("Contexto")[0]


# ── A05: las tablas dicen de cuántas filas enseñan una parte ─────────────────────────────────────────────────


def _nueve_poses():
    return [{"rank": i + 1, "affinity": -9.0 + 0.1 * i, "rmsd_lb": 0.0, "rmsd_ub": 0.0} for i in range(9)]


@requiere_pypdf
def test_la_tabla_de_poses_dice_cuantas_enseña_de_cuantas():
    texto = _plano(_texto(_informe(extra={"docking_poses": _nueve_poses()})))
    assert "Se muestran las 5 mejores poses de 9." in texto


@requiere_pypdf
def test_la_tabla_de_poses_no_añade_nota_si_las_enseña_todas():
    texto = _plano(_texto(_informe()))
    assert "mejores poses de" not in texto


@requiere_pypdf
def test_la_tabla_de_poses_sale_traducida():
    texto = _plano(_en_ingles(lambda: _texto(_informe(extra={"docking_poses": _nueve_poses()}))))
    assert "Showing the 5 best poses of 9." in texto and "Se muestran" not in texto


def _receptor_con_nueve_residuos():
    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import AllChem

    ligando = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    AllChem.EmbedMolecule(ligando, randomSeed=3)
    AllChem.MMFFOptimizeMolecule(ligando)
    sdf = Chem.MolToMolBlock(ligando) + "$$$$\n"
    c = np.array(ligando.GetConformer().GetAtomPosition(0))
    direcciones = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1), (1, 1, 0), (-1, -1, 0), (0, 1, 1)]
    lineas = []
    for i, d in enumerate(direcciones):
        x, y, z = c + 3.6 * np.array(d) / np.linalg.norm(d)
        lineas.append(f"ATOM  {i + 1:5d}  CB  ALA A{i + 10:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C\n")
    return sdf, "".join(lineas)


@requiere_pypdf
def test_la_tabla_de_contactos_dice_cuantos_residuos_enseña_de_cuantos():
    sdf, receptor = _receptor_con_nueve_residuos()
    texto = _plano(_texto(_informe(smiles="CCO", pose_sdf=sdf, receptor_pdb=receptor)))
    assert "Se muestran los 7 residuos más cercanos al ligando de los 9 con contacto." in texto


@requiere_pypdf
def test_la_tabla_de_contactos_sale_traducida():
    sdf, receptor = _receptor_con_nueve_residuos()
    texto = _plano(_en_ingles(lambda: _texto(_informe(smiles="CCO", pose_sdf=sdf, receptor_pdb=receptor))))
    assert "Showing the 7 residues closest to the ligand of the 9 in contact." in texto
    assert "Se muestran" not in texto


# ── A06: el inventario no se presenta como el veredicto de Preparación ───────────────────────────────────────


@requiere_pypdf
def test_el_informe_acota_lo_que_dice_su_estado_de_preparacion_del_sistema():
    listo = {"is_prepared": True, "grid_size_x": 20.0, "grid_size_y": 20.0, "grid_size_z": 20.0,
             "hotspots": [{"name": f"A:RES{i}", "importance": 0.5} for i in range(6)]}
    texto = _plano(_texto(_informe(target_extra=listo)))
    assert "No incluye la auditoría de Preparación (metales, huecos y aguas)." in texto


def test_el_dossier_acota_lo_que_dice_su_estado_de_preparacion_del_sistema():
    from services.dossier.model import build_case_dossier
    from tests.fixtures_dossier import caso_completo

    dossier = build_case_dossier(**caso_completo())
    sistema = next(d for d in dossier.dimensiones if d.codigo == "SYSTEM")
    assert "No incluye la auditoría de Preparación" in sistema.observacion


# ── A07: PubChem no se consulta, y el informe lo dice ──────────────────────────────────────────────────────


@requiere_pypdf
def test_los_nombres_de_pubchem_dicen_que_no_se_consultaron():
    texto = _plano(_texto(_informe()))
    assert "Nombre Común (PubChem): No consultado" in texto and "Nombre Sistemático (IUPAC): No consultado" in texto
    assert "Nombre Común (PubChem): N/A" not in texto


@requiere_pypdf
def test_los_nombres_de_pubchem_salen_traducidos():
    texto = _plano(_en_ingles(lambda: _texto(_informe())))
    assert "Not queried" in texto and "No consultado" not in texto


# ── A08: nada interno a la vista ─────────────────────────────────────────────────────────────────────────


@requiere_pypdf
def test_un_receptor_subido_no_se_rotula_con_un_pdb_id_que_no_lo_es():
    texto = _plano(_texto(_informe(pdb_id="USR_5D94FF", nombre_receptor="Mi receptor")))
    assert "PDB ID: USR_5D94FF" not in texto
    assert "ID del receptor: USR_5D94FF" in texto


@requiere_pypdf
def test_un_receptor_del_catalogo_conserva_su_pdb_id():
    assert "PDB ID: 1M17" in _plano(_texto(_informe()))


def _dossier_con_json_en_sus_campos(idioma: str = "es") -> str:
    import io

    from core.i18n import reset_request_locale, set_request_locale
    from services.dossier.model import build_case_dossier
    from services.dossier.pdf import render_dossier_pdf
    from tests.fixtures_dossier import caso_completo
    from tests.test_pdf_dossier_textos_de_sistema import _texto as texto_del_pdf

    caso = caso_completo()
    protocolo = dict(caso["eval_result"].docking_protocol)
    protocolo["execution_provenance"] = {**(protocolo.get("execution_provenance") or {}),
                                         "toolchain": {"meeko": "0.7.1", "rdkit": "2025.9.6", "vina": "1.2.7"}}
    caso["eval_result"].docking_protocol = protocolo
    caso["projection"].inputs.config.pipeline_config = {"docking_engine": "vina", "enabled_stages": ["docking", "xgb"],
                                                         "stage_params": {"docking": {"seed": 42}}}
    token = set_request_locale(idioma)
    try:
        return texto_del_pdf(render_dossier_pdf(build_case_dossier(**caso)).getvalue())
    finally:
        reset_request_locale(token)


@requiere_pypdf
def test_el_dossier_no_imprime_json_crudo_en_sus_celdas():
    texto = _plano(_dossier_con_json_en_sus_campos())
    assert re.search(r"meeko\W+0\.7\.1", texto) and "docking_engine" in texto      # el dato sigue ahí…
    assert not re.search(r'[{}]|\["|\]', texto), re.findall(r'.{40}[{}\[\]].{40}', texto)[:2]   # …sin llaves ni corchetes


def test_el_json_del_modelo_sigue_siendo_json():
    """Sólo el PDF lo presenta legible: el modelo canónico y el paquete conservan el dato tal cual."""
    import json

    from services.dossier.model import build_case_dossier
    from tests.fixtures_dossier import caso_completo

    caso = caso_completo()
    caso["projection"].inputs.config.pipeline_config = {"docking_engine": "vina"}
    campo = next(c for c in build_case_dossier(**caso).protocolo if c.etiqueta == "Configuración PRO declarada")
    assert json.loads(campo.valor) == {"docking_engine": "vina"}


@requiere_pypdf
def test_el_dossier_nombra_en_castellano_los_campos_de_procedencia_sin_sellar():
    from tests.test_pdf_dossier_textos_de_sistema import _dossier_pdf

    if importlib.util.find_spec("pypdf") is None:
        pytest.skip("pypdf no está en este intérprete")
    texto = _plano(_dossier_pdf("es"))
    assert "vocabulario_especies" not in texto
    assert "vocabulario de especies del sitio" in texto


def test_el_aviso_de_la_caja_no_nombra_un_id_interno():
    import inspect

    from services.docking.vina_service import _check_ligand_fits_box

    assert "Target: {target_pdb_id}" not in inspect.getsource(_check_ligand_fits_box)


# ── A09: un ejemplo de la literatura se dice ejemplo ─────────────────────────────────────────────────────


def test_los_motivos_de_especie_en_revision_dicen_que_sus_ejemplos_no_son_esta_molecula():
    from chem import especie_en_revision as er

    for motivo in (er._BASES_PROXIMAS, er._SULFONIL_PIPERAZINA, er._ACIDO_ENOLICO, er._AMINA_CON_ATRACTOR):
        assert re.search(r"ejemplos? de la literatura, no esta molécula", motivo.texto), motivo.codigo


# ── A10: la especie que ocupa el lugar de la pose no es un «aditivo de cristalización» ─────────────────────


def test_la_especie_sobre_la_pose_se_describe_por_su_geometria():
    from tests.test_dossier_dice_lo_mismo_que_la_auditoria import _ambos, _con_diff, _fila, _medido

    receptor_prep = _con_diff([_fila("STI", "other_heteroatom", numero="201"), _fila("GOL", "other_heteroatom", numero="266")])
    dossier, _ = _ambos(receptor_prep, _medido(STI_A_201=0.06, GOL_A_266=3.57))
    campo = next(c for c in dossier.preparacion if c.etiqueta == "Otras especies junto al sitio")
    assert "STI A:201 ocupa el mismo lugar que la pose" in campo.razon
    assert "puede ser el ligando que cocristalizó con la estructura" in campo.razon
    assert "Pueden ser aditivos de cristalización" in campo.razon      # lo sigue siendo GOL A:266: la preparación no lo distingue


def test_una_especie_lejos_de_la_pose_conserva_la_frase_de_siempre():
    from tests.test_dossier_dice_lo_mismo_que_la_auditoria import _ambos, _con_diff, _fila, _medido

    dossier, _ = _ambos(_con_diff([_fila("GOL", "other_heteroatom", numero="266")]), _medido(GOL_A_266=3.57))
    campo = next(c for c in dossier.preparacion if c.etiqueta == "Otras especies junto al sitio")
    assert "ocupa el mismo lugar" not in campo.razon and campo.razon.startswith("Pueden ser aditivos de cristalización")


# ── A11: la cohorte de la que sale la cifra tiene nombre ─────────────────────────────────────────────────


def test_la_cohorte_del_dossier_dice_cual_es():
    from services.dossier.model import _campos_de_eficiencia
    from tests.fixtures_dossier import caso_completo

    caso = caso_completo()
    caso["eval_result"].heavy_atom_count = 29
    campos = _campos_de_eficiencia(caso["eval_result"], {"top_pose_affinity": -7.19})
    escrito = _plano(" ".join(str(c) for c in campos))
    assert "la cohorte de acoplamiento de este proyecto (8 dianas, 17 431 moléculas con score de Vina" in escrito
    assert "cohorte de este proyecto (17 431" not in escrito


# ── A12: una comprobación, un estado ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("etapa", ["passed", "review", "failed", "not_evaluated"])
def test_la_validez_fisica_tiene_el_mismo_estado_en_los_controles_y_en_las_dimensiones(etapa):
    from services.dossier.model import build_case_dossier
    from tests.fixtures_dossier import caso_completo

    caso = caso_completo()
    caso["eval_result"].structural_evidence = {**caso["eval_result"].structural_evidence, "stage_status": etapa}
    dossier = build_case_dossier(**caso)
    control = next(c for c in dossier.controles if c.codigo == "VALIDEZ_FISICA_POSES")
    dimension = next(d for d in dossier.dimensiones if d.codigo == "PHYSICAL")
    assert dimension.estado == control.estado, (etapa, control.estado, dimension.estado)
