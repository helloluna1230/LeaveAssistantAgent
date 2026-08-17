import pytest

from leave_mcp.server import mcp


@pytest.mark.anyio
async def test_personal_tools_do_not_expose_employee_id():
    tools = {tool.name: tool for tool in await mcp.list_tools()}

    assert "employee_id" not in tools["get_leave_balance"].inputSchema["properties"]
    assert "employee_id" not in tools["get_leave_history"].inputSchema["properties"]