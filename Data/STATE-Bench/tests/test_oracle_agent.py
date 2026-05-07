from __future__ import annotations

import json
from types import SimpleNamespace

from agents.base import AgentRuntimeContext
from agents.oracle import OracleAgent, OracleMemoryStore


class DummyClient:
    def __init__(self, result, usage=None):
        self.result = result
        self.usage = usage
        self.calls = []

    def complete_json(self, prompt, system_prompt=None, max_tokens=None, reasoning_effort=None):
        self.calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "max_tokens": max_tokens,
                "reasoning_effort": reasoning_effort,
            }
        )
        return dict(self.result)

    def complete_json_response(self, prompt, system_prompt=None, max_tokens=None, reasoning_effort=None):
        self.calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "max_tokens": max_tokens,
                "reasoning_effort": reasoning_effort,
            }
        )
        return SimpleNamespace(output_text=json.dumps(self.result), usage=self.usage)


def _make_usage(*, input_tokens: int, cached_tokens: int, output_tokens: int, reasoning_tokens: int = 0):
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=cached_tokens),
        output_tokens_details=SimpleNamespace(reasoning_tokens=reasoning_tokens),
    )


def test_oracle_store_only_reads_same_task_baselines(tmp_path):
    outputs_dir = tmp_path / "outputs" / "travel"
    (outputs_dir / "run1").mkdir(parents=True)
    (outputs_dir / "run2").mkdir(parents=True)

    same_task = {
        "task_id": "task-a",
        "task_summary": "same",
        "task_completion_pass": 1,
        "task_requirements_reasoning": "same task reasoning",
        "ux_reasoning": "same task ux",
        "conversation": [{"role": "assistant", "content": "same task"}],
    }
    other_task = {
        "task_id": "task-b",
        "task_summary": "other",
        "task_completion_pass": 1,
        "task_requirements_reasoning": "other task reasoning",
        "ux_reasoning": "other task ux",
        "conversation": [{"role": "assistant", "content": "other task"}],
    }

    (outputs_dir / "run1" / "task-a.json").write_text(json.dumps(same_task))
    (outputs_dir / "run2" / "task-b.json").write_text(json.dumps(other_task))

    client = DummyClient(
        {
            "failure_summary": "summary",
            "root_cause": "cause",
            "correct_procedure": ["step one", "step two"],
            "learning_type": "policy_rule",
            "transferable_lesson": "do the exact task-a steps",
        }
    )
    context = AgentRuntimeContext(
        task_id="task-a",
        user_id="user-1",
        domain="travel",
        now="2026-06-15T10:00:00",
        output_dir=str(outputs_dir / "run3"),
        task_summary="ground truth summary for task a",
        state_requirements=[{"entity_type": "booking", "field": "status", "expected_value": "cancelled"}],
        task_requirements=[{"id": "must_explain_fee"}],
        config={"baseline_outputs_dir": str(outputs_dir)},
    )
    store = OracleMemoryStore(client, context)

    learning = store.retrieve()

    assert "do the exact task-a steps" in learning
    assert "step one" in learning
    assert len(client.calls) == 1
    assert "TASK ID: task-a" in client.calls[0]["prompt"]
    assert "TASK ID: task-b" not in client.calls[0]["prompt"]
    assert "TASK SUMMARY: ground truth summary for task a" in client.calls[0]["prompt"]
    assert "must_explain_fee" in client.calls[0]["prompt"]


def test_oracle_agent_ignores_learning_for_other_task(tmp_path):
    learning_dir = tmp_path / "learnings"
    learning_dir.mkdir(parents=True)
    (learning_dir / "task-a.json").write_text(
        json.dumps(
            {
                "task_id": "task-a",
                "failure_summary": "failed task a",
                "root_cause": "root a",
                "correct_procedure": ["only for task a"],
                "transferable_lesson": "lesson a",
            }
        )
    )
    (learning_dir / "task-b.json").write_text(
        json.dumps(
            {
                "task_id": "task-b",
                "failure_summary": "failed task b",
                "root_cause": "root b",
                "correct_procedure": ["only for task b"],
                "transferable_lesson": "lesson b",
            }
        )
    )

    client = DummyClient({"learning": "generated"})
    context = AgentRuntimeContext(
        task_id="task-a",
        user_id="user-1",
        domain="travel",
        now="2026-06-15T10:00:00",
        output_dir=str(tmp_path / "outputs" / "travel" / "run2"),
        task_summary="summary",
        config={"learning_dir": str(learning_dir), "baseline_outputs_dir": str(tmp_path / "empty")},
    )
    agent = OracleAgent(client, "system", [], {}, runtime_context=context)

    prepared = agent.prepare_conversation([{"role": "user", "content": "solve task a"}])

    assert prepared[0]["role"] == "system"
    assert "only for task a" in prepared[0]["content"]
    assert "only for task b" not in prepared[0]["content"]
    assert client.calls == []


def test_oracle_store_skips_regeneration_when_brief_exists(tmp_path):
    learning_dir = tmp_path / "outputs" / "travel" / "learning_opportunities"
    learning_dir.mkdir(parents=True)
    (learning_dir / "task-a.json").write_text(
        json.dumps(
            {
                "task_id": "task-a",
                "failure_summary": "existing summary",
                "root_cause": "existing cause",
                "correct_procedure": ["existing step"],
                "transferable_lesson": "existing lesson",
            }
        )
    )

    client = DummyClient({"failure_summary": "new"})
    context = AgentRuntimeContext(
        task_id="task-a",
        user_id="user-1",
        domain="travel",
        now="2026-06-15T10:00:00",
        output_dir=str(tmp_path / "outputs" / "travel" / "run2"),
        task_summary="summary",
        config={"learning_dir": str(learning_dir), "baseline_outputs_dir": str(tmp_path / "outputs" / "travel")},
    )
    store = OracleMemoryStore(client, context)

    learning = store.retrieve()

    assert "existing step" in learning
    assert client.calls == []


def test_oracle_agent_counts_learning_extraction_usage(tmp_path):
    outputs_dir = tmp_path / "outputs" / "travel"
    (outputs_dir / "run1").mkdir(parents=True)
    (outputs_dir / "run1" / "task-a.json").write_text(
        json.dumps(
            {
                "task_id": "task-a",
                "task_completion_pass": 0,
                "task_requirements_reasoning": "missed requirement",
                "state_requirements_met": 0,
                "task_requirements_met": 0,
                "ux_score": 2.0,
                "conversation": [{"role": "assistant", "content": "bad attempt"}],
            }
        )
    )

    client = DummyClient(
        {
            "failure_summary": "summary",
            "root_cause": "cause",
            "correct_procedure": ["step one"],
            "learning_type": "policy_rule",
            "transferable_lesson": "lesson",
        },
        usage=_make_usage(input_tokens=1000, cached_tokens=400, output_tokens=120, reasoning_tokens=30),
    )
    context = AgentRuntimeContext(
        task_id="task-a",
        user_id="user-1",
        domain="travel",
        now="2026-06-15T10:00:00",
        output_dir=str(outputs_dir / "run2"),
        task_summary="ground truth summary",
        state_requirements=[{"entity_type": "booking", "field": "status", "expected_value": "cancelled"}],
        task_requirements=[{"id": "must_explain_fee"}],
        config={"baseline_outputs_dir": str(outputs_dir)},
    )

    agent = OracleAgent(client, "system", [], {}, runtime_context=context)

    assert "step one" in agent.cached_learning
    assert agent.token_usage.input_tokens == 1000
    assert agent.token_usage.cached_input_tokens == 400
    assert agent.token_usage.output_tokens == 120
    assert agent.token_usage.reasoning_output_tokens == 30
    assert agent.token_usage.agent_turn_cost_usd == 0.0
    assert round(agent.token_usage.memory_ingestion_cost_usd, 6) == round(((600 * 1.25) + (400 * 0.13) + (120 * 10.0)) / 1_000_000, 6)
    assert round(agent.token_usage.total_cost_usd, 6) == round(((600 * 1.25) + (400 * 0.13) + (120 * 10.0)) / 1_000_000, 6)
