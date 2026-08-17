"""End-to-end authorization boundary: identity token -> verified principal ->
server-side authz. Proves that model/client-supplied ids cannot escalate access.
"""

from datetime import date

import pytest

from agents.leave_assistant import identity
from leave_mcp import service
from leave_mcp.schemas import ErrorCode, LeaveError


def as_user(emp: str):
    identity.set_current_user_token(identity.demo_token_for(emp))
    return identity.current_principal()


def test_impersonation_via_employee_id_is_denied():
    # Caller authenticated as E1001 but tries to read E1002 by passing employee_id.
    principal = as_user("E1001")
    with pytest.raises(LeaveError) as exc:
        service.get_leave_balance(principal, employee_id="E1002")
    assert exc.value.code == ErrorCode.FORBIDDEN


def test_history_cross_user_denied():
    principal = as_user("E1002")
    with pytest.raises(LeaveError) as exc:
        service.get_leave_history(
            principal, date(2026, 1, 1), date(2026, 12, 31), employee_id="E1001"
        )
    assert exc.value.code == ErrorCode.FORBIDDEN


def test_manager_summary_only_not_history():
    manager = as_user("M1001")
    # Allowed: report balance summary.
    assert service.get_leave_balance(manager, employee_id="E1001")["balances"]
    # Denied: report detailed history.
    with pytest.raises(LeaveError) as exc:
        service.get_leave_history(manager, date(2026, 1, 1), date(2026, 12, 31), employee_id="E1001")
    assert exc.value.code == ErrorCode.FORBIDDEN


def test_denial_does_not_leak_target_identity():
    principal = as_user("E1001")
    with pytest.raises(LeaveError) as exc:
        service.get_leave_balance(principal, employee_id="E1002")
    assert "E1002" not in exc.value.message
