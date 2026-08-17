"""Per-request simulated identity for the agent.

The frontend forwards the selected demo employee id. This module keeps that id in
a contextvar and resolves it through the same simulated directory as the MCP.
The downstream MCP independently requires its server-to-server API key before it
accepts the forwarded id.
"""

from __future__ import annotations

import contextvars
import os

# Imported via sys.path bootstrap in agents.leave_assistant.__init__.
from leave_mcp.auth import Principal, authenticate  # noqa: E402

_current_user_token: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_user_token", default=None
)


def set_current_user_token(token: str | None) -> contextvars.Token:
    return _current_user_token.set(token)


def reset_current_user_token(reset_token: contextvars.Token) -> None:
    _current_user_token.reset(reset_token)


def current_user_token() -> str | None:
    return _current_user_token.get()


def current_principal() -> Principal:
    """Verified caller identity for the current request (raises UNAUTHORIZED if absent/invalid)."""
    token = _current_user_token.get()
    if not token:
        # Foundry HOSTED runtime does not run our identity middleware, so no
        # x-user-token reaches in-process tools (planning/preferences). In the
        # single-user hosted demo, fall back to the configured demo identity so
        # those local tools work. The MCP server still re-authorizes every call
        # independently (via the toolbox connection's forwarded identity); this
        # fallback never weakens that boundary and only applies when no verified
        # token is present AND DEMO_DEFAULT_USER is set.
        demo = os.environ.get("DEMO_DEFAULT_USER", "").strip()
        if demo:
            token = demo
    return authenticate(token)


def demo_token_for(employee_id: str) -> str:
    """Return a directory-validated demo identity for frontend compatibility."""
    return authenticate(employee_id).employee_id
