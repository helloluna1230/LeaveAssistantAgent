from datetime import date

import pytest

from leave_mcp import service
from leave_mcp.auth import authenticate
from leave_mcp.schemas import ErrorCode, LeaveError


def principal(emp: str):
    return authenticate(emp)


def test_get_own_balance():
    result = service.get_leave_balance(principal("E1001"))
    annual = next(b for b in result["balances"] if b["leave_type"] == "annual_leave")
    assert annual["remaining_days"] == 9
    assert annual["expiring_days"] == 3
    assert result["simulated"] is True


def test_balance_filter_by_type():
    result = service.get_leave_balance(principal("E1001"), leave_type="sick_leave")
    assert len(result["balances"]) == 1
    assert result["balances"][0]["leave_type"] == "sick_leave"


def test_unsupported_leave_type():
    with pytest.raises(LeaveError) as exc:
        service.get_leave_balance(principal("E1001"), leave_type="unicorn_leave")
    assert exc.value.code == ErrorCode.LEAVE_TYPE_NOT_SUPPORTED


def test_history_within_range():
    result = service.get_leave_history(
        principal("E1001"), date(2026, 1, 1), date(2026, 4, 1)
    )
    ids = {i["record_id"] for i in result["items"]}
    assert ids == {"H-E1001-01", "H-E1001-02"}


def test_history_empty_result_is_not_error():
    result = service.get_leave_history(
        principal("M1001"), date(2026, 1, 1), date(2026, 1, 31)
    )
    assert result["items"] == []


def test_history_invalid_range():
    with pytest.raises(LeaveError) as exc:
        service.get_leave_history(principal("E1001"), date(2026, 5, 1), date(2026, 1, 1))
    assert exc.value.code == ErrorCode.INVALID_DATE_RANGE


def test_faulty_employee_triggers_service_unavailable():
    with pytest.raises(LeaveError) as exc:
        service.get_leave_balance(principal("E9999"))
    assert exc.value.code == ErrorCode.SERVICE_UNAVAILABLE


def test_leave_types_and_holidays():
    types = service.get_leave_types(principal("E1002"))
    assert len(types["leave_types"]) == 3
    holidays = service.get_public_holidays(principal("E1002"), 2026)
    assert holidays["year"] == 2026
    assert any("国庆" in h["name"] or "National" in h["name"] for h in holidays["holidays"])


def test_leave_preview_within_balance():
    # E1001 has 9 annual days remaining; request 1 business day.
    result = service.create_leave_request_preview(
        principal("E1001"), "annual_leave", date(2026, 11, 9), date(2026, 11, 9)
    )
    assert result["status"] == "pending_confirmation"
    assert result["requested_days"] == 1
    assert result["remaining_after"] == 8
    assert result["simulated"] is True


def test_leave_preview_insufficient_balance():
    # E1002 has only 1 annual day remaining; request a long span.
    with pytest.raises(LeaveError) as exc:
        service.create_leave_request_preview(
            principal("E1002"), "annual_leave", date(2026, 11, 2), date(2026, 11, 30)
        )
    assert exc.value.code == ErrorCode.INSUFFICIENT_LEAVE_BALANCE
