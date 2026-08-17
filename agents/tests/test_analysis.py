from datetime import date

from agents.leave_assistant.analysis import analyze


def test_analyze_builds_chart_series():
    balances = [
        {"leave_type": "annual_leave", "used_days": 6, "remaining_days": 9, "expiring_days": 3,
         "expiration_date": "2026-12-31"},
        {"leave_type": "sick_leave", "used_days": 2, "remaining_days": 8},
    ]
    history = [
        {"leave_type": "annual_leave", "start_date": date(2026, 3, 10), "end_date": date(2026, 3, 12), "days": 3},
        {"leave_type": "annual_leave", "start_date": date(2026, 5, 1), "end_date": date(2026, 5, 3), "days": 3},
        {"leave_type": "sick_leave", "start_date": "2026-02-14", "end_date": "2026-02-14", "days": 1},
    ]
    out = analyze(balances, history)
    assert out["summary"]["total_used_days"] == 7
    assert out["charts"]["monthly_usage"] == {"2026-02": 1, "2026-03": 3, "2026-05": 3}
    assert out["charts"]["type_distribution"]["annual_leave"] == 6
    assert out["expiring"][0]["leave_type"] == "annual_leave"
    assert out["simulated"] is True


def test_analyze_handles_empty():
    out = analyze([], [])
    assert out["summary"]["records"] == 0
    assert out["charts"]["monthly_usage"] == {}
    assert out["expiring"] == []
