"""Preference store: explicit prefs only, per-user isolation, allowed-key filter."""

from pathlib import Path

from agents.leave_assistant.preference_store import PreferenceStore


def _store(tmp_path: Path) -> PreferenceStore:
    return PreferenceStore(path=tmp_path / "prefs.json")


def test_set_and_get_roundtrip(tmp_path):
    s = _store(tmp_path)
    saved = s.set("E1001", {"preferred_periods": ["May", "October"], "preferred_trip_type": "long_trip"})
    assert saved["preferred_periods"] == ["May", "October"]
    assert s.get("E1001")["preferred_trip_type"] == "long_trip"


def test_disallowed_keys_are_dropped(tmp_path):
    s = _store(tmp_path)
    # Business data must never be persisted as a preference.
    saved = s.set("E1001", {"remaining_days": 9, "planning_strategy": "maximize_consecutive_days"})
    assert "remaining_days" not in saved
    assert saved["planning_strategy"] == "maximize_consecutive_days"


def test_users_are_isolated(tmp_path):
    s = _store(tmp_path)
    s.set("E1001", {"preferred_trip_type": "long_trip"})
    s.set("E1002", {"preferred_trip_type": "short_trip"})
    assert s.get("E1001")["preferred_trip_type"] == "long_trip"
    assert s.get("E1002")["preferred_trip_type"] == "short_trip"


def test_delete(tmp_path):
    s = _store(tmp_path)
    s.set("E1001", {"preferred_trip_type": "long_trip"})
    s.delete("E1001")
    assert s.get("E1001") == {}
