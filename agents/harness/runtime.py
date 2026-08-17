"""Per-request harness runtime: enforce step/tool-call budgets and retry transient
tool failures. Pure module (no agent_framework) so it is unit-testable and reused
by the tool layer.
"""

from __future__ import annotations

import contextvars
import time
from collections.abc import Callable
from typing import Any

from .config import DEFAULT, HarnessConfig, should_retry
from .hooks import HarnessLimitExceeded, RunBudget

_current_budget: contextvars.ContextVar[RunBudget | None] = contextvars.ContextVar(
    "run_budget", default=None
)


def start_run(config: HarnessConfig = DEFAULT) -> RunBudget:
    """Begin a new run budget for the current request/context."""
    budget = RunBudget(config=config)
    _current_budget.set(budget)
    return budget


def get_budget() -> RunBudget | None:
    return _current_budget.get()


def end_run() -> None:
    """Clear the active budget (e.g. after a run, or to isolate tests)."""
    _current_budget.set(None)


def note_tool_call(name: str) -> None:
    """Count a tool call against the active budget; raises if the cap is exceeded."""
    budget = _current_budget.get()
    if budget is not None:
        budget.on_tool_call(name)


def note_step() -> None:
    budget = _current_budget.get()
    if budget is not None:
        budget.on_step()


def should_retry_sleep(
    error_code: str,
    attempt: int,
    config: HarnessConfig = DEFAULT,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Return True (after backoff) if a transient error should be retried."""
    if should_retry(error_code, attempt, config):
        sleep(config.retry.backoff_seconds * (attempt + 1))
        return True
    return False


def run_with_retry(
    call: Callable[[], Any],
    error_code_of: Callable[[Any], str | None],
    *,
    config: HarnessConfig = DEFAULT,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Invoke `call`; if the result carries a retryable error code, retry per policy."""
    attempt = 0
    while True:
        result = call()
        code = error_code_of(result)
        if code and should_retry(code, attempt, config):
            attempt += 1
            sleep(config.retry.backoff_seconds * attempt)
            continue
        return result


__all__ = [
    "HarnessLimitExceeded",
    "start_run",
    "end_run",
    "get_budget",
    "note_tool_call",
    "note_step",
    "should_retry_sleep",
    "run_with_retry",
]
