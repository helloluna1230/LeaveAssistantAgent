import pytest
from pathlib import Path

from agents.harness.config import DEFAULT, is_write_tool, should_retry
from agents.harness.hooks import HarnessLimitExceeded, RunBudget


ROOT = Path(__file__).resolve().parents[2]


def test_write_tools_flagged():
    assert is_write_tool("create_leave_request_preview")
    assert is_write_tool("delete_my_preferences")
    assert not is_write_tool("get_leave_balance")


def test_retry_only_transient():
    assert should_retry("SERVICE_UNAVAILABLE", attempt=0)
    assert not should_retry("FORBIDDEN", attempt=0)
    assert not should_retry("SERVICE_UNAVAILABLE", attempt=DEFAULT.retry.max_attempts)


def test_step_budget_enforced():
    budget = RunBudget()
    with pytest.raises(HarnessLimitExceeded):
        for _ in range(DEFAULT.max_steps + 2):
            budget.on_step()


def test_tool_call_budget_enforced():
    budget = RunBudget()
    with pytest.raises(HarnessLimitExceeded):
        for _ in range(DEFAULT.max_tool_calls + 2):
            budget.on_tool_call("get_leave_balance")


def test_agents_readme_documents_the_harness_build_contract():
    guide = (ROOT / "agents" / "README.md").read_text(encoding="utf-8")

    required_terms = (
        "快速理解 Leave Assistant",
        "启动流程",
        "单次请求流程",
        "组件职责",
        "MCP_MODE=local",
        "MCP_MODE=remote",
        "MCP_MODE=toolbox",
        "余额查询",
        "政策问答",
        "休假规划",
        "五分钟快速上手",
        "构建新的 Agent 包",
        "当前实现边界",
        "HarnessConfig",
        "start_run",
        "note_tool_call",
        "should_retry_sleep",
        'approval_mode="always_require"',
        "build_agent",
        "ResponsesHostServer",
        "azure.yaml",
        "note_step()",
        "远程 MCP",
        "Toolbox",
    )
    for term in required_terms:
        assert term in guide
