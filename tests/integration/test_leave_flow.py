"""Integration: the balance -> holidays -> planning flow used by the agent,
exercised through the same identity + service + skill path (no model)."""

from datetime import date

from agents.leave_assistant import identity
from leave_mcp import service
from planner import plan_leave


def setup_user(emp: str):
    identity.set_current_user_token(identity.demo_token_for(emp))
    return identity.current_principal()


def test_balance_then_plan_for_e1001():
    principal = setup_user("E1001")
    balance = service.get_leave_balance(principal, leave_type="annual_leave")["balances"][0]
    holidays = service.get_public_holidays(principal, 2026)["holidays"]

    plan = plan_leave(
        remaining_leave_days=balance["remaining_days"],
        expiring_leave_days=balance["expiring_days"],
        public_holidays=holidays,
        user_preferences={"preferred_periods": ["October"], "preferred_trip_type": "long_trip"},
    )
    assert plan["recommended_plans"]
    used = sum(p["leave_days_used"] for p in plan["recommended_plans"])
    assert used <= balance["remaining_days"]


def test_preview_requires_sufficient_balance():
    principal = setup_user("E1001")
    preview = service.create_leave_request_preview(
        principal, "annual_leave", date(2026, 12, 24), date(2026, 12, 24)
    )
    assert preview["status"] == "pending_confirmation"
    assert preview["simulated"] is True
