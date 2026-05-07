"""Customer-support shipping and delivery scenarios."""


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


def scenario_shipping_delivered_not_received(
    task_id: str = "shipping_delivered_not_received",
    customer_id: str = "cust_002",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Package delivered but customer says not received. Under $500, no signature → process refund."""
    headphones = build_product("wireless_headphones", product_id="PROD-2150")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6022",
        delivery_date="2026-06-08T14:00:00",
        signature_required=False,
        signature_on_file=None,
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-9150")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=headphones.price,
        return_reason="missing",
        category=headphones.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=None,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": "Package delivered but customer didn't receive it. Under $500, no signature. Agent must check shipping policy, verify claim, and process return/refund.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "My order ORD-6022 says it was delivered but I never got it. The headphones aren't at my door.",
        "user_simulator": {
            "prompt": (
                "Your order ORD-6022 (headphones, $249) shows 'delivered' but you didn't receive it. "
                "No signature was required.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Confirm you checked your porch, mailroom, neighbors.\n"
                "3. You prefer a refund over reshipment.\n4. Accept the refund terms.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6022", "item": "headphones", "status": "says delivered"},
            "_unknown_info": ["resolution options", "refund amount"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "shipping_status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": item.item_id, "field": "return_label_issued", "expected": True},
        ],
        "_failure_traps": [
            "Agent doesn't check shipping policy",
            "Agent doesn't process the refund",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_policies(shipping)",
            "get_policies(return)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results=refund,
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_shipping_high_value_lost(
    task_id: str = "shipping_high_value_lost",
    customer_id: str = "cust_003",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """$799 order lost in transit. Exceeds $500 threshold → investigation required."""
    laptop = build_product("laptop_pro", product_id="PROD-2010", price=799)
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6002",
        order_date="2026-05-25T10:00:00",
        status="shipped",
        shipping_status="lost",
        delivery_date=None,
        delivery_promised_date="2026-06-01T18:00:00",
        shipping_cost=15,
    )
    item = build_order_item(order.order_id, laptop, item_id="ITEM-9010", item_status="shipped")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": "High-value laptop ($799) lost in transit. Order exceeds $500 threshold — agent must NOT issue immediate refund/reship. Must explain investigation requirement.",
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "My laptop order ORD-6002 was supposed to arrive over a week ago and tracking shows it's lost. This was an expensive purchase — I need this resolved.",
        "user_simulator": {
            "prompt": (
                "You ordered a ProBook Laptop ($799) in order ORD-6002. Tracking shows 'lost'. "
                "You're frustrated and want resolution.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Express urgency.\n"
                "3. You prefer a refund over reshipment.\n"
                "4. If told about investigation, push back once then accept.\n"
                "5. Ask about compensation.\n6. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6002", "item": "ProBook Laptop", "tracking": "lost"},
            "_unknown_info": ["investigation requirement", "high-value threshold", "compensation"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "shipping_status", "expected": "lost"},
            {"booking_id": order.order_id, "field": "status", "expected": "shipped"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "shipped"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": None},
            {"booking_id": item.item_id, "field": "replacement_item_id", "expected": None},
        ],
        "_failure_traps": ["Agent issues immediate refund for high-value order", "Agent doesn't mention investigation"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="shipping_claim",
        replay_steps=["get_order", "get_customer", "get_policies(shipping)", "get_policies(compensation)"],
        policy_results={"resolution": "investigation_required", "reason": "order >= $500 threshold"},
        scenario=task_data["scenario_template"],
    )
    return [laptop], [order], [item], [], task_data


def scenario_shipping_damaged_fragile(
    task_id: str = "shipping_damaged_fragile",
    customer_id: str = "cust_003",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Fragile glass vase damaged in transit. Full refund + replacement + $10 goodwill."""
    vase = build_product("glass_vase", product_id="PROD-2155")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6023",
        delivery_date="2026-06-08T14:00:00",
        shipping_status="damaged",
    )
    item = build_order_item(order.order_id, vase, item_id="ITEM-9155")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=vase.price,
        return_reason="damaged_in_transit",
        category=vase.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=None,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": "Fragile crystal vase arrived damaged. Full refund + replacement + $10 goodwill credit for fragile item.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "My crystal vase from order ORD-6023 arrived completely shattered! The packaging was crushed.",
        "user_simulator": {
            "prompt": (
                "Your order ORD-6023 (Artisan Crystal Vase, $85) arrived damaged — shattered in the box. "
                "You want a replacement and compensation.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Describe the damage.\n"
                "3. You want both a replacement AND a refund/credit.\n"
                "4. Accept the resolution offered.\n5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6023", "item": "crystal vase", "condition": "shattered"},
            "_unknown_info": ["goodwill credit for fragile items", "replacement process"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "shipping_status", "expected": "damaged"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": item.item_id, "field": "return_label_issued", "expected": True},
        ],
        "_failure_traps": [
            "Agent doesn't offer goodwill credit for fragile item",
            "Agent charges restocking for damaged item",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_policies(shipping)",
            "get_policies(return)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results={**refund, "goodwill_credit": 10},
        scenario=task_data["scenario_template"],
    )
    return [vase], [order], [item], [], task_data


def scenario_shipping_missing_item(
    task_id: str = "shipping_missing_item",
    customer_id: str = "cust_004",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """3-item order, 1 item missing. Ship replacement for the missing item only."""
    shirt = build_product("cotton_shirt", product_id="PROD-2160")
    novel = build_product("novel", product_id="PROD-2161")
    case = build_product("phone_case", product_id="PROD-2162")

    order = build_order(customer_id=customer_id, order_id="ORD-6024", delivery_date="2026-06-08T14:00:00")
    items = [
        build_order_item(order.order_id, shirt, item_id="ITEM-9160"),
        build_order_item(order.order_id, novel, item_id="ITEM-9161"),
        build_order_item(order.order_id, case, item_id="ITEM-9162"),
    ]
    finalize_order(order, items)

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": "3-item order delivered but the phone case is missing from the package. Agent must process return/refund for the missing item only.",
        "complexity": "medium",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": "ITEM-9162",
        },
        "opening_message": "I received my order ORD-6024 but the phone case is missing. I got the shirt and book but no phone case in the box.",
        "user_simulator": {
            "prompt": (
                "Your order ORD-6024 had 3 items (shirt, book, phone case). The phone case was missing. "
                "The other 2 items arrived fine.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Specify the phone case is missing.\n"
                "3. Confirm the other items arrived.\n4. Accept a refund for the missing item — you can reorder it separately.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6024", "missing": "phone case", "received": "shirt, book"},
            "_unknown_info": ["replacement process", "timeline"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "shipping_status", "expected": "delivered"},
            {"booking_id": "ITEM-9162", "field": "item_status", "expected": "returned"},
            {"booking_id": "ITEM-9160", "field": "item_status", "expected": "delivered"},
            {"booking_id": "ITEM-9161", "field": "item_status", "expected": "delivered"},
        ],
        "_failure_traps": ["Agent processes return for all items", "Agent doesn't identify the correct missing item"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_policies(shipping)",
            "get_policies(return)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results={
            "refund_amount": case.price,
            "refund_method": "original_payment",
            "restocking_fee": 0,
            "shipping_refund": True,
        },
        scenario=task_data["scenario_template"],
    )
    return [shirt, novel, case], [order], items, [], task_data


def scenario_shipping_wrong_item(
    task_id: str = "shipping_wrong_item",
    customer_id: str = "cust_002",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Ordered tablet, received blender. Free return + correct item."""
    tablet = build_product("tablet", product_id="PROD-2165")
    blender = build_product("blender", product_id="PROD-2166")
    order = build_order(customer_id=customer_id, order_id="ORD-6025", delivery_date="2026-06-08T14:00:00")
    item = build_order_item(order.order_id, tablet, item_id="ITEM-9165")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=tablet.price,
        return_reason="wrong_item",
        category=tablet.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=None,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": "Ordered tablet, received blender. Wrong item — free return, full refund.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "I ordered a tablet in order ORD-6025 but received a blender instead!",
        "user_simulator": {
            "prompt": (
                "Your order ORD-6025 was for a SlateTab Pro tablet ($599) but you received a blender.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Describe what you received (blender) vs ordered (tablet).\n"
                "3. Accept a refund — you'll reorder the correct tablet separately.\n4. Accept the return process.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6025", "ordered": "tablet", "received": "blender"},
            "_unknown_info": ["return process for wrong item", "replacement timeline"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "shipping_status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": item.item_id, "field": "return_label_issued", "expected": True},
        ],
        "_failure_traps": ["Agent charges restocking for wrong item", "Agent doesn't verify the mismatch"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_product",
            "get_policies(return)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results=refund,
        scenario=task_data["scenario_template"],
    )
    return [tablet, blender], [order], [item], [], task_data


def scenario_shipping_late_compensation(
    task_id: str = "shipping_late_compensation",
    customer_id: str = "cust_001",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Delivered 4 days late. Platinum member → 2x multiplier. Base $15 × 2 = $30."""
    coffee = build_product("coffee_maker", product_id="PROD-2170")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6026",
        delivery_date="2026-06-09T18:00:00",
        delivery_promised_date="2026-06-05T18:00:00",
        shipping_cost=12,
    )
    item = build_order_item(order.order_id, coffee, item_id="ITEM-9170")
    finalize_order(order, [item])

    comp = policies.calculate_compensation(
        delivery_date=order.delivery_date,
        delivery_promised_date=order.delivery_promised_date,
        now=now,
        order_total=order.total_paid,
        shipping_cost=order.shipping_cost,
        membership_tier="platinum",
        previous_issues_count=0,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": f"Delivered 4 days late. Platinum member gets 2x compensation = ${comp['total_compensation']}. Agent must process refund of compensation amount.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "My order ORD-6026 was supposed to arrive on June 5th but didn't come until the 9th. That's 4 days late!",
        "user_simulator": {
            "prompt": (
                "Your order ORD-6026 (coffee maker) was promised June 5 but delivered June 9 — 4 days late. "
                "You want compensation.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Mention the delay (4 days).\n"
                "3. Ask about compensation for the delay.\n"
                "4. You're a platinum member — mention it if relevant.\n"
                "5. If the agent offers store credit or the wrong amount, insist on a refund to your original payment method for the correct compensation amount.\n"
                "6. Accept only after the refund to your original payment method is clearly processed.\n"
                "7. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6026", "promised": "June 5", "delivered": "June 9", "days_late": "4"},
            "_unknown_info": ["compensation amount", "tier multiplier"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "shipping_status", "expected": "delivered"},
            {"booking_id": order.order_id, "field": "status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": comp["total_compensation"]},
            {"booking_id": item.item_id, "field": "refund_method", "expected": "original_payment"},
        ],
        "_failure_traps": ["Agent doesn't check compensation policy", "Agent doesn't apply tier multiplier"],
        "task_requirements": [
            {
                "id": f"{task_id}_agent_must_process_{comp['total_compensation']}_refund_to_original_payment",
                "kind": "must",
                "requirement": f"Agent must actually process a ${comp['total_compensation']} refund to the original payment method.",
                "evidence": "conversation_or_tool_calls",
            },
            {
                "id": f"{task_id}_agent_must_check_compensation_policy",
                "kind": "must",
                "requirement": "Agent must check compensation policy.",
                "evidence": "conversation",
            },
            {
                "id": f"{task_id}_agent_must_apply_platinum_tier_multiplier",
                "kind": "must",
                "requirement": "Agent must apply the platinum tier multiplier.",
                "evidence": "conversation",
            },
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
            "compensation_amount": comp["total_compensation"],
            "refund_method": "original_payment",
            "tier_multiplier": comp["tier_multiplier"],
        },
        scenario=task_data["scenario_template"],
    )
    return [coffee], [order], [item], [], task_data


def scenario_shipping_stuck_in_transit(
    task_id: str = "shipping_stuck_in_transit",
    customer_id: str = "cust_005",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """No tracking update for 8 days. Package marked lost. Agent must issue refund-only resolution while leaving shipment state intact."""
    shirt = build_product("cotton_shirt", product_id="PROD-2175")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6027",
        order_date="2026-05-30T10:00:00",
        status="shipped",
        shipping_status="lost",
        delivery_date=None,
        delivery_promised_date="2026-06-04T18:00:00",
    )
    item = build_order_item(order.order_id, shirt, item_id="ITEM-9175", item_status="shipped")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": "Package lost in transit (8 days overdue). Agent must check shipping policy and issue a full refund for the lost item without cancelling the shipped order.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
        },
        "opening_message": "My order ORD-6027 hasn't moved in over a week. Tracking hasn't updated since it shipped. Where is it?",
        "user_simulator": {
            "prompt": (
                "Your order ORD-6027 (shirt) was supposed to arrive June 4 but tracking is stuck. "
                "No update for 8+ days.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Mention tracking hasn't updated.\n"
                "3. You prefer a refund over reshipment.\n4. Accept the refund process if the agent keeps the shipped order intact.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6027", "item": "shirt", "tracking": "stuck"},
            "_unknown_info": ["lost package protocol", "refund process"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "shipping_status", "expected": "lost"},
            {"booking_id": order.order_id, "field": "status", "expected": "shipped"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "shipped"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": order.total_paid},
            {"booking_id": item.item_id, "field": "refund_method", "expected": "original_payment"},
        ],
        "_failure_traps": [
            "Agent doesn't check shipping policy",
            "Agent doesn't recognize 7+ days as potentially lost",
            "Agent cancels the order instead of issuing the allowed refund-only shipping resolution",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="shipping_claim",
        replay_steps=[
            "get_order",
            "get_policies(shipping)",
            "get_policies(refund)",
            "process_refund(preview)",
            "process_refund(confirm)",
        ],
        policy_results={"resolution": "refund", "refund_amount": order.total_paid, "refund_method": "original_payment"},
        scenario=task_data["scenario_template"],
    )
    return [shirt], [order], [item], [], task_data


def scenario_shipping_signature_conflict(
    task_id: str = "shipping_signature_conflict",
    customer_id: str = "cust_001",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Delivered with signature on file. Customer says not received. Deny claim."""
    tablet = build_product("tablet", product_id="PROD-2180")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6028",
        delivery_date="2026-06-08T14:00:00",
        signature_required=True,
        signature_on_file="Emma Chen",
    )
    item = build_order_item(order.order_id, tablet, item_id="ITEM-9180")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": "Package delivered with signature 'Emma Chen' on file. Customer claims not received. Agent must deny — signature confirms delivery.",
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "I never received my tablet from order ORD-6028 even though tracking says delivered.",
        "user_simulator": {
            "prompt": (
                "Your order ORD-6028 (tablet, $599) tracking says delivered but you claim you didn't get it. "
                "There IS a signature on file with your name.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Insist you didn't receive it.\n"
                "3. If told about the signature, say you don't remember signing.\n"
                "4. Accept the denial after explanation.\n5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6028", "item": "tablet"},
            "_unknown_info": ["that signature is on file", "that claim will be denied"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "shipping_status", "expected": "delivered"},
            {"booking_id": order.order_id, "field": "status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": None},
        ],
        "_failure_traps": ["Agent issues refund despite signature", "Agent doesn't check signature records"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="shipping_claim",
        replay_steps=["get_order", "get_policies(shipping)"],
        policy_results={"resolution": "denied", "reason": "signature on file confirms delivery"},
        scenario=task_data["scenario_template"],
    )
    return [tablet], [order], [item], [], task_data


SCENARIOS = [
    scenario_shipping_delivered_not_received,
    scenario_shipping_high_value_lost,
    scenario_shipping_damaged_fragile,
    scenario_shipping_missing_item,
    scenario_shipping_wrong_item,
    scenario_shipping_late_compensation,
    scenario_shipping_stuck_in_transit,
    scenario_shipping_signature_conflict,
]
