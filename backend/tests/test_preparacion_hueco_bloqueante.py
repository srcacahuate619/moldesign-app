"""Sólo bloquean los cortes físicos del esqueleto medidos junto al sitio."""
import copy
import pytest
from tests.test_preparacion_auditoria import _auditar, _con_procedencia, _requisito, _bloque
from tests.test_preparacion_cadenas_truncadas import _truncada
from services.dossier.localization import traducir_dossier

GAP={"chain":"A","after":"THR 197","before":"VAL 199","c_n_distance_A":4.79,"missing_declared":1,"distance_to_box_A":1.25,"site_critical":True}

def audited(gaps, trunc=None):
    case=_con_procedencia()
    prep=case["eval_result"].docking_protocol["execution_provenance"]["receptor_prep"]
    if gaps is not ...: prep["backbone_gaps"]=gaps
    if trunc is not None: prep["truncated_sidechains"]=trunc
    return _auditar(case)

@pytest.mark.parametrize("lang, phrase",[("es","Modela o repara"),("en","Model or repair")])
def test_hueco_en_sitio_bloquea_con_ubicacion_y_accion(lang,phrase):
    audit=traducir_dossier(audited([copy.deepcopy(GAP)]),lang)
    req=_requisito(audit,"receptor.huecos")
    assert req["estado"] == "ABSTENCION"
    assert req["imprescindible"] is True
    assert "receptor.huecos" in audit["bloqueantes"]
    assert audit["estado"] == "BLOQUEADO" and _bloque(audit,"receptor")["estado"] == "BLOQUEADO"
    assert req["ubicacion"] == [GAP]
    assert phrase in req["accion_recomendada"]
    assert all(str(x) in req["valor"] for x in ["A","THR 197","VAL 199",4.79,1,1.25])
    assert "esqueleto" in audit["razon"] if lang=="es" else "backbone" in audit["razon"].lower()
    assert "cavidad" in req["razon"] if lang=="es" else "cavity" in req["razon"]
    if lang == "en":
        assert "de la caja" not in req["valor"] and "ausente(s)" not in req["valor"]
        assert "Å from the box" in req["valor"]


def test_hueco_lejano_solo_revision():
    audit=audited([{**GAP,"distance_to_box_A":20.0,"site_critical":False}])
    assert _requisito(audit,"receptor.huecos")["estado"] == "REVISAR"
    assert "receptor.huecos" not in audit["bloqueantes"]
    assert _bloque(audit,"receptor")["estado"] != "BLOQUEADO"


def test_truncadas_en_sitio_no_bloquean():
    audit=audited([],[_truncada(198,1.25,True)])
    assert _requisito(audit,"receptor.cadenas_truncadas")["estado"] == "REVISAR"
    assert "receptor.cadenas_truncadas" not in audit["bloqueantes"]


def test_sin_hueco_continuo_no_se_inventa_bloqueo():
    audit=audited([])
    assert _requisito(audit,"receptor.huecos")["estado"] == "REGISTRADO"
    assert "receptor.huecos" not in audit["bloqueantes"]


def test_sin_medida_no_evaluado_no_obligatorio():
    audit=audited(...)
    req=_requisito(audit,"receptor.huecos")
    assert req["estado"] == "NO_EVALUADO" and req["imprescindible"] is False
    assert "ubicacion" not in req
    assert "receptor.huecos" not in audit["bloqueantes"]


def test_bloquea_distancia_fisica_aunque_remark465_no_declare_ausentes():
    gap={**GAP,"missing_declared":None}
    audit=audited([gap])
    assert "receptor.huecos" in audit["bloqueantes"]
    req=_requisito(audit,"receptor.huecos")
    assert req["ubicacion"][0]["missing_declared"] is None
    assert "no declara" in req["valor"]
    english=_requisito(traducir_dossier(audit,"en"),"receptor.huecos")
    assert "does not declare" in english["valor"] and "no declara" not in english["valor"]
