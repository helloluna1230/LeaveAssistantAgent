import pytest

from agents.harness.runtime import (
    HarnessLimitExceeded,
    end_run,
    get_budget,
    note_tool_call,
    run_with_retry,
    should_retry_sleep,
    start_run,
)


def test_tool_call_budget_enforced():
    start_run()
    with pytest.raises(HarnessLimitExceeded):
        for _ in range(get_budget().config.max_tool_calls + 1):
            note_tool_call("get_leave_balance")


def test_note_tool_call_without_budget_is_noop():
    end_run()  # clear any budget from a prior test
    note_tool_call("x")  # must not raise when no budget is active
    assert get_budget() is None


def test_should_retry_sleep_transient(monkeypatch):
    slept = []
    assert should_retry_sleep("SERVICE_UNAVAILABLE", 0, sleep=slept.append) is True
    assert slept  # backoff applied


def test_should_retry_sleep_non_transient():
    assert should_retry_sleep("FORBIDDEN", 0, sleep=lambda _s: None) is False


def test_run_with_retry_recovers():
    calls = {"n": 0}

    def call():
        calls["n"] += 1
        return {"error": {"code": "SERVICE_UNAVAILABLE"}} if calls["n"] < 2 else {"ok": True}

    result = run_with_retry(
        call,
        lambda r: r.get("error", {}).get("code"),
        sleep=lambda _s: None,
    )
    assert result == {"ok": True}
    assert calls["n"] == 2
