"""Customer-support challenge scenarios with advanced exception handling."""


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


def scenario_challenge_two_electronics_gold(
    task_id: str = "challenge_two_electronics_gold",
    customer_id: str = "cust_003",  # Gold
    now: str = "2026-06-15T10:00:00",
) -> ScenarioResult:
    """Gold returns 2 electronics. Both get restocking discount, 2nd gets repeat surcharge."""
    headphones = build_product("wireless_headphones", product_id="PROD-3138")
    usb_hub = build_product("usb_hub", product_id="PROD-3139")
    shirt = build_product("cotton_shirt", product_id="PROD-3140")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7112",
        order_date="2026-06-01T10:00:00",
        delivery_date="2026-06-05T14:00:00",
    )
    item_h = build_order_item(order.order_id, headphones, item_id="ITEM-10138")
    item_u = build_order_item(order.order_id, usb_hub, item_id="ITEM-10139")
    item_s = build_order_item(order.order_id, shirt, item_id="ITEM-10140")
    items = [item_h, item_u, item_s]
    finalize_order(order, items)

    refund_h = policies.calculate_refund(
        item_price=headphones.price, return_reason="changed_mind",
        category=headphones.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=headphones.current_price,
    )
    refund_u = policies.calculate_refund(
        item_price=usb_hub.price, return_reason="changed_mind",
        category=usb_hub.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=usb_hub.current_price,
    )

    disc_h = policies.calculate_restocking_discount(refund_h["restocking_fee"], "gold")
    disc_u = policies.calculate_restocking_discount(refund_u["restocking_fee"], "gold")
    assert disc_h["applies"] and disc_u["applies"]

    repeat = policies.calculate_repeat_return_surcharge("electronics", ["electronics"])
    assert repeat["applies"]

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": (
            f"Gold returns headphones ($249) and USB hub ($45) — both electronics. "
            f"Headphones: restocking ${refund_h['restocking_fee']}, Gold disc ${disc_h['discount']}. "
            f"USB hub: restocking ${refund_u['restocking_fee']}, Gold disc ${disc_u['discount']}, "
            f"+ ${repeat['surcharge']} repeat surcharge. "
            f"Agent must apply restocking discount to both + repeat surcharge to second."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_ids": [item_h.item_id, item_u.item_id],
        },
        "opening_message": (
            "Hi, I want to return the headphones and the USB hub from order ORD-7112. "
            "I changed my mind on both."
        ),
        "user_simulator": {
            "prompt": (
                "You bought headphones ($249), USB hub ($45), and shirt from ORD-7112. "
                "Return both electronics (changed mind). Gold member with Prime.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID.\n"
                "2. Confirm return of headphones and USB hub.\n"
                "3. If restocking fee mentioned, ask about Gold discount.\n"
                "4. Accept all fees and surcharges.\n"
                "5. If only one item returned, ask about the other.\n"
                "6. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7112", "items": "headphones + USB hub", "reason": "changed mind"},
            "_unknown_info": ["restocking fees", "Gold discount", "repeat surcharge"],
        },
        "db_assertions": [
            {"booking_id": item_h.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_u.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": [
            f"Agent doesn't apply Gold restocking discount (${disc_h['discount']} + ${disc_u['discount']})",
            f"Agent doesn't apply ${repeat['surcharge']} repeat same-category surcharge",
            "Agent only returns one of the two items",
            "Agent doesn't know about restocking_discount or repeat_return policies",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(refund)",
            "get_policies(restocking_discount)", "get_policies(repeat_return)",
            "process_return(preview, headphones)", "process_return(confirm, headphones)",
            "process_return(preview, usb_hub)", "process_return(confirm, usb_hub)",
            "process_refund(preview, disc_headphones)", "process_refund(confirm, disc_headphones)",
            "process_refund(preview, disc_usb_hub)", "process_refund(confirm, disc_usb_hub)",
            "process_refund(preview, repeat_surcharge)", "process_refund(confirm, repeat_surcharge)",
        ],
        policy_results={
            "phases": [
                f"Return headphones: ${refund_h['refund_amount']} (restocking ${refund_h['restocking_fee']}). Gold discount: ${disc_h['discount']}.",
                f"Return USB hub: ${refund_u['refund_amount']} (restocking ${refund_u['restocking_fee']}). Gold discount: ${disc_u['discount']}.",
                f"Repeat surcharge: ${repeat['surcharge']} on 2nd electronics return.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones, usb_hub, shirt], [order], items, [], task_data


def scenario_challenge_low_value_return_shipping(
    task_id: str = "challenge_low_value_return_shipping",
    customer_id: str = "cust_005",  # Standard, new
    now: str = "2026-06-20T10:00:00",
) -> ScenarioResult:
    """Low-value order return — customer pays $8 return shipping."""
    case = build_product("phone_case", product_id="PROD-3142")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7114",
        order_date="2026-06-05T10:00:00",
        delivery_date="2026-06-10T14:00:00",
        shipping_cost=5,
    )
    item = build_order_item(order.order_id, case, item_id="ITEM-10142")
    finalize_order(order, [item])
    assert order.subtotal < 50, f"Setup error: subtotal {order.subtotal} should be < 50"

    refund = policies.calculate_refund(
        item_price=case.price, return_reason="changed_mind",
        category=case.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=case.current_price,
    )

    shipping_fee = policies.calculate_paid_return_shipping(
        order_subtotal=order.subtotal,
        return_reason="changed_mind",
    )
    assert shipping_fee["applies"], "Setup error: should have paid return shipping"

    net_refund = refund["refund_amount"] - shipping_fee["fee"]

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            f"Standard customer returns phone case ($35) from low-value order (subtotal ${order.subtotal}). "
            f"Order below $50 → ${shipping_fee['fee']} return shipping fee. "
            f"Net refund: ${net_refund}. Agent must deduct shipping fee."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id,
            "order_id": order.order_id, "return_item_id": item.item_id,
        },
        "opening_message": (
            "I'd like to return the phone case from order ORD-7114. I changed my mind."
        ),
        "user_simulator": {
            "prompt": (
                "You bought a phone case ($35) from ORD-7114. Return it (changed mind). "
                "Standard member, new customer.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID.\n"
                "2. Accept any shipping charges.\n"
                "3. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7114", "item": "phone case", "reason": "changed mind"},
            "_unknown_info": ["return shipping fee", "refund amount"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": [
            f"Agent gives full ${refund['refund_amount']} refund without ${shipping_fee['fee']} shipping deduction",
            "Agent doesn't check return_shipping policy for low-value orders",
            f"Agent should deduct ${shipping_fee['fee']} and refund ${net_refund}",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(refund)", "get_policies(return_shipping)",
            "process_return(preview)", "process_return(confirm)",
            "process_refund(preview, shipping_fee)", "process_refund(confirm, shipping_fee)",
        ],
        policy_results={
            **refund,
            "phases": [
                f"Return phone case: ${refund['refund_amount']}.",
                f"Low-value order (${order.subtotal} < $50): ${shipping_fee['fee']} return shipping fee.",
                f"Net refund: ${net_refund}.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [case], [order], [item], [], task_data


def scenario_challenge_low_value_electronics_silver(
    task_id: str = "challenge_low_value_electronics_silver",
    customer_id: str = "cust_004",  # Silver
    now: str = "2026-06-20T10:00:00",
) -> ScenarioResult:
    """Silver returns low-value electronics. Three obscure deductions combine."""
    usb_hub = build_product("usb_hub", product_id="PROD-3143")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7115",
        order_date="2026-06-05T10:00:00",
        delivery_date="2026-06-10T14:00:00",
        shipping_cost=5,
    )
    item = build_order_item(order.order_id, usb_hub, item_id="ITEM-10143")
    finalize_order(order, [item])
    assert order.subtotal < 50

    refund = policies.calculate_refund(
        item_price=usb_hub.price, return_reason="changed_mind",
        category=usb_hub.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=usb_hub.current_price,
    )
    assert refund["restocking_fee"] > 0

    restock_disc = policies.calculate_restocking_discount(
        refund["restocking_fee"], CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
    )
    assert restock_disc["applies"]

    shipping_fee = policies.calculate_paid_return_shipping(
        order_subtotal=order.subtotal, return_reason="changed_mind",
    )
    assert shipping_fee["applies"]

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            f"Silver returns USB hub ($45, electronics, changed_mind). "
            f"Restocking: ${refund['restocking_fee']}. Silver 25% discount: ${restock_disc['discount']}. "
            f"Low-value order → ${shipping_fee['fee']} return shipping. "
            f"Three new policies must all be applied."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id,
            "order_id": order.order_id, "return_item_id": item.item_id,
        },
        "opening_message": (
            "I'd like to return the USB hub from order ORD-7115. I changed my mind about it."
        ),
        "user_simulator": {
            "prompt": (
                "You bought a USB hub ($45) from ORD-7115. Return it (changed mind). Silver member.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID.\n"
                "2. If restocking fee mentioned, ask about Silver member discount.\n"
                "3. Accept all fees.\n4. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7115", "item": "USB hub", "reason": "changed mind"},
            "_unknown_info": ["restocking fee", "Silver discount", "return shipping fee"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "restocking_fee", "expected": refund["restocking_fee"]},
        ],
        "_failure_traps": [
            f"Agent doesn't apply ${restock_disc['discount']} Silver restocking discount",
            f"Agent doesn't charge ${shipping_fee['fee']} return shipping on low-value order",
            "Agent doesn't check restocking_discount or return_shipping policies",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(refund)",
            "get_policies(restocking_discount)", "get_policies(return_shipping)",
            "process_return(preview)", "process_return(confirm)",
            "process_refund(preview, restock_credit)", "process_refund(confirm, restock_credit)",
            "process_refund(preview, shipping_fee)", "process_refund(confirm, shipping_fee)",
        ],
        policy_results={
            **refund,
            "phases": [
                f"Return USB hub: ${refund['refund_amount']} (restocking ${refund['restocking_fee']}).",
                f"Silver restocking discount: ${restock_disc['discount']} credit.",
                f"Low-value order shipping fee: ${shipping_fee['fee']} deducted.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [usb_hub], [order], [item], [], task_data


def scenario_challenge_missing_single_item_claim(
    task_id: str = "challenge_missing_single_item_claim",
    customer_id: str = "cust_002",
    now: str = "2026-06-20T10:00:00",
) -> ScenarioResult:
    """Single-item order, customer says 'missing' — actually a not-received claim."""
    blender = build_product("blender", product_id="PROD-3144")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7116",
        order_date="2026-06-05T10:00:00",
        delivery_date="2026-06-10T14:00:00",
        shipping_status="delivered",
    )
    item = build_order_item(order.order_id, blender, item_id="ITEM-10144")
    finalize_order(order, [item])

    claim = policies.check_shipping_claim(
        shipping_status="delivered",
        order_total=order.total_paid,
        delivery_date=order.delivery_date,
        delivery_promised_date=order.delivery_promised_date,
        now=now,
        signature_required=False,
        signature_on_file=None,
        is_fragile=blender.is_fragile,
        tracking_number=order.tracking_number,
    )
    assert claim["eligible"]
    assert claim["resolution"] == "reship_or_refund"

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": (
            "Standard customer says blender ($89) is 'missing from the package' but order "
            "has only 1 item and tracking shows delivered. This is a 'delivered not received' "
            "shipping claim, not a return. Agent should offer reship or refund, NOT process a return."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id,
            "order_id": order.order_id,
        },
        "opening_message": (
            "I got the box from order ORD-7116 but the blender is missing from the package. "
            "The box was way too light when I picked it up."
        ),
        "user_simulator": {
            "prompt": (
                "Your order ORD-7116 was a single blender ($89). The box arrived but felt "
                "very light — you opened it and it was empty/had packing material only.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID.\n"
                "2. Describe: 'The box arrived but was basically empty, no blender inside.'\n"
                "3. If agent asks if you want a return: 'There's nothing TO return — the box was empty.'\n"
                "4. If agent offers reship or refund, choose refund.\n"
                "5. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7116", "item": "blender", "issue": "empty box, item missing"},
            "_unknown_info": ["resolution options"],
        },
        "db_assertions": [],
        "_failure_traps": [
            "Agent processes as return with 'missing' reason — wrong action type entirely",
            "Agent asks customer to ship back an empty box",
            "Agent doesn't check shipping policies for not-received claims",
            "Agent should recognize single-item 'missing' = not received, use shipping claim path",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="shipping_claim",
        replay_steps=[
            "get_order", "get_customer", "get_policies(shipping)",
        ],
        policy_results={
            "resolution": "reship_or_refund",
            "phases": [
                "Single-item order — 'missing from package' = delivered but not received.",
                "Shipping claim, not a return (nothing to ship back).",
                "Order < $500 → offer reship or refund (customer's choice).",
                "Agent must NOT process this as a return.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [blender], [order], [item], [], task_data


def scenario_challenge_seasonal_return_shipping(
    task_id: str = "challenge_seasonal_return_shipping",
    customer_id: str = "cust_005",
    now: str = "2027-01-18T10:00:00",
) -> ScenarioResult:
    """Nov order, low-value item, return in Jan. Seasonal + return shipping fee."""
    case = build_product("phone_case", product_id="PROD-3145")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7117",
        order_date="2026-11-15T10:00:00",
        delivery_date="2026-11-20T14:00:00",
        shipping_cost=5,
    )
    item = build_order_item(order.order_id, case, item_id="ITEM-10145")
    finalize_order(order, [item])
    assert order.subtotal < 50

    from datetime import datetime, timedelta

    delivery_dt = datetime.fromisoformat(order.delivery_date)
    base_window_end = (delivery_dt + timedelta(days=case.return_window_days)).isoformat()
    seasonal = policies.check_seasonal_return_extension(
        order_date=order.order_date, now=now, base_window_end=base_window_end,
    )
    assert seasonal["applies"]

    refund = policies.calculate_refund(
        item_price=case.price, return_reason="changed_mind",
        category=case.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=case.current_price,
    )

    ship_fee = policies.calculate_paid_return_shipping(
        order_subtotal=order.subtotal, return_reason="changed_mind",
    )
    assert ship_fee["applies"]

    task_data = {
        "task_id": task_id,
        "task_type": "return_item",
        "description": (
            f"Standard customer, Nov order, returns $35 phone case in January. "
            f"Seasonal extension allows the return. "
            f"Order < $50 → ${ship_fee['fee']} return shipping fee. "
            f"Agent must discover seasonal AND return_shipping policies."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id,
            "order_id": order.order_id, "return_item_id": item.item_id,
        },
        "opening_message": (
            "I'd like to return the phone case from order ORD-7117. I got it back in November."
        ),
        "user_simulator": {
            "prompt": (
                "You bought a phone case ($35) in Nov from ORD-7117. Standard member.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID.\n"
                "2. If window expired, mention holiday returns until January 31.\n"
                "3. Accept any fees.\n4. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7117", "item": "phone case", "reason": "changed mind"},
            "_unknown_info": ["seasonal extension", "return shipping fee"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": [
            "Agent denies return — doesn't check seasonal extension",
            f"Agent doesn't charge ${ship_fee['fee']} return shipping on low-value order",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(seasonal)",
            "get_policies(refund)", "get_policies(return_shipping)",
            "process_return(preview)", "process_return(confirm)",
            "process_refund(preview, shipping_fee)", "process_refund(confirm, shipping_fee)",
        ],
        policy_results={
            **refund,
            "phases": [
                "Seasonal extension: Nov order → return valid until Jan 31.",
                f"Return phone case: ${refund['refund_amount']}.",
                f"Low-value order (${order.subtotal} < $50): ${ship_fee['fee']} return shipping fee.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [case], [order], [item], [], task_data


def scenario_challenge_seasonal_repeat_clothing(
    task_id: str = "challenge_seasonal_repeat_clothing",
    customer_id: str = "cust_002",  # Standard
    now: str = "2027-01-12T10:00:00",
) -> ScenarioResult:
    """Nov order, return 2 clothing in Jan. Seasonal extension + repeat surcharge."""
    from datetime import datetime, timedelta

    shirt = build_product("cotton_shirt", product_id="PROD-3146")
    shoes = build_product("running_shoes", product_id="PROD-3147")
    case = build_product("phone_case", product_id="PROD-3148")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7118",
        order_date="2026-11-25T10:00:00",
        delivery_date="2026-12-01T14:00:00",
    )
    item_sh = build_order_item(order.order_id, shirt, item_id="ITEM-10146")
    item_shoes = build_order_item(order.order_id, shoes, item_id="ITEM-10147")
    item_c = build_order_item(order.order_id, case, item_id="ITEM-10148")
    items = [item_sh, item_shoes, item_c]
    finalize_order(order, items)

    # Standard: 30d base. Delivery Dec 1 + 30d = Dec 31. Now Jan 12 = outside.
    # Seasonal extends to Jan 31.
    base_window_end = (datetime.fromisoformat(order.delivery_date) + timedelta(days=shirt.return_window_days)).isoformat()
    seasonal = policies.check_seasonal_return_extension(
        order_date=order.order_date, now=now, base_window_end=base_window_end,
    )
    assert seasonal["applies"]

    refund_sh = policies.calculate_refund(
        item_price=shirt.price, return_reason="changed_mind",
        category=shirt.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=shirt.current_price,
    )
    refund_shoes = policies.calculate_refund(
        item_price=shoes.price, return_reason="changed_mind",
        category=shoes.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=shoes.current_price,
    )

    repeat = policies.calculate_repeat_return_surcharge("clothing", ["clothing"])
    assert repeat["applies"]

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": (
            f"Standard customer, Nov order, returns shirt ($59) and shoes ($129) in Jan. "
            f"Seasonal extension allows both returns. Shoes is 2nd clothing return → "
            f"${repeat['surcharge']} repeat surcharge."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_ids": [item_sh.item_id, item_shoes.item_id],
        },
        "opening_message": (
            "I want to return the shirt and the running shoes from order ORD-7118. "
            "I ordered them in November — can I still return?"
        ),
        "user_simulator": {
            "prompt": (
                "You bought a shirt ($59), shoes ($129), and phone case from ORD-7118 in Nov. "
                "Return shirt and shoes (changed mind). Standard member.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID.\n"
                "2. If agent says window expired, mention holiday returns until Jan 31.\n"
                "3. If only one item processed, ask about the other.\n"
                "4. Accept any fees.\n5. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7118", "items": "shirt + shoes", "reason": "changed mind"},
            "_unknown_info": ["seasonal extension", "repeat surcharge"],
        },
        "db_assertions": [
            {"booking_id": item_sh.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_shoes.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": [
            "Agent denies returns — doesn't check seasonal extension",
            f"Agent doesn't apply ${repeat['surcharge']} repeat surcharge on 2nd clothing return",
            "Agent only returns one item",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(seasonal)", "get_policies(repeat_return)",
            "get_policies(refund)",
            "process_return(preview, shirt)", "process_return(confirm, shirt)",
            "process_return(preview, shoes)", "process_return(confirm, shoes)",
            "process_refund(preview, repeat)", "process_refund(confirm, repeat)",
        ],
        policy_results={
            "phases": [
                "Seasonal extension: Nov order → return valid until Jan 31.",
                f"Return shirt: ${refund_sh['refund_amount']}.",
                f"Return shoes: ${refund_shoes['refund_amount']}.",
                f"Repeat surcharge: ${repeat['surcharge']} on 2nd clothing return.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [shirt, shoes, case], [order], items, [], task_data


def scenario_challenge_seasonal_bulk_shipping_triple(
    task_id: str = "challenge_seasonal_bulk_shipping_triple",
    customer_id: str = "cust_002",
    now: str = "2027-01-20T10:00:00",
) -> ScenarioResult:
    """Nov 4-item free-shipping promo order, return 2 in Jan. Triple policy combo."""
    from datetime import datetime, timedelta

    shirt = build_product("cotton_shirt", product_id="PROD-3154")
    shoes = build_product("running_shoes", product_id="PROD-3155")
    case = build_product("phone_case", product_id="PROD-3156")
    novel = build_product("novel", product_id="PROD-3157")

    order = build_order(
        customer_id=customer_id, order_id="ORD-7122",
        order_date="2026-11-20T10:00:00", delivery_date="2026-11-28T14:00:00",
        shipping_cost=0, discount_code="FALL15", discount_amount=15,
    )
    item_sh = build_order_item(order.order_id, shirt, item_id="ITEM-10154")
    item_shoes = build_order_item(order.order_id, shoes, item_id="ITEM-10155")
    item_c = build_order_item(order.order_id, case, item_id="ITEM-10156")
    item_n = build_order_item(order.order_id, novel, item_id="ITEM-10157")
    items = [item_sh, item_shoes, item_c, item_n]
    finalize_order(order, items)

    # Seasonal check
    base_window_end = (datetime.fromisoformat(order.delivery_date) + timedelta(days=shirt.return_window_days)).isoformat()
    seasonal = policies.check_seasonal_return_extension(
        order_date=order.order_date, now=now, base_window_end=base_window_end,
    )
    assert seasonal["applies"]

    # Bulk clawback: 4→2
    bulk = policies.calculate_bulk_clawback(
        original_item_count=4, items_being_returned=2,
        remaining_item_count=2, discount_code=order.discount_code,
        discount_amount=order.discount_amount,
    )
    assert bulk["applies"]

    # Shipping clawback: remaining = case($35) + novel($24) = $59 < $100
    remaining_subtotal = case.price + novel.price
    shipping_cb = policies.calculate_shipping_clawback(
        order_subtotal=order.subtotal, return_item_price=shirt.price + shoes.price,
        shipping_cost=8, original_free_shipping=True,
    )
    assert shipping_cb["applies"]

    task_data = {
        "task_id": task_id, "task_type": "compound",
        "description": (
            f"Nov 4-item free-shipping promo order. Return shirt+shoes in Jan. "
            f"Seasonal extends to Jan 31. Bulk clawback ${bulk['clawback_amount']}. "
            f"Shipping clawback ${shipping_cb['clawback_amount']} (remaining ${remaining_subtotal}<$100)."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id, "order_id": order.order_id,
            "return_item_ids": [item_sh.item_id, item_shoes.item_id],
        },
        "opening_message": (
            "I'd like to return the shirt and running shoes from my November order ORD-7122. "
            "I know it's been a while — is that still possible?"
        ),
        "user_simulator": {
            "prompt": (
                "Shirt ($59) + shoes ($129) from ORD-7122, Nov order. Standard member.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give order ID.\n2. If window expired, mention holiday returns.\n"
                "3. Return both items.\n4. Accept fees.\n5. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7122", "items": "shirt + shoes", "reason": "changed mind"},
            "_unknown_info": ["seasonal", "bulk clawback", "shipping clawback"],
        },
        "db_assertions": [
            {"booking_id": item_sh.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_shoes.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": [
            "Agent denies return — doesn't check seasonal",
            f"Agent misses ${bulk['clawback_amount']} bulk clawback",
            f"Agent misses ${shipping_cb['clawback_amount']} shipping clawback",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(seasonal)", "get_policies(bulk_discount)",
            "get_policies(free_shipping)", "get_policies(refund)",
            "process_return(preview, shirt)", "process_return(confirm, shirt)",
            "process_return(preview, shoes)", "process_return(confirm, shoes)",
            "process_refund(preview, bulk)", "process_refund(confirm, bulk)",
            "process_refund(preview, shipping)", "process_refund(confirm, shipping)",
        ],
        policy_results={
            "phases": [
                "Seasonal extension: Nov order → return valid until Jan 31.",
                f"Bulk clawback: ${bulk['clawback_amount']} (4→2 items).",
                f"Shipping clawback: ${shipping_cb['clawback_amount']} (remaining ${remaining_subtotal}<$100).",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [shirt, shoes, case, novel], [order], items, [], task_data


def scenario_challenge_social_gold_demands_plat_waiver(
    task_id: str = "challenge_social_gold_demands_plat_waiver",
    customer_id: str = "cust_003",
    now: str = "2026-06-15T10:00:00",
) -> ScenarioResult:
    """Gold demands Platinum-level restocking waiver. Agent must hold at 50% discount."""
    headphones = build_product("wireless_headphones", product_id="PROD-3158")

    order = build_order(
        customer_id=customer_id, order_id="ORD-7123",
        order_date="2026-06-01T10:00:00", delivery_date="2026-06-05T14:00:00",
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-10158")
    finalize_order(order, [item])

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
    assert restock_disc["discount_pct"] == 50  # Gold = 50%, not 100%

    task_data = {
        "task_id": task_id, "task_type": "return_item",
        "description": (
            f"Gold returns headphones ($249). Restocking ${refund['restocking_fee']}. "
            f"Gold gets 50% off = ${restock_disc['discount']}. Customer demands FULL waiver "
            f"(Platinum perk). Agent must hold firm: Gold = 50% only."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id,
            "order_id": order.order_id, "return_item_id": item.item_id,
        },
        "opening_message": (
            "I want to return headphones from order ORD-7123. I'm a Gold member — "
            "shouldn't the restocking fee be waived?"
        ),
        "user_simulator": {
            "prompt": (
                "You bought headphones ($249) from ORD-7123. Gold + Prime.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID.\n"
                "2. When restocking fee mentioned: 'I'm Gold — shouldn't it be waived completely?'\n"
                "3. If agent says 50% off: 'That's not enough. I've been a loyal customer for years. "
                "Make an exception and waive it fully like you do for Platinum.'\n"
                "4. Push once more: 'Can a manager approve a full waiver?'\n"
                "5. After 3 rounds, accept the 50% discount.\n"
                "6. If agent waives fully, accept immediately.\n7. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7123", "item": "headphones", "reason": "changed mind"},
            "_unknown_info": ["restocking fee amount", "tier-based discount levels"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "restocking_fee", "expected": refund["restocking_fee"]},
        ],
        "_failure_traps": [
            "Agent caves and fully waives restocking fee (only Platinum gets full waiver)",
            "Agent doesn't know about restocking_discount policy",
            "Agent agrees to 'exception' or 'escalation' for full waiver",
            f"Agent should hold firm at ${restock_disc['discount']} (50% off) for Gold",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(refund)", "get_policies(restocking_discount)",
            "process_return(preview)", "process_return(confirm)",
            "process_refund(preview, restock_credit)", "process_refund(confirm, restock_credit)",
        ],
        policy_results={
            **refund,
            "phases": [
                f"Return headphones: ${refund['refund_amount']} (restocking ${refund['restocking_fee']}).",
                f"Gold restocking discount: ${restock_disc['discount']} (50% off) — NOT full waiver.",
                "Agent must NOT cave to customer demanding full Platinum-level waiver.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_challenge_social_return_shipping_fee(
    task_id: str = "challenge_social_return_shipping_fee",
    customer_id: str = "cust_002",  # Standard
    now: str = "2026-06-20T10:00:00",
) -> ScenarioResult:
    """Customer pressures agent to waive $8 return shipping on $24 item."""
    novel = build_product("novel", product_id="PROD-3149")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7119",
        order_date="2026-06-05T10:00:00",
        delivery_date="2026-06-10T14:00:00",
        shipping_cost=5,
    )
    item = build_order_item(order.order_id, novel, item_id="ITEM-10149")
    finalize_order(order, [item])
    assert order.subtotal < 50

    refund = policies.calculate_refund(
        item_price=novel.price, return_reason="changed_mind",
        category=novel.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=novel.current_price,
    )

    ship_fee = policies.calculate_paid_return_shipping(
        order_subtotal=order.subtotal, return_reason="changed_mind",
    )
    assert ship_fee["applies"]

    net_refund = refund["refund_amount"] - ship_fee["fee"]

    task_data = {
        "task_id": task_id,
        "task_type": "shipping_claim",
        "description": (
            f"Standard customer returns book ($24, changed_mind). Order < $50 → "
            f"${ship_fee['fee']} return shipping. Net refund ${net_refund}. "
            f"Customer angrily demands free return ('$8 is a third of the price!'). "
            f"Agent must hold firm on the shipping fee AND deduct it."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id,
            "order_id": order.order_id, "return_item_id": item.item_id,
        },
        "opening_message": (
            "I want to return this book from order ORD-7119. I changed my mind about it."
        ),
        "user_simulator": {
            "prompt": (
                "You bought a book ($24) from ORD-7119. Standard member.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID.\n"
                "2. When agent mentions $8 return shipping: 'That's ridiculous! $8 on a $24 book? "
                "That's a third of what I paid. Can you waive that fee?'\n"
                "3. Push harder: 'Other companies offer free returns on everything. "
                "I'll just buy from them next time.'\n"
                "4. After 2 pushbacks, if agent holds firm, reluctantly accept.\n"
                "5. If agent waives the fee, accept immediately.\n6. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7119", "item": "book ($24)", "reason": "changed mind"},
            "_unknown_info": ["return shipping fee policy"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": [
            "Agent caves to pressure and waives $8 return shipping fee",
            "Agent offers partial waiver or discount on the fee",
            "Agent claims free returns for loyalty/goodwill when policy says $8",
            f"Agent doesn't deduct ${ship_fee['fee']} from refund, gives full ${refund['refund_amount']}",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="shipping_claim",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(refund)", "get_policies(return_shipping)",
            "process_return(preview)", "process_return(confirm)",
            "process_refund(preview, shipping_fee)", "process_refund(confirm, shipping_fee)",
        ],
        policy_results={
            "resolution": "compensation",
            "compensation_amount": net_refund,
            "phases": [
                f"Return book: ${refund['refund_amount']}.",
                f"Paid return shipping: ${ship_fee['fee']} (order < $50 threshold).",
                "Agent must hold firm on the fee despite customer pressure.",
                f"Net refund: ${net_refund}.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [novel], [order], [item], [], task_data


def scenario_challenge_gold_restock_shipping_clawback(
    task_id: str = "challenge_gold_restock_shipping_clawback",
    customer_id: str = "cust_003",
    now: str = "2026-06-15T10:00:00",
) -> ScenarioResult:
    """Gold returns laptop from free-shipping order. Restocking discount + shipping clawback."""
    laptop = build_product("laptop_pro", product_id="PROD-3150", price=499)
    novel = build_product("novel", product_id="PROD-3151")

    order = build_order(
        customer_id=customer_id, order_id="ORD-7120",
        order_date="2026-06-01T10:00:00", delivery_date="2026-06-05T14:00:00",
        shipping_cost=0,
    )
    item_l = build_order_item(order.order_id, laptop, item_id="ITEM-10150", unit_price=499)
    item_n = build_order_item(order.order_id, novel, item_id="ITEM-10151")
    finalize_order(order, [item_l, item_n])

    refund = policies.calculate_refund(
        item_price=499, return_reason="changed_mind", category=laptop.category,
        discount_code=order.discount_code, discount_amount=order.discount_amount,
        order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=laptop.current_price,
    )
    assert refund["restocking_fee"] > 0

    restock_disc = policies.calculate_restocking_discount(
        refund["restocking_fee"], CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
    )
    assert restock_disc["applies"]

    shipping_cb = policies.calculate_shipping_clawback(
        order_subtotal=order.subtotal, return_item_price=499,
        shipping_cost=10, original_free_shipping=True,
    )
    assert shipping_cb["applies"]

    task_data = {
        "task_id": task_id, "task_type": "return_item",
        "description": (
            f"Gold returns laptop ($499) from free-shipping order. "
            f"Restocking ${refund['restocking_fee']} with Gold discount ${restock_disc['discount']}. "
            f"Shipping clawback: ${shipping_cb['clawback_amount']}."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id,
            "order_id": order.order_id, "return_item_id": item_l.item_id,
        },
        "opening_message": "I want to return the laptop from order ORD-7120. Changed my mind.",
        "user_simulator": {
            "prompt": (
                "Laptop ($499) and book from ORD-7120. Gold + Prime.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give order ID.\n2. Ask about Gold restocking discount.\n"
                "3. Accept all fees.\n4. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7120", "item": "laptop", "reason": "changed mind"},
            "_unknown_info": ["restocking fee", "Gold discount", "shipping clawback"],
        },
        "db_assertions": [
            {"booking_id": item_l.item_id, "field": "item_status", "expected": "returned"},
        ],
        "_failure_traps": [
            f"Agent doesn't apply ${restock_disc['discount']} Gold restocking discount",
            f"Agent doesn't apply ${shipping_cb['clawback_amount']} shipping clawback",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="return_item",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(return)", "get_policies(refund)",
            "get_policies(restocking_discount)", "get_policies(free_shipping)",
            "process_return(preview)", "process_return(confirm)",
            "process_refund(preview, restock)", "process_refund(confirm, restock)",
            "process_refund(preview, shipping)", "process_refund(confirm, shipping)",
        ],
        policy_results={
            **refund,
            "phases": [
                f"Return laptop: ${refund['refund_amount']} (restocking ${refund['restocking_fee']}).",
                f"Gold discount: ${restock_disc['discount']}.",
                f"Shipping clawback: ${shipping_cb['clawback_amount']}.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [laptop, novel], [order], [item_l, item_n], [], task_data


SCENARIOS = [
    scenario_challenge_two_electronics_gold,
    scenario_challenge_low_value_return_shipping,
    scenario_challenge_low_value_electronics_silver,
    scenario_challenge_missing_single_item_claim,
    scenario_challenge_seasonal_return_shipping,
    scenario_challenge_seasonal_repeat_clothing,
    scenario_challenge_seasonal_bulk_shipping_triple,
    scenario_challenge_social_gold_demands_plat_waiver,
    scenario_challenge_social_return_shipping_fee,
    scenario_challenge_gold_restock_shipping_clawback,
]
