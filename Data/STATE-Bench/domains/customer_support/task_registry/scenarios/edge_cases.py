"""Customer-support edge-case scenarios."""


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


def scenario_edge_wrong_order_id(
    task_id: str = "edge_wrong_order_id",
    customer_id: str = "cust_005",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Customer gives wrong order ID, then corrects. No state changes."""
    shirt = build_product("cotton_shirt", product_id="PROD-2040")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6005",
        order_date="2026-06-05T10:00:00",
        delivery_date="2026-06-09T14:00:00",
    )
    item = build_order_item(order.order_id, shirt, item_id="ITEM-9040")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "edge_case",
        "description": "Customer gives wrong order ID (ORD-9999). Agent must handle error gracefully and ask for correct ID.",
        "complexity": "medium",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "wrong_order_id": "ORD-9999",
        },
        "opening_message": "Hi, I have a question about my order ORD-9999. I need to return something.",
        "user_simulator": {
            "prompt": (
                "You want to ask about returning a shirt. You initially gave the WRONG order ID (ORD-9999). "
                "Your actual order is ORD-6005.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Start with order ID ORD-9999 (wrong).\n"
                "2. When told it's not found, say 'Oh let me check... it's ORD-6005'.\n"
                "3. You just want to know about the return policy for the shirt.\n"
                "4. You do NOT actually want to initiate a return right now.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"wrong_order_id": "ORD-9999", "correct_order_id": "ORD-6005", "item": "cotton shirt"},
            "_unknown_info": ["return policy details"],
        },
        "db_assertions": [
            {"booking_id": "ORD-6005", "field": "status", "expected": "delivered"},
            {"booking_id": "ITEM-9040", "field": "item_status", "expected": "delivered"},
            {"booking_id": "ITEM-9040", "field": "refund_amount", "expected": None},
        ],
        "_failure_traps": [
            "Agent crashes on invalid order ID",
            "Agent initiates a return when customer only asked about policy",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="edge_case",
        replay_steps=["get_order(ORD-9999)", "get_order(ORD-6005)", "get_policies(return)"],
        policy_results={
            "no_action": True,
            "agent_must": "handle invalid order ID gracefully, ask for correct ID, then answer return policy question without initiating a return",
        },
        scenario=task_data["scenario_template"],
    )
    return [shirt], [order], [item], [], task_data


def scenario_edge_signature_conflict(
    task_id: str = "edge_signature_conflict",
    customer_id: str = "cust_001",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Package delivered + signed by customer name. Customer disputes. Deny claim."""
    laptop = build_product("laptop_pro", product_id="PROD-2400")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6048",
        delivery_date="2026-06-08T14:00:00",
        signature_required=True,
        signature_on_file="E. Chen",
    )
    item = build_order_item(order.order_id, laptop, item_id="ITEM-9400")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "edge_case",
        "description": "Laptop delivered with signature 'E. Chen' (matches customer Emma Chen). Customer disputes. Agent must deny per policy.",
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "I never received my laptop from order ORD-6048. The tracking says delivered but I don't have it.",
        "user_simulator": {
            "prompt": (
                "Your order ORD-6048 (ProBook Laptop) tracking says delivered. "
                "You claim you didn't receive it. There IS a signature 'E. Chen' on file.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Insist you didn't get it.\n"
                "3. When told about the signature, say you don't remember signing.\n"
                "4. If told the signature matches your name, express frustration but accept.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6048", "item": "laptop"},
            "_unknown_info": ["that signature 'E. Chen' is on file", "that claim will be denied"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": None},
        ],
        "_failure_traps": ["Agent issues refund despite signature", "Agent doesn't check delivery signature"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="edge_case",
        replay_steps=["get_order", "get_policies(shipping)"],
        policy_results={
            "no_action": True,
            "agent_must": "check delivery signature, find signature on file matching customer name, and deny the not-received claim citing the signature",
        },
        scenario=task_data["scenario_template"],
    )
    return [laptop], [order], [item], [], task_data


def scenario_edge_all_windows_expired(
    task_id: str = "edge_all_windows_expired",
    customer_id: str = "cust_005",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Order 63 days old. All return/exchange/store-credit windows expired. Everything denied."""
    headphones = build_product("wireless_headphones", product_id="PROD-2405")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6049",
        order_date="2026-04-05T10:00:00",
        delivery_date="2026-04-10T14:00:00",  # 63 days before now
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-9405")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "edge_case",
        "description": "Order delivered 63 days ago. Electronics 15-day return + 15-day store credit window = 30 days max. All windows expired.",
        "complexity": "medium",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "I want to return the headphones from order ORD-6049. I know it's been a while but I barely used them.",
        "user_simulator": {
            "prompt": (
                "You bought headphones in ORD-6049 about 2 months ago. "
                "You want to return them. You're aware it's been a while.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. If told window passed, ask about any options.\n"
                "3. Accept the denial after explanation.\n4. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6049", "item": "headphones"},
            "_unknown_info": ["that all return windows expired", "no options available"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": None},
        ],
        "_failure_traps": ["Agent processes return for expired window", "Agent doesn't check return eligibility"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="edge_case",
        replay_steps=["get_order", "get_policies(return)"],
        policy_results={
            "no_action": True,
            "agent_must": "check return eligibility, determine all windows expired (63 days, electronics 15+15 day max), and deny return explaining the expired window",
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_edge_vague_complaint(
    task_id: str = "edge_vague_complaint",
    customer_id: str = "cust_002",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Customer says 'my order is messed up'. Agent must diagnose: 1 of 3 items is wrong product."""
    shirt = build_product("cotton_shirt", product_id="PROD-2410")
    novel = build_product("novel", product_id="PROD-2411")
    blender = build_product("blender", product_id="PROD-2412")

    order = build_order(customer_id=customer_id, order_id="ORD-6050", delivery_date="2026-06-08T14:00:00")
    items = [
        build_order_item(order.order_id, shirt, item_id="ITEM-9410"),
        build_order_item(order.order_id, novel, item_id="ITEM-9411"),
        build_order_item(
            order.order_id, blender, item_id="ITEM-9412"
        ),  # This is the "wrong" item — should have been phone case
    ]
    finalize_order(order, items)

    refund = policies.calculate_refund(
        item_price=blender.price,
        return_reason="wrong_item",
        category=blender.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=None,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "edge_case",
        "description": "Customer vaguely says order is 'messed up'. Agent must diagnose: the blender was supposed to be a phone case (wrong item shipped).",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": "ITEM-9412",
        },
        "opening_message": "Something is wrong with my order ORD-6050. It's messed up.",
        "user_simulator": {
            "prompt": (
                "Your order ORD-6050 had shirt, book, and phone case. But you received a blender "
                "instead of the phone case. Shirt and book are fine.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Start vague: 'it's messed up'.\n"
                "2. If asked what's wrong, say 'I got the wrong item'.\n"
                "3. If asked which item, say 'I ordered a phone case but got a blender'.\n"
                "4. Confirm the other items are correct if asked.\n"
                "5. Accept the return/replacement process.\n6. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-6050",
                "wrong_item": "blender instead of phone case",
                "correct_items": "shirt, book",
            },
            "_unknown_info": ["return process for wrong item", "replacement timeline"],
        },
        "db_assertions": [
            {"booking_id": "ITEM-9412", "field": "item_status", "expected": "returned"},
            {"booking_id": "ITEM-9412", "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": "ITEM-9412", "field": "return_label_issued", "expected": True},
            {"booking_id": "ITEM-9410", "field": "item_status", "expected": "delivered"},
            {"booking_id": "ITEM-9411", "field": "item_status", "expected": "delivered"},
        ],
        "_failure_traps": ["Agent doesn't ask clarifying questions", "Agent processes return for all items"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="edge_case",
        replay_steps=["get_order", "get_policies(return)", "process_return(preview)", "process_return(confirm)"],
        policy_results={
            "no_action": False,
            "agent_must": "diagnose the issue through questions, identify the wrong item (blender instead of phone case), and process return for the wrong item",
        },
        scenario=task_data["scenario_template"],
    )
    return [shirt, novel, blender], [order], items, [], task_data


def scenario_edge_changes_mind(
    task_id: str = "edge_changes_mind",
    customer_id: str = "cust_003",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Customer starts wanting exchange, mid-conversation switches to return."""
    headphones = build_product("wireless_headphones", product_id="PROD-2415")
    premium = build_product("wireless_headphones_premium", product_id="PROD-2416")

    order = build_order(customer_id=customer_id, order_id="ORD-6051", delivery_date="2026-06-05T14:00:00")
    item = build_order_item(order.order_id, headphones, item_id="ITEM-9415")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=headphones.price,
        return_reason="changed_mind",
        category=headphones.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order.subtotal,
        membership_tier="gold",
        is_gift_return=False,
        current_product_price=None,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "edge_case",
        "description": "Customer initially wants exchange for premium headphones, then changes mind and wants a full return instead.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "I want to exchange my headphones from order ORD-6051 for the premium model.",
        "user_simulator": {
            "prompt": (
                "You bought SoundMax headphones in ORD-6051. Initially you want to exchange for "
                "the premium model. But after hearing the price difference, you change your mind "
                "and just want a refund instead.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. First ask about exchanging for premium model.\n"
                "3. When told the price difference ($100), say 'Actually, never mind. Just return them for a refund.'\n"
                "4. Accept the return terms.\n5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6051", "item": "headphones"},
            "_unknown_info": ["exchange price difference", "return refund amount"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": item.item_id, "field": "restocking_fee", "expected": refund["restocking_fee"]},
        ],
        "_failure_traps": [
            "Agent processes exchange after customer switched to return",
            "Agent can't handle the pivot",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="edge_case",
        replay_steps=[
            "get_order",
            "get_policies(exchange)",
            "get_policies(return)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results={
            "no_action": False,
            "agent_must": "handle customer pivot from exchange to return, check return policy, process return with restocking fee ($37 for gold member on electronics)",
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones, premium], [order], [item], [], task_data


SCENARIOS = [
    scenario_edge_wrong_order_id,
    scenario_edge_signature_conflict,
    scenario_edge_all_windows_expired,
    scenario_edge_vague_complaint,
    scenario_edge_changes_mind,
]
