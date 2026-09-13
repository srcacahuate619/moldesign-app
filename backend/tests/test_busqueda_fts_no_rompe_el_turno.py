"""El texto del investigador no puede romper la búsqueda del historial.

Lo encontró el gate runtime de MolChat, no la lectura: la primera pregunta real
con un SMILES dentro devolvió **HTTP 500**.

    PersistenciaFallida: ai_memory.db falló la operación: no such column: SMILES

`search_chat_history` construye la expresión `MATCH` pegando las palabras del
mensaje: `" OR ".join(words)`. En FTS5, `algo:` es sintaxis de **filtro por
columna**, `"` abre un literal, `*` es un prefijo y `NEAR`/`AND`/`OR`/`NOT` son
operadores. Una pregunta como «calcula las propiedades de este SMILES: CC(=O)O»
se convertía en una consulta con una columna inexistente.

Dos fallos, no uno:

1. el texto de quien pregunta entra sin escapar en un lenguaje de consulta —la
   forma de esto es una inyección, aunque aquí sólo alcance a romper la
   búsqueda—;
2. desde MOLCHAT-BE-008 los errores de `ai_memory.db` dejaron de tragarse, y
   este viajaba hasta el endpoint. La corrección de BE-008 es correcta para la
   conversación —perder un turno guardado importa— pero el índice de búsqueda es
   **derivado**: si falla, se degrada la búsqueda, no el turno.
"""

from __future__ import annotations

import sqlite3
import uuid

import pytest

from services.ai import memory_store
from services.ai.chat_service import ChatService
from services.ai.conversation_state import Conversation

ALICE = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def base_aislada(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_store, "_DB_PATH", tmp_path / "ai_memory.db")
    yield


TEXTOS_QUE_ROMPIAN = [
    pytest.param("calcula las propiedades de este SMILES: CC(=O)Oc1ccccc1C(=O)O", id="dos-puntos"),
    pytest.param('busca "aspirina" en el historial', id="comillas"),
    pytest.param("dame moleculas NEAR el receptor 7E2Y", id="operador-near"),
    pytest.param("compara aspirina AND cafeina", id="operador-and"),
    pytest.param("busca aspir* con prefijo", id="asterisco"),
    pytest.param("una pregunta con (parentesis) y ^acentos^", id="simbolos"),
    pytest.param("target: 7E2Y score: alto", id="varios-dos-puntos"),
]


class TestLaConsultaNoRompe:
    @pytest.mark.parametrize("mensaje", TEXTOS_QUE_ROMPIAN)
    def test_ningun_mensaje_hace_estallar_la_busqueda(self, mensaje):
        memory_store.index_chat_message(
            "conv-alice", "user", "una nota previa sobre la aspirina", user_id=ALICE
        )

        # No debe lanzar. Que encuentre o no es otra cosa; lo que no puede es
        # convertir la pregunta del investigador en un error de SQL.
        resultados = memory_store.search_chat_history(mensaje, user_id=ALICE)

        assert isinstance(resultados, list)

    def test_la_busqueda_sigue_encontrando_lo_que_debe(self):
        """Escapar no puede convertirse en «no buscar nada»."""
        memory_store.index_chat_message(
            "conv-alice", "user", "la aspirina contra el receptor 7E2Y", user_id=ALICE
        )

        assert memory_store.search_chat_history("aspirina receptor", user_id=ALICE)

    def test_un_termino_con_dos_puntos_se_busca_literal(self):
        memory_store.index_chat_message(
            "conv-alice", "user", "el score total fue alto en esa corrida", user_id=ALICE
        )

        resultados = memory_store.search_chat_history("score: total", user_id=ALICE)

        assert resultados, "«score» sigue siendo una palabra, no un filtro de columna"


class TestElIndiceEsDerivado:
    def test_un_fallo_del_indice_no_tumba_el_turno(self, monkeypatch):
        """Es la mitad de BE-008 que faltaba: derivado ≠ conversación."""
        servicio = ChatService()
        conv = Conversation(id="c1", user_id=ALICE)

        def _explota(*_a, **_kw):
            raise sqlite3.OperationalError("fts5 corrupto")

        monkeypatch.setattr(memory_store, "search_chat_history", _explota)

        mensajes = servicio._prepare_messages_with_context(
            conv,
            "una pregunta cualquiera sobre la aspirina",
            "",
            "",
            include_tools=False,
            include_engram=True,
        )

        assert mensajes, "el turno se construye igual, sin el historial"

    def test_la_conversacion_si_marca_su_fallo(self, monkeypatch):
        """El contraste: guardar el turno SÍ es de la conversación (BE-008)."""
        servicio = ChatService()
        conv = servicio.create_conversation(user_id=ALICE)

        def _explota(*_a, **_kw):
            raise sqlite3.OperationalError("disco lleno")

        monkeypatch.setattr(memory_store, "save_conversation", _explota)
        conv.add_message("user", "una pregunta cualquiera sobre la aspirina")
        servicio._persist_conv(conv)

        assert conv.persistencia_degradada
