# AGENTS.md — Leave Assistant Demo

Guidance for coding agents working in this repo.

## Project
Enterprise Leave Assistant demo on Microsoft Foundry: Agent Framework hosted agent
(`agents/leave_assistant/`, Responses protocol, `gpt-5.6-luna`), a mock HR **MCP
server** with server-side authorization (`mcp-server/`), a **Leave Planning Skill**
(`skills/leave_planning/`), Foundry IQ knowledge (`knowledge/`), a React chat UI
(`frontend/web-chat-ui/`), and evaluation (`evaluation/`). **All HR data is simulated.**

## Conventions
- **Contract-first.** Before changing frontend↔agent behavior, update
  `docs/architecture/api-contract.yaml`, then both sides.
- **Never trust identity from the model or client.** Identity comes from the
  verified token; the MCP re-authorizes every call. Don't weaken
  `mcp-server/leave_mcp/service.py` authorization.
- **No secrets/endpoints hardcoded.** Read from env (`.env.example`).
- Two MCP modes share the same service code: `MCP_MODE=local` (in-process) and
  `remote` (HTTP Container App).
- Business data is fetched fresh; only whitelisted preferences are persisted.

## Build & test
```bash
pip install -r agents/leave_assistant/requirements.txt -r mcp-server/requirements-dev.txt
python -m pytest mcp-server/tests skills/leave_planning/tests agents/tests tests -q
python evaluation/run_eval.py
```

## Deploy
Sync `.env` with `bash scripts/azd-env-sync.sh`, then deploy the Hosted Agent with
`azd deploy leave-assistant --no-prompt` (see `README.md`). This repository has no
infrastructure template, so do not run `azd provision`. Operator must run
`az login` / `azd auth login`.

If you are in VS Code, read the vscode-microsoft-foundry skill first.
