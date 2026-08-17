"""Remote-mode tools: connect the agent to the standalone HR MCP server.

The server-to-server API key gates the forwarded simulated user id so the MCP
enforces authorization server-side. Planning and preference tools stay local.
"""

from __future__ import annotations

import logging

from .config import Config
from .identity import current_user_token
from .local_tools import (
    analyze_leave_usage,
    delete_my_preferences,
    get_my_preferences,
    plan_leave,
    save_my_preferences,
    search_leave_policy,
)

logger = logging.getLogger("leave_assistant.remote_tools")


def _auth_headers() -> dict[str, str]:
    import os

    token = current_user_token() or ""
    api_key = os.environ.get("MCP_API_KEY", "")
    headers = {"x-api-key": api_key}
    if token:
        headers["x-user-token"] = token.removeprefix("Bearer ").strip()
    return headers


def build_remote_tools(client, config: Config) -> list:
    """Build the HR MCP tool plus local planning/preference tools."""
    tools: list = []
    try:
        # Prefer a per-request header provider so each user's identity is forwarded.
        try:
            mcp_tool = client.get_mcp_tool(
                name="LeaveHR",
                url=config.mcp_endpoint,
                header_provider=_auth_headers,
                approval_mode="never_require",
            )
        except TypeError:
            # Older API without header_provider: fall back to static headers.
            mcp_tool = client.get_mcp_tool(
                name="LeaveHR",
                url=config.mcp_endpoint,
                headers=_auth_headers(),
                approval_mode="never_require",
            )
        tools.append(mcp_tool)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to register HR MCP tool at %s: %s", config.mcp_endpoint, exc)

    tools.extend(
        [
            plan_leave,
            analyze_leave_usage,
            search_leave_policy,
            get_my_preferences,
            save_my_preferences,
            delete_my_preferences,
        ]
    )
    return tools


def build_knowledge_tool(client, config: Config):
    """Attach the Foundry IQ knowledge base as a retrieval tool, if supported.

    The knowledge base (`FOUNDRY_KNOWLEDGE_INDEX`) is created in the portal; see
    knowledge/README.md. Returns None if the client build doesn't expose it.
    """
    if not config.knowledge_index:
        return None
    for factory in ("get_knowledge_tool", "get_foundry_iq_tool", "get_ai_search_tool"):
        fn = getattr(client, factory, None)
        if callable(fn):
            try:
                return fn(name="HRPolicyKnowledge", index=config.knowledge_index)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Knowledge tool factory %s failed: %s", factory, exc)
    logger.info("No knowledge tool factory available on this client build; configure IQ via portal/toolbox.")
    return None
