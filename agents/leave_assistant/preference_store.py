"""File-backed preference store, isolated per verified user. No agent_framework
dependency so it stays unit-testable. Swap for a Foundry Memory Store in
production; the get/set/delete interface is identical. Business data (balances,
history) is NEVER stored here.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

# Default to a writable temp dir: in the Foundry hosted container the app
# directory is read-only, so writing preferences next to the code fails. Override
# with PREFERENCE_STORE_PATH (e.g. a mounted volume) for durable storage.
_STORE_PATH = Path(os.environ.get(
    "PREFERENCE_STORE_PATH",
    str(Path(tempfile.gettempdir()) / "leave_assistant_prefs.json"),
))
_TTL_SECONDS = int(os.environ.get("PREFERENCE_TTL_SECONDS", str(180 * 24 * 3600)))
_lock = threading.Lock()

# Only these keys may be persisted as long-term preferences.
ALLOWED_KEYS = {
    "preferred_periods",
    "preferred_trip_type",
    "planning_strategy",
    "use_expiring_leave_first",
}


class PreferenceStore:
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

    def set(self, user_id: str, prefs: dict[str, Any]) -> dict[str, Any]:
        filtered = {k: v for k, v in prefs.items() if k in ALLOWED_KEYS}
        with _lock:
            data = self._read()
            current = data.get(user_id, {})
            current.update(filtered)
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


class FoundryMemoryPreferenceStore:
    """Preferences backed by the Foundry Agent Service Memory store (preview).

    Uses the low-level Memory Store item API (works with our hosted container
    agent; the memory_search tool targets prompt agents). Preferences are stored
    as a single JSON `user_profile` memory item per scope (= employee id). Same
    get/set/delete interface as the file/blob stores.
    """

    _API_SCOPE = "https://ai.azure.com/.default"

    def __init__(self, project_endpoint: str, store_name: str, api_version: str) -> None:
        self._base = f"{project_endpoint.rstrip('/')}/memory_stores/{store_name}"
        self._api = api_version
        self._credential = None

    def _token(self) -> str:
        if self._credential is None:
            from azure.identity import DefaultAzureCredential

            self._credential = DefaultAzureCredential()
        return self._credential.get_token(self._API_SCOPE).token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token()}", "Content-Type": "application/json"}

    def _items(self, user_id: str) -> list[dict[str, Any]]:
        import httpx

        url = f"{self._base}:search_memories?api-version={self._api}"
        resp = httpx.post(url, headers=self._headers(), json={"scope": user_id}, timeout=30.0)
        resp.raise_for_status()
        return [m.get("memory_item", {}) for m in resp.json().get("memories", [])]

    def _stored_prefs(self, user_id: str) -> dict[str, Any]:
        """Return the JSON preference record (with _updated), or {}."""
        for item in self._items(user_id):
            try:
                record = json.loads(item.get("content", ""))
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(record, dict) and any(k in ALLOWED_KEYS for k in record):
                return record
        return {}

    def _delete_scope(self, user_id: str) -> None:
        import httpx

        url = f"{self._base}:delete_scope?api-version={self._api}"
        httpx.post(url, headers=self._headers(), json={"scope": user_id}, timeout=30.0)

    def get(self, user_id: str) -> dict[str, Any]:
        record = self._stored_prefs(user_id)
        if not record:
            return {}
        if time.time() - record.get("_updated", 0) > _TTL_SECONDS:
            self.delete(user_id)
            return {}
        return {k: v for k, v in record.items() if k in ALLOWED_KEYS}

    def set(self, user_id: str, prefs: dict[str, Any]) -> dict[str, Any]:
        import httpx

        filtered = {k: v for k, v in prefs.items() if k in ALLOWED_KEYS}
        with _lock:
            current = self._stored_prefs(user_id)
            current.update(filtered)
            current["_updated"] = time.time()
            # Single source of truth: clear the scope, then write one JSON item.
            self._delete_scope(user_id)
            url = f"{self._base}/items?api-version={self._api}"
            body = {
                "scope": user_id,
                "content": json.dumps(current, ensure_ascii=False),
                "kind": "user_profile",
            }
            httpx.post(url, headers=self._headers(), json=body, timeout=30.0).raise_for_status()
        return {k: v for k, v in current.items() if k in ALLOWED_KEYS}

    def delete(self, user_id: str) -> None:
        with _lock:
            self._delete_scope(user_id)


def _build_store():
    """Native Foundry Memory when configured (hosted); file store otherwise (local dev)."""
    mem = os.environ.get("FOUNDRY_MEMORY_STORE", "").strip()
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if mem and endpoint:
        api = os.environ.get("FOUNDRY_MEMORY_API_VERSION", "2025-11-15-preview")
        return FoundryMemoryPreferenceStore(endpoint, mem, api)
    return PreferenceStore()


store = _build_store()
