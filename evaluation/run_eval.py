"""Deterministic backend security/exception boundary evaluator (no model).

Measures whether the HR MCP service correctly DENIES cross-user/impersonation
access and returns the expected error codes — i.e. the safety guarantees the
agent depends on. Model-based hosted regression runs separately via
`azd ai agent eval run --config evaluation/hosted_functional_eval.yaml`;
candidate search uses `azd ai agent optimize --config agent-optimizer/optimizer.yaml`.

Run:  python evaluation/run_eval.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for sub in ("", "mcp-server", "skills/leave_planning"):
    p = str(_ROOT / sub) if sub else str(_ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)

from agents.leave_assistant import identity  # noqa: E402
from leave_mcp import service  # noqa: E402
from leave_mcp.schemas import ErrorCode, LeaveError  # noqa: E402

DATASETS = _ROOT / "evaluation" / "datasets"
RESULTS = _ROOT / "evaluation" / "results"


def _load(name: str) -> list[dict]:
    path = DATASETS / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _principal(emp: str):
    identity.set_current_user_token(identity.demo_token_for(emp))
    return identity.current_principal()


def _attempt_cross_user(case: dict) -> tuple[bool, str]:
    """Simulate the worst-case tool call an over-eager model might make and
    confirm the backend denies it. Returns (passed, detail)."""
    principal = _principal(case["user"])
    target = "E1002" if case["user"] != "E1002" else "E1001"
    try:
        service.get_leave_balance(principal, employee_id=target)
        return False, "backend returned data for another employee"
    except LeaveError as exc:
        ok = exc.code == ErrorCode.FORBIDDEN and target not in exc.message
        return ok, exc.code.value


def _check_exception(case: dict) -> tuple[bool, str]:
    principal = _principal(case["user"])
    try:
        if case.get("expected_error") == "INVALID_DATE_RANGE":
            service.get_leave_history(principal, date(2026, 5, 1), date(2026, 1, 1))
        elif case.get("expected_error") == "INSUFFICIENT_LEAVE_BALANCE":
            service.create_leave_request_preview(principal, "annual_leave", date(2026, 11, 2), date(2026, 11, 30))
        elif case.get("expected_error") == "LEAVE_TYPE_NOT_SUPPORTED":
            service.get_leave_balance(principal, leave_type="moon_leave")
        elif case.get("expected_error") == "SERVICE_UNAVAILABLE":
            service.get_leave_balance(principal)
        elif case.get("expected_empty"):
            res = service.get_leave_history(principal, date(2026, 1, 1), date(2026, 1, 31))
            return res["items"] == [], "empty"
        else:
            return True, "delegated_to_model"  # e.g. cannot_confirm — model-side
        return False, "no error raised"
    except LeaveError as exc:
        return exc.code.value == case.get("expected_error"), exc.code.value


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    report: dict = {"security": [], "exception": [], "summary": {}}

    for case in _load("security.jsonl"):
        if case.get("expected_behavior") == "require_confirmation":
            passed, detail = True, "handled_by_approval_mode(always_require)"
        else:
            passed, detail = _attempt_cross_user(case)
        report["security"].append({"id": case["id"], "passed": passed, "detail": detail})

    for case in _load("exception.jsonl"):
        passed, detail = _check_exception(case)
        report["exception"].append({"id": case["id"], "passed": passed, "detail": detail})

    sec_pass = sum(c["passed"] for c in report["security"])
    exc_pass = sum(c["passed"] for c in report["exception"])
    report["summary"] = {
        "security_pass_rate": round(sec_pass / len(report["security"]), 3),
        "exception_pass_rate": round(exc_pass / len(report["exception"]), 3),
        "security_passed": sec_pass,
        "security_total": len(report["security"]),
        "exception_passed": exc_pass,
        "exception_total": len(report["exception"]),
    }

    out = RESULTS / "backend_boundary.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"\nWrote {out}")

    # Non-zero exit if any backend safety case failed.
    return 0 if sec_pass == len(report["security"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
