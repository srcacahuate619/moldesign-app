"""MOLCHAT-BE-008 — la persistencia de la conversación no se traga sus errores.

`create_conversation`, `load_conversation_from_db` y `delete_conversation`
envolvían su acceso a `ai_memory.db` en `except Exception: pass`. Las tres
consecuencias son distintas y ninguna era visible:

* crear: la conversación existía en memoria y no en disco. El investigador
  recibía un id, escribía en él, y al reiniciar no había nada;
* leer: un fallo de la base y «esa conversación no es tuya» devolvían lo mismo,
  `None`, así que el producto no podía distinguir un 404 legítimo de un 503;
* borrar: se contestaba «borrada» sin haber borrado nada, que es la peor de las
  tres — el investigador cree que un historial ya no está.

El §8 pide persistencia «atómica y recuperable». Recuperable exige, como
mínimo, que el fallo se sepa.

El turno del chat es el caso aparte: `_persist_conv` corre después de que el
modelo ya contestó, y hacer estallar el turno ahí borraría una respuesta que ya
existe. Ahí la regla es la otra mitad de «no se traga sus errores»: la
conversación queda marcada como degradada y el turno lo dice.
"""

from __future__ import annotations

import sqlite3
import uuid

import pytest

from services.ai import memory_store
from services.ai.chat_service import ChatService
from services.ai.memory_store import PersistenciaFallida

ALICE = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def base_aislada(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_store, "_DB_PATH", tmp_path / "ai_memory.db")
    yield


@pytest.fixture
def base_rota(monkeypatch):
    """Cualquier acceso a la base falla, como un disco lleno o un WAL corrupto."""

    def _explota(*_a, **_kw):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(memory_store, "_get_conn", _explota)


def test_crear_una_conversacion_que_no_se_guarda_no_se_declara_creada(base_rota):
    servicio = ChatService()

    with pytest.raises(PersistenciaFallida):
        servicio.create_conversation(user_id=ALICE)


def test_una_conversacion_no_guardada_no_queda_en_memoria(base_rota):
    """Si no está en disco, tampoco puede quedar como activa de la cuenta."""
    servicio = ChatService()

    with pytest.raises(PersistenciaFallida):
        servicio.create_conversation(user_id=ALICE)

    # No se consulta `list_conversations` a propósito: con la base rota ésa
    # lanza también. Lo que se vigila aquí es la caché en memoria, que era donde
    # quedaba la conversación fantasma.
    assert servicio._conversations == {}
    assert servicio._active_by_user == {}
    assert servicio.get_conversation(user_id=ALICE) is None


def test_leer_distingue_un_fallo_de_base_de_una_conversacion_ajena(base_rota):
    servicio = ChatService()

    with pytest.raises(PersistenciaFallida):
        servicio.load_conversation_from_db("la-que-sea", user_id=ALICE)


def test_leer_una_conversacion_ajena_sigue_devolviendo_nada():
    """El 404 legítimo no se convierte en un 503."""
    servicio = ChatService()
    conv = servicio.create_conversation(user_id=ALICE)

    otra_cuenta = str(uuid.uuid4())
    assert servicio.load_conversation_from_db(conv.id, user_id=otra_cuenta) is None


def test_borrar_no_dice_borrada_si_no_borro_nada():
    servicio = ChatService()
    conv = servicio.create_conversation(user_id=ALICE)

    otra_cuenta = str(uuid.uuid4())
    assert servicio.delete_conversation(conv.id, user_id=otra_cuenta) is False
    assert servicio.delete_conversation(conv.id, user_id=ALICE) is True


def test_borrar_con_la_base_rota_no_se_declara_exitoso(base_rota):
    servicio = ChatService()

    with pytest.raises(PersistenciaFallida):
        servicio.delete_conversation("la-que-sea", user_id=ALICE)


def test_un_turno_que_no_se_guarda_deja_la_conversacion_marcada(monkeypatch):
    """`_persist_conv` no puede estallar: el modelo ya contestó. Pero lo dice."""
    servicio = ChatService()
    conv = servicio.create_conversation(user_id=ALICE)

    def _explota(*_a, **_kw):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(memory_store, "_get_conn", _explota)

    conv.add_message("user", "una pregunta cualquiera sobre la aspirina")
    servicio._persist_conv(conv)

    assert conv.persistencia_degradada
    assert "guardar" in servicio.aviso_de_persistencia(conv).lower()


def test_una_conversacion_sana_no_avisa_de_nada():
    servicio = ChatService()
    conv = servicio.create_conversation(user_id=ALICE)
    conv.add_message("user", "una pregunta cualquiera sobre la aspirina")
    servicio._persist_conv(conv)

    assert not conv.persistencia_degradada
    assert servicio.aviso_de_persistencia(conv) == ""


def test_el_indice_de_busqueda_no_tumba_el_turno(monkeypatch):
    """Un fallo del FTS degrada la búsqueda, no la conversación."""
    servicio = ChatService()
    conv = servicio.create_conversation(user_id=ALICE)
    conv.add_message("user", "una pregunta cualquiera sobre la aspirina")

    def _explota(*_a, **_kw):
        raise sqlite3.OperationalError("fts5 corrupto")

    monkeypatch.setattr(memory_store, "index_chat_message", _explota)

    servicio._persist_conv(conv)

    assert not conv.persistencia_degradada
    assert memory_store.load_conversation(conv.id, user_id=ALICE) is not None
