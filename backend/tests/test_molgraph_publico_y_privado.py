"""MOLCHAT-BE-009 / D-10 — el grafo público no es la memoria de nadie.

`molgraph.db` era un solo archivo compartido por todas las cuentas de la
máquina. `queue_handler` escribía ahí cada evaluación —de quien fuera— y ocho
herramientas de MolChat lo leían. Era la fuga que MOLCHAT-BE-004 cerró, por un
cuarto almacén.

Y no bastaba con filtrar la lectura, que es la corrección aparente: el nodo de
molécula tenía id `mol_<smiles>`, **compartido entre cuentas**, y
`add_evaluation_node` sobrescribía sus propiedades con la última evaluación. Con
sólo filtrar, una cuenta seguiría pisando el score de otra y encima sin que se
viera: el dato **mal** en vez de sólo compartido.

La arquitectura que fija esta prueba:

* el corpus público —el `molgraph_seed.db` que el instalador copia— es
  **inmutable**: nadie vuelve a escribir en él;
* cada cuenta tiene su propio almacén de nodos, aristas, huellas y scores;
* la lectura **compone** las dos fuentes, y la escritura sólo puede tocar la
  privada, porque la composición es una vista y una vista no acepta escrituras;
* lo que había en el archivo vivo y **no** está en el seed lo produjo alguien en
  esta máquina y no se sabe quién: queda heredado, sin dueño, y sólo lo ve la
  cuenta invitada (mismo criterio que D-07).
"""

from __future__ import annotations

import sqlite3
import uuid

import pytest

from services.ai import molgraph

ALICE = str(uuid.uuid4())
BOB = str(uuid.uuid4())

ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"
CAFEINA = "CN1C=NC2=C1C(=O)N(C)C(=O)N2C"


@pytest.fixture(autouse=True)
def grafo_aislado(tmp_path, monkeypatch):
    """Corpus y almacén privado propios, y la caché de huellas limpia."""
    monkeypatch.setattr(molgraph, "_PUBLIC_DB", tmp_path / "molgraph.db")
    monkeypatch.setattr(molgraph, "_PRIVATE_DB", tmp_path / "molgraph_private.db")
    monkeypatch.setattr(molgraph, "_SEED_DB", tmp_path / "molgraph_seed.db")
    molgraph.invalidar_cache_de_huellas()
    yield
    molgraph.invalidar_cache_de_huellas()


def _corpus_con(nodos: list[tuple[str, str, str]]) -> None:
    """Escribe un corpus público mínimo y su copia como seed."""
    for destino in (molgraph._PUBLIC_DB, molgraph._SEED_DB):
        destino.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(destino))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS mol_nodes ("
            "id TEXT PRIMARY KEY, type TEXT NOT NULL, name TEXT NOT NULL, "
            "smiles TEXT, target_pdb TEXT, properties_json TEXT, created_at REAL NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS mol_edges ("
            "id TEXT PRIMARY KEY, source_id TEXT NOT NULL, target_id TEXT NOT NULL, "
            "relation TEXT NOT NULL, weight REAL DEFAULT 1.0, metadata_json TEXT, "
            "created_at REAL NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS mol_fingerprints ("
            "node_id TEXT PRIMARY KEY, fp_blob BLOB NOT NULL)"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS molgraph_fts USING fts5("
            "node_id UNINDEXED, name, type, properties_text, tokenize='unicode61')"
        )
        for node_id, nombre, smiles in nodos:
            conn.execute(
                "INSERT OR REPLACE INTO mol_nodes VALUES(?,?,?,?,?,?,?)",
                (node_id, "molecule", nombre, smiles, None, '{"score": 50}', 1.0),
            )
            conn.execute(
                "INSERT INTO molgraph_fts VALUES(?,?,?,?)",
                (node_id, nombre, "molecule", '{"score": 50}'),
            )
        conn.commit()
        conn.close()


class TestCorpusInmutable:
    def test_una_evaluacion_no_toca_el_corpus_publico(self):
        _corpus_con([("mol_publica", "publica", "CCO")])

        molgraph.add_evaluation_node(
            smiles=ASPIRINA, target_pdb="7E2Y", affinity=-8.1, score=71.0,
            user_id=ALICE,
        )

        publico = sqlite3.connect(str(molgraph._PUBLIC_DB))
        ids = {r[0] for r in publico.execute("SELECT id FROM mol_nodes")}
        publico.close()

        assert ids == {"mol_publica"}, "el corpus público tiene que quedarse como estaba"

    def test_escribir_sin_cuenta_es_un_error_declarado(self):
        _corpus_con([])

        with pytest.raises(molgraph.SinCuenta):
            molgraph.add_evaluation_node(
                smiles=ASPIRINA, target_pdb="7E2Y", affinity=-8.1, score=71.0,
                user_id=None,
            )

    def test_la_composicion_no_acepta_escrituras(self):
        """La vista es de sólo lectura por construcción, no por convención."""
        _corpus_con([("mol_publica", "publica", "CCO")])

        with molgraph._grafo(user_id=ALICE) as conn:
            with pytest.raises(sqlite3.OperationalError):
                conn.execute(
                    "INSERT INTO mol_nodes VALUES('x','molecule','x','CCO',NULL,'{}',1.0)"
                )


class TestDosCuentas:
    def _dos_evaluaciones(self):
        _corpus_con([("mol_publica", "publica", "CCO")])
        molgraph.add_evaluation_node(
            smiles=ASPIRINA, target_pdb="7E2Y", affinity=-8.1, score=71.0, user_id=ALICE
        )
        molgraph.add_evaluation_node(
            smiles=CAFEINA, target_pdb="7E2Y", affinity=-9.4, score=88.0, user_id=BOB
        )

    def test_el_ranking_no_mezcla_cuentas(self):
        self._dos_evaluaciones()

        de_alice = {m["smiles"] for m in molgraph.get_top_molecules(limit=50, user_id=ALICE)}
        de_bob = {m["smiles"] for m in molgraph.get_top_molecules(limit=50, user_id=BOB)}

        assert ASPIRINA in de_alice and CAFEINA not in de_alice
        assert CAFEINA in de_bob and ASPIRINA not in de_bob

    def test_las_dos_cuentas_ven_el_corpus_publico(self):
        self._dos_evaluaciones()

        for cuenta in (ALICE, BOB):
            smiles = {m["smiles"] for m in molgraph.get_top_molecules(limit=50, user_id=cuenta)}
            assert "CCO" in smiles, "el corpus es de todos; es su razón de ser"

    def test_una_cuenta_no_pisa_el_score_de_la_otra(self):
        """El fallo que un filtro de lectura NO habría arreglado."""
        _corpus_con([])
        molgraph.add_evaluation_node(
            smiles=ASPIRINA, target_pdb="7E2Y", affinity=-8.1, score=71.0, user_id=ALICE
        )
        molgraph.add_evaluation_node(
            smiles=ASPIRINA, target_pdb="7E2Y", affinity=-4.0, score=12.0, user_id=BOB
        )

        de_alice = molgraph.get_top_molecules(limit=50, user_id=ALICE)
        de_bob = molgraph.get_top_molecules(limit=50, user_id=BOB)

        assert [m["score"] for m in de_alice if m["smiles"] == ASPIRINA] == [71.0]
        assert [m["score"] for m in de_bob if m["smiles"] == ASPIRINA] == [12.0]

    def test_la_busqueda_de_texto_no_cruza_cuentas(self):
        self._dos_evaluaciones()

        de_alice = molgraph.query_fts("evaluacion", user_id=ALICE)
        nombres = " ".join(r["name"] for r in de_alice)

        assert CAFEINA[:12] not in nombres

    def test_los_vecinos_no_cruzan_cuentas(self):
        self._dos_evaluaciones()

        vecinos = molgraph.query_neighbors(ASPIRINA, user_id=BOB)

        assert all(v["smiles"] != ASPIRINA for v in vecinos)

    def test_la_similitud_no_cruza_cuentas(self):
        self._dos_evaluaciones()

        similares = molgraph.query_molgraph_similar(
            ASPIRINA, threshold=0.99, limit=10, user_id=BOB
        )

        assert all(s["smiles"] != ASPIRINA for s in similares)

    def test_la_sugerencia_no_ofrece_moleculas_de_otra_cuenta(self):
        self._dos_evaluaciones()

        from services.ai.tools import suggest_tools

        cargadas = suggest_tools._load_graph_molecules(user_id=BOB)
        smiles = {m["smiles"] for m in cargadas}

        assert ASPIRINA not in smiles
        assert CAFEINA in smiles

    def test_el_impacto_de_modificaciones_no_cruza_cuentas(self):
        _corpus_con([])
        molgraph.add_modification_edge(
            ASPIRINA, CAFEINA, modification="metilacion", delta_affinity=-1.3,
            user_id=ALICE,
        )

        assert molgraph.query_modification_impact(user_id=ALICE)
        assert molgraph.query_modification_impact(user_id=BOB) == []

    def test_sin_cuenta_solo_se_ve_el_corpus(self):
        self._dos_evaluaciones()

        smiles = {m["smiles"] for m in molgraph.get_top_molecules(limit=50, user_id=None)}

        assert smiles == {"CCO"}


class TestMigracionDeLoHeredado:
    def test_lo_que_no_esta_en_el_seed_queda_sin_dueno(self):
        """Se compara contra el seed: no se adjudica propietario por suposición."""
        _corpus_con([("mol_publica", "publica", "CCO")])

        # Una evaluación anterior a esta arquitectura, escrita directamente en
        # el archivo vivo por quien fuera.
        vivo = sqlite3.connect(str(molgraph._PUBLIC_DB))
        vivo.execute(
            "INSERT INTO mol_nodes VALUES('mol_heredada','molecule','heredada',"
            "'CCC',NULL,'{\"score\": 90}',2.0)"
        )
        vivo.commit()
        vivo.close()

        molgraph.init_graph()

        publico = sqlite3.connect(str(molgraph._PUBLIC_DB))
        ids = {r[0] for r in publico.execute("SELECT id FROM mol_nodes")}
        publico.close()
        assert ids == {"mol_publica"}, "el corpus vuelve a ser exactamente el seed"

        de_alice = {m["smiles"] for m in molgraph.get_top_molecules(limit=50, user_id=ALICE)}
        assert "CCC" not in de_alice, "lo heredado no es de nadie"

        del_invitado = {
            m["smiles"]
            for m in molgraph.get_top_molecules(
                limit=50, user_id=ALICE, incluir_heredadas=True
            )
        }
        assert "CCC" in del_invitado, "el invitado sí hereda (D-07)"

    def test_la_migracion_es_idempotente(self):
        _corpus_con([("mol_publica", "publica", "CCO")])
        vivo = sqlite3.connect(str(molgraph._PUBLIC_DB))
        vivo.execute(
            "INSERT INTO mol_nodes VALUES('mol_heredada','molecule','heredada',"
            "'CCC',NULL,'{\"score\": 90}',2.0)"
        )
        vivo.commit()
        vivo.close()

        molgraph.init_graph()
        molgraph.init_graph()
        molgraph.init_graph()

        heredadas = molgraph.get_top_molecules(
            limit=50, user_id=ALICE, incluir_heredadas=True
        )
        assert [m["smiles"] for m in heredadas].count("CCC") == 1

    def test_sin_seed_no_se_declara_publico_nada(self, caplog):
        """Sin con qué comparar, lo conservador es no adjudicar."""
        _corpus_con([("mol_publica", "publica", "CCO")])
        molgraph._SEED_DB.unlink()

        molgraph.init_graph()

        de_alice = {m["smiles"] for m in molgraph.get_top_molecules(limit=50, user_id=ALICE)}
        assert de_alice == set(), "sin seed no se puede afirmar que algo sea corpus"

        del_invitado = {
            m["smiles"]
            for m in molgraph.get_top_molecules(
                limit=50, user_id=ALICE, incluir_heredadas=True
            )
        }
        assert "CCO" in del_invitado


class TestElPipelineEscribeConDueno:
    def test_queue_handler_pasa_la_cuenta_al_grafo(self):
        import inspect

        from services.docking import queue_handler

        fuente = inspect.getsource(queue_handler)
        posicion = fuente.index("add_evaluation_node(")
        fragmento = fuente[posicion : posicion + 800]

        assert "user_id=" in fragmento, (
            "el pipeline escribe en el grafo: tiene que decir de quién es la corrida"
        )
