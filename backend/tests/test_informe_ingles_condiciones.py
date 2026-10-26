"""SCI-A-026: las condiciones de interpretación del informe también salen en inglés.

La auditoría encontró en el informe inglés, en castellano: la advertencia de los
pesos del stacking sin salida, «Faltan poses o afinidad serializada», los rótulos
«EVIDENCIA DISPONIBLE / INCOMPLETA», la piscina del ensemble y «Sin datos
suficientes». Cada uno se comprueba aquí con el texto que emite el backend.
"""
from __future__ import annotations

import pytest

from core.i18n_plantillas import traducir


@pytest.mark.parametrize("texto, ingles", [
    ("Faltan poses o afinidad serializada.", "Poses or serialized affinity are missing."),
    ("EVIDENCIA DISPONIBLE", "EVIDENCE AVAILABLE"),
    ("EVIDENCIA INCOMPLETA", "INCOMPLETE EVIDENCE"),
    ("REVISIÓN NECESARIA", "REVIEW REQUIRED"),
    ("Sin datos suficientes", "Insufficient data"),
    ("Ensemble · 3 de 3 conformaciones · pose elegida entre 9 candidatas",
     "Ensemble · 3 of 3 conformers · pose chosen from 9 candidates"),
])
def test_cada_condicion_tiene_ingles(texto, ingles):
    assert traducir(texto, "en") == ingles


def test_los_pesos_sin_salida_conservan_la_lista_y_la_cautela():
    texto = ("El protocolo de familia asigna peso en el stacking a XGBoost, CL-GNN, pero esas "
             "etapas no serializaron salida en esta corrida. El peso describe lo que el protocolo "
             "esperaba, no lo que aporto: no debe leerse como que ese modelo domino el resultado.")
    ingles = traducir(texto, "en")
    assert ingles.startswith("The family protocol assigns stacking weight to XGBoost, CL-GNN,")
    assert "not what it contributed" in ingles and "dominated" in ingles


def test_las_frases_vienen_del_codigo_que_las_emite():
    """El guardián mira el texto real: si el emisor cambia, esta prueba se entera."""
    import inspect
    from services.blockchain import evidence_summary
    from services.docking import selectividad_margen
    fuente = inspect.getsource(evidence_summary)
    for literal in ("Faltan poses o afinidad serializada.", '"EVIDENCIA DISPONIBLE"',
                    '"EVIDENCIA INCOMPLETA"', "El protocolo de familia asigna peso en el stacking a "):
        assert literal in fuente
    assert selectividad_margen.VEREDICTO_SIN_DATOS == "Sin datos suficientes"
