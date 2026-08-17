from __future__ import annotations

import json


_TOOL_ALIASES = {
    "hr_policy_search": "HRPolicyKnowledge",
}


def _mapped_list(value: object) -> list | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return None
    return value if isinstance(value, list) else None


def _normalize_tool_name(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    name = value.rsplit("___", 1)[-1]
    return _TOOL_ALIASES.get(name, name)


def _contract_names(value: object) -> set[str] | None:
    values = _mapped_list(value)
    if values is None or any(not isinstance(name, str) for name in values):
        return None
    return {normalized for name in values if (normalized := _normalize_tool_name(name))}


def _tool_names(value: object):
    if isinstance(value, list):
        for entry in value:
            yield from _tool_names(entry)
        return
    if not isinstance(value, dict):
        return

    if value.get("type") in {"function_call", "tool_call"}:
        name = _normalize_tool_name(value.get("name"))
        if name:
            yield name

    for key in ("content", "tool_calls", "output_items"):
        yield from _tool_names(value.get(key))


def grade(
    sample: object,
    item: object,
) -> float:
    item_sample = item.get("sample") if isinstance(item, dict) else None
    if isinstance(item_sample, dict) and "tool_calls" in item_sample:
        tool_calls_value = item_sample.get("tool_calls")
    else:
        tool_calls_value = sample.get("tool_calls") if isinstance(sample, dict) else sample
    expected_tools_value = item.get("expected_tools") if isinstance(item, dict) else item
    tool_calls = _mapped_list(tool_calls_value)
    if tool_calls is None:
        return 0.0
    expected = _contract_names(expected_tools_value)
    if expected is None:
        return 0.0

    actual = set(_tool_names(tool_calls))
    if not expected:
        return 1.0 if not actual else 0.0
    return 1.0 if expected <= actual else 0.0