"""Fuga por el índice de búsqueda — la memoria de MolChat no tenía dueño.

MOLCHAT-BE-004 puso `user_id` en `conversations` y cerró la fuga por la lista de
conversaciones. Dejó anotada una limitación que nunca se auditó: `ai_catalog`,
`ai_details` y el índice FTS5 `engram_chat` viven en el mismo `ai_memory.db`, no
tienen dimensión de cuenta, y **reintroducen por otra vía exactamente la misma
fuga**.

La vía es peor que un listado, porque no hace falta que nadie pida nada: cada
turno, `_prepare_messages_with_context` consultaba `search_chat_history` sin
filtro y metía en el prompt de una cuenta los mensajes de otra. Y
`build_context_for_llm` hacía lo propio con el catálogo de evaluaciones.

Regla, la misma que D-05 y D-07: sin identidad no se lee nada, y las filas
anteriores a la columna no se le asignan a nadie por suposición — sólo las ve la
cuenta invitada, que es quien hereda.
"""

from __future__ import annotations

import sqlite3
import uuid

import pytest

from services.ai import memory_store

ALICE = str(uuid.uuid4())
BOB = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def base_aislada(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_store, "_DB_PATH", tmp_path / "ai_memory.db")
    yield


@pytest.fixture
def dos_cuentas_con_datos():
    memory_store.store_evaluation(
        molecule_id="mol-de-alice",
        smiles="CC(=O)Oc1ccccc1C(=O)O",
        target_pdb="7E2Y",
        affinity=-8.1,
        score=71.0,
        summary="aspirina de alice",
        user_id=ALICE,
    )
    memory_store.store_evaluation(
        molecule_id="mol-de-bob",
        smiles="CN1C=NC2=C1C(=O)N(C)C(=O)N2C",
        target_pdb="7E2Y",
        affinity=-9.4,
        score=88.0,
        summary="cafeina de bob",
        user_id=BOB,
    )


def test_el_catalogo_solo_devuelve_lo_de_la_cuenta(dos_cuentas_con_datos):
    de_alice = memory_store.get_last_evaluations(n=10, user_id=ALICE)

    assert [e["molecule_id"] for e in de_alice] == ["mol-de-alice"]


def test_el_contexto_del_llm_no_lleva_moleculas_ajenas(dos_cuentas_con_datos):
    contexto = memory_store.build_context_for_llm(user_id=ALICE)

    assert "aspirina de alice" in contexto or "CC(=O)Oc1ccccc1C(=O)O" in contexto
    assert "cafeina de bob" not in contexto
    assert "CN1C=NC2=C1C(=O)N(C)C(=O)N2C" not in contexto


def test_sin_identidad_el_contexto_esta_vacio(dos_cuentas_con_datos):
    """D-05: no hay una cuenta por defecto a la que caer."""
    assert memory_store.build_context_for_llm(user_id=None) == ""
    assert memory_store.get_last_evaluations(n=10, user_id=None) == []


def test_el_detalle_de_una_molecula_ajena_no_se_lee(dos_cuentas_con_datos):
    assert memory_store.get_full_evaluation("mol-de-bob", user_id=ALICE) is None
    assert memory_store.get_full_evaluation("mol-de-bob", user_id=BOB) is not None


def test_el_ranking_por_target_no_mezcla_cuentas(dos_cuentas_con_datos):
    top = memory_store.get_top_by_target("7E2Y", n=10, user_id=ALICE)

    assert [t["molecule_id"] for t in top] == ["mol-de-alice"]


def test_la_cuenta_de_evaluaciones_es_de_la_cuenta(dos_cuentas_con_datos):
    assert memory_store.get_evaluation_count(user_id=ALICE) == 1
    assert memory_store.get_evaluation_count(user_id=BOB) == 1
    assert memory_store.get_evaluation_count(user_id=None) == 0


def test_el_indice_fts_no_devuelve_mensajes_de_otra_cuenta():
    memory_store.index_chat_message(
        "conv-alice", "user", "quiero evaluar la aspirina contra 7E2Y", user_id=ALICE
    )
    memory_store.index_chat_message(
        "conv-bob", "user", "quiero evaluar la cafeina contra 7E2Y", user_id=BOB
    )

    de_alice = memory_store.search_chat_history("evaluar aspirina cafeina", user_id=ALICE)

    assert de_alice, "la cuenta sí debe encontrar lo suyo"
    assert all(r["conv_id"] == "conv-alice" for r in de_alice)
    assert not any("cafeina" in r["content"] for r in de_alice)


def test_sin_identidad_el_indice_no_devuelve_nada():
    memory_store.index_chat_message(
        "conv-alice", "user", "quiero evaluar la aspirina contra 7E2Y", user_id=ALICE
    )

    assert memory_store.search_chat_history("evaluar aspirina", user_id=None) == []


def test_lo_heredado_solo_lo_ve_el_invitado():
    """D-07: las filas anteriores a la columna no se le asignan a nadie."""
    memory_store.store_evaluation(
        molecule_id="mol-heredada",
        smiles="CCO",
        target_pdb="7E2Y",
        affinity=-4.0,
        score=30.0,
        summary="anterior a las cuentas",
        user_id=None,
    )
    memory_store.index_chat_message(
        "conv-heredada", "user", "un mensaje anterior a las cuentas", user_id=None
    )

    assert memory_store.get_last_evaluations(n=10, user_id=ALICE) == []
    heredadas = memory_store.get_last_evaluations(
        n=10, user_id=ALICE, incluir_heredadas=True
    )
    assert [e["molecule_id"] for e in heredadas] == ["mol-heredada"]

    assert memory_store.search_chat_history("mensaje anterior", user_id=ALICE) == []
    assert memory_store.search_chat_history(
        "mensaje anterior", user_id=ALICE, incluir_heredadas=True
    )


def test_el_indice_anterior_a_la_columna_se_migra_sin_perder_nada(tmp_path):
    """La tabla FTS5 no admite ALTER: se reconstruye, y lo viejo queda heredado."""
    conn = sqlite3.connect(str(memory_store._DB_PATH))
    conn.execute(
        "CREATE VIRTUAL TABLE engram_chat USING fts5("
        "content, role, conv_id UNINDEXED, tokenize='unicode61')"
    )
    conn.execute(
        "INSERT INTO engram_chat(content, role, conv_id) VALUES (?, ?, ?)",
        ("un mensaje de la epoca sin cuentas", "user", "conv-vieja"),
    )
    conn.commit()
    conn.close()

    memory_store.init_engram_db()

    columnas = memory_store._columnas_de("engram_chat")
    assert "user_id" in columnas

    assert memory_store.search_chat_history("mensaje epoca", user_id=ALICE) == []
    heredadas = memory_store.search_chat_history(
        "mensaje epoca", user_id=ALICE, incluir_heredadas=True
    )
    assert len(heredadas) == 1
    assert heredadas[0]["conv_id"] == "conv-vieja"


def test_el_catalogo_anterior_a_la_columna_se_migra(tmp_path):
    conn = sqlite3.connect(str(memory_store._DB_PATH))
    conn.execute(
        "CREATE TABLE ai_catalog (molecule_id TEXT PRIMARY KEY, smiles TEXT NOT NULL, "
        "target_pdb TEXT NOT NULL, affinity REAL, score REAL, summary TEXT, "
        "n_hotspots INTEGER DEFAULT 0, created_at REAL)"
    )
    conn.execute(
        "INSERT INTO ai_catalog(molecule_id, smiles, target_pdb, affinity, score, "
        "summary, created_at) VALUES ('vieja', 'CCO', '7E2Y', -4.0, 30.0, 'vieja', 1.0)"
    )
    conn.commit()
    conn.close()

    memory_store.init_db()

    assert "user_id" in memory_store._columnas_de("ai_catalog")
    assert memory_store.get_last_evaluations(n=10, user_id=ALICE) == []
    assert memory_store.get_last_evaluations(
        n=10, user_id=ALICE, incluir_heredadas=True
    )


def test_el_turno_no_inyecta_el_historial_de_otra_cuenta(monkeypatch):
    """La fuga real: el prompt de una cuenta llevaba mensajes de otra."""
    from services.ai.chat_service import ChatService

    memory_store.index_chat_message(
        "conv-bob", "user", "la cafeina de bob contra el receptor 7E2Y", user_id=BOB
    )
    memory_store.index_chat_message(
        "conv-alice", "user", "la aspirina de alice contra el receptor 7E2Y", user_id=ALICE
    )

    servicio = ChatService()
    conv = servicio.create_conversation(user_id=ALICE)

    mensajes = servicio._prepare_messages_with_context(
        conv,
        "que sabes de la cafeina y la aspirina contra el receptor 7E2Y",
        "",
        "",
        include_tools=False,
        include_engram=True,
    )

    entero = "\n".join(m.get("content", "") for m in mensajes)
    assert "la cafeina de bob" not in entero
    # Y el filtro no puede cerrarse por la vía fácil de no buscar nada: la
    # cuenta sigue viendo su propio historial.
    assert "la aspirina de alice" in entero
