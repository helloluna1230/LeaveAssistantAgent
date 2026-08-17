"""Resolve an API-key-gated simulated caller id to a trusted employee.

SECURITY BOUNDARY (demo):
- The MCP transport validates the shared API key before exposing a caller id.
- This module maps that caller id to the simulated employee directory.
- Tool arguments never establish identity; service.py authorizes every call
    against the resolved Principal.
"""

from __future__ import annotations

from dataclasses import dataclass

from .mock_data import EMPLOYEES
from .schemas import ErrorCode, LeaveError, Role


@dataclass(frozen=True)
class Principal:
    """The trusted, verified caller identity. Source of truth for authorization."""

    employee_id: str
    name: str
    role: Role
    manager_of: tuple[str, ...] = ()

    @property
    def is_manager(self) -> bool:
        return self.role == Role.MANAGER


def authenticate(token: str | None) -> Principal:
    """Resolve a transport-gated caller id, or raise UNAUTHORIZED."""
    if not token:
        raise LeaveError(ErrorCode.UNAUTHORIZED, "Missing caller identity.")
    token = token.removeprefix("Bearer ").strip()
    return _principal_for(token)


def _principal_for(employee_id: str | None) -> Principal:
    emp = EMPLOYEES.get(employee_id) if employee_id else None
    if not employee_id or emp is None:
        raise LeaveError(ErrorCode.UNAUTHORIZED, "Caller is not a known employee.")
    return Principal(
        employee_id=employee_id,
        name=emp["name"],
        role=Role(emp["role"]),
        manager_of=tuple(emp.get("manager_of", ())),
    )
