from __future__ import annotations

from unittest.mock import MagicMock

from agents.base import Agent, AgentRuntimeContext
from agents.vanilla import VanillaAgent
from state_bench.orchestrator import run_task


def _make_response(response_id: str, output_items: list, output_text: str = "") -> MagicMock:
    response = MagicMock()
    response.id = response_id
    response.output = output_items
    response.output_text = output_text
    response.status = "completed"
    response.incomplete_details = None
    response.usage = None
    return response


def _make_text_item(text: str) -> MagicMock:
    item = MagicMock()
    item.type = "message"
    item.text = text
    return item


class HookedAgent(VanillaAgent):
    def __init__(self, client, system_prompt, tools, tool_handlers, runtime_context=None):
        super().__init__(client, system_prompt, tools, tool_handlers, runtime_context=runtime_context)
        self.ingest_calls = []

    def prepare_conversation(self, conversation):
        return self.inject_system_message(conversation, "memory: prior successful refund flow")

    def ingest_trajectory(self, trajectory):
        self.ingest_calls.append(trajectory.task_id)


class LegacyAgent(Agent):
    def __init__(self, client, system_prompt, tools, tool_handlers):
        super().__init__()
        self.client = client
        self.system_prompt = system_prompt
        self.tools = tools
        self.tool_handlers = tool_handlers

    def act(self, conversation):
        return "ok", [], []


class DummyEnvData:
    def deep_copy(self):
        return self


class DummyEnv:
    def __init__(self, env_data, now):
        self.tool_handlers = {}

    def get_full_snapshot(self):
        return {}


class DummyTask:
    task_id = "task-1"
    task_summary = "Task summary"
    user_simulator = type("Sim", (), {"user_sim_context": "User simulator context"})()
    user_id = "user_001"
    now = "2026-06-15T10:00:00"
    opening_message = "hello"
    tags = {}


class DummyDomain:
    name = "travel"
    tool_schemas = []
    agent_system_prompt = "You are an agent for {user_id} at {now}."
    environment_class = DummyEnv
    max_agent_turns = 1
    check_termination = None

    @staticmethod
    def build_simulator_prompt(task, env_data, user_id):
        return "sim prompt"


def test_vanilla_prepare_conversation_injects_system_message_before_latest_user():
    text_item = _make_text_item("Hello!")
    response = _make_response("resp_001", [text_item], "Hello!")
    mock = MagicMock(side_effect=[response])

    pinned_client = MagicMock()
    pinned_client.complete_with_tools = mock
    pinned_ctx = MagicMock()
    pinned_ctx.__enter__ = MagicMock(return_value=pinned_client)
    pinned_ctx.__exit__ = MagicMock(return_value=False)
    client = MagicMock()
    client.pinned.return_value = pinned_ctx

    agent = HookedAgent(
        client=client,
        system_prompt="You are a travel agent.",
        tools=[],
        tool_handlers={},
        runtime_context=AgentRuntimeContext(task_id="task-1", user_id="user_001", domain="travel", now="2026-06-15T10:00:00"),
    )

    agent.act([
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ])

    sent_input = mock.call_args_list[0].kwargs["input"]
    assert sent_input[-2] == {"role": "system", "content": "memory: prior successful refund flow"}
    assert sent_input[-1] == {"role": "user", "content": "third"}


def test_run_task_calls_ingest_trajectory_hook_once():
    text_item = _make_text_item("Hello!")
    response = _make_response("resp_001", [text_item], "Hello!")
    mock = MagicMock(side_effect=[response])

    pinned_client = MagicMock()
    pinned_client.complete_with_tools = mock
    pinned_ctx = MagicMock()
    pinned_ctx.__enter__ = MagicMock(return_value=pinned_client)
    pinned_ctx.__exit__ = MagicMock(return_value=False)
    client = MagicMock()
    client.pinned.return_value = pinned_ctx

    agent = HookedAgent(client, "You are an agent.", [], {})

    simulator = MagicMock()
    simulator.respond.return_value = "[TASK_DONE]"

    from unittest.mock import patch

    with patch("state_bench.orchestrator.UserSimulator", return_value=simulator):
        trajectory = run_task(
            task=DummyTask(),
            env_data=DummyEnvData(),
            user_id="user_001",
            client=client,
            domain=DummyDomain(),
            agent=agent,
            env=DummyEnv(DummyEnvData(), now="2026-06-15T10:00:00"),
        )

    assert trajectory.task_id == "task-1"
    assert agent.ingest_calls == ["task-1"]


def test_legacy_agent_can_ignore_runtime_context_support():
    agent = LegacyAgent(client=MagicMock(), system_prompt="x", tools=[], tool_handlers={})
    assert agent.act([]) == ("ok", [], [])
