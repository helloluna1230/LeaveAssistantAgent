"""Session-pointer store: bookmark-only, per-user isolation, no chat content."""

from pathlib import Path

from agents.leave_assistant.session_store import SessionPointerStore


def _store(tmp_path: Path) -> SessionPointerStore:
    return SessionPointerStore(path=tmp_path / "sessions.json")


def test_set_and_get_roundtrip(tmp_path):
    s = _store(tmp_path)
    saved = s.set("E1001", {"previous_response_id": "caresp_abc", "conversation": "c1"})
    assert saved["previous_response_id"] == "caresp_abc"
    assert s.get("E1001")["conversation"] == "c1"


def test_only_pointer_keys_are_kept(tmp_path):
    s = _store(tmp_path)
    # Chat content / business data must never be persisted as a bookmark.
    saved = s.set("E1001", {"previous_response_id": "caresp_x", "text": "我还有多少年假", "remaining_days": 9})
    assert "text" not in saved
    assert "remaining_days" not in saved
    assert saved == {"previous_response_id": "caresp_x"}


def test_users_are_isolated(tmp_path):
    s = _store(tmp_path)
    s.set("E1001", {"previous_response_id": "caresp_1"})
    s.set("E1002", {"previous_response_id": "caresp_2"})
    assert s.get("E1001")["previous_response_id"] == "caresp_1"
    assert s.get("E1002")["previous_response_id"] == "caresp_2"


def test_empty_pointer_clears(tmp_path):
    s = _store(tmp_path)
    s.set("E1001", {"previous_response_id": "caresp_1"})
    # Falsy values are filtered out, so an empty pointer effectively clears it.
    s.set("E1001", {"previous_response_id": None, "conversation": None})
    assert s.get("E1001") == {}


def test_delete(tmp_path):
    s = _store(tmp_path)
    s.set("E1001", {"previous_response_id": "caresp_1"})
    s.delete("E1001")
    assert s.get("E1001") == {}
