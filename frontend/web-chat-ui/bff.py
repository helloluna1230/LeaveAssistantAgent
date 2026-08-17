"""BFF for the single-user Leave Assistant web UI.

Serves the built static site AND proxies POST /responses to the Foundry HOSTED
agent, injecting a Managed-Identity `ai.azure.com` bearer so the browser never
holds a Foundry token. Streams the agent's SSE straight back to the browser.

Env:
  AGENT_RESPONSES_ENDPOINT  Full hosted-agent responses URL
      (…/agents/<name>/endpoint/protocols/openai/responses?api-version=v1)
  AGENT_TOKEN_SCOPE         Token scope (default https://ai.azure.com/.default)
  STATIC_DIR                Built site dir (default ./dist)
  PORT                      Listen port (default 8080)
"""

from __future__ import annotations

import os

import httpx
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

AGENT_ENDPOINT = os.environ.get("AGENT_RESPONSES_ENDPOINT", "")
SCOPE = os.environ.get("AGENT_TOKEN_SCOPE", "https://ai.azure.com/.default")
STATIC_DIR = os.environ.get("STATIC_DIR", "dist")

_token = get_bearer_token_provider(DefaultAzureCredential(), SCOPE)


async def responses(request: Request):
    if not AGENT_ENDPOINT:
        return JSONResponse({"error": "AGENT_RESPONSES_ENDPOINT not set"}, status_code=500)
    body = await request.body()
    headers = {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
        "Accept": request.headers.get("accept", "application/json, text/event-stream"),
    }
    # Forward the caller-asserted identity (demo/single-user) to the agent.
    user_token = request.headers.get("x-user-token")
    if user_token:
        headers["x-user-token"] = user_token
    client = httpx.AsyncClient(timeout=httpx.Timeout(180.0))
    upstream_req = client.build_request("POST", AGENT_ENDPOINT, content=body, headers=headers)
    upstream = await client.send(upstream_req, stream=True)

    async def stream():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        stream(),
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )


async def healthz(_request: Request):
    return JSONResponse({"ok": True})


app = Starlette(
    routes=[
        Route("/responses", responses, methods=["POST"]),
        Route("/healthz", healthz, methods=["GET"]),
        Mount("/", app=StaticFiles(directory=STATIC_DIR, html=True), name="static"),
    ]
)
