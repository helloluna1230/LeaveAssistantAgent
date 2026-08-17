"""Deterministic leave-planning logic behind the Leave Planning Skill.

Pure functions over plain dicts so the agent can call it as a tool and tests can
verify it without any network or model. See SKILL.md for the contract.
"""

from __future__ import annotations

from datetime import date, timedelta

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _preferred_months(prefs: dict) -> set[int]:
    months: set[int] = set()
    for p in prefs.get("preferred_periods", []) or []:
        key = str(p).strip().lower()
        if key in _MONTHS:
            months.add(_MONTHS[key])
    return months


def _holiday_ranges(public_holidays: list[dict]) -> list[tuple[str, date, date]]:
    ranges: list[tuple[str, date, date]] = []
    for h in public_holidays or []:
        try:
            ranges.append((h.get("name", "holiday"), _parse_date(h["start_date"]), _parse_date(h["end_date"])))
        except (KeyError, ValueError):
            continue
    return ranges


def _extend_off_block(start: date, end: date, off_days: set[date]) -> tuple[date, date]:
    """Extend a holiday block through adjacent weekends already off."""
    d = start - timedelta(days=1)
    while d.weekday() >= 5:  # Sat/Sun before the block
        start = d
        d -= timedelta(days=1)
    d = end + timedelta(days=1)
    while d.weekday() >= 5:  # Sat/Sun after the block
        end = d
        d += timedelta(days=1)
    return start, end


def _bridge_days(anchor_start: date, anchor_end: date, budget: int) -> tuple[list[date], date, date]:
    """Pick working 'bridge' days around a holiday block to grow one long break.

    Greedily consumes working days immediately before then after the block,
    absorbing weekends for free, up to `budget` leave days.
    """
    leave_dates: list[date] = []
    block_start, block_end = _extend_off_block(anchor_start, anchor_end, set())
    remaining = budget

    # Bridge backward.
    d = block_start - timedelta(days=1)
    while remaining > 0 and d.weekday() < 5:
        leave_dates.append(d)
        block_start = d
        remaining -= 1
        d -= timedelta(days=1)
        while d.weekday() >= 5:  # absorb weekend for free
            block_start = d
            d -= timedelta(days=1)

    # Bridge forward.
    d = block_end + timedelta(days=1)
    while remaining > 0 and d.weekday() < 5:
        leave_dates.append(d)
        block_end = d
        remaining -= 1
        d += timedelta(days=1)
        while d.weekday() >= 5:
            block_end = d
            d += timedelta(days=1)

    return sorted(leave_dates), block_start, block_end


def plan_leave(
    remaining_leave_days: float,
    expiring_leave_days: float = 0,
    policy_constraints: list[str] | None = None,
    public_holidays: list[dict] | None = None,
    user_preferences: dict | None = None,
) -> dict:
    """Return recommended leave plans. See skills/leave_planning/SKILL.md."""
    policy_constraints = policy_constraints or []
    prefs = user_preferences or {}
    notes: list[str] = list(policy_constraints)

    if remaining_leave_days <= 0:
        return {
            "recommended_plans": [],
            "remaining_days_after_plan": remaining_leave_days,
            "policy_notes": notes + ["当前没有可用年假余额，无法生成休假计划。"],
        }

    if expiring_leave_days and prefs.get("use_expiring_leave_first", False):
        notes.append(f"建议优先使用即将过期的 {expiring_leave_days} 天假期。")

    ranges = _holiday_ranges(public_holidays or [])
    preferred = _preferred_months(prefs)

    # Prioritize holidays that fall in preferred months.
    def _priority(item: tuple[str, date, date]) -> tuple[int, date]:
        _, s, _e = item
        return (0 if s.month in preferred else 1, s)

    ranges.sort(key=_priority)

    plans: list[dict] = []
    budget = int(remaining_leave_days)

    for name, start, end in ranges:
        if budget <= 0:
            break
        # Cap leave used per single holiday to keep plans realistic.
        per_holiday_budget = min(budget, 3 if prefs.get("preferred_trip_type") == "long_trip" else 2)
        leave_dates, block_start, block_end = _bridge_days(start, end, per_holiday_budget)
        used = len(leave_dates)
        if used == 0:
            continue
        consecutive = (block_end - block_start).days + 1
        plans.append(
            {
                "plan_name": f"{name}长假方案",
                "leave_dates": [d.isoformat() for d in leave_dates],
                "leave_days_used": used,
                "consecutive_days_off": consecutive,
                "reason": (
                    f"用 {used} 天假期衔接周末与「{name}」假期，形成约 {consecutive} 天连休。"
                ),
            }
        )
        budget -= used

    if not plans:
        notes.append("未提供可用于拼假的法定节假日，建议围绕周末安排 3-4 天短假连休。")

    used_total = sum(p["leave_days_used"] for p in plans)
    return {
        "recommended_plans": plans,
        "remaining_days_after_plan": remaining_leave_days - used_total,
        "policy_notes": notes,
    }
