"""Identity resolution: the agent derives the caller from request context,
never from chat text. Uses the same simulated directory as the MCP server.
"""

import pytest

from agents.leave_assistant import identity
from leave_mcp.schemas import ErrorCode, LeaveError


def test_current_principal_from_token():
    demo_identity = identity.demo_token_for("E1001")
    assert demo_identity == "E1001"
    reset = identity.set_current_user_token(demo_identity)
    try:
        principal = identity.current_principal()
        assert principal.employee_id == "E1001"
    finally:
        identity.reset_current_user_token(reset)


def test_no_token_is_unauthorized():
    reset = identity.set_current_user_token(None)
    try:
        with pytest.raises(LeaveError) as exc:
            identity.current_principal()
        assert exc.value.code == ErrorCode.UNAUTHORIZED
    finally:
        identity.reset_current_user_token(reset)


def test_bearer_prefixed_token_accepted():
    reset = identity.set_current_user_token(f"Bearer {identity.demo_token_for('M1001')}")
    try:
        assert identity.current_principal().is_manager
    finally:
        identity.reset_current_user_token(reset)
