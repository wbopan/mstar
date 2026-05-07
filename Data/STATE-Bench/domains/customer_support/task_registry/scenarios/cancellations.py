"""Customer-support order cancellation scenarios."""


from __future__ import annotations


from domains.customer_support.task_registry._builders import (
    ScenarioResult,
    build_ground_truth_trace,
    build_order,
    build_order_item,
    build_product,
    finalize_order,
)


def scenario_cancel_before_shipment(
    task_id: str = "cancel_before_shipment",
    customer_id: str = "cust_002",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Cancel pre-shipment order. Free cancellation, full refund."""
    tablet = build_product("tablet", product_id="PROD-2100")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6015",
        order_date="2026-06-11T10:00:00",
        status="processing",
        shipping_status="pending",
        delivery_date=None,
        delivery_promised_date="2026-06-16T18:00:00",
    )
    item = build_order_item(order.order_id, tablet, item_id="ITEM-9100", item_status="confirmed")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "cancel_order",
        "description": "Cancel an order still in processing. Free cancellation — no fees.",
        "complexity": "medium",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "I'd like to cancel my order ORD-6015. I found a better deal elsewhere.",
        "user_simulator": {
            "prompt": (
                "You placed order ORD-6015 for a tablet. It hasn't shipped yet. "
                "You want to cancel.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Confirm full cancellation.\n"
                "3. Accept the cancellation terms.\n4. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6015", "item": "tablet"},
            "_unknown_info": ["cancellation fee", "refund timeline"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "status", "expected": "cancelled"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "cancelled"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": tablet.price},
        ],
        "_failure_traps": ["Agent charges a fee for pre-shipment cancel", "Agent doesn't preview first"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="cancel_order",
        replay_steps=["get_order", "get_policies(cancellation)", "cancel_order(preview)", "cancel_order(confirm)"],
        policy_results={"cancellation_fee": 0, "refund_amount": tablet.price},
        scenario=task_data["scenario_template"],
    )
    return [tablet], [order], [item], [], task_data


def scenario_cancel_after_shipment(
    task_id: str = "cancel_after_shipment",
    customer_id: str = "cust_004",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Cancel shipped order with 2 items. $10 intercept fee per item = $20."""
    headphones = build_product("wireless_headphones", product_id="PROD-2020")
    usb_hub = build_product("usb_hub", product_id="PROD-2021")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6003",
        order_date="2026-06-10T10:00:00",
        status="shipped",
        shipping_status="in_transit",
        delivery_date=None,
        delivery_promised_date="2026-06-14T18:00:00",
    )
    item_hp = build_order_item(order.order_id, headphones, item_id="ITEM-9020", item_status="shipped")
    item_hub = build_order_item(order.order_id, usb_hub, item_id="ITEM-9021", item_status="shipped")
    items = [item_hp, item_hub]
    finalize_order(order, items)

    task_data = {
        "task_id": task_id,
        "task_type": "cancel_order",
        "description": "Cancel a shipped order with 2 items. In-transit cancellation incurs $10 intercept fee per item ($20 total).",
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "I need to cancel my order ORD-6003. I ordered headphones and a USB hub but I don't need them anymore.",
        "user_simulator": {
            "prompt": (
                "You placed order ORD-6003 with wireless headphones and a USB hub. "
                "The order has shipped but you want to cancel.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. You want to cancel BOTH items.\n"
                "3. When told about the intercept fee, ask how much.\n"
                "4. Accept the fee after explanation.\n5. Confirm the cancellation.\n"
                "6. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6003", "items": "headphones and USB hub"},
            "_unknown_info": ["intercept fee", "refund amount"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "status", "expected": "cancelled"},
            {"booking_id": "ITEM-9020", "field": "item_status", "expected": "cancelled"},
            {"booking_id": "ITEM-9021", "field": "item_status", "expected": "cancelled"},
            {"booking_id": "ITEM-9020", "field": "refund_amount", "expected": headphones.price - 10},
            {"booking_id": "ITEM-9021", "field": "refund_amount", "expected": usb_hub.price - 10},
        ],
        "_failure_traps": ["Agent cancels without checking policy", "Agent doesn't mention intercept fee"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="cancel_order",
        replay_steps=["get_order", "get_policies(cancellation)", "cancel_order(preview)", "cancel_order(confirm)"],
        policy_results={"cancellation_fee": 20, "refund_amount": headphones.price + usb_hub.price - 20},
        scenario=task_data["scenario_template"],
    )
    return [headphones, usb_hub], [order], items, [], task_data


def scenario_cancel_partial(
    task_id: str = "cancel_partial",
    customer_id: str = "cust_003",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Cancel 1 of 3 items from pre-shipment order."""
    shirt = build_product("cotton_shirt", product_id="PROD-2105")
    novel = build_product("novel", product_id="PROD-2106")
    case = build_product("phone_case", product_id="PROD-2107")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6016",
        order_date="2026-06-11T10:00:00",
        status="processing",
        shipping_status="pending",
        delivery_date=None,
        delivery_promised_date="2026-06-16T18:00:00",
    )
    items = [
        build_order_item(order.order_id, shirt, item_id="ITEM-9105", item_status="confirmed"),
        build_order_item(order.order_id, novel, item_id="ITEM-9106", item_status="confirmed"),
        build_order_item(order.order_id, case, item_id="ITEM-9107", item_status="confirmed"),
    ]
    finalize_order(order, items)

    task_data = {
        "task_id": task_id,
        "task_type": "cancel_order",
        "description": "Cancel 1 of 3 items (the shirt) from a pre-shipment order. Other items remain confirmed.",
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "I'd like to cancel just the shirt from my order ORD-6016. I still want the book and the phone case.",
        "user_simulator": {
            "prompt": (
                "You placed order ORD-6016 with a shirt, book, and phone case. "
                "You want to cancel ONLY the shirt. Keep the other two.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Be specific: cancel the shirt only.\n"
                "3. Confirm if the agent asks about partial cancellation.\n"
                "4. Accept the terms.\n5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6016", "cancel_item": "shirt", "keep": "book, phone case"},
            "_unknown_info": ["partial cancel process", "refund for shirt"],
        },
        "db_assertions": [
            {"booking_id": "ITEM-9105", "field": "item_status", "expected": "cancelled"},
            {"booking_id": "ITEM-9106", "field": "item_status", "expected": "confirmed"},
            {"booking_id": "ITEM-9107", "field": "item_status", "expected": "confirmed"},
            # Order stays processing (partial cancel, not all items cancelled)
            {"booking_id": "ORD-6016", "field": "status", "expected": "processing"},
        ],
        "_failure_traps": ["Agent cancels entire order instead of just the shirt", "Agent cancels wrong item"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="cancel_order",
        replay_steps=[
            "get_order",
            "get_policies(cancellation)",
            "cancel_order(item_ids, preview)",
            "cancel_order(confirm)",
        ],
        policy_results={"cancellation_fee": 0, "refund_amount": shirt.price},
        scenario=task_data["scenario_template"],
    )
    return [shirt, novel, case], [order], items, [], task_data


def scenario_cancel_split_payment(
    task_id: str = "cancel_split_payment",
    customer_id: str = "cust_003",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Cancel order paid with credit card + gift card. Proportional refund."""
    phone_case = build_product("phone_case", product_id="PROD-2110")  # $35
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6017",
        order_date="2026-06-11T10:00:00",
        status="processing",
        shipping_status="pending",
        delivery_date=None,
        delivery_promised_date="2026-06-16T18:00:00",
        payment_method="split",
        payment_details={"credit_card": 30, "gift_card": 13},
        shipping_cost=0,
    )
    item = build_order_item(order.order_id, phone_case, item_id="ITEM-9110", item_status="confirmed")
    finalize_order(order, [item])
    # Fix payment_details to match total_paid exactly
    order.payment_details = {"credit_card": 30, "gift_card": 5}  # = 35 = total_paid (35 - 0 + 0)

    task_data = {
        "task_id": task_id,
        "task_type": "cancel_order",
        "description": "Cancel order paid with split payment (credit card $30 + gift card $5). Refund must go to correct payment methods proportionally.",
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "I need to cancel order ORD-6017. I paid with both my credit card and a gift card.",
        "user_simulator": {
            "prompt": (
                "You placed order ORD-6017 for a phone case, paid with credit card ($30) + gift card ($5). "
                "You want to cancel.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Mention you paid with split payment if asked.\n"
                "3. Ask how the refund will be split.\n4. Accept the terms.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6017", "payment": "credit card $30 + gift card $5"},
            "_unknown_info": ["refund split details", "cancellation process"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "status", "expected": "cancelled"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "cancelled"},
        ],
        "_failure_traps": ["Agent refunds everything to one payment method", "Agent doesn't handle split refund"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="cancel_order",
        replay_steps=["get_order", "get_policies(cancellation)", "cancel_order(preview)", "cancel_order(confirm)"],
        policy_results={"cancellation_fee": 0, "split_refund": True},
        scenario=task_data["scenario_template"],
    )
    return [phone_case], [order], [item], [], task_data


def scenario_cancel_backordered(
    task_id: str = "cancel_backordered",
    customer_id: str = "cust_005",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """2-item order, 1 item backordered. Cancel the backordered item only."""
    shirt = build_product("cotton_shirt", product_id="PROD-2115")
    blender = build_product("blender", product_id="PROD-2116")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6018",
        order_date="2026-05-20T10:00:00",
        status="processing",
        shipping_status="in_transit",  # partially shipped — shirt is in transit
        delivery_date=None,
        delivery_promised_date="2026-06-15T18:00:00",
    )
    item_shirt = build_order_item(order.order_id, shirt, item_id="ITEM-9115", item_status="shipped")
    item_blender = build_order_item(order.order_id, blender, item_id="ITEM-9116", item_status="confirmed")
    items = [item_shirt, item_blender]
    finalize_order(order, items)

    task_data = {
        "task_id": task_id,
        "task_type": "cancel_order",
        "description": "2-item order: shirt already shipped, blender backordered 3+ weeks. Cancel only the backordered blender.",
        "complexity": "medium",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "My order ORD-6018 has a blender that's been backordered for weeks. I want to cancel just the blender.",
        "user_simulator": {
            "prompt": (
                "You placed order ORD-6018 with a shirt and a blender. The shirt already shipped "
                "but the blender has been backordered for 3 weeks. You want to cancel the blender only.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Cancel ONLY the blender.\n"
                "3. Keep the shirt.\n4. Accept the cancellation terms.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6018", "cancel_item": "blender", "keep": "shirt"},
            "_unknown_info": ["cancellation process for backordered", "refund amount"],
        },
        "db_assertions": [
            {"booking_id": "ITEM-9116", "field": "item_status", "expected": "cancelled"},
            {"booking_id": "ITEM-9115", "field": "item_status", "expected": "shipped"},
            # Order stays processing (only backordered item cancelled)
            {"booking_id": "ORD-6018", "field": "status", "expected": "processing"},
        ],
        "_failure_traps": ["Agent cancels entire order", "Agent cancels the shipped shirt instead"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="cancel_order",
        replay_steps=[
            "get_order",
            "get_policies(cancellation)",
            "cancel_order(item_ids, preview)",
            "cancel_order(confirm)",
        ],
        policy_results={"cancellation_fee": 10},
        scenario=task_data["scenario_template"],
    )
    return [shirt, blender], [order], items, [], task_data


def scenario_cancel_delivered(
    task_id: str = "cancel_delivered",
    customer_id: str = "cust_002",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Delivered order — cannot cancel. Agent must redirect to return process."""
    novel = build_product("novel", product_id="PROD-2120")
    order = build_order(customer_id=customer_id, order_id="ORD-6019", delivery_date="2026-06-08T14:00:00")
    item = build_order_item(order.order_id, novel, item_id="ITEM-9120")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "cancel_order",
        "description": "Order already delivered. Cancellation denied — agent must redirect customer to return process.",
        "complexity": "medium",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "I want to cancel order ORD-6019.",
        "user_simulator": {
            "prompt": (
                "You want to cancel order ORD-6019 (a book). You don't realize it's already delivered.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. If told it can't be cancelled, ask what to do.\n"
                "3. Accept the redirect to the return process, but do not ask the agent to start the return now.\n"
                "4. End once the agent clearly explains cancellation is denied and return is the next step.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6019", "item": "book"},
            "_unknown_info": ["that order is delivered", "that return is the correct process"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": None},
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="edge_case",
        replay_steps=["get_order", "get_policies(cancellation)"],
        policy_results={"no_action": True, "agent_must": "deny cancellation and suggest return process"},
        scenario=task_data["scenario_template"],
    )
    return [novel], [order], [item], [], task_data


def scenario_cancel_price_match(
    task_id: str = "cancel_price_match",
    customer_id: str = "cust_002",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Item price dropped within 7 days of delivery. Agent checks refund policy, finds price-match rule, refunds the difference."""
    headphones = build_product("wireless_headphones", product_id="PROD-2125", current_price=199)
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6020",
        order_date="2026-06-08T10:00:00",
        delivery_date="2026-06-10T14:00:00",
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-9125")
    finalize_order(order, [item])

    price_diff = headphones.price - headphones.current_price  # 249 - 199 = 50

    task_data = {
        "task_id": task_id,
        "task_type": "price_match_refund",
        "description": "Headphones price dropped $50 within 7 days of delivery. Agent must check refund policy (price_match rule), verify the drop via get_product, and refund the difference without cancelling the order.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "I bought headphones in order ORD-6020 for $249 but now they're $199. I want the price difference back.",
        "user_simulator": {
            "prompt": (
                "You bought headphones in ORD-6020 for $249. Now they're $199 — a $50 drop. "
                "You want a price match (refund the $50 difference).\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. You want the PRICE DIFFERENCE, not to return.\n"
                "3. If agent suggests cancel+reorder, push back — you just want the difference.\n"
                "4. Accept the refund of $50.\n5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6020", "paid": "$249", "current_price": "$199"},
            "_unknown_info": ["price match policy", "refund process"],
        },
        "db_assertions": [
            # Order stays delivered, item stays delivered
            {"booking_id": order.order_id, "field": "status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "delivered"},
            # Refund of price difference processed
            {"booking_id": item.item_id, "field": "refund_amount", "expected": price_diff},
        ],
        "_failure_traps": [
            "Agent cancels the order instead of price matching",
            "Agent doesn't check refund policy for price_match rule",
            "Agent doesn't verify current product price",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="price_match_refund",
        replay_steps=[
            "get_order",
            "get_product",
            "get_policies(refund)",
            "process_refund(preview)",
            "process_refund(confirm)",
        ],
        policy_results={"refund_amount": price_diff},
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_cancel_already_cancelled(
    task_id: str = "cancel_already_cancelled",
    customer_id: str = "cust_002",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Order already cancelled. Agent must inform gracefully."""
    phone_case = build_product("phone_case", product_id="PROD-2130")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6021",
        order_date="2026-06-05T10:00:00",
        status="cancelled",
        shipping_status="pending",
        delivery_date=None,
    )
    item = build_order_item(order.order_id, phone_case, item_id="ITEM-9130", item_status="cancelled")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "cancel_order",
        "description": "Order already cancelled. Agent must inform customer gracefully — no action needed.",
        "complexity": "medium",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "Can you cancel my order ORD-6021 please?",
        "user_simulator": {
            "prompt": (
                "You want to cancel order ORD-6021. You don't realize it's already cancelled.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. If told already cancelled, say 'Oh, I didn't realize.'\n"
                "3. Ask about the refund status.\n4. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6021"},
            "_unknown_info": ["that order is already cancelled"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "status", "expected": "cancelled"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "cancelled"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": None},
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="edge_case",
        replay_steps=["get_order"],
        policy_results={"no_action": True, "agent_must": "inform customer the order is already cancelled"},
        scenario=task_data["scenario_template"],
    )
    return [phone_case], [order], [item], [], task_data


SCENARIOS = [
    scenario_cancel_before_shipment,
    scenario_cancel_after_shipment,
    scenario_cancel_partial,
    scenario_cancel_split_payment,
    scenario_cancel_backordered,
    scenario_cancel_delivered,
    scenario_cancel_price_match,
    scenario_cancel_already_cancelled,
]
