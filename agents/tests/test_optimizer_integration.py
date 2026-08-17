from types import SimpleNamespace

from agents.leave_assistant import agent as agent_module
from agents.leave_assistant import main as main_module


class _FakeServer:
    def __init__(self, agent) -> None:
        self.agent = agent

    def add_middleware(self, *args, **kwargs) -> None:
        pass

    def add_route(self, *args, **kwargs) -> None:
        pass

    def run(self) -> None:
        pass


def test_main_uses_optimizer_model_and_instructions(monkeypatch):
    app_config = SimpleNamespace(
        project_endpoint="https://example.test/project",
        model_deployment="baseline-model",
        demo_default_user="E1001",
        mcp_mode="local",
    )
    optimizer_config = SimpleNamespace(
        model="optimized-model",
        compose_instructions=lambda: "optimized instructions",
    )
    captured = {}

    monkeypatch.setattr(main_module, "load_dotenv", lambda: None)
    monkeypatch.setattr(main_module, "load_config", lambda: app_config)
    monkeypatch.setattr(main_module, "load_optimization_config", lambda: optimizer_config, raising=False)
    monkeypatch.setattr(main_module, "setup_observability", lambda config: None)
    monkeypatch.setattr(main_module, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(main_module, "demo_token_for", lambda employee_id: "demo-token")
    monkeypatch.setattr(main_module, "set_current_user_token", lambda token: None)
    monkeypatch.setattr(main_module, "ResponsesHostServer", _FakeServer)

    def fake_client(**kwargs):
        captured["model"] = kwargs["model"]
        return object()

    def fake_build_agent(client, config, *, instructions):
        captured["instructions"] = instructions
        return object()

    monkeypatch.setattr(main_module, "FoundryChatClient", fake_client)
    monkeypatch.setattr(main_module, "build_agent", fake_build_agent)

    main_module.main()

    assert captured == {
        "model": "optimized-model",
        "instructions": "optimized instructions",
    }


def test_main_falls_back_when_optimizer_config_is_missing(monkeypatch):
    app_config = SimpleNamespace(
        project_endpoint="https://example.test/project",
        model_deployment="baseline-model",
        instructions="baseline instructions",
        demo_default_user="E1001",
        mcp_mode="local",
    )
    captured = {}

    monkeypatch.setattr(main_module, "load_dotenv", lambda: None)
    monkeypatch.setattr(main_module, "load_config", lambda: app_config)
    monkeypatch.setattr(main_module, "load_optimization_config", lambda: None, raising=False)
    monkeypatch.setattr(main_module, "setup_observability", lambda config: None)
    monkeypatch.setattr(main_module, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(main_module, "demo_token_for", lambda employee_id: "demo-token")
    monkeypatch.setattr(main_module, "set_current_user_token", lambda token: None)
    monkeypatch.setattr(main_module, "ResponsesHostServer", _FakeServer)

    def fake_client(**kwargs):
        captured["model"] = kwargs["model"]
        return object()

    def fake_build_agent(client, config, *, instructions):
        captured["instructions"] = instructions
        return object()

    monkeypatch.setattr(main_module, "FoundryChatClient", fake_client)
    monkeypatch.setattr(main_module, "build_agent", fake_build_agent)

    main_module.main()

    assert captured == {
        "model": "baseline-model",
        "instructions": "baseline instructions",
    }


def test_build_agent_uses_supplied_instructions(monkeypatch):
    config = SimpleNamespace(
        agent_name="leave-assistant",
        mcp_mode="local",
        responses_store=True,
    )
    captured = {}

    def fake_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(agent_module, "Agent", fake_agent)

    agent_module.build_agent(object(), config, instructions="optimized instructions")

    assert captured["instructions"] == "optimized instructions"