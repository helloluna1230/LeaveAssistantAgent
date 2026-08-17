import pytest

from leave_mcp.auth import authenticate
from leave_mcp.schemas import ErrorCode, LeaveError, Role


def test_employee_id_maps_to_principal():
    principal = authenticate("E1001")
    assert principal.employee_id == "E1001"
    assert principal.role == Role.EMPLOYEE
    assert not principal.is_manager


def test_manager_identity_has_reports():
    principal = authenticate("M1001")
    assert principal.is_manager
    assert set(principal.manager_of) == {"E1001", "E1002"}


def test_missing_token_is_unauthorized():
    with pytest.raises(LeaveError) as exc:
        authenticate(None)
    assert exc.value.code == ErrorCode.UNAUTHORIZED


def test_bearer_prefixed_employee_id_accepted():
    principal = authenticate("Bearer E1002")
    assert principal.employee_id == "E1002"


def test_unknown_identity_rejected():
    with pytest.raises(LeaveError) as exc:
        authenticate("E404")
    assert exc.value.code == ErrorCode.UNAUTHORIZED
