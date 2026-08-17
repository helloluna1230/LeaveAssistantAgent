#!/usr/bin/env bash
# Build and deploy this MCP server to an EXISTING ACR + Container Apps env,
# then mirror the endpoint and API key through the canonical .env sync workflow.
#
# Idempotent: re-run to roll out a new image. Creates NO Foundry/ACR/env resources.
# You must be logged in first (this script never logs you in): az login
#
# Override any of these via env vars:
#   ACR RG ACA_ENV APP IMAGE_TAG AZD_ENV ENV_FILE MCP_API_KEY
set -euo pipefail
cd "$(dirname "$0")/../.."

# Safely load KEY=VALUE lines from a dotenv file WITHOUT letting the shell
# interpret values (placeholders like https://<fqdn>/mcp contain <,> which the
# shell would treat as redirections when using `source`).
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
    if [[ ! -v "$key" ]]; then export "$key=$val"; fi
  done < "$file"
}

update_env_value() {
  local file="$1" key="$2" value="$3" line found=false temp
  temp="$(mktemp)"
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == "$key="* ]]; then
      printf '%s=%s\n' "$key" "$value" >> "$temp"
      found=true
    else
      printf '%s\n' "$line" >> "$temp"
    fi
  done < "$file"
  if [[ "$found" == false ]]; then
    printf '%s=%s\n' "$key" "$value" >> "$temp"
  fi
  mv "$temp" "$file"
}

# Explicit shell environment values take precedence over .env values.
ENV_FILE="${ENV_FILE:-.env}"
[[ -f "$ENV_FILE" ]] || { echo "ERROR: $ENV_FILE not found."; exit 1; }
load_env "$ENV_FILE"

ACR="${ACR:-azureaidemoacr}"
RG="${RG:-rg-azureaidemo}"
ACA_ENV="${ACA_ENV:-azureaidemo-env}"
APP="${APP:-leaveassistant-mcp}"
IMAGE_TAG="${IMAGE_TAG:-v5}"
AZD_ENV="${AZD_ENV:-leave-assistant-demo}"
[[ -n "${MCP_API_KEY:-}" ]] || {
  echo "ERROR: deployment requires MCP_API_KEY in the environment or .env."
  exit 1
}

SECRETS=("mcp-api-key=$MCP_API_KEY")
AUTH_ENV_VARS=("MCP_API_KEY=secretref:mcp-api-key")

echo "==> Checking az login (will NOT log you in)…"
az account show >/dev/null 2>&1 || { echo "ERROR: run 'az login' first."; exit 1; }

IMAGE="${ACR}.azurecr.io/leave-mcp:${IMAGE_TAG}"
echo "==> Building ${IMAGE} in ACR ${ACR} (remote build, no local Docker)…"
az acr build --registry "$ACR" --image "leave-mcp:${IMAGE_TAG}" ./mcp-server >/dev/null

if az containerapp show -n "$APP" -g "$RG" >/dev/null 2>&1; then
  echo "==> Updating existing Container App ${APP}…"
  az containerapp secret set -n "$APP" -g "$RG" --secrets "${SECRETS[@]}" >/dev/null
  az containerapp update -n "$APP" -g "$RG" --image "$IMAGE" \
    --replace-env-vars "${AUTH_ENV_VARS[@]}" >/dev/null
else
  echo "==> Creating Container App ${APP} in env ${ACA_ENV}…"
  az containerapp create -n "$APP" -g "$RG" --environment "$ACA_ENV" \
    --image "$IMAGE" \
    --registry-server "${ACR}.azurecr.io" --registry-identity system \
    --target-port 8080 --ingress external --min-replicas 1 --max-replicas 2 \
    --secrets "${SECRETS[@]}" \
    --env-vars "${AUTH_ENV_VARS[@]}" >/dev/null
fi

FQDN=$(az containerapp show -n "$APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)

echo "==> Pinning DNS-rebinding allowed hosts to the FQDN…"
az containerapp update -n "$APP" -g "$RG" \
  --set-env-vars "MCP_ALLOWED_HOSTS=${FQDN},localhost:8080" >/dev/null

if [[ -x .venv/bin/python ]]; then
  echo "==> Smoke test (authenticated MCP tool call)…"
  if .venv/bin/python scripts/validate-mcp-containerapp.py \
    --url "https://${FQDN}/mcp" \
    --key "$MCP_API_KEY"; then
    echo "    OK (authenticated MCP call succeeded)"
  else
    echo "    WARN: authenticated MCP call failed (new revision may still be activating; retry shortly)"
  fi
else
  echo "==> Smoke test (MCP initialize)…"
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "https://${FQDN}/mcp" \
    -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
    -H "X-API-Key: $MCP_API_KEY" -H "x-user-token: E1001" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}')
  if [[ "$code" == "200" ]]; then echo "    OK (HTTP 200)"; else echo "    WARN: HTTP $code (new revision may still be activating; retry shortly)"; fi
fi

# Keep .env authoritative, then let the canonical sync script mirror it to azd.
echo "==> Updating ${ENV_FILE} and syncing azd environment ${AZD_ENV}…"
update_env_value "$ENV_FILE" MCP_SERVER_ENDPOINT "https://${FQDN}/mcp"
update_env_value "$ENV_FILE" MCP_API_KEY "$MCP_API_KEY"
AZURE_DEV_USER_AGENT="${AZURE_DEV_USER_AGENT:-microsoft_foundry_skill}" \
  ENV_FILE="$ENV_FILE" AZD_ENV="$AZD_ENV" bash scripts/azd-env-sync.sh

cat <<EOF

MCP deployed:  https://${FQDN}/mcp
   API key stored as Container App secret 'mcp-api-key' and mirrored to the azd env.

Next (optional): create the Foundry IQ knowledge base (portal), build the toolbox,
then deploy the agent:  azd deploy leave-assistant
EOF