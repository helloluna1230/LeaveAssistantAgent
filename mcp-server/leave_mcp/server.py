"""FastMCP server exposing the simulated HR leave tools over streamable HTTP.

The shared API key gates every caller identity. A Starlette middleware validates
it before capturing `x-user-token` into a contextvar so each tool can resolve the
trusted Principal. Tools never trust an employee_id supplied in tool arguments.
"""

from __future__ import annotations

import contextvars
import os
from datetime import date

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from . import service
from .auth import authenticate
from .schemas import LeaveError

_current_token: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_token", default=None
)


def _transport_security() -> TransportSecuritySettings:
    """DNS-rebinding protection config.

    When MCP_ALLOWED_HOSTS is set (comma-separated Host values, e.g. the Container
    App FQDN), protection stays ON with that allow-list. Without it, protection is
    disabled — the deployment then relies on ingress + per-request API-key auth.
    """
    hosts = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    origins = [o.strip() for o in os.environ.get("MCP_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    if hosts or origins:
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=origins,
        )
    return TransportSecuritySettings(enable_dns_rebinding_protection=False)


mcp = FastMCP(
    name="leave-hr-mock",
    instructions=(
        "Mock HR leave service. ALL DATA IS SIMULATED. Identity is derived only "
        "from the API-key-gated caller token, never from tool arguments."
    ),
    transport_security=_transport_security(),
)


def _principal():
    return authenticate(_current_token.get())


def _guard(fn, *args, **kwargs) -> dict:
    try:
        return fn(_principal(), *args, **kwargs)
    except LeaveError as exc:
        return exc.to_dict()


@mcp.tool(
    description="Return fresh simulated balances for the authenticated employee, optionally filtered by exact "
    "leave_type. Use for remaining, used, or expiring days; not policy rules or leave history."
)
def get_leave_balance(leave_type: str | None = None) -> dict:
    return _guard(service.get_leave_balance, leave_type=leave_type)


@mcp.tool(
    description="Return the authenticated employee's simulated leave records in an inclusive date range, "
    "optionally filtered by exact leave_type. Use for past or pending records; not current balances."
)
def get_leave_history(
    start_date: date,
    end_date: date,
    leave_type: str | None = None,
) -> dict:
    return _guard(
        service.get_leave_history,
        start_date=start_date,
        end_date=end_date,
        leave_type=leave_type,
    )


@mcp.tool(
    description="List canonical leave_type values and simulated accrual, carryover, and expiry rules. "
    "Use for policy metadata or when the leave type is ambiguous; this does not return employee balances."
)
def get_leave_types() -> dict:
    return _guard(service.get_leave_types)


@mcp.tool(
    description="Return simulated public-holiday dates for one calendar year (default 2026). "
    "Use for schedule planning and business-day checks; not leave balances or policy rules."
)
def get_public_holidays(year: int = 2026) -> dict:
    return _guard(service.get_public_holidays, year=year)


@mcp.tool(
    description="Validate one hypothetical leave request and return its simulated business-day count and "
    "remaining balance. This non-binding preview never creates or submits a leave record."
)
def create_leave_request_preview(leave_type: str, start_date: date, end_date: date) -> dict:
    return _guard(
        service.create_leave_request_preview,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
    )


class _AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        expected = os.environ.get("MCP_API_KEY", "")
        provided = request.headers.get("x-api-key") or request.headers.get(
            "authorization", ""
        ).removeprefix("Bearer ").strip()
        token = (
            request.headers.get("x-user-token") or request.headers.get("x-user-id")
            if expected and provided == expected
            else None
        )
        reset = _current_token.set(token)
        try:
            return await call_next(request)
        finally:
            _current_token.reset(reset)


def build_app():
    app = mcp.streamable_http_app()
    app.add_middleware(_AuthContextMiddleware)
    return app


app = build_app()


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
