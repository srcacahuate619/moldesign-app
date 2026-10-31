"""Async job following: poll with backoff, cancel, resume.

Polling is the source of truth; one SSE window waits for live progress
first (bounded, falls back to polling on anything unexpected). Unknown
remote states keep polling until the budget trips — never assumed terminal.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .budget import BudgetExceeded, BudgetTracker
from .store import ExecutionStore

EVAL_DONE = "SUCCESS"
EVAL_FAILED = "FAILURE"
BATCH_DONE = "completed"
BATCH_CANCELLED = "cancelled"
MOLCY_DONE = "completo"
MOLCY_FAILED = "fallido"
MOLCY_CANCELLED = "cancelado"


@dataclass
class JobResult:
    kind: str  # "evaluation" | "batch"
    remote_id: str
    outcome: str  # done | failed | cancelled
    status: dict[str, Any] = field(default_factory=dict)
    polls: int = 0


class JobTracker:
    def __init__(self, bridge: Any, store: ExecutionStore | None = None,
                 budget: BudgetTracker | None = None,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 base_delay: float = 2.0, max_delay: float = 30.0,
                 jitter: float = 0.2) -> None:
        self._bridge = bridge
        self._store = store
        self._budget = budget or BudgetTracker()
        self._sleep = sleep
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._jitter = jitter

    async def follow_evaluation(self, task_id: str, *, digest: str = "",
                                step_id: str = "", job_id: int | None = None) -> JobResult:
        return await self._follow("evaluation", task_id, digest, step_id, job_id)

    async def follow_batch(self, batch_id: str, *, digest: str = "",
                           step_id: str = "", job_id: int | None = None) -> JobResult:
        return await self._follow("batch", batch_id, digest, step_id, job_id)

    async def follow_molcy(self, remote_id: str, *, digest: str = "",
                         step_id: str = "", job_id: int | None = None) -> JobResult:
        return await self._follow("molcy", remote_id, digest, step_id, job_id)

    async def cancel(self, kind: str, remote_id: str) -> dict[str, Any]:
        if kind == "evaluation":
            return await self._bridge.call("cancel_evaluation", {"task_id": remote_id})
        if kind == "batch":
            return await self._bridge.call("cancel_batch", {"batch_id": remote_id})
        if kind == "molcy":
            return await self._bridge.call("cancel_molcy_job", {"job_id": remote_id})
        raise ValueError(f"tipo de trabajo desconocido: {kind}")

    async def _follow(self, kind: str, remote_id: str, digest: str,
                      step_id: str, job_id: int | None) -> JobResult:
        self._budget.check_job_start()
        try:
            return await self._follow_inner(kind, remote_id, digest, step_id, job_id)
        finally:
            self._budget.release_job()

    async def _follow_inner(self, kind: str, remote_id: str, digest: str,
                            step_id: str, job_id: int | None) -> JobResult:
        row_id = job_id
        if self._store is not None and digest:
            row_id = job_id or self._store.save_job(digest, step_id, kind, remote_id)
        polls = 0
        status = await self._poll(kind, remote_id)
        polls += 1
        outcome = self._outcome(kind, status)
        if outcome is not None:
            return self._finish(row_id, kind, remote_id, outcome, status, polls)
        await self._await_stream(kind, remote_id)
        delay = self._base_delay
        while True:
            if polls >= self._budget.budget.max_polls_per_job:
                raise BudgetExceeded(f"límite de sondeos ({polls}) siguiendo {remote_id}")
            self._budget.check_time()
            await self._sleep(delay + random.uniform(0, delay * self._jitter))
            delay = min(delay * 2, self._max_delay)
            status = await self._poll(kind, remote_id)
            polls += 1
            if row_id and self._store is not None:
                self._store.update_job(row_id, "running", status)
            outcome = self._outcome(kind, status)
            if outcome is not None:
                return self._finish(row_id, kind, remote_id, outcome, status, polls)

    async def _poll(self, kind: str, remote_id: str) -> dict[str, Any]:
        if kind == "evaluation":
            result = await self._bridge.call("evaluation_status", {"task_id": remote_id})
        elif kind == "molcy":
            result = await self._bridge.call("molcy_job_status", {"job_id": remote_id})
        else:
            result = await self._bridge.call("batch_status", {"batch_id": remote_id})
        return result if isinstance(result, dict) else {}

    async def _await_stream(self, kind: str, remote_id: str) -> None:
        """One bounded SSE wait; anything unexpected falls back to polling."""
        if kind != "evaluation":
            return
        try:
            await self._bridge.call("stream_evaluation", {"task_id": remote_id})
        except Exception:  # noqa: BLE001 - the poll loop is the fallback
            pass

    @staticmethod
    def _outcome(kind: str, status: dict[str, Any]) -> str | None:
        # Molcy reports `estado`; evaluations and batches report `status`.
        state = status.get("estado") if kind == "molcy" else status.get("status")
        if kind == "evaluation":
            if state == EVAL_DONE:
                return "done"
            if state == EVAL_FAILED:
                return "failed"
            return None
        if kind == "molcy":
            if state == MOLCY_DONE:
                return "done"
            if state == MOLCY_FAILED:
                return "failed"
            if state == MOLCY_CANCELLED:
                return "cancelled"
            return None
        if state == BATCH_DONE:
            return "done"
        if state == BATCH_CANCELLED:
            return "cancelled"
        if status.get("error") and state not in ("running", "cancelling"):
            return "failed"
        return None

    def _finish(self, row_id: int | None, kind: str, remote_id: str,
                outcome: str, status: dict[str, Any], polls: int) -> JobResult:
        if row_id and self._store is not None:
            self._store.update_job(row_id, outcome, status)
        return JobResult(kind=kind, remote_id=remote_id, outcome=outcome,
                         status=status, polls=polls)
