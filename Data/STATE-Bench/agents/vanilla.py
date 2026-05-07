"""VanillaAgent — default agent with no memory.

Ships with the benchmark as the baseline. Calls the LLM with tools
directly, implementing the standard Responses API tool-calling loop.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from agents.base import Agent, AgentRuntimeContext
from state_bench.client import LLMClient, PooledLLMClient


class VanillaAgent(Agent):
    """Default agent with no memory. Calls the LLM with tools directly.

    This is the baseline agent used when no custom agent is provided.
    It implements the standard Responses API tool-calling loop: send the
    conversation, execute any tool calls, feed results back, repeat until
    the model produces a final text response.
    """

    def __init__(
        self,
        client: LLMClient | PooledLLMClient,
        system_prompt: str,
        tools: list[dict[str, Any]],
        tool_handlers: dict[str, Callable],
        runtime_context: AgentRuntimeContext | None = None,
    ):
        super().__init__(runtime_context=runtime_context)
        self.client = client
        self.system_prompt = system_prompt
        self.tools = tools
        self.tool_handlers = tool_handlers

    def act(self, conversation: list[Any]) -> tuple[str, list[dict[str, Any]], list[Any]]:
        """Run one turn: LLM call + tool execution loop.

        Pins to a single deployment for the entire tool loop so that
        previous_response_id chaining works across calls.
        """
        all_tool_calls: list[dict[str, Any]] = []
        raw_items: list[Any] = []
        prepared_conversation = self.prepare_conversation(conversation)

        with self.client.pinned() as pinned:
            response = pinned.complete_with_tools(
                instructions=self.system_prompt,
                input=prepared_conversation,
                tools=self.tools,
            )
            if response.usage:
                self.total_output_tokens += response.usage.output_tokens
                self.add_response_usage(response.usage, category="agent_turn")

            # Process tool calls in a loop
            while True:
                tool_calls = [item for item in response.output if item.type == "function_call"]
                if not tool_calls:
                    break

                raw_items.extend(response.output)

                tool_results: list[dict[str, Any]] = []
                for tc in tool_calls:
                    args = json.loads(tc.arguments)
                    handler = self.tool_handlers.get(tc.name)

                    if handler is None:
                        output = json.dumps({"error": f"Unknown tool: {tc.name}"})
                    else:
                        result = handler(args)
                        all_tool_calls.append(
                            {
                                "name": tc.name,
                                "arguments": args,
                                "result": result,
                            }
                        )
                        output = json.dumps(result, ensure_ascii=False)

                    tool_result_item = {
                        "type": "function_call_output",
                        "call_id": tc.call_id,
                        "output": output,
                    }
                    tool_results.append(tool_result_item)
                    raw_items.append(tool_result_item)

                # Follow-up call with tool results — same deployment via pinned client
                response = pinned.complete_with_tools(
                    instructions=self.system_prompt,
                    input=tool_results,
                    tools=self.tools,
                    previous_response_id=response.id,
                )
                if response.usage:
                    self.total_output_tokens += response.usage.output_tokens
                    self.add_response_usage(response.usage, category="agent_turn")

        # Add final response output
        raw_items.extend(response.output)

        return response.output_text or "", all_tool_calls, raw_items
