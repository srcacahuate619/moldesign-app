from __future__ import annotations

import pytest

from core import i18n


@pytest.fixture
def idioma_ingles():
    token = i18n.set_request_locale("en-US")
    try:
        yield
    finally:
        i18n.reset_request_locale(token)


@pytest.mark.parametrize(
    ("origen", "esperado"),
    [
        (
            "La fuente incluye 3 cadena(s); el receptor de la corrida sólo conserva 'A'.",
            "The source contains 3 chain(s); the run's receptor retains only 'A'.",
        ),
        (
            "Cola de evaluaciones saturada: no se pudo iniciar en 30s.",
            "Evaluation queue is saturated; could not start within 30s.",
        ),
        (
            "La cohorte está en estado `blocked` y no se puede ejecutar.",
            "The cohort is in state `blocked` and cannot be run.",
        ),
        (
            "No existe una corrida persistida con ese task_id para molecule_id=case-123",
            "No persisted run exists for that task_id and molecule_id=case-123",
        ),
        (
            "Se detectaron 1 estereocentro(s) sin estereoquimica definida. RDKit elegira un enantiomero arbitrario para el docking 3D. Usa '@' o '@@' en el SMILES para especificar la quiralidad deseada.",
            "1 stereocenter(s) have undefined stereochemistry. RDKit will choose an arbitrary enantiomer for 3D docking. Use '@' or '@@' in SMILES to specify the desired chirality.",
        ),
        (
            "No tienes permiso para exportar el dossier de esta molécula.",
            "You do not have permission to export this molecule's dossier.",
        ),
    ],
)
def test_capa4_traduce_avisos_y_errores_dinamicos(origen, esperado, idioma_ingles) -> None:
    assert i18n.translate_text(origen) == esperado


def test_capa4_localiza_descripciones_openapi_sin_tratar_datos_como_mensajes(
    idioma_ingles,
) -> None:
    schema = {
        "paths": {
            "/evaluation/engines": {
                "get": {
                    "summary": "Qué motores de docking puede ejecutar esta instalación",
                    "tags": ["Evaluación científica"],
                    "operationId": "leer_evaluacion",
                }
            }
        },
        "components": {
            "schemas": {
                "EvaluationSubmitRequest": {
                    "properties": {
                        "ph": {"description": "pH solicitado para el microestado del ligando"}
                    }
                }
            }
        },
    }

    localized = i18n.localize_openapi_payload(schema)
    ordinary = i18n.localize_payload({"description": "pH solicitado para el microestado del ligando"})

    operation = localized["paths"]["/evaluation/engines"]["get"]
    assert operation["summary"] == "Docking engines this installation can run"
    assert operation["tags"] == ["Scientific evaluation"]
    assert operation["operationId"] == "leer_evaluacion"
    description = localized["components"]["schemas"]["EvaluationSubmitRequest"]["properties"]["ph"]["description"]
    assert description == "Requested pH for the ligand microstate"
    assert ordinary["description"] == "pH solicitado para el microestado del ligando"
