"""
services/ai/molgraph.py — MolGraph: Knowledge Graph Quimico de MolDesign.

Tecnologia propia. Nodos (moleculas, targets, evaluaciones) y aristas
(docking, similitud, relacion) en SQLite con FTS5. Reemplaza el formato
DENSE (2000 tokens) por queries precisas de ~60-100 tokens.

Arquitectura inspirada en CodeGraph, aplicada a quimica medicinal.
"""

from __future__ import annotations

import json
import os
import pickle
import sqlite3
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np

from utils.logger import get_logger

log = get_logger(__name__)

class SinCuenta(RuntimeError):
    """Se intentó escribir en el grafo sin saber de quién es lo que se escribe.

    MOLCHAT-BE-009. Antes esto no existía: cualquier escritura entraba en el
    archivo compartido de la máquina. Un nodo sin dueño no es «de todos», es un
    nodo que no se puede aislar, listar, ni retirar cuando su cuenta se va.
    """


def _directorio_de_datos() -> Path:
    """Dónde viven las bases del grafo.

    Bajo `MOLDESIGN_TESTING=1` **nunca** es el home del usuario. Es el mismo
    guard que ya protege `core.database`, y aquí hacía falta por la misma razón:
    una prueba que olvide aislar la ruta escribiría —y migraría— sobre los datos
    reales de quien ejecuta la suite. Pasó una vez; que no dependa de acordarse.
    """
    if os.environ.get("MOLDESIGN_TESTING") == "1":
        return Path(tempfile.gettempdir()) / "moldesign-tests" / "molgraph"
    return Path.home() / "MolDesign" / "data"


#: El corpus que el instalador copia en el primer arranque. Inmutable.
_PUBLIC_DB = _directorio_de_datos() / "molgraph.db"
#: Lo que produce cada cuenta. Es donde se escribe, siempre.
_PRIVATE_DB = _directorio_de_datos() / "molgraph_private.db"
#: La referencia con la que se distingue el corpus de lo que se produjo aquí.
_SEED_DB = Path(__file__).resolve().parents[3] / "data" / "molgraph_seed.db"

#: Compatibilidad: algunos módulos y pruebas antiguas leen `_DB_PATH`.
_DB_PATH = _PUBLIC_DB

#: Almacenes ya migrados, por ruta. No es un booleano de proceso a propósito:
#: las pruebas y una reconfiguración en caliente apuntan a otro archivo, y un
#: `True` global haría que la migración no corriera sobre el nuevo.
_migracion_hecha: set[str] = set()
_migracion_lock = __import__("threading").Lock()


def _clausula_de_dueno(user_id: str | None, incluir_heredadas: bool) -> tuple[str, list]:
    """Filtro de propiedad del almacén privado.

    `incluir_heredadas` sólo lo activa la cuenta invitada (D-07): las filas sin
    `user_id` son anteriores a que el grafo tuviera dueños y no se sabe de quién
    eran. Sin `user_id` la cláusula no empareja con nada, que es lo correcto:
    sin identidad se ve el corpus y nada más.
    """
    if incluir_heredadas:
        return "(user_id = ? OR user_id IS NULL)", [user_id]
    return "user_id = ?", [user_id]


def _crear_esquema_privado(conn: sqlite3.Connection) -> None:
    """Las tablas privadas se llaman distinto **a propósito**.

    Si se llamaran `mol_nodes` como las públicas, la vista de composición las
    ensombrecería y una escritura descuidada podría acabar en cualquiera de las
    dos. Con nombres distintos, escribir exige nombrar `priv_nodes`, y leer la
    composición exige la vista: no hay forma de confundirlas.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS priv_nodes (
            user_id TEXT,
            id TEXT NOT NULL,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            smiles TEXT,
            target_pdb TEXT,
            properties_json TEXT,
            created_at REAL NOT NULL,
            PRIMARY KEY (user_id, id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS priv_edges (
            user_id TEXT,
            id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relation TEXT NOT NULL,
            weight REAL DEFAULT 1.0,
            metadata_json TEXT,
            created_at REAL NOT NULL,
            PRIMARY KEY (user_id, id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS priv_fingerprints (
            user_id TEXT,
            node_id TEXT NOT NULL,
            fp_blob BLOB NOT NULL,
            PRIMARY KEY (user_id, node_id)
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS priv_fts USING fts5(
            node_id UNINDEXED,
            user_id UNINDEXED,
            name,
            type,
            properties_text,
            tokenize='unicode61'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_priv_nodes_user ON priv_nodes(user_id, type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_priv_nodes_smiles ON priv_nodes(user_id, smiles)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_priv_edges_src ON priv_edges(user_id, source_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_priv_edges_rel ON priv_edges(user_id, relation)")
    conn.commit()


def _conn_privada() -> sqlite3.Connection:
    _PRIVATE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_PRIVATE_DB))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _crear_esquema_privado(conn)
    return conn


def _ids_del_seed() -> set[str] | None:
    """Los nodos que vienen en el corpus distribuido. `None` si no hay seed."""
    if not _SEED_DB.exists():
        return None
    try:
        seed = sqlite3.connect(f"file:{_SEED_DB}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        return {fila[0] for fila in seed.execute("SELECT id FROM mol_nodes")}
    except sqlite3.Error:
        return None
    finally:
        seed.close()


def _migrar_lo_heredado() -> None:
    """Saca del corpus lo que no vino en el seed, sin adjudicarle propietario.

    Lo que está en el archivo vivo y **no** en el seed lo produjo alguien en esta
    máquina, y no se sabe quién. No se le asigna dueño por suposición —mismo
    criterio que D-07 y que MOLDEX-SCI-001—: pasa al almacén privado con
    `user_id NULL`, donde sólo lo ve la cuenta invitada.

    Sin seed no hay con qué comparar. Entonces **nada** se declara corpus: se
    hereda todo. Es la lectura conservadora — degrada la capacidad de sugerir
    sobre el corpus, pero no publica el trabajo de nadie.
    """
    clave = str(_PRIVATE_DB)
    with _migracion_lock:
        if clave in _migracion_hecha:
            return
        if not _PUBLIC_DB.exists():
            _migracion_hecha.add(clave)
            return

        del_seed = _ids_del_seed()
        if del_seed is None:
            log.warning(
                "molgraph_sin_seed",
                detalle=(
                    "no hay molgraph_seed.db con el que distinguir el corpus; "
                    "todo el grafo vivo se trata como heredado sin dueño"
                ),
                seed=str(_SEED_DB),
            )
            del_seed = set()

        publico = sqlite3.connect(str(_PUBLIC_DB))
        privado = _conn_privada()
        try:
            try:
                todos = publico.execute(
                    "SELECT id, type, name, smiles, target_pdb, properties_json, created_at "
                    "FROM mol_nodes"
                ).fetchall()
            except sqlite3.Error:
                _migracion_hecha.add(clave)
                return

            ajenos = [fila for fila in todos if fila[0] not in del_seed]
            if not ajenos:
                _migracion_hecha.add(clave)
                return

            ids_ajenos = {fila[0] for fila in ajenos}
            privado.executemany(
                "INSERT OR REPLACE INTO priv_nodes "
                "(user_id, id, type, name, smiles, target_pdb, properties_json, created_at) "
                "VALUES (NULL,?,?,?,?,?,?,?)",
                ajenos,
            )
            for fila in ajenos:
                privado.execute(
                    "INSERT INTO priv_fts(node_id, user_id, name, type, properties_text) "
                    "VALUES (?,NULL,?,?,?)",
                    (fila[0], fila[2], fila[1], (fila[5] or "")[:1000]),
                )

            try:
                aristas = publico.execute(
                    "SELECT id, source_id, target_id, relation, weight, metadata_json, created_at "
                    "FROM mol_edges"
                ).fetchall()
            except sqlite3.Error:
                aristas = []
            aristas_ajenas = [
                a for a in aristas if a[1] in ids_ajenos or a[2] in ids_ajenos
            ]
            if aristas_ajenas:
                privado.executemany(
                    "INSERT OR REPLACE INTO priv_edges "
                    "(user_id, id, source_id, target_id, relation, weight, metadata_json, created_at) "
                    "VALUES (NULL,?,?,?,?,?,?,?)",
                    aristas_ajenas,
                )

            try:
                huellas = publico.execute(
                    "SELECT node_id, fp_blob FROM mol_fingerprints WHERE node_id IN "
                    "(" + ",".join("?" * len(ids_ajenos)) + ")",
                    tuple(ids_ajenos),
                ).fetchall()
            except sqlite3.Error:
                huellas = []
            if huellas:
                privado.executemany(
                    "INSERT OR REPLACE INTO priv_fingerprints (user_id, node_id, fp_blob) "
                    "VALUES (NULL,?,?)",
                    huellas,
                )
            privado.commit()

            marcadores = ",".join("?" * len(ids_ajenos))
            publico.execute(
                f"DELETE FROM mol_nodes WHERE id IN ({marcadores})", tuple(ids_ajenos)
            )
            for tabla, columna in (("mol_fingerprints", "node_id"),):
                try:
                    publico.execute(
                        f"DELETE FROM {tabla} WHERE {columna} IN ({marcadores})",
                        tuple(ids_ajenos),
                    )
                except sqlite3.Error:
                    pass
            if aristas_ajenas:
                ids_aristas = tuple(a[0] for a in aristas_ajenas)
                try:
                    publico.execute(
                        "DELETE FROM mol_edges WHERE id IN ("
                        + ",".join("?" * len(ids_aristas))
                        + ")",
                        ids_aristas,
                    )
                except sqlite3.Error:
                    pass
            try:
                publico.execute(
                    f"DELETE FROM molgraph_fts WHERE node_id IN ({marcadores})",
                    tuple(ids_ajenos),
                )
            except sqlite3.Error:
                pass
            publico.commit()

            log.info(
                "molgraph_migrado_a_privado",
                nodos=len(ajenos),
                aristas=len(aristas_ajenas),
                motivo="anteriores a la separación corpus/privado, sin dueño conocido",
            )
        finally:
            publico.close()
            privado.close()
            _migracion_hecha.add(clave)


@contextmanager
def _grafo(user_id: str | None = None, incluir_heredadas: bool = False):
    """Abre el grafo **compuesto**: corpus público + almacén de esta cuenta.

    La composición son vistas de SQLite, y una vista con `UNION ALL` no acepta
    escrituras. Eso no es un detalle de implementación: es la garantía de que
    ninguna consulta de lectura pueda, por descuido, acabar escribiendo en el
    corpus compartido. Para escribir hay que nombrar `priv_nodes` a mano.

    La cuenta activa viaja en una tabla temporal —`sesion`— en vez de
    interpolarse en el SQL de la vista: una vista no acepta parámetros, y meter
    un identificador de usuario dentro del texto de la consulta es la clase de
    atajo que acaba siendo una inyección.
    """
    _migrar_lo_heredado()
    conn = _conn_privada()
    try:
        _PUBLIC_DB.parent.mkdir(parents=True, exist_ok=True)
        conn.execute("ATTACH DATABASE ? AS corpus", (str(_PUBLIC_DB),))
        try:
            corpus_tiene = {
                fila[0]
                for fila in conn.execute(
                    "SELECT name FROM corpus.sqlite_master WHERE type='table'"
                )
            }
        except sqlite3.Error:
            corpus_tiene = set()

        conn.execute("CREATE TEMP TABLE sesion (user_id TEXT, hereda INTEGER NOT NULL)")
        conn.execute(
            "INSERT INTO sesion (user_id, hereda) VALUES (?, ?)",
            (user_id, 1 if incluir_heredadas else 0),
        )

        # Sin cuenta no se lee memoria de nadie: sólo el corpus. Con cuenta, lo
        # suyo; y lo heredado únicamente si quien pregunta es el invitado.
        propiedad = (
            "((SELECT user_id FROM sesion) IS NOT NULL "
            " AND user_id = (SELECT user_id FROM sesion)) "
            "OR ((SELECT hereda FROM sesion) = 1 AND user_id IS NULL)"
        )

        def _union(vista: str, columnas: str, tabla_publica: str, tabla_privada: str) -> None:
            publica = (
                f"SELECT {columnas} FROM corpus.{tabla_publica} UNION ALL "
                if tabla_publica in corpus_tiene
                else ""
            )
            conn.execute(
                f"CREATE TEMP VIEW {vista} AS {publica}"
                f"SELECT {columnas} FROM {tabla_privada} WHERE {propiedad}"
            )

        _union(
            "mol_nodes",
            "id, type, name, smiles, target_pdb, properties_json, created_at",
            "mol_nodes",
            "priv_nodes",
        )
        _union(
            "mol_edges",
            "id, source_id, target_id, relation, weight, metadata_json, created_at",
            "mol_edges",
            "priv_edges",
        )
        _union(
            "mol_fingerprints",
            "node_id, fp_blob",
            "mol_fingerprints",
            "priv_fingerprints",
        )
        yield conn
    finally:
        conn.close()


def _escribir(user_id: str | None, *, permitir_sin_cuenta: bool = False):
    """Conexión de ESCRITURA. Sólo toca el almacén privado, nunca el corpus."""
    if user_id is None and not permitir_sin_cuenta:
        raise SinCuenta(
            "el grafo no acepta escrituras sin cuenta: un nodo sin dueño no se "
            "puede aislar, listar ni retirar cuando esa cuenta se va"
        )
    _migrar_lo_heredado()
    return _conn_privada()



# ── Cache de huellas en memoria, por cuenta ──────────────────────────────────
# Antes era un único diccionario de proceso: cargaba las huellas del archivo
# compartido y las servía a todas las cuentas. Con el grafo separado, la caché
# tiene que estar separada también, o la similitud de una cuenta se calcularía
# sobre las moléculas de otra.
_fp_cache: dict[tuple[str | None, bool], dict[str, Any]] = {}
_fp_cache_lock = __import__("threading").Lock()


def invalidar_cache_de_huellas() -> None:
    """Vacía la caché y el registro de migraciones.

    La usan las pruebas y cualquier cambio de almacén: si el proceso apunta a
    otro archivo, ni las huellas cargadas ni la migración ya hecha valen.
    """
    with _fp_cache_lock:
        _fp_cache.clear()
    with _migracion_lock:
        _migracion_hecha.clear()


def _load_fingerprint_cache(
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> dict[str, Any]:
    """Huellas visibles para esta cuenta: corpus público + lo suyo."""
    clave = (user_id, incluir_heredadas)
    cacheada = _fp_cache.get(clave)
    if cacheada is not None:
        return cacheada
    with _fp_cache_lock:
        cacheada = _fp_cache.get(clave)
        if cacheada is not None:
            return cacheada
        with _grafo(user_id, incluir_heredadas) as conn:
            rows = conn.execute(
                "SELECT n.id, f.fp_blob FROM mol_nodes n "
                "JOIN mol_fingerprints f ON n.id = f.node_id"
            ).fetchall()
        cache: dict[str, Any] = {}
        for node_id, fp_blob in rows:
            if fp_blob:
                try:
                    cache[node_id] = pickle.loads(fp_blob)
                except Exception:
                    pass
        _fp_cache[clave] = cache
        log.info("fp_cache_loaded", count=len(cache), cuenta=bool(user_id))
        return cache


def init_graph():
    """Prepara el almacén privado y migra lo heredado. El corpus no se toca."""
    _migrar_lo_heredado()
    conn = _conn_privada()
    conn.close()


def add_molecule_node(
    smiles: str,
    properties: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> str:
    """Agregar o actualizar el nodo de molecula **de esta cuenta**.

    El id sigue siendo `mol_<smiles>`, pero ahora la clave primaria del almacén
    privado es `(user_id, id)`: dos cuentas que evalúan la misma molécula tienen
    dos filas, y ninguna sobrescribe a la otra. Ése era el fallo que un simple
    filtro de lectura no habría arreglado.
    """
    node_id = f"mol_{smiles[:40]}"
    # Computar fingerprint para similitud quimica
    fp_blob = b""
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
            fp_blob = pickle.dumps(fp)
    except Exception:
        pass

    conn = _escribir(user_id)
    try:
        exists = conn.execute(
            "SELECT id FROM priv_nodes WHERE user_id IS ? AND id = ?", (user_id, node_id)
        ).fetchone()
        props = json.dumps(properties or {}, ensure_ascii=False)
        name = smiles[:40]
        now = time.time()
        if exists:
            conn.execute(
                "UPDATE priv_nodes SET properties_json=?, created_at=? "
                "WHERE user_id IS ? AND id=?",
                (props, now, user_id, node_id),
            )
        else:
            conn.execute(
                "INSERT INTO priv_nodes "
                "(user_id, id, type, name, smiles, target_pdb, properties_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (user_id, node_id, "molecule", name, smiles, None, props, now),
            )
            conn.execute(
                "INSERT INTO priv_fts(node_id, user_id, name, type, properties_text) "
                "VALUES (?,?,?,?,?)",
                (node_id, user_id, name, "molecule", props[:1000]),
            )
        if fp_blob:
            conn.execute(
                "INSERT OR REPLACE INTO priv_fingerprints (user_id, node_id, fp_blob) "
                "VALUES (?,?,?)",
                (user_id, node_id, fp_blob),
            )
        conn.commit()
    finally:
        conn.close()
    invalidar_cache_de_huellas()
    return node_id


def add_target_node(
    pdb_id: str,
    name: str = "",
    properties: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> str:
    """Agregar o actualizar nodo de target (proteina) en el almacén de la cuenta."""
    node_id = f"target_{pdb_id}"
    conn = _escribir(user_id)
    try:
        exists = conn.execute(
            "SELECT id FROM priv_nodes WHERE user_id IS ? AND id = ?", (user_id, node_id)
        ).fetchone()
        props = json.dumps(properties or {}, ensure_ascii=False)
        display = name or pdb_id
        now = time.time()
        if exists:
            conn.execute(
                "UPDATE priv_nodes SET properties_json=?, created_at=? "
                "WHERE user_id IS ? AND id=?",
                (props, now, user_id, node_id),
            )
        else:
            conn.execute(
                "INSERT INTO priv_nodes "
                "(user_id, id, type, name, smiles, target_pdb, properties_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (user_id, node_id, "target", display, None, pdb_id, props, now),
            )
            conn.execute(
                "INSERT INTO priv_fts(node_id, user_id, name, type, properties_text) "
                "VALUES (?,?,?,?,?)",
                (node_id, user_id, display, "target", props[:1000]),
            )
        conn.commit()
    finally:
        conn.close()
    return node_id


def add_evaluation_node(
    smiles: str,
    target_pdb: str,
    affinity: float | None,
    score: float | None,
    properties: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> str:
    """Registrar una evaluacion **de una cuenta**: nodo eval + arista docking.

    MOLCHAT-BE-009: `user_id` no tiene valor por defecto útil a propósito. Sin
    él, `_escribir` lanza `SinCuenta`. El pipeline siempre sabe de quién es la
    corrida; si dejara de saberlo, es un error que hay que ver, no un nodo
    anónimo más en un archivo compartido.
    """
    node_id = f"eval_{uuid.uuid4().hex[:12]}"
    mol_id = add_molecule_node(smiles, properties, user_id=user_id)
    target_id = add_target_node(
        target_pdb,
        properties.get("target_name", "") if properties else "",
        user_id=user_id,
    )
    conn = _escribir(user_id)
    try:
        now = time.time()
        props = json.dumps({
            "affinity_kcal": affinity,
            "score": score,
            **(properties or {}),
        }, ensure_ascii=False)
        # Actualizar nodo molecula con datos de evaluacion
        conn.execute(
            "UPDATE priv_nodes SET properties_json=? WHERE user_id IS ? AND id=?",
            (props, user_id, mol_id),
        )
        conn.execute(
            "INSERT INTO priv_nodes "
            "(user_id, id, type, name, smiles, target_pdb, properties_json, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, node_id, "evaluation",
             f"Eval {smiles[:20]} vs {target_pdb}", smiles, target_pdb, props, now),
        )
        conn.execute(
            "INSERT INTO priv_fts(node_id, user_id, name, type, properties_text) "
            "VALUES (?,?,?,?,?)",
            (node_id, user_id, f"evaluacion {smiles[:30]} {target_pdb}",
             "evaluation", props[:1000]),
        )
        # Arista: molecula --docking--> target
        edge_id = f"edge_{uuid.uuid4().hex[:8]}"
        conn.execute(
            "INSERT OR REPLACE INTO priv_edges "
            "(user_id, id, source_id, target_id, relation, weight, metadata_json, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, edge_id, mol_id, target_id, "docking",
             float(abs(affinity or 0)), props, now),
        )
        # Arista: molecule --simil--> other molecules con mismo target. Sólo
        # entre moléculas de la misma cuenta: relacionar la molécula de alguien
        # con la de otro sería reintroducir la mezcla por la puerta del grafo.
        rows = conn.execute(
            "SELECT source_id FROM priv_edges "
            "WHERE user_id IS ? AND relation='docking' AND target_id=? AND source_id!=?",
            (user_id, target_id, mol_id),
        ).fetchall()
        for (src,) in rows:
            if src != mol_id:
                sim_edge = f"edge_sim_{uuid.uuid4().hex[:8]}"
                conn.execute(
                    "INSERT OR REPLACE INTO priv_edges "
                    "(user_id, id, source_id, target_id, relation, weight, "
                    "metadata_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (user_id, sim_edge, mol_id, src, "same_target", 0.5,
                     json.dumps({"target": target_pdb}), now),
                )
        conn.commit()
    finally:
        conn.close()
    log.info("molgraph_evaluation_registered", node_id=node_id[:12], cuenta=bool(user_id))
    return node_id


def query_graph(
    node_type: str = "",
    target_pdb: str = "",
    relation: str = "",
    min_score: float = 0,
    min_affinity: float = -999,
    limit: int = 10,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> list[dict]:
    """
    Query flexible del knowledge graph quimico.
    Ej: query_graph(target_pdb="7E2Y", min_affinity=-8)
    """
    init_graph()
    _gestor = _grafo(user_id, incluir_heredadas)
    c = _gestor.__enter__()
    try:
        sql = ("SELECT DISTINCT m.id, m.name, m.smiles, m.properties_json FROM mol_nodes m "
               "JOIN mol_edges e ON m.id = e.source_id "
               "WHERE 1=1")
        params: list[Any] = []
        if node_type:
            sql += " AND m.type=?"
            params.append(node_type)
        if target_pdb:
            sql += " AND e.relation='docking' AND e.target_id LIKE ?"
            params.append(f"%{target_pdb}%")
        if relation:
            sql += " AND e.relation=?"
            params.append(relation)
        sql += " ORDER BY e.weight DESC LIMIT ?"
        params.append(limit)

        rows = c.execute(sql, params).fetchall()
        results = []
        for r in rows:
            props = json.loads(r[3]) if r[3] else {}
            if min_score > 0 and props.get("score", 0) < min_score:
                continue
            if min_affinity > -998 and props.get("affinity_kcal", 0) > min_affinity:
                continue
            results.append({
                "node_id": r[0],
                "name": r[1],
                "smiles": r[2],
                "affinity": props.get("affinity_kcal"),
                "score": props.get("score"),
                "logp": props.get("log_p", "?"),
                "mw": props.get("molecular_weight", "?"),
            })
        return results
    finally:
        _gestor.__exit__(None, None, None)


def query_neighbors(
    smiles: str,
    limit: int = 5,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> list[dict]:
    """Encontrar moleculas relacionadas con esta."""
    init_graph()
    _gestor = _grafo(user_id, incluir_heredadas)
    c = _gestor.__enter__()
    mol_id = f"mol_{smiles[:40]}"
    try:
        # Buscar moleculas con mismo target
        rows = c.execute(
            """SELECT m2.name, m2.smiles, m2.properties_json, e.relation
               FROM mol_edges e
               JOIN mol_nodes m1 ON e.source_id = m1.id
               JOIN mol_nodes m2 ON e.target_id = m2.id
               WHERE m1.id = ? AND m2.type = 'molecule'
               UNION
               SELECT m2.name, m2.smiles, m2.properties_json, e2.relation
               FROM mol_edges e
               JOIN mol_nodes m1 ON e.source_id = m1.id
               JOIN mol_edges e2 ON e.target_id = e2.target_id
               JOIN mol_nodes m2 ON e2.source_id = m2.id
               WHERE m1.id = ? AND e2.source_id != ?
               LIMIT ?""",
            (mol_id, mol_id, mol_id, limit),
        ).fetchall()
        results = []
        for r in rows:
            props = json.loads(r[2]) if r[2] else {}
            results.append({
                "smiles": r[1],
                "name": r[0][:50],
                "relation": r[3],
                "affinity": props.get("affinity_kcal"),
                "score": props.get("score"),
            })
        return results
    finally:
        _gestor.__exit__(None, None, None)


def query_fts(
    text: str,
    limit: int = 8,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> list[dict]:
    """Busqueda FTS5 en el grafo: corpus público + lo de esta cuenta.

    El FTS es la excepción a la composición por vistas: `MATCH` exige la tabla
    virtual real, no una vista sobre ella. Así que se consultan las dos tablas y
    se juntan aquí, con el filtro de propiedad aplicado a la privada.
    """
    init_graph()
    safe = text.replace('"', "").replace("'", "")
    words = " OR ".join(safe.split()[:6])
    if not words:
        return []
    rows: list[tuple] = []
    with _grafo(user_id, incluir_heredadas) as c:
        try:
            rows.extend(c.execute(
                "SELECT node_id, name, type, properties_text FROM corpus.molgraph_fts "
                "WHERE corpus.molgraph_fts MATCH ? ORDER BY rank LIMIT ?",
                (words, limit),
            ).fetchall())
        except Exception:
            pass
        try:
            propiedad = (
                "((SELECT user_id FROM sesion) IS NOT NULL "
                " AND user_id = (SELECT user_id FROM sesion)) "
                "OR ((SELECT hereda FROM sesion) = 1 AND user_id IS NULL)"
            )
            rows.extend(c.execute(
                "SELECT node_id, name, type, properties_text FROM priv_fts "
                f"WHERE priv_fts MATCH ? AND ({propiedad}) ORDER BY rank LIMIT ?",
                (words, limit),
            ).fetchall())
        except Exception:
            pass
    rows = rows[:limit]
    results = []
    for r in rows:
        results.append({
            "node_id": r[0],
            "name": r[1],
            "type": r[2],
        })
    return results


def get_top_molecules(
    by: str = "score",
    limit: int = 5,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> list[dict]:
    """Top moleculas por score o afinidad."""
    init_graph()
    _gestor = _grafo(user_id, incluir_heredadas)
    c = _gestor.__enter__()
    rows = c.execute(
        "SELECT name, smiles, properties_json, type FROM mol_nodes WHERE type='molecule' LIMIT 200"
    ).fetchall()
    _gestor.__exit__(None, None, None)
    results = []
    for r in rows:
        try:
            props = json.loads(r[2]) if r[2] else {}
        except Exception:
            continue
        results.append({
            "smiles": r[1],
            "name": r[0],
            "score": props.get("score"),
            "affinity": props.get("affinity_kcal"),
        })
    if by == "score":
        results.sort(key=lambda x: x["score"] or 0, reverse=True)
    else:
        results.sort(key=lambda x: x["affinity"] or 0)
    return results[:limit]


def query_molgraph_similar(
    smiles: str,
    threshold: float = 0.6,
    limit: int = 5,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> list[dict]:
    """Encontrar moleculas quimicamente similares via fingerprints RDKit (con cache en RAM)."""
    init_graph()
    try:
        from rdkit import Chem, DataStructs
        from rdkit.Chem import AllChem
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return []
        query_fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
    except ImportError:
        return []

    cache = _load_fingerprint_cache(user_id, incluir_heredadas)

    # Solo cargar SMILES y propiedades — los fingerprints ya estan en RAM
    _gestor = _grafo(user_id, incluir_heredadas)
    c = _gestor.__enter__()
    rows = c.execute(
        "SELECT n.id, n.smiles, n.properties_json FROM mol_nodes n "
        "WHERE n.type = 'molecule'"
    ).fetchall()
    _gestor.__exit__(None, None, None)

    results = []
    for node_id, smiles, props_json in rows:
        target_fp = cache.get(node_id)
        if target_fp is None:
            continue
        sim = DataStructs.FingerprintSimilarity(query_fp, target_fp)
        if sim >= threshold:
            props = json.loads(props_json) if props_json else {}
            results.append({
                "smiles": smiles,
                "similarity": round(sim, 3),
                "score": props.get("score"),
                "affinity": props.get("affinity_kcal"),
            })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


# ═══════════════════════════════════════════════════════════════════════
# #1 CROSS-EVALUATION IMPACT — modified_from edge
# ═══════════════════════════════════════════════════════════════════════

def add_modification_edge(parent_smiles: str, child_smiles: str,
                          modification: str = "", delta_affinity: float = 0.0,
                          user_id: str | None = None):
    """Registrar que una molecula deriva de otra, en el grafo de esta cuenta."""
    # Registrar ambas moleculas primero, con su dueño
    add_molecule_node(parent_smiles, user_id=user_id)
    add_molecule_node(child_smiles, user_id=user_id)
    parent_id = f"mol_{parent_smiles[:40]}"
    child_id = f"mol_{child_smiles[:40]}"
    conn = _escribir(user_id)
    try:
        now = time.time()
        edge_id = f"mod_{uuid.uuid4().hex[:8]}"
        meta = json.dumps({
            "modification": modification,
            "delta_affinity": delta_affinity,
        }, ensure_ascii=False)
        conn.execute(
            "INSERT OR REPLACE INTO priv_edges "
            "(user_id, id, source_id, target_id, relation, weight, metadata_json, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, edge_id, child_id, parent_id, "modified_from",
             abs(delta_affinity) or 0.5, meta, now),
        )
        conn.commit()
    finally:
        conn.close()
    log.info("molgraph_modification_edge", parent=parent_smiles[:20], child=child_smiles[:20])


def query_modification_impact(
    substructure: str = "",
    min_delta: float = -99.0,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> list[dict]:
    """
    Analizar que modificaciones funcionaron mejor.
    Ej: query_modification_impact("NH2") → todos los casos donde se agrego NH2.
    """
    init_graph()
    _gestor = _grafo(user_id, incluir_heredadas)
    c = _gestor.__enter__()
    rows = c.execute(
        "SELECT e.metadata_json, m1.smiles AS parent_smiles, m2.smiles AS child_smiles, "
        "m1.properties_json, m2.properties_json "
        "FROM mol_edges e "
        "JOIN mol_nodes m1 ON e.target_id = m1.id "
        "JOIN mol_nodes m2 ON e.source_id = m2.id "
        "WHERE e.relation = 'modified_from' ORDER BY e.weight DESC"
    ).fetchall()
    _gestor.__exit__(None, None, None)
    results = []
    for r in rows:
        try:
            meta = json.loads(r[0])
        except Exception:
            continue
        mod = meta.get("modification", "")
        delta = meta.get("delta_affinity", 0.0)
        if substructure and substructure.lower() not in mod.lower():
            continue
        if delta < min_delta:
            continue
        parent_props = json.loads(r[3]) if r[3] else {}
        child_props = json.loads(r[4]) if r[4] else {}
        results.append({
            "parent_smiles": r[1],
            "child_smiles": r[2],
            "modification": mod,
            "delta_affinity": delta,
            "parent_score": parent_props.get("score"),
            "child_score": child_props.get("score"),
        })
    return results


# ═══════════════════════════════════════════════════════════════════════
# Early Exit — prediccion rapida para evitar docking innecesario
# ═══════════════════════════════════════════════════════════════════════

def predict_early_exit(smiles: str, min_neighbors: int = 3,
                       min_similarity: float = 0.6,
                       score_threshold: float = 0.45,
                       user_id: str | None = None,
                       incluir_heredadas: bool = False) -> dict:
    """Early Exit: predecir si dockear es innecesario usando MolGraph."""
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
        from rdkit import DataStructs

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {"skip": False, "reason": "invalid_smiles", "confidence": 0.0, "n_neighbors": 0}

        fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
        cache = _load_fingerprint_cache(user_id, incluir_heredadas)

        _gestor = _grafo(user_id, incluir_heredadas)
        c = _gestor.__enter__()
        rows = c.execute(
            "SELECT n.id, n.properties_json FROM mol_nodes n WHERE n.type = 'molecule'"
        ).fetchall()
        _gestor.__exit__(None, None, None)

        neighbors = []
        for node_id, props_json in rows:
            db_fp = cache.get(node_id)
            if db_fp is None:
                continue
            sim = DataStructs.TanimotoSimilarity(fp, db_fp)
            if sim >= min_similarity:
                score = None
                if props_json:
                    try:
                        props = json.loads(props_json)
                        score = props.get("composite", props.get("xgb_prob", 0.5))
                    except Exception:
                        score = 0.5
                neighbors.append({"similarity": sim, "score": score})

        n = len(neighbors)
        if n < min_neighbors:
            return {"skip": False, "reason": "cold_start", "confidence": 0.0, "n_neighbors": n}

        scores = [x["score"] for x in neighbors if x["score"] is not None]
        if len(scores) < min_neighbors:
            return {"skip": False, "reason": "cold_start", "confidence": 0.0, "n_neighbors": n}

        mean = float(np.mean(scores))
        std = float(np.std(scores))
        confidence = round(1.0 / (1.0 + std * 5), 3)

        if mean < score_threshold and std < 0.05:
            return {"skip": True, "reason": f"low_{mean:.3f}", "confidence": confidence, "n_neighbors": n}
        elif std > 0.1:
            return {"skip": False, "reason": "variance", "confidence": confidence, "n_neighbors": n}
        else:
            return {"skip": False, "reason": f"ok_{mean:.3f}", "confidence": confidence, "n_neighbors": n}

    except Exception as e:
        log.warning("early_exit_error", error=str(e))
        return {"skip": False, "reason": "error", "confidence": 0.0, "n_neighbors": 0}


if __name__ == "__main__":
    import sys
    s = sys.argv[1] if len(sys.argv) > 1 else "c1ccccc1"
    r = predict_early_exit(s)
    print(f"skip={r['skip']} reason={r['reason']} conf={r['confidence']} neighbors={r['n_neighbors']}")


# ═══════════════════════════════════════════════════════════════════════
# #3 SCAFFOLD/SERIES AUTO-DETECTION — clustering por fingerprints
# ═══════════════════════════════════════════════════════════════════════

def query_scaffold_groups(
    threshold: float = 0.5,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> list[dict]:
    """
    Agrupar moleculas en series quimicas por similitud Tanimoto.
    Retorna grupos con el mejor score de cada serie.
    """
    init_graph()
    cache = _load_fingerprint_cache(user_id, incluir_heredadas)

    _gestor = _grafo(user_id, incluir_heredadas)
    c = _gestor.__enter__()
    rows = c.execute(
        "SELECT n.id, n.smiles, n.properties_json "
        "FROM mol_nodes n WHERE n.type = 'molecule' ORDER BY n.created_at DESC"
    ).fetchall()
    _gestor.__exit__(None, None, None)

    if not rows:
        return []

    try:
        from rdkit import DataStructs
        fps = []
        molecules = []
        for node_id, smiles, props_json in rows:
            fp = cache.get(node_id)
            if fp:
                fps.append(fp)
                props = json.loads(props_json) if props_json else {}
                molecules.append({
                    "node_id": node_id,
                    "smiles": smiles,
                    "score": props.get("score"),
                    "affinity": props.get("affinity_kcal"),
                })
    except ImportError:
        return []

    # Greedy clustering
    groups = []
    assigned = set()
    for i in range(len(molecules)):
        if i in assigned:
            continue
        group = [molecules[i]]
        assigned.add(i)
        for j in range(i + 1, len(molecules)):
            if j in assigned:
                continue
            sim = DataStructs.FingerprintSimilarity(fps[i], fps[j])
            if sim >= threshold:
                group.append(molecules[j])
                assigned.add(j)
        if len(group) > 0:
            best = max(group, key=lambda x: x["score"] or 0)
            groups.append({
                "series_leader": best["smiles"][:30],
                "members": len(group),
                "best_score": best["score"],
                "best_affinity": best["affinity"],
                "smiles_list": [m["smiles"][:30] for m in group],
            })

    groups.sort(key=lambda x: x["best_score"] or 0, reverse=True)
    return groups


# ═══════════════════════════════════════════════════════════════════════
# #4 DRUG-LIKENESS VIOLATION GRAPH
# ═══════════════════════════════════════════════════════════════════════

def query_druglikeness_stats(
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> dict:
    """Analisis de reglas drug-likeness fallidas en todas las evaluaciones."""
    init_graph()
    _gestor = _grafo(user_id, incluir_heredadas)
    c = _gestor.__enter__()
    rows = c.execute(
        "SELECT properties_json FROM mol_nodes WHERE type='molecule' AND properties_json IS NOT NULL"
    ).fetchall()
    _gestor.__exit__(None, None, None)

    stats = {"total": 0, "mw_gt_500": 0, "logp_gt_5": 0, "hbd_gt_5": 0,
             "hba_gt_10": 0, "tpsa_gt_140": 0, "rot_gt_10": 0}
    for r in rows:
        try:
            p = json.loads(r[0])
        except Exception:
            continue
        stats["total"] += 1
        if p.get("molecular_weight", 0) > 500:
            stats["mw_gt_500"] += 1
        if p.get("log_p", 0) > 5:
            stats["logp_gt_5"] += 1
        if p.get("hbd", 0) > 5:
            stats["hbd_gt_5"] += 1
        if p.get("hba", 0) > 10:
            stats["hba_gt_10"] += 1
        if p.get("tpsa", 0) > 140:
            stats["tpsa_gt_140"] += 1
        if p.get("rotatable_bonds", 0) > 10:
            stats["rot_gt_10"] += 1
    return stats


# ═══════════════════════════════════════════════════════════════════════
# #5 ADMET ASSOCIATION GRAPH
# ═══════════════════════════════════════════════════════════════════════

def query_admet_correlation(
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> dict:
    """Correlacionar propiedades fisicoquimicas con predicciones ADMET."""
    init_graph()
    _gestor = _grafo(user_id, incluir_heredadas)
    c = _gestor.__enter__()
    rows = c.execute(
        "SELECT properties_json FROM mol_nodes WHERE properties_json IS NOT NULL"
    ).fetchall()
    _gestor.__exit__(None, None, None)

    # Agrupar por LogP
    groups = {"low_logp": [], "mid_logp": [], "high_logp": []}
    for r in rows:
        try:
            p = json.loads(r[0])
        except Exception:
            continue
        logp = p.get("log_p", 0)
        bbb = p.get("blood_bbb_permeable")
        hia = p.get("blood_hia_permeable")
        mw = p.get("molecular_weight", 0)
        if logp < 1.5:
            groups["low_logp"].append({"bbb": bbb, "hia": hia, "mw": mw})
        elif logp < 3.5:
            groups["mid_logp"].append({"bbb": bbb, "hia": hia, "mw": mw})
        else:
            groups["high_logp"].append({"bbb": bbb, "hia": hia, "mw": mw})

    result = {}
    for group, entries in groups.items():
        if not entries:
            continue
        bbb_yes = sum(1 for e in entries if e.get("bbb"))
        hia_yes = sum(1 for e in entries if e.get("hia"))
        total = len(entries)
        result[group] = {
            "count": total,
            "bbb_permeable_pct": round(bbb_yes / total * 100, 1) if total else 0,
            "hia_permeable_pct": round(hia_yes / total * 100, 1) if total else 0,
            "avg_mw": round(sum(e.get("mw", 0) for e in entries) / total, 1),
        }
    return result
