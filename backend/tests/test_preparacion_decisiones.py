"""Decisiones del investigador en Preparación (punto 3, 2026-10-10).

Antes la auditoría ignoraba `projection.decisions`: un investigador que había visto
la ojiva de su ligando y decidido calcular el complejo no covalente no tenía dónde
dejarlo escrito, y el requisito seguía pidiendo revisión para siempre. Ahora:

- una decisión justificada sobre ESTA corrida resuelve lo que pedía revisión;
- sobre lo que bloquea se registra, pero no lo levanta;
- sin justificación, o sobre otra corrida del caso, no resuelve nada;
- el dato del requisito no cambia, y la justificación no se traduce.
"""

from __future__ import annotations

from core.i18n_plantillas import _PARECE_CASTELLANO
from services.dossier.localization import traducir_dossier
from services.dossier.model import build_case_dossier
from services.dossier.preparacion import PREFIJO_DECISION, build_preparacion
from services.dossier.schemas import DecisionHumana
from tests.test_diff_de_especies_de_la_corrida import _diff
from tests.test_preparacion_auditoria import _bloque, _con_procedencia, _requisito
from tests.test_preparacion_covalente_membrana_campo import IBRUTINIB

HUELLA = "tarea:task-completa-0001"
MOTIVO = "Se calcula el complejo no covalente previo: es el paso que ordena la serie."


def _auditar(*decisiones: DecisionHumana) -> dict:
    caso = _con_procedencia(_diff(), smiles_acoplado=IBRUTINIB)
    caso["projection"] = caso["projection"].model_copy(update={"decisions": list(decisiones)})
    return build_preparacion(build_case_dossier(**caso), caso["eval_result"], caso["projection"])


def _decision(clave: str, nota: str | None = MOTIVO, huella: str = HUELLA) -> DecisionHumana:
    return DecisionHumana(control_code=PREFIJO_DECISION + clave, fingerprint=huella,
                          at="2026-10-10T21:00:00Z", note=nota)


def test_la_auditoria_dice_con_que_huella_se_decide():
    auditoria = _auditar()
    assert auditoria["huella_de_decision"] == HUELLA
    assert auditoria["decididos"] == []
    assert auditoria["decisiones_de_otras_corridas"] == 0


def test_una_decision_justificada_resuelve_lo_que_pedia_revision():
    sin = _auditar()
    con = _auditar(_decision("ligando.covalente"))

    covalente = _requisito(con, "ligando.covalente")
    assert covalente["estado"] == "REVISAR"                      # el dato no cambia
    assert covalente["valor"] == _requisito(sin, "ligando.covalente")["valor"]
    assert covalente["decision"] == {"justificacion": MOTIVO, "registrada": "2026-10-10T21:00:00Z",
                                     "resuelve": True}
    assert "ligando.covalente" in sin["en_revision"]
    assert "ligando.covalente" not in con["en_revision"]
    assert con["decididos"] == ["ligando.covalente"]


def test_resolver_todo_lo_que_pide_revision_en_un_bloque_lo_deja_registrado():
    pose = _bloque(_auditar(), "pose")
    abiertos = [r["clave"] for r in pose["requisitos"] if r["estado"] not in ("REGISTRADO", "PASA", "NO_APLICA")]
    assert pose["estado"] == "REVISION" and abiertos
    decidida = _auditar(*[_decision(clave) for clave in abiertos])
    assert _bloque(decidida, "pose")["estado"] == "REGISTRADO"


def test_lo_que_bloquea_se_registra_pero_no_se_levanta():
    auditoria = _auditar(_decision("entorno.metales_cofactores", "El zinc no participa en la unión."))
    metales = _requisito(auditoria, "entorno.metales_cofactores")
    assert metales["decision"]["resuelve"] is False
    assert "entorno.metales_cofactores" in auditoria["bloqueantes"]
    assert auditoria["estado"] == "BLOQUEADO"


def test_sin_justificacion_o_sobre_otra_corrida_no_resuelve():
    auditoria = _auditar(
        _decision("ligando.covalente", nota="  "),
        _decision("entorno.membrana", huella="tarea:otra-corrida"),
        DecisionHumana(control_code="LIGANDO_GRANDE", fingerprint=HUELLA, note=MOTIVO),  # de la comprobación previa
    )
    assert "decision" not in _requisito(auditoria, "ligando.covalente")
    assert "decision" not in _requisito(auditoria, "entorno.membrana")
    assert auditoria["decididos"] == []
    assert auditoria["decisiones_de_otras_corridas"] == 1


def test_la_justificacion_es_del_investigador_y_no_se_traduce():
    en = traducir_dossier(_auditar(_decision("ligando.covalente")), "en")
    covalente = _requisito(en, "ligando.covalente")
    assert covalente["decision"]["justificacion"] == MOTIVO
    assert not _PARECE_CASTELLANO.search(covalente["razon"])


def test_con_todo_decidido_el_techo_sigue_en_revision_y_lo_dice():
    from services.dossier.preparacion import Requisito, estado_global
    from services.dossier.model import Campo
    from services.dossier.taxonomy import Estado

    decidido = Requisito("x", Campo("X", "y", Estado.REVISAR, "z"), "f", False,
                         decision={"justificacion": MOTIVO, "registrada": None})
    estado, razon = estado_global([decidido])
    assert estado == "REVISION"
    assert razon.startswith("Todos los requisitos tienen dato registrado o una decisión justificada")
    assert not _PARECE_CASTELLANO.search(traducir_dossier({"razon": razon}, "en")["razon"])
