"""Customer-support challenge scenarios with compounded adjustments and stacked outcomes."""


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


def scenario_challenge_return_shipping_plus_repeat(
    task_id: str = "challenge_return_shipping_plus_repeat",
    customer_id: str = "cust_005",
    now: str = "2026-06-20T10:00:00",
) -> ScenarioResult:
    """2 cheap same-category returns. Return shipping ($8) + repeat surcharge ($5)."""
    case1 = build_product("phone_case", product_id="PROD-3152", price=22)
    case2 = build_product("phone_case", product_id="PROD-3153", price=22)

    order = build_order(
        customer_id=customer_id, order_id="ORD-7121",
        order_date="2026-06-05T10:00:00", delivery_date="2026-06-10T14:00:00",
        shipping_cost=5,
    )
    item_c1 = build_order_item(order.order_id, case1, item_id="ITEM-10152")
    item_c2 = build_order_item(order.order_id, case2, item_id="ITEM-10153")
    items = [item_c1, item_c2]
    finalize_order(order, items)
    assert order.subtotal < 50

    refund1 = policies.calculate_refund(
        item_price=case1.price, return_reason="changed_mind", category=case1.category,
        discount_code=order.discount_code, discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=case1.current_price,
    )
    refund2 = policies.calculate_refund(
        item_price=case2.price, return_reason="changed_mind", category=case2.category,
        discount_code=order.discount_code, discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=case2.current_price,
    )

    ship_fee = policies.calculate_paid_return_shipping(
        order_subtotal=order.subtotal, return_reason="changed_mind",
    )
    assert ship_fee["applies"]

    repeat = policies.calculate_repeat_return_surcharge("accessories", ["accessories"])
    assert repeat["applies"]

    task_data = {
        "task_id": task_id, "task_type": "compound",
        "description": (
            f"Standard returns 2 phone cases ($22 each) from $44 order. "
            f"Low-value → ${ship_fee['fee']} shipping. Repeat surcharge: ${repeat['surcharge']}."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id, "order_id": order.order_id,
            "return_item_ids": [item_c1.item_id, item_c2.item_id],
        },
        "opening_message": "I want to return both phone cases from order ORD-7121. Neither fits my phone.",
        "user_simulator": {
            "prompt": (
                "2 phone cases ($22 each) from ORD-7121. Standard member.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give order ID.\n2. Return both (changed mind).\n"
                "3. Accept fees.\n4. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7121", "items": "2 phone cases", "reason": "don't fit"},
            "_unknown_info": ["return shipping", "repeat surcharge"],
        },
        "db_assertions": [
            {"booking_id": item_c1.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_c2.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": [
            f"Agent doesn't charge ${ship_fee['fee']} return shipping",
            f"Agent doesn't apply ${repeat['surcharge']} repeat surcharge",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(refund)",
            "get_policies(return_shipping)", "get_policies(repeat_return)",
            "process_return(preview, case1)", "process_return(confirm, case1)",
            "process_return(preview, case2)", "process_return(confirm, case2)",
            "process_refund(preview, shipping)", "process_refund(confirm, shipping)",
            "process_refund(preview, repeat)", "process_refund(confirm, repeat)",
        ],
        policy_results={
            "phases": [
                f"Return case 1: ${refund1['refund_amount']}.",
                f"Return case 2: ${refund2['refund_amount']}.",
                f"Shipping: ${ship_fee['fee']}. Repeat: ${repeat['surcharge']}.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [case1, case2], [order], items, [], task_data


def scenario_challenge_wear_as_not_described(
    task_id: str = "challenge_wear_as_not_described",
    customer_id: str = "cust_002",
    now: str = "2026-06-25T10:00:00",
) -> ScenarioResult:
    """Customer claims worn shirt doesn't match description. Should be changed_mind."""
    shirt = build_product("cotton_shirt", product_id="PROD-3159")

    order = build_order(
        customer_id=customer_id, order_id="ORD-7124",
        order_date="2026-06-01T10:00:00", delivery_date="2026-06-05T14:00:00",
    )
    item = build_order_item(order.order_id, shirt, item_id="ITEM-10159")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=shirt.price, return_reason="changed_mind",
        category=shirt.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=shirt.current_price,
    )

    task_data = {
        "task_id": task_id, "task_type": "return_item",
        "description": (
            "Standard customer claims shirt 'doesn't match the online description' after "
            "wearing and washing it. This is buyer's remorse/changed_mind, not a product "
            "mismatch. Agent should process as changed_mind with standard refund."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id,
            "order_id": order.order_id, "return_item_id": item.item_id,
        },
        "opening_message": (
            "The cotton shirt I got from order ORD-7124 is not as described. "
            "The fabric feels completely different from what was shown on the website."
        ),
        "user_simulator": {
            "prompt": (
                "You bought a cotton shirt ($59) from ORD-7124. You wore it a few times "
                "and washed it. Now you think the fabric feels different than expected.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID.\n"
                "2. When asked about the issue: 'The fabric is rougher than the website showed. "
                "After washing, it shrank a bit and the texture changed.'\n"
                "3. If asked if you wore/washed it: 'Yes, I wore it a few times and washed it once.'\n"
                "4. If agent says this might be normal wear: 'I guess so, but I'm still disappointed.'\n"
                "5. Accept the return terms.\n"
                "6. If agent processes as defective/not_as_described without asking about usage, go along.\n"
                "7. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7124", "item": "cotton shirt", "actual_issue": "wore and washed, disappointed"},
            "_unknown_info": ["return process", "correct classification"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "return_reason", "expected": "changed_mind"},
        ],
        "_failure_traps": [
            "Agent classifies as defective or not_as_described without probing",
            "Agent accepts 'not as described' at face value for worn/washed item",
            "Agent doesn't ask about item usage to determine correct classification",
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
            **refund,
            "phases": [
                "Customer wore and washed the shirt — this is changed_mind, NOT not_as_described.",
                f"Return: ${refund['refund_amount']} to {refund['refund_method'].replace('_', ' ')}.",
                "Agent must probe usage before accepting customer's 'not as described' framing.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [shirt], [order], [item], [], task_data


def scenario_challenge_seasonal_restock_shipping_triple(
    task_id: str = "challenge_seasonal_restock_shipping_triple",
    customer_id: str = "cust_004",
    now: str = "2027-01-15T10:00:00",
) -> ScenarioResult:
    """Dec electronics return in Jan. Seasonal + Silver restocking disc + shipping clawback."""
    from datetime import datetime, timedelta

    headphones = build_product("wireless_headphones", product_id="PROD-3160")
    novel = build_product("novel", product_id="PROD-3161")

    order = build_order(
        customer_id=customer_id, order_id="ORD-7125",
        order_date="2026-12-05T10:00:00", delivery_date="2026-12-10T14:00:00",
        shipping_cost=0,
    )
    item_h = build_order_item(order.order_id, headphones, item_id="ITEM-10160")
    item_n = build_order_item(order.order_id, novel, item_id="ITEM-10161")
    finalize_order(order, [item_h, item_n])

    base_window_end = (datetime.fromisoformat(order.delivery_date) + timedelta(days=headphones.return_window_days)).isoformat()
    seasonal = policies.check_seasonal_return_extension(
        order_date=order.order_date, now=now, base_window_end=base_window_end,
    )
    assert seasonal["applies"]

    refund = policies.calculate_refund(
        item_price=headphones.price, return_reason="changed_mind",
        category=headphones.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=headphones.current_price,
    )
    assert refund["restocking_fee"] > 0

    restock_disc = policies.calculate_restocking_discount(
        refund["restocking_fee"], CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
    )
    assert restock_disc["applies"]

    shipping_cb = policies.calculate_shipping_clawback(
        order_subtotal=order.subtotal, return_item_price=headphones.price,
        shipping_cost=8, original_free_shipping=True,
    )
    assert shipping_cb["applies"]

    task_data = {
        "task_id": task_id, "task_type": "return_item",
        "description": (
            f"Silver, Dec order, returns headphones in Jan. Seasonal + restocking disc ${restock_disc['discount']} + "
            f"shipping clawback ${shipping_cb['clawback_amount']}."
        ),
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id, "return_item_id": item_h.item_id},
        "opening_message": "I want to return the headphones from order ORD-7125. Got them in December.",
        "user_simulator": {
            "prompt": (
                "Headphones ($249) + book from ORD-7125, Dec order. Silver member.\n\n"
                "Your preferences:\n{{user_attributes}}\n\nRULES:\n1. Give order ID.\n"
                "2. If window expired, mention holiday returns.\n3. If restocking fee, ask about Silver discount.\n"
                "4. Accept fees.\n5. 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7125", "item": "headphones", "reason": "changed mind"},
            "_unknown_info": ["seasonal", "restocking discount", "shipping clawback"],
        },
        "db_assertions": [{"booking_id": item_h.item_id, "field": "item_status", "expected": "returned"}],
        "_failure_traps": ["Agent denies return (no seasonal)", f"Misses ${restock_disc['discount']} disc", f"Misses ${shipping_cb['clawback_amount']} clawback"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=["get_order", "get_customer", "get_policies(return)", "get_policies(seasonal)",
            "get_policies(refund)", "get_policies(restocking_discount)", "get_policies(free_shipping)",
            "process_return(preview)", "process_return(confirm)",
            "process_refund(preview, restock)", "process_refund(confirm, restock)",
            "process_refund(preview, shipping)", "process_refund(confirm, shipping)"],
        policy_results={**refund, "phases": [
            "Seasonal: Dec order → Jan 31.", f"Restocking ${refund['restocking_fee']}, Silver disc ${restock_disc['discount']}.",
            f"Shipping clawback ${shipping_cb['clawback_amount']}.",
        ]},
        scenario=task_data["scenario_template"],
    )
    return [headphones, novel], [order], [item_h, item_n], [], task_data


def scenario_challenge_seasonal_repeat_shipping(
    task_id: str = "challenge_seasonal_repeat_shipping",
    customer_id: str = "cust_002",
    now: str = "2027-01-18T10:00:00",
) -> ScenarioResult:
    """Nov 3-item free-shipping order. Return 2 clothing in Jan. Triple policy."""
    from datetime import datetime, timedelta

    shirt = build_product("cotton_shirt", product_id="PROD-3163")
    shoes = build_product("running_shoes", product_id="PROD-3164")
    case = build_product("phone_case", product_id="PROD-3165")

    order = build_order(
        customer_id=customer_id, order_id="ORD-7127",
        order_date="2026-11-18T10:00:00", delivery_date="2026-11-25T14:00:00",
        shipping_cost=0,
    )
    item_sh = build_order_item(order.order_id, shirt, item_id="ITEM-10163")
    item_shoes = build_order_item(order.order_id, shoes, item_id="ITEM-10164")
    item_c = build_order_item(order.order_id, case, item_id="ITEM-10165")
    items = [item_sh, item_shoes, item_c]
    finalize_order(order, items)

    base_window_end = (datetime.fromisoformat(order.delivery_date) + timedelta(days=shirt.return_window_days)).isoformat()
    seasonal = policies.check_seasonal_return_extension(order_date=order.order_date, now=now, base_window_end=base_window_end)
    assert seasonal["applies"]

    repeat = policies.calculate_repeat_return_surcharge("clothing", ["clothing"])
    assert repeat["applies"]

    remaining = case.price  # $35
    shipping_cb = policies.calculate_shipping_clawback(
        order_subtotal=order.subtotal, return_item_price=shirt.price + shoes.price,
        shipping_cost=8, original_free_shipping=True,
    )
    assert shipping_cb["applies"]

    task_data = {
        "task_id": task_id, "task_type": "compound",
        "description": f"Nov free-shipping order, return 2 clothing in Jan. Seasonal + repeat ${repeat['surcharge']} + shipping ${shipping_cb['clawback_amount']}.",
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id, "return_item_ids": [item_sh.item_id, item_shoes.item_id]},
        "opening_message": "I want to return the shirt and running shoes from order ORD-7127. I ordered them in November.",
        "user_simulator": {
            "prompt": "Shirt ($59)+shoes ($129)+case from ORD-7127, Nov. Standard.\n\nYour preferences:\n{{user_attributes}}\n\nRULES:\n1. Give order ID.\n2. If window expired, mention holiday returns.\n3. Accept fees.\n4. If one item only, ask about other.\n5. 1-3 sentences.",
            "_known_info": {"order_id": "ORD-7127", "items": "shirt+shoes", "reason": "changed mind"},
            "_unknown_info": ["seasonal", "repeat surcharge", "shipping clawback"],
        },
        "db_assertions": [
            {"booking_id": item_sh.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_shoes.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": ["Agent denies (no seasonal)", f"Misses ${repeat['surcharge']} repeat", f"Misses ${shipping_cb['clawback_amount']} shipping"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=["get_order", "get_customer", "get_policies(return)", "get_policies(seasonal)",
            "get_policies(repeat_return)", "get_policies(free_shipping)", "get_policies(refund)",
            "process_return(preview, shirt)", "process_return(confirm, shirt)",
            "process_return(preview, shoes)", "process_return(confirm, shoes)",
            "process_refund(preview, repeat)", "process_refund(confirm, repeat)",
            "process_refund(preview, shipping)", "process_refund(confirm, shipping)"],
        policy_results={"phases": [
            "Seasonal: Nov order → Jan 31.",
            f"Repeat: ${repeat['surcharge']} on 2nd clothing.",
            f"Shipping clawback: ${shipping_cb['clawback_amount']} (remaining ${remaining}<$100).",
        ]},
        scenario=task_data["scenario_template"],
    )
    return [shirt, shoes, case], [order], items, [], task_data


def scenario_challenge_promo_shipping_restock_gold(
    task_id: str = "challenge_promo_shipping_restock_gold",
    customer_id: str = "cust_003",
    now: str = "2026-06-15T10:00:00",
) -> ScenarioResult:
    """Gold returns headphones from promo free-shipping order. Triple policy."""
    headphones = build_product("wireless_headphones", product_id="PROD-3166")
    novel = build_product("novel", product_id="PROD-3167")

    order = build_order(
        customer_id=customer_id, order_id="ORD-7128",
        order_date="2026-06-01T10:00:00", delivery_date="2026-06-05T14:00:00",
        shipping_cost=0, discount_code="SAVE8", discount_amount=8,
    )
    item_h = build_order_item(order.order_id, headphones, item_id="ITEM-10166")
    item_n = build_order_item(order.order_id, novel, item_id="ITEM-10167")
    finalize_order(order, [item_h, item_n])

    refund = policies.calculate_refund(
        item_price=headphones.price, return_reason="changed_mind",
        category=headphones.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=headphones.current_price,
    )
    assert refund["restocking_fee"] > 0 and refund["discount_adjustment"] > 0

    restock_disc = policies.calculate_restocking_discount(refund["restocking_fee"], "gold")
    assert restock_disc["applies"]

    shipping_cb = policies.calculate_shipping_clawback(
        order_subtotal=order.subtotal, return_item_price=headphones.price,
        shipping_cost=8, original_free_shipping=True,
    )
    assert shipping_cb["applies"]

    task_data = {
        "task_id": task_id, "task_type": "return_item",
        "description": (
            f"Gold returns headphones ($249) from promo free-shipping order. "
            f"Promo adj ${refund['discount_adjustment']}. Restocking ${refund['restocking_fee']}, Gold disc ${restock_disc['discount']}. "
            f"Shipping clawback ${shipping_cb['clawback_amount']}."
        ),
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id, "return_item_id": item_h.item_id},
        "opening_message": "I want to return the wireless headphones from order ORD-7128.",
        "user_simulator": {
            "prompt": "Headphones ($249)+book from ORD-7128 (SAVE8 promo). Gold+Prime.\n\nYour preferences:\n{{user_attributes}}\n\nRULES:\n1. Give ID.\n2. Ask about Gold restocking discount.\n3. Accept fees.\n4. 1-3 sentences.",
            "_known_info": {"order_id": "ORD-7128", "item": "headphones", "reason": "changed mind"},
            "_unknown_info": ["promo adj", "restocking discount", "shipping clawback"],
        },
        "db_assertions": [{"booking_id": item_h.item_id, "field": "item_status", "expected": "returned"}],
        "_failure_traps": [f"Misses Gold ${restock_disc['discount']} disc", f"Misses ${shipping_cb['clawback_amount']} clawback"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=["get_order", "get_customer", "get_policies(return)", "get_policies(refund)",
            "get_policies(restocking_discount)", "get_policies(free_shipping)",
            "process_return(preview)", "process_return(confirm)",
            "process_refund(preview, restock)", "process_refund(confirm, restock)",
            "process_refund(preview, shipping)", "process_refund(confirm, shipping)"],
        policy_results={**refund, "phases": [
            f"Promo adj ${refund['discount_adjustment']}. Restocking ${refund['restocking_fee']}.",
            f"Gold disc ${restock_disc['discount']}. Shipping ${shipping_cb['clawback_amount']}.",
        ]},
        scenario=task_data["scenario_template"],
    )
    return [headphones, novel], [order], [item_h, item_n], [], task_data


def scenario_challenge_gold_repeat_restock_shipping(
    task_id: str = "challenge_gold_repeat_restock_shipping",
    customer_id: str = "cust_003",
    now: str = "2026-06-15T10:00:00",
) -> ScenarioResult:
    """Gold returns 2 electronics from free-shipping order. Triple: disc+repeat+shipping."""
    headphones = build_product("wireless_headphones", product_id="PROD-3172")
    usb_hub = build_product("usb_hub", product_id="PROD-3173")
    shirt = build_product("cotton_shirt", product_id="PROD-3174")

    order = build_order(
        customer_id=customer_id, order_id="ORD-7130",
        order_date="2026-06-01T10:00:00", delivery_date="2026-06-05T14:00:00",
        shipping_cost=0,
    )
    item_h = build_order_item(order.order_id, headphones, item_id="ITEM-10172")
    item_u = build_order_item(order.order_id, usb_hub, item_id="ITEM-10173")
    item_s = build_order_item(order.order_id, shirt, item_id="ITEM-10174")
    items = [item_h, item_u, item_s]
    finalize_order(order, items)

    refund_h = policies.calculate_refund(
        item_price=headphones.price, return_reason="changed_mind", category=headphones.category,
        discount_code=order.discount_code, discount_amount=order.discount_amount,
        order_subtotal=order.subtotal, membership_tier="gold",
        is_gift_return=False, current_product_price=headphones.current_price,
    )
    refund_u = policies.calculate_refund(
        item_price=usb_hub.price, return_reason="changed_mind", category=usb_hub.category,
        discount_code=order.discount_code, discount_amount=order.discount_amount,
        order_subtotal=order.subtotal, membership_tier="gold",
        is_gift_return=False, current_product_price=usb_hub.current_price,
    )

    disc_h = policies.calculate_restocking_discount(refund_h["restocking_fee"], "gold")
    disc_u = policies.calculate_restocking_discount(refund_u["restocking_fee"], "gold")
    repeat = policies.calculate_repeat_return_surcharge("electronics", ["electronics"])
    shipping_cb = policies.calculate_shipping_clawback(
        order_subtotal=order.subtotal, return_item_price=headphones.price + usb_hub.price,
        shipping_cost=10, original_free_shipping=True,
    )
    assert disc_h["applies"] and disc_u["applies"] and repeat["applies"] and shipping_cb["applies"]

    task_data = {
        "task_id": task_id, "task_type": "compound",
        "description": (
            f"Gold returns headphones+USB hub from free-shipping order. "
            f"Gold disc on both restocking, repeat ${repeat['surcharge']}, shipping ${shipping_cb['clawback_amount']}."
        ),
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id,
            "return_item_ids": [item_h.item_id, item_u.item_id]},
        "opening_message": "I want to return the headphones and USB hub from order ORD-7130.",
        "user_simulator": {
            "prompt": "Headphones ($249)+USB hub ($45)+shirt from ORD-7130. Gold+Prime.\n\nYour preferences:\n{{user_attributes}}\n\nRULES:\n1. Give ID.\n2. Ask about Gold restocking discount.\n3. Accept fees.\n4. Return both electronics.\n5. 1-3 sentences.",
            "_known_info": {"order_id": "ORD-7130", "items": "headphones+hub", "reason": "changed mind"},
            "_unknown_info": ["restocking fees", "Gold discount", "repeat surcharge", "shipping clawback"],
        },
        "db_assertions": [
            {"booking_id": item_h.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_u.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": ["Misses Gold restocking discounts", f"Misses repeat ${repeat['surcharge']}", f"Misses shipping ${shipping_cb['clawback_amount']}"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=["get_order", "get_customer", "get_policies(return)", "get_policies(refund)",
            "get_policies(restocking_discount)", "get_policies(repeat_return)", "get_policies(free_shipping)",
            "process_return(preview, headphones)", "process_return(confirm, headphones)",
            "process_return(preview, hub)", "process_return(confirm, hub)",
            "process_refund(preview, disc_h)", "process_refund(confirm, disc_h)",
            "process_refund(preview, disc_u)", "process_refund(confirm, disc_u)",
            "process_refund(preview, repeat)", "process_refund(confirm, repeat)",
            "process_refund(preview, shipping)", "process_refund(confirm, shipping)"],
        policy_results={"phases": [
            f"Return headphones: ${refund_h['refund_amount']} (restock ${refund_h['restocking_fee']}). Gold disc: ${disc_h['discount']}.",
            f"Return USB hub: ${refund_u['refund_amount']} (restock ${refund_u['restocking_fee']}). Gold disc: ${disc_u['discount']}.",
            f"Repeat surcharge: ${repeat['surcharge']}. Shipping clawback: ${shipping_cb['clawback_amount']}.",
        ]},
        scenario=task_data["scenario_template"],
    )
    return [headphones, usb_hub, shirt], [order], items, [], task_data


def scenario_challenge_seasonal_low_value_silver_electronics(
    task_id: str = "challenge_seasonal_low_value_silver_electronics",
    customer_id: str = "cust_004",
    now: str = "2027-01-12T10:00:00",
) -> ScenarioResult:
    """Dec low-value electronics, Silver. Jan return. 4 new policies."""
    from datetime import datetime, timedelta

    usb_hub = build_product("usb_hub", product_id="PROD-3175")

    order = build_order(
        customer_id=customer_id, order_id="ORD-7131",
        order_date="2026-12-01T10:00:00", delivery_date="2026-12-05T14:00:00",
        shipping_cost=5,
    )
    item = build_order_item(order.order_id, usb_hub, item_id="ITEM-10175")
    finalize_order(order, [item])
    assert order.subtotal < 50

    base_window_end = (datetime.fromisoformat(order.delivery_date) + timedelta(days=usb_hub.return_window_days)).isoformat()
    seasonal = policies.check_seasonal_return_extension(order_date=order.order_date, now=now, base_window_end=base_window_end)
    assert seasonal["applies"]

    refund = policies.calculate_refund(
        item_price=usb_hub.price, return_reason="changed_mind", category=usb_hub.category,
        discount_code=order.discount_code, discount_amount=order.discount_amount,
        order_subtotal=order.subtotal, membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=usb_hub.current_price,
    )
    assert refund["restocking_fee"] > 0

    restock_disc = policies.calculate_restocking_discount(refund["restocking_fee"], "silver")
    assert restock_disc["applies"]

    ship_fee = policies.calculate_paid_return_shipping(order_subtotal=order.subtotal, return_reason="changed_mind")
    assert ship_fee["applies"]

    task_data = {
        "task_id": task_id, "task_type": "return_item",
        "description": (
            f"Silver, Dec USB hub ($45), return in Jan. Seasonal + restocking ${refund['restocking_fee']} "
            f"+ Silver disc ${restock_disc['discount']} + return shipping ${ship_fee['fee']}."
        ),
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id, "return_item_id": item.item_id},
        "opening_message": "I want to return the USB hub from my December order ORD-7131.",
        "user_simulator": {
            "prompt": "USB hub ($45) from ORD-7131, Dec. Silver.\n\nYour preferences:\n{{user_attributes}}\n\nRULES:\n1. Give ID.\n2. If window expired, mention holiday returns.\n3. If restocking, ask about Silver discount.\n4. Accept fees.\n5. 1-3 sent.",
            "_known_info": {"order_id": "ORD-7131", "item": "USB hub", "reason": "changed mind"},
            "_unknown_info": ["seasonal", "restocking", "Silver disc", "return shipping"],
        },
        "db_assertions": [{"booking_id": item.item_id, "field": "item_status", "expected": "returned"}],
        "_failure_traps": ["Denies (no seasonal)", f"Misses Silver disc ${restock_disc['discount']}", f"Misses shipping ${ship_fee['fee']}"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=["get_order", "get_customer", "get_policies(return)", "get_policies(seasonal)",
            "get_policies(refund)", "get_policies(restocking_discount)", "get_policies(return_shipping)",
            "process_return(preview)", "process_return(confirm)",
            "process_refund(preview, disc)", "process_refund(confirm, disc)",
            "process_refund(preview, shipping)", "process_refund(confirm, shipping)"],
        policy_results={**refund, "phases": [
            f"Seasonal: Dec → Jan 31. Restocking ${refund['restocking_fee']}.",
            f"Silver disc ${restock_disc['discount']}. Return shipping ${ship_fee['fee']}.",
        ]},
        scenario=task_data["scenario_template"],
    )
    return [usb_hub], [order], [item], [], task_data


def scenario_challenge_triple_same_category_return(
    task_id: str = "challenge_triple_same_category_return",
    customer_id: str = "cust_002",
    now: str = "2026-06-20T10:00:00",
) -> ScenarioResult:
    """Return 3 clothing items. Double repeat surcharge ($5 + $5 = $10)."""
    shirt1 = build_product("cotton_shirt", product_id="PROD-3176")
    shirt2 = build_product("cotton_shirt_large", product_id="PROD-3177")
    shoes = build_product("running_shoes", product_id="PROD-3178")
    case = build_product("phone_case", product_id="PROD-3179")

    order = build_order(
        customer_id=customer_id, order_id="ORD-7132",
        order_date="2026-06-05T10:00:00", delivery_date="2026-06-10T14:00:00",
    )
    item_s1 = build_order_item(order.order_id, shirt1, item_id="ITEM-10176")
    item_s2 = build_order_item(order.order_id, shirt2, item_id="ITEM-10177")
    item_shoes = build_order_item(order.order_id, shoes, item_id="ITEM-10178")
    item_c = build_order_item(order.order_id, case, item_id="ITEM-10179")
    items = [item_s1, item_s2, item_shoes, item_c]
    finalize_order(order, items)

    # Repeat surcharges: 2nd clothing = $5, 3rd clothing = $5
    repeat2 = policies.calculate_repeat_return_surcharge("clothing", ["clothing"])
    repeat3 = policies.calculate_repeat_return_surcharge("clothing", ["clothing", "clothing"])
    assert repeat2["applies"] and repeat3["applies"]
    total_surcharge = repeat2["surcharge"] + repeat3["surcharge"]  # $10

    task_data = {
        "task_id": task_id, "task_type": "compound",
        "description": (
            f"Return 3 clothing items from 4-item order. 2nd and 3rd each get $5 repeat surcharge. "
            f"Total surcharge: ${total_surcharge}."
        ),
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id,
            "return_item_ids": [item_s1.item_id, item_s2.item_id, item_shoes.item_id]},
        "opening_message": "I want to return all three clothing items from order ORD-7132 — both shirts and the shoes. I'm keeping just the phone case.",
        "user_simulator": {
            "prompt": "2 shirts ($59 each) + shoes ($129) + case from ORD-7132. Standard.\n\nYour preferences:\n{{user_attributes}}\n\nRULES:\n1. Give ID.\n2. Return all 3 clothing items.\n3. Accept fees.\n4. If not all processed, ask about remaining.\n5. 1-3 sent.",
            "_known_info": {"order_id": "ORD-7132", "items": "2 shirts + shoes", "reason": "changed mind"},
            "_unknown_info": ["repeat surcharge", "surcharge amounts"],
        },
        "db_assertions": [
            {"booking_id": item_s1.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_s2.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_shoes.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": [
            f"Agent doesn't apply ${total_surcharge} total repeat surcharges ($5 + $5)",
            "Agent applies surcharge to only one of the 2nd/3rd items",
            "Agent only returns 1 or 2 items instead of all 3",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=["get_order", "get_customer", "get_policies(return)", "get_policies(refund)",
            "get_policies(repeat_return)",
            "process_return(preview, s1)", "process_return(confirm, s1)",
            "process_return(preview, s2)", "process_return(confirm, s2)",
            "process_return(preview, shoes)", "process_return(confirm, shoes)",
            "process_refund(preview, repeat2)", "process_refund(confirm, repeat2)",
            "process_refund(preview, repeat3)", "process_refund(confirm, repeat3)"],
        policy_results={"phases": [
            "Return 3 clothing items from same order.",
            f"2nd clothing return: ${repeat2['surcharge']} surcharge.",
            f"3rd clothing return: ${repeat3['surcharge']} surcharge.",
            f"Total repeat surcharge: ${total_surcharge}.",
        ]},
        scenario=task_data["scenario_template"],
    )
    return [shirt1, shirt2, shoes, case], [order], items, [], task_data


def scenario_challenge_triple_action(
    task_id: str = "challenge_triple_action",
    customer_id: str = "cust_004",
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """Defective fragile item + late delivery = 3 separate actions."""
    kitchen_scale = build_product("kitchen_scale", product_id="PROD-3042")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7042",
        order_date="2026-06-20T10:00:00",
        delivery_date="2026-07-04T14:00:00",
        delivery_promised_date="2026-06-30T10:00:00",
        status="delivered",
        shipping_status="damaged",
        shipping_cost=8,
    )
    item = build_order_item(order.order_id, kitchen_scale, item_id="ITEM-10042")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=kitchen_scale.price,
        return_reason="damaged_in_transit",
        category=kitchen_scale.category,
        discount_code=order.discount_code,
        discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False,
        current_product_price=kitchen_scale.current_price,
    )
    comp = policies.calculate_compensation(
        delivery_date=order.delivery_date,
        delivery_promised_date=order.delivery_promised_date,
        now=now,
        order_total=order.subtotal,
        shipping_cost=order.shipping_cost,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        previous_issues_count=0,
    )
    shipping_claim = policies.check_shipping_claim(
        shipping_status=order.shipping_status,
        order_total=order.total_paid,
        delivery_date=order.delivery_date,
        delivery_promised_date=order.delivery_promised_date,
        now=now,
        signature_required=order.signature_required,
        signature_on_file=order.signature_on_file,
        is_fragile=kitchen_scale.is_fragile,
        tracking_number=order.tracking_number,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": (
            f"Fragile kitchen scale damaged + 4 days late. THREE actions: "
            f"(1) Return: ${refund['refund_amount']}. (2) Late comp: ${comp['total_compensation']}. "
            f"(3) Fragile goodwill: ${shipping_claim['goodwill_credit']}."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "My kitchen scale from order ORD-7042 arrived 4 days late AND damaged — the glass surface is cracked. This is completely unacceptable.",
        "user_simulator": {
            "prompt": (
                "Kitchen scale (ORD-7042, $32) arrived 4 days late AND damaged (cracked glass). "
                "Fragile item. You want: refund, late delivery compensation, AND extra for the fragile item damage.\n\n"
                "RULES:\n1. Give order ID.\n2. Mention BOTH late delivery AND damage.\n"
                "3. If agent only handles one issue, remind about the others.\n"
                "4. Ask about fragile item goodwill if not mentioned.\n"
                "5. Don't end until all 3 compensations are confirmed.\n6. Keep to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-7042",
                "item": "kitchen scale ($32)",
                "issues": "4 days late + damaged + fragile",
            },
            "_unknown_info": ["compensation amounts", "fragile goodwill policy"],
        },
        "db_assertions": [{"booking_id": item.item_id, "field": "item_status", "expected": "returned"}],
        "_failure_traps": [
            "Agent handles return but forgets late delivery compensation",
            "Agent handles return + late comp but forgets $10 fragile goodwill",
            "Agent combines everything into one refund instead of separate calls",
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
            "get_policies(compensation)",
            "process_return(preview)",
            "process_return(confirm)",
            "process_refund(preview, comp)",
            "process_refund(confirm, comp)",
            "process_refund(preview, goodwill)",
            "process_refund(confirm, goodwill)",
        ],
        policy_results={
            "phases": [
                f"Return damaged scale: ${refund['refund_amount']}, free return label.",
                f"Late delivery comp: ${comp['total_compensation']} via process_refund.",
                f"Fragile goodwill: ${shipping_claim['goodwill_credit']} via process_refund.",
            ]
        },
        scenario=task_data["scenario_template"],
    )
    return [kitchen_scale], [order], [item], [], task_data


def scenario_challenge_gold_7day_all_parts(
    task_id: str = "challenge_gold_7day_all_parts",
    customer_id: str = "cust_003",
    now: str = "2026-07-08T10:00:00",
) -> ScenarioResult:
    """Gold, 7 days, 3 issues, $149 order. All 3 comp parts, no cap. Int truncation trap."""
    coffee = build_product("coffee_maker", product_id="PROD-3069")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7064",
        order_date="2026-06-15T10:00:00",
        delivery_date="2026-07-03T14:00:00",
        delivery_promised_date="2026-06-26T10:00:00",
        shipping_cost=12,
    )
    item = build_order_item(order.order_id, coffee, item_id="ITEM-10069")
    finalize_order(order, [item])

    comp = policies.calculate_compensation(
        delivery_date=order.delivery_date,
        delivery_promised_date=order.delivery_promised_date,
        now=now,
        order_total=order.subtotal,
        shipping_cost=order.shipping_cost,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        previous_issues_count=3,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": (
            f"Gold, 7 days late, 3 issues. Credit int(15*1.5)=${comp['adjusted_credit']} + "
            f"shipping ${comp['shipping_refund']} + goodwill $25 = ${comp['total_compensation']}."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "previous_issues_count": 3,
        },
        "opening_message": "My coffee maker from ORD-7064 was a full week late — 7 days! This is my 4th issue. I want full compensation.",
        "user_simulator": {
            "prompt": (
                "Coffee maker (ORD-7064, $149) 7 days late. 3 previous issues. Gold.\n\n"
                "RULES:\n1. Give order ID.\n2. Say 3 previous issues.\n3. Ask for breakdown.\n"
                "4. Accept only after the correct payout is actually processed.\n5. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7064", "days_late": "7", "previous_issues": "3"},
            "_unknown_info": ["compensation breakdown"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "delivered"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": comp["total_compensation"]},
            {"booking_id": item.item_id, "field": "refund_method", "expected": "original_payment"},
        ],
        "_failure_traps": [
            "Agent computes $22.50 instead of $22 (int truncation)",
            "Agent applies 1.5x to goodwill: ($15+$25)*1.5=$60",
            "Agent applies 1.5x to shipping refund",
            "Agent forgets one of the 3 components",
        ],
        "task_requirements": [
            {
                "id": f"{task_id}_agent_must_process_59_refund_to_original_payment",
                "kind": "must",
                "requirement": "Agent must actually process a $59 refund to the original payment method.",
                "evidence": "conversation_or_tool_calls",
            },
            {
                "id": f"{task_id}_agent_must_include_all_three_compensation_components",
                "kind": "must",
                "requirement": "Agent must include the $22 late-delivery credit, the $12 shipping refund, and the $25 goodwill credit.",
                "evidence": "conversation",
            },
            {
                "id": f"{task_id}_agent_must_not_multiply_shipping_or_goodwill",
                "kind": "must_not",
                "requirement": "Agent must not apply the gold multiplier to the shipping refund or the goodwill credit.",
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
            "adjusted_credit": comp["adjusted_credit"],
            "goodwill_credit": comp["goodwill_credit"],
            "shipping_refund": comp["shipping_refund"],
            "days_late": comp["days_late"],
        },
        scenario=task_data["scenario_template"],
    )
    return [coffee], [order], [item], [], task_data


SCENARIOS = [
    scenario_challenge_return_shipping_plus_repeat,
    scenario_challenge_wear_as_not_described,
    scenario_challenge_seasonal_restock_shipping_triple,
    scenario_challenge_seasonal_repeat_shipping,
    scenario_challenge_promo_shipping_restock_gold,
    scenario_challenge_gold_repeat_restock_shipping,
    scenario_challenge_seasonal_low_value_silver_electronics,
    scenario_challenge_triple_same_category_return,
    scenario_challenge_triple_action,
    scenario_challenge_gold_7day_all_parts,
]
