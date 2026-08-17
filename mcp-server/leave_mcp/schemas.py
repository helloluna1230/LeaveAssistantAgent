"""Shared schemas, enums, and error codes for the mock HR MCP server.

ALL DATA SERVED BY THIS SERVER IS SIMULATED and for demo purposes only.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
    LEAVE_TYPE_NOT_SUPPORTED = "LEAVE_TYPE_NOT_SUPPORTED"
    INSUFFICIENT_LEAVE_BALANCE = "INSUFFICIENT_LEAVE_BALANCE"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class LeaveError(Exception):
    """Raised by the service layer; maps to a structured error output."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict:
        return {"error": {"code": self.code.value, "message": self.message}, "simulated": True}


class LeaveType(str, Enum):
    ANNUAL = "annual_leave"
    SICK = "sick_leave"
    COMPENSATORY = "compensatory_leave"


class Role(str, Enum):
    EMPLOYEE = "employee"
    MANAGER = "manager"


# ---- Tool output models (documented output schema) ----


class LeaveBalance(BaseModel):
    employee_id: str
    leave_type: str
    entitled_days: float
    used_days: float
    remaining_days: float
    expiring_days: float = 0
    expiration_date: date | None = None
    as_of_date: date
    source: str = "simulated_hr_mcp"
    simulated: bool = True


class LeaveHistoryItem(BaseModel):
    record_id: str
    leave_type: str
    start_date: date
    end_date: date
    days: float
    status: str


class LeaveHistory(BaseModel):
    employee_id: str
    start_date: date
    end_date: date
    items: list[LeaveHistoryItem]
    source: str = "simulated_hr_mcp"
    simulated: bool = True


class LeaveTypeInfo(BaseModel):
    leave_type: str
    display_name: str
    unit: str = "day"
    accrual: str


class PublicHoliday(BaseModel):
    name: str
    start_date: date
    end_date: date


class PublicHolidays(BaseModel):
    year: int
    region: str = "CN"
    holidays: list[PublicHoliday]
    source: str = "simulated_hr_mcp"
    simulated: bool = True


class LeaveRequestPreview(BaseModel):
    request_id: str
    employee_id: str
    leave_type: str
    start_date: date
    end_date: date
    requested_days: float
    remaining_after: float
    status: str = "preview"  # preview | pending_confirmation | cancelled
    note: str = "This is a non-binding preview. No real HR record was created."
    simulated: bool = True


class DateRange(BaseModel):
    start_date: date = Field(..., description="Inclusive start date (YYYY-MM-DD)")
    end_date: date = Field(..., description="Inclusive end date (YYYY-MM-DD)")
