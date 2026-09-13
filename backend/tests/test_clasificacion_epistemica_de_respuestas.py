"""MOLCHAT-AUD-01, eje SCI — qué es cada respuesta, y qué no se puede fingir.

El §8 pide cuatro cosas del eje científico y ninguna estaba implementada:
clasificar la respuesta (cálculo / dato persistido / inferencia / recuperación
externa / explicación), citar la procedencia, no fabricar resultados y
abstenerse cuando no hay dato.

Las tres primeras son un mismo agujero de contrato: el turno inyectaba
`compute_properties: MW: 180.2 Da` y `predict_admet: LogS: -2.1` con el mismo
formato y la misma autoridad aparente, aunque uno sea aritmética determinista
sobre el grafo molecular y el otro la salida de un modelo entrenado. Un lector
—y el propio modelo que redacta— no tiene con qué distinguirlos.

La cuarta apareció dos veces en la lectura de `tools/`, en la misma forma: una
comprobación falla, el error se traga, y la herramienta contesta el **negativo**
como si lo hubiera comprobado. «Sin alertas PAINS» cuando el catálogo PAINS ni
se cargó es fabricar un resultado, no ser conciso.
"""

from __future__ import annotations

import pytest

from services.ai.tool_registry import (
    CLASES_EPISTEMICAS,
    ToolDef,
    format_tool_results,
    get_tool_registry,
)


def _todas_las_tools() -> list[ToolDef]:
    from api.routers.ai import _bootstrap_tools

    _bootstrap_tools()
    return get_tool_registry().list_all()


def test_toda_herramienta_declara_que_clase_de_respuesta_produce():
    sin_clase = [
        t.name for t in _todas_las_tools() if t.clase not in CLASES_EPISTEMICAS
    ]

    assert sin_clase == [], (
        "estas herramientas no declaran si su salida es cálculo, dato "
        f"persistido, inferencia, recuperación externa o explicación: {sin_clase}"
    )


def test_toda_herramienta_declara_su_procedencia():
    sin_fuente = [t.name for t in _todas_las_tools() if not t.procedencia.strip()]

    assert sin_fuente == [], (
        f"estas herramientas no dicen de dónde sale su número: {sin_fuente}"
    )


def test_el_calculo_y_la_inferencia_no_se_presentan_igual():
    """Es el hallazgo en una línea: dos estatutos, un mismo formato."""
    tools = {t.name: t for t in _todas_las_tools()}

    assert tools["compute_properties"].clase == "calculo"
    assert tools["predict_admet"].clase == "inferencia"
    assert tools["query_evaluation_details"].clase == "dato_persistido"
    assert tools["pubchem_lookup"].clase == "recuperacion_externa"


def test_el_texto_inyectado_lleva_la_clase_y_la_fuente():
    texto = format_tool_results([
        {"tool": "compute_properties", "result": "MW: 180.2 Da"},
    ])

    assert "compute_properties" in texto
    assert "cálculo" in texto.lower()
    assert "rdkit" in texto.lower()
    assert "MW: 180.2 Da" in texto


def test_una_inferencia_se_marca_como_prediccion():
    texto = format_tool_results([
        {"tool": "predict_admet", "result": "LogS: -2.1"},
    ])

    assert "inferencia" in texto.lower() or "predicción" in texto.lower()


def test_un_error_de_herramienta_es_abstencion_y_no_trae_numero():
    texto = format_tool_results([
        {"tool": "predict_admet", "error": "ADMET-AI no disponible"},
    ])

    assert "no se obtuvo" in texto.lower() or "sin dato" in texto.lower()
    assert "no inventes" in texto.lower()


def test_una_herramienta_desconocida_no_se_presenta_como_verificada():
    texto = format_tool_results([
        {"tool": "herramienta_que_no_existe", "result": "42"},
    ])

    assert "sin clasificar" in texto.lower()


def test_el_prompt_permanente_pide_conservar_la_clase_y_abstenerse():
    """La etiqueta no sirve si el modelo la borra al redactar."""
    from services.ai.chat_service import ChatService
    from services.ai.conversation_state import Conversation

    servicio = ChatService()
    conv = Conversation(id="x", user_id=None)
    mensajes = servicio._prepare_messages_with_context(
        conv, "hola", "", "", include_tools=False, include_engram=False
    )
    prompt = "\n".join(m.get("content", "") for m in mensajes)

    assert "PROCEDENCIA" in prompt
    assert "ABSTENCIÓN" in prompt
    assert "predicción como una medida" in prompt


@pytest.mark.asyncio
async def test_pains_no_declara_ausencia_de_alertas_si_no_pudo_mirar(monkeypatch):
    """Fabricación de un negativo: el §8 la prohíbe igual que la de un positivo."""
    from services.ai.tools import rdkit_tools

    import chem.pains as pains

    def _catalogo_roto():
        raise RuntimeError("catálogo PAINS no disponible")

    monkeypatch.setattr(pains, "_get_pains_catalog", _catalogo_roto)

    texto = await rdkit_tools.check_druglikeness("CC(=O)Oc1ccccc1C(=O)O")

    assert "sin alertas pains" not in texto.lower()
    assert "no se pudo" in texto.lower() or "no evaluad" in texto.lower()


@pytest.mark.asyncio
async def test_pains_si_dice_que_no_hay_alertas_cuando_de_verdad_miro():
    from services.ai.tools import rdkit_tools

    texto = await rdkit_tools.check_druglikeness("CCO")

    assert "PAINS" in texto
    assert "no se pudo" not in texto.lower()


@pytest.mark.asyncio
async def test_la_fragmentacion_fallida_no_se_reporta_como_cero_fragmentos(monkeypatch):
    from rdkit.Chem import BRICS

    from services.ai.tools import analog_tools

    def _brics_roto(*_a, **_kw):
        raise RuntimeError("BRICS falló")

    monkeypatch.setattr(BRICS, "BRICSDecompose", _brics_roto)

    texto = await analog_tools.explain_fragments("CC(=O)Oc1ccccc1C(=O)O")

    assert "Fragmentos BRICS: 0" not in texto
    assert "no se pudo" in texto.lower() or "no disponible" in texto.lower()
