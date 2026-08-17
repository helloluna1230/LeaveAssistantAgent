---
name: leave-planning
description: Method for turning a user's remaining leave balance, expiring days, public holidays, and saved preferences into concrete leave plans that maximize continuous time off within policy and balance limits.
---

# Skill: Leave Planning (休假规划)

Reusable task capability that turns a user's remaining balance, applicable
policies, public holidays, and saved preferences into one or more concrete
leave plans. Invoked by the Leave Assistant agent; implemented in
[`planner.py`](planner.py).

## 1. Task goal

Produce practical leave plans that maximize the user's continuous time off (or
another requested strategy) **within** their remaining balance and policy
constraints, and clearly explain the trade-offs of each plan.

## 2. Input requirements

```json
{
  "remaining_leave_days": 9,
  "expiring_leave_days": 3,
  "policy_constraints": ["最多可结转5天年假至次年3月31日"],
  "public_holidays": [{ "name": "中秋国庆", "start_date": "2026-10-01", "end_date": "2026-10-08" }],
  "user_preferences": {
    "preferred_trip_type": "long_trip",
    "preferred_periods": ["May", "October"],
    "planning_strategy": "maximize_consecutive_days",
    "use_expiring_leave_first": true
  }
}
```

- `remaining_leave_days` is required and authoritative (from MCP, not the model).
- `public_holidays` should come from the MCP `get_public_holidays` tool.
- `user_preferences` come from Foundry user memory when available.

## 3. Planning steps

1. Normalize holidays into date ranges; identify adjacent weekends.
2. For each holiday (prioritizing `preferred_periods`), compute **bridge**
   working days that connect the weekend + holiday into one continuous block.
3. Score each candidate by continuous days off per leave day used.
4. Select plans under the `remaining_leave_days` budget; honor
   `planning_strategy` and `use_expiring_leave_first`.
5. Compute `leave_days_used`, `consecutive_days_off`, and a human explanation.
6. Summarize remaining balance after the recommended plan and any policy notes.

## 4. Constraints

- **Policy**: never propose a plan that violates provided `policy_constraints`.
- **Balance**: total `leave_days_used` across a single plan must not exceed
  `remaining_leave_days`.
- **Preferences**: apply saved preferences but let the current request override
  them; if they conflict, prefer the explicit request and note it.

## 5. Output format

```json
{
  "recommended_plans": [
    {
      "plan_name": "国庆长假方案",
      "leave_dates": ["2026-09-30"],
      "leave_days_used": 1,
      "consecutive_days_off": 9,
      "reason": "用 1 天年假衔接周末与国庆假期，形成 9 天连休。"
    }
  ],
  "remaining_days_after_plan": 8,
  "policy_notes": ["建议优先使用即将过期的假期。"]
}
```

## 6. Forbidden actions

- Do not invent public holidays or balances; use only provided inputs.
- Do not submit or approve any real leave request (planning only).
- Do not exceed the remaining balance or ignore expiry rules.

## 7. Exception handling

- If `public_holidays` is empty, propose generic long-weekend plans and note the
  limitation.
- If `remaining_leave_days <= 0`, return no plans and explain why.
- If inputs are malformed, return an empty `recommended_plans` with a note
  rather than fabricating a plan.