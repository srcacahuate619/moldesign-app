"""MOLCHAT-BE-004 y MOLCHAT-BE-006 — la conversación tiene dueño.

El aislamiento faltaba en las cuatro capas a la vez: el objeto `Conversation` no
tenía `user_id`, `ChatService._conversations` y `_active_conv_id` eran atributos
de **clase** sobre un singleton de proceso, la tabla `conversations` no tenía
columna de usuario, y ninguna de las cuatro operaciones recibía identidad.

Y `ai_memory.db` vive en `~/MolDesign/data/`: un único archivo para todas las
cuentas de la máquina. Dentro de cada conversación viaja `molecule_context`, así
que no era sólo el texto del chat — era el caso y la molécula de los que se
habló.

D-07 (decisión del propietario, 2026-08-30): las conversaciones anteriores a
esta columna quedan en `NULL` y **no se les asigna dueño por suposición** —mismo
criterio que con los sellos heredados de MOLDEX-SCI-001—. Se muestran a la
cuenta invitada `Desktop User`, coherente con D-05.
"""

from __future__ import annotations

import uuid

import pytest

from services.ai import memory_store
from services.ai.chat_service import ChatService

ALICE = str(uuid.uuid4())
BOB = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def base_aislada(tmp_path, monkeypatch):
    """Cada prueba usa su propia `ai_memory.db`."""
    monkeypatch.setattr(memory_store, "_DB_PATH", tmp_path / "ai_memory.db")
    yield


@pytest.fixture
def servicio():
    return ChatService()


# ── El esquema ───────────────────────────────────────────────────────────────


def test_la_tabla_de_conversaciones_tiene_columna_de_usuario():
    memory_store.init_conv_db()
    conn = memory_store._get_conn()
    columnas = {r[1] for r in conn.execute("PRAGMA table_info(conversations)")}
    conn.close()

    assert "user_id" in columnas


def test_una_base_anterior_recibe_la_columna_sin_perder_filas():
    """Migración aditiva sobre la base real, no sobre una recreada."""
    import sqlite3

    conn = sqlite3.connect(str(memory_store._DB_PATH))
    conn.execute(
        "CREATE TABLE conversations ("
        " conv_id TEXT PRIMARY KEY, messages_json TEXT NOT NULL DEFAULT '[]',"
        " summary TEXT DEFAULT '', molecule_context_json TEXT,"
        " created_at REAL NOT NULL, updated_at REAL NOT NULL)"
    )
    conn.execute(
        "INSERT INTO conversations VALUES ('vieja','[]','',NULL,1.0,1.0)"
    )
    conn.commit()
    conn.close()

    memory_store.init_conv_db()

    conn = memory_store._get_conn()
    fila = conn.execute(
        "SELECT conv_id, user_id FROM conversations WHERE conv_id='vieja'"
    ).fetchone()
    conn.close()

    assert fila[0] == "vieja"
    # Heredada: sin dueño, y no se le inventa uno.
    assert fila[1] is None


# ── El estado del servicio ───────────────────────────────────────────────────


def test_el_estado_no_se_comparte_entre_instancias():
    """Eran atributos de CLASE: dos instancias veían el mismo diccionario."""
    a, b = ChatService(), ChatService()
    a.create_conversation(user_id=ALICE)

    assert a._conversations is not b._conversations


def test_la_conversacion_activa_es_por_cuenta(servicio):
    de_alice = servicio.create_conversation(user_id=ALICE)
    de_bob = servicio.create_conversation(user_id=BOB)

    # Que Bob abra la suya no puede mover la de Alice.
    assert servicio.get_conversation(user_id=ALICE).id == de_alice.id
    assert servicio.get_conversation(user_id=BOB).id == de_bob.id


# ── El aislamiento ───────────────────────────────────────────────────────────


def test_una_cuenta_no_lista_las_conversaciones_de_otra(servicio):
    servicio.create_conversation(user_id=ALICE)

    ids_de_bob = {c["id"] for c in servicio.list_conversations(user_id=BOB)}

    assert ids_de_bob == set()


def test_una_cuenta_no_puede_leer_la_conversacion_de_otra(servicio):
    de_alice = servicio.create_conversation(user_id=ALICE)

    assert servicio.load_conversation_from_db(de_alice.id, user_id=BOB) is None
    assert servicio.load_conversation_from_db(de_alice.id, user_id=ALICE) is not None


def test_una_cuenta_no_puede_borrar_la_conversacion_de_otra(servicio):
    de_alice = servicio.create_conversation(user_id=ALICE)

    servicio.delete_conversation(de_alice.id, user_id=BOB)

    # Sigue ahí para su dueña.
    assert servicio.load_conversation_from_db(de_alice.id, user_id=ALICE) is not None


def test_leer_una_conversacion_ajena_no_mueve_la_activa_de_nadie(servicio):
    """MOLCHAT-BE-006: `load_conversation_from_db` reasignaba la activa global."""
    de_alice = servicio.create_conversation(user_id=ALICE)
    de_bob = servicio.create_conversation(user_id=BOB)

    servicio.load_conversation_from_db(de_alice.id, user_id=BOB)

    assert servicio.get_conversation(user_id=ALICE).id == de_alice.id
    assert servicio.get_conversation(user_id=BOB).id == de_bob.id


# ── D-07: las heredadas ──────────────────────────────────────────────────────


def _insertar_heredada(conv_id: str = "heredada"):
    memory_store.init_conv_db()
    conn = memory_store._get_conn()
    conn.execute(
        "INSERT INTO conversations (conv_id, messages_json, summary,"
        " molecule_context_json, created_at, updated_at, user_id)"
        " VALUES (?,'[]','',NULL,1.0,1.0,NULL)",
        (conv_id,),
    )
    conn.commit()
    conn.close()


def test_una_conversacion_heredada_no_es_de_una_cuenta_cualquiera(servicio):
    _insertar_heredada()

    assert servicio.load_conversation_from_db("heredada", user_id=ALICE) is None
    assert "heredada" not in {c["id"] for c in servicio.list_conversations(user_id=ALICE)}


def test_una_conversacion_heredada_la_ve_el_invitado(servicio):
    """D-07 opción (b): el invitado del escritorio las hereda."""
    _insertar_heredada()

    encontrada = servicio.load_conversation_from_db(
        "heredada", user_id=BOB, incluir_heredadas=True
    )

    assert encontrada is not None
    assert "heredada" in {
        c["id"]
        for c in servicio.list_conversations(user_id=BOB, incluir_heredadas=True)
    }


# ── D-07 en el router: quién es «el invitado» ────────────────────────────────


def test_solo_la_cuenta_invitada_hereda():
    """La decisión no puede depender de una cadena repetida en cada capa."""
    from types import SimpleNamespace

    from core.identity import GUEST_EMAIL, es_invitado

    assert es_invitado(SimpleNamespace(email=GUEST_EMAIL)) is True
    assert es_invitado(SimpleNamespace(email="investigadora@example.org")) is False
    assert es_invitado(SimpleNamespace()) is False
    assert es_invitado(None) is False


def test_el_correo_del_invitado_es_el_que_crea_el_auto_login():
    """Si `/auth/desktop-login` cambia de correo, esto lo detecta."""
    import inspect

    from api.routers import auth
    from core.identity import GUEST_EMAIL

    fuente = inspect.getsource(auth.desktop_auto_login)

    assert GUEST_EMAIL in fuente
