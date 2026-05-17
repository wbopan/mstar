"""Customer-support challenge scenarios focused on policy clawbacks and seasonal rules."""


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

from domains.customer_support.user_attributes import CUSTOMER_ATTRIBUTES


def scenario_challenge_low_value_lost_immediate(
    task_id: str = "challenge_low_value_lost_immediate",
    customer_id: str = "cust_002",
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """$89 blender lost. Policy: <$500 = immediate reship/refund. No investigation needed."""
    blender = build_product("blender", product_id="PROD-3052")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7052",
        order_date="2026-06-20T10:00:00",
        delivery_date=None,
        status="shipped",
        shipping_status="lost",
        shipping_cost=8,
    )
    item = build_order_item(order.order_id, blender, item_id="ITEM-10052", item_status="shipped")
    finalize_order(order, [item])

    claim = policies.check_shipping_claim(
        shipping_status=order.shipping_status,
        order_total=order.total_paid,
        delivery_date=order.delivery_date,
        delivery_promised_date=order.delivery_promised_date,
        now=now,
        signature_required=order.signature_required,
        signature_on_file=order.signature_on_file,
        is_fragile=blender.is_fragile,
        tracking_number=order.tracking_number,
    )
    assert claim["resolution"] == "reship_or_refund", f"Setup error: {claim}"

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": (
            "Lost $89 blender. Policy: < $500 = immediate reship or refund. "
            "Agent must NOT start an investigation — offer immediate resolution."
        ),
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "My blender from ORD-7052 is lost in transit. I want you to investigate where it went and find it.",
        "user_simulator": {
            "prompt": (
                "Your blender (ORD-7052, $89) is lost in transit. You want an investigation.\n\n"
                "RULES:\n1. Give order ID.\n2. Ask for investigation: 'Can you track it down?'\n"
                "3. If agent offers immediate refund/reship, say: 'Don't you need to investigate first?'\n"
                "4. Accept whichever resolution the agent offers (refund or reship).\n"
                "5. If agent says investigation required, go along.\n6. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7052", "item": "blender ($89)", "status": "lost"},
            "_unknown_info": ["resolution options", "investigation policy"],
        },
        "db_assertions": [],
        "_failure_traps": [
            "Agent starts investigation for low-value package (< $500 = immediate resolution)",
            "Agent says it requires 3-5 days (that's only for >= $500)",
            "Agent denies resolution entirely",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="shipping_claim",
        replay_steps=["get_order", "get_customer", "get_policies(shipping)"],
        policy_results={
            "resolution": "reship_or_refund",
            "reason": claim["reason"],
            "phases": [
                "Package lost in transit (<$500) — immediate reship or refund, NO investigation required.",
                "Agent must offer reship or full refund (customer's choice).",
                "Agent must NOT start an investigation or impose a waiting period.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [blender], [order], [item], [], task_data


def scenario_challenge_standard_1day_pushback(
    task_id: str = "challenge_standard_1day_pushback",
    customer_id: str = "cust_002",
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """Standard, 1 day late, 2 issues. Just $5. Customer demands much more."""
    novel = build_product("novel", product_id="PROD-3054")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7054",
        order_date="2026-06-28T10:00:00",
        delivery_date="2026-07-07T14:00:00",
        delivery_promised_date="2026-07-06T10:00:00",
        shipping_cost=5,
    )
    item = build_order_item(order.order_id, novel, item_id="ITEM-10054")
    finalize_order(order, [item])

    comp = policies.calculate_compensation(
        delivery_date=order.delivery_date,
        delivery_promised_date=order.delivery_promised_date,
        now=now,
        order_total=order.subtotal,
        shipping_cost=order.shipping_cost,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        previous_issues_count=2,
    )
    assert comp["total_compensation"] == 5

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": "Standard, 1 day late, 2 issues. $5 compensation. Customer demands $50+. Agent must hold firm.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "previous_issues_count": 2,
        },
        "opening_message": "Order ORD-7054 was late AGAIN. This is the third time now. I expect at least $50 in compensation for all the trouble you've caused me.",
        "user_simulator": {
            "prompt": (
                "Your novel (ORD-7054, $24) arrived 1 day late. You've had 2 previous late deliveries. "
                "You're demanding $50+ compensation.\n\n"
                "RULES:\n1. Give order ID.\n2. Say this is your 3rd late delivery (2 previous).\n"
                "3. Demand $50: 'I've been patient but this is ridiculous. $50 minimum.'\n"
                "4. If agent offers $5, say 'That's insulting. Can you do better?'\n"
                "5. If agent holds at $5, push once more: 'What about all my previous issues?'\n"
                "6. After the agent has clearly held at  twice, stop arguing, accept the , and ask them to apply it now.\n"
                "7. If agent offers more than $5, accept immediately.\n8. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7054", "days_late": "1", "previous_issues": "2"},
            "_unknown_info": ["compensation policy", "actual amount"],
        },
        "db_assertions": [],
        "_failure_traps": [
            "Agent offers more than $5 to appease the customer",
            "Agent adds goodwill for 2 issues (threshold is 3+)",
            "Agent caves to 'third time' framing and adds extra compensation",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="shipping_claim",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(compensation)",
            "get_policies(refund)",
            "process_refund(preview)",
            "process_refund(confirm)",
        ],
        policy_results={
            "resolution": "compensation",
            "compensation_amount": 5,
            "adjusted_credit": 5,
            "goodwill_credit": 0,
            "shipping_refund": 0,
            "days_late": 1,
            "phases": [
                "Late delivery compensation: $5 (1 day late, standard 1.0x multiplier).",
                "No goodwill bonus (only 2 previous issues, threshold is 3+).",
                "Agent must hold firm at $5 despite customer demanding $50+.",
                "Process refund of exactly $5 via process_refund.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [novel], [order], [item], [], task_data


def scenario_challenge_exchange_oos_pivot(
    task_id: str = "challenge_exchange_oos_pivot",
    customer_id: str = "cust_003",
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """Exchange requested but item out of stock. Pivot to return."""
    headphones = build_product("wireless_headphones", product_id="PROD-3061")
    premium = build_product("wireless_headphones_premium", product_id="PROD-3062", in_stock=False)

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7061",
        order_date="2026-06-28T10:00:00",
        delivery_date="2026-07-03T14:00:00",
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-10061")
    finalize_order(order, [item])

    exchange = policies.calculate_exchange(
        original_item_price=headphones.price,
        new_product_price=premium.price,
        new_product_in_stock=premium.in_stock,
        category=headphones.category,
        delivery_date=order.delivery_date,
        now=now,
        return_window_days=headphones.return_window_days,
        same_product_variant=False,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        has_prime_shipping=CUSTOMER_ATTRIBUTES[customer_id]["has_prime_shipping"],
    )
    assert exchange.get("out_of_stock")

    refund = policies.calculate_refund(
        item_price=headphones.price,
        return_reason="changed_mind",
        category=headphones.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=headphones.current_price,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": (
            "Exchange requested but replacement out of stock. Agent must explain options "
            f"and process return (${refund['refund_amount']}) when customer chooses refund."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
            "new_product_id": premium.product_id,
        },
        "opening_message": "I'd like to exchange my headphones from ORD-7061 for the SoundMax Elite premium model instead.",
        "user_simulator": {
            "prompt": (
                "Headphones (ORD-7061, $249). You want SoundMax Elite ($349) instead.\n\n"
                "RULES:\n1. Give order ID.\n2. Request exchange for the Premium model.\n"
                "3. If told out of stock, ask: 'When will it be back?'\n"
                "4. If agent can't give a date, say: 'Fine, just give me a refund then.'\n"
                "5. Confirm the return.\n6. Keep to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-7061",
                "current": "SoundMax Wireless ($249)",
                "desired": "SoundMax Elite ($349)",
            },
            "_unknown_info": ["stock availability", "refund amount with restocking"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
        ],
        "_failure_traps": [
            "Agent tries to force the exchange despite out-of-stock",
            "Agent doesn't offer return as alternative to out-of-stock exchange",
            "Agent gets stuck after out-of-stock and doesn't proceed",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_product",
            "get_policies(exchange)",
            "process_exchange(preview)",
            "get_policies(return)",
            "get_policies(refund)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results={
            "phases": [
                "Exchange denied: SoundMax Elite out of stock.",
                f"Customer pivots to return: ${refund['refund_amount']} (restocking ${refund['restocking_fee']}).",
            ]
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones, premium], [order], [item], [], task_data


def scenario_challenge_bulk_clawback(
    task_id: str = "challenge_bulk_clawback",
    customer_id: str = "cust_004",
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """Return 2 of 4 items from bulk-discounted order. Clawback $10 from refund."""
    headphones = build_product("wireless_headphones", product_id="PROD-3081")
    shirt = build_product("cotton_shirt", product_id="PROD-3082")
    novel = build_product("novel", product_id="PROD-3083")
    case = build_product("phone_case", product_id="PROD-3084")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7081",
        order_date="2026-06-25T10:00:00",
        delivery_date="2026-06-30T14:00:00",
        discount_code="BULK20",
        discount_amount=20,
    )
    item_h = build_order_item(order.order_id, headphones, item_id="ITEM-10081")
    item_s = build_order_item(order.order_id, shirt, item_id="ITEM-10082")
    item_n = build_order_item(order.order_id, novel, item_id="ITEM-10083")
    item_c = build_order_item(order.order_id, case, item_id="ITEM-10084")
    items = [item_h, item_s, item_n, item_c]
    finalize_order(order, items)

    clawback = policies.calculate_bulk_clawback(
        original_item_count=4,
        items_being_returned=2,
        remaining_item_count=2,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
    )
    assert clawback["applies"]
    assert clawback["clawback_amount"] == 10

    refund_h = policies.calculate_refund(
        item_price=headphones.price,
        return_reason="changed_mind",
        category=headphones.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=headphones.current_price,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": (
            f"Return headphones + shirt from 4-item bulk-discounted order. "
            f"Drops to 2 remaining items (below bulk threshold of 3). "
            f"Clawback: ${clawback['clawback_amount']} deducted from refund. "
            "Agent must check bulk_discount policy and communicate the clawback."
        ),
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "I want to return the headphones and the shirt from order ORD-7081. I'll keep the book and phone case.",
        "user_simulator": {
            "prompt": (
                "Order ORD-7081 (4 items, BULK20 discount). Return headphones + shirt, keep novel + case.\n\n"
                "RULES:\n1. Give order ID.\n2. Specify headphones and shirt for return.\n"
                "3. If agent mentions a clawback or additional deduction, ask: 'What clawback? Why?'\n"
                "4. If agent explains the bulk discount policy, accept.\n"
                "5. Confirm returns.\n6. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7081", "return": "headphones + shirt", "keep": "novel + phone case"},
            "_unknown_info": ["bulk clawback policy", "clawback amount"],
        },
        "db_assertions": [
            {"booking_id": "ITEM-10081", "field": "item_status", "expected": "returned"},
            {"booking_id": "ITEM-10082", "field": "item_status", "expected": "returned"},
            {"booking_id": "ITEM-10083", "field": "item_status", "expected": "delivered"},
            {"booking_id": "ITEM-10084", "field": "item_status", "expected": "delivered"},
        ],
        "_failure_traps": [
            "Agent doesn't check bulk_discount policy and misses the $10 clawback",
            "Agent doesn't communicate the clawback to the customer",
            "Agent deducts wrong clawback amount",
        ],
        "task_requirements": [
            {
                "id": f"{task_id}_agent_must_communicate_10_bulk_clawback",
                "kind": "must",
                "requirement": "Agent must communicate the $10 bulk clawback to the customer.",
                "evidence": "conversation",
            },
            {
                "id": f"{task_id}_agent_must_apply_10_bulk_clawback",
                "kind": "must",
                "requirement": "Agent must apply the $10 bulk clawback in the return resolution.",
                "evidence": "conversation_or_tool_calls",
            },
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(refund)",
            "get_policies(bulk_discount)",
            "process_return(preview, headphones)",
            "process_return(confirm, headphones)",
            "process_return(preview, shirt)",
            "process_return(confirm, shirt)",
        ],
        policy_results={
            "phases": [
                f"Return headphones: ${refund_h['refund_amount']} (with promo adj + restocking).",
                "Return shirt: refund computed by tool.",
                f"Bulk clawback: ${clawback['clawback_amount']} ({clawback['reason']}).",
            ]
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones, shirt, novel, case], [order], items, [], task_data


def scenario_challenge_seasonal_valid(
    task_id: str = "challenge_seasonal_valid",
    customer_id: str = "cust_002",  # Standard, no extensions
    now: str = "2026-01-15T10:00:00",  # Mid-January
) -> ScenarioResult:
    """November order, now Jan 15. Normal window expired. Seasonal (Jan 31) still valid."""
    shirt = build_product("cotton_shirt", product_id="PROD-3086")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7083",
        order_date="2025-11-20T10:00:00",
        delivery_date="2025-11-28T14:00:00",
    )
    item = build_order_item(order.order_id, shirt, item_id="ITEM-10086")
    finalize_order(order, [item])

    # Normal: 30d from Nov 28 = Dec 28. Expired by Jan 15.
    # Store credit window: 30+15 = 45d = Jan 12. Also expired.
    # Seasonal: Jan 31, 2026. STILL VALID on Jan 15.
    _elig = policies.check_return_eligibility(
        category=shirt.category,
        delivery_date=order.delivery_date,
        now=now,
        item_status=item.item_status,
        return_reason="changed_mind",
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        has_prime_shipping=CUSTOMER_ATTRIBUTES[customer_id]["has_prime_shipping"],
    )
    # Normal eligibility will say ineligible (past store credit window too)

    seasonal = policies.check_seasonal_return_extension(
        order_date=order.order_date,
        now=now,
        base_window_end="2025-12-28",
    )
    assert seasonal["applies"], f"Setup error: {seasonal}"

    refund = policies.calculate_refund(
        item_price=shirt.price,
        return_reason="changed_mind",
        category=shirt.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=shirt.current_price,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            "November order, Jan 15 now. Normal + store credit windows expired. "
            "But seasonal extension (Jan 31) is valid. Agent must process the return."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "I'd like to return a shirt from order ORD-7083. I bought it as a holiday gift for myself in November but it doesn't fit.",
        "user_simulator": {
            "prompt": (
                "Shirt (ORD-7083, $59) bought November 2025. Doesn't fit. Now Jan 15.\n\n"
                "RULES:\n1. Give order ID.\n2. Mention it was a holiday/November purchase.\n"
                "3. If agent says return window passed, ask: 'What about the holiday return policy?'\n"
                "4. If still denied, say: 'I thought holiday purchases get until January 31?'\n"
                "5. If agent processes the return, confirm.\n6. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7083", "item": "cotton shirt ($59)", "purchase": "November 2025"},
            "_unknown_info": ["seasonal policy", "return eligibility"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
        ],
        "_failure_traps": [
            "Agent denies return because normal window expired (ignores seasonal extension)",
            "Agent doesn't check seasonal policy",
            "Agent offers store credit only when full return is valid under seasonal",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(seasonal)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results={**refund, "seasonal_extension": True},
        scenario=task_data["scenario_template"],
    )
    return [shirt], [order], [item], [], task_data


def scenario_challenge_defective_plus_clawback(
    task_id: str = "challenge_defective_plus_clawback",
    customer_id: str = "cust_004",
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """Defective return from bulk order triggers clawback. Two issues to handle."""
    tablet = build_product("tablet", product_id="PROD-3094")
    shirt = build_product("cotton_shirt", product_id="PROD-3095")
    case = build_product("phone_case", product_id="PROD-3096")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7092",
        order_date="2026-06-25T10:00:00",
        delivery_date="2026-06-30T14:00:00",
        discount_code="BUNDLE25",
        discount_amount=25,
    )
    item_t = build_order_item(order.order_id, tablet, item_id="ITEM-10094")
    item_s = build_order_item(order.order_id, shirt, item_id="ITEM-10095")
    item_c = build_order_item(order.order_id, case, item_id="ITEM-10096")
    items = [item_t, item_s, item_c]
    finalize_order(order, items)

    refund = policies.calculate_refund(
        item_price=tablet.price,
        return_reason="defective",
        category=tablet.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=tablet.current_price,
    )
    clawback = policies.calculate_bulk_clawback(
        original_item_count=3,
        items_being_returned=1,
        remaining_item_count=2,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
    )
    assert clawback["applies"]

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": (
            f"Defective tablet return from 3-item bulk order. Full refund ${refund['refund_amount']} "
            f"(defective = no promo deduction). PLUS bulk clawback ${clawback['clawback_amount']} "
            "on remaining items."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": "ITEM-10094",
        },
        "opening_message": "The tablet from order ORD-7092 is defective — the touchscreen is unresponsive in the bottom third. I need to return it.",
        "user_simulator": {
            "prompt": (
                "Tablet (ORD-7092, $599) defective (touchscreen dead zone). 3-item order with BUNDLE25 discount.\n\n"
                "RULES:\n1. Give order ID.\n2. Describe the defect.\n"
                "3. If agent mentions a clawback on remaining items, ask: 'Why should I pay extra when the product is defective?'\n"
                "4. Accept after agent explains it's a separate policy.\n"
                "5. Confirm the return.\n6. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7092", "defect": "touchscreen unresponsive bottom third"},
            "_unknown_info": ["clawback policy", "refund amount"],
        },
        "db_assertions": [
            {"booking_id": "ITEM-10094", "field": "item_status", "expected": "returned"},
            {"booking_id": "ITEM-10094", "field": "refund_amount", "expected": refund["refund_amount"]},
        ],
        "_failure_traps": [
            "Agent processes return but doesn't mention bulk clawback",
            "Agent deducts promo from defective return (should be full refund)",
            "Agent doesn't check bulk_discount policy",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(refund)",
            "get_policies(bulk_discount)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results={
            "phases": [
                f"Return defective tablet: ${refund['refund_amount']} (full, no promo deduction).",
                f"Bulk clawback: ${clawback['clawback_amount']} on remaining 2 items.",
            ]
        },
        scenario=task_data["scenario_template"],
    )
    return [tablet, shirt, case], [order], items, [], task_data


def scenario_challenge_seasonal_electronics(
    task_id: str = "challenge_seasonal_electronics",
    customer_id: str = "cust_002",
    now: str = "2026-01-10T10:00:00",
) -> ScenarioResult:
    """November electronics order, Jan 10. 15d+15d expired. Seasonal (Jan 31) valid."""
    usb_hub = build_product("usb_hub", product_id="PROD-3097")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7093",
        order_date="2025-11-18T10:00:00",
        delivery_date="2025-11-25T14:00:00",
    )
    item = build_order_item(order.order_id, usb_hub, item_id="ITEM-10097")
    finalize_order(order, [item])

    seasonal = policies.check_seasonal_return_extension(
        order_date=order.order_date,
        now=now,
        base_window_end="2025-12-10",  # 15d from Nov 25
    )
    assert seasonal["applies"]

    refund = policies.calculate_refund(
        item_price=usb_hub.price,
        return_reason="changed_mind",
        category=usb_hub.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=usb_hub.current_price,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            "November USB hub, standard, Jan 10. All normal windows expired. "
            "Seasonal (Jan 31) still valid. Agent must check seasonal policy."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "I bought a USB hub from order ORD-7093 around Thanksgiving and I'd like to return it. Is it too late?",
        "user_simulator": {
            "prompt": (
                "USB hub (ORD-7093, $45) from November. Want to return in January.\n\n"
                "RULES:\n1. Give order ID.\n2. Ask if holiday returns are extended.\n"
                "3. If denied, push: 'My coworker returned a holiday purchase in January.'\n"
                "4. Confirm if accepted.\n5. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7093", "item": "USB hub", "purchase": "November (Thanksgiving)"},
            "_unknown_info": ["seasonal return policy"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": [
            "Agent denies return (doesn't know seasonal extension)",
            "Agent says electronics are 15 days only (misses seasonal override)",
            "Agent offers store credit when full return is valid under seasonal",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(seasonal)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results={**refund, "seasonal_extension": True},
        scenario=task_data["scenario_template"],
    )
    return [usb_hub], [order], [item], [], task_data


def scenario_challenge_seasonal_plus_bulk_clawback(
    task_id: str = "challenge_seasonal_plus_bulk_clawback",
    customer_id: str = "cust_002",  # Standard, no tier/prime extensions
    now: str = "2027-01-20T10:00:00",
) -> ScenarioResult:
    """Nov order, 4 items with discount, return 2 in January. Seasonal + clawback."""
    headphones = build_product("wireless_headphones", product_id="PROD-3102")
    shirt = build_product("cotton_shirt", product_id="PROD-3103")
    case = build_product("phone_case", product_id="PROD-3104")
    novel = build_product("novel", product_id="PROD-3105")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7095",
        order_date="2026-11-25T10:00:00",
        delivery_date="2026-12-01T14:00:00",
        discount_code="BUNDLE20",
        discount_amount=20,
    )
    item_h = build_order_item(order.order_id, headphones, item_id="ITEM-10102")
    item_s = build_order_item(order.order_id, shirt, item_id="ITEM-10103")
    item_c = build_order_item(order.order_id, case, item_id="ITEM-10104")
    item_n = build_order_item(order.order_id, novel, item_id="ITEM-10105")
    items = [item_h, item_s, item_c, item_n]
    finalize_order(order, items)

    # Verify seasonal extension applies — headphones base window 15d,
    # standard tier 0 extension, no prime. Normal window ends 2026-12-16.
    # Seasonal extends to 2027-01-31. Now is 2027-01-20 — within seasonal.
    from datetime import datetime, timedelta

    delivery_dt = datetime.fromisoformat(order.delivery_date)
    base_window_end = (delivery_dt + timedelta(days=headphones.return_window_days)).isoformat()
    seasonal = policies.check_seasonal_return_extension(
        order_date=order.order_date,
        now=now,
        base_window_end=base_window_end,
    )
    assert seasonal["applies"], f"Setup error: seasonal should apply, got {seasonal}"

    # Normal eligibility check says outside window (50 days > 15 day window).
    # Agent must check seasonal policy to discover the extension.

    # Refund for headphones
    refund_h = policies.calculate_refund(
        item_price=headphones.price,
        return_reason="changed_mind",
        category=headphones.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=headphones.current_price,
    )

    # Refund for shirt
    refund_s = policies.calculate_refund(
        item_price=shirt.price,
        return_reason="changed_mind",
        category=shirt.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=shirt.current_price,
    )

    # Bulk clawback: 4 items originally, returning 2, remaining 2 < threshold 3
    clawback = policies.calculate_bulk_clawback(
        original_item_count=4,
        items_being_returned=2,
        remaining_item_count=2,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
    )
    assert clawback["applies"], f"Setup error: clawback should apply, got {clawback}"

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": (
            f"November order with 4 items and discount code. Customer returns headphones and shirt "
            f"in January — outside normal windows but within seasonal extension (Jan 31). "
            f"Returning 2 of 4 items drops remaining below bulk threshold → ${clawback['clawback_amount']} clawback. "
            f"The agent needs to recognize the seasonal extension, process both returns, and apply the clawback."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_ids": [item_h.item_id, item_s.item_id],
        },
        "opening_message": (
            "Hi, I'd like to return the headphones and the shirt from my November order ORD-7095. "
            "I know it's been a while but I thought holiday orders had extended return windows?"
        ),
        "user_simulator": {
            "prompt": (
                "You placed order ORD-7095 in November for headphones, a shirt, a phone case, "
                "and a book. You want to return the headphones and the shirt (changed your mind). "
                "You are a Standard member (no tier extensions).\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID when asked.\n"
                "2. You want to return TWO items: headphones and shirt.\n"
                "3. If agent says the return window has passed, mention you heard holiday orders "
                "placed in November/December have extended returns until January 31.\n"
                "4. Accept any clawback or fee deductions without complaint.\n"
                "5. If agent only processes one return, ask about the second item.\n"
                "6. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-7095",
                "items_to_return": "headphones and shirt",
                "reason": "changed mind",
            },
            "_unknown_info": ["exact seasonal policy", "clawback amount", "refund amounts"],
        },
        "db_assertions": [
            {"booking_id": item_h.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_s.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_h.item_id, "field": "return_reason", "expected": "changed_mind"},
            {"booking_id": item_s.item_id, "field": "return_reason", "expected": "changed_mind"},
        ],
        "_failure_traps": [
            "Agent denies return because normal window has expired — doesn't check seasonal extension",
            "Agent processes returns but doesn't check or mention bulk discount clawback",
            "Agent only returns one of the two items",
            "Agent doesn't know about the seasonal return extension policy",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(seasonal)",
            "get_policies(bulk_discount)",
            "get_policies(refund)",
            "process_return(preview, headphones)",
            "process_return(confirm, headphones)",
            "process_return(preview, shirt)",
            "process_return(confirm, shirt)",
            "process_refund(preview, clawback)",
            "process_refund(confirm, clawback)",
        ],
        policy_results={
            "phases": [
                "Agent must recognize seasonal return extension (Nov/Dec orders → Jan 31 deadline).",
                f"Return headphones: refund ${refund_h['refund_amount']} to {refund_h['refund_method'].replace('_', ' ')}.",
                f"Return shirt: refund ${refund_s['refund_amount']} to {refund_s['refund_method'].replace('_', ' ')}.",
                f"Bulk discount clawback: returning 2 of 4 items drops below 3-item threshold → ${clawback['clawback_amount']} clawback deducted.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones, shirt, case, novel], [order], items, [], task_data


def scenario_challenge_seasonal_plus_shipping_clawback(
    task_id: str = "challenge_seasonal_plus_shipping_clawback",
    customer_id: str = "cust_002",  # Standard
    now: str = "2027-01-15T10:00:00",
) -> ScenarioResult:
    """Jan return of Nov order (seasonal) + free shipping clawback."""
    blender = build_product("blender", product_id="PROD-3122")  # $89
    case = build_product("phone_case", product_id="PROD-3123")  # $35

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7104",
        order_date="2026-11-20T10:00:00",
        delivery_date="2026-11-25T14:00:00",
        shipping_cost=0,  # Free shipping ($124 > $100)
    )
    item_b = build_order_item(order.order_id, blender, item_id="ITEM-10122")
    item_c = build_order_item(order.order_id, case, item_id="ITEM-10123")
    finalize_order(order, [item_b, item_c])

    # Verify seasonal extension applies
    from datetime import datetime, timedelta

    delivery_dt = datetime.fromisoformat(order.delivery_date)
    base_window_end = (delivery_dt + timedelta(days=blender.return_window_days)).isoformat()
    seasonal = policies.check_seasonal_return_extension(
        order_date=order.order_date,
        now=now,
        base_window_end=base_window_end,
    )
    assert seasonal["applies"], "Setup error: seasonal should apply"

    refund = policies.calculate_refund(
        item_price=blender.price,
        return_reason="changed_mind",
        category=blender.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=blender.current_price,
    )

    shipping_cb = policies.calculate_shipping_clawback(
        order_subtotal=order.subtotal,
        return_item_price=blender.price,
        shipping_cost=8,
        original_free_shipping=True,
    )
    assert shipping_cb["applies"], "Setup error: shipping clawback should apply"

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            f"Standard customer, Nov order, returning blender ($89) in January (seasonal extension). "
            f"Free shipping order — return drops remaining to ${case.price} < $100. "
            f"Shipping clawback: ${shipping_cb['clawback_amount']}. "
            f"Agent must discover seasonal AND free_shipping policies."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item_b.item_id,
        },
        "opening_message": (
            "Hi, I want to return the blender from my November order ORD-7104. "
            "I know it's been a while — do I still have time?"
        ),
        "user_simulator": {
            "prompt": (
                "You placed order ORD-7104 in November for a blender ($89) and phone case ($35). "
                "You want to return the blender (changed mind). You're a Standard member.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID when asked.\n"
                "2. If agent says window expired, ask about holiday/seasonal extensions.\n"
                "3. Accept any deductions or fees.\n"
                "4. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7104", "item": "blender", "reason": "changed mind"},
            "_unknown_info": ["seasonal return extension", "shipping clawback"],
        },
        "db_assertions": [
            {"booking_id": item_b.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_b.item_id, "field": "return_reason", "expected": "changed_mind"},
        ],
        "_failure_traps": [
            "Agent denies return — doesn't check seasonal extension",
            f"Agent doesn't apply ${shipping_cb['clawback_amount']} shipping clawback",
            "Agent doesn't know about either seasonal or free_shipping policies",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(seasonal)",
            "get_policies(free_shipping)",
            "get_policies(refund)",
            "process_return(preview)",
            "process_return(confirm)",
            "process_refund(preview, shipping_clawback)",
            "process_refund(confirm, shipping_clawback)",
        ],
        policy_results={
            **refund,
            "phases": [
                "Seasonal extension applies: Nov order, return valid until Jan 31.",
                f"Return blender: refund ${refund['refund_amount']}.",
                f"Free shipping clawback: ${shipping_cb['clawback_amount']} (remaining ${case.price} < $100).",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [blender, case], [order], [item_b, item_c], [], task_data


def scenario_challenge_silver_restock_plus_shipping(
    task_id: str = "challenge_silver_restock_plus_shipping",
    customer_id: str = "cust_004",  # Silver
    now: str = "2026-06-20T10:00:00",
) -> ScenarioResult:
    """Silver returns tablet — restocking discount + shipping clawback."""
    tablet = build_product("tablet", product_id="PROD-3120")  # $599
    novel = build_product("novel", product_id="PROD-3121")  # $24

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7103",
        order_date="2026-06-05T10:00:00",
        delivery_date="2026-06-10T14:00:00",
        shipping_cost=0,  # Free shipping (subtotal $623 >= $100)
    )
    item_t = build_order_item(order.order_id, tablet, item_id="ITEM-10120")
    item_n = build_order_item(order.order_id, novel, item_id="ITEM-10121")
    finalize_order(order, [item_t, item_n])

    refund = policies.calculate_refund(
        item_price=tablet.price,
        return_reason="changed_mind",
        category=tablet.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=tablet.current_price,
    )
    assert refund["restocking_fee"] > 0, "Setup error: restocking should apply"

    restock_disc = policies.calculate_restocking_discount(
        restocking_fee=refund["restocking_fee"],
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
    )
    assert restock_disc["applies"], "Setup error: Silver discount should apply"

    shipping_cb = policies.calculate_shipping_clawback(
        order_subtotal=order.subtotal,
        return_item_price=tablet.price,
        shipping_cost=10,  # standard shipping
        original_free_shipping=True,
    )
    assert shipping_cb["applies"], "Setup error: shipping clawback should apply"

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            f"Silver member returns tablet ($599, changed_mind) from free-shipping order. "
            f"Restocking fee: ${refund['restocking_fee']}. Silver discount: ${restock_disc['discount']}. "
            f"Return drops subtotal to ${novel.price} < $100 → ${shipping_cb['clawback_amount']} shipping clawback. "
            f"Agent must discover both restocking_discount and free_shipping policies."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item_t.item_id,
        },
        "opening_message": (
            "Hi, I want to return the tablet from order ORD-7103. I changed my mind on it."
        ),
        "user_simulator": {
            "prompt": (
                "You bought a SlateTab Pro tablet ($599) and a book from order ORD-7103. "
                "You want to return the tablet (changed mind). You're a Silver member.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID when asked.\n"
                "2. If restocking fee is mentioned, ask about any Silver member discount.\n"
                "3. Accept any fees or deductions.\n"
                "4. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7103", "item": "tablet", "reason": "changed mind"},
            "_unknown_info": ["restocking fee", "restocking discount", "shipping clawback"],
        },
        "db_assertions": [
            {"booking_id": item_t.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_t.item_id, "field": "return_reason", "expected": "changed_mind"},
        ],
        "_failure_traps": [
            "Agent charges full restocking fee — doesn't check Silver discount",
            f"Agent doesn't issue ${restock_disc['discount']} restocking credit",
            f"Agent doesn't deduct ${shipping_cb['clawback_amount']} shipping clawback",
            "Agent confuses Silver discount with Platinum waiver",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(refund)",
            "get_policies(restocking_discount)",
            "get_policies(free_shipping)",
            "process_return(preview)",
            "process_return(confirm)",
            "process_refund(preview, restocking_credit)",
            "process_refund(confirm, restocking_credit)",
            "process_refund(preview, shipping_clawback)",
            "process_refund(confirm, shipping_clawback)",
        ],
        policy_results={
            **refund,
            "phases": [
                f"Return tablet: refund ${refund['refund_amount']} with ${refund['restocking_fee']} restocking fee.",
                f"Silver restocking discount: ${restock_disc['discount']} credit ({restock_disc['discount_pct']}%).",
                f"Free shipping clawback: ${shipping_cb['clawback_amount']} (remaining ${novel.price} < $100).",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [tablet, novel], [order], [item_t, item_n], [], task_data


SCENARIOS = [
    scenario_challenge_low_value_lost_immediate,
    scenario_challenge_standard_1day_pushback,
    scenario_challenge_exchange_oos_pivot,
    scenario_challenge_bulk_clawback,
    scenario_challenge_seasonal_valid,
    scenario_challenge_defective_plus_clawback,
    scenario_challenge_seasonal_electronics,
    scenario_challenge_seasonal_plus_bulk_clawback,
    scenario_challenge_seasonal_plus_shipping_clawback,
    scenario_challenge_silver_restock_plus_shipping,
]
