"""API-key authentication plus a plaintext employee id in x-user-token.

The shared MCP_API_KEY is validated by the server transport middleware; here we
test the identity resolution `authenticate()` does once the gate has passed —
the value it receives must be a known simulated employee id.
"""

import pytest


@pytest.fixture()
def apikey_env():
    from leave_mcp import auth

    return auth


def test_plain_employee_id_resolves(apikey_env):
    auth = apikey_env
    p = auth.authenticate("E1001")
    assert p.employee_id == "E1001" and not p.is_manager


def test_manager_role_from_directory(apikey_env):
    auth = apikey_env
    p = auth.authenticate("Bearer M1001")  # tolerates a Bearer prefix
    assert p.is_manager and set(p.manager_of) == {"E1001", "E1002"}


def test_different_users_are_distinguished(apikey_env):
    auth = apikey_env
    assert auth.authenticate("E1001").name != auth.authenticate("E1002").name


def test_external_caller_id_is_not_accepted(apikey_env):
    auth = apikey_env
    with pytest.raises(auth.LeaveError) as exc:
        auth.authenticate("user-oid-123")
    assert exc.value.code.value == "UNAUTHORIZED"


def test_unknown_user_rejected(apikey_env):
    auth = apikey_env
    with pytest.raises(auth.LeaveError) as exc:
        auth.authenticate("not-an-employee")
    assert exc.value.code.value == "UNAUTHORIZED"


def test_missing_identity_rejected(apikey_env):
    auth = apikey_env
    with pytest.raises(auth.LeaveError):
        auth.authenticate(None)
