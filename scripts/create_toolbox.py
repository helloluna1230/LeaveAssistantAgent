"""Build (or update) the Leave Assistant Foundry Toolbox version.

Creates a governed toolbox that curates: the HR MCP server (hosted on Container
App), a Tool Search tool, the Code Interpreter, and the HR-policy knowledge
(Foundry IQ / Azure AI Search). Agents then consume ALL of these through one
toolbox MCP endpoint — no tool credentials in agent code.

Preview: `project.toolboxes.*` ships in preview `azure-ai-projects` builds, the
REST API, azd, and the Foundry Toolkit. You must be logged in (`az login`) with
permission to manage toolboxes; the Foundry toolbox APIs require the
`https://ai.azure.com/.default` scope.

Usage:
  export FOUNDRY_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
  export MCP_SERVER_ENDPOINT=https://<mcp-containerapp-fqdn>/mcp
  export MCP_CONNECTION_ID=<foundry-connection-id-holding-mcp-credentials>
  export FOUNDRY_KNOWLEDGE_INDEX=hr-leave-policies-index        # optional
  export AZURE_AI_SEARCH_CONNECTION_NAME=<project-search-connection>  # optional (Foundry IQ/AI Search)
  python scripts/create_toolbox.py

Confirmed tool classes (azure-ai-projects>=2.0.0): MCPTool, ToolboxSearchPreviewTool,
CodeInterpreterToolboxTool(+AutoCodeInterpreterToolParam), AzureAISearchTool(+
AzureAISearchToolResource, AISearchIndexResource, AzureAISearchQueryType).

Prints the toolbox consumer endpoint to set as TOOLBOX_ENDPOINT.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    mcp_url = os.environ.get("MCP_SERVER_ENDPOINT")
    toolbox_name = os.environ.get("TOOLBOX_NAME", "leave-assistant-toolbox")
    mcp_connection_id = os.environ.get("MCP_CONNECTION_ID")  # credentials live in Foundry
    knowledge_index = os.environ.get("FOUNDRY_KNOWLEDGE_INDEX", "hr-leave-policies-index")
    # Project connection to the Azure AI Search / Foundry IQ index (created in portal).
    search_connection_name = os.environ.get("AZURE_AI_SEARCH_CONNECTION_NAME", "")

    if not endpoint or not mcp_url:
        print("ERROR: set FOUNDRY_PROJECT_ENDPOINT and MCP_SERVER_ENDPOINT.", file=sys.stderr)
        return 2

    try:
        from azure.ai.projects import AIProjectClient
        from azure.ai.projects.models import MCPTool, ToolboxSearchPreviewTool
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        print(
            "ERROR: 'azure-ai-projects>=2.0.0' with toolbox models is required.\n"
            f"       ({exc})\n"
            "       Install it, or create the toolbox in the Foundry portal / Toolkit.",
            file=sys.stderr,
        )
        return 3

    project = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())

    mcp_kwargs = {
        "server_label": "leave-hr",
        "server_url": mcp_url,
        "require_approval": "never",
    }
    if mcp_connection_id:
        mcp_kwargs["project_connection_id"] = mcp_connection_id

    tools: list = [
        MCPTool(**mcp_kwargs),
        ToolboxSearchPreviewTool(),
    ]

    _add_code_interpreter(tools)
    _add_knowledge(tools, project, search_connection_name, knowledge_index)

    version = project.toolboxes.create_toolbox_version(
        name=toolbox_name,
        description="Leave Assistant governed tools: HR MCP (Container App) + Tool Search + Code Interpreter + HR policy knowledge.",
        tools=tools,
    )
    print(f"Created toolbox '{version.name}', version {version.version}.")
    consumer = f"{endpoint}/toolboxes/{toolbox_name}/mcp?api-version=v1"
    print("\nAdd these values to .env:")
    print(f"  TOOLBOX_ENDPOINT={consumer}")
    print(f"  TOOLBOX_NAME={toolbox_name}")
    print("  MCP_MODE=toolbox")
    print("Then run: bash scripts/azd-env-sync.sh")
    return 0


def _add_code_interpreter(tools: list) -> None:
    """Add the Code Interpreter tool (toolbox variant) with an auto sandbox container.

    NOTE: through a toolbox, Code Interpreter shares one container per project — it is
    NOT per-user isolated. Keep per-user data minimization in mind (analyze only the
    caller's already-retrieved figures; don't upload other users' data).
    """
    try:
        from azure.ai.projects.models import AutoCodeInterpreterToolParam, CodeInterpreterToolboxTool

        tools.append(CodeInterpreterToolboxTool(container=AutoCodeInterpreterToolParam(file_ids=[])))
    except Exception as exc:  # noqa: BLE001 - SDK version mismatch
        print(f"Note: CodeInterpreterToolboxTool unavailable ({exc}); add Code Interpreter in the portal.")


def _add_knowledge(tools: list, project, search_connection_name: str, index: str) -> None:
    """Ground on an Azure AI Search / Foundry IQ index via a project connection."""
    if not index or not search_connection_name:
        print(
            "Note: skipping knowledge tool — set AZURE_AI_SEARCH_CONNECTION_NAME (and "
            "FOUNDRY_KNOWLEDGE_INDEX) to attach the Foundry IQ / Azure AI Search index."
        )
        return
    try:
        from azure.ai.projects.models import (
            AISearchIndexResource,
            AzureAISearchQueryType,
            AzureAISearchTool,
            AzureAISearchToolResource,
        )

        connection_id = project.connections.get(search_connection_name).id
        tools.append(
            AzureAISearchTool(
                azure_ai_search=AzureAISearchToolResource(
                    indexes=[
                        AISearchIndexResource(
                            project_connection_id=connection_id,
                            index_name=index,
                            query_type=AzureAISearchQueryType.SIMPLE,
                        )
                    ]
                )
            )
        )
    except Exception as exc:  # noqa: BLE001 - SDK/connection issue
        print(f"Note: AzureAISearchTool unavailable ({exc}); attach the knowledge index in the portal.")


if __name__ == "__main__":
    raise SystemExit(main())
