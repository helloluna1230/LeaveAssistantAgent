#!/usr/bin/env bash
# Prepare the Foundry project and Toolbox artifacts for the Leave Assistant.
# You must be logged in first (this script never logs you in):
#   az login && azd auth login
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE="${ENV_FILE:-.env}"
AZD_ENV="${AZD_ENV:-leave-assistant-demo}"

echo "==> Checking auth (will NOT log you in)…"
az account show >/dev/null 2>&1 || { echo "ERROR: run 'az login' first."; exit 1; }
azd auth login --check-status >/dev/null 2>&1 || { echo "ERROR: run 'azd auth login' first."; exit 1; }

# Ensure the AI agent extension is present.
azd extension install azure.ai.agents >/dev/null 2>&1 || true

echo "==> Syncing ${ENV_FILE} to azd environment ${AZD_ENV}…"
AZURE_DEV_USER_AGENT="${AZURE_DEV_USER_AGENT:-microsoft_foundry_skill}" \
  ENV_FILE="$ENV_FILE" AZD_ENV="$AZD_ENV" bash scripts/azd-env-sync.sh

MODE="$(azd env get-value MCP_MODE 2>/dev/null || true)"
MODE="${MODE:-toolbox}"

echo "==> Reading the independently deployed MCP endpoint…"
MCP_SERVER_ENDPOINT="$(azd env get-value MCP_SERVER_ENDPOINT 2>/dev/null || true)"
: "${MCP_SERVER_ENDPOINT:?deploy MCP first with mcp-server/leave_mcp/deploy-mcp.sh}"

if [[ "$MODE" == "toolbox" ]]; then
  echo "==> Uploading the leave-planning Agent Skill to the Foundry project…"
  bash scripts/upload-leave-planning-skill.sh

  echo "==> Ready to create the Foundry Toolbox (HR MCP + Tool Search + Code Interpreter + IQ + leave-planning skill)…"
  echo "    fill placeholders in ./toolbox.yaml, then:"
  echo "    azd ai toolbox create leave-assistant-toolbox --from-file ./toolbox.yaml --no-prompt"
fi

