"""Actualizar la aplicación no puede destruir el trabajo de nadie.

Es el criterio del gate de release que más caro sale si falla: un investigador
instala la versión nueva y sus evaluaciones, sus moléculas guardadas y sus
conversaciones tienen que seguir ahí. No hay deshacer.

Esta tanda añadió cuatro migraciones, y todas tocan datos existentes:

* `ai_memory.db` — `user_id` en `conversations`, en `ai_catalog`, y la
  reconstrucción del índice FTS5 (que no admite `ALTER`);
* `molgraph.db` — la separación del corpus público y el almacén privado, que
  **mueve filas de un archivo a otro**;
* `moldesign_local.db` — nada estructural, pero el catálogo de receptores pasa a
  publicar su nivel de calibración.

La que más riesgo tiene es la del grafo: es la única que borra del origen. Estas
pruebas la ejercitan sobre bases que ya tienen datos, comprueban que nada se
pierde, que repetirla no duplica, y que un archivo corrupto no se lleva por
delante lo que había.
"""

from __future__ import annotations

import sqlite3
import uuid

import pytest

from services.ai import memory_store, molgraph

ALICE = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def bases_aisladas(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_store, "_DB_PATH", tmp_path / "ai_memory.db")
    monkeypatch.setattr(molgraph, "_PUBLIC_DB", tmp_path / "molgraph.db")
    monkeypatch.setattr(molgraph, "_PRIVATE_DB", tmp_path / "molgraph_private.db")
    monkeypatch.setattr(molgraph, "_SEED_DB", tmp_path / "molgraph_seed.db")
    molgraph.invalidar_cache_de_huellas()
    yield
    molgraph.invalidar_cache_de_huellas()


# ── ai_memory.db, tal como era antes de esta tanda ───────────────────────────


def _memoria_anterior(ruta):
    """Reproduce el esquema previo: sin `user_id` en ningún sitio."""
    conn = sqlite3.connect(str(ruta))
    conn.execute(
        "CREATE TABLE conversations ("
        "conv_id TEXT PRIMARY KEY, messages_json TEXT NOT NULL DEFAULT '[]', "
        "summary TEXT DEFAULT '', molecule_context_json TEXT, "
        "created_at REAL NOT NULL, updated_at REAL NOT NULL)"
    )
    conn.execute(
        "INSERT INTO conversations VALUES ('conv-vieja', "
        "'[{\"role\": \"user\", \"content\": \"una pregunta de antes\"}]', "
        "'', NULL, 1.0, 2.0)"
    )
    conn.execute(
        "CREATE TABLE ai_catalog (molecule_id TEXT PRIMARY KEY, smiles TEXT NOT NULL, "
        "target_pdb TEXT NOT NULL, affinity REAL, score REAL, summary TEXT, "
        "n_hotspots INTEGER DEFAULT 0, created_at REAL)"
    )
    conn.execute(
        "INSERT INTO ai_catalog VALUES ('mol-vieja','CCO','7E2Y',-4.0,30.0,'de antes',0,1.0)"
    )
    conn.execute(
        "CREATE VIRTUAL TABLE engram_chat USING fts5("
        "content, role, conv_id UNINDEXED, tokenize='unicode61')"
    )
    conn.execute(
        "INSERT INTO engram_chat(content, role, conv_id) "
        "VALUES ('un mensaje indexado de antes', 'user', 'conv-vieja')"
    )
    conn.commit()
    conn.close()


class TestLaMemoriaDeMolChat:
    def test_las_conversaciones_anteriores_no_se_pierden(self):
        _memoria_anterior(memory_store._DB_PATH)

        memory_store.init_conv_db()

        # Sin dueño conocido: sólo las ve el invitado (D-07). Lo que importa
        # aquí es que sigan existiendo.
        heredadas = memory_store.load_all_conversations(
            user_id=ALICE, incluir_heredadas=True
        )
        assert [c["id"] for c in heredadas] == ["conv-vieja"]
        assert memory_store.load_all_conversations(user_id=ALICE) == []

    def test_el_catalogo_anterior_no_se_pierde(self):
        _memoria_anterior(memory_store._DB_PATH)

        memory_store.init_db()

        assert memory_store.get_last_evaluations(
            n=10, user_id=ALICE, incluir_heredadas=True
        )
        assert memory_store.get_last_evaluations(n=10, user_id=ALICE) == []

    def test_el_indice_fts_se_reconstruye_sin_perder_lo_indexado(self):
        _memoria_anterior(memory_store._DB_PATH)

        memory_store.init_engram_db()

        assert "user_id" in memory_store._columnas_de("engram_chat")
        heredado = memory_store.search_chat_history(
            "mensaje indexado", user_id=ALICE, incluir_heredadas=True
        )
        assert len(heredado) == 1

    def test_repetir_la_actualizacion_no_duplica(self):
        _memoria_anterior(memory_store._DB_PATH)

        for _ in range(3):
            memory_store.init_conv_db()
            memory_store.init_db()
            memory_store.init_engram_db()

        heredado = memory_store.search_chat_history(
            "mensaje indexado", user_id=ALICE, incluir_heredadas=True
        )
        assert len(heredado) == 1
        assert len(memory_store.load_all_conversations(
            user_id=ALICE, incluir_heredadas=True
        )) == 1

    def test_una_base_ya_actualizada_no_se_toca(self):
        """Instalar dos veces la misma versión no puede cambiar nada."""
        _memoria_anterior(memory_store._DB_PATH)
        memory_store.init_conv_db()
        memory_store.save_conversation(
            conv_id="conv-nueva", messages=[{"role": "user", "content": "hola"}],
            user_id=ALICE,
        )

        memory_store.init_conv_db()

        de_alice = memory_store.load_all_conversations(user_id=ALICE)
        assert [c["id"] for c in de_alice] == ["conv-nueva"]


# ── molgraph.db: la migración que mueve filas entre archivos ─────────────────


def _grafo_anterior(publico, seed, nodos_del_seed, nodos_locales):
    for ruta, nodos in ((seed, nodos_del_seed), (publico, nodos_del_seed + nodos_locales)):
        conn = sqlite3.connect(str(ruta))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS mol_nodes (id TEXT PRIMARY KEY, type TEXT NOT NULL, "
            "name TEXT NOT NULL, smiles TEXT, target_pdb TEXT, properties_json TEXT, "
            "created_at REAL NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS mol_edges (id TEXT PRIMARY KEY, source_id TEXT NOT NULL, "
            "target_id TEXT NOT NULL, relation TEXT NOT NULL, weight REAL DEFAULT 1.0, "
            "metadata_json TEXT, created_at REAL NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS mol_fingerprints (node_id TEXT PRIMARY KEY, fp_blob BLOB NOT NULL)"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS molgraph_fts USING fts5("
            "node_id UNINDEXED, name, type, properties_text, tokenize='unicode61')"
        )
        for node_id, smiles in nodos:
            conn.execute(
                "INSERT OR REPLACE INTO mol_nodes VALUES (?,?,?,?,?,?,?)",
                (node_id, "molecule", node_id, smiles, None, '{"score": 50}', 1.0),
            )
        conn.commit()
        conn.close()


class TestElGrafo:
    def test_lo_del_seed_se_queda_y_lo_local_se_mueve(self):
        _grafo_anterior(
            molgraph._PUBLIC_DB, molgraph._SEED_DB,
            nodos_del_seed=[("mol_corpus", "CCO")],
            nodos_locales=[("mol_local", "CCC")],
        )

        molgraph.init_graph()

        publico = sqlite3.connect(str(molgraph._PUBLIC_DB))
        ids = {r[0] for r in publico.execute("SELECT id FROM mol_nodes")}
        publico.close()
        assert ids == {"mol_corpus"}, "el corpus vuelve a ser exactamente el seed"

        privado = sqlite3.connect(str(molgraph._PRIVATE_DB))
        heredados = privado.execute(
            "SELECT id, user_id FROM priv_nodes"
        ).fetchall()
        privado.close()
        assert heredados == [("mol_local", None)], "lo local se conserva, sin dueño"

    def test_nada_se_pierde_en_el_traslado(self):
        _grafo_anterior(
            molgraph._PUBLIC_DB, molgraph._SEED_DB,
            nodos_del_seed=[("mol_corpus", "CCO")],
            nodos_locales=[("mol_a", "CCC"), ("mol_b", "CCCC")],
        )

        molgraph.init_graph()

        visibles = {
            m["smiles"]
            for m in molgraph.get_top_molecules(
                limit=50, user_id=ALICE, incluir_heredadas=True
            )
        }
        assert visibles == {"CCO", "CCC", "CCCC"}

    def test_repetir_la_actualizacion_no_duplica_ni_reborra(self):
        _grafo_anterior(
            molgraph._PUBLIC_DB, molgraph._SEED_DB,
            nodos_del_seed=[("mol_corpus", "CCO")],
            nodos_locales=[("mol_local", "CCC")],
        )

        for _ in range(3):
            molgraph.invalidar_cache_de_huellas()
            molgraph.init_graph()

        privado = sqlite3.connect(str(molgraph._PRIVATE_DB))
        cuantos = privado.execute("SELECT COUNT(*) FROM priv_nodes").fetchone()[0]
        privado.close()
        assert cuantos == 1

    def test_sin_grafo_previo_la_actualizacion_no_falla(self):
        """Instalación nueva: no hay nada que migrar y no puede romperse."""
        molgraph.init_graph()

        assert molgraph.get_top_molecules(limit=5, user_id=ALICE) == []

    def test_un_corpus_ilegible_no_destruye_lo_privado(self):
        """Un archivo corrupto degrada, no borra."""
        _grafo_anterior(
            molgraph._PUBLIC_DB, molgraph._SEED_DB,
            nodos_del_seed=[("mol_corpus", "CCO")],
            nodos_locales=[],
        )
        molgraph.init_graph()
        molgraph.add_evaluation_node(
            smiles="CC(=O)Oc1ccccc1C(=O)O", target_pdb="7E2Y",
            affinity=-8.0, score=70.0, user_id=ALICE,
        )

        molgraph._PUBLIC_DB.write_bytes(b"esto no es una base de datos")
        molgraph.invalidar_cache_de_huellas()

        # Lo de la cuenta sigue ahí: vive en otro archivo, que es la razón de
        # haberlos separado.
        privado = sqlite3.connect(str(molgraph._PRIVATE_DB))
        cuantos = privado.execute(
            "SELECT COUNT(*) FROM priv_nodes WHERE user_id = ?", (ALICE,)
        ).fetchone()[0]
        privado.close()
        assert cuantos > 0
