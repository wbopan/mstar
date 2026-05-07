"""Agent base class for the benchmark.

All agents evaluated by the benchmark must subclass Agent and implement act().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from state_bench.schemas import TokenUsage


def _load_pricing() -> dict[str, Any]:
    pricing_path = Path(__file__).resolve().parent.parent / "configs" / "pricing.yaml"
    with open(pricing_path) as f:
        return yaml.safe_load(f) or {}


@dataclass(slots=True)
class AgentRuntimeContext:
    """Per-run context passed to custom agents at construction time.

    This keeps the benchmark memory-agnostic while giving BYO agents access to
    stable task/runtime metadata and an optional free-form config payload.
    """

    task_id: str
    user_id: str
    domain: str
    now: str
    output_dir: str | None = None
    run_idx: int | None = None
    task_summary: str | None = None
    state_requirements: list[dict[str, Any]] = field(default_factory=list)
    task_requirements: list[dict[str, Any]] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


class Agent(ABC):
    """Base class for agents evaluated by the benchmark.

    The orchestrator calls act() once per conversation turn with the full
    conversation history. The agent returns its text response, any tool
    calls it made, and the raw API output items for conversation chaining.

    Subclass this to build agents with memory, RAG, planning, etc.
    Place your implementation in the top-level agents/ directory so it
    can be auto-discovered by the benchmark scripts.

    Two common memory patterns:

    1. **Prompt injection** — retrieve memories before the LLM call and prepend
       them to the conversation or system prompt inside act().

    2. **Memory tool** — add a retrieval tool to the tool schemas so the LLM
       can call it on its own when it needs context from past trajectories.
    """

    total_output_tokens: int = 0

    def __init__(self, runtime_context: AgentRuntimeContext | None = None):
        self.runtime_context = runtime_context
        self.token_usage = TokenUsage()

    def _pricing_for_model(self, model_name: str = "gpt-5.1") -> dict[str, Any]:
        return _load_pricing()["models"][model_name]

    def add_response_usage(self, usage: Any, *, category: str = "other_llm") -> None:
        """Accumulate agent-side Responses API usage for later cost reporting."""
        if not usage:
            return

        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
        input_details = getattr(usage, "input_tokens_details", None)
        output_details = getattr(usage, "output_tokens_details", None)
        cached_input_tokens = int(getattr(input_details, "cached_tokens", 0) or 0)
        reasoning_output_tokens = int(getattr(output_details, "reasoning_tokens", 0) or 0)

        pricing = self._pricing_for_model("gpt-5.1")
        non_cached_input_tokens = max(0, input_tokens - cached_input_tokens)
        input_cost = non_cached_input_tokens * pricing["input_per_million_usd"] / 1_000_000
        cached_input_cost = cached_input_tokens * pricing["cached_input_per_million_usd"] / 1_000_000
        output_cost = output_tokens * pricing["output_per_million_usd"] / 1_000_000
        total_cost = input_cost + cached_input_cost + output_cost

        self.token_usage.input_tokens += input_tokens
        self.token_usage.cached_input_tokens += cached_input_tokens
        self.token_usage.output_tokens += output_tokens
        self.token_usage.reasoning_output_tokens += reasoning_output_tokens
        self.token_usage.total_tokens += total_tokens
        self.token_usage.input_cost_usd += input_cost
        self.token_usage.cached_input_cost_usd += cached_input_cost
        self.token_usage.output_cost_usd += output_cost
        self.token_usage.total_cost_usd += total_cost

        if category == "agent_turn":
            self.token_usage.agent_turn_cost_usd += total_cost
        elif category == "memory_ingestion":
            self.token_usage.memory_ingestion_cost_usd += total_cost
        elif category == "memory_retrieval":
            self.token_usage.memory_retrieval_cost_usd += total_cost
        else:
            self.token_usage.other_llm_cost_usd += total_cost

    def add_embedding_usage(self, input_tokens: int, *, model_name: str = "text-embedding-3-large", category: str = "embedding") -> None:
        """Accumulate embedding-model spend for custom agents."""
        if input_tokens <= 0:
            return

        pricing = self._pricing_for_model(model_name)
        embedding_cost = input_tokens * pricing["input_per_million_usd"] / 1_000_000
        self.token_usage.embedding_input_tokens += input_tokens
        self.token_usage.embedding_cost_usd += embedding_cost
        self.token_usage.total_cost_usd += embedding_cost
        if category == "memory_retrieval":
            self.token_usage.memory_retrieval_cost_usd += embedding_cost
        else:
            self.token_usage.memory_ingestion_cost_usd += embedding_cost

    @abstractmethod
    def act(self, conversation: list[Any]) -> tuple[str, list[dict[str, Any]], list[Any]]:
        """Execute one agent turn.

        Args:
            conversation: Full conversation as Responses API input items
                (stateless chaining pattern — includes message dicts,
                function_call items, and function_call_output items).

        Returns:
            A 3-tuple of:
            - text: The agent's final text response for this turn
            - tool_calls: List of tool call records, each a dict with
              keys {name, arguments, result}
            - raw_items: Raw API output items (for conversation chaining)
        """
        ...

    def prepare_conversation(self, conversation: list[Any]) -> list[Any]:
        """Optional pre-turn hook for retrieval or system-message injection.

        Custom agents can override this to retrieve memories and inject a
        `{"role": "system", "content": ...}` message into the turn input
        without mutating the benchmark's canonical conversation transcript.
        """
        return conversation

    def inject_system_message(
        self,
        conversation: list[Any],
        content: str,
        *,
        before_last_user: bool = True,
    ) -> list[Any]:
        """Return a copy of the turn input with an injected system message."""
        if not content:
            return conversation

        system_item = {"role": "system", "content": content}
        if not before_last_user or not conversation:
            return [*conversation, system_item]
        return [*conversation[:-1], system_item, conversation[-1]]

    def ingest_trajectory(self, trajectory: Any) -> None:
        """Optional post-run hook for BYO ingestion.

        Called once after a trajectory is produced, before it is written to disk.
        Override this to ingest the just-finished conversation into a custom
        memory store or analytics pipeline.
        """
        return None
