"""Orchestrator — runs a multi-turn agent-user conversation with tool execution.

The orchestrator:
1. Creates a deep copy of the environment for the run
2. Runs the agent-user-tool loop (agent.act() per turn)
3. Computes efficiency metrics (deterministic)
4. Returns a Trajectory without completion or UX scores; use the scoring scripts separately

Domain-agnostic: all domain-specific behavior is provided via DomainConfig.
"""

from __future__ import annotations

import time
from typing import Any

from agents.base import Agent
from state_bench.client import LLMClient, PooledLLMClient
from state_bench.domain import DomainConfig
from state_bench.schemas import (
    StateDiff,
    TaskDefinition,
    Trajectory,
)
from state_bench.scoring import compute_efficiency
from state_bench.simulator import UserSimulator


def run_task(
    task: TaskDefinition,
    env_data: Any,
    user_id: str,
    client: LLMClient | PooledLLMClient,
    domain: DomainConfig,
    agent: Agent | None = None,
    env: Any | None = None,
) -> Trajectory:
    """Run a single task and return the trajectory.

    Generates the conversation and computes efficiency metrics.
    Does NOT run completion or UX judges — use rescore.py or inline scoring for that.

    Args:
        task: The task definition.
        env_data: The environment data (will be deep-copied). Type varies by domain.
        user_id: The user to run the task for.
        client: LLM client (LLMClient or PooledLLMClient) for agent + simulator.
        domain: Domain configuration providing all domain-specific behavior.
        agent: Agent to evaluate. If None, uses VanillaAgent (no memory).
        env: Optional prebuilt environment instance. When provided, the same env must
            also back the agent's tool handlers.

    Returns:
        A Trajectory with conversation, tool calls, state diff, and efficiency metrics.
    """
    t0 = time.monotonic()

    now = task.now
    if env is None:
        # Deep copy environment for this run
        env_copy = env_data.deep_copy()
        env = domain.environment_class(env_copy, now=now)
    # Build agent (default: VanillaAgent with no memory)
    agent_system_prompt = domain.agent_system_prompt.format(now=now, user_id=user_id)
    if agent is None:
        from agents.vanilla import VanillaAgent

        agent = VanillaAgent(client, agent_system_prompt, domain.tool_schemas, env.tool_handlers)

    # Build simulator
    sim_prompt = domain.build_simulator_prompt(task, env_data, user_id)
    simulator = UserSimulator(client, sim_prompt)

    # Snapshot before the run
    db_before = env.get_full_snapshot()

    # Build conversation
    # `conversation` holds Responses API input items: message dicts + raw output items (function_call,
    # function_call_output). This is the stateless input-array chaining pattern — the full conversation
    # is passed on each turn. We do NOT use previous_response_id across turns because the PooledLLMClient
    # may route different turns to different endpoints that don't share server-side state.
    opening = task.opening_message
    conversation: list[Any] = [{"role": "user", "content": opening}]
    conversation_full: list[dict[str, Any]] = [{"role": "user", "content": opening}]
    all_tool_calls: list[dict[str, Any]] = []
    user_response: str = ""

    print(f"  Task: {task.task_id} | User: {user_id} | Now: {now}")
    print(f"  User: {opening[:100]}")

    for turn in range(domain.max_agent_turns):
        # Build input for this turn — full conversation for stateless chaining
        if turn > 0:
            conversation.append({"role": "user", "content": user_response})

        # Agent turn
        agent_text, tool_calls, raw_items = agent.act(conversation)

        all_tool_calls.extend(tool_calls)
        conversation.extend(raw_items)  # Append raw output items for stateless chaining
        conversation_full.append(
            {
                "role": "assistant",
                "content": agent_text,
                "tool_calls": tool_calls if tool_calls else None,
            }
        )

        tc_names = [tc["name"] for tc in tool_calls]
        print(f"  Turn {turn + 1}: {tc_names if tc_names else 'no tools'} | {agent_text[:80] if agent_text else ''}")

        if turn < domain.max_agent_turns - 1:
            # User simulator responds
            user_response = simulator.respond(conversation_full)
            conversation_full.append({"role": "user", "content": user_response})
            print(f"  User: {user_response[:80]}")

            if domain.check_termination and domain.check_termination(user_response):
                break

    # Snapshot after
    db_after = env.get_full_snapshot()

    # --- Compute metrics (no judge — use rescore.py) ---
    state_diff = StateDiff.compute(db_before, db_after)
    efficiency = compute_efficiency(conversation_full, all_tool_calls)

    elapsed = round(time.monotonic() - t0, 2)
    print(f"\n  {'=' * 40}")
    print(f"  TRAJECTORY ({elapsed}s):")
    if efficiency:
        print(f"    Turns:           {efficiency.turns}")
        print(f"    Tool Calls:      {efficiency.tool_calls}")
        print(f"    Tool Errors:     {efficiency.tool_errors}")
        print(f"    Redundant Calls: {efficiency.redundant_calls}")
    if state_diff:
        print(f"    State Diff:      {'empty' if state_diff.is_empty() else 'changes detected'}")

    trajectory = Trajectory(
        task_id=task.task_id,
        user_id=user_id,
        task_summary=task.task_summary,
        conversation=conversation_full,
        state_diff=state_diff,
        efficiency=efficiency,
        token_usage=agent.token_usage,
    )
    agent.ingest_trajectory(trajectory)
    return trajectory
