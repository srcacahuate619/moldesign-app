"""Background plan executions: submit, watch, cancel explicitly.

An execution runs an :class:`AgentExecutor` in a detached asyncio task: the
observer (SSE stream, UI tab) may disconnect without affecting the run —
cancelling is always the explicit ``cancel()`` call, which cancels the
*remote* jobs and marks the execution, never silently (MP-06). The runner
keeps ``cancelled`` once marked, attaching its final report as evidence.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from ..executor import AgentExecutor, ExecutionReport
from ..orchestration.budget import Budget
from ..orchestration.jobs import JobTracker
from ..orchestration.store import ExecutionStore
from ..plan import Plan

TERMINAL = frozenset({"completed", "failed", "blocked", "awaiting_approval",
                      "ambiguous", "cancelled"})


@dataclass
class ExecutionRecord:
    id: str
    digest: str
    state: str = "queued"
    report: dict[str, Any] | None = None
    cancel_requested: bool = False
    created_at: float = field(default_factory=time.time)


class ExecutionManager:
    def __init__(self, bridge: Any, store: ExecutionStore,
                 budget: Budget | None = None,
                 tracker_factory: Callable[..., JobTracker] | None = None,
                 ) -> None:
        self._bridge = bridge
        self._store = store
        self._budget = budget or Budget()
        self._tracker_factory = tracker_factory or (
            lambda: JobTracker(bridge, store=store))
        self._records: dict[str, ExecutionRecord] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def submit(self, plan: Plan, *, approval_digest: str | None = None,
               approved_steps: set[str] | None = None,
               platform_token: str | None = None) -> ExecutionRecord:
        """Queue a run. ``platform_token`` (hosted mode) binds this run to
        the request's identity instead of the manager's fixed bridge."""
        record = ExecutionRecord(id=uuid.uuid4().hex[:16], digest=plan.digest)
        self._records[record.id] = record
        task = asyncio.get_running_loop().create_task(
            self._run(record, plan, approval_digest, approved_steps or set(),
                      platform_token))
        self._tasks[record.id] = task
        task.add_done_callback(lambda _t, rid=record.id: self._tasks.pop(rid, None))
        return record

    def get(self, exec_id: str) -> ExecutionRecord | None:
        return self._records.get(exec_id)

    def view(self, record: ExecutionRecord) -> dict[str, Any]:
        return {"id": record.id, "digest": record.digest, "state": record.state,
                "report": record.report, "created_at": record.created_at}

    def _bound(self, platform_token: str | None) -> Any:
        if platform_token is None:
            return self._bridge
        return self._bridge.with_token(platform_token)

    def _tracker_for(self, bridge: Any) -> JobTracker:
        if bridge is self._bridge:
            return self._tracker_factory()
        return JobTracker(bridge, store=self._store)

    async def cancel(self, exec_id: str,
                     platform_token: str | None = None) -> tuple[bool, str]:
        """Cancel remote work and mark the execution. (True, detail) on change."""
        record = self._records.get(exec_id)
        if record is None:
            return False, "not-found"
        if record.state in TERMINAL:
            return False, f"already terminal: {record.state}"
        record.cancel_requested = True
        cancelled: list[str] = []
        tracker = self._tracker_for(self._bound(platform_token))
        for job in self._store.pending_jobs(record.digest):
            try:
                await tracker.cancel(job["kind"], job["remote_id"])
                cancelled.append(f"{job['kind']}:{job['remote_id']}")
            except Exception:  # noqa: BLE001 - best effort per job, reported below
                cancelled.append(f"{job['kind']}:{job['remote_id']}:FAILED")
        # Non-terminal: the runner lands "cancelled" with its final report.
        # Observers watching the event stream see the report arrive.
        record.state = "cancelling"
        if cancelled:
            return True, "cancelling: " + ", ".join(cancelled)
        return True, "cancelling (no remote jobs were pending)"

    async def _run(self, record: ExecutionRecord, plan: Plan,
                   approval_digest: str | None, approved_steps: set[str],
                   platform_token: str | None) -> None:
        record.state = "running"
        try:
            bridge = self._bound(platform_token)
            executor = AgentExecutor(bridge, store=self._store,
                                     jobs=self._tracker_for(bridge),
                                     budget=self._budget)
            report: ExecutionReport = await executor.execute(
                plan, approval_digest=approval_digest, approved_steps=approved_steps)
            record.report = report.as_dict()
            record.state = "cancelled" if record.cancel_requested else report.state
        except Exception as exc:  # noqa: BLE001 - a run must always land somewhere
            record.report = {"error": f"{type(exc).__name__}: {exc}"}
            record.state = "cancelled" if record.cancel_requested else "failed"
