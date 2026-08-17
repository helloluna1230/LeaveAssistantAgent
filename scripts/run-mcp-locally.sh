#!/usr/bin/env bash
# Run everything locally for the demo: MCP server (optional) + hosted agent host.
# Requires: az login (for the model), Python 3.11+.
set -euo pipefail

cd "$(dirname "$0")/.."

MODE="${MCP_MODE:-local}"

if [[ "$MODE" == "remote" ]]; then
  echo "==> Starting mock HR MCP server on :8080 …"
  ( cd mcp-server && python -m uvicorn leave_mcp.server:app --host 0.0.0.0 --port 8080 ) &
  echo "    MCP PID $!"
fi

echo "==> Starting the hosted agent host (Responses) on :8088 …"
echo "    Ensure .env is populated (copy from .env.example) and 'az login' is done."
python agents/leave_assistant/main.py
