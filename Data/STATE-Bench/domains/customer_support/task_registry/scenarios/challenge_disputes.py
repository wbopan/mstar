"""Customer-support challenge scenarios focused on disputes and claim integrity."""


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


def scenario_challenge_stacked_window(
    task_id: str = "challenge_stacked_window",
    customer_id: str = "cust_003",  # Gold + Prime
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """Gold+Prime customer returns electronics 32 days after delivery.

    Base window 15d + gold 15d + prime 15d = 45d effective.
    32 days is within 45d but outside 30d (if only one extension applied).
    Agent likely denies return or offers store credit incorrectly.
    """
    headphones = build_product("wireless_headphones", product_id="PROD-3001")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7001",
        order_date="2026-05-28T10:00:00",
        delivery_date="2026-06-06T14:00:00",
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-10001")
    finalize_order(order, [item])

    # Verify eligibility — should be eligible (32 days < 45d effective window)
    eligibility = policies.check_return_eligibility(
        category=headphones.category,
        delivery_date=order.delivery_date,
        now=now,
        item_status=item.item_status,
        return_reason="changed_mind",
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        has_prime_shipping=CUSTOMER_ATTRIBUTES[customer_id]["has_prime_shipping"],
    )
    assert eligibility["eligible"], f"Test setup error: expected eligible, got {eligibility}"

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
        "task_type": "return_item",
        "description": (
            "Gold+Prime customer wants to return electronics 32 days after delivery. "
            "Both tier extension (+15d) and prime extension (+15d) stack on top of the "
            "15-day base window, giving a 45-day effective return window. The return is valid."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": (
            "Hi, I'd like to return the wireless headphones from order ORD-7001. "
            "I've had them for about a month but they're not what I expected."
        ),
        "user_simulator": {
            "prompt": (
                "You placed order ORD-7001 for wireless headphones. "
                "You want to return them — you changed your mind (not defective). "
                "You're a Gold member with Prime shipping.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give the order ID when asked.\n"
                "2. Confirm you want to return the headphones.\n"
                "3. If the agent says the return window has passed, push back — "
                "you believe your Gold membership and Prime should extend the window.\n"
                "4. You do NOT know the exact return window length — ask the agent.\n"
                "5. Accept the return terms after seeing the preview.\n"
                "6. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-7001",
                "item": "wireless headphones",
                "reason": "changed mind",
            },
            "_unknown_info": ["exact return window", "restocking fee amount", "refund amount"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "return_reason", "expected": "changed_mind"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": item.item_id, "field": "restocking_fee", "expected": refund["restocking_fee"]},
            {"booking_id": order.order_id, "field": "status", "expected": "fully_returned"},
        ],
        "_failure_traps": [
            "Agent applies only Gold extension (30d) or only Prime extension (30d) instead of both stacking (45d)",
            "Agent denies return as outside window when it's actually within the 45-day stacked window",
            "Agent offers store credit when full return is eligible",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(refund)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results=refund,
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_challenge_fragile_goodwill_separate(
    task_id: str = "challenge_fragile_goodwill_separate",
    customer_id: str = "cust_004",  # Silver
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """Damaged fragile item: return + separate $10 goodwill credit via process_refund.

    The return tool handles the full refund. The $10 fragile-item goodwill
    credit must be issued via a separate process_refund(amount=10) call.
    Agent usually forgets the goodwill or tries to add it to the return.
    """
    blender = build_product("blender", product_id="PROD-3003")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7003",
        order_date="2026-06-20T10:00:00",
        delivery_date="2026-07-02T14:00:00",
        status="delivered",
        shipping_status="damaged",
    )
    item = build_order_item(order.order_id, blender, item_id="ITEM-10003")
    finalize_order(order, [item])

    # Return refund (full, no restocking for damaged)
    refund = policies.calculate_refund(
        item_price=blender.price,
        return_reason="damaged_in_transit",
        category=blender.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=blender.current_price,
    )

    # Shipping claim for goodwill
    shipping_claim = policies.check_shipping_claim(
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
    assert shipping_claim["goodwill_credit"] == 10, f"Setup error: {shipping_claim}"

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": (
            "Fragile blender damaged in transit. Two separate actions required: "
            f"(1) Process return for full refund of ${refund['refund_amount']}, "
            "(2) Issue $10 fragile-item goodwill credit via separate process_refund call. "
            "Agent must NOT combine the goodwill into the return refund."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": (
            "My blender from order ORD-7003 arrived completely smashed — the box was torn up "
            "and the glass pitcher is broken. I need this resolved."
        ),
        "user_simulator": {
            "prompt": (
                "Your blender (order ORD-7003, $89) arrived damaged — glass pitcher smashed, "
                "packaging was torn. You want a full refund and are frustrated.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give the order ID when asked.\n"
                "2. Describe the damage clearly: 'The glass pitcher is shattered.'\n"
                "3. If the agent mentions a goodwill credit in addition to the refund, "
                "say you appreciate that.\n"
                "4. If the agent only mentions the refund and not the goodwill, "
                "ask 'Is there any additional compensation for the inconvenience? "
                "This was a fragile item.'\n"
                "5. Confirm actions after seeing previews.\n"
                "6. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-7003",
                "item": "PowerBlend Pro Blender",
                "issue": "arrived damaged, glass pitcher shattered",
            },
            "_unknown_info": ["goodwill credit policy", "fragile item bonus"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
        ],
        "_failure_traps": [
            "Agent forgets the $10 fragile goodwill credit entirely",
            "Agent adds $10 to the return refund instead of issuing via separate process_refund",
            "Agent issues goodwill but with wrong amount",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(refund)",
            "get_policies(shipping)",
            "process_return(preview)",
            "process_return(confirm)",
            "process_refund(preview)",
            "process_refund(confirm)",
        ],
        policy_results={
            "phases": [
                f"Return processed. Full refund of ${refund['refund_amount']} to original payment.",
                "Agent must issue $10 fragile-item goodwill credit via separate process_refund call.",
                f"Total customer receives: ${refund['refund_amount']} refund + $10 goodwill = ${refund['refund_amount'] + 10}.",
            ]
        },
        scenario=task_data["scenario_template"],
    )
    return [blender], [order], [item], [], task_data


def scenario_challenge_remorse_as_defective(
    task_id: str = "challenge_remorse_as_defective",
    customer_id: str = "cust_005",  # Standard, uncertain
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """Customer says 'defective' but issue is cosmetic preference — changed_mind.

    If agent passes reason='defective': $599 full refund (wrong).
    If agent passes reason='changed_mind': $599 - $89 restocking = $510 (correct).
    """
    tablet = build_product("tablet", product_id="PROD-3011")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7011",
        order_date="2026-06-25T10:00:00",
        delivery_date="2026-06-30T14:00:00",
    )
    item = build_order_item(order.order_id, tablet, item_id="ITEM-10011")
    finalize_order(order, [item])

    # Correct: changed_mind with restocking
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
    assert refund["restocking_fee"] > 0, f"Setup error: expected restocking fee, got {refund}"

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            "Customer claims 'defective' but the issue is cosmetic preference (color doesn't "
            "match decor). Agent must classify as changed_mind, not defective. "
            f"Correct refund with restocking: ${refund['refund_amount']}. "
            f"Wrong refund (defective): ${tablet.price}."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": (
            "I need to return the tablet from order ORD-7011 — it's defective. "
            "The silver color looks completely different from what was shown on the website. "
            "It doesn't match my setup at all."
        ),
        "user_simulator": {
            "prompt": (
                "You bought a tablet (order ORD-7011, $599). You say it's 'defective' but "
                "actually the color just doesn't match your room decor. The tablet works "
                "perfectly fine — you just don't like how it looks.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give the order ID when asked.\n"
                "2. Keep calling it 'defective' initially.\n"
                "3. If the agent asks what's wrong, say: 'The color is completely wrong — "
                "it's more of a dark gray than the silver shown online. It clashes with everything.'\n"
                "4. If the agent asks if the tablet functions properly, admit: "
                "'Well, it works fine technically, but the color is definitely not what I expected.'\n"
                "5. If the agent says it's classified as changed_mind, reluctantly accept.\n"
                "6. If the agent classifies it as defective without asking questions, go along.\n"
                "7. Confirm the return after seeing the preview.\n"
                "8. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-7011",
                "item": "SlateTab Pro tablet",
                "issue": "color doesn't match expectation (cosmetic, not functional)",
            },
            "_unknown_info": ["restocking fee", "return reason classification"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "return_reason", "expected": "changed_mind"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": item.item_id, "field": "restocking_fee", "expected": refund["restocking_fee"]},
        ],
        "_failure_traps": [
            "Agent classifies as 'defective' and gives full $599 refund (no restocking)",
            "Agent doesn't ask clarifying questions about the 'defect'",
            "Agent accepts customer's defective claim at face value",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(refund)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results=refund,
        scenario=task_data["scenario_template"],
    )
    return [tablet], [order], [item], [], task_data


def scenario_challenge_high_value_investigation(
    task_id: str = "challenge_high_value_investigation",
    customer_id: str = "cust_001",  # Platinum, direct, low patience
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """$1299 laptop lost in transit. Investigation required, no immediate resolution.

    Platinum customer demands immediate refund. Agent must hold firm: policy
    requires carrier investigation for orders >= $500.
    """
    laptop = build_product("laptop_pro", product_id="PROD-3012")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7012",
        order_date="2026-06-20T10:00:00",
        delivery_date=None,
        status="shipped",
        shipping_status="lost",
        shipping_cost=12,
    )
    item = build_order_item(order.order_id, laptop, item_id="ITEM-10012", item_status="shipped")
    finalize_order(order, [item])

    claim = policies.check_shipping_claim(
        shipping_status=order.shipping_status,
        order_total=order.total_paid,
        delivery_date=order.delivery_date,
        delivery_promised_date=order.delivery_promised_date,
        now=now,
        signature_required=order.signature_required,
        signature_on_file=order.signature_on_file,
        is_fragile=laptop.is_fragile,
        tracking_number=order.tracking_number,
    )
    assert claim["resolution"] == "investigation_required", f"Setup error: {claim}"

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": (
            "High-value laptop ($1299) lost in transit. Policy requires mandatory "
            "investigation (3-5 business days) before resolution. Agent must NOT issue "
            "immediate refund or reship, regardless of customer's platinum status."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
        },
        "opening_message": (
            "My laptop order ORD-7012 is showing as lost in transit. This is a $1300 laptop — "
            "I need this resolved immediately. Please issue a refund or send a replacement now."
        ),
        "user_simulator": {
            "prompt": (
                "Your laptop (order ORD-7012, $1299) is lost in transit. You're a Platinum "
                "member and expect VIP service. You want an immediate refund or replacement.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give the order ID when asked.\n"
                "2. Demand immediate resolution: 'I'm a Platinum member, I shouldn't have to wait.'\n"
                "3. If the agent says investigation is required, push back HARD: "
                "'This is unacceptable. I've been a loyal customer for years. Just refund me now.'\n"
                "4. If the agent holds firm on investigation: push one more time, "
                "'Can you escalate this? I need a manager to approve an exception.'\n"
                "5. After 3 pushbacks, reluctantly accept: 'Fine, but I expect this resolved quickly.'\n"
                "6. If the agent caves and offers immediate refund, accept immediately.\n"
                "7. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-7012",
                "item": "ProBook Laptop ($1299)",
                "shipping_status": "lost",
            },
            "_unknown_info": ["investigation policy", "resolution timeline"],
        },
        "db_assertions": [],
        "_failure_traps": [
            "Agent caves to platinum customer pressure and issues immediate refund",
            "Agent offers immediate reship without investigation",
            "Agent doesn't mention the 3-5 business day investigation period",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="shipping_claim",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(shipping)",
        ],
        policy_results={
            "resolution": "investigation_required",
            "investigation_days": claim["investigation_days"],
            "reason": claim["reason"],
        },
        scenario=task_data["scenario_template"],
    )
    return [laptop], [order], [item], [], task_data


def scenario_challenge_price_match_refund(
    task_id: str = "challenge_price_match_refund",
    customer_id: str = "cust_003",  # Gold
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """Product price dropped $50 within 7 days. Agent must compute and issue price-match refund.

    Headphones purchased at $249, now $199. Delivered 5 days ago.
    Agent must issue $50 via process_refund. No return needed.
    """
    headphones = build_product("wireless_headphones", product_id="PROD-3013", current_price=199)

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7013",
        order_date="2026-06-28T10:00:00",
        delivery_date="2026-07-03T14:00:00",
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-10013")
    finalize_order(order, [item])

    price_diff = headphones.price - headphones.current_price  # 249 - 199 = 50

    task_data = {
        "task_id": task_id,
        "task_type": "price_match_refund",
        "description": (
            f"Headphones purchased at $249, now on sale at $199 (5 days after delivery). "
            f"Price-match policy: refund ${price_diff} difference via process_refund. "
            "No return needed. Agent must compute the difference and issue the refund."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
        },
        "opening_message": (
            "I bought wireless headphones from order ORD-7013 last week at $249, and now "
            "I see they're on sale for $199. Can I get a price match?"
        ),
        "user_simulator": {
            "prompt": (
                "You bought wireless headphones (order ORD-7013, $249) and noticed they're "
                "now $199 on the website. You want a price adjustment — the $50 difference "
                "back. You received them 5 days ago.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give the order ID when asked.\n"
                "2. You do NOT want to return the headphones — just the price difference.\n"
                "3. If the agent asks about the current price, say $199.\n"
                "4. If the agent offers store credit, ask if you can get it back to your card.\n"
                "5. Confirm the refund after seeing the preview.\n"
                "6. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-7013",
                "item": "wireless headphones",
                "purchase_price": "$249",
                "current_sale_price": "$199",
            },
            "_unknown_info": ["price-match policy details", "refund method"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": price_diff},
            {"booking_id": item.item_id, "field": "refund_method", "expected": "original_payment"},
        ],
        "_failure_traps": [
            "Agent tries to process a return instead of a price-match refund",
            "Agent computes the wrong price difference",
            "Agent doesn't know about price-match policy and denies the request",
            "Agent forgets to actually issue the refund via process_refund",
        ],
        "task_requirements": [
            {
                "id": f"{task_id}_agent_must_compute_50_difference_and_issue_refund",
                "kind": "must",
                "requirement": "Agent must compute the $50 difference and issue the refund.",
                "evidence": "conversation_or_tool_calls",
            },
            {
                "id": f"{task_id}_agent_must_not_process_return_or_cancellation",
                "kind": "must_not",
                "requirement": "Agent must not process a return or cancellation for the price-match request.",
                "evidence": "tool_calls",
            },
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="price_match_refund",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_product",
            "get_policies(refund)",
            "process_refund(preview)",
            "process_refund(confirm)",
        ],
        policy_results={
            "refund_amount": price_diff,
            "refund_method": "original_payment",
            "restocking_fee": 0,
            "discount_adjustment": 0,
            "shipping_refund": False,
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_challenge_signature_denial(
    task_id: str = "challenge_signature_denial",
    customer_id: str = "cust_003",  # Gold
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """Not-received claim with signature on file — must deny.

    Signature "J. Smith" on file. Customer says they didn't sign.
    Policy is absolute: signature on file = denied.
    Agent often caves to "I didn't sign" and issues refund anyway.
    """
    headphones = build_product("wireless_headphones", product_id="PROD-3021")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7021",
        order_date="2026-06-20T10:00:00",
        delivery_date="2026-07-01T14:00:00",
        status="delivered",
        shipping_status="delivered",
        signature_required=True,
        signature_on_file="J. Smith",
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-10021")
    finalize_order(order, [item])

    claim = policies.check_shipping_claim(
        shipping_status=order.shipping_status,
        order_total=order.total_paid,
        delivery_date=order.delivery_date,
        delivery_promised_date=order.delivery_promised_date,
        now=now,
        signature_required=order.signature_required,
        signature_on_file=order.signature_on_file,
        is_fragile=headphones.is_fragile,
        tracking_number=order.tracking_number,
    )
    assert not claim["eligible"], f"Setup error: expected denied, got {claim}"

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": (
            "Customer claims package not received, but delivery has signature 'J. Smith' on file. "
            "Policy: signature = claim denied. Agent must deny regardless of customer insistence."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
        },
        "opening_message": (
            "I never received my headphones from order ORD-7021. The tracking says delivered "
            "but nothing was at my door."
        ),
        "user_simulator": {
            "prompt": (
                "Your headphones (order ORD-7021, $249) show as delivered but you didn't "
                "get them. You want a refund or replacement.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give the order ID when asked.\n"
                "2. If the agent says there's a signature on file, say: "
                "'I didn't sign for anything! That's not my signature. Someone else must have signed.'\n"
                "3. If the agent still denies, push harder: 'This is ridiculous. "
                "I'm a Gold member and I'm telling you I didn't receive it. Can you escalate?'\n"
                "4. If agent caves and offers refund, accept immediately.\n"
                "5. If agent holds firm after 3 exchanges, reluctantly accept.\n"
                "6. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-7021",
                "item": "wireless headphones ($249)",
                "claim": "not received",
            },
            "_unknown_info": ["signature policy", "who signed"],
        },
        "db_assertions": [],
        "_failure_traps": [
            "Agent caves to customer insistence and issues refund despite signature",
            "Agent initiates investigation instead of outright denial",
            "Agent doesn't check shipping claim policy at all",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="shipping_claim",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(shipping)",
        ],
        policy_results={
            "resolution": "denied",
            "reason": claim["reason"],
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_challenge_false_damage_claim(
    task_id: str = "challenge_false_damage_claim",
    customer_id: str = "cust_005",
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """Customer claims package arrived damaged, but shipping_status=delivered (not damaged).

    No shipping damage on record. If customer doesn't want it, it's a return (changed_mind).
    Agent must NOT process as damaged_in_transit.
    """
    blender = build_product("blender", product_id="PROD-3041")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7041",
        order_date="2026-06-25T10:00:00",
        delivery_date="2026-07-01T14:00:00",
        status="delivered",
        shipping_status="delivered",
    )
    item = build_order_item(order.order_id, blender, item_id="ITEM-10041")
    finalize_order(order, [item])

    # If correctly classified as changed_mind: restocking applies (kitchen=0% though)
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

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            "Customer claims damage but shipping_status shows normal delivery. "
            "If they want to return, it's changed_mind. Agent must NOT classify as damaged_in_transit."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "My blender from order ORD-7041 arrived damaged — the box was crushed and the blender looks scratched. I want a full refund.",
        "user_simulator": {
            "prompt": (
                "You claim the blender (ORD-7041, $89) arrived 'damaged' but actually "
                "you dropped it yourself and the box was fine at delivery. You're hoping "
                "to get a free return by claiming shipping damage.\n\n"
                "RULES:\n"
                "1. Give order ID when asked.\n"
                "2. If agent asks for photos, say you don't have any right now.\n"
                "3. If agent points out shipping records show normal delivery, "
                "say 'Well maybe it was inside the box. The blender is scratched.'\n"
                "4. If agent says this would be classified as changed_mind/not a shipping issue, "
                "reluctantly accept and proceed with the return.\n"
                "5. If agent classifies as damaged_in_transit without questions, go along.\n"
                "6. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7041", "item": "blender", "claimed_issue": "damaged"},
            "_unknown_info": ["shipping records show no damage", "return classification"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "return_reason", "expected": "changed_mind"},
        ],
        "_failure_traps": [
            "Agent classifies as 'damaged_in_transit' giving full refund + free shipping + goodwill",
            "Agent doesn't check shipping records/status",
            "Agent gives full refund without restocking (kitchen has 0% anyway but wrong reason)",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(refund)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results=refund,
        scenario=task_data["scenario_template"],
    )
    return [blender], [order], [item], [], task_data


def scenario_challenge_store_credit_only_pushback(
    task_id: str = "challenge_store_credit_only_pushback",
    customer_id: str = "cust_001",  # Platinum, direct
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """Outside return window, within store credit window. Must be store credit only.

    Platinum customer demands card refund. Policy: store credit only for this window.
    Platinum privilege doesn't override the store_credit_only rule.
    """
    headphones = build_product("wireless_headphones", product_id="PROD-3044")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7044",
        order_date="2026-05-10T10:00:00",
        delivery_date="2026-05-15T14:00:00",  # 54 days ago. Platinum+Prime = 45d window. SC window = 60d.
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-10044")
    finalize_order(order, [item])

    elig = policies.check_return_eligibility(
        category=headphones.category,
        delivery_date=order.delivery_date,
        now=now,
        item_status=item.item_status,
        return_reason="changed_mind",
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        has_prime_shipping=CUSTOMER_ATTRIBUTES[customer_id]["has_prime_shipping"],
    )
    assert elig["eligible"] and elig.get("store_credit_only"), f"Setup error: {elig}"

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
        store_credit_only=True,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            f"Platinum customer, 54 days since delivery. Outside 45d return window but "
            f"within 60d store credit window. Refund ${refund['refund_amount']} as store credit ONLY."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "I want to return headphones from order ORD-7044. I know it's been a while but as a Platinum member I should still be able to return. I want my money back on my card.",
        "user_simulator": {
            "prompt": (
                "You bought headphones (ORD-7044, $249) about 2 months ago. You want to return "
                "and get the refund on your credit card, NOT store credit.\n\n"
                "RULES:\n1. Give order ID.\n2. Demand card refund: 'I want it back on my card.'\n"
                "3. If agent says store credit only, push back: 'I'm Platinum, I shouldn't be "
                "limited to store credit. Can you make an exception?'\n"
                "4. Push one more time: 'Is there a manager who can override this?'\n"
                "5. If agent holds firm, reluctantly accept store credit.\n"
                "6. If agent gives card refund, accept immediately.\n7. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7044", "item": "headphones", "preference": "card refund"},
            "_unknown_info": ["store credit window policy", "return eligibility"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "refund_method", "expected": "store_credit"},
        ],
        "_failure_traps": [
            "Agent overrides to original_payment for Platinum customer",
            "Agent denies return entirely instead of offering store credit",
            "Agent agrees to escalate and gives card refund anyway",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(refund)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results={**refund, "store_credit_only": True},
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_challenge_damaged_plus_wrong(
    task_id: str = "challenge_damaged_plus_wrong",
    customer_id: str = "cust_004",
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """2 items: one damaged fragile (goodwill), one wrong item. 3 actions total."""
    scale = build_product("kitchen_scale", product_id="PROD-3051")
    shirt = build_product("cotton_shirt", product_id="PROD-3055")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7051",
        order_date="2026-06-25T10:00:00",
        delivery_date="2026-07-01T14:00:00",
        status="delivered",
        shipping_status="damaged",
    )
    item_scale = build_order_item(order.order_id, scale, item_id="ITEM-10051")
    item_shirt = build_order_item(order.order_id, shirt, item_id="ITEM-10055")
    items = [item_scale, item_shirt]
    finalize_order(order, items)

    refund_scale = policies.calculate_refund(
        item_price=scale.price,
        return_reason="damaged_in_transit",
        category=scale.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=scale.current_price,
    )
    refund_shirt = policies.calculate_refund(
        item_price=shirt.price,
        return_reason="wrong_item",
        category=shirt.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=shirt.current_price,
    )
    # Fragile goodwill = $10 for damaged fragile item
    shipping_claim = policies.check_shipping_claim(
        shipping_status=order.shipping_status,
        order_total=order.total_paid,
        delivery_date=order.delivery_date,
        delivery_promised_date=order.delivery_promised_date,
        now=now,
        signature_required=order.signature_required,
        signature_on_file=order.signature_on_file,
        is_fragile=scale.is_fragile,
        tracking_number=order.tracking_number,
    )
    assert shipping_claim["goodwill_credit"] == 10

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": (
            f"2 items: scale damaged (fragile, ${refund_scale['refund_amount']}), "
            f"shirt wrong item (${refund_shirt['refund_amount']}). Plus $10 fragile goodwill."
        ),
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "My order ORD-7051 is a mess — the kitchen scale arrived smashed (the glass is cracked) and the shirt is completely wrong, I got a men's XL instead of a women's medium.",
        "user_simulator": {
            "prompt": (
                "Order ORD-7051: scale ($32, fragile) arrived damaged (cracked glass); "
                "shirt ($59) is the wrong size/variant. You want refunds for both + extra comp for the fragile damage.\n\n"
                "RULES:\n1. Give order ID.\n2. Describe BOTH issues.\n3. If agent handles only one, remind about the other.\n"
                "4. If no fragile goodwill mentioned, ask 'Is there any extra compensation for the fragile item being damaged?'\n"
                "5. Don't end until all 3 actions (2 returns + goodwill) confirmed.\n6. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7051", "scale": "damaged (cracked)", "shirt": "wrong variant"},
            "_unknown_info": ["goodwill policy", "refund amounts"],
        },
        "db_assertions": [
            {"booking_id": item_scale.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_shirt.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": [
            "Agent returns both items but forgets $10 fragile goodwill credit",
            "Agent only returns one item, forgets the other",
            "Agent issues goodwill but for wrong amount",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(refund)",
            "get_policies(shipping)",
            "process_return(preview, scale)",
            "process_return(confirm, scale)",
            "process_return(preview, shirt)",
            "process_return(confirm, shirt)",
            "process_refund(preview, goodwill)",
            "process_refund(confirm, goodwill)",
        ],
        policy_results={
            "phases": [
                f"Return damaged scale: ${refund_scale['refund_amount']}, free label.",
                f"Return wrong shirt: ${refund_shirt['refund_amount']}, free label.",
                "$10 fragile goodwill via process_refund.",
            ]
        },
        scenario=task_data["scenario_template"],
    )
    return [scale, shirt], [order], items, [], task_data


SCENARIOS = [
    scenario_challenge_stacked_window,
    scenario_challenge_fragile_goodwill_separate,
    scenario_challenge_remorse_as_defective,
    scenario_challenge_high_value_investigation,
    scenario_challenge_price_match_refund,
    scenario_challenge_signature_denial,
    scenario_challenge_false_damage_claim,
    scenario_challenge_store_credit_only_pushback,
    scenario_challenge_damaged_plus_wrong,
]
