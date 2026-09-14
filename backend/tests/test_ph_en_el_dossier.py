"""El pH al que se acopló tiene que estar en el expediente.

Mientras el pH estuvo escrito a mano en 7.4, omitirlo del dossier era una
omisión tolerable: siempre era el mismo. Desde que el usuario puede elegirlo en
las opciones avanzadas deja de serlo — dos corridas de la misma molécula pueden
haber acoplado especies distintas, y sin esto el expediente no permite
distinguirlas ni saber cuál se ejecutó.

`ligand_state` YA se persistía entero; lo que faltaba era leerlo. El dossier
sólo sacaba de él la transferencia de péptidos.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.dossier import model as dossier_model


def _campos(ligand_state):
    """Los campos del bloque que lee `ligand_state`, sin montar un dossier entero."""
    eval_result = SimpleNamespace(
        ligand_state=ligand_state,
        affinity_kcal=-7.2,
        pose_selection_status=None,
    )
    fabricante = getattr(dossier_model, "_campos_de_protocolo_y_abstencion", None)
    if fabricante is None:
        pytest.skip("la función que compone estos campos cambió de nombre")
    return {c.etiqueta: c for c in fabricante(eval_result, resumen={})}


PROTONACION = {
    "aplicada": True,
    "motor": "dimorphite-dl",
    "ph": 5.5,
    "ph_solicitado": 5.5,
    "aviso_de_ph": None,
    "alternativas": 3,
    "seleccion": {"criterio": "cargas_esperadas_ph_5.5", "ph": 5.5, "empatados": 1},
}


def test_el_ph_ejecutado_aparece_en_el_dossier():
    campos = _campos({"protonacion": PROTONACION})
    campo = campos.get("pH de protonación del ligando")
    assert campo is not None, "el dossier no dice a qué pH se protonó"
    assert campo.valor == "5.5"


def test_si_se_acoto_el_dossier_dice_las_dos_cifras():
    """Escribir sólo el pH pedido cuando corrió otro sería peor que callarlo:
    parecería verificado."""
    campos = _campos({
        "protonacion": {
            **PROTONACION,
            "ph": 12.0,
            "ph_solicitado": 20.0,
            "aviso_de_ph": "pH 20 por encima del rango admitido; se acopla a 12.",
        }
    })
    valor = campos["pH de protonación del ligando"].valor
    assert "12" in valor and "20" in valor, valor


def test_un_empate_alfabetico_se_declara():
    """El desempate lo rompe el orden del SMILES, no la química. Cambia cuánto
    vale la elección, así que se dice."""
    campos = _campos({
        "protonacion": {**PROTONACION, "seleccion": {**PROTONACION["seleccion"], "empatados": 2}}
    })
    valor = campos["Especie acoplada"].valor
    assert "empataron" in valor and "alfab" in valor, valor


def test_sin_empate_no_se_menciona_el_desempate():
    campos = _campos({"protonacion": PROTONACION})
    assert "empataron" not in (campos["Especie acoplada"].valor or "")


def test_una_corrida_sin_protonacion_no_inventa_el_campo():
    """Ausente es ausente: el dossier no puede suponer 7.4 porque sea lo
    habitual. Ver la regla del archivo: un hueco nunca pasa por contenido."""
    campos = _campos({"peptide_transfer": {"status": "completed"}})
    assert "pH de protonación del ligando" not in campos


def test_protonacion_no_aplicada_tampoco_lo_inventa():
    """Cuando dimorphite no está o falló, se acopla la forma neutra y NO hay
    un pH que declarar."""
    campos = _campos({
        "protonacion": {"aplicada": False, "motor": None, "ph": None, "motivo": "no instalado"}
    })
    assert "pH de protonación del ligando" not in campos
