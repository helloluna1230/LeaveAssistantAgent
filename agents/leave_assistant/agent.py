"""Assemble the Leave Assistant agent (client-agnostic build function)."""

from __future__ import annotations

import logging

from agent_framework import Agent

from .config import Config
from .memory import UserPreferenceProvider

logger = logging.getLogger("leave_assistant.agent")


def build_agent(client, config: Config, *, instructions: str | None = None) -> Agent:
    """Build the agent with tools selected by MCP_MODE and the preference memory provider."""
    context_providers = [UserPreferenceProvider()]
    if config.mcp_mode == "toolbox":
        # Governed Foundry Toolbox: one MCP endpoint exposes all curated tools.
        from .toolbox_tools import build_toolbox_capabilities

        tools, toolbox_context_providers = build_toolbox_capabilities(config)
        context_providers.extend(toolbox_context_providers)
    elif config.mcp_mode == "remote":
        from .remote_tools import build_knowledge_tool, build_remote_tools

        tools = build_remote_tools(client, config)
        knowledge = build_knowledge_tool(client, config)
        if knowledge is not None:
            tools.append(knowledge)
    else:
        from .local_tools import LOCAL_TOOLS

        tools = list(LOCAL_TOOLS)

    logger.info("Building agent '%s' in %s mode with %d tools.", config.agent_name, config.mcp_mode, len(tools))

    return Agent(
        client=client,
        name=config.agent_name,
        instructions=config.instructions if instructions is None else instructions,
        tools=tools,
        context_providers=context_providers,
        # Platform-managed conversations: the Foundry Responses store persists
        # each turn and resolves previous_response_id server-side, scoped to the
        # verified caller identity. Set RESPONSES_STORE=false to opt out.
        default_options={"store": config.responses_store},
    )
