"""El informe narrativo no presenta el índice compuesto como la nota de la molécula.

`total_score` no ordena mejor que la afinidad de Vina (SUP-02, NO_GO) y la interfaz lo rotula «índice compuesto
heredado». Hasta el 2026-11-15 viajaba al modelo como `score_general_sobre_100`, y el párrafo lo leía como la
puntuación general del candidato (D-07 de la investigación de 1.0.4). El valor que se envía no cambia.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from services.evaluation import interpreter


def _peticion(total_score: float | None = 61.04) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=None,
        molecule_smiles="CC(=O)Oc1ccccc1C(=O)O",
        target_name="3F75",
        affinity_kcal=-5.665,
        score_breakdown=None if total_score is None else SimpleNamespace(
            total_score=total_score, ligand_efficiency=0.41, lipophilic_efficiency=2.1),
        properties=SimpleNamespace(sa_score=1.23),
        hotspots_hit=[],
    )


def _datos(mensajes: list[dict]) -> dict:
    contenido = mensajes[1]["content"]
    return json.loads(contenido.split("```json\n", 1)[1].rsplit("\n```", 1)[0])


def test_el_indice_viaja_rotulado_como_heredado_con_el_mismo_valor():
    mensajes = interpreter.build_ai_messages(_peticion())
    datos = _datos(mensajes)

    assert datos["indice_compuesto_heredado_0_100"] == 61.0
    assert "score_general_sobre_100" not in datos
    assert "score_general" not in mensajes[0]["content"] + mensajes[1]["content"]


def test_el_prompt_pide_no_juzgar_la_molecula_por_el_indice():
    sistema = interpreter.build_ai_messages(_peticion())[0]["content"]

    assert '"indice_compuesto_heredado_0_100" es un indice historico de MolDesign, no una medida del potencial' in sistema
    assert "llamalo indice compuesto heredado" in sistema


def test_sin_contexto_de_cuenta_no_se_invita_a_comparar_con_evaluaciones_previas():
    """La memoria de cuenta ya no existe: la regla que invitaba a compararse con ella no puede seguir en el prompt."""
    sistema, usuario = (m["content"] for m in interpreter.build_ai_messages(_peticion()))
    assert "evaluaciones previas" not in sistema
    assert "---" not in usuario.split("```json", 1)[0]


def test_sin_desglose_el_indice_sigue_declarado_como_no_disponible():
    assert _datos(interpreter.build_ai_messages(_peticion(None)))["indice_compuesto_heredado_0_100"] == "N/A"
