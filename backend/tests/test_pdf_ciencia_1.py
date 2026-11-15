"""Caza 1 (2026-11-12), arreglos de ciencia, tanda 1: lo que el PDF afirma tiene que ser lo que se calculó.

Salió de leer 58 PDF de 15 corridas de la cápsula (`.tmp/pdf-capsula-2026-11-12/CAZA-1.md`). Cada prueba GENERA el PDF (o ejerce
la función que escribe la frase) y falló antes del arreglo:

* B10 — la LLE sale de la afinidad de Vina convertida a pKi y el informe no lo decía.
* B11 — el dossier declaraba «1.37 kcal/mol por unidad logarítmica» y calculaba con 1.364.
* B12 — el «Índice de reglas heredado» es QED×100; el dossier ya lo llamaba «similitud a fármaco».
* B13 — «DENTRO DEL DOMINIO DECLARADO» aparecía también cuando la familia no tenía modelo y se usaba el universal.
* B14 — HBD y HBA siguen la definición de Lipinski original y el PDF no la declaraba.
* B07 — una azida (`N=[N+]=[N-]`) se contaba como doble enlace E/Z sin especificar, con severidad CRÍTICA.
* B08 — «el modo de unión no es único — la predicción es menos confiable» se inferían de un rango de afinidades.
* B09 — la especie acoplada era un dicatión y la carga neta no se decía.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from tests.test_pdf_informe_figuras_y_cuadros import _informe, _texto
from tests.test_pdf_dossier_textos_de_sistema import _dossier_pdf

RAIZ = Path(__file__).resolve().parents[2]

#: `pypdf` no viaja en python-embed: las pruebas que leen el texto del PDF sólo corren con el intérprete de desarrollo.
requiere_pypdf = pytest.mark.skipif(importlib.util.find_spec("pypdf") is None, reason="pypdf no está en este intérprete")


def _plano(texto: str) -> str:
    return re.sub(r"\s+", " ", texto)


# ── B10 / B14: lo que el informe declara de sus propias cifras ───────────────────────────────────


@requiere_pypdf
def test_el_informe_dice_de_donde_salen_LE_y_LLE():
    texto = _plano(_texto(_informe()))
    assert "LLE = |afinidad| / 1.364 − logP" in texto
    assert "parten de la afinidad de Vina" in texto and "no de una medida experimental" in texto


@requiere_pypdf
def test_el_informe_sin_logp_se_genera_y_conserva_la_nota_de_eficiencia():
    """Un `import` local de la constante en la rama de la LLE la volvía local a toda la función: sin logP no existía."""
    texto = _plano(_texto(_informe(extra={"log_p": None})))
    assert "LLE = |afinidad| / 1.364 − logP" in texto


@requiere_pypdf
def test_el_informe_declara_la_definicion_de_hbd_y_hba():
    texto = _plano(_texto(_informe()))
    assert "HBD: número de hidrógenos unidos a N u O" in texto
    assert "HBA: número de átomos de N y O" in texto


# ── B12: un solo nombre para el mismo índice en los dos documentos ────────────────────────────────


@requiere_pypdf
def test_el_indice_heredado_de_qed_se_llama_igual_en_los_dos_documentos():
    informe = _plano(_texto(_informe()))
    dossier = _plano(_dossier_pdf("es"))
    assert "Índice de reglas heredado" not in informe
    assert "Índice de similitud a fármaco heredado" in informe
    assert "Índice de similitud a fármaco heredado" in dossier


# ── B11: la constante que se declara es la que se usa ─────────────────────────────────────────────


def test_el_dossier_declara_la_constante_de_conversion_que_usa():
    from scoring.eficiencia import KCAL_POR_UNIDAD_LOG

    # La fixture no trae recuento de átomos pesados y sin él el dossier no escribe el campo de eficiencia.
    from services.dossier.model import _campos_de_eficiencia
    from tests.fixtures_dossier import caso_completo

    caso = caso_completo()
    caso["eval_result"].heavy_atom_count = 29
    campos = _campos_de_eficiencia(caso["eval_result"], {"top_pose_affinity": -7.19})
    escrito = _plano(" ".join(str(c) for c in campos))
    assert f"la conversión usa {KCAL_POR_UNIDAD_LOG} kcal/mol por unidad logarítmica" in escrito
    assert "usa 1.37 kcal/mol" not in escrito


# ── B13: el dominio es el del modelo que se usó ───────────────────────────────────────────────────

_FALLBACK = "Familia 'cytochrome_p450' sin modelo entrenado disponible — modelo universal usado."


@requiere_pypdf
def test_el_dominio_dice_de_que_modelo_habla_y_no_duplica_el_punto():
    texto = _plano(_texto(_informe(extra={"model_used": "universal", "fallback_reason": _FALLBACK,
                                          "in_applicability_domain": True})))
    assert "DENTRO DEL DOMINIO DECLARADO" not in texto
    assert "DENTRO DEL DOMINIO DEL MODELO USADO" in texto
    assert "universal usado.." not in texto and "universal usado." in texto


# ── B07: una azida no tiene isomería E/Z ──────────────────────────────────────────────────────────


def test_una_azida_no_cuenta_como_doble_enlace_sin_especificar():
    from rdkit import Chem

    from chem.validator import estereo_no_asignada

    azida = "CC(C)C[C@H](NC(=O)[C@H](Cc1ccccc1)N=[N+]=[N-])C(=O)NCC(=O)N[C@H](CCS(C)(=O)=O)Cc1ccc(CN)cc1"
    assert estereo_no_asignada(Chem.MolFromSmiles(azida)) == (0, 0)
    # el control: un doble enlace C=C que sí admite E/Z se sigue contando, y uno declarado no
    assert estereo_no_asignada(Chem.MolFromSmiles("CC=CC")) == (0, 1)
    assert estereo_no_asignada(Chem.MolFromSmiles("C/C=C/C")) == (0, 0)


# ── B08: el aviso de rango de poses no infiere lo que no mide ─────────────────────────────────────


def test_el_aviso_de_rango_de_poses_no_concluye_sobre_el_modo_de_union():
    fuente = (RAIZ / "rescoring" / "model_manager.py").read_text(encoding="utf-8")
    assert "El modo de unión no es único" not in fuente
    assert "la predicción es menos confiable" not in fuente
    assert "Rango de afinidad entre poses" in fuente


# ── B09: la especie acoplada dice su carga neta ───────────────────────────────────────────────────


def test_la_especie_acoplada_declara_su_carga_neta():
    from services.docking.ligand_state_warnings import avisos_estado_ligando

    estado = {
        "cambio_respecto_a_la_entrada": True,
        "smiles_entrada": "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1",
        "smiles_acoplado": "Cc1ccc(NC(=O)c2ccc(C[NH+]3CC[NH+](C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1",
    }
    mensajes = [a["mensaje"] for a in avisos_estado_ligando(estado)]
    assert any("carga neta +2" in m for m in mensajes), mensajes
    neutra = dict(estado, smiles_acoplado="Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1")
    assert any("carga neta 0" in a["mensaje"] for a in avisos_estado_ligando(neutra))


@requiere_pypdf
def test_la_carga_neta_sale_traducida_en_el_informe_ingles():
    from core.i18n import reset_request_locale, set_request_locale
    from services.docking.ligand_state_warnings import avisos_estado_ligando

    estado = {"cambio_respecto_a_la_entrada": True, "smiles_entrada": "CCN", "smiles_acoplado": "CC[NH3+]"}
    aviso = avisos_estado_ligando(estado)[0]["mensaje"]
    token = set_request_locale("en")
    try:
        texto = _plano(_texto(_informe(avisos=[aviso])))
    finally:
        reset_request_locale(token)
    assert "net charge +1" in texto
    assert not re.search(r"carga neta|La especie acoplada", texto)


# ── B06: Ghose cuenta átomos TOTALES (con H), no pesados ──────────────────────────────────────────


def test_ghose_cuenta_atomos_totales_y_no_pesados():
    """Ghose et al. 1999: 20–70 átomos. Con átomos pesados el tope de 70 es inalcanzable con MW ≤ 480 (≈ 35 pesados) y una
    molécula de 12 pesados y 23 átomos totales (norepinefrina, E10 de la cápsula) fallaba por «pocos átomos»."""
    from chem.properties import GhoseRule, calculate_properties

    norepinefrina = calculate_properties("NC[C@H](O)c1ccc(O)c(O)c1", run_admet_ai=False)
    assert norepinefrina.heavy_atom_count == 12
    assert norepinefrina.ghose_pass is True
    cumple, motivos = GhoseRule.evaluate(300.0, 2.0, 19, 60.0)
    assert not cumple and any("19" in m and "átomos" in m for m in motivos), motivos
    assert GhoseRule.evaluate(300.0, 2.0, 20, 60.0)[0] is True
