# Mock HR MCP Server (SIMULATED)

A standalone Model Context Protocol server exposing simulated HR leave tools with
**server-side authorization**. The API key authenticates the caller, while a
simulated employee id selects the principal; the
`employee_id` in tool arguments is advisory and ignored when it conflicts with the
authenticated caller.

## Tools
| Tool | Purpose |
|------|---------|
| `get_leave_balance` | Current user's leave balance(s) |
| `get_leave_history` | Current user's leave history in a date range |
| `get_leave_types` | Supported leave types + accrual rules |
| `get_public_holidays` | Simulated public holidays (default 2026) |
| `create_leave_request_preview` | Non-binding preview (HITL; never a real record) |

## Error codes
`UNAUTHORIZED`, `FORBIDDEN`, `USER_NOT_FOUND`, `INVALID_DATE_RANGE`,
`LEAVE_TYPE_NOT_SUPPORTED`, `INSUFFICIENT_LEAVE_BALANCE`, `SERVICE_UNAVAILABLE`.

## Identity & authorization
- The server middleware validates `MCP_API_KEY` from **`x-api-key`** before it
  accepts the simulated employee id from **`x-user-token`**.
- `auth.py` resolves that id through the simulated employee directory.
- `service.py` authorizes every call against the verified `Principal`. Regular
  employees see only their own data; manager `M1001` sees direct-report **balance
  summaries only**. Cross-user denials are generic (no existence leakage).

## Mock users
| id | role | note |
|----|------|------|
| E1001 | employee | annual 15/6/9, 3 expiring |
| E1002 | employee | annual 12/11/1 (edge: near-empty) |
| M1001 | manager | manages E1001/E1002 (summary only) |
| E9999 | employee | triggers `SERVICE_UNAVAILABLE` (exception tests) |

## Run
```bash
pip install -r requirements-dev.txt
python -m pytest -q                       # 24 tests
python -m uvicorn leave_mcp.server:app --host 0.0.0.0 --port 8080
```
Endpoint: `http://localhost:8080/mcp` (set `MCP_SERVER_ENDPOINT` for the agent's
`MCP_MODE=remote`). Docker: see `Dockerfile`.

## Validate the deployed Container App

From the repository root, run:

```bash
.venv/bin/python scripts/validate-mcp-containerapp.py \
  --url https://<fqdn>/mcp \
  --key '<api-key>'
```

The script directly uses the supplied endpoint and key to validate MCP
initialization, tool discovery, leave types, and an authenticated balance call.
It does not use Azure CLI or print the API key. Use `--user-id` and
`--leave-type` to override the simulated caller and balance type.

## Deploy independently

From the repository root, set `MCP_API_KEY`, then run:

```bash
bash mcp-server/leave_mcp/deploy-mcp.sh
```

The idempotent script builds this server in the existing ACR, creates or updates
its Container App, validates an authenticated tool call, and writes the endpoint
and API key to the selected local azd environment. Agent deployment is separate.
