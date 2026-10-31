"""Budgets and brakes: exceeding a limit blocks, never raises through."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    """A budget limit tripped. The executor maps this to blocked + reason."""


@dataclass(frozen=True)
class Budget:
    max_time_s: float = 600.0
    max_jobs: int = 1
    max_polls_per_job: int = 120


@dataclass
class BudgetTracker:
    budget: Budget = field(default_factory=Budget)

    def __post_init__(self) -> None:
        self.started = time.monotonic()
        self.jobs_started = 0

    def check_time(self) -> None:
        elapsed = time.monotonic() - self.started
        # ">=": at the limit you are over it. With a strict ">" a budget of
        # 0 s only tripped if the clock advanced between construction and the
        # first check (measured: it does not under some interpreter/OS pairs,
        # e.g. Windows + 3.12), so "no time allowed" let fast steps run.
        if elapsed >= self.budget.max_time_s:
            raise BudgetExceeded(f"tiempo excedido ({elapsed:.0f}s >= {self.budget.max_time_s:.0f}s)")

    def check_job_start(self) -> None:
        if self.jobs_started >= self.budget.max_jobs:
            raise BudgetExceeded(f"límite de trabajos concurrentes ({self.budget.max_jobs})")
        self.jobs_started += 1

    def release_job(self) -> None:
        self.jobs_started = max(0, self.jobs_started - 1)
