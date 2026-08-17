from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.leave_assistant import toolbox_tools


RUNTIME_REQUIREMENTS = Path(__file__).parents[1] / "leave_assistant" / "requirements.txt"


def test_foundry_toolbox_sdk_is_available():
    from agent_framework.foundry import FoundryToolbox

    assert FoundryToolbox is not None


def test_hosted_optimization_loader_is_a_declared_dependency():
    requirements = RUNTIME_REQUIREMENTS.read_text(encoding="utf-8").splitlines()

    assert "azure-ai-agentserver-optimization==1.0.0b1" in requirements


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        (None, {}),
        ("E1001", {"x-user-token": "Bearer E1001"}),
        ("Bearer E1002", {"x-user-token": "Bearer E1002"}),
    ],
)
def test_user_headers_forward_only_the_current_identity(monkeypatch, token, expected):
    monkeypatch.setattr(toolbox_tools, "current_user_token", lambda: token)

    assert toolbox_tools._user_headers({}) == expected


def test_build_toolbox_capabilities_uses_one_connection(monkeypatch):
    created = []
    skills_provider = object()

    class FakeFoundryToolbox:
        def __init__(self, credential, *, url, load_prompts):
            self.credential = credential
            self.url = url
            self.load_prompts = load_prompts
            created.append(self)

        def as_skills_provider(self, *, disable_load_skill_approval):
            assert disable_load_skill_approval is True
            return skills_provider

    monkeypatch.setattr("agent_framework.foundry.FoundryToolbox", FakeFoundryToolbox)

    tools, providers = toolbox_tools.build_toolbox_capabilities(
        SimpleNamespace(toolbox_endpoint="https://example.test/toolbox/mcp")
    )

    assert len(created) == 1
    assert created[0] in tools
    assert created[0]._header_provider({}) == {}
    assert providers == [skills_provider]
    assert toolbox_tools.plan_leave in tools
    assert toolbox_tools.get_my_preferences in tools
    assert toolbox_tools.save_my_preferences in tools
    assert toolbox_tools.delete_my_preferences in tools