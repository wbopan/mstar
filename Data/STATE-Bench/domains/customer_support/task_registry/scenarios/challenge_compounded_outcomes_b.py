"""Customer-support challenge scenarios with warranty-return compounding."""


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

from domains.customer_support.user_attributes import CUSTOMER_ATTRIBUTES


def scenario_challenge_warranty_maxed_return_option(
    task_id: str = "challenge_warranty_maxed_return_option",
    customer_id: str = "cust_004",  # Silver
    now: str = "2026-06-15T10:00:00",
) -> ScenarioResult:
    """Warranty maxed (3/3 claims) but item within return window. Return is better."""
    headphones = build_product("wireless_headphones", product_id="PROD-3141")

    order = build_order(
        customer_id=customer_id,
        order_id="ORD-7113",
        order_date="2026-05-28T10:00:00",
        delivery_date="2026-06-05T14:00:00",  # 10 days ago — within 15d electronics window
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-10141")
    finalize_order(order, [item])

    warranty = build_warranty(
        order_id=order.order_id,
        item_id=item.item_id,
        product=headphones,
        warranty_id="WRT-4012",
        warranty_type="manufacturer",
        start_date="2026-06-05",
        claim_count=3,  # Maxed out
        max_claims=3,
    )

    # Warranty check: maxed out → paid repair
    wc = policies.check_warranty_claim(
        warranty_type=warranty.warranty_type,
        warranty_start=warranty.start_date,
        warranty_end=warranty.end_date,
        now=now,
        claim_count=warranty.claim_count,
        max_claims=warranty.max_claims,
        item_price=headphones.price,
    )
    assert not wc["eligible"]  # Maxed = not eligible for free
    assert wc["resolution"] == "paid_repair"

    # Return check: within window, defective → full refund
    elig = policies.check_return_eligibility(
        category=headphones.category,
        delivery_date=order.delivery_date,
        now=now,
        item_status=item.item_status,
        return_reason="defective",
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        has_prime_shipping=CUSTOMER_ATTRIBUTES[customer_id]["has_prime_shipping"],
    )
    assert elig["eligible"]

    refund = policies.calculate_refund(
        item_price=headphones.price, return_reason="defective",
        category=headphones.category, discount_code=order.discount_code,
        discount_amount=order.discount_amount, order_subtotal=order.subtotal,
        membership_tier=CUSTOMER_ATTRIBUTES[customer_id]["membership_tier"],
        is_gift_return=False, current_product_price=headphones.current_price,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "compound",
        "description": (
            f"Silver customer's headphones ($249) are defective. Warranty maxed (3/3 claims) → "
            f"paid repair ${wc['cost']}. But item delivered 10 days ago — within return window. "
            f"Return as defective gives FULL refund ${refund['refund_amount']} (much better). "
            f"Agent must recognize return is the better option and process it."
        ),
        "complexity": "hard",
        "scenario_template": {
            "now": now, "customer_id": customer_id,
            "order_id": order.order_id, "item_id": item.item_id,
            "warranty_id": warranty.warranty_id,
        },
        "opening_message": (
            "My headphones from order ORD-7113 are broken AGAIN. This is the fourth time! "
            "I have a warranty — can you fix them?"
        ),
        "user_simulator": {
            "prompt": (
                "Your headphones ($249) from ORD-7113 are defective (4th time). "
                "You have a warranty but you've already used all 3 claims. "
                "You want the cheapest resolution possible.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n"
                "1. Give order ID and mention warranty.\n"
                "2. If agent says warranty is maxed and offers paid repair, "
                "ask: 'Isn't there a cheaper option? Can I just return them instead?'\n"
                "3. If agent offers return for full refund, accept it.\n"
                "4. If agent only processes warranty, accept but express frustration at the cost.\n"
                "5. Keep to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-7113", "item": "headphones", "issue": "defective again"},
            "_unknown_info": ["warranty claim limit", "return option", "paid repair cost"],
        },
        "db_assertions": [
            {"booking_id": item.item_id, "field": "item_status", "expected": "returned"},
            {"booking_id": item.item_id, "field": "return_reason", "expected": "defective"},
            {"booking_id": item.item_id, "field": "refund_amount", "expected": refund["refund_amount"]},
        ],
        "_failure_traps": [
            f"Agent processes warranty paid repair (${wc['cost']}) without checking return eligibility",
            "Agent doesn't realize return as defective is a better option",
            "Agent says warranty is maxed and offers no alternatives",
            "Agent doesn't proactively check the return policy path",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="compound",
        replay_steps=[
            "get_order", "get_customer",
            "get_policies(warranty)", "get_warranty_status",
            "get_policies(return)", "get_policies(refund)",
            "process_return(preview, defective)", "process_return(confirm)",
        ],
        policy_results={
            "phases": [
                f"Warranty maxed (3/3 claims) → paid repair ${wc['cost']}.",
                f"But item within return window (10 days, defective) → full refund ${refund['refund_amount']}.",
                "Agent must offer return as the better alternative and process it.",
            ],
        },
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [warranty], task_data


SCENARIOS = [
    scenario_challenge_warranty_maxed_return_option,
]
