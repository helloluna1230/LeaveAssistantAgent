# Leave Assistant — Web Chat UI (React + Vite + TypeScript)

Minimal chat client for the Leave Assistant hosted agent. Shows the demo user
switcher, conversation id, streaming output, tool-call status, citations, memory
actions, trace id, and agent version. All HR data is SIMULATED.

## Run

```bash
npm install
# point at your hosted agent (defaults to http://localhost:8088)
export VITE_AGENT_ENDPOINT="http://localhost:8088"
npm run dev
```

Open http://localhost:5173.

## Backend contract

This UI implements [`docs/architecture/api-contract.yaml`](../../docs/architecture/api-contract.yaml):

- `POST /demo/token` — validate a demo employee id (the route name is retained for compatibility).
- `POST /responses` — send a turn (streams SSE); forwards the selected demo identity.

The simulated identity is forwarded on every request. The MCP accepts it only
after validating its API key and enforces authorization server-side. Switching
users resets the session so different users see different simulated data.

> Note: `POST /demo/token` is a demo helper. When running only the bare Foundry
> `ResponsesHostServer`, add this route (see `docs/security-design.md`). In
> production, replace the demo identity flow with real Entra ID sign-in.
