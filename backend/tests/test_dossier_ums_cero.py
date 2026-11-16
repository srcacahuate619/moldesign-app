"""Un 0 de la señal de warheads dice qué buscan los SMARTS y qué no ven (D-08 de la investigación de 1.0.4).

Medido en el producto y sellado en `DEC-104-D08-REPLAY`: una sulfonamida, un hidroxamato o un tiol escritos como
anión dan `ums_warhead = 0`, igual que una molécula sin ningún grupo, mientras que en forma neutra dan 0,8833. La nota
va sólo con el cero: un valor distinto de cero, una corrida sin la señal y el UMS histórico siguen como estaban.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.dossier.bloques_protocolo import NOTA_UMS_CERO, campos_de_m5_zn
from services.dossier.localization import traducir_dossier
from services.dossier.model import Campo, _campo_dato, _v
from services.pipeline.protocols.m5.ejecucion import ums_autorizado

ETIQUETA = "Señal · warheads de zinc (UMS, SMARTS)"


def _ums(resultado: SimpleNamespace, pdb: str = "3DC3") -> dict:
    campos = campos_de_m5_zn(Campo, _campo_dato, _v, resultado, {"top_pose_affinity": -7.2},
                             SimpleNamespace(pdb_id=pdb))
    return next(c.as_dict() for c in campos if c.etiqueta == ETIQUETA)


@pytest.mark.parametrize("neutra, anion", [
    ("CS(=O)(=O)N", "CS(=O)(=O)[NH-]"),
    ("CC(=O)NO", "CC(=O)N[O-]"),
    ("CCS", "CC[S-]"),
])
def test_lo_que_dice_la_nota_es_lo_que_hace_el_producto(neutra, anion):
    assert ums_autorizado(neutra) > 0 and ums_autorizado(anion) == 0.0


def test_la_senal_se_calcula_sobre_el_smiles_de_entrada():
    """La nota dice «SMILES de entrada»: las dos rutas pasan a M5 el SMILES de la petición, no el protonado."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1] / "services"
    for ruta in (raiz / "docking" / "queue_handler.py", raiz / "pipeline" / "runner.py"):
        texto = ruta.read_text(encoding="utf-8")
        llamada = texto[texto.index("ejecutar_m5("):][:600]
        assert "smiles=pipeline_params.molecule_smiles" in llamada, ruta
    assert "SMILES de entrada" in NOTA_UMS_CERO


def test_el_carboxilato_si_se_reconoce_como_anion():
    """Por eso la nota no nombra el carboxilato."""
    assert ums_autorizado("CC(=O)[O-]") > 0 and "carboxil" not in NOTA_UMS_CERO


@pytest.mark.parametrize("pdb", ["3DC3", "9ZZZ"])          # con perfil y fuera de las tres dianas
def test_un_cero_calculado_lleva_la_nota(pdb):
    campo = _ums(SimpleNamespace(target_family="metalloenzyme", ums_warhead=0.0), pdb)

    assert campo["estado"] == "REGISTRADO" and campo["valor"] == NOTA_UMS_CERO
    assert campo["valor"].startswith("0.0000 — ")


def test_un_valor_distinto_de_cero_no_lleva_la_nota():
    campo = _ums(SimpleNamespace(target_family="metalloenzyme", ums_warhead=0.8833))
    assert campo["valor"] == "0.8833"


def test_sin_senal_ni_historico_sigue_sin_calcular():
    campo = _ums(SimpleNamespace(target_family="metalloenzyme"))
    assert campo["estado"] != "REGISTRADO" and campo["valor"] is None
    assert campo["razon"] == "No se calculó la señal de warheads."


def test_el_historico_no_lleva_la_nota_aunque_valga_cero():
    campo = _ums(SimpleNamespace(target_family="metalloenzyme", ums_score=0.0))
    assert "UMS HISTÓRICO" in campo["valor"] and campo["valor"] != NOTA_UMS_CERO


def test_la_nota_pasa_al_ingles_sin_dejar_castellano():
    from tests.test_dossier_en_ingles_completo import _parece_espanol

    campo = _ums(SimpleNamespace(target_family="metalloenzyme", ums_warhead=0.0))
    en = traducir_dossier({"bloques": [{"id": "protocolo", "requisitos": [
        {**campo, "clave": "protocolo.ums"}]}]}, "en")["bloques"][0]["requisitos"][0]

    assert en["valor"].startswith("0.0000 — the input SMILES matches none of the signal's SMARTS patterns")
    assert not _parece_espanol(en["valor"]), en["valor"]


# ── Revisión final de 1.0.4 (D-08): un cero es una observación sólo si el SMILES se leyó ─────────────────────────────


@pytest.mark.parametrize("ilegible", ["esto no es un smiles", "C1CC", "c1ccc(", "[Zn+9"])
def test_un_smiles_ilegible_no_se_registra_como_un_cero_calculado(ilegible):
    """`detect_warheads` devuelve todo falso ante un SMILES que RDKit no lee, y eso daba un 0.0 «calculado»."""
    assert ums_autorizado(ilegible) is None


def test_un_smiles_legible_sin_grupos_sigue_dando_cero_y_con_grupos_no():
    assert ums_autorizado("CCO") == 0.0
    assert ums_autorizado("CS(=O)(=O)N") > 0


def test_el_score_m5_no_cuenta_un_smiles_ilegible_como_cero_warheads():
    from services.pipeline.protocols.m5.zinc import calcular, smiles_legible

    assert smiles_legible("CCO") and not smiles_legible("esto no es un smiles") and not smiles_legible(None)
    resultado = calcular(pdb_id="3DC3", smiles="esto no es un smiles", vina_kcal_mol=-7.0, xgb_prob=0.5,
                         hay_zinc_confirmado=True, familia_normalizada="metalloenzyme")
    # Sin la señal de warheads el score no se calcula: no se rellena con un cero.
    assert resultado.m5_score is None


def test_la_nota_del_cero_dice_que_no_descarta_coordinacion_y_que_no_es_el_ums_combinado():
    assert "ni descarta coordinación" in NOTA_UMS_CERO
    assert "sin donantes ni MolChamb" in NOTA_UMS_CERO


def test_la_nota_anterior_se_sigue_traduciendo_para_los_dossiers_ya_escritos():
    from services.dossier.bloques_protocolo import NOTA_UMS_CERO_ANTERIOR
    from tests.test_dossier_en_ingles_completo import _parece_espanol

    for nota in (NOTA_UMS_CERO, NOTA_UMS_CERO_ANTERIOR):
        en = traducir_dossier({"bloques": [{"id": "protocolo", "requisitos": [
            {"etiqueta": ETIQUETA, "valor": nota, "estado": "REGISTRADO", "clave": "protocolo.ums"}]}]},
            "en")["bloques"][0]["requisitos"][0]
        assert not _parece_espanol(en["valor"]), en["valor"]
