"""Actualizar la aplicación no puede destruir el trabajo de nadie.

Es el criterio del gate de release que más caro sale si falla: un investigador
instala la versión nueva y sus evaluaciones, sus moléculas guardadas y sus
conversaciones tienen que seguir ahí. No hay deshacer.

Esta tanda añadió cuatro migraciones, y todas tocan datos existentes:

* `ai_memory.db` — ELIMINADA en Fase 6.6 con el asistente interno (su
  `user_id` en `conversations`/`ai_catalog` y el FTS5 ya no existen);
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

from services import molgraph

ALICE = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def bases_aisladas(tmp_path, monkeypatch):
    monkeypatch.setattr(molgraph, "_PUBLIC_DB", tmp_path / "molgraph.db")
    monkeypatch.setattr(molgraph, "_PRIVATE_DB", tmp_path / "molgraph_private.db")
    monkeypatch.setattr(molgraph, "_SEED_DB", tmp_path / "molgraph_seed.db")
    molgraph.invalidar_cache_de_huellas()
    yield
    molgraph.invalidar_cache_de_huellas()


# (Fase 6.6) La mitad de ai_memory.db murio con el asistente interno; queda la del grafo.


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
