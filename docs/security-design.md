# Security Design — Leave Assistant Demo

All HR data is **SIMULATED**. This document describes the trust boundaries and how
the demo satisfies the security acceptance criteria (§23.2).

## Trust boundary & identity

```
User login (demo user switch)
  → frontend sends a simulated employee id to the Hosted Agent (/responses)
  → agent validates the id against the simulated directory
  → agent/toolbox authenticates to the HR MCP with MCP_API_KEY
  → agent forwards the simulated employee id on x-user-token
  → MCP accepts that header only after validating the API key
  → MCP maps the id to a Principal and authorizes every call (service.py)
```

`MCP_API_KEY` is the only MCP authentication mechanism. It is sent as `X-API-Key`;
the caller id rides on `x-user-token` as a plaintext simulated employee id. The
middleware discards the caller id when the API key is missing or wrong. `auth.py`
then resolves the id from the simulated directory, and `service.py` authorizes
every operation server-side.

### Identity forwarding per mode
- **`toolbox` (default).** The agent connects to one governed Foundry Toolbox MCP
  endpoint. The Toolbox authenticates to the platform with an `ai.azure.com` bearer
  on `Authorization` (credentials held by a Foundry connection, not in agent code).
  The simulated employee id is forwarded on `x-user-token`, while the Foundry MCP
  connection supplies `x-api-key` to the Container App.
- **`remote`.** The agent calls the Container App MCP directly and puts the verified
  API key on `x-api-key` and the simulated employee id on `x-user-token`.

Rules enforced in code:
- **No trust in model/client ids.** `service._resolve_target` ignores any supplied
  `employee_id` that doesn't match the verified caller (except a manager's limited
  summary of direct reports). Tests: `mcp-server/tests/test_authz.py`,
  `tests/security/test_authorization_boundary.py`.
- **No existence leakage.** Cross-user denials return a generic `FORBIDDEN` that
  never names the target or reveals whether it exists.
- **Manager least privilege.** `M1001` sees direct-report **balance summaries only**,
  never their history.
- **Production identity requires an IdP.** The simulated employee id is not proof of
  end-user identity. A production system must validate an IdP token and derive the
  employee mapping from trusted claims before forwarding identity to the MCP.

## Guardrails (mapped to §14)
| Threat | Mitigation | Evidence |
|--------|-----------|----------|
| Prompt injection ("ignore rules…") | System instructions treat tool/doc content as data, not commands; MCP authz is independent of the model | `evaluation/datasets/security.jsonl` (`sec-prompt-injection`) |
| Identity spoofing ("my id is E1002") | Identity comes from request context, not model text or tool arguments | `test_impersonation_via_employee_id_is_denied` |
| KB indirect injection | Retrieved text is data; agent never executes embedded instructions | `sec-kb-injection` |
| Sensitive data leak | Server-side authz + generic denials + output minimization | `test_denial_does_not_leak_target_identity` |
| Unconfirmed writes | Write tools use `@tool(approval_mode="always_require")` (HITL) | `local_tools.create_leave_request_preview`, `delete_my_preferences` |

## Data handling in telemetry
- `observability.redact()` masks bearer tokens and partially masks employee ids.
- Spans record masked user id, tool name, status, error type, latency — never full
  tokens, keys, or unmasked business data.
- Preference memory persists only whitelisted keys (`preference_store.ALLOWED_KEYS`);
  balances/history are never stored.

## The `/demo/token` compatibility endpoint
The web demo retains this route name for compatibility, but it returns only a
directory-validated simulated employee id. It does not issue an access token.
Replace the route and user switcher with real Entra ID / IdP sign-in for production.
