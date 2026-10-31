"""Sequential audited execution, with explicit plan-bound human approval.

Fase 3 evolution (backward compatible): resolves /2 bindings against prior
step results, follows async jobs to terminal states, persists to an injected
store, enforces budgets, and resumes interrupted executions without
re-executing anything. Every addition is injected; without store/jobs the
executor behaves exactly as before.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .bridge import BridgeTransportError, MolDesignBridge
from .orchestration.budget import Budget, BudgetExceeded, BudgetTracker
from .orchestration.jobs import JobTracker
from .orchestration.store import TERMINAL as STORE_TERMINAL, ExecutionStore
from .plan import BindingError, Plan, is_binding, resolve_binding
from .tools import PlanValidationError, capability


@dataclass
class StepOutcome:
    id: str
    capability: str
    state: str
    timestamp: str
    result: Any = None
    result_sha256: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ExecutionReport:
    plan: dict[str, Any]
    plan_digest: str
    outcomes: list[StepOutcome]
    state: str
    approvals: dict[str, Any] = field(default_factory=lambda: {"digest": None, "steps": []})

    def as_dict(self) -> dict[str, Any]:
        return {"schema": "moldesign.molchat.execution/1", "plan": self.plan,
                "plan_digest": self.plan_digest, "state": self.state,
                "approvals": self.approvals,
                "outcomes": [o.as_dict() for o in self.outcomes]}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wrap_result(value: Any) -> tuple[Any, str]:
    """(report-safe result, sha256): bytes hash over raw bytes, else canonical JSON."""
    if isinstance(value, bytes):
        digest = "sha256:" + sha256(value).hexdigest()
        return {"encoding": "base64", "data": base64.b64encode(value).decode("ascii")}, digest
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return value, "sha256:" + sha256(raw).hexdigest()


class AgentExecutor:
    def __init__(self, bridge: MolDesignBridge, *, store: ExecutionStore | None = None,
                 jobs: JobTracker | None = None, budget: Budget | None = None) -> None:
        self.bridge = bridge
        self.store = store
        self.jobs = jobs
        self.budget = budget or Budget()

    async def execute(
        self, plan: Plan, *, approval_digest: str | None = None,
        approved_steps: set[str] | None = None,
    ) -> ExecutionReport:
        # Freeze a validated snapshot before checking the signature, avoiding
        # any mutation of the original caller's nested dict while running.
        frozen = Plan.from_dict(plan.as_dict())
        digest = frozen.digest
        if self.store is not None:
            current = self.store.get_state(digest)
            if current in STORE_TERMINAL:
                # Already decided: idempotent no-op, never a second send.
                return self._stored_report(digest)
            self.store.save_plan(digest, frozen.as_dict(),
                                 "approved" if approval_digest else "planned")
            self.store.set_state(digest, "running")
        return await self._run_steps(frozen, digest, {}, [], approval_digest,
                                     approved_steps or set(), {},
                                     BudgetTracker(self.budget))

    async def resume(
        self, digest: str, *, approval_digest: str | None = None,
        approved_steps: set[str] | None = None,
    ) -> ExecutionReport:
        """Continue a stored execution. Completed steps never re-execute."""
        if self.store is None:
            raise ValueError("resume needs an injected store")
        plan_dict = self.store.get_plan(digest)
        if plan_dict is None:
            raise KeyError(f"plan desconocido: {digest}")
        state = self.store.get_state(digest)
        if state in STORE_TERMINAL:
            if state == "ambiguous":
                recovered = await self._resume_ambiguous(
                    digest, plan_dict, approval_digest, approved_steps)
                if recovered is not None:
                    return recovered
            return self._stored_report(digest)
        stored = self.store.outcomes(digest)
        frozen = Plan.from_dict(plan_dict)
        results = {o["id"]: o["result"] for o in stored if o["state"] == "completed"}
        outcomes = [StepOutcome(id=o["id"], capability=o.get("capability", ""),
                                state=o["state"], timestamp=o.get("timestamp", _now()),
                                result=o["result"], result_sha256=o.get("result_sha256"),
                                error=o.get("error")) for o in stored]
        pending = {job["step_id"]: job
                   for job in self.store.pending_jobs(digest)}
        self.store.set_state(digest, "running", "reanudación")
        return await self._run_steps(frozen, digest, results, outcomes, approval_digest,
                                     approved_steps or set(), pending,
                                     BudgetTracker(self.budget))

    def _stored_report(self, digest: str) -> ExecutionReport:
        assert self.store is not None
        plan_dict = self.store.get_plan(digest)
        assert plan_dict is not None
        stored = self.store.outcomes(digest)
        outcomes = [StepOutcome(id=o["id"], capability=o.get("capability", ""),
                                state=o["state"], timestamp=o.get("timestamp", _now()),
                                result=o["result"], result_sha256=o.get("result_sha256"),
                                error=o.get("error")) for o in stored]
        state = self.store.get_state(digest)
        assert state is not None
        return ExecutionReport(plan_dict, digest, outcomes,
                               {"done": "completed"}.get(state, state))

    async def _try_reconcile(self, key: str | None) -> dict[str, Any] | None:
        """Ask the platform what a lost response left (CR-06). None if unknown."""
        if key is None:
            return None
        try:
            vista = await self.bridge.call(
                "reconcile_operation", {"idempotency_key": key})
        except Exception:  # noqa: BLE001 - reconcile failing keeps ambiguity
            return None
        return vista if isinstance(vista, dict) else None

    async def _resume_ambiguous(
        self, digest: str, plan_dict: dict[str, Any],
        approval_digest: str | None, approved_steps: set[str] | None,
    ) -> ExecutionReport | None:
        """Recover an ambiguous plan via reconcile. None when still unknown."""
        assert self.store is not None
        stored = self.store.outcomes(digest)
        ambiguous = [o for o in stored if o["state"] == "ambiguous"]
        if not ambiguous:
            return None
        adopted: dict[str, Any] = {}
        for outcome in ambiguous:
            vista = await self._try_reconcile(f"{digest}:{outcome['id']}")
            if vista is None or vista.get("status") != "COMPLETADA" \
                    or not isinstance(vista.get("response"), dict):
                return None  # still unknown: keep the stored ambiguous report
            adopted[outcome["id"]] = vista["response"]
        frozen = Plan.from_dict(plan_dict)
        results = {o["id"]: o["result"] for o in stored if o["state"] == "completed"}
        outcomes = [StepOutcome(id=o["id"], capability=o.get("capability", ""),
                                state=o["state"], timestamp=o.get("timestamp", _now()),
                                result=o["result"], result_sha256=o.get("result_sha256"),
                                error=o.get("error")) for o in stored
                    if o["state"] != "ambiguous"]
        pending = {job["step_id"]: job for job in self.store.pending_jobs(digest)}
        self.store.reopen(digest, "reconciliación CR-06")
        return await self._run_steps(frozen, digest, results, outcomes, approval_digest,
                                     approved_steps or set(), pending,
                                     BudgetTracker(self.budget), adopted)

    async def _run_steps(self, frozen: Plan, digest: str, results: dict[str, Any],
                         outcomes: list[StepOutcome], approval_digest: str | None,
                         approved_steps: set[str], pending_jobs: dict[str, dict],
                         tracker: BudgetTracker,
                         adopted: dict[str, Any] | None = None) -> ExecutionReport:
        report = await self._run_steps_inner(
            frozen, digest, results, outcomes, approval_digest, approved_steps,
            pending_jobs, tracker, adopted or {})
        report.approvals = {"digest": approval_digest, "steps": sorted(approved_steps)}
        return report

    async def _run_steps_inner(self, frozen: Plan, digest: str, results: dict[str, Any],
                               outcomes: list[StepOutcome], approval_digest: str | None,
                               approved_steps: set[str], pending_jobs: dict[str, dict],
                               tracker: BudgetTracker,
                               adopted: dict[str, Any]) -> ExecutionReport:
        done_ids = {o.id for o in outcomes if o.state == "completed"}
        for step in frozen.steps:
            if step.id in done_ids:
                continue
            tool = capability(step.capability)
            try:
                tracker.check_time()
            except BudgetExceeded as exc:
                return self._terminal(frozen, digest, outcomes, "blocked", step,
                                      f"Presupuesto excedido: {exc}")
            if tool.risk != "read":
                if approval_digest != digest or step.id not in approved_steps:
                    outcomes.append(StepOutcome(
                        step.id, step.capability, "awaiting_approval", _now(),
                        error="Requiere aprobación humana ligada a la huella del plan",
                    ))
                    self._record(digest, outcomes[-1])
                    self._set_state(digest, "in_review")
                    return ExecutionReport(frozen.as_dict(), digest, outcomes, "awaiting_approval")
            try:
                arguments = self._resolve_arguments(tool.name, step.arguments, results)
            except (BindingError, PlanValidationError) as exc:
                return self._terminal(frozen, digest, outcomes, "blocked", step,
                                      f"Binding sin resolver: {exc}")
            pending = pending_jobs.pop(step.id, None)
            if step.id in adopted:
                # Reconciled earlier (CR-06): adopt the recorded response as
                # the result. Nothing is sent; the claim is untouched.
                value = adopted[step.id]
                outcome_state = "completed"
                self._mark_key(f"{digest}:{step.id}", "reconciled")
            else:
                idempotency_key, verdict = self._effectful_key(
                    digest, step, tool.risk, arguments)
                if verdict == "duplicate":
                    return self._terminal(
                        frozen, digest, outcomes, "ambiguous", step,
                        "Operación ya enviada con la misma clave y parámetros: "
                        "sin reenvío automático. Inspecciona o reconcilia primero.")
                if verdict == "conflict":
                    return self._terminal(
                        frozen, digest, outcomes, "blocked", step,
                        "Clave de idempotencia con otros parámetros: rehusado.")
                try:
                    if pending is not None and self.jobs is not None:
                        follow = {"evaluation": self.jobs.follow_evaluation,
                                  "batch": self.jobs.follow_batch,
                                  "molcy": self.jobs.follow_molcy}[pending["kind"]]
                        job = await follow(
                            pending["remote_id"], digest=digest, step_id=step.id,
                            job_id=pending["job_id"])
                        value = {"resumed_job": job.remote_id, "final": job.status,
                                      "polls": job.polls}
                        outcome_state = {"done": "completed", "failed": "failed",
                                         "cancelled": "cancelled"}[job.outcome]
                    else:
                        value = await self.bridge.call(
                            step.capability, arguments, idempotency_key=idempotency_key)
                        outcome_state = "completed"
                        self._mark_key(idempotency_key, "acked")
                except BridgeTransportError as exc:
                    # No response received. Reads just fail; effectful steps
                    # reconcile first (CR-06, a read): a COMPLETADA key adopts
                    # its recorded response — not a resend.
                    if tool.risk == "read":
                        outcomes.append(StepOutcome(
                            step.id, step.capability, "failed", _now(),
                            error=f"{type(exc).__name__}: {exc}"))
                        self._record(digest, outcomes[-1])
                        self._set_state(digest, "failed")
                        return ExecutionReport(frozen.as_dict(), digest, outcomes, "failed")
                    vista = await self._try_reconcile(idempotency_key)
                    status = vista.get("status") if vista else None
                    adopted_response = vista.get("response") if vista else None
                    if status == "COMPLETADA" and isinstance(adopted_response, dict):
                        value = adopted_response
                        outcome_state = "completed"
                        self._mark_key(idempotency_key, "reconciled")
                    else:
                        self._mark_key(idempotency_key, "ambiguous")
                        note = ("la plataforma confirma que el efecto no se produjo; "
                                "repetir con un plan nuevo es seguro (nueva clave)") \
                            if status == "FALLIDA" else \
                            "Sin reenvío automático; reconcilia antes de repetir."
                        outcomes.append(StepOutcome(
                            step.id, step.capability, "ambiguous", _now(),
                            error=f"Respuesta perdida tras enviar {tool.name}: {exc}. {note}"))
                        self._record(digest, outcomes[-1])
                        self._set_state(digest, "ambiguous")
                        return ExecutionReport(frozen.as_dict(), digest, outcomes, "ambiguous")
                except Exception as exc:
                    # Abort on errors. Never silently re-run write-capable tools.
                    if step.capability == "create_docking_proposal" \
                            and getattr(exc, "status_code", None) == 409:
                        detail = (getattr(exc, "detail", None) or "").lower()
                        if "bloque" in detail or "preflight" in detail:
                            return self._terminal(
                                frozen, digest, outcomes, "blocked", step,
                                "El preflight del servidor bloquea esta evaluación: "
                                "no se creó ninguna propuesta aprobable.")
                    outcomes.append(StepOutcome(step.id, step.capability, "failed", _now(),
                                                error=f"{type(exc).__name__}: {exc}"))
                    self._record(digest, outcomes[-1])
                    self._set_state(digest, "failed")
                    return ExecutionReport(frozen.as_dict(), digest, outcomes, "failed")
            report_value, sha = _wrap_result(value)
            # Scientific decision remains in MolDesign. Its actual preflight
            # contract exposes technical_blockers, warnings and not_evaluated;
            # we stop on blockers or an unexpected contract, never assume pass.
            if step.capability == "check_preflight":
                blockers = value.get("technical_blockers") if isinstance(value, dict) else None
                if not isinstance(blockers, list):
                    outcomes.append(StepOutcome(
                        step.id, step.capability, "failed", _now(), result=report_value,
                        result_sha256=sha,
                        error="MolDesign no devolvió technical_blockers como lista",
                    ))
                    self._record(digest, outcomes[-1])
                    self._set_state(digest, "failed")
                    return ExecutionReport(frozen.as_dict(), digest, outcomes, "failed")
                if blockers:
                    return self._finish_outcome(frozen, digest, outcomes, step, report_value,
                                                sha, "blocked",
                                                "El preflight encontró bloqueantes técnicos; requiere intervención")
            if outcome_state == "completed":
                try:
                    followed = await self._maybe_follow(digest, step, tool.risk, value)
                except Exception as exc:
                    outcomes.append(StepOutcome(
                        step.id, step.capability, "failed", _now(),
                        error=f"seguimiento del trabajo falló: {exc}"))
                    self._record(digest, outcomes[-1])
                    self._set_state(digest, "failed")
                    return ExecutionReport(frozen.as_dict(), digest, outcomes, "failed")
                if followed is not None:
                    outcome_state, report_value, sha, follow_error = followed
                    if outcome_state in ("failed", "cancelled", "blocked"):
                        terminal = {"failed": "failed", "cancelled": "cancelled"}.get(
                            outcome_state, "blocked")
                        outcomes.append(StepOutcome(
                            step.id, step.capability, outcome_state, _now(),
                            result=report_value, result_sha256=sha, error=follow_error))
                        self._record(digest, outcomes[-1])
                        self._set_state(digest, terminal)
                        return ExecutionReport(frozen.as_dict(), digest, outcomes, terminal)
            outcomes.append(StepOutcome(
                step.id, step.capability, outcome_state, _now(), result=report_value,
                result_sha256=sha,
            ))
            self._record(digest, outcomes[-1])
            results[step.id] = value
        self._set_state(digest, "done")
        return ExecutionReport(frozen.as_dict(), digest, outcomes, "completed")

    def _effectful_key(self, digest: str, step: Any, risk: str,
                         arguments: dict[str, Any]) -> tuple[str | None, str]:
        """(key, verdict) for an effectful step; reads get (None, "claimed").

        Without a store the key is still generated and sent (future CR-06
        server dedup) but nothing is claimed locally.
        """
        if risk == "read":
            return None, "claimed"
        key = f"{digest}:{step.id}"
        if self.store is None:
            return key, "claimed"
        params_hash = sha256(json.dumps(
            arguments, sort_keys=True, ensure_ascii=False,
            separators=(",", ":")).encode("utf-8")).hexdigest()
        return key, self.store.claim_key(key, digest, step.id, params_hash)

    def _mark_key(self, key: str | None, state: str) -> None:
        if key is not None and self.store is not None:
            self.store.mark_key(key, state)

    def _resolve_arguments(self, tool_name: str, arguments: dict[str, Any],
                           results: dict[str, Any]) -> dict[str, Any]:
        tool = capability(tool_name)
        fields = tool.required | tool.optional
        resolved: dict[str, Any] = {}
        for key, value in arguments.items():
            if not is_binding(value):
                resolved[key] = value
                continue
            leaf = resolve_binding(value["$from"], results)
            fields[key].validate(key, leaf)  # types checked on resolve
            resolved[key] = leaf
        return resolved

    async def _maybe_follow(self, digest: str, step: Any, risk: str,
                            value: Any) -> tuple | None:
        """Follow write-step jobs to terminal states. None when nothing to follow."""
        if self.jobs is None or not isinstance(value, dict) or risk == "read":
            return None
        kind = remote_id = None
        if isinstance(value.get("task_id"), str):
            kind, remote_id = "evaluation", value["task_id"]
        elif isinstance(value.get("batch_id"), str):
            kind, remote_id = "batch", value["batch_id"]
        elif step.capability == "request_case_video" and isinstance(value.get("id"), str):
            kind, remote_id = "molcy", value["id"]
        if kind is None or remote_id is None:
            return None
        self._set_state(digest, "waiting_job", step.id)
        try:
            if kind == "evaluation":
                job = await self.jobs.follow_evaluation(
                    remote_id, digest=digest, step_id=step.id)
            elif kind == "molcy":
                job = await self.jobs.follow_molcy(
                    remote_id, digest=digest, step_id=step.id)
            else:
                job = await self.jobs.follow_batch(
                    remote_id, digest=digest, step_id=step.id)
        except BudgetExceeded as exc:
            self._set_state(digest, "running")
            wrapped, sha = _wrap_result(value)
            return ("blocked", wrapped, sha, f"Presupuesto excedido: {exc}")
        self._set_state(digest, "running")
        final = {"submitted": value, "final": job.status, "polls": job.polls}
        wrapped, sha = _wrap_result(final)
        if job.outcome == "done":
            return ("completed", wrapped, sha, None)
        if job.outcome == "cancelled":
            return ("cancelled", wrapped, sha, "trabajo cancelado")
        ended = job.status.get("status", job.status.get("estado"))
        return ("failed", wrapped, sha, f"el trabajo terminó: {ended}")

    def _terminal(self, frozen: Plan, digest: str, outcomes: list[StepOutcome],
                  state: str, step: Any, error: str) -> ExecutionReport:
        outcomes.append(StepOutcome(step.id, step.capability, state, _now(), error=error))
        self._record(digest, outcomes[-1])
        self._set_state(digest, state)
        report_state = {"done": "completed"}.get(state, state)
        return ExecutionReport(frozen.as_dict(), digest, outcomes, report_state)

    def _finish_outcome(self, frozen: Plan, digest: str, outcomes: list[StepOutcome],
                        step: Any, result: Any, sha: str | None, state: str,
                        error: str) -> ExecutionReport:
        outcomes.append(StepOutcome(step.id, step.capability, state, _now(),
                                    result=result, result_sha256=sha, error=error))
        self._record(digest, outcomes[-1])
        self._set_state(digest, state)
        return ExecutionReport(frozen.as_dict(), digest, outcomes, state)

    def _record(self, digest: str, outcome: StepOutcome) -> None:
        if self.store is not None:
            self.store.record_outcome(digest, outcome.as_dict())

    def _set_state(self, digest: str, state: str, detail: str = "") -> None:
        if self.store is not None:
            self.store.set_state(digest, state, detail)


def save_report(report: ExecutionReport, path: str | Path) -> None:
    """Write the full evidence report locally; caller chooses the location."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # The CLI never writes logs to a cloud endpoint. Replace atomically.
    import os
    import tempfile
    name: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent,
                                         prefix=".molchat-", suffix=".tmp", delete=False) as out:
            name = out.name
            json.dump(report.as_dict(), out, ensure_ascii=False, indent=2)
            out.write("\n")
        os.replace(name, destination)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
