#!/usr/bin/env python3
"""Validate the deployed Leave Assistant MCP Container App."""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


EXPECTED_TOOLS = frozenset(
    {
        "get_leave_balance",
        "get_leave_history",
        "get_leave_types",
        "get_public_holidays",
        "create_leave_request_preview",
    }
)


def validate_balance(payload: dict, user_id: str, leave_type: str) -> dict:
    if payload.get("error"):
        error = payload["error"]
        raise ValueError(f"MCP error {error.get('code', 'UNKNOWN')}: {error.get('message', '')}")

    for balance in payload.get("balances", []):
        if balance.get("employee_id") == user_id and balance.get("leave_type") == leave_type:
            return balance
    raise ValueError("MCP balance did not match the requested user and leave type")


def validate_tool_names(tool_names: set[str]) -> None:
    missing = EXPECTED_TOOLS - tool_names
    if missing:
        raise ValueError(f"Missing MCP tools: {', '.join(sorted(missing))}")


def unpack_tool_result(result) -> dict:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    for item in result.content:
        if getattr(item, "type", None) == "text":
            return json.loads(item.text)
    raise ValueError("MCP tool returned no structured or JSON text content")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Full MCP endpoint URL, including /mcp")
    parser.add_argument("--key", required=True, help="MCP API key")
    parser.add_argument("--user-id", default="E1001")
    parser.add_argument("--leave-type", default="annual_leave")
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args(argv)


async def validate_mcp_call(
    endpoint: str,
    api_key: str,
    user_id: str,
    leave_type: str,
    timeout: float,
) -> dict:
    headers = {"X-API-Key": api_key, "x-user-token": user_id}

    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        async with streamable_http_client(endpoint, http_client=client) as (read, write, session_id):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                if not session_id():
                    raise ValueError("MCP server did not establish a session")

                tools = await session.list_tools()
                tool_names = {tool.name for tool in tools.tools}
                validate_tool_names(tool_names)

                leave_types_result = await session.call_tool("get_leave_types", {})
                leave_types_payload = unpack_tool_result(leave_types_result)
                supported_types = {
                    item.get("leave_type") for item in leave_types_payload.get("leave_types", [])
                }
                if leave_type not in supported_types:
                    raise ValueError(f"MCP does not advertise leave type: {leave_type}")

                balance_result = await session.call_tool(
                    "get_leave_balance",
                    {"leave_type": leave_type},
                )
                balance = validate_balance(
                    unpack_tool_result(balance_result),
                    user_id,
                    leave_type,
                )

    return {
        "endpoint": endpoint,
        "mcp": {
            "protocolVersion": initialized.protocolVersion,
            "session": "established",
            "tools": sorted(tool_names),
        },
        "balance": {
            "employeeId": balance["employee_id"],
            "leaveType": balance["leave_type"],
            "remainingDays": balance["remaining_days"],
            "simulated": balance.get("simulated", False),
        },
    }


def redact(message: str, secrets: list[str | None]) -> str:
    result = message
    for secret in secrets:
        if secret:
            result = result.replace(secret, "***")
    return result


def main() -> int:
    args = parse_args()
    try:
        report = asyncio.run(
            validate_mcp_call(
                args.url,
                args.key,
                args.user_id,
                args.leave_type,
                args.timeout,
            )
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print("MCP validation succeeded.")
        return 0
    except Exception as exc:
        print(f"MCP validation failed: {redact(str(exc), [args.key])}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())