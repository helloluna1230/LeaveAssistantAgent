# Copyright (c) Microsoft. All rights reserved.
"""Leave Assistant — Foundry hosted agent entrypoint (Responses protocol).

Run locally:  python main.py   (or: azd ai agent run)
Deploy:       azd deploy
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running as a script (`python agents/leave_assistant/main.py`): put the
# repo root on sys.path so `import agents...` resolves.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Ensure a usable CA bundle BEFORE any SDK/aiohttp client is created (hosted
# images sometimes lack one, causing SSL verify failures on outbound calls).
try:
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except Exception:  # noqa: BLE001
    pass

import logging  # noqa: E402

from agent_framework.foundry import FoundryChatClient  # noqa: E402
from azure.ai.agentserver.optimization import load_config as load_optimization_config  # noqa: E402
from azure.identity import DefaultAzureCredential  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

# The Responses host server ships in the agent-framework-foundry-hosting package.
try:
    from agent_framework_foundry_hosting import ResponsesHostServer  # noqa: E402
except ImportError:  # older/newer layouts re-export it under agent_framework.foundry
    from agent_framework.foundry import ResponsesHostServer  # type: ignore  # noqa: E402

from agents.leave_assistant.agent import build_agent  # noqa: E402
from agents.leave_assistant.config import load_config  # noqa: E402
from agents.leave_assistant.identity import (  # noqa: E402
    current_principal,
    demo_token_for,
    reset_current_user_token,
    set_current_user_token,
)
from agents.leave_assistant.observability import setup_observability  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("leave_assistant.main")


class _IdentityMiddleware:
    """Map each request's simulated identity value onto the contextvar.

    Reads x-user-token / Authorization; falls back to the seeded default identity
    so local requests still have a caller. Pure ASGI (not BaseHTTPMiddleware)
    so the contextvar propagates into the agent run within the same task.
    """

    def __init__(self, app, default_token: str) -> None:
        self.app = app
        self._default = default_token

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        raw = headers.get(b"x-user-token") or headers.get(b"authorization")
        token = raw.decode("latin-1") if raw else None
        if not token or token.removeprefix("Bearer ").strip() in ("", "local-demo"):
            token = self._default
        reset = set_current_user_token(token)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_current_user_token(reset)


async def _demo_token_route(request):
    """Compatibility endpoint returning a validated simulated employee id."""
    from starlette.responses import JSONResponse

    from leave_mcp.schemas import LeaveError

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    employee_id = (body or {}).get("employee_id", "")
    try:
        token = demo_token_for(employee_id)
    except LeaveError as exc:
        return JSONResponse(exc.to_dict(), status_code=400)
    return JSONResponse({"token": token, "employee_id": employee_id})


async def _session_state_route(request):
    """Per-user conversation bookmark (identity-scoped) for cross-device rehydrate.

    GET returns the caller's saved {previous_response_id, conversation}; POST saves
    it. Identity comes from request context set by the middleware,
    never from the client body. Stores no chat content — only a Responses pointer.
    """
    from starlette.responses import JSONResponse

    from agents.leave_assistant import session_store
    from leave_mcp.schemas import LeaveError

    try:
        principal = current_principal()
    except LeaveError as exc:
        return JSONResponse(exc.to_dict(), status_code=401)

    if request.method == "GET":
        return JSONResponse(session_store.store.get(principal.employee_id))

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    saved = session_store.store.set(principal.employee_id, body or {})
    return JSONResponse(saved)


def main() -> None:
    load_dotenv()
    config = load_config()
    optimization_config = load_optimization_config()
    setup_observability(config)
    model = optimization_config.model if optimization_config else config.model_deployment
    instructions = optimization_config.compose_instructions() if optimization_config else config.instructions

    client = FoundryChatClient(
        project_endpoint=config.project_endpoint,
        model=model,
        credential=DefaultAzureCredential(),
    )
    agent = build_agent(client, config, instructions=instructions)

    # Seed a default identity so local requests without a caller still work.
    default_token = demo_token_for(config.demo_default_user)
    set_current_user_token(default_token)
    logger.info("Leave Assistant starting as demo user %s (%s mode).", config.demo_default_user, config.mcp_mode)

    server = ResponsesHostServer(agent)
    # Per-request identity: the frontend forwards the selected employee id, which
    # this middleware maps onto the contextvar so tools authenticate as that user.
    server.add_middleware(_IdentityMiddleware, default_token=default_token)
    # Compatibility route used by the demo user switcher.
    server.add_route("/demo/token", _demo_token_route, methods=["POST"])
    # Per-user conversation bookmark so a returning user rehydrates their thread.
    server.add_route("/session/state", _session_state_route, methods=["GET", "POST"])

    server.run()


if __name__ == "__main__":
    main()
