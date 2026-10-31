"""Bounded hypothesis cycle (§14): screen, propose, approve, run, compare.

Available capabilities only: researcher-provided candidates (no CR-05
analogs), demo-dataset properties (CR-01 pending, labeled), preflight,
proposals (CR-07), approvals, jobs, history, Molcy video. Nothing here is
autonomous: screening and comparison run as code, but every effectful step
returns a pending approval the researcher must confirm by digest. The next
iteration only starts when the driver calls again — "continue" is a human
act, not a loop. The session file is an *expediente*, never a MolDesign
case (CR-02 pending, declared).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from ..executor import AgentExecutor, ExecutionReport
from ..plan import Plan
from .budget import Budget, BudgetExceeded
from .jobs import JobTracker
from .store import ExecutionStore

PropertiesFn = Callable[[str], Awaitable[dict[str, Any] | None]]
NarratorFn = Callable[[str], Awaitable[str]]


@dataclass(frozen=True)
class HypothesisBudget:
    max_iterations: int = 3
    max_runs: int = 3  # approved docking launches per session
    max_time_s: float = 3600.0


@dataclass
class Candidate:
    smiles: str
    index: int
    properties: dict[str, Any] | None = None
    preflight: dict[str, Any] | None = None
    eligible: bool = False
    reason: str = ""
    rank: int = 0


@dataclass
class Screening:
    objective: str
    target: str
    candidates: list[Candidate]

    def ranked(self) -> list[Candidate]:
        return sorted(self.candidates, key=lambda c: c.rank)


@dataclass
class PendingApproval:
    plan: dict[str, Any]
    digest: str
    candidate: Candidate
    sensitive_steps: list[str]


@dataclass
class IterationRecord:
    index: int
    screening: Screening
    pending: PendingApproval | None = None
    decision: str = "pending"  # pending | approved | declined | no_candidate
    report: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
    synthesis: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "objective": self.screening.objective,
            "target": self.screening.target,
            "candidates": [
                {"smiles": c.smiles, "rank": c.rank, "eligible": c.eligible,
                 "reason": c.reason,
                 "blockers": (c.preflight or {}).get("technical_blockers", []),
                 "warnings": (c.preflight or {}).get("warnings", [])}
                for c in self.screening.ranked()],
            "plan": self.pending.plan if self.pending else None,
            "plan_digest": self.pending.digest if self.pending else None,
            "decision": self.decision,
            "report": self.report,
            "comparison": self.comparison,
            "synthesis": self.synthesis,
        }


def rank_key(candidate: Candidate) -> tuple:
    """Documented deterministic order (no affinity signal exists pre-docking).

    Eligible first, fewer warnings first, Lipinski pass first, input order
    last. Affinity ranking happens only post-evaluation, in compare().
    """
    preflight = candidate.preflight or {}
    props = candidate.properties or {}
    drug = props.get("druglikeness") or {}
    return (0 if candidate.eligible else 1,
            len(preflight.get("warnings", []) or []),
            0 if drug.get("lipinski") else 1,
            candidate.index)


def compare_result(result: dict[str, Any],
                   history: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic post-evaluation comparison (code, never prose numbers)."""
    affinity = result.get("affinity_kcal")
    past = [h.get("affinity_kcal") for h in history
            if isinstance(h.get("affinity_kcal"), (int, float))]
    best_past = min(past) if past else None  # more negative binds better
    comparison: dict[str, Any] = {
        "affinity_kcal": affinity,
        "history_runs": len(history),
        "history_best_kcal": best_past,
        "delta_vs_best": (round(affinity - best_past, 3)
                          if isinstance(affinity, (int, float))
                          and best_past is not None else None),
        "verdict": "sin referencia previa" if best_past is None
        else ("mejora el mejor histórico" if affinity < best_past
              else "no mejora el mejor histórico")
        if isinstance(affinity, (int, float)) else "sin afinidad medida",
    }
    return comparison


class HypothesisRunner:
    def __init__(self, *, bridge: Any, store: ExecutionStore,
                 jobs: JobTracker | None = None,
                 budget: HypothesisBudget | None = None,
                 properties: PropertiesFn | None = None,
                 narrator: NarratorFn | None = None) -> None:
        self._bridge = bridge
        self._store = store
        self._jobs = jobs
        self._budget = budget or HypothesisBudget()
        self._properties = properties
        self._narrator = narrator
        self._started = time.monotonic()
        self._iterations: list[IterationRecord] = []
        self._runs = 0

    @property
    def iterations(self) -> list[IterationRecord]:
        return list(self._iterations)

    def can_continue(self) -> tuple[bool, str]:
        if len(self._iterations) >= self._budget.max_iterations:
            return False, f"límite de iteraciones ({self._budget.max_iterations})"
        if self._runs >= self._budget.max_runs:
            return False, f"límite de corridas ({self._budget.max_runs})"
        elapsed = time.monotonic() - self._started
        # ">=": mismo contrato que BudgetTracker.check_time; un estricto ">"
        # hacia depender del reloj un presupuesto de 0 s.
        if elapsed >= self._budget.max_time_s:
            return False, f"tiempo excedido ({elapsed:.0f}s)"
        return True, "ok"

    async def screen(self, objective: str, target: str,
                     smiles_list: list[str]) -> Screening:
        """Preflight every candidate (audited read-only plans) and rank."""
        allowed, reason = self.can_continue()
        if not allowed:
            raise BudgetExceeded(reason)
        if not smiles_list:
            raise ValueError("sin candidatos: el investigador propone los SMILES")
        screening = Screening(objective=objective, target=target, candidates=[])
        executor = AgentExecutor(self._bridge, store=self._store, jobs=self._jobs,
                                 budget=Budget())
        for index, smiles in enumerate(smiles_list):
            candidate = Candidate(smiles=smiles, index=index)
            if self._properties is not None:
                try:
                    candidate.properties = await self._properties(smiles)
                except Exception:  # noqa: BLE001 - missing data, not a failure
                    candidate.properties = None
            plan = Plan.from_dict({
                "goal": f"Preflight de {smiles} contra {target}",
                "planner": "hypothesis-runner",
                "steps": [{"id": "s1", "capability": "check_preflight",
                           "arguments": {"smiles": smiles, "target_pdb_id": target},
                           "rationale": "cribado determinista"}],
            })
            report = await executor.execute(plan)
            if report.state == "completed":
                candidate.preflight = report.outcomes[0].result
                candidate.eligible = True
                candidate.reason = "apto para propuesta"
            elif report.state == "blocked":
                outcome = report.outcomes[0]
                candidate.preflight = outcome.result or {}
                candidate.eligible = False
                candidate.reason = outcome.error or "bloqueado por preflight"
            else:
                candidate.eligible = False
                candidate.reason = f"preflight {report.state}: " \
                    f"{(report.outcomes[0].error if report.outcomes else '')}"
            screening.candidates.append(candidate)
        ordered = sorted(screening.candidates, key=rank_key)
        for rank, candidate in enumerate(ordered, 1):
            candidate.rank = rank
        return screening

    def propose_run(self, screening: Screening,
                    iteration: int | None = None) -> IterationRecord:
        """Draft the create→approve plan for the best untried candidate.

        A candidate already proposed in an earlier iteration is never
        re-proposed: its plan digest is identical, so the executor would
        return the stored report and the "iteration" would launch nothing
        (measured live, Fase 5: round 2 replayed round 1's task_id).
        """
        tried = {r.pending.candidate.smiles for r in self._iterations
                 if r.pending is not None}
        best = next((c for c in screening.ranked()
                     if c.eligible and c.smiles not in tried), None)
        record = IterationRecord(
            index=len(self._iterations) + 1 if iteration is None else iteration,
            screening=screening)
        if best is None:
            record.decision = "no_candidate"
            self._iterations.append(record)
            return record
        plan = Plan.from_dict({
            "goal": f"Evaluar {best.smiles} contra {screening.target}",
            "planner": "hypothesis-runner", "schema": "/2",
            "steps": [
                {"id": "s1", "capability": "create_docking_proposal",
                 "arguments": {"smiles": best.smiles,
                               "target_pdb_id": screening.target},
                 "rationale": "propuesta revisable, sin lanzar"},
                {"id": "s2", "capability": "approve_docking_proposal",
                 "arguments": {"proposal_id": {"$from": "s1.proposal_id"},
                               "proposal_hash": {"$from": "s1.proposal_hash"}},
                 "rationale": "lanzar tras aprobación humana del hash"},
            ],
        })
        record.pending = PendingApproval(
            plan=plan.as_dict(), digest=plan.digest, candidate=best,
            sensitive_steps=["s1", "s2"])
        self._iterations.append(record)
        return record

    async def execute_run(self, record: IterationRecord, *,
                          approval_digest: str,
                          approved_steps: set[str]) -> ExecutionReport:
        """Run a pending plan. Approval must match the digest exactly."""
        if record.pending is None:
            raise ValueError("sin plan pendiente: nada que ejecutar")
        if approval_digest != record.pending.digest:
            raise ValueError("la aprobación no corresponde a esta huella")
        if self._runs >= self._budget.max_runs:
            raise BudgetExceeded(f"límite de corridas ({self._budget.max_runs})")
        plan = Plan.from_dict(record.pending.plan)
        executor = AgentExecutor(self._bridge, store=self._store, jobs=self._jobs,
                                 budget=Budget())
        report = await executor.execute(
            plan, approval_digest=approval_digest, approved_steps=approved_steps)
        record.decision = "approved"
        record.report = report.as_dict()
        self._runs += 1
        return report

    def decline_run(self, record: IterationRecord, reason: str = "") -> None:
        record.decision = "declined"
        if record.report is None:
            record.report = {}
        record.report["declined_reason"] = reason or "el investigador no aprobó"

    async def compare_and_report(self, record: IterationRecord) -> dict[str, Any]:
        """Fetch history, compare deterministically, synthesize prose if able."""
        if record.report is None or record.pending is None:
            raise ValueError("sin reporte de corrida: nada que comparar")
        outcomes = record.report.get("outcomes", [])
        final = {}
        for outcome in outcomes:
            result = outcome.get("result") or {}
            final = result.get("final", result)
        # Followed jobs nest the measured payload one level deeper:
        # final = {task_id, status, result: {affinity_kcal, molecule_id...}}.
        # Without unwrapping, affinity reads as null and every comparison
        # reports "sin afinidad medida" (measured live, Fase 5).
        if isinstance(final, dict) and isinstance(final.get("result"), dict):
            final = final["result"]
        target = record.screening.target
        history: list[dict[str, Any]] = []
        try:
            listing = await self._bridge.call(
                "list_evaluations", {"target_pdb_id": target})
            history = listing.get("items", []) if isinstance(listing, dict) else []
        except Exception:  # noqa: BLE001 - history missing is reported, not fatal
            history = []
        record.comparison = compare_result(final if isinstance(final, dict) else {},
                                           history)
        record.comparison["history_source"] = (
            f"list_evaluations {target}" if history else "sin historial")
        if self._narrator is not None:
            record.synthesis = await self._narrator(self._synthesis_prompt(record))
        return record.comparison

    def _synthesis_prompt(self, record: IterationRecord) -> str:
        candidate = record.pending.candidate.smiles if record.pending else "?"
        return (
            "Resume esta iteración de hipótesis en 5 líneas o menos, citando "
            "solo cifras del bloque COMPARACIÓN. No inventes afinidades ni "
            f"conclusiones clínicas.\nCANDIDATO: {candidate}\n"
            f"COMPARACIÓN: {json.dumps(record.comparison, ensure_ascii=False)}")

    def expediente(self) -> dict[str, Any]:
        return {"schema": "moldesign.molchat.expediente/1",
                "note": "Expediente de sesión propio; no es un caso de MolDesign.",
                "budget": {"max_iterations": self._budget.max_iterations,
                           "max_runs": self._budget.max_runs,
                           "runs_used": self._runs},
                "iterations": [r.as_dict() for r in self._iterations]}

    def save_expediente(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.expediente(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        return destination
