import json

from domains.customer_support.config import get_config
from domains.customer_support.generate_tasks import _audit_product_lookup
from domains.customer_support.task_registry import build_replay_trace, build_task_environment, reset_counters
from domains.customer_support.task_registry._builders import _build_task_json
from domains.customer_support.task_registry.scenarios.cancellations import scenario_cancel_partial, scenario_cancel_price_match
from domains.customer_support.task_registry.scenarios.challenge_advanced_exceptions import (
    scenario_challenge_two_electronics_gold,
)
from domains.customer_support.task_registry.scenarios.challenge_compounded_outcomes_a import (
    scenario_challenge_gold_7day_all_parts,
    scenario_challenge_seasonal_restock_shipping_triple,
)
from domains.customer_support.task_registry.scenarios.challenge_disputes import (
    scenario_challenge_damaged_plus_wrong,
    scenario_challenge_fragile_goodwill_separate,
    scenario_challenge_price_match_refund,
)
from domains.customer_support.task_registry.scenarios.challenge_fees_loyalty import (
    scenario_challenge_gold_restocking_discount,
)
from domains.customer_support.task_registry.scenarios.challenge_policy_clawbacks import (
    scenario_challenge_bulk_clawback,
    scenario_challenge_exchange_oos_pivot,
)
from domains.customer_support.task_registry.scenarios.compound_cases import scenario_compound_partial_cancel_return
from domains.customer_support.task_registry.scenarios.edge_cases import scenario_edge_all_windows_expired
from domains.customer_support.task_registry.scenarios.exchanges import (
    scenario_exchange_more_expensive,
    scenario_exchange_outside_window,
)
from domains.customer_support.task_registry.scenarios.returns_refunds import scenario_return_partial_order
from domains.customer_support.task_registry.scenarios.shipping_delivery import (
    scenario_shipping_late_compensation,
    scenario_shipping_stuck_in_transit,
)
from state_bench.replay import derive_state_requirements_from_state_diff, execute_replay_trace


def test_customer_support_bridge_serializer_and_task_env() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_return_partial_order()
    task_data["task_id"] = f"1-{task_data['task_id']}"

    task_env = build_task_environment(products, orders, items, warranties, task_data)
    task_data["task_env_path"] = f"domains/customer_support/task_envs/{task_data['task_id']}.json"
    public = _build_task_json(task_data)

    assert public["task_env_path"] == "domains/customer_support/task_envs/1-return_partial_order.json"
    assert public["task_type"] == "return_item"
    assert public["task_requirements"]
    assert public["task_summary"].startswith(
        "**Task:** The customer wants to return only the headphones from a discounted three-item order."
    )

    env_dict = task_env.to_dict()
    assert sorted(env_dict) == ["customers", "order_items", "orders", "products", "warranties"]
    assert len(env_dict["orders"]) == 1
    assert len(env_dict["order_items"]) == 3
    assert len(env_dict["products"]) == 3
    assert len(env_dict["customers"]) == 5
    assert len(env_dict["warranties"]) == 0

    # Ensure the generated payload remains TaskDefinition-compatible JSON.
    json.dumps(public)


def test_customer_support_return_replay_trace_executes_and_derives_state() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_return_partial_order()
    env_data = build_task_environment(products, orders, items, warranties, task_data)

    replay_trace = build_replay_trace(task_data, env_data)

    assert [step["name"] for step in replay_trace] == [
        "get_order",
        "get_policies",
        "get_policies",
        "process_return",
        "process_return",
    ]
    assert replay_trace[-1]["arguments"] == {
        "item_id": "ITEM-9001",
        "reason": "changed_mind",
        "confirm": True,
    }

    domain = get_config()
    env = domain.environment_class(env_data.deep_copy(), now=task_data["scenario_template"]["now"])
    _executed, state_diff = execute_replay_trace(env, replay_trace)
    requirements = derive_state_requirements_from_state_diff(
        state_diff,
        replay_trace=replay_trace,
        post_snapshot=env.get_full_snapshot(),
    )

    assert any(
        req.get("entity_type") == "order_items"
        and req.get("record_key") == "ITEM-9001"
        and req.get("field") == "item_status"
        and req.get("expected_value") == "returned"
        for req in requirements
    )
    assert any(
        req.get("entity_type") == "orders"
        and req.get("record_key") == "ORD-6001"
        and req.get("field") == "status"
        and req.get("expected_value") == "partially_returned"
        for req in requirements
    )


def test_customer_support_partial_cancel_replay_targets_only_cancelled_item() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_cancel_partial()
    env_data = build_task_environment(products, orders, items, warranties, task_data)

    replay_trace = build_replay_trace(task_data, env_data)

    assert replay_trace[-2]["name"] == "cancel_order"
    assert replay_trace[-2]["arguments"]["item_ids"] == ["ITEM-9105"]
    assert replay_trace[-1]["arguments"]["item_ids"] == ["ITEM-9105"]

    domain = get_config()
    env = domain.environment_class(env_data.deep_copy(), now=task_data["scenario_template"]["now"])
    _executed, state_diff = execute_replay_trace(env, replay_trace)
    requirements = derive_state_requirements_from_state_diff(
        state_diff,
        replay_trace=replay_trace,
        post_snapshot=env.get_full_snapshot(),
    )

    assert any(
        req.get("entity_type") == "order_items"
        and req.get("record_key") == "ITEM-9105"
        and req.get("field") == "item_status"
        and req.get("expected_value") == "cancelled"
        for req in requirements
    )
    assert not any(
        req.get("entity_type") == "order_items"
        and req.get("record_key") in {"ITEM-9106", "ITEM-9107"}
        and req.get("field") == "item_status"
        for req in requirements
    )


def test_customer_support_shipping_stuck_in_transit_replay_derives_refund_only_state() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_shipping_stuck_in_transit()
    env_data = build_task_environment(products, orders, items, warranties, task_data)

    replay_trace = build_replay_trace(task_data, env_data)

    assert [step["name"] for step in replay_trace] == [
        "get_order",
        "get_policies",
        "get_policies",
        "process_refund",
        "process_refund",
    ]

    domain = get_config()
    env = domain.environment_class(env_data.deep_copy(), now=task_data["scenario_template"]["now"])
    _executed, state_diff = execute_replay_trace(env, replay_trace)
    requirements = derive_state_requirements_from_state_diff(
        state_diff,
        replay_trace=replay_trace,
        post_snapshot=env.get_full_snapshot(),
    )

    assert any(
        req.get("entity_type") == "order_items"
        and req.get("record_key") == "ITEM-9175"
        and req.get("field") == "refund_amount"
        and req.get("expected_value") == 67
        for req in requirements
    )
    assert not any(
        req.get("entity_type") == "orders"
        and req.get("record_key") == "ORD-6027"
        and req.get("field") == "status"
        for req in requirements
    )


def test_customer_support_compound_partial_cancel_return_replay_derives_partial_cancelled_order() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_compound_partial_cancel_return()
    env_data = build_task_environment(products, orders, items, warranties, task_data)

    replay_trace = build_replay_trace(task_data, env_data)

    domain = get_config()
    env = domain.environment_class(env_data.deep_copy(), now=task_data["scenario_template"]["now"])
    _executed, state_diff = execute_replay_trace(env, replay_trace)
    requirements = derive_state_requirements_from_state_diff(
        state_diff,
        replay_trace=replay_trace,
        post_snapshot=env.get_full_snapshot(),
    )

    assert any(
        req.get("entity_type") == "orders"
        and req.get("record_key") == "ORD-6047"
        and req.get("field") == "status"
        and req.get("expected_value") == "partially_cancelled"
        for req in requirements
    )


def test_customer_support_no_write_edge_case_produces_no_replay_trace() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_edge_all_windows_expired()
    env_data = build_task_environment(products, orders, items, warranties, task_data)

    replay_trace = build_replay_trace(task_data, env_data)

    assert replay_trace == [
        {"name": "get_order", "arguments": {"order_id": task_data["scenario_template"]["order_id"]}},
        {"name": "get_policies", "arguments": {"topic": "return"}},
    ]

    domain = get_config()
    env = domain.environment_class(env_data.deep_copy(), now=task_data["scenario_template"]["now"])
    _executed, state_diff = execute_replay_trace(env, replay_trace)
    requirements = derive_state_requirements_from_state_diff(
        state_diff,
        replay_trace=replay_trace,
        post_snapshot=env.get_full_snapshot(),
    )

    assert requirements == []


def test_customer_support_denied_exchange_preview_derives_empty_state_requirements() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_exchange_outside_window()
    env_data = build_task_environment(products, orders, items, warranties, task_data)

    replay_trace = build_replay_trace(task_data, env_data)

    assert replay_trace == [
        {"name": "get_order", "arguments": {"order_id": task_data["scenario_template"]["order_id"]}},
        {"name": "get_policies", "arguments": {"topic": "exchange"}},
        {
            "name": "process_exchange",
            "arguments": {
                "item_id": task_data["scenario_template"]["item_id"],
                "new_product_id": task_data["scenario_template"]["new_product_id"],
                "confirm": False,
            },
        },
    ]

    domain = get_config()
    import importlib

    from domains.customer_support.generate_tasks import _derive_replay_gt

    registry = importlib.import_module("domains.customer_support.task_registry")
    task_data = dict(task_data)
    task_data["task_id"] = f"38-{task_data['task_id']}"
    requirements, _replay_hash = _derive_replay_gt(registry, domain, env_data, task_data)

    assert requirements == []


def test_customer_support_generates_non_state_requirements_for_denial_tasks() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_exchange_outside_window()
    task_data["task_id"] = f"38-{task_data['task_id']}"

    public = _build_task_json(task_data)
    requirement_texts = {req["requirement"] for req in public["task_requirements"]}

    assert "Agent must deny the exchange request." in requirement_texts
    assert any("outside exchange window" in text.lower() for text in requirement_texts)


def test_customer_support_generates_separate_goodwill_requirements() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_challenge_fragile_goodwill_separate()
    task_data["task_id"] = f"52-{task_data['task_id']}"

    public = _build_task_json(task_data)
    requirement_texts = {req["requirement"] for req in public["task_requirements"]}

    assert any("process return for full refund" in text.lower() for text in requirement_texts)
    assert any("issue $10 fragile-item goodwill credit via separate process_refund call" in text for text in requirement_texts)
    assert any(req["kind"] == "must_not" and "combine the goodwill" in req["requirement"].lower() for req in public["task_requirements"])


def test_customer_support_product_lookup_audit_passes_for_price_match_task() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_cancel_price_match()
    env_data = build_task_environment(products, orders, items, warranties, task_data)

    issues = _audit_product_lookup(task_data, env_data)

    assert issues == []


def test_customer_support_product_lookup_audit_passes_for_exchange_oos_pivot() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_challenge_exchange_oos_pivot()
    env_data = build_task_environment(products, orders, items, warranties, task_data)

    assert task_data["scenario_template"]["item_id"] == "ITEM-10061"
    assert task_data["scenario_template"]["new_product_id"] == "PROD-3062"

    issues = _audit_product_lookup(task_data, env_data)

    assert issues == []


def test_customer_support_replay_infers_non_changed_mind_reasons_for_compound_returns() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_challenge_damaged_plus_wrong()
    env_data = build_task_environment(products, orders, items, warranties, task_data)

    replay_trace = build_replay_trace(task_data, env_data)
    return_steps = [step for step in replay_trace if step["name"] == "process_return" and step["arguments"]["confirm"]]

    assert len(return_steps) == 2
    reasons = {step["arguments"]["item_id"]: step["arguments"]["reason"] for step in return_steps}
    assert reasons == {
        "ITEM-10051": "damaged_in_transit",
        "ITEM-10055": "wrong_item",
    }


def test_customer_support_replay_consumes_labeled_multi_return_queue() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_challenge_two_electronics_gold()
    env_data = build_task_environment(products, orders, items, warranties, task_data)

    replay_trace = build_replay_trace(task_data, env_data)
    confirmed_returns = [step for step in replay_trace if step["name"] == "process_return" and step["arguments"]["confirm"]]

    assert len(confirmed_returns) == 2
    assert [step["arguments"]["item_id"] for step in confirmed_returns] == ["ITEM-10138", "ITEM-10139"]


def test_customer_support_task_summary_uses_replay_derived_write_state() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_challenge_gold_restocking_discount()
    env_data = build_task_environment(products, orders, items, warranties, task_data)
    replay_trace = build_replay_trace(task_data, env_data)

    domain = get_config()
    env = domain.environment_class(env_data.deep_copy(), now=task_data["scenario_template"]["now"])
    _executed, state_diff = execute_replay_trace(env, replay_trace)
    requirements = derive_state_requirements_from_state_diff(
        state_diff,
        replay_trace=replay_trace,
        post_snapshot=env.get_full_snapshot(),
    )

    task_data = dict(task_data)
    task_data["state_requirements"] = requirements
    public = _build_task_json(task_data)
    task_summary = public["task_summary"]

    assert task_summary.startswith("**Task:** A Gold customer is returning a laptop with a substantial restocking fee")
    assert " credit" in task_summary
    assert "Gold status entitles them to a separate fifty-percent restocking-discount credit" in task_summary
    assert "$1105" not in task_summary


def test_customer_support_price_match_task_summary_uses_refund_only_state() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_challenge_price_match_refund()
    env_data = build_task_environment(products, orders, items, warranties, task_data)
    replay_trace = build_replay_trace(task_data, env_data)

    domain = get_config()
    env = domain.environment_class(env_data.deep_copy(), now=task_data["scenario_template"]["now"])
    _executed, state_diff = execute_replay_trace(env, replay_trace)
    requirements = derive_state_requirements_from_state_diff(
        state_diff,
        replay_trace=replay_trace,
        post_snapshot=env.get_full_snapshot(),
    )

    task_data = dict(task_data)
    task_data["state_requirements"] = requirements
    public = _build_task_json(task_data)
    task_summary = public["task_summary"]

    assert task_summary.startswith("**Task:** The customer wants a $50 price-match refund")
    assert "issue the refund while leaving the order active" in task_summary
    assert "return flow" in task_summary
    assert "Item returned" not in task_summary


def test_format_attributes_for_prompt_omits_preferred_refund() -> None:
    from domains.customer_support.user_attributes import format_attributes_for_prompt

    rendered = format_attributes_for_prompt("cust_002")
    assert "Preferred Refund" not in rendered
    assert "Membership: Standard" in rendered
    assert "Prime Shipping: No" in rendered


def test_customer_support_seasonal_challenge_requirements_normalize_short_traps() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_challenge_seasonal_restock_shipping_triple()
    public = _build_task_json(task_data)
    requirement_texts = {req["requirement"] for req in public["task_requirements"]}

    assert "Agent must not deny the request for ignoring the seasonal extension." in requirement_texts
    assert "Agent must include the stated discount of $9." in requirement_texts
    assert "Agent must include the clawback of $8." in requirement_texts
    assert all("(no seasonal)" not in text for text in requirement_texts)


def test_customer_support_fragile_goodwill_requirements_do_not_emit_uppercase_not() -> None:
    reset_counters()
    products, orders, items, warranties, task_data = scenario_challenge_fragile_goodwill_separate()
    public = _build_task_json(task_data)
    requirement_texts = [req["requirement"] for req in public["task_requirements"]]

    assert all("Agent must NOT" not in text for text in requirement_texts)
    assert any("separate process_refund" in text for text in requirement_texts)
    assert any("goodwill credit into the item return refund" in text for text in requirement_texts)


def test_customer_support_shipping_late_compensation_serializes_strict_refund_requirements() -> None:
    reset_counters()
    _products, _orders, _items, _warranties, task_data = scenario_shipping_late_compensation()
    public = _build_task_json(task_data)

    req_ids = {req["id"] for req in public["task_requirements"]}
    assert "shipping_late_compensation_agent_must_process_30_refund_to_original_payment" in req_ids
    assert any(
        req["requirement"] == "Agent must actually process a $30 refund to the original payment method."
        and req["evidence"] == "conversation_or_tool_calls"
        for req in public["task_requirements"]
    )
    assert public["user_simulator"]["task_rules"][4].startswith("If the agent offers store credit or the wrong amount")


def test_customer_support_exchange_more_expensive_serializes_execution_requirement_and_new_item_state() -> None:
    reset_counters()
    _products, _orders, _items, _warranties, task_data = scenario_exchange_more_expensive()
    public = _build_task_json(task_data)

    assert any(
        req["requirement"] == "Agent must actually process the exchange rather than only explaining the policy."
        and req["evidence"] == "conversation_or_tool_calls"
        for req in public["task_requirements"]
    )
    assert any(
        req["requirement"] == "Agent must charge the $100 price difference."
        and req["evidence"] == "conversation_or_tool_calls"
        for req in public["task_requirements"]
    )
    assert any(
        req.get("booking_id") == "{{new_item_id}}"
        and req.get("field") == "goodwill_credit_method"
        and req.get("expected") is None
        for req in task_data["db_assertions"]
    )


def test_customer_support_challenge_gold_7day_all_parts_serializes_refund_execution_requirements() -> None:
    reset_counters()
    _products, _orders, _items, _warranties, task_data = scenario_challenge_gold_7day_all_parts()
    public = _build_task_json(task_data)

    assert any(
        req["requirement"] == "Agent must actually process a $59 refund to the original payment method."
        and req["evidence"] == "conversation_or_tool_calls"
        for req in public["task_requirements"]
    )
    assert any(
        req.get("booking_id") == "ITEM-10069"
        and req.get("field") == "refund_amount"
        and req.get("expected") == 59
        for req in task_data["db_assertions"]
    )
    assert public["user_simulator"]["task_rules"][3].startswith("Accept only after the correct payout is actually processed")


def test_customer_support_challenge_price_match_refund_serializes_without_bad_deny_requirement() -> None:
    reset_counters()
    _products, _orders, _items, _warranties, task_data = scenario_challenge_price_match_refund()
    public = _build_task_json(task_data)

    assert not any("denies the request" in req["requirement"] for req in public["task_requirements"])
    assert any(
        req["requirement"] == "Agent must compute the $50 difference and issue the refund."
        for req in public["task_requirements"]
    )


def test_customer_support_challenge_bulk_clawback_serializes_without_self_contradiction() -> None:
    reset_counters()
    _products, _orders, _items, _warranties, task_data = scenario_challenge_bulk_clawback()
    public = _build_task_json(task_data)
    requirement_texts = [req["requirement"] for req in public["task_requirements"]]

    assert "Agent must communicate the $10 bulk clawback to the customer." in requirement_texts
    assert not any("misses the $10 clawback" in text for text in requirement_texts)
