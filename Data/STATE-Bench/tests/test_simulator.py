"""Tests for user simulator conversation history handling.

Verifies that UserSimulator correctly accumulates conversation history
across turns and passes it with the system prompt to complete_chat.
"""

from unittest.mock import MagicMock

from state_bench.simulator import UserSimulator


class TestSimulatorConversationHistory:
    """Test that UserSimulator builds messages correctly across turns."""

    def _make_client(self) -> MagicMock:
        """Create a mock LLMClient."""
        client = MagicMock()
        client.complete_chat = MagicMock(return_value="I'd like to cancel my flight.")
        return client

    def test_first_turn_includes_system_prompt_and_opening(self):
        """On the first turn, messages should contain system prompt + conversation with just the opening."""
        client = self._make_client()
        system_prompt = "You are a customer named Alice."

        conversation = [
            {"role": "assistant", "content": "How can I help you?"},
        ]

        UserSimulator(client, system_prompt).respond(conversation)

        # Verify complete_chat was called once
        client.complete_chat.assert_called_once()
        call_kwargs = client.complete_chat.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]

        # Should be [system, user(instruction)]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == system_prompt
        assert messages[1]["role"] == "user"
        assert "CONVERSATION SO FAR:" in messages[1]["content"]
        assert "How can I help you?" in messages[1]["content"]

    def test_second_turn_includes_full_history(self):
        """On the second turn, the conversation text should include all prior messages."""
        client = self._make_client()
        system_prompt = "You are a customer named Alice."

        conversation = [
            {"role": "user", "content": "I need to cancel my flight."},
            {"role": "assistant", "content": "I can help with that. What's your booking ID?"},
        ]

        UserSimulator(client, system_prompt).respond(conversation)

        call_kwargs = client.complete_chat.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]

        instruction = messages[1]["content"]
        # Both messages should appear in the conversation text
        assert "I need to cancel my flight." in instruction
        assert "What's your booking ID?" in instruction

    def test_multi_turn_accumulation(self):
        """Across multiple turns, the conversation text grows to include all prior exchanges."""
        client = self._make_client()
        system_prompt = "You are a customer named Alice."

        # Simulate 3 turns of growing conversation
        conversations = [
            # Turn 1: just agent greeting
            [
                {"role": "assistant", "content": "How can I help you today?"},
            ],
            # Turn 2: user replied, agent asked for ID
            [
                {"role": "user", "content": "Cancel my flight please."},
                {"role": "assistant", "content": "What's your booking ID?"},
            ],
            # Turn 3: user gave ID, agent looked it up
            [
                {"role": "user", "content": "Cancel my flight please."},
                {"role": "assistant", "content": "What's your booking ID?"},
                {"role": "user", "content": "BK-1000"},
                {"role": "assistant", "content": "I found your booking. The fee is $52. Proceed?"},
            ],
        ]

        for i, conv in enumerate(conversations):
            client.complete_chat.reset_mock()
            UserSimulator(client, system_prompt).respond(conv)

            call_kwargs = client.complete_chat.call_args
            messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]

            # System prompt is always the same
            assert messages[0]["content"] == system_prompt

            # Instruction should contain all messages in the conversation
            instruction = messages[1]["content"]
            for msg in conv:
                if msg.get("content"):
                    assert msg["content"] in instruction, f"Turn {i + 1}: missing '{msg['content']}' in instruction"

    def test_tool_calls_included_in_conversation_text(self):
        """Assistant messages with tool_calls should include tool call summaries."""
        client = self._make_client()
        system_prompt = "You are a customer."

        conversation = [
            {"role": "user", "content": "Cancel my flight."},
            {
                "role": "assistant",
                "content": "Your booking is cancelled.",
                "tool_calls": [
                    {"name": "cancel_booking", "arguments": {"booking_id": "BK-1000", "confirm": True}},
                ],
            },
        ]

        UserSimulator(client, system_prompt).respond(conversation)

        call_kwargs = client.complete_chat.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
        instruction = messages[1]["content"]

        # Tool call summary should appear in the conversation text
        assert "cancel_booking" in instruction
        assert "BK-1000" in instruction

    def test_system_prompt_never_duplicated(self):
        """System prompt should appear exactly once in messages, regardless of turn count."""
        client = self._make_client()
        system_prompt = "You are a customer named Alice."

        conversation = [
            {"role": "user", "content": "Cancel my flight."},
            {"role": "assistant", "content": "Done."},
            {"role": "user", "content": "Thanks."},
            {"role": "assistant", "content": "Anything else?"},
        ]

        UserSimulator(client, system_prompt).respond(conversation)

        call_kwargs = client.complete_chat.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]

        system_messages = [m for m in messages if m["role"] == "system"]
        assert len(system_messages) == 1

    def test_temperature_is_set(self):
        """Simulator should use temperature=0.3 for controlled but varied responses."""
        client = self._make_client()

        UserSimulator(client, "You are a customer.").respond([{"role": "assistant", "content": "Hi"}])

        call_kwargs = client.complete_chat.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.3
