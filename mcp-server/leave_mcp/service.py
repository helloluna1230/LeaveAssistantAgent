"""Business logic + server-side authorization for the mock HR MCP tools.

Authorization is enforced HERE, based on the verified `Principal` (never on
model/client-supplied ids). Regular employees can only see their own data.
A manager gets a LIMITED view of direct reports: balance summaries only, no
detailed history. Cross-user access is denied without revealing whether the
target exists (returns FORBIDDEN uniformly).
"""

from __future__ import annotations

import logging
from datetime import date

from .auth import Principal
from . import mock_data as data
from .schemas import (
    DateRange,
    ErrorCode,
    LeaveBalance,
    LeaveError,
    LeaveHistory,
    LeaveHistoryItem,
    LeaveRequestPreview,
    LeaveType,
    LeaveTypeInfo,
    PublicHolidays,
    PublicHoliday,
)

logger = logging.getLogger("leave_mcp.service")


def _log(principal: Principal, tool: str, detail: str = "") -> None:
    # Masked audit log: only the trusted caller + tool, never raw PII payloads.
    logger.info("tool=%s caller=%s %s", tool, _mask(principal.employee_id), detail)


def _mask(employee_id: str) -> str:
    return employee_id[:2] + "***" if len(employee_id) > 2 else "***"


def _resolve_target(principal: Principal, requested: str | None, *, manager_summary: bool) -> str:
    """Return the employee_id the caller is authorized to access, else FORBIDDEN.

    `requested` is treated as an untrusted hint. Identity always comes from the
    verified principal.
    """
    if requested is None or requested == principal.employee_id:
        return principal.employee_id
    if manager_summary and principal.is_manager and requested in principal.manager_of:
        return requested
    # Do not leak whether `requested` exists.
    _log(principal, "authz.deny", f"requested={_mask(requested)}")
    raise LeaveError(
        ErrorCode.FORBIDDEN,
        "You can only access leave information you are authorized to view.",
    )


def _check_faulty(employee_id: str) -> None:
    if employee_id == data.FAULTY_EMPLOYEE_ID:
        raise LeaveError(ErrorCode.SERVICE_UNAVAILABLE, "Simulated HR backend is unavailable.")


def _validate_leave_type(leave_type: str | None) -> str | None:
    if leave_type is None:
        return None
    try:
        return LeaveType(leave_type).value
    except ValueError as exc:
        raise LeaveError(
            ErrorCode.LEAVE_TYPE_NOT_SUPPORTED, f"Unsupported leave type: {leave_type}."
        ) from exc


def get_leave_balance(
    principal: Principal, employee_id: str | None = None, leave_type: str | None = None
) -> dict:
    target = _resolve_target(principal, employee_id, manager_summary=True)
    _check_faulty(target)
    lt = _validate_leave_type(leave_type)
    _log(principal, "get_leave_balance", f"target={_mask(target)} type={lt}")

    balances = data.BALANCES.get(target)
    if balances is None:
        raise LeaveError(ErrorCode.USER_NOT_FOUND, "No leave data for the requested user.")

    types = [lt] if lt else list(balances.keys())
    results: list[dict] = []
    for t in types:
        b = balances.get(t)
        if b is None:
            continue
        results.append(
            LeaveBalance(
                employee_id=target,
                leave_type=t,
                entitled_days=b["entitled_days"],
                used_days=b["used_days"],
                remaining_days=b["remaining_days"],
                expiring_days=b.get("expiring_days", 0),
                expiration_date=b.get("expiration_date"),
                as_of_date=data.AS_OF,
            ).model_dump(mode="json")
        )
    return {"balances": results, "as_of_date": data.AS_OF.isoformat(), "simulated": True}


def get_leave_history(
    principal: Principal,
    start_date: date,
    end_date: date,
    leave_type: str | None = None,
    employee_id: str | None = None,
) -> dict:
    # History is NOT part of the manager's limited view -> self only.
    target = _resolve_target(principal, employee_id, manager_summary=False)
    _check_faulty(target)
    if start_date > end_date:
        raise LeaveError(ErrorCode.INVALID_DATE_RANGE, "start_date must be on or before end_date.")
    lt = _validate_leave_type(leave_type)
    DateRange(start_date=start_date, end_date=end_date)
    _log(principal, "get_leave_history", f"target={_mask(target)} type={lt}")

    records = data.HISTORY.get(target, [])
    items: list[LeaveHistoryItem] = []
    for r in records:
        if r["end_date"] < start_date or r["start_date"] > end_date:
            continue
        if lt and r["leave_type"] != lt:
            continue
        items.append(LeaveHistoryItem(**r))

    return LeaveHistory(
        employee_id=target,
        start_date=start_date,
        end_date=end_date,
        items=items,
    ).model_dump(mode="json")


def get_leave_types(principal: Principal) -> dict:
    _log(principal, "get_leave_types")
    types = [LeaveTypeInfo(**t).model_dump(mode="json") for t in data.LEAVE_TYPES]
    return {"leave_types": types, "simulated": True}


def get_public_holidays(principal: Principal, year: int = 2026) -> dict:
    _log(principal, "get_public_holidays", f"year={year}")
    holidays = data.PUBLIC_HOLIDAYS.get(year)
    if holidays is None:
        raise LeaveError(ErrorCode.USER_NOT_FOUND, f"No holiday data for year {year}.")
    return PublicHolidays(
        year=year,
        holidays=[PublicHoliday(**h) for h in holidays],
    ).model_dump(mode="json")


def _business_days(start: date, end: date) -> int:
    holiday_days: set[date] = set()
    for h in data.PUBLIC_HOLIDAYS.get(start.year, []):
        d = h["start_date"]
        while d <= h["end_date"]:
            holiday_days.add(d)
            d = date.fromordinal(d.toordinal() + 1)
    count = 0
    d = start
    while d <= end:
        if d.weekday() < 5 and d not in holiday_days:
            count += 1
        d = date.fromordinal(d.toordinal() + 1)
    return count


def create_leave_request_preview(
    principal: Principal, leave_type: str, start_date: date, end_date: date
) -> dict:
    """Non-binding preview only. Never creates a real HR record (write-op gate)."""
    _check_faulty(principal.employee_id)
    lt = _validate_leave_type(leave_type)
    if lt is None:
        raise LeaveError(ErrorCode.LEAVE_TYPE_NOT_SUPPORTED, "leave_type is required.")
    if start_date > end_date:
        raise LeaveError(ErrorCode.INVALID_DATE_RANGE, "start_date must be on or before end_date.")

    requested = _business_days(start_date, end_date)
    balance = data.BALANCES.get(principal.employee_id, {}).get(lt)
    if balance is None:
        raise LeaveError(ErrorCode.LEAVE_TYPE_NOT_SUPPORTED, f"No {lt} balance available.")
    remaining = balance["remaining_days"]
    if requested > remaining:
        raise LeaveError(
            ErrorCode.INSUFFICIENT_LEAVE_BALANCE,
            f"Requested {requested} day(s) exceeds remaining {remaining}.",
        )
    _log(principal, "create_leave_request_preview", f"type={lt} days={requested}")
    return LeaveRequestPreview(
        request_id=f"PREVIEW-{principal.employee_id}-{start_date.isoformat()}",
        employee_id=principal.employee_id,
        leave_type=lt,
        start_date=start_date,
        end_date=end_date,
        requested_days=requested,
        remaining_after=remaining - requested,
        status="pending_confirmation",
    ).model_dump(mode="json")
