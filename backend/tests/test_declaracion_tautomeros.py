"""FEP-ready, paso 1: el tautómero se declara, no sólo se cuenta.

`FEP-01` midió que 164 de 203 ligandos tienen más de un tautómero enumerable y
que el pipeline no declara cuál usa. El canónico de RDKit que se acopla es una
representación reproducible, no una predicción de población: tomarlo como la
verdad y seguir es exactamente lo que un paquete FEP no puede hacer en silencio.

Estas pruebas fijan el contrato de `chem/declaracion_tautomeros.py`: tres
estados (uno solo, varios sin descartar, no resuelto), candidatos con
identificador estable, la estereoquímica sp3 intacta y nunca una excepción; y
que el dossier lo enseñe sin reconstruirlo en corridas que no lo traen.
"""

from __future__ import annotations

from types import SimpleNamespace

from chem.declaracion_tautomeros import (
    MAX_TAUTOMEROS,
    MULTIESTADO_REQUERIDO,
    NO_RESUELTO,
    RESUELTO_UNICO,
    declarar_tautomeros,
)
from services.dossier import model as dossier_model
from services.dossier.taxonomy import Estado


def test_un_solo_tautomero_queda_resuelto():
    d = declarar_tautomeros("CCO")

    assert d["estado"] == RESUELTO_UNICO
    assert d["n_candidatos"] == 1 and d["enumeracion_completa"]
    assert d["atomos_tautomericos"] == []


def test_la_hidroxipiridina_requiere_varios_estados_y_no_se_descarta_ninguno():
    """El canónico (la piridona) no es el de entrada (la hidroxipiridina): los dos
    viajan, junto con el tercero que enumera RDKit, y ninguno lleva población."""
    d = declarar_tautomeros("Oc1ccccn1")

    assert d["estado"] == MULTIESTADO_REQUERIDO
    smiles = {c["smiles"] for c in d["candidatos"]}
    assert {"O=c1cccc[nH]1", "Oc1ccccn1"} <= smiles
    assert sum(c["es_canonico"] for c in d["candidatos"]) == 1
    assert sum(c["es_entrada"] for c in d["candidatos"]) == 1
    assert d["poblaciones"] is None and d["poblaciones_motivo"]
    assert d["atomos_tautomericos"], "hay que decir qué átomos cambian"


def test_los_identificadores_no_dependen_del_orden_del_enumerador():
    a, b = declarar_tautomeros("Oc1ccccn1"), declarar_tautomeros("O=c1cccc[nH]1")

    assert [c["smiles"] for c in a["candidatos"]] == [c["smiles"] for c in b["candidatos"]]
    assert [c["id"] for c in a["candidatos"]] == ["T0", "T1", "T2"]


def test_la_estereoquimica_sp3_sobrevive():
    """El valor por defecto de RDKit la borraba: los dos enantiómeros de la
    talidomida salían siendo la misma molécula."""
    s = declarar_tautomeros("O=C1CC[C@H](N2C(=O)c3ccccc3C2=O)C(=O)N1")
    r = declarar_tautomeros("O=C1CC[C@@H](N2C(=O)c3ccccc3C2=O)C(=O)N1")

    assert "@" in s["smiles_canonico"] and "@" in r["smiles_canonico"]
    assert s["smiles_canonico"] != r["smiles_canonico"]


def test_si_la_enumeracion_se_corta_en_el_tope_no_queda_resuelto():
    """Un flavonoide tipo quercetina pasa de 32 tautómeros: la lista de candidatos
    está incompleta, y eso no puede presentarse como «varios sin descartar»."""
    d = declarar_tautomeros("Oc1cc(O)c2c(c1)oc(-c1ccc(O)c(O)c1)c(O)c2=O")

    assert d["estado"] == NO_RESUELTO
    assert not d["enumeracion_completa"]
    assert d["n_candidatos"] == MAX_TAUTOMEROS
    assert "INCOMPLETA" in d["motivo"]


def test_un_smiles_invalido_es_un_estado_y_no_una_excepcion():
    d = declarar_tautomeros("esto no es un smiles")

    assert d["estado"] == NO_RESUELTO and d["motivo"] == "SMILES_INVALIDO"


def _campos_protocolo(ligand_state):
    eval_result = SimpleNamespace(ligand_state=ligand_state, affinity_kcal=-7.2, pose_selection_status=None)
    return {c.etiqueta: c for c in dossier_model._campos_de_protocolo_y_abstencion(eval_result, resumen={})}


def test_el_dossier_pide_revisar_cuando_quedan_varios_candidatos():
    campos = _campos_protocolo({"tautomeria": {"declaracion": declarar_tautomeros("Oc1ccccn1")}})
    campo = campos["Tautómero del ligando"]

    assert campo.estado == Estado.REVISAR
    assert "3 tautómeros" in campo.razon and "canónico de RDKit" in campo.razon


def test_el_dossier_registra_el_caso_resuelto_y_se_abstiene_en_el_no_resuelto():
    unico = _campos_protocolo({"tautomeria": {"declaracion": declarar_tautomeros("CCO")}})
    roto = _campos_protocolo({"tautomeria": {"declaracion": declarar_tautomeros("xx")}})

    assert unico["Tautómero del ligando"].estado == Estado.REGISTRADO
    assert roto["Tautómero del ligando"].estado == Estado.ABSTENCION


def test_una_corrida_sin_declaracion_no_la_inventa():
    """Las corridas anteriores sólo contaban alternativas: no se reconstruye nada."""
    campos = _campos_protocolo({"tautomeria": {"aplicada": True, "alternativas": 3}})

    assert "Tautómero del ligando" not in campos
    prep = dossier_model._campo_de_estado_quimico(SimpleNamespace(ligand_state={"tautomeria": {"alternativas": 3}}))
    assert prep.etiqueta == "Protonación, tautomería y estereoquímica"


def test_con_declaracion_la_preparacion_dice_lo_que_falta_de_verdad():
    prep = dossier_model._campo_de_estado_quimico(
        SimpleNamespace(ligand_state={"tautomeria": {"declaracion": declarar_tautomeros("CCO")}}))

    assert prep.etiqueta == "Estereoquímica del ligando"
    assert prep.estado == Estado.NO_EVALUADO


def test_el_conformador_adjunta_la_declaracion():
    """Por el camino real: el conformador tiene que dejarla en `estado_del_ligando`."""
    from chem.conformer import _construir_conformero

    estado = _construir_conformero("Oc1ccccn1")["estado_del_ligando"]
    declaracion = estado["tautomeria"]["declaracion"]

    assert declaracion["estado"] == MULTIESTADO_REQUERIDO
    assert declaracion["smiles_entrada"] == estado["smiles_entrada"]
