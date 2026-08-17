from __future__ import annotations

import inspect
import json

import pytest

from evaluation.tool_selection_evaluator import grade


def _tool_calls(*names: str) -> list[dict]:
    return [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "function_call",
                    "name": name,
                    "arguments": {},
                }
            ],
        }
        for name in names
    ]


def test_matches_expected_mcp_tool_after_stripping_toolbox_prefix() -> None:
    assert grade(
        {"tool_calls": _tool_calls("leave-hr___get_leave_balance")},
        {"expected_tools": ["get_leave_balance"]},
    ) == 1.0


def test_maps_policy_search_to_dataset_contract_name() -> None:
    assert grade(
        {"tool_calls": _tool_calls("hr_policy_search")},
        {"expected_tools": ["HRPolicyKnowledge"]},
    ) == 1.0


def test_accepts_json_serialized_mapped_columns() -> None:
    assert grade(
        {"tool_calls": json.dumps(_tool_calls("leave-hr___get_leave_balance"))},
        {"expected_tools": json.dumps(["get_leave_balance"])},
    ) == 1.0


def test_accepts_json_serialized_empty_tool_calls() -> None:
    assert grade(
        {"tool_calls": "[]"},
        {"expected_tools": "[]"},
    ) == 1.0


def test_accepts_direct_mapped_columns() -> None:
    assert grade(
        _tool_calls("leave-hr___get_leave_balance"),
        ["get_leave_balance"],
    ) == 1.0


def test_accepts_direct_json_serialized_mapped_columns() -> None:
    assert grade(
        json.dumps(_tool_calls("leave-hr___get_leave_balance")),
        json.dumps(["get_leave_balance"]),
    ) == 1.0


def test_accepts_direct_json_serialized_empty_columns() -> None:
    assert grade("[]", "[]") == 1.0


def test_reads_agent_target_fields_from_item_sample() -> None:
    assert grade(
        {},
        {
            "expected_tools": ["get_leave_balance"],
            "sample": {
                "tool_calls": _tool_calls("leave-hr___get_leave_balance"),
            },
        },
    ) == 1.0


def test_reads_serialized_agent_target_fields_from_item_sample() -> None:
    assert grade(
        {},
        {
            "expected_tools": json.dumps(["get_leave_balance"]),
            "sample": {
                "tool_calls": json.dumps(_tool_calls("leave-hr___get_leave_balance")),
            },
        },
    ) == 1.0


def test_deduplicates_retries() -> None:
    assert grade(
        {
            "tool_calls": _tool_calls(
                "leave-hr___get_leave_balance",
                "leave-hr___get_leave_balance",
            )
        },
        {"expected_tools": ["get_leave_balance"]},
    ) == 1.0


def test_allows_unforbidden_supporting_tools() -> None:
    assert grade(
        {
            "tool_calls": _tool_calls(
                "leave-hr___get_leave_balance",
                "plan_leave",
            )
        },
        {"expected_tools": ["plan_leave"]},
    ) == 1.0


def test_fails_when_expected_tool_is_missing() -> None:
    assert grade(
        {"tool_calls": _tool_calls("leave-hr___get_leave_balance")},
        {"expected_tools": ["get_leave_history"]},
    ) == 0.0


def test_uses_exactly_two_parameters_required_by_foundry_code_graders() -> None:
    assert len(inspect.signature(grade).parameters) == 2


@pytest.mark.parametrize(
    ("calls", "expected_score"),
    [
        ([], 1.0),
        (_tool_calls("leave-hr___get_leave_balance"), 0.0),
    ],
)
def test_no_tool_contract_requires_no_calls(calls: list[dict], expected_score: float) -> None:
    assert grade({"tool_calls": calls}, {"expected_tools": []}) == expected_score


@pytest.mark.parametrize(
    "sample,item",
    [
        ({}, {"expected_tools": []}),
        ({"tool_calls": []}, {"expected_tools": "get_leave_balance"}),
        (None, {"expected_tools": []}),
        ({"tool_calls": []}, None),
    ],
)
def test_malformed_contract_fails_without_raising(
    sample: object,
    item: object,
) -> None:
    assert grade(sample, item) == 0.0