"""Toolbox-mode tools: consume a governed Microsoft Foundry Toolbox.

The agent connects to ONE toolbox MCP endpoint and dynamically discovers every
governed tool it contains (HR MCP on Container App, Code Interpreter, Tool Search,
HR-policy knowledge). Tool credentials live in Foundry connections, not here.

Identity: the toolbox authenticates to the platform with an `ai.azure.com` bearer
(placed on `Authorization`). The simulated employee id is forwarded on a
separate `x-user-token` header so the HR MCP can still enforce per-user
authorization server-side. Planning and preference tools stay local (they are not
part of the HR system).

Build the toolbox with `scripts/create_toolbox.py`.
"""

from __future__ import annotations

import logging

from azure.identity import DefaultAzureCredential

from .config import Config
from .identity import current_user_token
from .local_tools import (
    delete_my_preferences,
    get_my_preferences,
    plan_leave,
    save_my_preferences,
)

logger = logging.getLogger("leave_assistant.toolbox_tools")

def _user_headers(_runtime_kwargs: dict) -> dict[str, str]:
    user_token = current_user_token()
    if not user_token:
        return {}
    bearer_token = user_token if user_token.startswith("Bearer ") else f"Bearer {user_token}"
    return {"x-user-token": bearer_token}


def build_toolbox_capabilities(config: Config) -> tuple[list, list]:
    """Build one Toolbox connection for governed tools and Agent Skills."""
    tools: list = [plan_leave, get_my_preferences, save_my_preferences, delete_my_preferences]
    context_providers: list = []
    if not config.toolbox_endpoint:
        logger.error(
            "TOOLBOX_ENDPOINT is not set. Create the toolbox with scripts/create_toolbox.py and set "
            "TOOLBOX_ENDPOINT to its consumer endpoint."
        )
        return tools, context_providers

    try:
        from agent_framework.foundry import FoundryToolbox

        toolbox = FoundryToolbox(
            DefaultAzureCredential(),
            url=config.toolbox_endpoint,
            load_prompts=False,
        )
        toolbox._header_provider = _user_headers  
        skills_provider = toolbox.as_skills_provider(disable_load_skill_approval=True)
        tools.append(toolbox)
        context_providers.append(skills_provider)
        logger.info("Connected to Foundry Toolbox tools and Agent Skills at %s", config.toolbox_endpoint)
    except Exception as exc:  
        logger.error("Failed to connect to toolbox %s: %s", config.toolbox_endpoint, exc)

    return tools, context_providers
