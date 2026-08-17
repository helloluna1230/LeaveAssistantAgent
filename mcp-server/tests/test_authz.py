"""Authorization / cross-user isolation tests -- the security core of the demo."""

from datetime import date

import pytest

from leave_mcp import service
from leave_mcp.auth import authenticate
from leave_mcp.schemas import ErrorCode, LeaveError


def principal(emp: str):
    return authenticate(emp)


def test_employee_cannot_read_other_balance():
    with pytest.raises(LeaveError) as exc:
        service.get_leave_balance(principal("E1001"), employee_id="E1002")
    assert exc.value.code == ErrorCode.FORBIDDEN


def test_employee_id_argument_is_ignored_for_self():
    # Supplying your OWN id is fine; the identity still comes from the token.
    result = service.get_leave_balance(principal("E1001"), employee_id="E1001")
    assert all(b["employee_id"] == "E1001" for b in result["balances"])


def test_spoofed_employee_id_does_not_escalate():
    # Caller is E1001 but asks for E1002 -> denied, not served as E1002.
    with pytest.raises(LeaveError) as exc:
        service.get_leave_history(
            principal("E1001"), date(2026, 1, 1), date(2026, 12, 31), employee_id="E1002"
        )
    assert exc.value.code == ErrorCode.FORBIDDEN


def test_manager_can_read_report_balance_summary():
    result = service.get_leave_balance(principal("M1001"), employee_id="E1001")
    assert result["balances"][0]["employee_id"] == "E1001"


def test_manager_cannot_read_report_history():
    # History is outside the manager's limited view.
    with pytest.raises(LeaveError) as exc:
        service.get_leave_history(
            principal("M1001"), date(2026, 1, 1), date(2026, 12, 31), employee_id="E1001"
        )
    assert exc.value.code == ErrorCode.FORBIDDEN


def test_manager_cannot_read_non_report():
    # M1001 manages E1001/E1002 only; E9999 is not a report.
    with pytest.raises(LeaveError) as exc:
        service.get_leave_balance(principal("M1001"), employee_id="E9999")
    assert exc.value.code == ErrorCode.FORBIDDEN


def test_forbidden_message_does_not_leak_target():
    with pytest.raises(LeaveError) as exc:
        service.get_leave_balance(principal("E1002"), employee_id="E1001")
    # Message must not reveal existence, balance, or identity of the target.
    assert "E1001" not in exc.value.message
