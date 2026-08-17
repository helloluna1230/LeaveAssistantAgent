"""Lifecycle hook helpers for the harness: step/tool-call caps and audit spans.

These are framework-agnostic helpers the entrypoint can attach as middleware or
call from tool wrappers. They enforce the limits declared in `config.py` so the
agent cannot loop indefinitely or exceed its tool budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import DEFAULT, HarnessConfig


class HarnessLimitExceeded(Exception):
    pass


@dataclass
class RunBudget:
    config: HarnessConfig = field(default_factory=lambda: DEFAULT)
    steps: int = 0
    tool_calls: int = 0

    def on_step(self) -> None:
        self.steps += 1
        if self.steps > self.config.max_steps:
            raise HarnessLimitExceeded(f"Exceeded max steps ({self.config.max_steps}).")

    def on_tool_call(self, name: str) -> None:
        self.tool_calls += 1
        if self.tool_calls > self.config.max_tool_calls:
            raise HarnessLimitExceeded(f"Exceeded max tool calls ({self.config.max_tool_calls}).")
