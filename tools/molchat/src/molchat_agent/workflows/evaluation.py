"""One molecule evaluated in a case, and the two signals that say it is over.

The iteration used to learn that a run was over by trying to load the next molecule and reading «busy». That mixed
two different questions. They are now asked separately, each to its owner:

1. **Is the result ready, and what is it?** Asked to MolDesign's backend by ``task_id`` until the job is terminal.
   Vina's energy for the best pose and that pose's physical controls are read from there. This is the number the
   iteration decides on, and it is available before the window has finished closing the run.
2. **Can the case take another molecule?** Asked to the window with the read-only host action ``case_status``. Only
   needed when the iteration goes on: if the molecule meets the rule, nothing else is loaded.

Each reading keeps how long each signal took, so the first runs in the app measure what was only guessed before.
"""
from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from ..lang import tr
from .run_record import record_from_result

TERMINAL = frozenset({"SUCCESS", "FAILURE", "FAILED", "CANCELLED", "CANCELED", "REVOKED"})
FREE_STATES = frozenset({"idle"})
WAIT_STATES = frozenset({"busy"})


class EvaluationHost(Protocol):
    """What one evaluation needs from the window that owns the case."""

    async def load_smiles(self, case_name: str, smiles: str) -> dict[str, Any]: ...
    async def evaluate(self, case_name: str) -> dict[str, Any]: ...
    async def case_status(self, case_name: str) -> dict[str, Any]: ...


class EvaluationPlatform(Protocol):
    """What one evaluation reads from MolDesign's backend."""

    async def job(self, task_id: str) -> dict[str, Any]: ...
    async def top_pose(self, task_id: str) -> dict[str, Any]: ...


@dataclass
class EvaluationReading:
    status: str  # evaluated | failed | timeout | unknown
    task_id: str | None = None
    molecule_id: str | None = None
    vina_kcal: float | None = None
    physical_status: str | None = None
    reason: str | None = None
    seconds_to_start: float | None = None  # waiting for the case, loading and starting
    seconds_to_result: float | None = None  # from the start of the run to the backend's terminal state
    retried_for: str | None = None  # why the run was repeated once (the machine ran out of memory), if it was
    run: dict[str, Any] | None = None  # what MolDesign said about the run besides the number (see run_record)


@dataclass
class FreeReading:
    status: str  # idle | busy (still, when the wait ran out) | not_found | ambiguous | failed | unknown
    seconds: float
    run_state: str | None = None
    asked: int = 0


def _out_of_memory(reason: str | None) -> bool:
    """Vina's own words when the machine cannot give it memory («Error: insufficient memory!»)."""
    return bool(reason) and "insufficient memory" in reason.lower()


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


class EvaluationStep:
    def __init__(self, host: EvaluationHost, platform: EvaluationPlatform, *,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 poll_s: float = 3.0, busy_wait_s: float = 5.0, busy_budget_s: float = 240.0,
                 memory_wait_s: float = 20.0, on_wait: Callable[[str | None], None] | None = None) -> None:
        self.host, self.platform = host, platform
        self._clock, self._sleep = clock, sleep
        self._poll_s, self._busy_wait_s, self._busy_budget_s = poll_s, busy_wait_s, busy_budget_s
        self._memory_wait_s = memory_wait_s
        self._on_wait = on_wait or (lambda _message: None)

    async def wait_until_free(self, case_name: str, budget_s: float | None = None) -> FreeReading:
        """Ask the window until the case can take another molecule. ``unknown`` comes back at once (an older window
        without ``case_status``, or no case workspace open): the caller then relies on «busy» when it loads."""
        budget = self._busy_budget_s if budget_s is None else min(self._busy_budget_s, budget_s)
        began, asked, announced = self._clock(), 0, False
        while True:
            answer = await self.host.case_status(case_name)
            asked += 1
            status = answer.get("status") if isinstance(answer, dict) else None
            run_state = answer.get("run_state") if isinstance(answer, dict) and isinstance(answer.get("run_state"), str) else None
            waited = self._clock() - began
            if status not in WAIT_STATES or waited + self._busy_wait_s > budget:
                if announced:
                    self._on_wait(None)
                return FreeReading(status if isinstance(status, str) else "unknown", round(waited, 1), run_state, asked)
            if not announced:
                announced = True
                self._on_wait(tr("MolDesign sigue cerrando la corrida anterior; espero a que el caso quede libre.",
                                 "MolDesign is still closing the previous run; waiting for the case to be free."))
            await self._sleep(self._busy_wait_s)

    async def _until_not_busy(self, call: Callable[[], Awaitable[dict[str, Any]]], budget: float) -> tuple[dict[str, Any], float]:
        """Fallback for a window that answered ``case_status`` with ``unknown``: repeat the call while it says «busy»
        (nothing was done, so repeating is safe). ``unknown`` is never repeated."""
        began = self._clock()
        while True:
            result = await call()
            waited = self._clock() - began
            if not isinstance(result, dict) or result.get("status") != "busy" or waited + self._busy_wait_s > budget:
                return result, waited
            await self._sleep(self._busy_wait_s)

    async def evaluate(self, case_name: str, smiles: str, *, timeout_s: float, budget_s: float | None = None) -> EvaluationReading:
        """Load ``smiles`` in the case, start the run and read Vina's energy when the backend says it is over."""
        budget = self._busy_budget_s if budget_s is None else min(self._busy_budget_s, budget_s)
        began = self._clock()
        loaded, waited = await self._until_not_busy(lambda: self.host.load_smiles(case_name, smiles), budget)
        if loaded.get("status") != "applied":
            return EvaluationReading("failed", reason=(
                tr(f"MolDesign siguió ocupado {waited:.0f} s y no se cargó la molécula en el caso.",
                   f"MolDesign stayed busy for {waited:.0f} s and the molecule was not loaded into the case.")
                if loaded.get("status") == "busy"
                else tr(f"No se cargó la molécula en el caso («{loaded.get('status')}»).",
                        f"The molecule was not loaded into the case (“{loaded.get('status')}”).")))
        reading = await self._start_and_read(case_name, budget, timeout_s, began)
        if reading.status == "failed" and _out_of_memory(reading.reason):
            # Vina could not get memory from the machine (another program was using it). The failed run left nothing
            # behind, so it is safe to wait for the case to be free and start it once more; a second failure stays.
            first = reading.reason
            await self._sleep(self._memory_wait_s)
            await self.wait_until_free(case_name, budget)
            reading = await self._start_and_read(case_name, budget, timeout_s, self._clock())
            reading.retried_for = "memoria"
            if reading.status == "failed" and _out_of_memory(reading.reason):
                reading.reason = f"{first} " + tr(
                    f"Se repitió una vez tras {self._memory_wait_s:g} s y volvió a faltar memoria: "
                    "el equipo no tenía memoria libre para Vina.",
                    f"It was repeated once after {self._memory_wait_s:g} s and ran out of memory again: "
                    "the computer had no free memory for Vina.")
        return reading

    async def _start_and_read(self, case_name: str, budget: float, timeout_s: float, began: float) -> EvaluationReading:
        started, waited = await self._until_not_busy(lambda: self.host.evaluate(case_name), budget)
        status, task_id = started.get("status"), started.get("task_id")
        if status == "unknown":
            return EvaluationReading("unknown", reason=tr(
                "No se pudo confirmar si la evaluación empezó; no se repitió para no duplicarla.",
                "Could not confirm whether the run started; it was not repeated, so as not to run it twice."))
        if status not in {"started", "started_unregistered"} or not isinstance(task_id, str):
            reason = started.get("reason") if isinstance(started.get("reason"), str) else None
            return EvaluationReading("failed", reason=(
                tr(f"MolDesign siguió ocupado {waited:.0f} s y no inició la evaluación.",
                   f"MolDesign stayed busy for {waited:.0f} s and did not start the run.") if status == "busy"
                else tr(f"MolDesign no inició la evaluación («{status}»)", f"MolDesign did not start the run (“{status}”)")
                + (f": {reason}" if reason else ".")))
        run_began = self._clock()
        reading = EvaluationReading("running", task_id=task_id, seconds_to_start=round(run_began - began, 1))
        job = await self._follow(task_id, timeout_s)
        reading.seconds_to_result = round(self._clock() - run_began, 1)
        if job is None:
            reading.status, reading.reason = "timeout", tr(f"La evaluación no terminó en {timeout_s:g} s.",
                                                           f"The run did not finish in {timeout_s:g} s.")
            return reading
        if job.get("status") != "SUCCESS" or not isinstance(job.get("result"), dict):
            error = job.get("error") if isinstance(job.get("error"), str) else None
            reading.status = "failed"
            reading.reason = tr(f"La evaluación terminó en {job.get('status')}", f"The run ended as {job.get('status')}") + (
                f": {error[:200]}" if error else ".")
            return reading
        result = job["result"]
        reading.run = record_from_result(result)
        reading.vina_kcal = _number(result.get("affinity_kcal"))
        molecule_id = result.get("molecule_id")
        reading.molecule_id = molecule_id if isinstance(molecule_id, str) else None
        top = await self.platform.top_pose(task_id)
        reading.physical_status = top.get("physical_status") if isinstance(top.get("physical_status"), str) else None
        reading.status = "evaluated"
        return reading

    async def _follow(self, task_id: str, timeout_s: float) -> dict[str, Any] | None:
        deadline = self._clock() + timeout_s
        while True:
            job = await self.platform.job(task_id)
            if isinstance(job, dict) and job.get("status") in TERMINAL:
                return job
            if self._clock() >= deadline:
                return None
            await self._sleep(self._poll_s)
