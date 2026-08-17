"""Local-mode tools: call the in-process mock HR service, the planner, and the
preference store. Authorization is enforced by the shared `leave_mcp` service
based on the verified caller identity — the same code path the remote MCP uses.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from agent_framework import tool
from pydantic import Field

# Resolved via sys.path bootstrap in agents.leave_assistant.__init__.
from leave_mcp import service as leave_service
from leave_mcp.schemas import LeaveError
from planner import plan_leave as _plan_leave

from ..harness.config import DEFAULT as HARNESS
from ..harness.runtime import HarnessLimitExceeded, note_tool_call, should_retry_sleep
from .identity import current_principal
from .observability import mask_user, traced
from .preference_store import store as pref_store


def _run(tool_name: str, fn, *args, **kwargs) -> dict:
    principal = current_principal()
    try:
        note_tool_call(tool_name)  # enforce the per-run tool-call budget
    except HarnessLimitExceeded as exc:
        return {"error": {"code": "TOOL_BUDGET_EXCEEDED", "message": str(exc)}, "simulated": True}

    attempt = 0
    while True:
        with traced(f"tool.{tool_name}", user_id=principal.employee_id, **{"tool.name": tool_name}) as span:
            try:
                result = fn(principal, *args, **kwargs)
                span.set_attribute("tool.status", "ok")
                return result
            except LeaveError as exc:
                span.set_attribute("tool.status", "error")
                span.set_attribute("error.type", exc.code.value)
                if should_retry_sleep(exc.code.value, attempt, HARNESS):
                    attempt += 1
                    continue
                return exc.to_dict()


@tool(approval_mode="never_require", description="Get the current user's simulated leave balance(s).")
def get_leave_balance(
    leave_type: Annotated[str | None, Field(description="Optional leave type filter.")] = None,
) -> dict:
    return _run("get_leave_balance", leave_service.get_leave_balance, leave_type=leave_type)


@tool(approval_mode="never_require", description="Get the current user's simulated leave history in a date range.")
def get_leave_history(
    start_date: Annotated[date, Field(description="Inclusive start date YYYY-MM-DD.")],
    end_date: Annotated[date, Field(description="Inclusive end date YYYY-MM-DD.")],
    leave_type: Annotated[str | None, Field(description="Optional leave type filter.")] = None,
) -> dict:
    return _run(
        "get_leave_history",
        leave_service.get_leave_history,
        start_date=start_date,
        end_date=end_date,
        leave_type=leave_type,
    )


@tool(approval_mode="never_require", description="List supported leave types and accrual rules.")
def get_leave_types() -> dict:
    return _run("get_leave_types", leave_service.get_leave_types)


@tool(approval_mode="never_require", description="Get simulated public holidays for a year (default 2026).")
def get_public_holidays(
    year: Annotated[int, Field(description="Calendar year.")] = 2026,
) -> dict:
    return _run("get_public_holidays", leave_service.get_public_holidays, year=year)


@tool(
    approval_mode="always_require",
    description="Preview a leave request (non-binding). Requires explicit user confirmation; "
    "never creates a real HR record.",
)
def create_leave_request_preview(
    leave_type: Annotated[str, Field(description="Leave type, e.g. annual_leave.")],
    start_date: Annotated[date, Field(description="Inclusive start date YYYY-MM-DD.")],
    end_date: Annotated[date, Field(description="Inclusive end date YYYY-MM-DD.")],
) -> dict:
    return _run(
        "create_leave_request_preview",
        leave_service.create_leave_request_preview,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
    )


@tool(
    approval_mode="never_require",
    description="Generate personalized leave plans from balance, holidays, and saved preferences "
    "(Leave Planning Skill).",
)
def plan_leave(
    remaining_leave_days: Annotated[float, Field(description="Authoritative remaining days from get_leave_balance.")],
    expiring_leave_days: Annotated[float, Field(description="Days expiring soon.")] = 0,
    public_holidays: Annotated[list[dict] | None, Field(description="Holidays from get_public_holidays.")] = None,
    policy_constraints: Annotated[list[str] | None, Field(description="Applicable policy notes.")] = None,
) -> dict:
    principal = current_principal()
    prefs = pref_store.get(principal.employee_id)
    with traced("skill.plan_leave", user_id=principal.employee_id):
        return _plan_leave(
            remaining_leave_days=remaining_leave_days,
            expiring_leave_days=expiring_leave_days,
            policy_constraints=policy_constraints or [],
            public_holidays=public_holidays or [],
            user_preferences=prefs,
        )


@tool(approval_mode="never_require", description="Show the current user's saved leave preferences.")
def get_my_preferences() -> dict:
    principal = current_principal()
    with traced("memory.read", user_id=principal.employee_id):
        return {"user_id": mask_user(principal.employee_id), "preferences": pref_store.get(principal.employee_id)}


@tool(
    approval_mode="never_require",
    description="Save explicitly stated leave preferences (preferred_periods, preferred_trip_type, "
    "planning_strategy, use_expiring_leave_first). Only for preferences the user clearly stated.",
)
def save_my_preferences(
    preferred_periods: Annotated[list[str] | None, Field(description="e.g. ['May','October'].")] = None,
    preferred_trip_type: Annotated[str | None, Field(description="'long_trip' or 'short_trip'.")] = None,
    planning_strategy: Annotated[str | None, Field(description="e.g. 'maximize_consecutive_days'.")] = None,
    use_expiring_leave_first: Annotated[bool | None, Field(description="Prefer using expiring leave first.")] = None,
) -> dict:
    principal = current_principal()
    incoming = {
        "preferred_periods": preferred_periods,
        "preferred_trip_type": preferred_trip_type,
        "planning_strategy": planning_strategy,
        "use_expiring_leave_first": use_expiring_leave_first,
    }
    prefs = {k: v for k, v in incoming.items() if v is not None}
    with traced("memory.write", user_id=principal.employee_id):
        saved = pref_store.set(principal.employee_id, prefs)
    return {"user_id": mask_user(principal.employee_id), "preferences": saved}


@tool(approval_mode="always_require", description="Delete the current user's saved leave preferences.")
def delete_my_preferences() -> dict:
    principal = current_principal()
    with traced("memory.write", user_id=principal.employee_id):
        pref_store.delete(principal.employee_id)
    return {"user_id": mask_user(principal.employee_id), "preferences": {}, "deleted": True}


@tool(
    approval_mode="never_require",
    description="Analyze the current user's leave usage and return chart-ready series "
    "(monthly usage, used vs remaining, type distribution, expiring). In hosted mode the "
    "Code Interpreter renders these as charts.",
)
def analyze_leave_usage(year: Annotated[int, Field(description="Calendar year to analyze.")] = 2026) -> dict:
    from .analysis import analyze

    principal = current_principal()
    note_tool_call("analyze_leave_usage")
    with traced("code_interpreter.analyze", user_id=principal.employee_id):
        try:
            balances = leave_service.get_leave_balance(principal).get("balances", [])
            history = leave_service.get_leave_history(
                principal, date(year, 1, 1), date(year, 12, 31)
            ).get("items", [])
        except LeaveError as exc:
            return exc.to_dict()
        return analyze(balances, history)


@tool(
    approval_mode="never_require",
    description="Search HR leave policy and return grounded excerpts with section citations. "
    "Use for policy questions; answer only from the returned text and cite the section.",
)
def search_leave_policy(
    query: Annotated[str, Field(description="The policy question, e.g. '年假什么时候过期'.")],
) -> dict:
    from .knowledge_local import search

    principal = current_principal()
    note_tool_call("search_leave_policy")
    with traced("knowledge.retrieve", user_id=principal.employee_id):
        return search(query)


LOCAL_TOOLS = [
    get_leave_balance,
    get_leave_history,
    get_leave_types,
    get_public_holidays,
    create_leave_request_preview,
    plan_leave,
    analyze_leave_usage,
    search_leave_policy,
    get_my_preferences,
    save_my_preferences,
    delete_my_preferences,
]
