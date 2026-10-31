"""SQLite memory store, always scoped by owner.

Reimplemented from MolDesign's ``memory_store.py`` (user_id on every row,
loud persistence failures) and ``conversation_state.py`` (bounded context,
deterministic compression) without importing them and without embeddings:
vectors and full-text search arrive when a tool needs them.
"""

from __future__ import annotations

from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Iterator


class PersistenciaFallida(RuntimeError):
    """The database failed an operation. Never a silent None."""


class ConversationNotFound(KeyError):
    """Unknown id, or owned by somebody else (same answer on purpose)."""


@dataclass
class Conversation:
    id: str
    user_id: str | None = None
    messages: list[dict[str, str]] = field(default_factory=list)
    summary: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    molecule_context: dict[str, Any] | None = None

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        self.updated_at = time.time()

    def estimated_tokens(self) -> int:
        return sum(int(len(m.get("content", "")) * 0.45) for m in self.messages)


_NOISE = {
    "gracias", "ok", "bien", "perfecto", "excelente", "hola",
    "buenos días", "buenas tardes", "buenas", "sí", "si", "no",
    "vale", "genial",
}


def _meaningful(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    kept = []
    for message in messages:
        content = message.get("content", "").strip().lower()
        if len(content) < 8 or content in _NOISE or content.rstrip(".! ") in _NOISE:
            continue
        kept.append(message)
    return kept


def _quick_compress(messages: list[dict[str, str]]) -> str:
    molecules: set[str] = set()
    targets: set[str] = set()
    topics: set[str] = set()
    facts: dict[str, str] = {}
    questions: list[str] = []
    for message in messages:
        content = message.get("content", "")
        if message.get("role") == "user":
            questions.append(content[:100])
            continue
        for pattern, key in (
            (r"afinidad\s*(?:de|:)?\s*([-\d.]+)\s*kcal", "aff"),
            (r"score\s*(?:total|general)?\s*(?:de|:)?\s*(\d+)\s*/100", "score"),
            (r"(\d+\.?\d*)\s*Da\b", "mw"),
            (r"log\s*[pP]\s*(?:de|:)?\s*([-\d.]+)", "logp"),
        ):
            match = re.search(pattern, content, re.IGNORECASE)
            if match and key not in facts:
                facts[key] = match.group(1)
        lowered = content.lower()
        for molecule in ("aspirina", "ibuprofeno", "paracetamol", "cafeina",
                         "morfina", "etanol", "dopamina", "glucosa"):
            if molecule in lowered:
                molecules.add(molecule)
        for target in ("5-ht1a", "7e2y", "1hsg", "egfr", "gpcr"):
            if target in lowered:
                targets.add(target.upper())
        for keyword in ("afinidad", "docking", "score", "lipinski", "admet",
                        "logp", "tpsa", "pains", "hotspot", "selectividad"):
            if keyword in lowered:
                topics.add(keyword)
    parts = [f"Charla anterior ({len(messages)} msgs)"]
    if molecules:
        parts.append(f"mols: {', '.join(sorted(molecules))}")
    if targets:
        parts.append(f"targets: {', '.join(sorted(targets))}")
    if facts:
        parts.append("datos: " + ", ".join(f"{k}={v}" for k, v in facts.items()))
    if topics:
        parts.append(f"temas: {', '.join(sorted(topics)[:6])}")
    if questions:
        parts.append(f"ultimas: {' | '.join(questions[-2:])}")
    return (". ".join(parts))[:500]


class MemoryStore:
    """Conversations + session molecules, persisted per owner in SQLite."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._init_db()

    @property
    def path(self) -> Path:
        return self._path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._path))
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.Error as exc:
            raise PersistenciaFallida(f"no se pudo abrir {self._path}: {exc}") from exc
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            raise PersistenciaFallida(f"{self._path} falló la operación: {exc}") from exc
        finally:
            with suppress(sqlite3.Error):
                conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    messages TEXT NOT NULL DEFAULT '[]',
                    summary TEXT NOT NULL DEFAULT '',
                    molecule_context TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_molecules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conv_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    smiles TEXT NOT NULL DEFAULT '',
                    props TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    FOREIGN KEY (conv_id) REFERENCES conversations(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mol_conv ON session_molecules(conv_id)")
            conn.execute("""CREATE TABLE IF NOT EXISTS harness_pending (
                conv_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, payload TEXT NOT NULL,
                FOREIGN KEY (conv_id) REFERENCES conversations(id))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS harness_jobs (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, conv_id TEXT NOT NULL,
                state TEXT NOT NULL, steps TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_harness_jobs_user ON harness_jobs(user_id, created_at)")

    def save_harness_job(self, job_id: str, user_id: str, conv_id: str, state: str,
                         steps: list[dict[str, str]]) -> None:
        now = time.time()
        with self._connect() as conn:
            conn.execute("""INSERT INTO harness_jobs (id, user_id, conv_id, state, steps, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,
                steps=excluded.steps, updated_at=excluded.updated_at WHERE harness_jobs.user_id=excluded.user_id""",
                (job_id, user_id, conv_id, state, json.dumps(steps, ensure_ascii=False), now, now))

    def list_harness_jobs(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, conv_id, state, steps, created_at, updated_at FROM harness_jobs "
                                "WHERE user_id=? ORDER BY created_at DESC LIMIT 100", (user_id,)).fetchall()
        return [{"id": row[0], "conversation_id": row[1], "state": row[2], "steps": json.loads(row[3]),
                 "created_at": row[4], "updated_at": row[5]} for row in rows]

    @staticmethod
    def _row_to_conversation(row: Any) -> Conversation:
        return Conversation(
            id=row[0], user_id=row[1],
            messages=json.loads(row[2]), summary=row[3],
            molecule_context=json.loads(row[4]) if row[4] else None,
            created_at=row[5], updated_at=row[6])

    def create_conversation(self, user_id: str) -> str:
        conv_id = uuid.uuid4().hex[:12]
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO conversations VALUES (?, ?, '[]', '', NULL, ?, ?)",
                (conv_id, user_id, now, now))
        return conv_id

    def get_conversation(self, conv_id: str, user_id: str) -> Conversation | None:
        """The conversation, or None when missing or owned by somebody else."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
                (conv_id, user_id)).fetchone()
        return self._row_to_conversation(row) if row else None

    def list_conversations(self, user_id: str) -> list[Conversation]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,)).fetchall()
        return [self._row_to_conversation(row) for row in rows]

    def delete_conversation(self, conv_id: str, user_id: str) -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM harness_pending WHERE conv_id = ? AND user_id = ?", (conv_id, user_id))
            conn.execute("DELETE FROM harness_jobs WHERE conv_id = ? AND user_id = ?", (conv_id, user_id))
            cursor = conn.execute(
                "DELETE FROM session_molecules WHERE conv_id IN "
                "(SELECT id FROM conversations WHERE id = ? AND user_id = ?)",
                (conv_id, user_id))
            molecules = cursor.rowcount
            cursor = conn.execute(
                "DELETE FROM conversations WHERE id = ? AND user_id = ?",
                (conv_id, user_id))
            deleted = cursor.rowcount > 0
            _ = molecules
        return deleted

    def set_harness_pending(self, conv_id: str, user_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            exists = conn.execute("SELECT 1 FROM conversations WHERE id = ? AND user_id = ?",
                                  (conv_id, user_id)).fetchone()
            if not exists:
                raise ConversationNotFound(conv_id)
            conn.execute("INSERT OR REPLACE INTO harness_pending (conv_id, user_id, payload) VALUES (?, ?, ?)",
                         (conv_id, user_id, json.dumps(payload, ensure_ascii=False)))

    def get_harness_pending(self, conv_id: str, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM harness_pending WHERE conv_id = ? AND user_id = ?",
                               (conv_id, user_id)).fetchone()
        return json.loads(row[0]) if row else None

    def clear_harness_pending(self, conv_id: str, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM harness_pending WHERE conv_id = ? AND user_id = ?", (conv_id, user_id))

    def claim_harness_reference(self, conv_id: str, user_id: str, cid: int) -> dict[str, Any] | None:
        """Consume exactly one offered reference, atomically, scoped to its owner."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT payload FROM harness_pending WHERE conv_id = ? AND user_id = ?",
                               (conv_id, user_id)).fetchone()
            if not row:
                return None
            payload = json.loads(row[0])
            selected = next((item for item in payload.get("references", [])
                             if isinstance(item, dict) and item.get("cid") == cid), None)
            if not selected:
                return None
            conv = conn.execute("SELECT messages FROM conversations WHERE id = ? AND user_id = ?",
                                (conv_id, user_id)).fetchone()
            if not conv:
                return None
            messages = json.loads(conv[0])
            selected_text = f"Seleccionaste {selected['name']} (PubChem {cid})."
            messages.append({"role": "assistant", "content": selected_text, "references": [selected]})
            conn.execute("UPDATE conversations SET messages = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                         (json.dumps(messages, ensure_ascii=False), time.time(), conv_id, user_id))
            conn.execute("DELETE FROM harness_pending WHERE conv_id = ? AND user_id = ?", (conv_id, user_id))
            payload["selection_text"] = selected_text
            return payload

    def add_message(self, conv_id: str, user_id: str, role: str, content: str, *,
                    references: list[dict[str, Any]] | None = None,
                    evidence: list[dict[str, Any]] | None = None,
                    comparison_cids: list[int] | None = None,
                    suggested_actions: list[dict[str, Any]] | None = None) -> None:
        conv = self.get_conversation(conv_id, user_id)
        if conv is None:
            raise ConversationNotFound(conv_id)
        conv.add_message(role, content)
        if references:
            conv.messages[-1]["references"] = references
        if evidence:
            conv.messages[-1]["evidence"] = evidence
        if comparison_cids is not None:
            conv.messages[-1]["comparison_cids"] = comparison_cids
        if suggested_actions is not None:
            conv.messages[-1]["suggested_actions"] = suggested_actions
        with self._connect() as conn:
            conn.execute(
                "UPDATE conversations SET messages = ?, updated_at = ? "
                "WHERE id = ? AND user_id = ?",
                (json.dumps(conv.messages, ensure_ascii=False), conv.updated_at,
                 conv_id, user_id))

    def set_summary(self, conv_id: str, user_id: str, summary: str) -> None:
        if self.get_conversation(conv_id, user_id) is None:
            raise ConversationNotFound(conv_id)
        with self._connect() as conn:
            conn.execute(
                "UPDATE conversations SET summary = ? WHERE id = ? AND user_id = ?",
                (summary, conv_id, user_id))

    def set_molecule_context(self, conv_id: str, user_id: str,
                             context: dict[str, Any] | None) -> None:
        if self.get_conversation(conv_id, user_id) is None:
            raise ConversationNotFound(conv_id)
        with self._connect() as conn:
            conn.execute(
                "UPDATE conversations SET molecule_context = ? WHERE id = ? AND user_id = ?",
                (json.dumps(context, ensure_ascii=False) if context else None,
                 conv_id, user_id))

    def record_molecule(self, conv_id: str, user_id: str, name: str,
                        smiles: str, props: dict[str, Any]) -> None:
        if self.get_conversation(conv_id, user_id) is None:
            raise ConversationNotFound(conv_id)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO session_molecules (conv_id, name, smiles, props, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (conv_id, name, smiles, json.dumps(props, ensure_ascii=False),
                 time.time()))

    def session_molecules(self, conv_id: str, user_id: str) -> list[dict[str, Any]]:
        if self.get_conversation(conv_id, user_id) is None:
            raise ConversationNotFound(conv_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, smiles, props FROM session_molecules "
                "WHERE conv_id = ? ORDER BY id ASC", (conv_id,)).fetchall()
        seen: set[str] = set()
        molecules: list[dict[str, Any]] = []
        for name, smiles, props in rows:
            if name in seen:
                continue
            seen.add(name)
            molecules.append({"name": name, "smiles": smiles,
                              "props": json.loads(props)})
        return molecules

    def search_messages(self, query: str, user_id: str, limit: int = 10) -> list[dict[str, str]]:
        """Substring search over one owner's messages only (LIKE, no FTS)."""
        terms = [t for t in query.lower().split() if len(t) >= 3]
        if not terms:
            return []
        hits: list[dict[str, str]] = []
        for conv in self.list_conversations(user_id):
            for message in conv.messages:
                content = message.get("content", "")
                lowered = content.lower()
                if all(term in lowered for term in terms):
                    hits.append({"conv_id": conv.id, "role": message.get("role", ""),
                                 "snippet": content[:160]})
                    if len(hits) >= limit:
                        return hits
        return hits

    def recent_context(self, conv: Conversation, keep: int = 12) -> tuple[list[dict[str, str]], str]:
        """Recent meaningful messages plus a deterministic compression of the rest."""
        meaningful = _meaningful(conv.messages)
        if len(meaningful) <= keep + 5:
            return conv.messages, conv.summary
        if conv.summary:
            return meaningful[-keep:], conv.summary
        return meaningful[-keep:], _quick_compress(meaningful[:-keep])
