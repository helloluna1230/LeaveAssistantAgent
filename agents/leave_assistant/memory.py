"""ContextProvider that injects the current user's saved preferences per run.

The persistence layer lives in `preference_store.py` (no agent_framework
dependency). Swap it for a Foundry Memory Store in production; the get/set/delete
interface is identical. Business data (balances, history) is NEVER written here.
"""

from __future__ import annotations

import json

from agent_framework import ContextProvider

from ..harness.runtime import start_run
from .identity import current_principal
from .observability import traced
from .preference_store import store


class UserPreferenceProvider(ContextProvider):
    """Injects the current user's saved leave preferences into each run."""

    DEFAULT_SOURCE_ID = "user_preferences"

    def __init__(self) -> None:
        super().__init__(self.DEFAULT_SOURCE_ID)

    async def before_run(self, *, agent, session, context, state, **kwargs) -> None:
        # Start a fresh harness budget for this run (step/tool-call caps + retry).
        start_run()
        try:
            principal = current_principal()
        except Exception:  # noqa: BLE001 - no identity yet; nothing to inject
            return
        with traced("memory.read", user_id=principal.employee_id):
            prefs = store.get(principal.employee_id)
        if prefs:
            context.extend_instructions(
                self.source_id,
                "The current user's saved leave preferences (private to them): "
                f"{json.dumps(prefs, ensure_ascii=False)}. Apply them unless the "
                "current request overrides them.",
            )
