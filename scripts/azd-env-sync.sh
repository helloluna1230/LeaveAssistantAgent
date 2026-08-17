#!/usr/bin/env bash
# Sync selected keys from the repo `.env` (your single config file) into the azd
# environment, so you don't run many `azd env set` by hand. Re-run after editing .env.
#
# Usage:  bash scripts/azd-env-sync.sh            # uses .env + azd env 'leave-assistant-demo'
#         ENV_FILE=.env.prod AZD_ENV=prod bash scripts/azd-env-sync.sh
#         RESET_LAST_EVAL_ID=true bash scripts/azd-env-sync.sh
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_FILE="${ENV_FILE:-.env}"
AZD_ENV="${AZD_ENV:-leave-assistant-demo}"

[[ -f "$ENV_FILE" ]] || { echo "ERROR: $ENV_FILE not found."; exit 1; }
command -v azd >/dev/null 2>&1 || { echo "ERROR: azd not installed."; exit 1; }
command -v az >/dev/null 2>&1 || { echo "ERROR: Azure CLI (az) not installed."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not installed."; exit 1; }

# Create the local azd environment if needed (creates NO Azure resources).
azd env select "$AZD_ENV" 2>/dev/null || azd env new "$AZD_ENV"

# Safely load KEY=VALUE lines from the config file WITHOUT letting the shell
# interpret values (placeholders like https://<fqdn>/mcp contain <,> which would
# be treated as redirections by `source`).
load_env() {
  local file="$1" line key val
  [[ -f "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue
    key="${line%%=*}"; val="${line#*=}"
    key="${key#"${key%%[![:space:]]*}"}"; key="${key%"${key##*[![:space:]]}"}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ "$val" == \"*\" ]]; then val="${val%\"}"; val="${val#\"}"; fi
    if [[ "$val" == \'*\' ]]; then val="${val%\'}"; val="${val#\'}"; fi
    export "$key=$val"
  done < "$file"
}

# Load the config file.
load_env "$ENV_FILE"
# Canonical hosted-agent values fall back to their documented local defaults.
: "${AZURE_AI_MODEL_DEPLOYMENT_NAME:=${FOUNDRY_MODEL:-${AZURE_OPENAI_MODEL_DEPLOYMENT:-}}}"
: "${DEMO_DEFAULT_USER:=E1001}"
: "${FOUNDRY_MEMORY_STORE:=leave-assistant-memory}"
: "${RESPONSES_STORE:=true}"

[[ -n "${FOUNDRY_PROJECT_ENDPOINT:-}" ]] || {
  echo "ERROR: FOUNDRY_PROJECT_ENDPOINT is required in $ENV_FILE."
  exit 1
}

# Both SDK naming conventions refer to the same Foundry project endpoint.
AZURE_AI_PROJECT_ENDPOINT="$FOUNDRY_PROJECT_ENDPOINT"

# Resolve the real project ARM ID, account location, and tenant from Azure.
IFS=$'\t' read -r FOUNDRY_ACCOUNT_NAME FOUNDRY_PROJECT_NAME < <(
  python3 - "$FOUNDRY_PROJECT_ENDPOINT" <<'PY'
import sys
from urllib.parse import unquote, urlparse

endpoint = sys.argv[1].strip().rstrip("/")
parsed = urlparse(endpoint)
suffix = ".services.ai.azure.com"
host = (parsed.hostname or "").lower()
parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]

if parsed.scheme != "https" or not host.endswith(suffix):
    raise SystemExit("ERROR: FOUNDRY_PROJECT_ENDPOINT must be an https://<account>.services.ai.azure.com URL.")

try:
    project_index = next(index for index, part in enumerate(parts) if part.lower() == "projects")
    project_name = parts[project_index + 1]
except (StopIteration, IndexError):
    raise SystemExit("ERROR: FOUNDRY_PROJECT_ENDPOINT must contain /api/projects/<project>.")

print(f"{host[:-len(suffix)]}\t{project_name}")
PY
)

ACCOUNT_INFO="$({ az cognitiveservices account list -o json; } | \
  FOUNDRY_ACCOUNT_NAME="$FOUNDRY_ACCOUNT_NAME" python3 -c '
import json, os, sys

target = os.environ["FOUNDRY_ACCOUNT_NAME"].lower()
matches = [
    account for account in json.load(sys.stdin)
    if (account.get("name") or "").lower() == target
    or ((account.get("properties") or {}).get("customSubDomainName") or "").lower() == target
]
if len(matches) != 1:
    raise SystemExit(f"ERROR: expected one Foundry account matching {target!r}, found {len(matches)}.")
account = matches[0]
print("\t".join((account["resourceGroup"], account["name"], account["location"])))
')"
IFS=$'\t' read -r FOUNDRY_RESOURCE_GROUP FOUNDRY_ACCOUNT_NAME AZURE_LOCATION <<< "$ACCOUNT_INFO"

PROJECT_INFO="$({
  az resource list \
    --resource-group "$FOUNDRY_RESOURCE_GROUP" \
    --resource-type Microsoft.CognitiveServices/accounts/projects \
    -o json
} | FOUNDRY_PROJECT_RESOURCE_NAME="$FOUNDRY_ACCOUNT_NAME/$FOUNDRY_PROJECT_NAME" python3 -c '
import json, os, sys

target = os.environ["FOUNDRY_PROJECT_RESOURCE_NAME"].lower()
matches = [resource for resource in json.load(sys.stdin) if (resource.get("name") or "").lower() == target]
if len(matches) != 1:
    raise SystemExit(f"ERROR: expected one Foundry project matching {target!r}, found {len(matches)}.")
project = matches[0]
print("\t".join((project["id"], project["location"])))
')"
IFS=$'\t' read -r AZURE_AI_PROJECT_ID AZURE_LOCATION <<< "$PROJECT_INFO"
[[ -n "$AZURE_AI_PROJECT_ID" ]] || { echo "ERROR: Azure returned an empty Foundry project ID."; exit 1; }

AZURE_TENANT_ID="$(az account show --query tenantId -o tsv)"
AZURE_SUBSCRIPTION_ID="$(az account show --query id -o tsv)"

# Only these keys are pushed to azd (add more as needed).
KEYS=(
  FOUNDRY_PROJECT_ENDPOINT
  AZURE_AI_MODEL_DEPLOYMENT_NAME
  FOUNDRY_AGENT_NAME
  APPLICATIONINSIGHTS_CONNECTION_STRING
  ENABLE_INSTRUMENTATION
  OTEL_SERVICE_NAME
  MCP_MODE
  MCP_SERVER_ENDPOINT
  MCP_API_KEY
  MCP_CONNECTION_ID
  FOUNDRY_KNOWLEDGE_INDEX
  AZURE_AI_SEARCH_CONNECTION_NAME
  TOOLBOX_ENDPOINT
  TOOLBOX_NAME
  DEMO_DEFAULT_USER
  FOUNDRY_MEMORY_STORE
  RESPONSES_STORE
  AGENT_MAX_STEPS
  AGENT_MAX_TOOL_CALLS
  # Required by `azd deploy leave-assistant` (hosted agent):
  AZURE_AI_PROJECT_ID
  AZURE_AI_PROJECT_ENDPOINT
  AZURE_LOCATION
  AZURE_TENANT_ID
  AZURE_SUBSCRIPTION_ID
)

echo "==> Syncing $ENV_FILE -> azd env '$AZD_ENV'"
for k in "${KEYS[@]}"; do
  v="${!k:-}"
  if [[ -n "$v" ]]; then
    azd env set "$k" "$v"
    case "$k" in
      APPLICATIONINSIGHTS_CONNECTION_STRING|MCP_API_KEY)
        echo "  set $k=<redacted>"
        ;;
      *)
        echo "  set $k=$v"
        ;;
    esac
  else
    echo "  skip $k (empty)"
  fi
done

if [[ "${RESET_LAST_EVAL_ID:-false}" == "true" ]]; then
  azd env set LAST_EVAL_ID ""
  echo "  reset LAST_EVAL_ID"
fi

echo "==> Done."
