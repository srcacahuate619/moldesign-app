"""Persistent plan states and resumable jobs (SQLite).

State machine: planned → in_review → approved → running → (waiting_job) →
done | blocked | failed | cancelled. Every transition is logged with its
timestamp; plans in running/waiting_job re-link to their remote ids on
resume. Nothing is ever re-executed.
"""

from __future__ import annotations

from contextlib import contextmanager, suppress
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterator

STATES = ("planned", "in_review", "approved", "running", "waiting_job",
          "done", "blocked", "failed", "cancelled", "ambiguous")
TERMINAL = frozenset({"done", "blocked", "failed", "cancelled", "ambiguous"})
JOB_ACTIVE = ("submitted", "running", "waiting")
JOB_TERMINAL = frozenset({"done", "failed", "cancelled"})


class StoreError(RuntimeError):
    """The execution store failed. Never a silent None."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExecutionStore:
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
            raise StoreError(f"no se pudo abrir {self._path}: {exc}") from exc
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            raise StoreError(f"{self._path} falló la operación: {exc}") from exc
        finally:
            with suppress(sqlite3.Error):
                conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS executions (
                    digest TEXT PRIMARY KEY,
                    plan_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS outcomes (
                    digest TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    capability TEXT NOT NULL DEFAULT '',
                    state TEXT NOT NULL,
                    result_json TEXT,
                    result_sha256 TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (digest, step_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    digest TEXT NOT NULL,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    digest TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    remote_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    last_status_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS idempotency (
                    key TEXT PRIMARY KEY,
                    digest TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    params_hash TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def save_plan(self, digest: str, plan: dict[str, Any],
                  state: str = "planned") -> None:
        if state not in STATES:
            raise ValueError(f"estado desconocido: {state}")
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO executions VALUES (?, ?, ?, ?, ?)",
                (digest, json.dumps(plan, ensure_ascii=False), state, now, now))

    def get_plan(self, digest: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT plan_json FROM executions WHERE digest = ?", (digest,)).fetchone()
        return json.loads(row[0]) if row else None

    def get_state(self, digest: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state FROM executions WHERE digest = ?", (digest,)).fetchone()
        return row[0] if row else None

    def set_state(self, digest: str, state: str, detail: str = "") -> None:
        if state not in STATES:
            raise ValueError(f"estado desconocido: {state}")
        current = self.get_state(digest)
        if current is None:
            raise KeyError(f"plan desconocido: {digest}")
        if current in TERMINAL and state != current:
            raise ValueError(f"estado terminal {current}: no admite {state}")
        with self._connect() as conn:
            conn.execute("UPDATE executions SET state = ?, updated_at = ? WHERE digest = ?",
                         (state, _now(), digest))
            conn.execute("INSERT INTO transitions (digest, from_state, to_state, created_at, detail)"
                         " VALUES (?, ?, ?, ?, ?)", (digest, current, state, _now(), detail))

    def record_outcome(self, digest: str, outcome: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO outcomes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (digest, outcome["id"], outcome.get("capability", ""),
                 outcome["state"],
                 json.dumps(outcome.get("result"), ensure_ascii=False, default=str)
                 if outcome.get("result") is not None else None,
                 outcome.get("result_sha256"), outcome.get("error"), _now()))

    def outcomes(self, digest: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT step_id, capability, state, result_json, result_sha256, error,"
                " created_at FROM outcomes WHERE digest = ? ORDER BY step_id",
                (digest,)).fetchall()
        return [{"id": r[0], "capability": r[1], "state": r[2],
                 "result": json.loads(r[3]) if r[3] is not None else None,
                 "result_sha256": r[4], "error": r[5], "timestamp": r[6]}
                for r in rows]

    def transitions(self, digest: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT from_state, to_state, created_at, detail FROM transitions"
                " WHERE digest = ? ORDER BY id", (digest,)).fetchall()
        return [{"from": r[0], "to": r[1], "at": r[2], "detail": r[3]} for r in rows]

    def save_job(self, digest: str, step_id: str, kind: str, remote_id: str) -> int:
        now = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO jobs (digest, step_id, kind, remote_id, state,"
                " last_status_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 'submitted', NULL, ?, ?)",
                (digest, step_id, kind, remote_id, now, now))
            return int(cursor.lastrowid or 0)

    def update_job(self, job_id: int, state: str,
                   last_status: dict[str, Any] | None = None) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE jobs SET state = ?, last_status_json = ?, updated_at = ?"
                         " WHERE id = ?",
                         (state, json.dumps(last_status, ensure_ascii=False, default=str)
                          if last_status is not None else None, _now(), job_id))

    def pending_jobs(self, digest: str | None = None) -> list[dict[str, Any]]:
        query = ("SELECT id, digest, step_id, kind, remote_id, state FROM jobs"
                 + (" WHERE digest = ?" if digest else ""))
        params: tuple = (digest,) if digest else ()
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [{"job_id": r[0], "digest": r[1], "step_id": r[2], "kind": r[3],
                 "remote_id": r[4], "state": r[5]} for r in rows
                if r[5] not in JOB_TERMINAL]

    def resumable(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT digest FROM executions WHERE state IN ('running', 'waiting_job')").fetchall()
        return [row[0] for row in rows]

    def claim_key(self, key: str, digest: str, step_id: str, params_hash: str
                  ) -> str:
        """Claim an idempotency key before sending (single transaction).

        Returns "claimed" (first use), "duplicate" (same key + same params:
        must NOT resend), or "conflict" (same key, different params: refuse).
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT params_hash FROM idempotency WHERE key = ?", (key,)).fetchone()
            if row is not None:
                return "duplicate" if row[0] == params_hash else "conflict"
            conn.execute("INSERT INTO idempotency VALUES (?, ?, ?, ?, 'sent', ?)",
                         (key, digest, step_id, params_hash, _now()))
            return "claimed"

    def mark_key(self, key: str, state: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE idempotency SET state = ? WHERE key = ?", (state, key))

    def reopen(self, digest: str, detail: str = "") -> None:
        """ambiguous -> running: the only escape from a terminal state.

        Used solely by CR-06 recovery (adopting a recorded response, never
        resending). Every other terminal state stays final.
        """
        current = self.get_state(digest)
        if current != "ambiguous":
            raise ValueError(f"solo ambiguous se reabre, no {current}")
        with self._connect() as conn:
            conn.execute("UPDATE executions SET state = 'running', updated_at = ?"
                         " WHERE digest = ?", (_now(), digest))
            conn.execute("INSERT INTO transitions (digest, from_state, to_state, created_at, detail)"
                         " VALUES (?, 'ambiguous', 'running', ?, ?)",
                         (digest, _now(), detail))
