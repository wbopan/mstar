"""Tests for canonical scoring helpers in state_bench.scoring."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from state_bench.schemas import (
    BinaryScore,
    StateDiff,
    TaskDefinition,
    TaskRequirementsScore,
    UserSimulatorConfig,
    UXQualityResult,
)
from state_bench.scoring import (
    TaskRequirementsJudge,
    UXQualityJudge,
    build_ux_prompt,
    combine_task_completion,
    evaluate_state_requirements,
    evaluate_task_requirements_empty,
)


def _make_task() -> TaskDefinition:
    """Create a minimal TaskDefinition for testing."""
    return TaskDefinition(
        task_id="test-task",
        task_summary="Task: Test task. Challenge: Test challenge. Outcome: Agent should do X.",
        user_id="user_001",
        now="2026-06-15T10:00:00",
        opening_message="Hello",
        user_simulator=UserSimulatorConfig(
            personality="cooperative",
            user_sim_context="User is trying to complete the task without knowing the hidden answer.",
            known_info=["user_id: user_001"],
            unknown_info=["fee amount"],
            task_rules=["End with [TASK_DONE]"],
        ),
    )


def _make_state_task(requirements: list[dict]) -> TaskDefinition:
    task = _make_task()
    task.state_requirements = requirements
    return task


class TestDeterministicStateRequirements:
    """Tests for structured state requirement matching."""

    def test_treats_missing_state_requirements_as_empty_requirements(self):
        task = _make_task()
        task.state_requirements = None

        result = evaluate_state_requirements(task, StateDiff())

        assert result == BinaryScore(
            score=1,
            reasoning="Task defines no required state changes and the saved state_diff is empty.",
        )

    def test_passes_for_explicit_no_write_task_with_empty_diff(self):
        task = _make_state_task([])

        result = evaluate_state_requirements(task, StateDiff())

        assert result == BinaryScore(
            score=1,
            reasoning="Task defines no required state changes and the saved state_diff is empty.",
        )

    def test_fails_for_explicit_no_write_task_with_non_empty_diff(self):
        task = _make_state_task([])

        result = evaluate_state_requirements(
            task,
            StateDiff(modified={"bookings": {"BK-1": {"status": {"old": "confirmed", "new": "cancelled"}}}}),
        )

        assert result == BinaryScore(
            score=0,
            reasoning="Task defines no required state changes but the saved state_diff is not empty.",
        )

    def test_passes_for_matching_modified_field(self):
        task = _make_state_task(
            [{"entity_type": "bookings", "record_key": "BK-1", "field": "status", "expected_value": "cancelled"}]
        )
        diff = StateDiff(modified={"bookings": {"BK-1": {"status": {"old": "confirmed", "new": "cancelled"}}}})

        result = evaluate_state_requirements(task, diff)

        assert result == BinaryScore(score=1, reasoning="All required state assertions matched the saved state_diff.")

    def test_fails_when_unexpected_modified_field_is_present(self):
        task = _make_state_task(
            [{"entity_type": "bookings", "record_key": "BK-1", "field": "status", "expected_value": "cancelled"}]
        )
        diff = StateDiff(
            modified={
                "bookings": {
                    "BK-1": {
                        "status": {"old": "confirmed", "new": "cancelled"},
                        "refund_amount": {"old": None, "new": 100},
                    }
                }
            }
        )

        result = evaluate_state_requirements(task, diff)

        assert result is not None
        assert result.score == 0
        assert "unexpected assertions:" in result.reasoning
        assert "bookings.BK-1.refund_amount=100" in result.reasoning

    def test_fails_when_unexpected_booking_configuration_change_is_present(self):
        task = _make_state_task(
            [{"entity_type": "bookings", "record_key": "BK-1", "field": "flight_id", "expected_value": "UA200"}]
        )
        diff = StateDiff(
            modified={
                "bookings": {
                    "BK-1": {
                        "flight_id": {"old": "UA100", "new": "UA200"},
                        "cabin_class": {"old": "economy", "new": "business"},
                        "meal_preference": {"old": "standard", "new": "vegan"},
                    }
                }
            }
        )

        result = evaluate_state_requirements(task, diff)

        assert result is not None
        assert result.score == 0
        assert 'bookings.BK-1.cabin_class="business"' in result.reasoning
        assert 'bookings.BK-1.meal_preference="vegan"' in result.reasoning

    def test_fails_for_under_specified_created_record(self):
        task = _make_state_task(
            [{"entity_type": "bookings", "record_key": "BK-NEW", "field": "payment_method", "expected_value": "points"}]
        )
        diff = StateDiff(created={"bookings": {"BK-NEW": {"payment_method": "points", "status": "confirmed"}}})

        result = evaluate_state_requirements(task, diff)

        assert result is not None
        assert result.score == 0
        assert "unexpected assertions:" in result.reasoning
        assert 'bookings.BK-NEW.status="confirmed"' in result.reasoning

    def test_passes_for_fully_specified_created_record(self):
        task = _make_state_task(
            [
                {"entity_type": "bookings", "record_key": "BK-NEW", "field": "payment_method", "expected_value": "points"},
                {"entity_type": "bookings", "record_key": "BK-NEW", "field": "status", "expected_value": "confirmed"},
            ]
        )
        diff = StateDiff(created={"bookings": {"BK-NEW": {"payment_method": "points", "status": "confirmed"}}})

        result = evaluate_state_requirements(task, diff)

        assert result == BinaryScore(score=1, reasoning="All required state assertions matched the saved state_diff.")

    def test_passes_for_created_record_matched_by_match_fields(self):
        task = _make_state_task(
            [
                {
                    "entity_type": "bookings",
                    "match_fields": {"user_id": "user_005", "flight_id": "B6202"},
                    "expected_fields": {
                        "status": "confirmed",
                        "cabin_class": "economy",
                        "meal_preference": "vegan",
                    },
                }
            ]
        )
        diff = StateDiff(
            created={
                "bookings": {
                    "BK-2042": {
                        "user_id": "user_005",
                        "flight_id": "B6202",
                        "status": "confirmed",
                        "cabin_class": "economy",
                        "meal_preference": "vegan",
                    }
                }
            }
        )

        result = evaluate_state_requirements(task, diff)

        assert result == BinaryScore(score=1, reasoning="All required state assertions matched the saved state_diff.")

    def test_match_fields_created_record_can_use_match_only_assertion(self):
        task = _make_state_task(
            [
                {
                    "entity_type": "cart_items",
                    "match_fields": {"customer_id": "shop_002", "product_id": "SP-1001", "gift_wrap": False, "quantity": 1},
                    "expected_fields": {},
                }
            ]
        )
        diff = StateDiff(
            created={
                "cart_items": {
                    "CI-0001": {
                        "customer_id": "shop_002",
                        "product_id": "SP-1001",
                        "quantity": 1,
                        "gift_wrap": False,
                        "variant_id": None,
                    }
                }
            }
        )

        result = evaluate_state_requirements(task, diff)

        assert result == BinaryScore(score=1, reasoning="All required state assertions matched the saved state_diff.")

    def test_match_fields_created_record_ignores_unspecified_extra_fields(self):
        task = _make_state_task(
            [
                {
                    "entity_type": "cart_items",
                    "match_fields": {"customer_id": "shop_002", "product_id": "SP-1001"},
                    "expected_fields": {"quantity": 1, "gift_wrap": False},
                }
            ]
        )
        diff = StateDiff(
            created={
                "cart_items": {
                    "CI-0001": {
                        "customer_id": "shop_002",
                        "product_id": "SP-1001",
                        "quantity": 1,
                        "gift_wrap": False,
                        "variant_id": None,
                    }
                }
            }
        )

        result = evaluate_state_requirements(task, diff)

        assert result == BinaryScore(score=1, reasoning="All required state assertions matched the saved state_diff.")

    def test_fails_when_created_record_match_fields_find_no_record(self):
        task = _make_state_task(
            [
                {
                    "entity_type": "bookings",
                    "match_fields": {"user_id": "user_005", "flight_id": "B6202"},
                    "expected_fields": {"status": "confirmed"},
                }
            ]
        )
        diff = StateDiff(created={"bookings": {"BK-2042": {"user_id": "user_005", "flight_id": "UA200", "status": "confirmed"}}})

        result = evaluate_state_requirements(task, diff)

        assert result is not None
        assert result.score == 0
        assert '"match_count": 0' in result.reasoning

    def test_fails_when_created_record_match_fields_are_ambiguous(self):
        task = _make_state_task(
            [
                {
                    "entity_type": "bookings",
                    "match_fields": {"user_id": "user_005"},
                    "expected_fields": {"status": "confirmed"},
                }
            ]
        )
        diff = StateDiff(
            created={
                "bookings": {
                    "BK-2042": {"user_id": "user_005", "flight_id": "B6202", "status": "confirmed"},
                    "BK-2043": {"user_id": "user_005", "flight_id": "UA200", "status": "confirmed"},
                }
            }
        )

        result = evaluate_state_requirements(task, diff)

        assert result is not None
        assert result.score == 0
        assert '"match_count": 2' in result.reasoning

    def test_fails_when_record_missing(self):
        task = _make_state_task(
            [{"entity_type": "bookings", "record_key": "BK-404", "field": "status", "expected_value": "cancelled"}]
        )

        result = evaluate_state_requirements(task, StateDiff())

        assert result is not None
        assert result.score == 0
        assert "missing assertions:" in result.reasoning
        assert 'bookings.BK-404.status="cancelled"' in result.reasoning

    def test_fails_when_field_missing(self):
        task = _make_state_task(
            [{"entity_type": "bookings", "record_key": "BK-1", "field": "refund_amount", "expected_value": 100}]
        )
        diff = StateDiff(modified={"bookings": {"BK-1": {"status": {"old": "confirmed", "new": "cancelled"}}}})

        result = evaluate_state_requirements(task, diff)

        assert result is not None
        assert result.score == 0
        assert "missing assertions:" in result.reasoning
        assert "bookings.BK-1.refund_amount=100" in result.reasoning
        assert "unexpected assertions:" in result.reasoning
        assert 'bookings.BK-1.status="cancelled"' in result.reasoning

    def test_fails_when_value_mismatched(self):
        task = _make_state_task(
            [{"entity_type": "bookings", "record_key": "BK-1", "field": "change_fee", "expected_value": 150}]
        )
        diff = StateDiff(modified={"bookings": {"BK-1": {"change_fee": {"old": None, "new": 75}}}})

        result = evaluate_state_requirements(task, diff)

        assert result is not None
        assert result.score == 0
        assert "missing assertions:" in result.reasoning
        assert "bookings.BK-1.change_fee=150" in result.reasoning
        assert "unexpected assertions:" in result.reasoning
        assert "bookings.BK-1.change_fee=75" in result.reasoning


def _make_prompts_dir_with_task_requirements() -> Path:
    """Create a temp dir with task requirement templates."""
    d = tempfile.mkdtemp()
    base = Path(d)
    (base / "judge_task_requirements.md").write_text(
        "Task summary: $task_summary\nRequirements: $task_requirements\nInstructions: judge exactly\nConversation: $conversation"
    )
    return base


class TestTaskRequirementsJudge:
    def test_empty_requirements_auto_pass(self):
        task = _make_task()
        task.task_requirements = []

        result = evaluate_task_requirements_empty(task)

        assert result == TaskRequirementsScore(
            score=1,
            reasoning="Task defines no non-state task requirements.",
            details=[],
        )

    def test_judge_returns_binary_score_and_details(self):
        client = MagicMock()
        client.complete_json.return_value = {
            "score": 1,
            "reasoning": "All requirements were satisfied.",
            "details": [{"id": "r1", "passed": True, "reasoning": "Agent did it."}],
        }
        prompts_dir = _make_prompts_dir_with_task_requirements()
        judge = TaskRequirementsJudge(client, prompts_dir, "Judge")
        task = _make_task()
        task.task_requirements = [{"id": "r1", "kind": "must", "requirement": "Do it", "evidence": "conversation"}]

        result = judge.evaluate(task, [{"role": "assistant", "content": "done"}], [], StateDiff())

        assert result == TaskRequirementsScore(
            score=1,
            reasoning="All requirements were satisfied.",
            details=[{"id": "r1", "passed": True, "reasoning": "Agent did it."}],
        )

    def test_judge_uses_auto_pass_without_llm_call_for_empty_requirements(self):
        client = MagicMock()
        prompts_dir = _make_prompts_dir_with_task_requirements()
        judge = TaskRequirementsJudge(client, prompts_dir, "Judge")
        task = _make_task()
        task.task_requirements = []

        result = judge.evaluate(task, [], [], StateDiff())

        assert result is not None
        assert result.score == 1
        client.complete_json.assert_not_called()


class TestCombineTaskCompletion:
    def test_returns_none_when_task_requirements_score_is_missing(self):
        assert combine_task_completion(BinaryScore(score=1, reasoning="ok"), None) is None

    def test_requires_both_surfaces_when_both_exist(self):
        result = combine_task_completion(
            BinaryScore(score=0, reasoning="bad state"),
            TaskRequirementsScore(score=1, reasoning="ok", details=[]),
        )
        assert result == 0


def _make_prompts_dir_with_ux() -> Path:
    d = tempfile.mkdtemp()
    base = Path(d)
    (base / "judge_ux_quality_v3_user.md").write_text(
        "$task_summary\nConversation: $conversation"
    )
    (base / "judge_ux_quality_v3.md").write_text("You are a UX judge.")
    return base


class TestUXQualityJudge:
    def test_build_ux_prompt_includes_task_context_and_conversation(self):
        prompts_dir = _make_prompts_dir_with_ux()
        task = _make_task()
        task.task_summary = "Task: desc\nChallenge: chall"
        prompt = build_ux_prompt(
            task=task,
            conversation=[{"role": "user", "content": "hello"}],
            tool_calls=[],
            prompts_dir=prompts_dir,
        )
        assert "Task: desc" in prompt
        assert "Challenge: chall" in prompt
        assert "hello" in prompt

    def test_evaluate_returns_ux_result(self):
        client = MagicMock()
        client.complete_json.return_value = {
            "consent": 4,
            "ease": 5,
            "discovery": 3,
            "information_quality": 4,
            "disambiguation": 5,
            "reasoning": "solid",
        }
        prompts_dir = _make_prompts_dir_with_ux()
        judge = UXQualityJudge(client, prompts_dir, "Judge")

        task = _make_task()
        task.task_summary = "Task: desc\nChallenge: chall"
        result = judge.evaluate(
            task=task,
            conversation=[{"role": "assistant", "content": "done"}],
            tool_calls=[],
        )

        assert result == UXQualityResult(
            consent=4,
            ease=5,
            discovery=3,
            information_quality=4,
            disambiguation=5,
            reasoning="solid",
        )
        assert result.ux_score == 4.2

    def test_evaluate_returns_none_on_exception(self):
        client = MagicMock()
        client.complete_json.side_effect = RuntimeError("boom")
        prompts_dir = _make_prompts_dir_with_ux()
        judge = UXQualityJudge(client, prompts_dir, "Judge")

        result = judge.evaluate(task=_make_task(), conversation=[], tool_calls=[])

        assert result is None


def test_state_requirements_can_match_preserved_seeded_state_from_task_env(tmp_path):
    task = _make_state_task(
        [
            {"entity_type": "cart_items", "match_fields": {"customer_id": "shop_004", "product_id": "SP-1002"}, "expected_fields": {"quantity": 1, "gift_wrap": False}},
            {"entity_type": "carts", "record_key": "CART-shop_004", "field": "subtotal", "expected_value": 1078},
            {"entity_type": "carts", "record_key": "CART-shop_004", "field": "total", "expected_value": 1078},
        ]
    )
    env_path = tmp_path / 'task_env.json'
    env_path.write_text(
        json.dumps(
            {
                "customers": {"shop_004": {"customer_id": "shop_004"}},
                "carts": {
                    "CART-shop_004": {
                        "cart_id": "CART-shop_004",
                        "customer_id": "shop_004",
                        "item_ids": ["CI-A1", "CI-A2"],
                        "subtotal": 1128,
                        "total": 1128,
                    }
                },
                "cart_items": {
                    "CI-A1": {"cart_item_id": "CI-A1", "customer_id": "shop_004", "product_id": "SP-1002", "quantity": 1, "gift_wrap": False},
                    "CI-A2": {"cart_item_id": "CI-A2", "customer_id": "shop_004", "product_id": "SP-2006", "quantity": 1, "gift_wrap": False},
                },
            }
        )
    )
    task.task_env_path = str(env_path)
    diff = StateDiff(
        modified={"carts": {"CART-shop_004": {"subtotal": {"old": 1128, "new": 1078}, "total": {"old": 1128, "new": 1078}}}},
        created={"cart_items": {"CI-0003": {"cart_item_id": "CI-0003", "customer_id": "shop_004", "product_id": "SP-2005", "quantity": 1, "gift_wrap": False}}},
        deleted={"cart_items": {"CI-A2": {"cart_item_id": "CI-A2", "customer_id": "shop_004", "product_id": "SP-2006", "quantity": 1, "gift_wrap": False}}},
    )

    result = evaluate_state_requirements(task, diff)

    assert result == BinaryScore(score=1, reasoning="All required state assertions matched the saved state_diff.")


def test_state_requirements_can_match_preserved_seeded_final_fields_after_remove_only(tmp_path):
    task = _make_state_task(
        [
            {"entity_type": "carts", "record_key": "CART-shop_004", "field": "applied_promo_codes", "expected_value": []},
            {"entity_type": "carts", "record_key": "CART-shop_004", "field": "subtotal", "expected_value": 129},
            {"entity_type": "carts", "record_key": "CART-shop_004", "field": "total", "expected_value": 129},
        ]
    )
    env_path = tmp_path / 'task_env.json'
    env_path.write_text(
        json.dumps(
            {
                "customers": {"shop_004": {"customer_id": "shop_004"}},
                "carts": {
                    "CART-shop_004": {
                        "cart_id": "CART-shop_004",
                        "customer_id": "shop_004",
                        "item_ids": [],
                        "subtotal": 0,
                        "total": 0,
                        "applied_promo_codes": [],
                    }
                },
                "cart_items": {},
                "promotions": {},
            }
        )
    )
    task.task_env_path = str(env_path)
    diff = StateDiff(
        modified={"carts": {"CART-shop_004": {"subtotal": {"old": 0, "new": 129}, "total": {"old": 0, "new": 129}}}},
        created={"cart_items": {"CI-0001": {"cart_item_id": "CI-0001", "customer_id": "shop_004", "product_id": "SP-2006", "quantity": 1, "gift_wrap": False}}},
    )

    result = evaluate_state_requirements(task, diff)

    assert result == BinaryScore(score=1, reasoning="All required state assertions matched the saved state_diff.")


def test_replay_created_record_fallback_should_be_direct_record_key_assertions():
    from state_bench.replay import derive_state_requirements_from_state_diff

    diff = StateDiff(
        created={
            "order_items": {
                "ITEM-NEW": {
                    "item_id": "ITEM-NEW",
                    "order_id": "ORD-1",
                    "product_id": "PROD-1",
                    "item_status": "confirmed",
                }
            }
        }
    )

    requirements = derive_state_requirements_from_state_diff(diff)

    assert all(req.get("record_key") == "ITEM-NEW" for req in requirements)
    assert all("match_fields" not in req for req in requirements)
    assert {req["field"] for req in requirements} == {"item_id", "order_id", "product_id", "item_status"}
