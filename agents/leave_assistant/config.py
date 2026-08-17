"""Environment-driven configuration. No secrets or endpoints hardcoded."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_INSTRUCTIONS_PATH = Path(__file__).resolve().parents[1] / "instructions" / "leave_assistant.md"


@dataclass(frozen=True)
class Config:
    project_endpoint: str
    model_deployment: str
    agent_name: str
    mcp_mode: str            # "toolbox" (governed Foundry Toolbox) | "remote" (direct HTTP MCP) | "local"
    mcp_endpoint: str
    toolbox_endpoint: str
    toolbox_name: str
    knowledge_index: str
    app_insights_conn: str
    enable_instrumentation: bool
    max_steps: int
    max_tool_calls: int
    demo_default_user: str
    responses_store: bool

    @property
    def instructions(self) -> str:
        return _INSTRUCTIONS_PATH.read_text(encoding="utf-8")


def load_config() -> Config:
    return Config(
        project_endpoint=os.environ.get("FOUNDRY_PROJECT_ENDPOINT", ""),
        model_deployment=os.environ.get(
            "AZURE_AI_MODEL_DEPLOYMENT_NAME",
            os.environ.get("AZURE_OPENAI_MODEL_DEPLOYMENT", os.environ.get("FOUNDRY_MODEL", "gpt-5.6-luna")),
        ),
        agent_name=os.environ.get("FOUNDRY_AGENT_NAME", "leave-assistant"),
        mcp_mode=os.environ.get("MCP_MODE", "toolbox").lower(),
        mcp_endpoint=os.environ.get("MCP_SERVER_ENDPOINT", "http://localhost:8080/mcp"),
        toolbox_endpoint=os.environ.get("TOOLBOX_ENDPOINT", ""),
        toolbox_name=os.environ.get("TOOLBOX_NAME", "leave-assistant-toolbox"),
        knowledge_index=os.environ.get("FOUNDRY_KNOWLEDGE_INDEX", "hr-leave-policies-index"),
        app_insights_conn=os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", ""),
        enable_instrumentation=os.environ.get("ENABLE_INSTRUMENTATION", "true").lower() == "true",
        max_steps=int(os.environ.get("AGENT_MAX_STEPS", "12")),
        max_tool_calls=int(os.environ.get("AGENT_MAX_TOOL_CALLS", "20")),
        demo_default_user=os.environ.get("DEMO_DEFAULT_USER", "E1001"),
        responses_store=os.environ.get("RESPONSES_STORE", "true").lower() == "true",
    )
