"""
services/ai/memory_store.py — Memoria persistente para el asistente IA.

Arquitectura jerárquica (v2):
  ┌─ catalog:      SMILES + score + affinity + summary  (~50 bytes/entry)
  │                → Barato de cargar. El LLM siempre ve esto.
  └─ details:      result_json + ADMET + embedding      (~2 KB/entry)
                   → Solo se carga bajo demanda via molecule_id.

Tabla de conversaciones (v1.4):
  ┌─ conversations: mensajes + summary + timestamps     (JSON)
                   → Persistencia entre restarts.
                   → El usuario no pierde sus chats.

Flujo:
  1. LLM ve el catalog (condensed, ~8 tokens por molécula)
  2. Si el usuario pregunta detalles → molecule_id → carga details
  3. Si el usuario pide "similar" → search_similar via embeddings
  4. Conversaciones → persisten IDs + previews + mensajes en SQLite
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
import time
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

import numpy as np

from utils.logger import get_logger

log = get_logger(__name__)

def _directorio_de_datos() -> Path:
    """Igual que en `molgraph`: bajo pruebas, nunca el home del usuario.

    `ai_memory.db` guarda conversaciones, catálogo y el índice de búsqueda de
    quien use la máquina. Una prueba que olvide aislar la ruta escribiría encima
    de todo eso.
    """
    if os.environ.get("MOLDESIGN_TESTING") == "1":
        return Path(tempfile.gettempdir()) / "moldesign-tests" / "ai"
    return Path("~/MolDesign/data").expanduser()


_DB_PATH = _directorio_de_datos() / "ai_memory.db"
_EMBEDDING_DIM = 1024


class PersistenciaFallida(RuntimeError):
    """`ai_memory.db` no pudo cumplir la operación que se le pidió.

    MOLCHAT-BE-008. Antes estas rutas terminaban en `except Exception: pass`, y
    los tres desenlaces —creada, leída, borrada— se contaban como buenos
    aunque la base no hubiera hecho nada. El §8 pide persistencia «atómica y
    recuperable», y recuperable exige, como mínimo, que el fallo se sepa.
    """


def _get_conn() -> sqlite3.Connection:
    """Obtener conexión a la DB de memoria IA."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


@contextmanager
def _conexion():
    """Abre, cierra y traduce. Un fallo de disco nunca sale como un `None`."""
    try:
        conn = _get_conn()
    except sqlite3.Error as exc:
        raise PersistenciaFallida(f"no se pudo abrir ai_memory.db: {exc}") from exc
    try:
        yield conn
    except sqlite3.Error as exc:
        raise PersistenciaFallida(f"ai_memory.db falló la operación: {exc}") from exc
    finally:
        with suppress(sqlite3.Error):
            conn.close()


def _columnas_de(nombre: str) -> set[str]:
    """Columnas reales de una tabla, para migraciones idempotentes."""
    with _conexion() as conn:
        return {fila[1] for fila in conn.execute(f"PRAGMA table_info({nombre})")}


def init_db():
    """Crear las tablas jerárquicas: catalog (condensed) + details (full data)."""
    with _conexion() as conn:
        # Catalog: lo que el LLM SIEMPRE ve (~50 bytes/entry, ultra barato)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_catalog (
                molecule_id TEXT PRIMARY KEY,
                smiles TEXT NOT NULL,
                target_pdb TEXT NOT NULL,
                affinity REAL,
                score REAL,
                summary TEXT,
                n_hotspots INTEGER DEFAULT 0,
                created_at REAL,
                user_id TEXT
            )
        """)
        # Details: solo se carga bajo demanda via molecule_id (link token)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_details (
                molecule_id TEXT PRIMARY KEY,
                result_json TEXT,
                embedding_blob BLOB,
                created_at REAL,
                FOREIGN KEY (molecule_id) REFERENCES ai_catalog(molecule_id)
            )
        """)
        # Fuga por el índice de búsqueda: `ai_catalog` no tenía dueño, así que
        # el catálogo de evaluaciones que el LLM ve en CADA turno era el de
        # todas las cuentas de la máquina. La columna es aditiva y nullable, y
        # las filas anteriores quedan heredadas sin dueño (D-07). `ai_details`
        # cuelga de `ai_catalog` por `molecule_id`: se filtra por el join, no
        # duplicando la columna, para que no haya dos verdades sobre de quién
        # es una molécula.
        columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(ai_catalog)")}
        if "user_id" not in columnas:
            conn.execute("ALTER TABLE ai_catalog ADD COLUMN user_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cat_target ON ai_catalog(target_pdb)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cat_score ON ai_catalog(score DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cat_created ON ai_catalog(created_at DESC)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cat_user ON ai_catalog(user_id, created_at DESC)"
        )
        conn.commit()


def store_evaluation(
    molecule_id: str,
    smiles: str,
    target_pdb: str,
    affinity: float | None,
    score: float | None,
    result_json: str | None = None,
    embedding: np.ndarray | None = None,
    summary: str | None = None,
    user_id: str | None = None,
):
    """Guardar en catalog + details (jerárquico), con la cuenta que lo evaluó."""
    init_db()
    now = time.time()
    with _conexion() as conn:
        # Catalog (siempre visible para el LLM de esa cuenta)
        conn.execute(
            """INSERT OR REPLACE INTO ai_catalog
               (molecule_id, smiles, target_pdb, affinity, score, summary, created_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (molecule_id, smiles, target_pdb, affinity, score, summary, now, user_id),
        )
        # Details (solo bajo demanda via molecule_id)
        blob = embedding.tobytes() if embedding is not None else None
        conn.execute(
            """INSERT OR REPLACE INTO ai_details
               (molecule_id, result_json, embedding_blob, created_at)
               VALUES (?, ?, ?, ?)""",
            (molecule_id, result_json, blob, now),
        )
        conn.commit()
    log.info("ai_memory_stored", molecule_id=molecule_id[:8], smiles=smiles[:30])


def search_similar(
    query_embedding: np.ndarray,
    top_k: int = 5,
    min_affinity: float | None = None,
    target_pdb: str | None = None,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> list[dict[str, Any]]:
    """
    Buscar evaluaciones similares por embedding (cosine similarity).

    Args:
        query_embedding: embedding de la consulta (1024 floats)
        top_k: número de resultados
        min_affinity: filtrar por afinidad mínima (más negativo = mejor)
        target_pdb: filtrar por target
        user_id: cuenta que pregunta. Sin ella no se devuelve nada.

    Returns:
        Lista de dicts con {smiles, target_pdb, affinity, score, summary, similarity}
    """
    init_db()

    filtro, params = _clausula_de_dueno(user_id, incluir_heredadas, columna="c.user_id")
    where_clauses = [filtro]
    if target_pdb:
        where_clauses.append("c.target_pdb = ?")
        params.append(target_pdb)
    if min_affinity is not None:
        where_clauses.append("c.affinity <= ?")
        params.append(min_affinity)

    where_sql = " AND ".join(where_clauses)

    with _conexion() as conn:
        rows = conn.execute(
            f"SELECT c.molecule_id, c.smiles, c.target_pdb, c.affinity, c.score, "
            f"d.embedding_blob, c.summary, d.result_json "
            f"FROM ai_catalog c LEFT JOIN ai_details d ON c.molecule_id = d.molecule_id "
            f"WHERE {where_sql}",
            params,
        ).fetchall()

    if not rows:
        return []

    # Cargar todos los embeddings en numpy
    all_embeddings = np.array([np.frombuffer(r[5], dtype=np.float32) for r in rows if r[5]])
    if len(all_embeddings) == 0:
        return []

    # Normalizar
    q_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
    e_norm = all_embeddings / (np.linalg.norm(all_embeddings, axis=1, keepdims=True) + 1e-10)

    # Cosine similarity
    similarities = np.dot(e_norm, q_norm)

    # Top-K
    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = []
    valid_rows = [r for r in rows if r[5]]  # solo con embedding
    for idx in top_indices:
        r = valid_rows[idx]
        results.append({
            "molecule_id": r[0],
            "smiles": r[1],
            "target_pdb": r[2],
            "affinity": r[3],
            "score": r[4],
            "summary": r[6],
            "result_json": r[7],
            "similarity": round(float(similarities[idx]), 4),
        })

    return results


def get_last_evaluations(
    n: int = 10,
    target_pdb: str | None = None,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> list[dict[str, Any]]:
    """Últimas N evaluaciones **de esta cuenta**, opcionalmente por target."""
    init_db()
    filtro, params = _clausula_de_dueno(user_id, incluir_heredadas)
    where = [filtro]
    if target_pdb:
        where.append("target_pdb = ?")
        params.append(target_pdb)
    params.append(n)
    with _conexion() as conn:
        rows = conn.execute(
            "SELECT molecule_id, smiles, target_pdb, affinity, score, summary "
            f"FROM ai_catalog WHERE {' AND '.join(where)} "
            "ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()

    return [
        {
            "molecule_id": r[0],
            "smiles": r[1],
            "target_pdb": r[2],
            "affinity": r[3],
            "score": r[4],
            "summary": r[5],
        }
        for r in rows
    ]


def build_context_for_llm(
    target_pdb: str | None = None,
    max_tokens: int = 6000,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> str:
    """
    Construir contexto inyectable en formato DENSE ultra-comprimido.

    DENSE FORMAT (v1): cada evaluación ocupa ~8-15 tokens en vez de ~50-80.
    Estructura: ║SMILE|target|score|aff|hotspots|summary║

    El LLM sabe interpretar este formato via system prompt.
    Links: cada molecule_id permite cargar datos completos bajo demanda.

    Sin `user_id` devuelve vacío: este contexto entra en el prompt de alguien, y
    sin saber de quién es la memoria no hay memoria que inyectar (D-05).
    """
    evals = get_last_evaluations(
        n=30,
        target_pdb=target_pdb,
        user_id=user_id,
        incluir_heredadas=incluir_heredadas,
    )
    if not evals:
        return ""

    # Ordenar por score descendente
    sorted_evals = sorted(evals, key=lambda x: x.get("score") or 0, reverse=True)

    header = "DENSEv1 | SMILE | TARGET | SCORE | AFF | SUMMARY"
    lines = [header]
    current_tokens = 8

    for e in sorted_evals:
        smi = e["smiles"][:40] if e["smiles"] else "?"
        tgt = e["target_pdb"] or "?"
        sc = f"{e['score']:.0f}" if e["score"] else "?"
        af = f"{e['affinity']:.1f}" if e["affinity"] else "?"
        hot = (e.get("summary", "") or "")[:30]
        dense = f"D|{smi}|{tgt}|{sc}|{af}|{hot}"
        line_tokens = len(dense) // 3
        if current_tokens + line_tokens > max_tokens:
            remaining = len(sorted_evals) - len(lines) + 1
            lines.append(f"D|...(+{remaining} more)")
            break
        lines.append(dense)
        current_tokens += line_tokens

    lines.append(
        "LEGEND: D=DENSEv1 SCORE 0-100(higher=better) AFF kcal/mol(more-negative=better)\n"
        "[Use molecule_id from the row to load full details]"
    )
    return "\n".join(lines)


def get_full_evaluation(
    molecule_id: str,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> dict | None:
    """Datos COMPLETOS de una evaluación **de esta cuenta** via molecule_id."""
    init_db()
    filtro, params = _clausula_de_dueno(user_id, incluir_heredadas, columna="c.user_id")
    with _conexion() as conn:
        row = conn.execute(
            "SELECT c.molecule_id, c.smiles, c.target_pdb, c.affinity, c.score, "
            "c.summary, d.result_json "
            "FROM ai_catalog c LEFT JOIN ai_details d ON c.molecule_id = d.molecule_id "
            f"WHERE c.molecule_id = ? AND {filtro}",
            (molecule_id, *params),
        ).fetchone()
    if not row:
        return None
    return {
        "molecule_id": row[0],
        "smiles": row[1],
        "target_pdb": row[2],
        "affinity": row[3],
        "score": row[4],
        "summary": row[5],
        "result_json": row[6],
    }


def get_evaluation_count(
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> int:
    """Número de evaluaciones almacenadas **de esta cuenta**."""
    init_db()
    filtro, params = _clausula_de_dueno(user_id, incluir_heredadas)
    with _conexion() as conn:
        return conn.execute(
            f"SELECT COUNT(*) FROM ai_catalog WHERE {filtro}", params
        ).fetchone()[0]


def get_top_by_target(
    target_pdb: str,
    n: int = 10,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> list[dict]:
    """Top-N mejores moléculas **de esta cuenta** para un target específico."""
    init_db()
    filtro, params = _clausula_de_dueno(user_id, incluir_heredadas)
    with _conexion() as conn:
        rows = conn.execute(
            "SELECT molecule_id, smiles, affinity, score, summary "
            f"FROM ai_catalog WHERE target_pdb = ? AND {filtro} "
            "ORDER BY affinity ASC LIMIT ?",
            (target_pdb, *params, n),
        ).fetchall()
    return [
        {"molecule_id": r[0], "smiles": r[1], "affinity": r[2], "score": r[3], "summary": r[4]}
        for r in rows
    ]


def init_conv_db():
    with _conexion() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                conv_id TEXT PRIMARY KEY,
                messages_json TEXT NOT NULL DEFAULT '[]',
                summary TEXT DEFAULT '',
                molecule_context_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at DESC)"
        )

        # MOLCHAT-BE-004: `ai_memory.db` vive en el home de la máquina, así que
        # era un único archivo de conversaciones para todas las cuentas. La
        # columna es aditiva y nullable: las filas anteriores quedan en `NULL` y
        # **no se les asigna dueño por suposición** (D-07). Esta base no pasa por
        # `_migrate_sqlite_db`, así que la migración vive aquí y es idempotente.
        columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(conversations)")}
        if "user_id" not in columnas:
            conn.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at DESC)"
        )
        conn.commit()


def _clausula_de_dueno(
    user_id: str | None,
    incluir_heredadas: bool,
    columna: str = "user_id",
) -> tuple[str, list]:
    """Filtro de propiedad para TODAS las consultas de `ai_memory.db`.

    `incluir_heredadas` sólo lo activa la cuenta invitada (D-07): las filas sin
    `user_id` son anteriores a esta columna y no se sabe de quién eran.

    Sin `user_id` la cláusula queda en `columna = NULL`, que en SQL no empareja
    con nada: sin identidad no se lee memoria de nadie. Es deliberado, y es la
    misma regla que D-05 aplicó a las herramientas.
    """
    if incluir_heredadas:
        return f"({columna} = ? OR {columna} IS NULL)", [user_id]
    return f"{columna} = ?", [user_id]


def save_conversation(
    conv_id: str,
    messages: list[dict[str, str]],
    summary: str = "",
    molecule_context: dict[str, Any] | None = None,
    created_at: float = 0.0,
    user_id: str | None = None,
):
    """Guarda la conversación, o lanza `PersistenciaFallida` (MOLCHAT-BE-008)."""
    init_conv_db()
    now = time.time()
    with _conexion() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO conversations
               (conv_id, messages_json, summary, molecule_context_json, created_at, updated_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                conv_id,
                json.dumps(messages, ensure_ascii=False),
                summary,
                json.dumps(molecule_context, ensure_ascii=False) if molecule_context else None,
                created_at if created_at > 0 else now,
                now,
                user_id,
            ),
        )
        conn.commit()


def load_conversation(
    conv_id: str,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> dict | None:
    """`None` significa «no existe o no es tuya», nunca «la base falló»."""
    init_conv_db()
    filtro, params = _clausula_de_dueno(user_id, incluir_heredadas)
    with _conexion() as conn:
        row = conn.execute(
            "SELECT conv_id, messages_json, summary, molecule_context_json, "
            f"created_at, updated_at FROM conversations WHERE conv_id = ? AND {filtro}",
            (conv_id, *params),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "messages": json.loads(row[1]),
        "summary": row[2],
        "molecule_context": json.loads(row[3]) if row[3] else None,
        "created_at": row[4],
        "updated_at": row[5],
    }


def load_all_conversations(
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> list[dict]:
    init_conv_db()
    filtro, params = _clausula_de_dueno(user_id, incluir_heredadas)
    with _conexion() as conn:
        rows = conn.execute(
            "SELECT conv_id, messages_json, summary, created_at, updated_at "
            f"FROM conversations WHERE {filtro} ORDER BY updated_at DESC LIMIT 50",
            params,
        ).fetchall()
    result = []
    for r in rows:
        messages = json.loads(r[1]) if r[1] else []
        preview = ""
        for m in messages:
            if isinstance(m, dict) and m.get("role") == "user":
                preview = m.get("content", "")[:80]
                break
        result.append({
            "id": r[0],
            "preview": preview,
            "message_count": len(messages),
            "summary": r[2],
            "created_at": r[3],
            "updated_at": r[4],
        })
    return result


def delete_conversation_db(
    conv_id: str,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> bool:
    """Devuelve si se borró **una fila**. `False` no es un fallo: es un 404.

    MOLCHAT-BE-008: antes no devolvía nada y el endpoint contestaba
    `{"status": "deleted"}` siempre, incluso cuando el filtro de propiedad no
    encontraba la conversación o la base había fallado.
    """
    init_conv_db()
    filtro, params = _clausula_de_dueno(user_id, incluir_heredadas)
    with _conexion() as conn:
        cursor = conn.execute(
            f"DELETE FROM conversations WHERE conv_id = ? AND {filtro}",
            (conv_id, *params),
        )
        borradas = cursor.rowcount
        conn.commit()
    return borradas > 0


# ═══════════════════════════════════════════════════════════════════════
# SLEEP CONSOLIDATION — Hippocampus Replay (v1.4)
# ═══════════════════════════════════════════════════════════════════════

def consolidate_session(conv_id: str) -> dict:
    """
    Comprimir toda una sesión de chat en un resumen estructurado.
    Imita el "sleep replay" del hipocampo: refuerza lo importante,
    olvida lo trivial.
    """
    init_conv_db()
    conn = _get_conn()
    row = conn.execute(
        "SELECT messages_json FROM conversations WHERE conv_id = ?", (conv_id,),
    ).fetchone()
    conn.close()
    if not row:
        return {}

    try:
        messages = json.loads(row[0])
    except Exception:
        return {}

    molecules = []
    targets = []
    tools_used = []
    key_topics = []
    total_user = 0
    total_assistant = 0
    smiles_re = re.compile(r'[A-Za-z0-9()=\[\]@#+\\/\-.%]{4,}')

    mol_keywords = {"aspirina", "ibuprofeno", "paracetamol", "morfina", "cafeína",
                    "dopamina", "serotonina", "penicilina", "amoxicilina",
                    "omeprazol", "lorazepam", "diazepam", "fluoxetina", "sertralina",
                    "metformina", "atorvastatina", "losartan", "enalapril"}
    target_keywords = {"receptor", "target", "proteína", "enzima", "5-HT", "EGFR", "CDK4",
                       "GPCR", "kinase", "docking", "PDB", "7E2Y", "1ABC"}
    topic_keywords = {"afinidad", "score", "logp", "logP", "lipinski", "veber", "admet", "toxicidad",
                      "síntesis", "solubilidad", "absorción", "BBB", "metabolismo",
                      "hotspot", "docking", "propiedad", "estructura", "interacción"}

    for m in messages:
        content = (m.get("content", "") if isinstance(m, dict) else "").lower()
        role = m.get("role", "") if isinstance(m, dict) else ""

        if role == "user":
            total_user += 1
        elif role == "assistant":
            total_assistant += 1

        for kw in mol_keywords:
            if kw in content and kw not in molecules:
                molecules.append(kw)
        for kw in target_keywords:
            if kw in content and kw not in targets:
                targets.append(kw)
        for kw in topic_keywords:
            if kw in content and kw not in key_topics:
                key_topics.append(kw)
        # Detectar SMILES: cadenas con caracteres químicos
        found_smiles = smiles_re.findall(content)
        for s in found_smiles[:3]:
            if len(s) > 5 and s not in molecules:
                molecules.append(s[:30])

    return {
        "conv_id": conv_id,
        "total_messages": total_user + total_assistant,
        "user_messages": total_user,
        "assistant_messages": total_assistant,
        "molecules_discussed": molecules[:10],
        "targets_discussed": targets[:8],
        "key_topics": key_topics[:10],
        "consolidated_at": time.time(),
    }


def get_all_consolidated_sessions(limit: int = 10) -> list[dict]:
    """Obtener todas las sesiones consolidadas para inyectar como 'memoria a largo plazo'."""
    init_conv_db()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT conv_id, messages_json, updated_at FROM conversations "
        "ORDER BY updated_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()

    results = []
    for r in rows:
        consolidated = consolidate_session(r[0])
        if consolidated:
            consolidated["updated_at"] = r[2]
            results.append(consolidated)
    return results


# ═══════════════════════════════════════════════════════════════════════
# ENGRAM MEMORY — Búsqueda FTS5 (full-text search) (v1.4)
# ═══════════════════════════════════════════════════════════════════════

_ENGRAM_COLUMNAS = (
    "content, role, conv_id UNINDEXED, user_id UNINDEXED, tokenize='unicode61'"
)


def init_engram_db():
    """Crear el índice FTS5 del historial de chat, con dimensión de cuenta.

    Esta era la fuga más silenciosa de la pestaña: `search_chat_history` no
    filtraba por cuenta y `_prepare_messages_with_context` la consultaba en cada
    turno, así que los mensajes de una cuenta entraban en el prompt de otra sin
    que nadie pidiera nada.

    FTS5 no admite `ALTER TABLE ... ADD COLUMN`, así que un índice anterior a la
    columna se **reconstruye** copiando su contenido con `user_id` nulo: quedan
    heredados, y sólo los ve la cuenta invitada (D-07).
    """
    with _conexion() as conn:
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS engram_chat USING fts5({_ENGRAM_COLUMNAS})"
        )
        columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(engram_chat)")}
        if "user_id" not in columnas:
            conn.execute(
                f"CREATE VIRTUAL TABLE engram_chat_con_dueno USING fts5({_ENGRAM_COLUMNAS})"
            )
            conn.execute(
                "INSERT INTO engram_chat_con_dueno(content, role, conv_id, user_id) "
                "SELECT content, role, conv_id, NULL FROM engram_chat"
            )
            conn.execute("DROP TABLE engram_chat")
            conn.execute("ALTER TABLE engram_chat_con_dueno RENAME TO engram_chat")
            log.info("engram_index_migrado_a_cuentas")
        conn.commit()


def index_chat_message(
    conv_id: str,
    role: str,
    content: str,
    user_id: str | None = None,
):
    """Indexar un mensaje de chat en FTS5 para búsqueda semántica rápida."""
    if not content or len(content) < 10:
        return
    init_engram_db()
    with _conexion() as conn:
        conn.execute(
            "INSERT INTO engram_chat(content, role, conv_id, user_id) VALUES (?, ?, ?, ?)",
            (content[:5000], role, conv_id, user_id),
        )
        conn.commit()


def _consulta_fts(texto: str, maximo: int = 6) -> str:
    """Convierte el texto de quien pregunta en una consulta FTS5 **literal**.

    Lo encontró el gate runtime de MolChat: la primera pregunta real con un
    SMILES devolvió HTTP 500 con `no such column: SMILES`. La consulta se
    construía pegando las palabras del mensaje, y en FTS5 `algo:` es un filtro
    por columna, `"` abre un literal, `*` es prefijo y `NEAR`/`AND`/`OR`/`NOT`
    son operadores. El texto del investigador entraba sin escapar en un lenguaje
    de consulta — la forma de esto es una inyección, aunque aquí sólo alcance a
    romper la búsqueda.

    Cada término se envuelve en comillas dobles, que es como FTS5 declara una
    cadena literal, duplicando las comillas internas. Así `SMILES:` vuelve a ser
    la palabra «SMILES», no un filtro de columna inexistente.
    """
    terminos: list[str] = []
    for palabra in texto.split():
        limpia = palabra.strip()
        if len(limpia) < 2:
            continue
        # `""` es el escape de comilla dentro de un literal FTS5.
        terminos.append('"' + limpia.replace('"', '""') + '"')
        if len(terminos) >= maximo:
            break
    return " OR ".join(terminos)


def search_chat_history(
    query: str,
    limit: int = 5,
    user_id: str | None = None,
    incluir_heredadas: bool = False,
) -> list[dict]:
    """Búsqueda FTS5 en el historial de chat **de esta cuenta**."""
    if not query or len(query) < 3:
        return []
    init_engram_db()
    or_query = _consulta_fts(query)
    if not or_query:
        return []
    filtro, params = _clausula_de_dueno(user_id, incluir_heredadas)
    with _conexion() as conn:
        rows = conn.execute(
            "SELECT content, role, conv_id, rank FROM engram_chat "
            f"WHERE engram_chat MATCH ? AND {filtro} ORDER BY rank LIMIT ?",
            (or_query, *params, limit),
        ).fetchall()

    results = []
    seen_content = {}
    for r in rows:
        content = r[0][:200]
        role = r[1]
        conv_id = r[2]
        content_key = content[:50]
        seen_content[content_key] = seen_content.get(content_key, 0) + 1
        results.append({
            "content": content,
            "role": role,
            "conv_id": conv_id,
            "repetition_weight": seen_content[content_key],
        })
    results.sort(key=lambda x: x["repetition_weight"], reverse=True)
    return results[:limit]
