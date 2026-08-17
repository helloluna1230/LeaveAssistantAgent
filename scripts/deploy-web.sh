#!/usr/bin/env bash
# Build & deploy the single-user Web UI (Vite + BFF) to a Container App, wire it
# to the hosted agent, and grant the container's managed identity access to the
# hosted agent endpoint. Idempotent — re-run to roll out a new build. Log in first:
#   az login
#
# Config from env (or repo .env), with defaults:
#   ACR RG ACA_ENV APP IMAGE_TAG
#   FOUNDRY_PROJECT_ENDPOINT (required)  FOUNDRY_AGENT_NAME (default leave-assistant)
#   AGENT_RESPONSES_ENDPOINT (optional; derived from the project endpoint if unset)
set -euo pipefail
cd "$(dirname "$0")/.."

ACR="${ACR:-azureaidemoacr}"
RG="${RG:-rg-azureaidemo}"
ACA_ENV="${ACA_ENV:-azureaidemo-env}"
APP="${APP:-leaveassistant-web}"
# Unique per-build tag so every deploy is a distinct image reference; reusing a
# fixed tag (e.g. v1) makes `containerapp update` a no-op and keeps serving the
# cached old image. Override IMAGE_TAG to pin a specific build.
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"

az account show >/dev/null 2>&1 || { echo "ERROR: run 'az login' first."; exit 1; }

# Safely load KEY=VALUE lines from .env WITHOUT shell interpretation (values may
# contain <,> placeholders that `source` would treat as redirections).
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
load_env .env

: "${FOUNDRY_PROJECT_ENDPOINT:?set FOUNDRY_PROJECT_ENDPOINT in .env (…/api/projects/<project>)}"
AGENT_NAME="${FOUNDRY_AGENT_NAME:-leave-assistant}"
AGENT_EP="${AGENT_RESPONSES_ENDPOINT:-${FOUNDRY_PROJECT_ENDPOINT%/}/agents/${AGENT_NAME}/endpoint/protocols/openai/responses?api-version=v1}"

IMAGE="${ACR}.azurecr.io/leave-web:${IMAGE_TAG}"
echo "==> Building ${IMAGE} (Vite build + BFF)…"
az acr build --registry "$ACR" --image "leave-web:${IMAGE_TAG}" ./frontend/web-chat-ui >/dev/null

if az containerapp show -n "$APP" -g "$RG" >/dev/null 2>&1; then
  echo "==> Updating Container App ${APP}…"
  az containerapp update -n "$APP" -g "$RG" --image "$IMAGE" \
    --set-env-vars "AGENT_RESPONSES_ENDPOINT=$AGENT_EP" >/dev/null
else
  echo "==> Creating Container App ${APP} in env ${ACA_ENV}…"
  az containerapp create -n "$APP" -g "$RG" --environment "$ACA_ENV" \
    --image "$IMAGE" --registry-server "${ACR}.azurecr.io" --registry-identity system \
    --system-assigned --target-port 8080 --ingress external --min-replicas 1 --max-replicas 2 \
    --env-vars "AGENT_RESPONSES_ENDPOINT=$AGENT_EP" >/dev/null
fi

# Grant the container's managed identity access to this hosted agent endpoint only.
PID=$(az containerapp show -n "$APP" -g "$RG" --query identity.principalId -o tsv)
ACCT_NAME=$(echo "$FOUNDRY_PROJECT_ENDPOINT" | sed -E 's#https?://([^.]+)\..*#\1#')
ACCT_ID=$(az cognitiveservices account list --query "[?name=='${ACCT_NAME}'].id | [0]" -o tsv 2>/dev/null)
if [[ -n "$PID" && -n "$ACCT_ID" ]]; then
  PROJECT_NAME="${FOUNDRY_PROJECT_ENDPOINT%/}"
  PROJECT_NAME="${PROJECT_NAME##*/}"
  AGENT_SCOPE="${ACCT_ID}/projects/${PROJECT_NAME}/agents/${AGENT_NAME}"
  AGENT_CONSUMER_ROLE="eed3b665-ab3a-47b6-8f48-c9382fb1dad6"
  echo "==> Granting Foundry Agent Consumer to the web identity on ${AGENT_NAME}…"
  az role assignment create --assignee-object-id "$PID" --assignee-principal-type ServicePrincipal \
    --role "$AGENT_CONSUMER_ROLE" --scope "$AGENT_SCOPE" >/dev/null 2>&1 || true
  echo "  + Foundry Agent Consumer"
else
  echo "  WARN: could not resolve MI principal / Foundry account for RBAC (PID=$PID, acct=$ACCT_NAME)"
fi

FQDN=$(az containerapp show -n "$APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)
echo "==> Smoke test (POST /responses)…"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "https://${FQDN}/responses" \
  -H "Content-Type: application/json" -d '{"input":"我还有多少年假？","store":true}')
if [[ "$code" == "200" ]]; then echo "    OK (HTTP 200)"; else echo "    HTTP $code (RBAC may still be propagating; retry in ~1 min)"; fi

cat <<EOF

✅ Web UI:        https://${FQDN}
   Agent endpoint: ${AGENT_EP}
   Re-run this script to roll out a new frontend build.
EOF
