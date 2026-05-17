"""Customer-support exchange scenarios."""


from __future__ import annotations


from domains.customer_support import policies

from domains.customer_support.task_registry._builders import (
    ScenarioResult,
    build_ground_truth_trace,
    build_order,
    build_order_item,
    build_product,
    finalize_order,
)


def scenario_exchange_size_swap(
    task_id: str = "exchange_size_swap",
    customer_id: str = "cust_003",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Clothing wrong size. Same product variant → free exchange."""
    shirt_m = build_product("cotton_shirt", product_id="PROD-2250")
    shirt_l = build_product("cotton_shirt_large", product_id="PROD-2251")

    order = build_order(customer_id=customer_id, order_id="ORD-6034", delivery_date="2026-06-05T14:00:00")
    item = build_order_item(order.order_id, shirt_m, item_id="ITEM-9250")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "exchange_item",
        "description": "Exchange medium shirt for large. Same product variant — free exchange, no restocking.",
        "complexity": "medium",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
            "new_product_id": shirt_l.product_id,
        },
        "opening_message": "I need to exchange the shirt from order ORD-6034 for a larger size. The medium is too tight.",
        "user_simulator": {
            "prompt": (
                "You bought a medium cotton shirt in ORD-6034 but need a large. "
                "You want a size exchange.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Specify you want same shirt in Large.\n"
                "3. Accept the exchange terms.\n4. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6034", "current": "medium", "want": "large"},
            "_unknown_info": ["exchange process", "whether there's a fee"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "exchanged"},
            {"booking_id": item.item_id, "field": "replacement_item_id", "expected": "{{new_item_id}}"},
            {"booking_id": "{{new_item_id}}", "field": "item_status", "expected": "confirmed"},
        ],
        "_failure_traps": ["Agent charges for same-variant exchange", "Agent processes return instead of exchange"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="exchange_item",
        replay_steps=[
            "get_order",
            "get_product",
            "get_policies(exchange)",
            "process_exchange(preview)",
            "process_exchange(confirm)",
        ],
        policy_results={"customer_pays": 0, "store_credit_refund": 0},
        scenario=task_data["scenario_template"],
    )
    return [shirt_m, shirt_l], [order], [item], [], task_data


def scenario_exchange_more_expensive(
    task_id: str = "exchange_more_expensive",
    customer_id: str = "cust_001",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Exchange headphones ($249) for premium model ($349). Customer pays $100 difference."""
    headphones = build_product("wireless_headphones", product_id="PROD-2255")
    premium = build_product("wireless_headphones_premium", product_id="PROD-2256")

    order = build_order(customer_id=customer_id, order_id="ORD-6035", delivery_date="2026-06-05T14:00:00")
    item = build_order_item(order.order_id, headphones, item_id="ITEM-9255")
    finalize_order(order, [item])

    exchange = policies.calculate_exchange(
        original_item_price=headphones.price,
        new_product_price=premium.price,
        new_product_in_stock=True,
        category=headphones.category,
        delivery_date=order.delivery_date,
        now=now,
        return_window_days=headphones.return_window_days,
        same_product_variant=False,
        membership_tier="platinum",
        has_prime_shipping=True,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "exchange_item",
        "description": f"Exchange headphones ($249) for premium ($349). Customer pays ${exchange['customer_pays']} difference.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
            "new_product_id": premium.product_id,
        },
        "opening_message": "I'd like to exchange the headphones from order ORD-6035 for the premium model instead.",
        "user_simulator": {
            "prompt": (
                "You bought SoundMax headphones ($249) in ORD-6035. You want to upgrade to the "
                "Elite model ($349).\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Specify you want the Elite (premium) model.\n"
                "3. Ask about the price difference.\n4. Accept paying the difference.\n"
                "5. If the agent cannot actually submit the exchange, keep asking them to process it rather than only explain the policy.\n"
                "6. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6035", "current": "SoundMax ($249)", "want": "Elite ($349)"},
            "_unknown_info": ["price difference amount", "exchange process"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "exchanged"},
            {"booking_id": item.item_id, "field": "replacement_item_id", "expected": "{{new_item_id}}"},
            {"booking_id": "{{new_item_id}}", "field": "item_status", "expected": "confirmed"},
            {"booking_id": "{{new_item_id}}", "field": "goodwill_credit_method", "expected": None},
        ],
        "_failure_traps": ["Agent doesn't charge the price difference", "Agent processes return instead of exchange"],
        "task_requirements": [
            {
                "id": f"{task_id}_agent_must_process_the_exchange",
                "kind": "must",
                "requirement": "Agent must actually process the exchange rather than only explaining the policy.",
                "evidence": "conversation_or_tool_calls",
            },
            {
                "id": f"{task_id}_agent_must_charge_the_{exchange['customer_pays']}_price_difference",
                "kind": "must",
                "requirement": f"Agent must charge the ${exchange['customer_pays']} price difference.",
                "evidence": "conversation_or_tool_calls",
            },
            {
                "id": f"{task_id}_agent_must_not_process_return_instead_of_exchange",
                "kind": "must_not",
                "requirement": "Agent must not process a return instead of the exchange.",
                "evidence": "conversation_or_tool_calls",
            },
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="exchange_item",
        replay_steps=[
            "get_order",
            "get_product",
            "get_policies(exchange)",
            "process_exchange(preview)",
            "process_exchange(confirm)",
        ],
        policy_results=exchange,
        scenario=task_data["scenario_template"],
    )
    return [headphones, premium], [order], [item], [], task_data


def scenario_exchange_cheaper(
    task_id: str = "exchange_cheaper",
    customer_id: str = "cust_004",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Exchange premium headphones ($349) for budget ($149). $200 difference → store credit."""
    premium = build_product("wireless_headphones_premium", product_id="PROD-2260")
    budget = build_product("budget_headphones", product_id="PROD-2261")

    order = build_order(customer_id=customer_id, order_id="ORD-6036", delivery_date="2026-06-05T14:00:00")
    item = build_order_item(order.order_id, premium, item_id="ITEM-9260")
    finalize_order(order, [item])

    exchange = policies.calculate_exchange(
        original_item_price=premium.price,
        new_product_price=budget.price,
        new_product_in_stock=True,
        category=premium.category,
        delivery_date=order.delivery_date,
        now=now,
        return_window_days=premium.return_window_days,
        same_product_variant=False,
        membership_tier="silver",
        has_prime_shipping=False,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "exchange_item",
        "description": f"Exchange premium headphones ($349) for budget ($149). ${exchange['store_credit_refund']} difference to store credit (not cash).",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
            "new_product_id": budget.product_id,
        },
        "opening_message": "I want to exchange my premium headphones from order ORD-6036 for the basic model. The premium ones are overkill for me.",
        "user_simulator": {
            "prompt": (
                "You bought SoundMax Elite headphones ($349) in ORD-6036. You want to exchange for "
                "SoundMax Basic ($149). You expect the $200 difference back.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Specify the basic model.\n"
                "3. Ask about the price difference refund.\n"
                "4. If told it's store credit (not cash), ask why. Accept after explanation.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6036", "current": "Elite $349", "want": "Basic $149"},
            "_unknown_info": ["that difference goes to store credit not cash", "exchange process"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "exchanged"},
            {"booking_id": item.item_id, "field": "replacement_item_id", "expected": "{{new_item_id}}"},
            {"booking_id": "{{new_item_id}}", "field": "item_status", "expected": "confirmed"},
        ],
        "_failure_traps": [
            "Agent refunds difference to original payment (should be store credit)",
            "Agent charges restocking",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="exchange_item",
        replay_steps=[
            "get_order",
            "get_product",
            "get_policies(exchange)",
            "process_exchange(preview)",
            "process_exchange(confirm)",
        ],
        policy_results={"store_credit_refund": exchange.get("store_credit_refund", 0)},
        scenario=task_data["scenario_template"],
    )
    return [premium, budget], [order], [item], [], task_data


def scenario_exchange_out_of_stock(
    task_id: str = "exchange_out_of_stock",
    customer_id: str = "cust_002",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Exchange target is out of stock. Offer store credit or waitlist."""
    shirt = build_product("cotton_shirt", product_id="PROD-2265")
    shoes = build_product("running_shoes", product_id="PROD-2266", in_stock=False)

    order = build_order(customer_id=customer_id, order_id="ORD-6037", delivery_date="2026-06-05T14:00:00")
    item = build_order_item(order.order_id, shirt, item_id="ITEM-9265")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "exchange_item",
        "description": "Exchange shirt for running shoes but shoes are out of stock. Agent must offer store credit or waitlist.",
        "complexity": "medium",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
            "new_product_id": shoes.product_id,
        },
        "opening_message": "I'd like to exchange the shirt from order ORD-6037 for a pair of running shoes instead.",
        "user_simulator": {
            "prompt": (
                "You bought a cotton shirt in ORD-6037. You want to exchange for running shoes.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Specify you want running shoes.\n"
                "3. If told out of stock, ask about alternatives.\n"
                "4. Accept store credit option.\n5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6037", "want": "running shoes"},
            "_unknown_info": ["that shoes are out of stock", "alternative options"],
        },
        "db_assertions": [
            # Exchange not completed — item stays delivered (OOS)
            {"booking_id": item.item_id, "field": "item_status", "expected": "delivered"},
        ],
        "_failure_traps": ["Agent completes exchange with OOS product", "Agent doesn't offer alternatives"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="exchange_item",
        replay_steps=["get_order", "get_product", "get_policies(exchange)", "process_exchange(preview)"],
        policy_results={"out_of_stock": True},
        scenario=task_data["scenario_template"],
    )
    return [shirt, shoes], [order], [item], [], task_data


def scenario_exchange_no_price_protection(
    task_id: str = "exchange_no_price_protection",
    customer_id: str = "cust_002",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Product price dropped $50. Customer asks for price adjustment via exchange. Exchange policy says no price protection — agent must deny and suggest return+rebuy."""
    headphones = build_product("wireless_headphones", product_id="PROD-2270", current_price=199)

    order = build_order(customer_id=customer_id, order_id="ORD-6038", delivery_date="2026-06-05T14:00:00")
    item = build_order_item(order.order_id, headphones, item_id="ITEM-9270")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "exchange_item",
        "description": "Headphones bought at $249, now $199. Customer wants $50 back via exchange. Exchange policy explicitly states no price protection — agent must deny and suggest return+rebuy alternative.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
        },
        "opening_message": "I want to exchange my headphones from order ORD-6038. I see they're now $199 — I paid $249. Can I get the difference back with the exchange?",
        "user_simulator": {
            "prompt": (
                "You bought headphones at $249 in ORD-6038. They're now $199. "
                "You want to exchange and get $50 back.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Ask about price difference refund on exchange.\n"
                "3. If told no price protection on exchanges, push back once.\n"
                "4. Accept after explanation. If suggested to return+rebuy, say you'll consider it.\n"
                "5. You do NOT want to actually initiate a return right now.\n"
                "6. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6038", "paid": "$249", "current_price": "$199"},
            "_unknown_info": ["no price protection on exchanges", "return+rebuy alternative"],
        },
        "db_assertions": [
            # No state change — agent explains policy, no exchange processed
            {"booking_id": item.item_id, "field": "item_status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": None},
            {"booking_id": order.order_id, "field": "status", "expected": "delivered"},
        ],
        "_failure_traps": [
            "Agent processes an exchange when customer just wants price adjustment",
            "Agent issues a $50 refund without policy backing",
            "Agent doesn't check exchange policy for no_price_protection rule",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="edge_case",
        replay_steps=["get_order", "get_product", "get_policies(exchange)"],
        policy_results={
            "no_action": True,
            "agent_must": "explain no price protection on exchanges and suggest return+rebuy alternative",
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_exchange_outside_window(
    task_id: str = "exchange_outside_window",
    customer_id: str = "cust_005",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Exchange requested 35 days after delivery for electronics (15-day window). Denied."""
    usb_hub = build_product("usb_hub", product_id="PROD-2275")
    headphones = build_product("wireless_headphones", product_id="PROD-2276")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6039",
        delivery_date="2026-05-08T14:00:00",  # 35 days before now
    )
    item = build_order_item(order.order_id, usb_hub, item_id="ITEM-9275")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "exchange_item",
        "description": "Exchange USB hub for headphones, 35 days after delivery. Electronics 15-day window — exchange denied.",
        "complexity": "medium",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
            "new_product_id": headphones.product_id,
        },
        "opening_message": "I want to exchange the USB hub from order ORD-6039 for headphones.",
        "user_simulator": {
            "prompt": (
                "You bought a USB hub in ORD-6039 about 5 weeks ago. "
                "You want to exchange it for headphones.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. If told exchange window passed, ask when it expired.\n"
                "3. Accept the denial.\n4. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6039", "want": "headphones"},
            "_unknown_info": ["exchange window", "that 15-day limit applies to electronics"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "delivered"},
        ],
        "task_requirements": [
            {
                "id": f"{task_id}_agent_must_use_actual_delivery_date_for_exchange_window",
                "kind": "must",
                "requirement": "Agent must use the actual delivery date from the order record to determine the exchange window is expired.",
                "evidence": "conversation_or_tool_calls",
            },
            {
                "id": f"{task_id}_agent_must_check_exchange_window",
                "kind": "must",
                "requirement": "Agent must check the applicable electronics exchange window.",
                "evidence": "conversation_or_tool_calls",
            },
            {
                "id": f"{task_id}_agent_must_explain_outside_exchange_window",
                "kind": "must",
                "requirement": "Agent must explain that the exchange is denied because the item is outside exchange window.",
                "evidence": "conversation_or_tool_calls",
            },
            {
                "id": f"{task_id}_agent_must_deny_exchange_request",
                "kind": "must",
                "requirement": "Agent must deny the exchange request.",
                "evidence": "conversation_or_tool_calls",
            },
            {
                "id": f"{task_id}_agent_must_not_say_window_open",
                "kind": "must_not",
                "requirement": "Agent must not state or imply that the exchange window is still open.",
                "evidence": "conversation_or_tool_calls",
            },
            {
                "id": f"{task_id}_agent_must_not_request_replacement_product",
                "kind": "must_not",
                "requirement": "Agent must not ask the customer to pick a replacement product or provide product IDs after the item is outside the exchange window.",
                "evidence": "conversation_or_tool_calls",
            },
            {
                "id": f"{task_id}_agent_must_not_attempt_exchange_or_return",
                "kind": "must_not",
                "requirement": "Agent must not attempt to process an exchange or return for this change-of-mind request.",
                "evidence": "tool_calls",
            },
        ],
        "_failure_traps": ["Agent processes exchange outside window", "Agent doesn't check return window"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="exchange_item",
        replay_steps=["get_order", "get_policies(exchange)", "process_exchange(preview)"],
        policy_results={"denied": True, "reason": "outside exchange window"},
        scenario=task_data["scenario_template"],
    )
    return [usb_hub, headphones], [order], [item], [], task_data


SCENARIOS = [
    scenario_exchange_size_swap,
    scenario_exchange_more_expensive,
    scenario_exchange_cheaper,
    scenario_exchange_out_of_stock,
    scenario_exchange_no_price_protection,
    scenario_exchange_outside_window,
]
