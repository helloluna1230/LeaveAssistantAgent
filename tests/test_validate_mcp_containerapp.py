import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate-mcp-containerapp.py"


@pytest.fixture
def validator():
    assert SCRIPT_PATH.exists(), "validation script has not been implemented"
    spec = importlib.util.spec_from_file_location("validate_mcp_containerapp", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parses_direct_url_and_key(validator):
    args = validator.parse_args(
        [
            "--url",
            "https://leave.example.test/mcp",
            "--key",
            "secret-value",
        ]
    )

    assert args.url == "https://leave.example.test/mcp"
    assert args.key == "secret-value"
    assert args.user_id == "E1001"
    assert args.leave_type == "annual_leave"


def test_requires_url_and_key(validator):
    with pytest.raises(SystemExit):
        validator.parse_args([])


def test_validates_balance_belongs_to_requested_user(validator):
    balance = validator.validate_balance(
        {
            "balances": [
                {
                    "employee_id": "E1001",
                    "leave_type": "annual_leave",
                    "remaining_days": 9.0,
                    "simulated": True,
                }
            ],
            "simulated": True,
        },
        "E1001",
        "annual_leave",
    )

    assert balance["remaining_days"] == 9.0


def test_rejects_balance_for_another_user(validator):
    with pytest.raises(ValueError, match="requested user"):
        validator.validate_balance(
            {
                "balances": [
                    {
                        "employee_id": "E1002",
                        "leave_type": "annual_leave",
                        "remaining_days": 1.0,
                    }
                ]
            },
            "E1001",
            "annual_leave",
        )


def test_requires_all_expected_mcp_tools(validator):
    validator.validate_tool_names(
        {
            "get_leave_balance",
            "get_leave_history",
            "get_leave_types",
            "get_public_holidays",
            "create_leave_request_preview",
        }
    )

    with pytest.raises(ValueError, match="Missing MCP tools: get_leave_history"):
        validator.validate_tool_names(
            {
                "get_leave_balance",
                "get_leave_types",
                "get_public_holidays",
                "create_leave_request_preview",
            }
        )


def test_rejects_mcp_error_payload(validator):
    with pytest.raises(ValueError, match="UNAUTHORIZED"):
        validator.validate_balance(
            {
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Missing identity token.",
                }
            },
            "E1001",
            "annual_leave",
        )


def test_redacts_api_key_from_error_message(validator):
    api_key = "top-secret-api-key"

    message = validator.redact(f"request failed with {api_key}", [api_key])

    assert message == "request failed with ***"
    assert api_key not in message