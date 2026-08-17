from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "mcp-server" / "leave_mcp" / "deploy-mcp.sh"


def script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_has_no_legacy_authentication_mode():
    text = script_text()

    assert "AUTH_MODE" not in text
    assert "MCP_JWT" not in text
    assert 'IMAGE_TAG="${IMAGE_TAG:-v5}"' in text


def test_api_key_is_stored_and_injected_as_container_app_secret():
    text = script_text()

    assert '"mcp-api-key=$MCP_API_KEY"' in text
    assert '"MCP_API_KEY=secretref:mcp-api-key"' in text
    assert '--replace-env-vars "${AUTH_ENV_VARS[@]}"' in text


def test_api_key_mode_requires_a_configured_key():
    text = script_text()

    assert 'requires MCP_API_KEY' in text


def test_endpoint_and_api_key_are_synced_through_canonical_env_script():
    text = script_text()

    assert 'update_env_value "$ENV_FILE" MCP_SERVER_ENDPOINT "https://${FQDN}/mcp"' in text
    assert 'update_env_value "$ENV_FILE" MCP_API_KEY "$MCP_API_KEY"' in text
    assert "bash scripts/azd-env-sync.sh" in text
    assert 'azd env set MCP_API_KEY "$MCP_API_KEY"' not in text


def test_api_key_smoke_test_performs_an_authenticated_tool_call():
    text = script_text()

    assert "scripts/validate-mcp-containerapp.py" in text
    assert '--url "https://${FQDN}/mcp"' in text
    assert '--key "$MCP_API_KEY"' in text


def test_toolbox_deploy_is_independent_from_mcp_and_agent_deploys():
    azure_yaml = (ROOT / "azure.yaml").read_text(encoding="utf-8")
    toolbox_deploy = (ROOT / "scripts" / "deploy-toolboxs.sh").read_text(encoding="utf-8")

    assert "leave-mcp:" not in azure_yaml
    assert "azd deploy leave-mcp" not in toolbox_deploy
    assert "azd deploy leave-assistant" not in toolbox_deploy
    assert "bash mcp-server/leave_mcp/deploy-mcp.sh" not in toolbox_deploy
    assert "azd env get-value MCP_SERVER_ENDPOINT" in toolbox_deploy
    assert not (ROOT / "scripts" / "deploy-mcp.sh").exists()
    assert not (ROOT / "infrastructure" / "bicep" / "mcp-containerapp.bicep").exists()


def test_toolbox_deploy_uses_the_canonical_env_sync_workflow():
    toolbox_deploy = (ROOT / "scripts" / "deploy-toolboxs.sh").read_text(encoding="utf-8")

    assert "bash scripts/azd-env-sync.sh" in toolbox_deploy
    assert "azd env set" not in toolbox_deploy
    assert "azd provision" not in toolbox_deploy


def test_toolbox_template_contains_no_environment_specific_resource_values():
    toolbox = (ROOT / "toolbox.yaml").read_text(encoding="utf-8")

    assert "/subscriptions/28a3e2ae-" not in toolbox
    assert "leaveassistant-mcp.wittyisland-" not in toolbox
    assert "https://<mcp-containerapp-fqdn>/mcp" in toolbox
    assert "<AZURE_AI_PROJECT_ID>/connections/<search-connection-name>" in toolbox