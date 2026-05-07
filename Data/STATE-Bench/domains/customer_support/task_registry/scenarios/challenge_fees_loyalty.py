"""Customer-support challenge scenarios focused on fees, tier perks, and credits."""


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


def scenario_challenge_free_shipping_clawback(
    task_id: str = "challenge_free_shipping_clawback",
    customer_id: str = "cust_002",  # Standard
    now: str = "2026-06-20T10:00:00",
) -> ScenarioResult:
    """Return from free-shipping order drops subtotal below threshold → shipping clawback."""
    blender = build_product("blender", product_id="PROD-3110")
    shirt = build_product("cotton_shirt", product_id="PROD-3111")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7099",
        order_date="2026-06-05T10:00:00",
        delivery_date="2026-06-10T14:00:00",
        shipping_cost=0,  # Free shipping (subtotal $148 = $89 + $59 >= $100)
    )
    item_b = build_order_item(order.order_id, blender, item_id="ITEM-10110")
    item_s = build_order_item(order.order_id, shirt, item_id="ITEM-10111")
    finalize_order(order, [item_b, item_s])
    assert order.subtotal >= 100, f"Setup error: subtotal {order.subtotal} should be >= 100"

    # Return blender (changed_mind)
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

    # Check shipping clawback
    clawback = policies.calculate_shipping_clawback(
        order_subtotal=order.subtotal,
        return_item_price=blender.price,
        shipping_cost=8,  # Standard shipping would have been $8
        original_free_shipping=True,
    )
    assert clawback["applies"], f"Setup error: shipping clawback should apply, got {clawback}"

    # Net refund = item refund - shipping clawback
    net_refund = refund["refund_amount"] - clawback["clawback_amount"]

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            f"Standard customer returns blender ($89) from 2-item order (subtotal $148, free shipping). "
            f"Return drops remaining to $59 (below $100 threshold). "
            f"Must deduct $8 shipping clawback. Net refund: ${net_refund}."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item_b.item_id,
        },
        "opening_message": (
            "Hi, I'd like to return the blender from order ORD-7099. I changed my mind about it."
        ),
        "user_simulator": {
            "prompt": (
                "You placed order ORD-7099 for a blender ($89) and a shirt ($59). "
                "You want to return the blender (changed your mind). "
                "You are a Standard member.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID when asked.\n"
                "2. Confirm you want to return the blender.\n"
                "3. Accept whatever refund amount the agent offers.\n"
                "4. If the agent mentions a shipping deduction, ask why but accept it.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-7099",
                "item_to_return": "blender",
                "reason": "changed mind",
            },
            "_unknown_info": ["refund amount", "shipping clawback policy"],
        },
        "db_assertions": [
            {"booking_id": item_b.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_b.item_id, "field": "return_reason", "expected": "changed_mind"},
        ],
        "_failure_traps": [
            "Agent returns the blender with full $89 refund without checking free shipping threshold",
            "Agent doesn't know about the free_shipping clawback policy",
            f"Agent doesn't deduct ${clawback['clawback_amount']} shipping cost from the return refund",
            "Agent issues refund without mentioning the shipping cost deduction",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
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
                f"Return blender: refund ${refund['refund_amount']}.",
                f"Free shipping clawback: remaining subtotal ${order.subtotal - blender.price} < $100 threshold.",
                f"Deduct ${clawback['clawback_amount']} original shipping cost via separate process_refund.",
                f"Net customer receives: ${net_refund}.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [blender, shirt], [order], [item_b, item_s], [], task_data


def scenario_challenge_repeat_category_return(
    task_id: str = "challenge_repeat_category_return",
    customer_id: str = "cust_003",  # Gold
    now: str = "2026-06-20T10:00:00",
) -> ScenarioResult:
    """Return 2 clothing items from same order — second gets $5 surcharge."""
    shirt1 = build_product("cotton_shirt", product_id="PROD-3112")
    shirt2 = build_product("cotton_shirt_large", product_id="PROD-3113")
    shoes = build_product("running_shoes", product_id="PROD-3114")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7100",
        order_date="2026-06-05T10:00:00",
        delivery_date="2026-06-10T14:00:00",
    )
    item_s1 = build_order_item(order.order_id, shirt1, item_id="ITEM-10112")
    item_s2 = build_order_item(order.order_id, shirt2, item_id="ITEM-10113")
    item_sh = build_order_item(order.order_id, shoes, item_id="ITEM-10114")
    finalize_order(order, [item_s1, item_s2, item_sh])

    # First shirt return — no surcharge
    refund1 = policies.calculate_refund(
        item_price=shirt1.price,
        return_reason="changed_mind",
        category=shirt1.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=shirt1.current_price,
    )

    # Second shirt return — $5 surcharge (same category)
    refund2 = policies.calculate_refund(
        item_price=shirt2.price,
        return_reason="changed_mind",
        category=shirt2.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=shirt2.current_price,
    )

    surcharge = policies.calculate_repeat_return_surcharge(
        return_category="clothing",
        already_returned_categories=["clothing"],
    )
    assert surcharge["applies"], f"Setup error: surcharge should apply, got {surcharge}"

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": (
            f"Gold customer returns 2 clothing items from same order. "
            f"First shirt: refund ${refund1['refund_amount']}. "
            f"Second shirt (Large): refund ${refund2['refund_amount']} minus ${surcharge['surcharge']} "
            f"same-category surcharge = ${refund2['refund_amount'] - surcharge['surcharge']}. "
            f"Agent must discover repeat_return policy and apply surcharge."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_ids": [item_s1.item_id, item_s2.item_id],
        },
        "opening_message": (
            "Hi, I bought three things from order ORD-7100 but I'd like to return both shirts. "
            "The regular one and the large one don't fit. I'm keeping the running shoes though."
        ),
        "user_simulator": {
            "prompt": (
                "You placed order ORD-7100 for 2 cotton shirts and running shoes. "
                "You want to return BOTH shirts (changed mind — wrong sizes). Keeping the shoes.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID when asked.\n"
                "2. Confirm you want to return both shirts.\n"
                "3. Accept any fees or surcharges without complaint.\n"
                "4. If agent only processes one return, remind them about the second shirt.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-7100",
                "items_to_return": "both cotton shirts",
                "reason": "changed mind (wrong sizes)",
            },
            "_unknown_info": ["refund amounts", "repeat return surcharge"],
        },
        "db_assertions": [
            {"booking_id": item_s1.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_s2.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_s1.item_id, "field": "return_reason", "expected": "changed_mind"},
            {"booking_id": item_s2.item_id, "field": "return_reason", "expected": "changed_mind"},
        ],
        "_failure_traps": [
            "Agent returns both shirts without checking repeat_return policy",
            "Agent doesn't know about the same-category repeat return surcharge",
            f"Agent doesn't deduct ${surcharge['surcharge']} surcharge from the second shirt's refund",
            "Agent only returns one shirt",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(repeat_return)",
            "get_policies(refund)",
            "process_return(preview, shirt1)",
            "process_return(confirm, shirt1)",
            "process_return(preview, shirt2)",
            "process_return(confirm, shirt2)",
            "process_refund(preview, surcharge)",
            "process_refund(confirm, surcharge)",
        ],
        policy_results={
            "phases": [
                f"Return shirt 1: refund ${refund1['refund_amount']}.",
                f"Return shirt 2 (Large): refund ${refund2['refund_amount']}.",
                f"Same-category surcharge: ${surcharge['surcharge']} on 2nd clothing return — deducted via process_refund.",
                f"Net for shirt 2: ${refund2['refund_amount'] - surcharge['surcharge']}.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [shirt1, shirt2, shoes], [order], [item_s1, item_s2, item_sh], [], task_data


def scenario_challenge_bulk_plus_shipping_clawback(
    task_id: str = "challenge_bulk_plus_shipping_clawback",
    customer_id: str = "cust_002",  # Standard
    now: str = "2026-06-20T10:00:00",
) -> ScenarioResult:
    """Return 2 of 4 items from discounted free-shipping order. Double clawback."""
    blender = build_product("blender", product_id="PROD-3115")  # $89
    shirt = build_product("cotton_shirt", product_id="PROD-3116")  # $59
    case = build_product("phone_case", product_id="PROD-3117")  # $35
    novel = build_product("novel", product_id="PROD-3118")  # $24
    # subtotal = 89 + 59 + 35 + 24 = 207. Free shipping (> $100).
    # Return blender ($89) + shirt ($59). Remaining: case ($35) + novel ($24) = $59.
    # Remaining count: 2 (< 3 bulk threshold). Remaining subtotal: $59 (< $100 shipping threshold).

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7101",
        order_date="2026-06-05T10:00:00",
        delivery_date="2026-06-10T14:00:00",
        shipping_cost=0,  # Free shipping
        discount_code="BUNDLE15",
        discount_amount=15,
    )
    item_b = build_order_item(order.order_id, blender, item_id="ITEM-10115")
    item_s = build_order_item(order.order_id, shirt, item_id="ITEM-10116")
    item_c = build_order_item(order.order_id, case, item_id="ITEM-10117")
    item_n = build_order_item(order.order_id, novel, item_id="ITEM-10118")
    items = [item_b, item_s, item_c, item_n]
    finalize_order(order, items)
    assert order.subtotal >= 100, f"Setup error: subtotal {order.subtotal} should be >= 100"

    # Bulk clawback: 4 items → 2, with discount code
    bulk = policies.calculate_bulk_clawback(
        original_item_count=4,
        items_being_returned=2,
        remaining_item_count=2,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
    )
    assert bulk["applies"], f"Setup error: bulk clawback should apply, got {bulk}"

    # Free shipping clawback
    remaining_subtotal = case.price + novel.price  # $35 + $24 = $59
    shipping = policies.calculate_shipping_clawback(
        order_subtotal=order.subtotal,
        return_item_price=blender.price + shirt.price,  # total being returned
        shipping_cost=8,  # standard shipping
        original_free_shipping=True,
    )
    assert shipping["applies"], f"Setup error: shipping clawback should apply, got {shipping}"

    # Refunds for returned items
    refund_b = policies.calculate_refund(
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

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": (
            f"Standard customer returns blender ($89) and shirt ($59) from 4-item discounted "
            f"free-shipping order (subtotal ${order.subtotal}). Remaining: case + novel = ${remaining_subtotal}. "
            f"Triggers both: bulk clawback ${bulk['clawback_amount']} (drops below 3 items) "
            f"AND shipping clawback ${shipping['clawback_amount']} (drops below $100). "
            f"Agent must discover and apply both."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_ids": [item_b.item_id, item_s.item_id],
        },
        "opening_message": (
            "Hi, I want to return the blender and the cotton shirt from order ORD-7101. "
            "I changed my mind on both of them."
        ),
        "user_simulator": {
            "prompt": (
                "You placed order ORD-7101 for a blender, shirt, phone case, and book "
                "with a BUNDLE15 discount code. You want to return the blender and shirt.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID when asked.\n"
                "2. Confirm you want to return both the blender and shirt.\n"
                "3. Accept any fees or deductions without complaint.\n"
                "4. If agent only returns one item, ask about the second.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-7101",
                "items_to_return": "blender and cotton shirt",
                "reason": "changed mind",
            },
            "_unknown_info": ["refund amounts", "bulk clawback", "shipping clawback"],
        },
        "db_assertions": [
            {"booking_id": item_b.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_s.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": [
            "Agent returns both items without checking bulk discount or free shipping policies",
            f"Agent doesn't apply ${bulk['clawback_amount']} bulk discount clawback",
            f"Agent doesn't apply ${shipping['clawback_amount']} free shipping clawback",
            "Agent only processes one of the two returns",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(return)",
            "get_policies(bulk_discount)",
            "get_policies(free_shipping)",
            "get_policies(refund)",
            "process_return(preview, blender)",
            "process_return(confirm, blender)",
            "process_return(preview, shirt)",
            "process_return(confirm, shirt)",
            "process_refund(preview, bulk_clawback)",
            "process_refund(confirm, bulk_clawback)",
            "process_refund(preview, shipping_clawback)",
            "process_refund(confirm, shipping_clawback)",
        ],
        policy_results={
            "phases": [
                f"Return blender: refund ${refund_b['refund_amount']} (with promo adj of ${refund_b['discount_adjustment']}).",
                f"Return shirt: refund ${refund_s['refund_amount']}.",
                f"Bulk clawback: ${bulk['clawback_amount']} (remaining 2 items < 3-item threshold).",
                f"Free shipping clawback: ${shipping['clawback_amount']} (remaining ${remaining_subtotal} < $100).",
                "Both clawbacks must be applied via separate process_refund calls.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [blender, shirt, case, novel], [order], items, [], task_data


def scenario_challenge_gold_restocking_discount(
    task_id: str = "challenge_gold_restocking_discount",
    customer_id: str = "cust_003",  # Gold + Prime
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Gold member returns laptop — restocking fee charged but deserves 50% discount."""
    laptop = build_product("laptop_pro", product_id="PROD-3119")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7102",
        order_date="2026-06-01T10:00:00",
        delivery_date="2026-06-05T14:00:00",
    )
    item = build_order_item(order.order_id, laptop, item_id="ITEM-10119")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=laptop.price,
        return_reason="changed_mind",
        category=laptop.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=laptop.current_price,
    )
    assert refund["restocking_fee"] > 0, f"Setup error: restocking should apply, got {refund}"

    restock_discount = policies.calculate_restocking_discount(
        restocking_fee=refund["restocking_fee"],
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
    )
    assert restock_discount["applies"], f"Setup error: discount should apply, got {restock_discount}"

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            f"Gold member returns laptop (changed_mind). Restocking fee: ${refund['restocking_fee']}. "
            f"Gold gets {restock_discount['discount_pct']}% off = ${restock_discount['discount']} credit. "
            f"Agent must process return AND issue restocking discount credit via process_refund."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": (
            "Hi, I'd like to return the ProBook Laptop from order ORD-7102. I changed my mind about it."
        ),
        "user_simulator": {
            "prompt": (
                "You bought a ProBook Laptop ($1299) from order ORD-7102. You want to return it "
                "(changed mind). You're a Gold member with Prime shipping.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID when asked.\n"
                "2. If agent mentions restocking fee, ask if your Gold membership gets any discount on it.\n"
                "3. Accept the return terms after seeing the preview.\n"
                "4. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7102", "item": "ProBook Laptop", "reason": "changed mind"},
            "_unknown_info": ["restocking fee amount", "restocking discount for Gold"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "return_reason", "expected": "changed_mind"},
            {"booking_id": item.item_id, "field": "restocking_fee", "expected": refund["restocking_fee"]},
        ],
        "_failure_traps": [
            "Agent charges full restocking fee without checking for Gold tier discount",
            "Agent doesn't know about the restocking_discount policy",
            f"Agent doesn't issue ${restock_discount['discount']} credit via process_refund",
            "Agent waives the restocking fee entirely (only Platinum gets full waiver)",
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
            "process_return(preview)",
            "process_return(confirm)",
            "process_refund(preview, restocking_credit)",
            "process_refund(confirm, restocking_credit)",
        ],
        policy_results={
            **refund,
            "phases": [
                f"Return laptop: refund ${refund['refund_amount']} with ${refund['restocking_fee']} restocking fee.",
                f"Gold restocking discount: {restock_discount['discount_pct']}% off = ${restock_discount['discount']} credit via process_refund.",
                f"Net: customer receives ${refund['refund_amount']} + ${restock_discount['discount']} = ${refund['refund_amount'] + restock_discount['discount']}.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [laptop], [order], [item], [], task_data


def scenario_challenge_promo_bulk_repeat(
    task_id: str = "challenge_promo_bulk_repeat",
    customer_id: str = "cust_002",  # Standard
    now: str = "2026-06-20T10:00:00",
) -> ScenarioResult:
    """Return 2 clothing from 4-item promo order. Promo adj + bulk + repeat."""
    shirt1 = build_product("cotton_shirt", product_id="PROD-3124")
    shirt2 = build_product("cotton_shirt_large", product_id="PROD-3125")
    blender = build_product("blender", product_id="PROD-3126")
    case = build_product("phone_case", product_id="PROD-3127")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7105",
        order_date="2026-06-05T10:00:00",
        delivery_date="2026-06-10T14:00:00",
        discount_code="SPRING20",
        discount_amount=20,
    )
    item_s1 = build_order_item(order.order_id, shirt1, item_id="ITEM-10124")
    item_s2 = build_order_item(order.order_id, shirt2, item_id="ITEM-10125")
    item_b = build_order_item(order.order_id, blender, item_id="ITEM-10126")
    item_c = build_order_item(order.order_id, case, item_id="ITEM-10127")
    items = [item_s1, item_s2, item_b, item_c]
    finalize_order(order, items)

    # Bulk clawback: 4→2 items
    bulk = policies.calculate_bulk_clawback(
        original_item_count=4, items_being_returned=2,
        remaining_item_count=2, discount_code=order.discount_code,
        discount_amount=order.discount_amount,
    )
    assert bulk["applies"]

    # Repeat surcharge: 2nd clothing item
    repeat = policies.calculate_repeat_return_surcharge("clothing", ["clothing"])
    assert repeat["applies"]

    # Refunds (promo redistribution is automatic in process_return)
    refund1 = policies.calculate_refund(
        item_price=shirt1.price, return_reason="changed_mind",
        category=shirt1.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=shirt1.current_price,
    )
    refund2 = policies.calculate_refund(
        item_price=shirt2.price, return_reason="changed_mind",
        category=shirt2.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=shirt2.current_price,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": (
            f"Standard customer returns 2 clothing items from 4-item promo order (SPRING20, $20 off). "
            f"Shirt 1: ${refund1['refund_amount']} (promo adj ${refund1['discount_adjustment']}). "
            f"Shirt 2: ${refund2['refund_amount']} (promo adj ${refund2['discount_adjustment']}). "
            f"Bulk clawback: ${bulk['clawback_amount']} (4→2 items). "
            f"Repeat surcharge: ${repeat['surcharge']} (2nd clothing). "
            f"Agent must apply bulk and repeat policies after returns."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_ids": [item_s1.item_id, item_s2.item_id],
        },
        "opening_message": (
            "Hello, I'd like to return both cotton shirts from order ORD-7105. "
            "Neither of them fit properly."
        ),
        "user_simulator": {
            "prompt": (
                "You ordered 4 items (2 shirts, blender, phone case) with SPRING20 discount. "
                "You want to return both shirts (changed mind — wrong sizes). "
                "You are a Standard member.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID when asked.\n"
                "2. Confirm return of both shirts.\n"
                "3. Accept any fees or surcharges.\n"
                "4. If agent only processes one, ask about the second.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7105", "items": "both cotton shirts", "reason": "wrong sizes"},
            "_unknown_info": ["promo adjustment", "bulk clawback", "repeat surcharge"],
        },
        "db_assertions": [
            {"booking_id": item_s1.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_s2.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": [
            f"Agent doesn't apply ${bulk['clawback_amount']} bulk discount clawback",
            f"Agent doesn't apply ${repeat['surcharge']} repeat same-category surcharge",
            "Agent only returns one shirt",
            "Agent doesn't know about bulk_discount or repeat_return policies",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(refund)",
            "get_policies(bulk_discount)", "get_policies(repeat_return)",
            "process_return(preview, shirt1)", "process_return(confirm, shirt1)",
            "process_return(preview, shirt2)", "process_return(confirm, shirt2)",
            "process_refund(preview, bulk_clawback)", "process_refund(confirm, bulk_clawback)",
            "process_refund(preview, repeat_surcharge)", "process_refund(confirm, repeat_surcharge)",
        ],
        policy_results={
            "phases": [
                f"Return shirt 1: ${refund1['refund_amount']} (promo adj ${refund1['discount_adjustment']}).",
                f"Return shirt 2: ${refund2['refund_amount']} (promo adj ${refund2['discount_adjustment']}).",
                f"Bulk clawback: ${bulk['clawback_amount']} (4→2 items, below threshold).",
                f"Repeat surcharge: ${repeat['surcharge']} (2nd clothing return in same order).",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [shirt1, shirt2, blender, case], [order], items, [], task_data


def scenario_challenge_gold_restock_on_promo(
    task_id: str = "challenge_gold_restock_on_promo",
    customer_id: str = "cust_003",  # Gold + Prime
    now: str = "2026-06-15T10:00:00",
) -> ScenarioResult:
    """Gold returns headphones from promo order. Restocking discount needed."""
    headphones = build_product("wireless_headphones", product_id="PROD-3128")
    shirt = build_product("cotton_shirt", product_id="PROD-3129")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7106",
        order_date="2026-06-01T10:00:00",
        delivery_date="2026-06-05T14:00:00",
        discount_code="SAVE10",
        discount_amount=10,
    )
    item_h = build_order_item(order.order_id, headphones, item_id="ITEM-10128")
    item_s = build_order_item(order.order_id, shirt, item_id="ITEM-10129")
    finalize_order(order, [item_h, item_s])

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
    assert refund["restocking_fee"] > 0

    restock_disc = policies.calculate_restocking_discount(
        restocking_fee=refund["restocking_fee"],
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
    )
    assert restock_disc["applies"]

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            f"Gold member returns headphones ($249) from promo order (SAVE10). "
            f"Promo redistribution: -${refund['discount_adjustment']}. Restocking: ${refund['restocking_fee']}. "
            f"Gold restocking discount: ${restock_disc['discount']} credit. "
            f"Agent must issue the credit via process_refund."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item_h.item_id,
        },
        "opening_message": (
            "Hi, I want to return the wireless headphones from order ORD-7106. I changed my mind."
        ),
        "user_simulator": {
            "prompt": (
                "You bought headphones ($249) and a shirt from order ORD-7106 with SAVE10 code. "
                "You want to return the headphones (changed mind). You're a Gold member.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID when asked.\n"
                "2. If restocking fee is mentioned, ask about Gold member discount.\n"
                "3. Accept the return terms.\n"
                "4. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7106", "item": "headphones", "reason": "changed mind"},
            "_unknown_info": ["promo adjustment", "restocking fee", "Gold restocking discount"],
        },
        "db_assertions": [
            {"booking_id": item_h.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_h.item_id, "field": "restocking_fee", "expected": refund["restocking_fee"]},
        ],
        "_failure_traps": [
            f"Agent doesn't issue ${restock_disc['discount']} Gold restocking discount credit",
            "Agent doesn't know about restocking_discount policy topic",
            "Agent waives restocking fee entirely (only Platinum gets waiver)",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(refund)", "get_policies(restocking_discount)",
            "process_return(preview)", "process_return(confirm)",
            "process_refund(preview, restocking_credit)", "process_refund(confirm, restocking_credit)",
        ],
        policy_results={
            **refund,
            "phases": [
                f"Return headphones: ${refund['refund_amount']} (promo adj ${refund['discount_adjustment']}, restocking ${refund['restocking_fee']}).",
                f"Gold restocking discount: ${restock_disc['discount']} credit via process_refund.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones, shirt], [order], [item_h, item_s], [], task_data


def scenario_challenge_plat_no_restock_but_shipping(
    task_id: str = "challenge_plat_no_restock_but_shipping",
    customer_id: str = "cust_001",  # Platinum + Prime
    now: str = "2026-06-20T10:00:00",
) -> ScenarioResult:
    """Platinum returns laptop. No restocking (waived) but shipping clawback."""
    laptop = build_product("laptop_pro", product_id="PROD-3130", price=499)  # cheaper laptop variant
    novel = build_product("novel", product_id="PROD-3131")

    # Override laptop to have lower price for threshold math
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7107",
        order_date="2026-06-05T10:00:00",
        delivery_date="2026-06-08T14:00:00",
        shipping_cost=0,  # Free shipping ($523 > $100)
    )
    item_l = build_order_item(order.order_id, laptop, item_id="ITEM-10130", unit_price=499)
    item_n = build_order_item(order.order_id, novel, item_id="ITEM-10131")
    finalize_order(order, [item_l, item_n])

    refund = policies.calculate_refund(
        item_price=499,
        return_reason="changed_mind",
        category=laptop.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=laptop.current_price,
    )
    # Platinum: restocking waived ($0)
    assert refund["restocking_fee"] == 0, f"Platinum should have 0 restocking, got {refund}"

    shipping_cb = policies.calculate_shipping_clawback(
        order_subtotal=order.subtotal,
        return_item_price=499,
        shipping_cost=12,  # shipping cost
        original_free_shipping=True,
    )
    assert shipping_cb["applies"], f"Setup error: shipping clawback should apply, got {shipping_cb}"

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            f"Platinum returns laptop ($499, changed_mind). Restocking fee waived (Platinum). "
            f"But free-shipping order — return drops subtotal to ${novel.price} < $100. "
            f"Shipping clawback: ${shipping_cb['clawback_amount']}. "
            f"Platinum privilege doesn't exempt from shipping clawback."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item_l.item_id,
        },
        "opening_message": (
            "Hi, I want to return the ProBook Laptop from order ORD-7107. I changed my mind. "
            "As a Platinum member, I believe the restocking fee should be waived."
        ),
        "user_simulator": {
            "prompt": (
                "You bought a laptop ($499) and book from order ORD-7107. Free shipping order. "
                "You want to return the laptop (changed mind). You're Platinum with Prime.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID when asked.\n"
                "2. Mention you expect restocking fee waiver as Platinum.\n"
                "3. Accept any shipping deductions.\n"
                "4. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7107", "item": "laptop", "reason": "changed mind"},
            "_unknown_info": ["shipping clawback policy"],
        },
        "db_assertions": [
            {"booking_id": item_l.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_l.item_id, "field": "restocking_fee", "expected": 0},
        ],
        "_failure_traps": [
            f"Agent doesn't apply ${shipping_cb['clawback_amount']} shipping clawback",
            "Agent assumes Platinum means no deductions at all",
            "Agent doesn't check free_shipping policy",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(refund)", "get_policies(free_shipping)",
            "process_return(preview)", "process_return(confirm)",
            "process_refund(preview, shipping_clawback)", "process_refund(confirm, shipping_clawback)",
        ],
        policy_results={
            **refund,
            "phases": [
                f"Return laptop: ${refund['refund_amount']} (restocking waived for Platinum).",
                f"Free shipping clawback: ${shipping_cb['clawback_amount']} (remaining ${novel.price} < $100).",
                "Platinum waiver only applies to restocking, NOT shipping clawback.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [laptop, novel], [order], [item_l, item_n], [], task_data


def scenario_challenge_seasonal_gold_restocking(
    task_id: str = "challenge_seasonal_gold_restocking",
    customer_id: str = "cust_003",  # Gold + Prime
    now: str = "2027-01-10T10:00:00",
) -> ScenarioResult:
    """Nov order, Gold returns headphones in Jan. Seasonal + restocking discount."""
    headphones = build_product("wireless_headphones", product_id="PROD-3132")
    shirt = build_product("cotton_shirt", product_id="PROD-3133")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7108",
        order_date="2026-12-01T10:00:00",
        delivery_date="2026-12-05T14:00:00",
    )
    item_h = build_order_item(order.order_id, headphones, item_id="ITEM-10132")
    item_s = build_order_item(order.order_id, shirt, item_id="ITEM-10133")
    finalize_order(order, [item_h, item_s])

    refund = policies.calculate_refund(
        item_price=headphones.price, return_reason="changed_mind",
        category=headphones.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=headphones.current_price,
    )

    restock_disc = policies.calculate_restocking_discount(
        restocking_fee=refund["restocking_fee"],
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
    )
    assert restock_disc["applies"], "Setup error: Gold restocking discount should apply"

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            f"Gold+Prime member, Dec order, returns headphones in Jan (seasonal extension). "
            f"Restocking fee ${refund['restocking_fee']} applies. Gold gets ${restock_disc['discount']} off. "
            f"The agent needs to recognize the seasonal extension and issue the restocking-discount credit."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id,
            "order_id": order.order_id, "return_item_id": item_h.item_id,
        },
        "opening_message": (
            "Hi, I'd like to return the wireless headphones from my December order ORD-7108. "
            "I know it's been over a month — is it still possible?"
        ),
        "user_simulator": {
            "prompt": (
                "You ordered headphones ($249) and shirt in December (ORD-7108). "
                "You want to return headphones in January (changed mind). Gold member with Prime.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID when asked.\n"
                "2. If agent says window expired, mention holiday/seasonal extension.\n"
                "3. If restocking fee mentioned, ask about Gold member discount.\n"
                "4. Accept return terms.\n5. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7108", "item": "headphones", "reason": "changed mind"},
            "_unknown_info": ["seasonal extension", "restocking discount"],
        },
        "db_assertions": [
            {"booking_id": item_h.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": [
            "Agent denies return — doesn't check seasonal extension",
            f"Agent doesn't issue ${restock_disc['discount']} restocking discount credit",
            "Agent doesn't know about seasonal or restocking_discount policies",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(seasonal)",
            "get_policies(refund)", "get_policies(restocking_discount)",
            "process_return(preview)", "process_return(confirm)",
            "process_refund(preview, restock_credit)", "process_refund(confirm, restock_credit)",
        ],
        policy_results={
            **refund,
            "phases": [
                "Seasonal extension applies: Dec order → return valid until Jan 31.",
                f"Return headphones: ${refund['refund_amount']} (restocking ${refund['restocking_fee']}).",
                f"Gold restocking discount: ${restock_disc['discount']} credit.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones, shirt], [order], [item_h, item_s], [], task_data


def scenario_challenge_defective_shipping_clawback(
    task_id: str = "challenge_defective_shipping_clawback",
    customer_id: str = "cust_002",  # Standard
    now: str = "2026-06-20T10:00:00",
) -> ScenarioResult:
    """Defective return from free-shipping order. Shipping clawback still applies."""
    blender = build_product("blender", product_id="PROD-3134")
    novel = build_product("novel", product_id="PROD-3135")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7109",
        order_date="2026-06-05T10:00:00",
        delivery_date="2026-06-10T14:00:00",
        shipping_cost=0,  # Free shipping
    )
    item_b = build_order_item(order.order_id, blender, item_id="ITEM-10134")
    item_n = build_order_item(order.order_id, novel, item_id="ITEM-10135")
    finalize_order(order, [item_b, item_n])

    refund = policies.calculate_refund(
        item_price=blender.price, return_reason="defective",
        category=blender.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=blender.current_price,
    )
    assert refund["restocking_fee"] == 0  # Defective: no restocking

    shipping_cb = policies.calculate_shipping_clawback(
        order_subtotal=order.subtotal, return_item_price=blender.price,
        shipping_cost=8, original_free_shipping=True,
    )
    assert shipping_cb["applies"]

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            f"Standard customer returns defective blender ($89) from free-shipping order. "
            f"Defective = full refund, free return label, no restocking. "
            f"BUT return drops subtotal to ${novel.price} < $100 → ${shipping_cb['clawback_amount']} shipping clawback. "
            f"Agent must apply shipping clawback even on defective returns."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id,
            "order_id": order.order_id, "return_item_id": item_b.item_id,
        },
        "opening_message": (
            "The blender from order ORD-7109 is defective — it won't turn on. "
            "I need a full refund."
        ),
        "user_simulator": {
            "prompt": (
                "Your blender ($89) from ORD-7109 is defective. You want a full refund. "
                "Standard member.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID when asked.\n"
                "2. Describe the defect: blender won't power on.\n"
                "3. If any deductions mentioned, ask why (defective should be free).\n"
                "4. Accept if agent explains shipping threshold policy.\n"
                "5. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7109", "item": "blender", "reason": "defective"},
            "_unknown_info": ["shipping clawback"],
        },
        "db_assertions": [
            {"booking_id": item_b.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_b.item_id, "field": "return_reason", "expected": "defective"},
        ],
        "_failure_traps": [
            "Agent issues full refund without shipping clawback (defective ≠ exempt from threshold)",
            f"Agent misses ${shipping_cb['clawback_amount']} shipping clawback",
            "Agent assumes defective returns have zero deductions",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(refund)", "get_policies(free_shipping)",
            "process_return(preview)", "process_return(confirm)",
            "process_refund(preview, shipping_clawback)", "process_refund(confirm, shipping_clawback)",
        ],
        policy_results={
            **refund,
            "phases": [
                f"Defective return: full refund ${refund['refund_amount']}, free return label.",
                f"Free shipping clawback still applies: ${shipping_cb['clawback_amount']} (remaining ${novel.price} < $100).",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [blender, novel], [order], [item_b, item_n], [], task_data


def scenario_challenge_user_error_as_defective(
    task_id: str = "challenge_user_error_as_defective",
    customer_id: str = "cust_004",  # Silver
    now: str = "2026-07-05T10:00:00",
) -> ScenarioResult:
    """Customer claims headphones don't work but it's Bluetooth pairing issue."""
    headphones = build_product("wireless_headphones", product_id="PROD-3137")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7111",
        order_date="2026-06-15T10:00:00",
        delivery_date="2026-06-20T14:00:00",
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-10137")
    finalize_order(order, [item])

    # It's within the 15-day window (15 days since delivery) — barely eligible.
    # If classified as changed_mind: restocking fee applies (electronics).
    # If classified as defective: no restocking, no window restriction.
    refund_correct = policies.calculate_refund(
        item_price=headphones.price, return_reason="changed_mind",
        category=headphones.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=headphones.current_price,
    )
    assert refund_correct["restocking_fee"] > 0  # Changed_mind on electronics

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            f"Silver customer says headphones 'don't work' but describes Bluetooth pairing issue "
            f"(user error, not defective). Correct classification: changed_mind. "
            f"Restocking fee: ${refund_correct['restocking_fee']}. "
            f"Agent likely classifies as defective (no fee) instead of changed_mind (with fee)."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id,
            "order_id": order.order_id, "return_item_id": item.item_id,
        },
        "opening_message": (
            "The wireless headphones from order ORD-7111 don't work. "
            "I've tried everything but they won't connect to my phone."
        ),
        "user_simulator": {
            "prompt": (
                "Your headphones ($249) from ORD-7111 'don't work.' But the real issue is "
                "you can't figure out Bluetooth pairing — you've tried pressing the power "
                "button but haven't held it for 5 seconds to enter pairing mode.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID when asked.\n"
                "2. When asked to describe the issue: 'I press the button and nothing happens "
                "on my phone. No Bluetooth device shows up.'\n"
                "3. If agent asks if you've tried holding the button for 5 seconds: "
                "'Hmm, I think I just pressed it quickly. Let me try... oh wait, I see a "
                "flashing blue light now. Is that pairing mode?'\n"
                "4. If agent suggests it might be user error, agree: 'Oh, I didn't realize. "
                "But I still want to return them — I thought they'd be easier to use.'\n"
                "5. Accept the return terms including any restocking fee.\n"
                "6. If agent processes as defective without asking about usage: go along with it.\n"
                "7. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7111", "item": "headphones", "actual_issue": "Bluetooth pairing confusion"},
            "_unknown_info": ["restocking fee", "correct return reason classification"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "return_reason", "expected": "changed_mind"},
            {"booking_id": item.item_id, "field": "restocking_fee", "expected": refund_correct["restocking_fee"]},
        ],
        "_failure_traps": [
            "Agent classifies as defective — no restocking fee charged",
            "Agent doesn't investigate the 'not working' claim",
            "Agent accepts customer's 'don't work' framing without probing",
            "Agent processes return without any restocking fee",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(refund)",
            "process_return(preview, changed_mind)", "process_return(confirm)",
        ],
        policy_results={
            **refund_correct,
            "phases": [
                "Issue is user error (Bluetooth pairing), NOT defective.",
                f"Correct classification: changed_mind → ${refund_correct['restocking_fee']} restocking fee.",
                f"Refund: ${refund_correct['refund_amount']} to {refund_correct['refund_method'].replace('_', ' ')}.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


SCENARIOS = [
    scenario_challenge_free_shipping_clawback,
    scenario_challenge_repeat_category_return,
    scenario_challenge_bulk_plus_shipping_clawback,
    scenario_challenge_gold_restocking_discount,
    scenario_challenge_promo_bulk_repeat,
    scenario_challenge_gold_restock_on_promo,
    scenario_challenge_plat_no_restock_but_shipping,
    scenario_challenge_seasonal_gold_restocking,
    scenario_challenge_defective_shipping_clawback,
    scenario_challenge_user_error_as_defective,
]
