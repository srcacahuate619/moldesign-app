"""SCI-A-036: «Poses solicitadas al motor» es lo que selló la corrida, no lo que dice el caso.

El dossier la tomaba de `config.num_poses`, la configuración del caso, que es otro
objeto y puede cambiar después de ejecutar. Lo declarado por el caso va aparte, en
«Poses declaradas por el caso», con REVISAR si difiere.
"""
from __future__ import annotations

from services.dossier.model import build_case_dossier
from services.dossier.taxonomy import Estado
from tests.fixtures_dossier import caso_completo


def _campo(dossier, seccion, etiqueta):
    return next(c for c in getattr(dossier, seccion) if c.etiqueta == etiqueta)


def test_lo_pedido_al_motor_sale_del_protocolo_aunque_el_caso_diga_otra_cosa():
    caso = caso_completo()
    caso["projection"].inputs.config.num_poses = 18      # el caso cambió después
    dossier = build_case_dossier(**caso)
    assert _campo(dossier, "generacion", "Poses solicitadas al motor").valor == "9"
    declarado = _campo(dossier, "protocolo", "Poses declaradas por el caso")
    assert declarado.valor == "18" and declarado.estado is Estado.REVISAR


def test_sin_protocolo_no_se_suple_con_el_caso():
    caso = caso_completo()
    caso["eval_result"].docking_protocol = {}
    dossier = build_case_dossier(**caso)
    campo = _campo(dossier, "generacion", "Poses solicitadas al motor")
    assert campo.valor is None and not campo.estado.es_afirmativo
