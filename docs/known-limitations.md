# Known Limitations

This is a demonstration reference, not a production system.

## Data & scope
- **All HR data is simulated** (`mcp-server/leave_mcp/mock_data.py`). No real HR
  integration, approvals, or record mutations. Write operations only produce
  non-binding previews.

## Identity
- Demo uses a shared MCP API key plus a plaintext simulated employee id, not real
  user sign-in. The MCP validates the key before accepting `x-user-token`, then
  applies server-side authorization. Real user authentication, token refresh, and
  tenant/claims validation are not implemented.
- `POST /demo/token` is retained as a frontend compatibility endpoint, but returns
  a validated simulated employee id rather than an access token. Replace it with
  real Entra ID / IdP sign-in for production (see `docs/security-design.md`).

## Per-request identity in hosted mode
- **Implemented** for the local host: `main.py` adds a pure-ASGI `_IdentityMiddleware`
  that maps each request's `x-user-token` / `Authorization` onto the identity
  contextvar (falling back to `DEMO_DEFAULT_USER` when absent), so switching users in
  the UI truly switches the verified identity (E1001→9 days, E1002→1 day). For the
  deployed Foundry runtime, validate that the same middleware hook is honored; the
  toolbox/remote `x-user-token` forwarding still applies for tool calls.

## Foundry-native features requiring the platform
- **Foundry Toolbox** (`MCP_MODE=toolbox`, default): the toolbox is built by
  `scripts/create_toolbox.py`, which needs a **preview** `azure-ai-projects` build
  and `az login`. The `x-user-token` forwarding for per-user authorization depends
  on the Toolbox/MCP-connection passing custom headers through to the Container App
  MCP; if your toolbox configuration strips them, use `MCP_MODE=remote` for strict
  per-user authz, or wire an OAuth-based MCP connection so the end-user identity is
  proxied. Container-App credentials for the toolbox live in a Foundry connection
  (`MCP_CONNECTION_ID`).
- **Foundry IQ** knowledge base is created manually in the portal; in toolbox mode
  it is attached as a toolbox tool (best-effort in `create_toolbox.py`), otherwise
  via `remote_tools.build_knowledge_tool`. A grounded local fallback
  (`knowledge_local.search` → `search_leave_policy` tool) provides cited policy
  answers offline for the demo/eval; it is keyword-based, not semantic like IQ.
- **Foundry Memory**: the demo uses a file-backed preference store with the same
  get/set/delete interface; swap for a Foundry Memory Store in production.
- **Platform-managed conversations**: with `RESPONSES_STORE=true` (default) the
  Foundry Responses store persists each turn and resolves `previous_response_id`
  server-side (retrieval scoped to the verified caller identity) — the client never
  resends prior turns. Hosted deployments get the durable platform store
  (`FoundryStorageProvider`); local runs auto-fall back to an in-process store
  (multi-turn works within the running host but is lost on restart). This
  conversation store is distinct from preference memory: it holds the Q&A thread,
  never the whitelisted preferences. The web UI keeps a local transcript cache for
  instant re-render, but a returning user (even on a new device) rehydrates the
  thread from the platform: the host exposes an identity-scoped bookmark
  (`GET/POST /session/state`, backed by `session_store.py`) holding only the last
  Responses pointer, and the UI rebuilds the transcript via
  `GET /responses/{id}/input_items` + `GET /responses/{id}`. Swap the file-backed
  pointer store for a durable DB (e.g. Cosmos DB) in production; the get/set
  interface is identical. Locally the in-process Responses store is wiped on host
  restart, so a saved pointer may 404 after a restart — the UI falls back to the
  local cache.
- **Code Interpreter**: hosted mode renders charts via the Foundry Code Interpreter.
  Offline, `analyze_leave_usage` (`analysis.analyze`) returns the chart-ready series
  (monthly usage, used vs remaining, type distribution, expiring) but does not draw
  images. **Toolbox/Tool Search** is exercised through the Foundry runtime. The
  toolbox build (`scripts/create_toolbox.py`) uses the confirmed SDK classes
  `CodeInterpreterToolboxTool` and `AzureAISearchTool`. ⚠️ Code Interpreter **through a
  toolbox shares one container per project — it is NOT per-user isolated**; the agent
  therefore analyzes only the caller's already-retrieved figures and never uploads
  other users' data. For strict isolation, use a per-agent Code Interpreter or the
  local `analyze_leave_usage` path.
- **Harness**: step/tool-call budgets and transient-error retry are enforced at the
  tool layer (`agents/harness/runtime.py`, reset per run in `memory.before_run`).
  Model-loop step counting still depends on the framework surfacing per-step hooks.
- **Observability**: tool/skill/memory/knowledge/code-interpreter spans are emitted
  with redacted attributes; `trace_id`/`agent_version` surfacing to the frontend
  response still depends on the hosting layer.

## Evaluation
- `evaluation/run_eval.py` deterministically validates the backend security/exception
  boundary only. Model-based quality metrics (groundedness, tool selection, task
  completion) require `azd ai agent eval run --config
  evaluation/hosted_functional_eval.yaml` against a deployed Agent version.

## Frontend
- Minimal chat UI; `npm install` not run in this environment. SSE parsing assumes a
  `data: {delta|output_text|...}` event shape; adjust to your host's exact stream.

## Cloud provisioning
- This repository reuses an existing Foundry project, model deployment, ACR, and
  Container Apps environment; it does not contain an `infra/main.bicep` or Terraform
  template for `azd provision`.
- `azd deploy` requires `az login` / `azd auth login`, which are the operator's
  responsibility (not automated).
