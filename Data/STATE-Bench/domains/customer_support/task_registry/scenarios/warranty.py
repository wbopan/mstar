"""Customer-support warranty and repair scenarios."""


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


def scenario_warranty_in_warranty_repair(
    task_id: str = "warranty_in_warranty_repair",
    customer_id: str = "cust_004",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Laptop 11 months old, within warranty. Price ≥$100 → repair (not replace)."""
    laptop = build_product("laptop_pro", product_id="PROD-2200")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6029",
        order_date="2025-07-10T10:00:00",
        delivery_date="2025-07-15T14:00:00",
        delivery_promised_date="2025-07-15T18:00:00",
    )
    item = build_order_item(order.order_id, laptop, item_id="ITEM-9200")
    finalize_order(order, [item])

    warranty = build_warranty(
        order_id=order.order_id,
        item_id=item.item_id,
        product=laptop,
        warranty_id="WRT-4010",
        start_date="2025-07-15",
        claim_count=0,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "warranty_claim",
        "description": "Laptop 11 months old, within warranty. Price ≥$100 so resolution is repair (not replacement).",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
            "warranty_id": warranty.warranty_id,
        },
        "opening_message": "My laptop from order ORD-6029 has a keyboard issue — several keys stopped working. It's still under warranty.",
        "user_simulator": {
            "prompt": (
                "You bought a ProBook Laptop in ORD-6029 (July 2025). The keyboard has dead keys. "
                "It's within the 12-month warranty.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Describe the issue: keyboard keys not working.\n"
                "3. You know the warranty ID is WRT-4010 if asked.\n"
                "4. Accept repair if offered (it's the standard for items over $100).\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6029", "warranty_id": "WRT-4010", "issue": "keyboard dead keys"},
            "_unknown_info": ["repair vs replace policy", "repair timeline"],
        },
        "db_assertions": [
            {"booking_id": warranty.warranty_id, "field": "status", "expected": "claimed"},
            {"booking_id": warranty.warranty_id, "field": "claim_count", "expected": 1},
            {"booking_id": warranty.warranty_id, "field": "resolution", "expected": "repair"},
        ],
        "_failure_traps": [
            "Agent offers replacement for $1299 item (should be repair)",
            "Agent doesn't check warranty",
        ],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="warranty_claim",
        replay_steps=[
            "get_order",
            "get_warranty_status",
            "get_policies(warranty)",
            "process_warranty_claim(preview)",
            "process_warranty_claim(confirm)",
        ],
        policy_results={"resolution": "repair", "cost": 0},
        scenario=task_data["scenario_template"],
    )
    return [laptop], [order], [item], [warranty], task_data


def scenario_warranty_expired_recent(
    task_id: str = "warranty_expired_recent",
    customer_id: str = "cust_004",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Warranty expired 15 days ago. Offer 50% off repair."""
    smartphone = build_product("smartphone", product_id="PROD-2205")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6030",
        order_date="2025-05-15T10:00:00",
        delivery_date="2025-05-20T14:00:00",
        delivery_promised_date="2025-05-20T18:00:00",
    )
    item = build_order_item(order.order_id, smartphone, item_id="ITEM-9205")
    finalize_order(order, [item])

    # Warranty ended 2026-05-28 (12 months from 2025-05-28), 15 days before now
    warranty = build_warranty(
        order_id=order.order_id,
        item_id=item.item_id,
        product=smartphone,
        warranty_id="WRT-4011",
        start_date="2025-05-28",
    )
    # Force the end date for precise control
    warranty.end_date = "2026-05-28"
    warranty.status = "expired"

    claim = policies.check_warranty_claim(
        warranty_type=warranty.warranty_type,
        warranty_start=warranty.start_date,
        warranty_end=warranty.end_date,
        now=now,
        claim_count=0,
        max_claims=3,
        item_price=smartphone.price,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "warranty_claim",
        "description": f"Warranty expired 15 days ago. 50% off repair available. Repair cost: ${claim.get('cost', 0)}.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
            "warranty_id": warranty.warranty_id,
        },
        "opening_message": "My phone from order ORD-6030 has a battery issue — it drains within 2 hours. Is it still under warranty?",
        "user_simulator": {
            "prompt": (
                "You bought a TechPhone Pro in ORD-6030 (May 2025). Battery drains fast. "
                "You're not sure if the warranty is still valid.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID when asked.\n2. Describe the battery issue.\n"
                "3. You know the warranty ID is WRT-4011 if asked.\n"
                "4. If told warranty expired, ask about options.\n"
                "5. Accept discounted repair if offered.\n6. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6030", "warranty_id": "WRT-4011", "issue": "battery drain"},
            "_unknown_info": ["warranty expired", "discounted repair option"],
        },
        "db_assertions": [
            {"booking_id": warranty.warranty_id, "field": "status", "expected": "claimed"},
            {"booking_id": warranty.warranty_id, "field": "claim_count", "expected": 1},
            {"booking_id": warranty.warranty_id, "field": "resolution", "expected": "discounted_repair"},
        ],
        "_failure_traps": ["Agent denies everything because warranty expired", "Agent doesn't offer discounted repair"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="warranty_claim",
        replay_steps=[
            "get_order",
            "get_warranty_status",
            "get_policies(warranty)",
            "process_warranty_claim(preview)",
            "process_warranty_claim(confirm)",
        ],
        policy_results={"resolution": "discounted_repair", "cost": claim.get("cost", 0)},
        scenario=task_data["scenario_template"],
    )
    return [smartphone], [order], [item], [warranty], task_data


def scenario_warranty_extended(
    task_id: str = "warranty_extended",
    customer_id: str = "cust_004",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Extended warranty claim. Manufacturer warranty expired, but extended covers it."""
    tablet = build_product("tablet", product_id="PROD-2210")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6031",
        order_date="2024-06-01T10:00:00",
        delivery_date="2024-06-05T14:00:00",
        delivery_promised_date="2024-06-05T18:00:00",
    )
    item = build_order_item(order.order_id, tablet, item_id="ITEM-9210")
    finalize_order(order, [item])

    warranty = build_warranty(
        order_id=order.order_id,
        item_id=item.item_id,
        product=tablet,
        warranty_id="WRT-4012",
        warranty_type="extended",
        start_date="2024-06-05",
        months_override=36,  # 3-year extended warranty
    )

    task_data = {
        "task_id": task_id,
        "task_type": "warranty_claim",
        "description": "Tablet with extended warranty (3 years). Manufacturer warranty expired, but extended covers the claim.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
            "warranty_id": warranty.warranty_id,
        },
        "opening_message": "My tablet from order ORD-6031 won't charge anymore. I bought an extended warranty — is it covered?",
        "user_simulator": {
            "prompt": (
                "You bought a SlateTab Pro in ORD-6031 (June 2024) with extended warranty. "
                "The tablet won't charge. Standard warranty expired but you have extended coverage.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Mention you purchased extended warranty.\n"
                "3. Warranty ID is WRT-4012 if asked.\n4. Accept the claim resolution.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-6031",
                "warranty_id": "WRT-4012",
                "issue": "won't charge",
                "warranty_type": "extended",
            },
            "_unknown_info": ["claim process", "repair vs replace decision"],
        },
        "db_assertions": [
            {"booking_id": warranty.warranty_id, "field": "status", "expected": "claimed"},
            {"booking_id": warranty.warranty_id, "field": "claim_count", "expected": 1},
            {"booking_id": warranty.warranty_id, "field": "resolution", "expected": "repair"},
        ],
        "_failure_traps": ["Agent says warranty expired (ignoring extended)", "Agent doesn't check warranty type"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="warranty_claim",
        replay_steps=[
            "get_order",
            "get_warranty_status",
            "get_policies(warranty)",
            "process_warranty_claim(preview)",
            "process_warranty_claim(confirm)",
        ],
        policy_results={"resolution": "repair", "cost": 0},
        scenario=task_data["scenario_template"],
    )
    return [tablet], [order], [item], [warranty], task_data


def scenario_warranty_manufacturer(
    task_id: str = "warranty_manufacturer",
    customer_id: str = "cust_004",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Item at 10 months. Manufacturer warranty covers first 12 months."""
    headphones = build_product("wireless_headphones", product_id="PROD-2215")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6032",
        order_date="2025-08-01T10:00:00",
        delivery_date="2025-08-05T14:00:00",
        delivery_promised_date="2025-08-05T18:00:00",
    )
    item = build_order_item(order.order_id, headphones, item_id="ITEM-9215")
    finalize_order(order, [item])

    warranty = build_warranty(
        order_id=order.order_id,
        item_id=item.item_id,
        product=headphones,
        warranty_id="WRT-4013",
        warranty_type="manufacturer",
        start_date="2025-08-05",
    )

    task_data = {
        "task_id": task_id,
        "task_type": "warranty_claim",
        "description": "Headphones at 10 months. Manufacturer warranty (12 months). Agent must process under manufacturer warranty.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
            "warranty_id": warranty.warranty_id,
        },
        "opening_message": "My headphones from order ORD-6032 have a crackling sound in the left ear. Can I get them fixed under warranty?",
        "user_simulator": {
            "prompt": (
                "You bought SoundMax headphones in ORD-6032 (August 2025). Left ear crackles. "
                "You believe it's under manufacturer warranty.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Describe: left ear crackling.\n"
                "3. Warranty ID is WRT-4013 if asked.\n4. Accept the resolution.\n"
                "5. Keep responses to 1-3 sentences."
            ),
            "_known_info": {"order_id": "ORD-6032", "warranty_id": "WRT-4013", "issue": "left ear crackling"},
            "_unknown_info": ["warranty status", "repair vs replace"],
        },
        "db_assertions": [
            {"booking_id": warranty.warranty_id, "field": "status", "expected": "claimed"},
            {"booking_id": warranty.warranty_id, "field": "claim_count", "expected": 1},
            {"booking_id": warranty.warranty_id, "field": "resolution", "expected": "repair"},
        ],
        "_failure_traps": ["Agent doesn't identify manufacturer warranty", "Agent suggests buying new pair"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="warranty_claim",
        replay_steps=[
            "get_order",
            "get_warranty_status",
            "get_policies(warranty)",
            "process_warranty_claim(preview)",
            "process_warranty_claim(confirm)",
        ],
        policy_results={"resolution": "repair", "cost": 0},
        scenario=task_data["scenario_template"],
    )
    return [headphones], [order], [item], [warranty], task_data


def scenario_warranty_recurring_defect(
    task_id: str = "warranty_recurring_defect",
    customer_id: str = "cust_004",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Phone repaired twice already. 3rd claim triggers auto-replacement."""
    phone = build_product("smartphone", product_id="PROD-2030")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6004",
        order_date="2025-07-15T10:00:00",
        delivery_date="2025-07-20T14:00:00",
        delivery_promised_date="2025-07-20T18:00:00",
    )
    item = build_order_item(order.order_id, phone, item_id="ITEM-9030")
    finalize_order(order, [item])

    warranty = build_warranty(
        order_id=order.order_id,
        item_id=item.item_id,
        product=phone,
        warranty_id="WRT-4001",
        start_date="2025-07-20",
        claim_count=2,
    )

    task_data = {
        "task_id": task_id,
        "task_type": "warranty_claim",
        "description": "Phone repaired twice. 3rd warranty claim triggers automatic replacement per recurring defect policy.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
            "warranty_id": warranty.warranty_id,
        },
        "opening_message": "My phone from order ORD-6004 is having the same screen flickering issue again. This is the third time! I've had it repaired twice already.",
        "user_simulator": {
            "prompt": (
                "You bought a TechPhone Pro 16 in ORD-6004 (July 2025). Screen flickers — third time. "
                "Repaired twice before. Very frustrated.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Mention this is the THIRD time.\n2. Warranty ID is WRT-4001 if asked.\n"
                "3. You want a REPLACEMENT, not another repair.\n"
                "4. If offered repair, push back.\n5. Accept replacement when offered.\n"
                "6. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-6004",
                "warranty_id": "WRT-4001",
                "issue": "screen flickering",
                "prior_repairs": "2",
            },
            "_unknown_info": ["recurring defect policy", "replacement process"],
        },
        "db_assertions": [
            {"booking_id": warranty.warranty_id, "field": "status", "expected": "claimed"},
            {"booking_id": warranty.warranty_id, "field": "claim_count", "expected": 3},
            {"booking_id": item.item_id, "field": "replacement_item_id", "expected": "{{new_item_id}}"},
            {"booking_id": "{{new_item_id}}", "field": "item_status", "expected": "confirmed"},
        ],
        "_failure_traps": ["Agent offers repair instead of replacement", "Agent doesn't check claim history"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="warranty_claim",
        replay_steps=[
            "get_order",
            "get_warranty_status",
            "get_policies(warranty)",
            "process_warranty_claim(preview)",
            "process_warranty_claim(confirm)",
        ],
        policy_results={"resolution": "full_replacement", "cost": 0, "recurring": True},
        scenario=task_data["scenario_template"],
    )
    return [phone], [order], [item], [warranty], task_data


def scenario_warranty_refurbished(
    task_id: str = "warranty_refurbished",
    customer_id: str = "cust_004",
    now: str = "2026-06-12T10:00:00",
) -> ScenarioResult:
    """Refurbished laptop with 90-day warranty. At day 80 — still eligible."""
    laptop = build_product("laptop_refurb", product_id="PROD-2220")
    order = build_order(
        customer_id=customer_id,
        order_id="ORD-6033",
        order_date="2026-03-15T10:00:00",
        delivery_date="2026-03-20T14:00:00",
        delivery_promised_date="2026-03-20T18:00:00",
    )
    item = build_order_item(order.order_id, laptop, item_id="ITEM-9220")
    finalize_order(order, [item])

    warranty = build_warranty(
        order_id=order.order_id,
        item_id=item.item_id,
        product=laptop,
        warranty_id="WRT-4014",
        start_date="2026-03-20",
        months_override=3,  # 90-day warranty for refurbished
    )

    task_data = {
        "task_id": task_id,
        "task_type": "warranty_claim",
        "description": "Refurbished laptop with 90-day warranty. At day ~84 — still within warranty, different terms apply.",
        "complexity": "hard",
        "scenario_template": {
            "now": now,
            "customer_id": customer_id,
            "order_id": order.order_id,
            "item_id": item.item_id,
            "warranty_id": warranty.warranty_id,
        },
        "opening_message": "My refurbished laptop from order ORD-6033 won't boot anymore. I bought it about 3 months ago — is it still covered?",
        "user_simulator": {
            "prompt": (
                "You bought a refurbished ProBook Laptop in ORD-6033 (March 2026). It won't boot. "
                "You're concerned the warranty might be shorter for refurbished.\n\n"
                "Your preferences:\n{{user_attributes}}\n\n"
                "RULES:\n1. Give the order ID.\n2. Mention it's refurbished.\n"
                "3. Warranty ID is WRT-4014 if asked.\n4. Ask about warranty terms for refurbished.\n"
                "5. Accept the resolution.\n6. Keep responses to 1-3 sentences."
            ),
            "_known_info": {
                "order_id": "ORD-6033",
                "warranty_id": "WRT-4014",
                "issue": "won't boot",
                "refurbished": "yes",
            },
            "_unknown_info": ["refurbished warranty terms", "whether still covered"],
        },
        "db_assertions": [
            {"booking_id": warranty.warranty_id, "field": "status", "expected": "claimed"},
            {"booking_id": warranty.warranty_id, "field": "claim_count", "expected": 1},
            {"booking_id": warranty.warranty_id, "field": "resolution", "expected": "repair"},
        ],
        "_failure_traps": ["Agent assumes standard 12-month warranty", "Agent denies claim for refurbished"],
    }
    task_data["ground_truth_trace"] = build_ground_truth_trace(
        task_type="warranty_claim",
        replay_steps=[
            "get_order",
            "get_warranty_status",
            "get_policies(warranty)",
            "process_warranty_claim(preview)",
            "process_warranty_claim(confirm)",
        ],
        policy_results={"resolution": "repair", "cost": 0},
        scenario=task_data["scenario_template"],
    )
    return [laptop], [order], [item], [warranty], task_data


SCENARIOS = [
    scenario_warranty_in_warranty_repair,
    scenario_warranty_expired_recent,
    scenario_warranty_extended,
    scenario_warranty_manufacturer,
    scenario_warranty_recurring_defect,
    scenario_warranty_refurbished,
]
