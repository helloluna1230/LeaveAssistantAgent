from __future__ import annotations

import os
import sys
from pathlib import Path


EVALUATOR_NAME = "leave-assistant-tool-selection"


def main() -> int:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        print("ERROR: set FOUNDRY_PROJECT_ENDPOINT.", file=sys.stderr)
        return 2

    try:
        from azure.ai.projects import AIProjectClient
        from azure.ai.projects.models import EvaluatorCategory, EvaluatorDefinitionType
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        print(
            "ERROR: install evaluation dependencies with "
            "'python3 -m pip install -r evaluation/requirements.txt'.\n"
            f"       ({exc})",
            file=sys.stderr,
        )
        return 3

    code_path = Path(__file__).resolve().parents[1] / "evaluation" / "tool_selection_evaluator.py"
    code_text = code_path.read_text(encoding="utf-8")

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=endpoint, credential=credential) as project,
    ):
        evaluator = project.beta.evaluators.create_version(
            name=EVALUATOR_NAME,
            evaluator_version={
                "name": EVALUATOR_NAME,
                "categories": [EvaluatorCategory.QUALITY],
                "display_name": "Leave Assistant Tool Selection",
                "description": (
                    "Deterministically compares hosted agent tool calls with "
                    "expected_tools and forbidden_tools."
                ),
                "definition": {
                    "type": EvaluatorDefinitionType.CODE,
                    "code_text": code_text,
                    "init_parameters": {
                        "type": "object",
                        "properties": {
                            "deployment_name": {"type": "string"},
                            "pass_threshold": {"type": "number"},
                        },
                        "required": ["deployment_name", "pass_threshold"],
                    },
                    "metrics": {
                        "result": {
                            "type": "continuous",
                            "desirable_direction": "increase",
                            "min_value": 0.0,
                            "max_value": 1.0,
                        }
                    },
                    "data_schema": {
                        "type": "object",
                        "required": ["item"],
                        "properties": {
                            "item": {
                                "type": "object",
                                "required": ["expected_tools"],
                                "properties": {
                                    "expected_tools": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "sample": {
                                        "type": "object",
                                        "properties": {
                                            "tool_calls": {
                                                "type": "array",
                                                "items": {"type": "object"},
                                            }
                                        },
                                    },
                                },
                            }
                        },
                    },
                },
            },
        )

    print(f"Created evaluator {evaluator.name}:{evaluator.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())