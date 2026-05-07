"""Customer-support return and refund scenarios."""


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


def scenario_return_partial_order(
    task_id: str = "return_partial_order",
    customer_id: str = "cust_002",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Return 1 of 3 items from order with SAVE20 promo code.

    Agent must compute proportional discount redistribution.
    Headphones $249, case $35, book $24 = $308 subtotal. Discount $66.
    Refund = 249 - restocking(37) - discount_adj(53) = 159.
    """
    headphones = build_product("wireless_headphones", product_id="PROD-2001")
    phone_case = build_product("phone_case", product_id="PROD-2002")
    novel = build_product("novel", product_id="PROD-2003")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6001",
        order_date="2026-05-28T10:00:00",
        delivery_date="2026-06-02T14:00:00",
        discount_code="SAVE20",
        discount_amount=66,
    )

    item_headphones = build_order_item(order.order_id, headphones, item_id="ITEM-9001")
    item_case = build_order_item(order.order_id, phone_case, item_id="ITEM-9002")
    item_novel = build_order_item(order.order_id, novel, item_id="ITEM-9003")
    items = [item_headphones, item_case, item_novel]
    finalize_order(order, items)

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
        "description": "Return headphones from a 3-item order that had a SAVE20 promo code. Compute correct partial refund with discount redistribution.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": "ITEM-9001",
        },
        "opening_message": "Hi, I'd like to return the headphones from my recent order ORD-6001. I changed my mind about them.",
        "user_simulator": {
            "prompt": (
                "You placed order ORD-6001 which had wireless headphones, a phone case, and a book. "
                "You used a SAVE20 promo code. You want to return the headphones (changed your mind).\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give the order ID when asked.\n"
                "2. Confirm you want to return the headphones specifically.\n"
                "3. You do NOT know the exact refund amount — ask the agent.\n"
                "4. Accept the refund terms after seeing the preview.\n"
                "5. If the agent mentions a restocking fee or discount adjustment, ask for clarification.\n"
                "6. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6001", "item": "wireless headphones", "reason": "changed mind"},
            "_unknown_info": ["refund amount", "discount redistribution rules", "restocking fee"],
        },
        "db_assertions": [
            {"booking_id": "ITEM-9001", "field": "item_status", "expected": "returned"},
            {"booking_id": "ITEM-9001", "field": "return_reason", "expected": "changed_mind"},
            {"booking_id": "ITEM-9001", "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": "ITEM-9001", "field": "refund_method", "expected": refund["refund_method"]},
            {"booking_id": "ITEM-9001", "field": "restocking_fee", "expected": refund["restocking_fee"]},
            {"booking_id": "ITEM-9001", "field": "return_label_issued", "expected": False},
            {"booking_id": "ITEM-9002", "field": "item_status", "expected": "delivered"},
            {"booking_id": "ITEM-9003", "field": "item_status", "expected": "delivered"},
            {"booking_id": order.order_id, "field": "status", "expected": "partially_returned"},
        ],
        "_failure_traps": [
            "Agent returns without checking policies first",
            "Agent doesn't preview before confirming",
            "Agent calculates refund without accounting for promo discount redistribution",
            "Agent returns the wrong item",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_policies(return)",
            "get_policies(refund)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results=refund,
        scenario=task_data["scenario_template"],
    )
    return [headphones, phone_case, novel], [order], items, [], task_data


def scenario_return_defective_electronics(
    task_id: str = "return_defective_electronics",
    customer_id: str = "cust_004",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Defective laptop within warranty. Full refund, no restocking, free return label."""
    laptop = build_product("laptop_pro", product_id="PROD-2050")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6006",
        order_date="2026-05-20T10:00:00",
        delivery_date="2026-05-25T14:00:00",
    )
    item = build_order_item(order.order_id, laptop, item_id="ITEM-9050")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=laptop.price,
        return_reason="defective",
        category=laptop.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=None,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": "Return a defective laptop. Full refund, no restocking fee, free return shipping label.",
        "complexity": "medium",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "My laptop from order ORD-6006 has a defective screen — it flickers constantly. I'd like to return it.",
        "user_simulator": {
            "prompt": (
                "You bought a ProBook Laptop in order ORD-6006. The screen flickers — it's defective. "
                "You want a full return and refund.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Describe the defect: screen flickering.\n"
                "3. Confirm you want a return, not a warranty repair.\n4. Accept the refund terms.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6006", "item": "ProBook Laptop", "defect": "screen flickering"},
            "_unknown_info": ["refund amount", "return label process"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "return_reason", "expected": "defective"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": item.item_id, "field": "refund_method", "expected": refund["refund_method"]},
            {"booking_id": item.item_id, "field": "restocking_fee", "expected": 0},
            {"booking_id": item.item_id, "field": "return_label_issued", "expected": True},
            {"booking_id": order.order_id, "field": "status", "expected": "fully_returned"},
        ],
        "_failure_traps": ["Agent applies restocking fee to defective item", "Agent doesn't provide free return label"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results=refund,
        scenario=task_data["scenario_template"],
    )
    return [laptop], [order], [item], [], task_data


def scenario_return_outside_window(
    task_id: str = "return_outside_window",
    customer_id: str = "cust_002",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Headphones 20 days after delivery. Electronics 15-day window → store credit only (within 30-day store credit window)."""
    headphones = build_product("wireless_headphones", product_id="PROD-2055")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6007",
        order_date="2026-05-15T10:00:00",
        delivery_date="2026-05-23T14:00:00",  # 20 days before now
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-9055")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=headphones.price,
        return_reason="changed_mind",
        category=headphones.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=None,
        store_credit_only=True,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": "Return headphones 20 days after delivery (electronics 15-day window). Store credit only — outside window but within extended store credit period.",
        "complexity": "medium",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "I'd like to return the headphones from order ORD-6007. I just haven't been using them.",
        "user_simulator": {
            "prompt": (
                "You bought SoundMax Wireless Headphones in order ORD-6007. You want to return them "
                "(changed mind). You don't know the return window has passed.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. You do NOT know the return window has passed.\n"
                "3. If told about store credit only, ask why no cash refund.\n"
                "4. Accept store credit after explanation.\n5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6007", "item": "headphones", "reason": "changed mind"},
            "_unknown_info": ["return window status", "store credit only policy"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "return_reason", "expected": "changed_mind"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": item.item_id, "field": "refund_method", "expected": "store_credit"},
            {"booking_id": item.item_id, "field": "restocking_fee", "expected": refund["restocking_fee"]},
            {"booking_id": item.item_id, "field": "return_label_issued", "expected": False},
            {"booking_id": order.order_id, "field": "status", "expected": "fully_returned"},
        ],
        "_failure_traps": [
            "Agent refunds to original payment (should be store credit)",
            "Agent denies return entirely",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results={**refund, "store_credit_only": True},
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_return_promo_recalculation(
    task_id: str = "return_promo_recalculation",
    customer_id: str = "cust_003",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Return 1 of 3 items with 15% OFF promo. Different items/amounts from return_partial_order."""
    blender = build_product("blender", product_id="PROD-2060")
    shirt = build_product("cotton_shirt", product_id="PROD-2061")
    novel = build_product("novel", product_id="PROD-2062")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6008",
        order_date="2026-06-01T10:00:00",
        delivery_date="2026-06-05T14:00:00",
        discount_code="SAVE15",
        discount_amount=25,
    )
    items = [
        build_order_item(order.order_id, blender, item_id="ITEM-9060"),
        build_order_item(order.order_id, shirt, item_id="ITEM-9061"),
        build_order_item(order.order_id, novel, item_id="ITEM-9062"),
    ]
    finalize_order(order, items)

    refund = policies.calculate_refund(
        item_price=blender.price,
        return_reason="changed_mind",
        category=blender.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=None,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": "Return blender from 3-item order with SAVE15 promo. Agent must compute refund with proportional discount redistribution.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": "ITEM-9060",
        },
        "opening_message": "Hi, I want to return the blender from my order ORD-6008. I already have one.",
        "user_simulator": {
            "prompt": (
                "You placed order ORD-6008 with a blender, shirt, and book. Used SAVE15 promo. "
                "You want to return the blender.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Confirm you want to return the blender.\n"
                "3. You do NOT know the refund amount.\n4. Accept refund terms after preview.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6008", "item": "blender", "reason": "already have one"},
            "_unknown_info": ["refund amount", "promo redistribution"],
        },
        "db_assertions": [
            {"booking_id": "ITEM-9060", "field": "item_status", "expected": "returned"},
            {"booking_id": "ITEM-9060", "field": "return_reason", "expected": "changed_mind"},
            {"booking_id": "ITEM-9060", "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": "ITEM-9060", "field": "refund_method", "expected": refund["refund_method"]},
            {"booking_id": "ITEM-9060", "field": "restocking_fee", "expected": refund["restocking_fee"]},
            {"booking_id": "ITEM-9060", "field": "return_label_issued", "expected": False},
            {"booking_id": "ITEM-9061", "field": "item_status", "expected": "delivered"},
            {"booking_id": "ITEM-9062", "field": "item_status", "expected": "delivered"},
            {"booking_id": order.order_id, "field": "status", "expected": "partially_returned"},
        ],
        "_failure_traps": ["Agent ignores promo redistribution", "Agent returns wrong item"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_policies(return)",
            "get_policies(refund)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results=refund,
        scenario=task_data["scenario_template"],
    )
    return [blender, shirt, novel], [order], items, [], task_data


def scenario_return_gift(
    task_id: str = "return_gift",
    customer_id: str = "cust_003",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Gift return. Store credit at current (sale) price, not original."""
    headphones = build_product("wireless_headphones", product_id="PROD-2065", current_price=199)
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6009",
        order_date="2026-05-20T10:00:00",
        delivery_date="2026-05-25T14:00:00",
        is_gift=True,
        gift_sender="Uncle Bob",
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-9065")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=headphones.price,
        return_reason="changed_mind",
        category=headphones.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=True,
        current_product_price=headphones.current_price,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": "Gift return — no receipt. Refund as store credit at current (sale) price of $199, not original $249.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "I received headphones as a gift from order ORD-6009 and I'd like to return them.",
        "user_simulator": {
            "prompt": (
                "You received SoundMax headphones as a gift from Uncle Bob (order ORD-6009). "
                "You want to return them — you already have headphones.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Mention it's a gift when asked.\n2. You know the order ID from the gift receipt.\n"
                "3. You do NOT know the refund will be store credit at sale price.\n"
                "4. Accept store credit after explanation.\n5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6009", "item": "headphones", "gift": "from Uncle Bob"},
            "_unknown_info": ["refund method (store credit)", "refund amount (current sale price)"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "return_reason", "expected": "changed_mind"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": item.item_id, "field": "refund_method", "expected": "store_credit"},
            {"booking_id": item.item_id, "field": "restocking_fee", "expected": refund["restocking_fee"]},
            {"booking_id": item.item_id, "field": "return_label_issued", "expected": False},
            {"booking_id": order.order_id, "field": "status", "expected": "fully_returned"},
        ],
        "_failure_traps": [
            "Agent refunds original price instead of current sale price",
            "Agent refunds to credit card instead of store credit",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_policies(return)",
            "get_policies(refund)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results={**refund, "is_gift_return": True},
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_return_wrong_item(
    task_id: str = "return_wrong_item",
    customer_id: str = "cust_002",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Customer ordered laptop but received blender. Free return + replacement."""
    laptop = build_product("laptop_pro", product_id="PROD-2070")
    blender = build_product("blender", product_id="PROD-2071")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6010",
        order_date="2026-06-01T10:00:00",
        delivery_date="2026-06-05T14:00:00",
    )
    item = build_order_item(order.order_id, laptop, item_id="ITEM-9070")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=laptop.price,
        return_reason="wrong_item",
        category=laptop.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=None,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": "Customer ordered laptop but received blender. Wrong item shipped — free return, full refund, replacement.",
        "complexity": "medium",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "I ordered a laptop from order ORD-6010 but I received a blender instead! This is not what I ordered.",
        "user_simulator": {
            "prompt": (
                "You ordered a ProBook Laptop in ORD-6010 but received a blender. "
                "You want a return and full refund so you can reorder the correct item.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Describe what you received (blender) vs what you ordered (laptop).\n"
                "3. You want a return and refund — you'll reorder the laptop separately.\n4. Accept the return process.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6010", "ordered": "laptop", "received": "blender"},
            "_unknown_info": ["return process for wrong item", "refund amount"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "return_reason", "expected": "wrong_item"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": item.item_id, "field": "refund_method", "expected": refund["refund_method"]},
            {"booking_id": item.item_id, "field": "restocking_fee", "expected": refund["restocking_fee"]},
            {"booking_id": item.item_id, "field": "return_label_issued", "expected": True},
            {"booking_id": order.order_id, "field": "status", "expected": "fully_returned"},
        ],
        "_failure_traps": ["Agent charges restocking fee for wrong item", "Agent doesn't provide free return label"],
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
    return [laptop, blender], [order], [item], [], task_data


def scenario_return_restocking_waived(
    task_id: str = "return_restocking_waived",
    customer_id: str = "cust_001",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Opened electronics return. Normally 15% restocking, but platinum member → waived."""
    headphones = build_product("wireless_headphones", product_id="PROD-2075")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6011",
        order_date="2026-06-01T10:00:00",
        delivery_date="2026-06-05T14:00:00",
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-9075")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=headphones.price,
        return_reason="changed_mind",
        category=headphones.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order.subtotal,
        membership_tier="platinum",
        is_gift_return=False,
        current_product_price=None,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": "Opened headphones return with changed_mind. Normally 15% restocking for electronics, but platinum member gets it waived.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "I'd like to return my headphones from order ORD-6011. I've opened them but they don't fit my ears well.",
        "user_simulator": {
            "prompt": (
                "You bought SoundMax headphones in ORD-6011. You opened them but they don't fit. "
                "You're a platinum member and expect good service.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Mention you've opened the product.\n"
                "3. If a restocking fee is mentioned, ask if your platinum membership helps.\n"
                "4. Accept the refund terms.\n5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6011", "item": "headphones", "opened": "yes"},
            "_unknown_info": ["restocking fee waiver for platinum", "refund amount"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "return_reason", "expected": "changed_mind"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": item.item_id, "field": "refund_method", "expected": refund["refund_method"]},
            {"booking_id": item.item_id, "field": "restocking_fee", "expected": 0},
            {"booking_id": item.item_id, "field": "return_label_issued", "expected": False},
            {"booking_id": order.order_id, "field": "status", "expected": "fully_returned"},
        ],
        "_failure_traps": ["Agent charges restocking fee to platinum member", "Agent doesn't check customer tier"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results={**refund, "restocking_waived": True},
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_return_high_value(
    task_id: str = "return_high_value",
    customer_id: str = "cust_001",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Return $1299 laptop. High-value return with full verification."""
    laptop = build_product("laptop_pro", product_id="PROD-2080")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6012",
        order_date="2026-06-01T10:00:00",
        delivery_date="2026-06-05T14:00:00",
    )
    item = build_order_item(order.order_id, laptop, item_id="ITEM-9080")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=laptop.price,
        return_reason="changed_mind",
        category=laptop.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order.subtotal,
        membership_tier="platinum",
        is_gift_return=False,
        current_product_price=None,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": "Return $1299 laptop. High-value item, platinum member (restocking waived). Full refund.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "I need to return the laptop from order ORD-6012. I changed my mind — it's more than I need.",
        "user_simulator": {
            "prompt": (
                "You bought a ProBook Laptop ($1299) in ORD-6012. It's not suitable for your needs. "
                "You want to return it.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Explain the laptop doesn't meet your needs.\n"
                "3. Accept the return terms after preview.\n4. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6012", "item": "ProBook Laptop", "reason": "not suitable"},
            "_unknown_info": ["refund amount", "return process"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "return_reason", "expected": "changed_mind"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": item.item_id, "field": "refund_method", "expected": refund["refund_method"]},
            {"booking_id": item.item_id, "field": "restocking_fee", "expected": 0},
            {"booking_id": item.item_id, "field": "return_label_issued", "expected": False},
            {"booking_id": order.order_id, "field": "status", "expected": "fully_returned"},
        ],
        "_failure_traps": ["Agent charges restocking to platinum", "Agent doesn't verify high-value return"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results={**refund, "restocking_waived": True},
        scenario=task_data["scenario_template"],
    )
    return [laptop], [order], [item], [], task_data


def scenario_return_gold_restocking(
    task_id: str = "return_gold_restocking",
    customer_id: str = "cust_003",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Gold member returns opened electronics. Restocking fee APPLIES (only platinum waives)."""
    headphones = build_product("wireless_headphones", product_id="PROD-2085")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6013",
        order_date="2026-06-01T10:00:00",
        delivery_date="2026-06-05T14:00:00",
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-9085")
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
        "task_type": "return_item",
        "description": "Gold member returns opened electronics. 15% restocking fee applies — only platinum gets waiver.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "I want to return headphones from order ORD-6013. I opened them but didn't like the sound quality.",
        "user_simulator": {
            "prompt": (
                "You bought SoundMax headphones in ORD-6013. Opened but didn't like sound. "
                "You're a gold member and hope to avoid the restocking fee.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Mention you're a gold member if restocking fee mentioned.\n"
                "3. Accept the fee after explanation (only platinum waives).\n4. Confirm the return.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6013", "item": "headphones", "membership": "gold"},
            "_unknown_info": ["restocking fee amount", "that only platinum waives it"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "return_reason", "expected": "changed_mind"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": item.item_id, "field": "refund_method", "expected": refund["refund_method"]},
            {"booking_id": item.item_id, "field": "restocking_fee", "expected": refund["restocking_fee"]},
            {"booking_id": item.item_id, "field": "return_label_issued", "expected": False},
            {"booking_id": order.order_id, "field": "status", "expected": "fully_returned"},
        ],
        "_failure_traps": ["Agent waives restocking for gold (only platinum)", "Agent doesn't check customer tier"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results=refund,
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_return_full_order(
    task_id: str = "return_full_order",
    customer_id: str = "cust_005",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Return all 3 items. Full order reversal → fully_returned."""
    shirt = build_product("cotton_shirt", product_id="PROD-2090")
    novel = build_product("novel", product_id="PROD-2091")
    case = build_product("phone_case", product_id="PROD-2092")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6014",
        order_date="2026-06-01T10:00:00",
        delivery_date="2026-06-05T14:00:00",
    )
    items = [
        build_order_item(order.order_id, shirt, item_id="ITEM-9090"),
        build_order_item(order.order_id, novel, item_id="ITEM-9091"),
        build_order_item(order.order_id, case, item_id="ITEM-9092"),
    ]
    finalize_order(order, items)

    # Compute refund for each item
    refunds = {}
    for item, prod in zip(items, [shirt, novel, case]):
        r = policies.calculate_refund(
            item_price=prod.price,
            return_reason="changed_mind",
            category=prod.category,
            discount_code=None,
            discount_amount=0,
            order_subtotal=order.subtotal,
            membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
            is_gift_return=False,
            current_product_price=None,
        )
        refunds[item.item_id] = r

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": "Return all 3 items from order. Full order reversal resulting in fully_returned status.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": "ITEM-9090",
        },
        "opening_message": "I want to return everything from order ORD-6014. The shirt, book, and phone case — all of it.",
        "user_simulator": {
            "prompt": (
                "You placed order ORD-6014 with a shirt, book, and phone case. "
                "You want to return ALL items. Changed your mind about the whole order.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Confirm you want ALL items returned.\n"
                "3. Accept the refund terms for each item.\n4. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6014", "items": "shirt, book, phone case", "reason": "changed mind"},
            "_unknown_info": ["individual refund amounts", "return process for multiple items"],
        },
        "db_assertions": [
            {"booking_id": "ITEM-9090", "field": "item_status", "expected": "returned"},
            {"booking_id": "ITEM-9090", "field": "return_reason", "expected": "changed_mind"},
            {"booking_id": "ITEM-9091", "field": "item_status", "expected": "returned"},
            {"booking_id": "ITEM-9092", "field": "item_status", "expected": "returned"},
            {"booking_id": "ITEM-9090", "field": "refund_amount", "expected": refunds["ITEM-9090"]["refund_amount"]},
            {"booking_id": "ITEM-9090", "field": "refund_method", "expected": refunds["ITEM-9090"]["refund_method"]},
            {"booking_id": "ITEM-9091", "field": "refund_amount", "expected": refunds["ITEM-9091"]["refund_amount"]},
            {"booking_id": "ITEM-9092", "field": "refund_amount", "expected": refunds["ITEM-9092"]["refund_amount"]},
            {"booking_id": "ITEM-9090", "field": "return_label_issued", "expected": False},
            {"booking_id": "ITEM-9090", "field": "restocking_fee", "expected": refunds["ITEM-9090"]["restocking_fee"]},
            {"booking_id": order.order_id, "field": "status", "expected": "fully_returned"},
        ],
        "_failure_traps": ["Agent only returns some items", "Agent doesn't achieve fully_returned status"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_policies(return)",
            "process_return(preview)",
            "process_return(confirm)",
            "process_return(preview)",
            "process_return(confirm)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results=refunds.get("ITEM-9090", {}),
        scenario=task_data["scenario_template"],
    )
    return [shirt, novel, case], [order], items, [], task_data


SCENARIOS = [
    scenario_return_partial_order,
    scenario_return_defective_electronics,
    scenario_return_outside_window,
    scenario_return_promo_recalculation,
    scenario_return_gift,
    scenario_return_wrong_item,
    scenario_return_restocking_waived,
    scenario_return_high_value,
    scenario_return_gold_restocking,
    scenario_return_full_order,
]
