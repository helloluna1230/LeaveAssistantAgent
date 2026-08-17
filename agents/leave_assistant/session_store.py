"""File-backed session-pointer store, isolated per verified user.

Holds only a lightweight conversation bookmark — the last Responses `response_id`
(and optional conversation id) — so a returning user (even on a new device) can
rehydrate their thread from the platform Responses store. It stores NO business
data and NO chat content; the transcript itself is fetched fresh from the
platform. Swap the file backend for a durable store (Cosmos DB, etc.) in
production; the get/set interface is identical.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_STORE_PATH = Path(os.environ.get(
    "SESSION_STORE_PATH",
    str(Path(__file__).resolve().parent / ".session_store.json"),
))
_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", str(30 * 24 * 3600)))
_lock = threading.Lock()

# Only these keys are persisted as a session bookmark.
ALLOWED_KEYS = {"previous_response_id", "conversation"}


class SessionPointerStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _STORE_PATH

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, user_id: str) -> dict[str, Any]:
        with _lock:
            record = self._read().get(user_id)
        if not record:
            return {}
        if time.time() - record.get("_updated", 0) > _TTL_SECONDS:
            self.delete(user_id)
            return {}
        return {k: v for k, v in record.items() if k in ALLOWED_KEYS}

    def set(self, user_id: str, pointer: dict[str, Any]) -> dict[str, Any]:
        filtered = {k: v for k, v in pointer.items() if k in ALLOWED_KEYS and v}
        with _lock:
            data = self._read()
            current = filtered
            current["_updated"] = time.time()
            data[user_id] = current
            self._write(data)
        return {k: v for k, v in current.items() if k in ALLOWED_KEYS}

    def delete(self, user_id: str) -> None:
        with _lock:
            data = self._read()
            if user_id in data:
                del data[user_id]
                self._write(data)


store = SessionPointerStore()
