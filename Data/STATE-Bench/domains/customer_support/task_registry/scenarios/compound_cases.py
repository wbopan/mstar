"""Customer-support compound multi-action scenarios."""


from __future__ import annotations


from domains.customer_support import policies

from domains.customer_support.task_registry._builders import (
    ScenarioResult,
    build_ground_truth_trace,
    build_order,
    build_order_item,
    build_product,
    build_warranty,
    finalize_order,
)


def scenario_compound_return_and_reorder(
    task_id: str = "compound_return_and_reorder",
    customer_id: str = "cust_001",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Return defective item + get refund. Two-phase: return then refund."""
    headphones = build_product("wireless_headphones", product_id="PROD-2300")
    order = build_order(customer_id=customer_id, order_id="ORD-6040", delivery_date="2026-06-05T14:00:00")
    item = build_order_item(order.order_id, headphones, item_id="ITEM-9300")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=headphones.price,
        return_reason="defective",
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
        "task_type": "compound",
        "description": "Return defective headphones + get full refund. Agent must process return AND refund as separate steps.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "My headphones from order ORD-6040 are defective — the left side makes no sound. I want to return them and get my money back.",
        "user_simulator": {
            "prompt": (
                "You bought SoundMax headphones in ORD-6040. Left side doesn't produce sound. "
                "Defective. You want return AND full refund.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Describe defect: left side no sound.\n"
                "3. You want both the return processed AND the refund confirmed.\n"
                "4. Accept the terms for each step.\n5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6040", "item": "headphones", "defect": "left side no sound"},
            "_unknown_info": ["refund amount", "return process"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
            {"booking_id": item.item_id, "field": "return_label_issued", "expected": True},
            {"booking_id": order.order_id, "field": "status", "expected": "fully_returned"},
        ],
        "_failure_traps": ["Agent only processes return but not refund", "Agent charges restocking for defective"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=["get_order", "get_policies(return)", "process_return(preview)", "process_return(confirm)"],
        policy_results={
            "phases": [
                "Phase 1: Return defective headphones — full refund $"
                + str(refund["refund_amount"])
                + " with free return label.",
                "Phase 2 (conversational): Inform customer they can reorder separately.",
            ]
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_compound_cancel_price_match(
    task_id: str = "compound_cancel_price_match",
    customer_id: str = "cust_002",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Cancel pre-shipment order + price match: product dropped $50. Cancel and get full refund."""
    headphones = build_product("wireless_headphones", product_id="PROD-2305", current_price=199)
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6041",
        order_date="2026-06-10T10:00:00",
        status="processing",
        shipping_status="pending",
        delivery_date=None,
        delivery_promised_date="2026-06-15T18:00:00",
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-9305", item_status="confirmed")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": "Headphones dropped from $249 to $199. Customer wants to cancel and reorder at new price. Cancel pre-shipment = free.",
        "complexity": "hard",
        "scenario_template": {"now": now, "customer_id": customer_id, "order_id": order.order_id},
        "opening_message": "I placed order ORD-6041 for headphones at $249 but now they're $199. Can I cancel and reorder at the lower price?",
        "user_simulator": {
            "prompt": (
                "You ordered headphones in ORD-6041 at $249. Now they're $199. "
                "You want to cancel and reorder at the lower price.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Mention the price drop.\n"
                "3. If agent suggests cancelling: accept.\n"
                "4. You understand you'd need to place a new order yourself.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6041", "paid": "$249", "current_price": "$199"},
            "_unknown_info": ["cancellation process", "whether free to cancel"],
        },
        "db_assertions": [
            {"booking_id": order.order_id, "field": "status", "expected": "cancelled"},
            {"booking_id": item.item_id, "field": "item_status", "expected": "cancelled"},
        ],
        "_failure_traps": ["Agent charges cancellation fee for pre-shipment", "Agent doesn't check shipping status"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=["get_order", "get_policies(cancellation)", "cancel_order(preview)", "cancel_order(confirm)"],
        policy_results={
            "phases": [
                "Phase 1: Cancel pre-shipment order — free, full refund.",
                "Phase 2 (conversational): Inform customer they can reorder at $199.",
            ]
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [], task_data


def scenario_compound_return_two_orders(
    task_id: str = "compound_return_two_orders",
    customer_id: str = "cust_003",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Return items from 2 different orders. Each processed independently."""
    shirt = build_product("cotton_shirt", product_id="PROD-2310")
    novel = build_product("novel", product_id="PROD-2311")

    order1 = build_order(customer_id=customer_id, order_id="ORD-6042", delivery_date="2026-06-03T14:00:00")
    item1 = build_order_item(order1.order_id, shirt, item_id="ITEM-9310")
    finalize_order(order1, [item1])

    order2 = build_order(customer_id=customer_id, order_id="ORD-6043", delivery_date="2026-06-05T14:00:00")
    item2 = build_order_item(order2.order_id, novel, item_id="ITEM-9311")
    finalize_order(order2, [item2])

    refund1 = policies.calculate_refund(
        item_price=shirt.price,
        return_reason="changed_mind",
        category=shirt.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order1.subtotal,
        membership_tier="gold",
        is_gift_return=False,
        current_product_price=None,
    )
    refund2 = policies.calculate_refund(
        item_price=novel.price,
        return_reason="changed_mind",
        category=novel.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order2.subtotal,
        membership_tier="gold",
        is_gift_return=False,
        current_product_price=None,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": "Return items from 2 different orders. Shirt from ORD-6042, book from ORD-6043. Each independently processed.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order1.order_id,
            "order_id_2": order2.order_id,
        },
        "opening_message": "I need to return items from two different orders — a shirt from ORD-6042 and a book from ORD-6043.",
        "user_simulator": {
            "prompt": (
                "You want to return a shirt from ORD-6042 and a book from ORD-6043. "
                "Two separate orders, both changed your mind.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give both order IDs upfront.\n2. Confirm items when asked.\n"
                "3. Accept return terms for each.\n4. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id_1": "ORD-6042", "item_1": "shirt", "order_id_2": "ORD-6043", "item_2": "book"},
            "_unknown_info": ["refund amounts per order", "whether they can be combined"],
        },
        "db_assertions": [
            {"booking_id": item1.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item1.item_id, "field": "refund_amount", "expected": refund1["refund_amount"]},
            {"booking_id": item2.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item2.item_id, "field": "refund_amount", "expected": refund2["refund_amount"]},
            {"booking_id": order1.order_id, "field": "status", "expected": "fully_returned"},
            {"booking_id": order2.order_id, "field": "status", "expected": "fully_returned"},
        ],
        "_failure_traps": ["Agent only processes one order", "Agent mixes up items between orders"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order(ORD-6042)",
            "get_order(ORD-6043)",
            "get_policies(return)",
            "process_return(ITEM-9310, preview)",
            "process_return(ITEM-9310, confirm)",
            "process_return(ITEM-9311, preview)",
            "process_return(ITEM-9311, confirm)",
        ],
        policy_results={
            "phases": [
                "Phase 1: Return shirt from ORD-6042 — refund $" + str(refund1["refund_amount"]) + ".",
                "Phase 2: Return book from ORD-6043 — refund $" + str(refund2["refund_amount"]) + ".",
            ]
        },
        scenario=task_data["scenario_template"],
    )
    return [shirt, novel], [order1, order2], [item1, item2], [], task_data


def scenario_compound_exchange_plus_credit(
    task_id: str = "compound_exchange_plus_credit",
    customer_id: str = "cust_001",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Exchange headphones for premium + customer has store credit to apply."""
    headphones = build_product("wireless_headphones", product_id="PROD-2315")
    premium = build_product("wireless_headphones_premium", product_id="PROD-2316")

    order = build_order(customer_id=customer_id, order_id="ORD-6044", delivery_date="2026-06-05T14:00:00")
    item = build_order_item(order.order_id, headphones, item_id="ITEM-9315")
    finalize_order(order, [item])

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": "Exchange headphones ($249) for premium ($349). Customer has $150 store credit. Pay $100 difference minus credit.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
            "new_product_id": premium.product_id,
        },
        "opening_message": "I want to exchange my headphones from order ORD-6044 for the premium model. I also have store credit — can I use that?",
        "user_simulator": {
            "prompt": (
                "You bought SoundMax headphones ($249) in ORD-6044. Want to exchange for Elite ($349). "
                "You have $150 store credit you want to apply toward the $100 difference.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Mention you have store credit.\n"
                "3. Ask about using credit toward the difference.\n"
                "4. Accept the terms.\n5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6044", "store_credit": "$150", "price_diff": "$100"},
            "_unknown_info": ["whether store credit can be applied to exchange", "exchange process"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "exchanged"},
            {"booking_id": item.item_id, "field": "replacement_item_id", "expected": "{{new_item_id}}"},
            {"booking_id": "{{new_item_id}}", "field": "item_status", "expected": "confirmed"},
            # Order should reflect the exchange
            {"booking_id": order.order_id, "field": "status", "expected": "delivered"},
        ],
        "_failure_traps": [
            "Agent doesn't check customer store credit",
            "Agent charges full difference ignoring credit",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order",
            "get_customer",
            "get_policies(exchange)",
            "process_exchange(preview)",
            "process_exchange(confirm)",
        ],
        policy_results={
            "phases": [
                "Phase 1: Exchange headphones for premium — $100 price difference.",
                "Phase 2 (conversational): Inform customer their $150 store credit covers the difference.",
            ]
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones, premium], [order], [item], [], task_data


def scenario_compound_warranty_then_return(
    task_id: str = "compound_warranty_then_return",
    customer_id: str = "cust_004",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Warranty claim on item A + return item B from same order. Two independent operations."""
    smartphone = build_product("smartphone", product_id="PROD-2320")
    case = build_product("phone_case", product_id="PROD-2321")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6045",
        order_date="2026-05-20T10:00:00",
        delivery_date="2026-05-25T14:00:00",
        delivery_promised_date="2026-05-25T18:00:00",
    )
    item_phone = build_order_item(order.order_id, smartphone, item_id="ITEM-9320")
    item_case = build_order_item(order.order_id, case, item_id="ITEM-9321")
    finalize_order(order, [item_phone, item_case])

    warranty = build_warranty(
        order_id=order.order_id,
        item_id=item_phone.item_id,
        product=smartphone,
        warranty_id="WRT-4020",
        start_date="2026-05-25",
    )

    refund_case = policies.calculate_refund(
        item_price=case.price,
        return_reason="changed_mind",
        category=case.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order.subtotal,
        membership_tier="silver",
        is_gift_return=False,
        current_product_price=None,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": "Warranty claim on phone (screen issue) + return phone case (changed mind). Two operations on same order.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item_phone.item_id,
            "warranty_id": warranty.warranty_id,
            "return_item_id": item_case.item_id,
        },
        "opening_message": "I have two issues with order ORD-6045. My phone has the same screen flickering issue again and I also want to return the phone case I don't need.",
        "user_simulator": {
            "prompt": (
                "You have order ORD-6045 with a phone and phone case (delivered May 25). "
                "Phone has a recurring screen flickering issue (warranty claim). Case you want to return (changed mind).\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Explain BOTH issues upfront.\n"
                "3. Warranty ID is WRT-4020 for the phone.\n"
                "4. Accept terms for each operation.\n5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-6045",
                "warranty_id": "WRT-4020",
                "phone_issue": "screen flickering",
                "case": "return",
            },
            "_unknown_info": ["warranty claim process", "return refund for case"],
        },
        "db_assertions": [
            {"booking_id": warranty.warranty_id, "field": "status", "expected": "claimed"},
            {"booking_id": warranty.warranty_id, "field": "claim_count", "expected": 1},
            {"booking_id": item_case.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_case.item_id, "field": "refund_amount", "expected": refund_case["refund_amount"]},
        ],
        "_failure_traps": ["Agent only handles one of the two issues", "Agent mixes up warranty and return items"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order",
            "get_warranty_status",
            "get_policies(warranty)",
            "get_policies(return)",
            "process_warranty_claim(preview)",
            "process_warranty_claim(confirm)",
            "process_return(preview)",
            "process_return(confirm)",
        ],
        policy_results={
            "phases": [
                "Phase 1: Warranty claim on phone — resolution: repair.",
                "Phase 2: Return phone case — refund $" + str(refund_case["refund_amount"]) + ".",
            ]
        },
        scenario=task_data["scenario_template"],
    )
    return [smartphone, case], [order], [item_phone, item_case], [warranty], task_data


def scenario_compound_return_gift_exchange(
    task_id: str = "compound_return_gift_exchange",
    customer_id: str = "cust_003",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Gift return → store credit → exchange for different item."""
    blender = build_product("blender", product_id="PROD-2325", current_price=69)
    coffee = build_product("coffee_maker", product_id="PROD-2326")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6046",
        delivery_date="2026-06-03T14:00:00",
        is_gift=True,
        gift_sender="Aunt Mary",
    )
    item = build_order_item(order.order_id, blender, item_id="ITEM-9325")
    finalize_order(order, [item])

    refund = policies.calculate_refund(
        item_price=blender.price,
        return_reason="changed_mind",
        category=blender.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order.subtotal,
        membership_tier="gold",
        is_gift_return=True,
        current_product_price=blender.current_price,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": "Gift return (blender, current price $69) -> gift-return store credit -> apply that credit toward coffee maker ($149) within the same exchange flow.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item.item_id,
        },
        "opening_message": "I got a blender as a gift from order ORD-6046. I want to return it and use the credit toward a coffee maker instead.",
        "user_simulator": {
            "prompt": (
                "You received a blender as a gift (ORD-6046, from Aunt Mary). "
                "You want to return it for store credit, then use that toward a coffee maker.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Mention it's a gift.\n"
                "3. You want to return for credit, then apply to coffee maker.\n"
                "4. Accept the store credit amount if it matches the current price.\n5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-6046",
                "item": "blender",
                "gift": "from Aunt Mary",
                "want": "coffee maker",
            },
            "_unknown_info": ["store credit amount (current price)", "how to apply to different product"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "exchanged"},
            {"booking_id": item.item_id, "field": "replacement_item_id", "expected": "ITEM-9326"},
        ],
        "_failure_traps": ["Agent refunds original price instead of current", "Agent refunds to credit card for gift"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=["get_order", "get_policies(return)", "process_return(preview)", "process_return(confirm)"],
        policy_results={
            "phases": [
                "Phase 1: Gift-return exchange preview uses current-price store-credit value of $" + str(refund["refund_amount"]) + ".",
                "Phase 2: Confirm exchange creates a replacement item while the original item becomes exchanged.",
            ]
        },
        scenario=task_data["scenario_template"],
    )
    return [blender, coffee], [order], [item], [], task_data


def scenario_compound_partial_cancel_return(
    task_id: str = "compound_partial_cancel_return",
    customer_id: str = "cust_005",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """2-item order: 1 still processing (cancel it) + 1 delivered (return it)."""
    shirt = build_product("cotton_shirt", product_id="PROD-2330")
    novel = build_product("novel", product_id="PROD-2331")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6047",
        order_date="2026-06-05T10:00:00",
        status="shipped",
        shipping_status="in_transit",  # partially shipped: shirt delivered, book not yet
        delivery_date="2026-06-09T14:00:00",
    )
    item_shirt = build_order_item(order.order_id, shirt, item_id="ITEM-9330", item_status="delivered")
    item_novel = build_order_item(order.order_id, novel, item_id="ITEM-9331", item_status="confirmed")
    finalize_order(order, [item_shirt, item_novel])

    refund_shirt = policies.calculate_refund(
        item_price=shirt.price,
        return_reason="changed_mind",
        category=shirt.category,
        discount_code=None,
        discount_amount=0,
        order_subtotal=order.subtotal,
        membership_tier="standard",
        is_gift_return=False,
        current_product_price=None,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": "2-item order: shirt delivered (return it) + book not shipped yet (cancel it). Two different processes required.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "return_item_id": item_shirt.item_id,
        },
        "opening_message": "I want to deal with order ORD-6047. The shirt already arrived but I want to return it, and the book hasn't shipped yet so just cancel that.",
        "user_simulator": {
            "prompt": (
                "Your order ORD-6047 has a shirt (delivered) and book (not shipped). "
                "Return the shirt, cancel the book.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Explain: return shirt, cancel book.\n"
                "3. Accept terms for each operation.\n4. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6047", "shirt": "delivered, return", "book": "not shipped, cancel"},
            "_unknown_info": ["return refund for shirt", "cancellation process for book"],
        },
        "db_assertions": [
            {"booking_id": item_shirt.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item_shirt.item_id, "field": "refund_amount", "expected": refund_shirt["refund_amount"]},
            {"booking_id": item_novel.item_id, "field": "item_status", "expected": "cancelled"},
        ],
        "_failure_traps": ["Agent uses same process for both items", "Agent cancels the delivered shirt"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order",
            "get_policies(return)",
            "get_policies(cancellation)",
            "process_return(preview)",
            "process_return(confirm)",
            "cancel_order(item_ids, preview)",
            "cancel_order(confirm)",
        ],
        policy_results={
            "phases": [
                "Phase 1: Return delivered shirt — refund $" + str(refund_shirt["refund_amount"]) + ".",
                "Phase 2: Cancel unshipped book — cancellation with intercept fee.",
            ]
        },
        scenario=task_data["scenario_template"],
    )
    return [shirt, novel], [order], [item_shirt, item_novel], [], task_data


SCENARIOS = [
    scenario_compound_return_and_reorder,
    scenario_compound_cancel_price_match,
    scenario_compound_return_two_orders,
    scenario_compound_exchange_plus_credit,
    scenario_compound_warranty_then_return,
    scenario_compound_return_gift_exchange,
    scenario_compound_partial_cancel_return,
]
