import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from planner import plan_leave


HOLIDAYS_2026 = [
    {"name": "劳动节", "start_date": "2026-05-01", "end_date": "2026-05-05"},
    {"name": "中秋国庆", "start_date": "2026-10-01", "end_date": "2026-10-08"},
]


def test_no_balance_returns_no_plans():
    out = plan_leave(0, public_holidays=HOLIDAYS_2026)
    assert out["recommended_plans"] == []
    assert out["remaining_days_after_plan"] == 0


def test_generates_plans_within_budget():
    out = plan_leave(
        9,
        expiring_leave_days=3,
        public_holidays=HOLIDAYS_2026,
        user_preferences={
            "preferred_periods": ["October", "May"],
            "preferred_trip_type": "long_trip",
            "planning_strategy": "maximize_consecutive_days",
            "use_expiring_leave_first": True,
        },
    )
    plans = out["recommended_plans"]
    assert plans, "expected at least one plan"
    total_used = sum(p["leave_days_used"] for p in plans)
    assert total_used <= 9
    assert out["remaining_days_after_plan"] == 9 - total_used
    # Each plan yields more continuous days off than leave days spent (bridge value).
    for p in plans:
        assert p["consecutive_days_off"] > p["leave_days_used"]


def test_preferred_month_prioritized_first():
    out = plan_leave(
        3,
        public_holidays=HOLIDAYS_2026,
        user_preferences={"preferred_periods": ["October"], "preferred_trip_type": "long_trip"},
    )
    assert out["recommended_plans"][0]["plan_name"].startswith("中秋国庆")


def test_expiring_note_added():
    out = plan_leave(
        5,
        expiring_leave_days=3,
        public_holidays=HOLIDAYS_2026,
        user_preferences={"use_expiring_leave_first": True},
    )
    assert any("即将过期" in n for n in out["policy_notes"])


def test_no_holidays_still_advises():
    out = plan_leave(5, public_holidays=[])
    assert out["recommended_plans"] == []
    assert any("周末" in n for n in out["policy_notes"])
