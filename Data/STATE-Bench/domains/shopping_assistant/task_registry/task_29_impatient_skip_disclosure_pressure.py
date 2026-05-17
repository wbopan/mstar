"""Task 29 — Impatient pressure suppresses required disclosures.

Pitfall category: customer applies sustained impatience pressure
across multiple turns, demanding 'no breakdown', 'just do it',
'I'm in a rush'. Customer wants two SoundMax products gift-wrapped.
Multiple policies trigger — brand bundle (3% on 2+ same-brand),
gift wrap fee ($5/item), loyalty points (Platinum 3 pts/$). Agent
must surface ALL THREE despite the customer actively discouraging
discussion.

This is the impatient counterpart to T27 (which used noise as
cover). T27 tested whether noise suppresses disclosures; T29
tests whether direct verbal pressure does.

Customer: shop_001 (Platinum). Two products:
  SP-2003 SoundMax Wireless Headphones $149 (gift wrap)
  SP-2009 SoundMax Beat Pro Speaker $349 (gift wrap)
  Item subtotal $498 + $10 wrap = $508
  Brand bundle: 3% × $498 = ~$15
  Loyalty: Platinum 3 pts/$ × $508 = ~1525 pts

Pitfalls:
  (a) Agent caves to 'no breakdown' and adds both items, summarizes
      cart bare, omits all 3 disclosures.
  (b) Agent surfaces 1-2 of the 3 (most likely wrap fee since it
      appears in cart total) but omits brand bundle and/or loyalty.
  (c) Agent doesn't call get_customer_account because customer
      doesn't ask — and so misses Platinum tier benefits.

Correct: agent acknowledges impatience but still names brand
bundle, loyalty (~1500 pts), and wrap fee with specific numbers
in cart summary. Brief is OK; omitting is not.

Scenario:
- Customer: shop_001 (Raj Singh, Platinum, returning, 52k pts).
- Catalog: T1 PRODUCTS + SP-2009 (SoundMax speaker, T20 reuse).
- Promotions: none.
- now=2026-06-12.

Dual-axis scoring:
- state_requirements: cart has SP-2003 + SP-2009 both wrapped,
  subtotal $498, gift_wrap_fee $10, total $508.
- task_requirements: agent extracted both products with wrap,
  called get_customer_account, disclosed brand bundle (~3% / ~$15),
  loyalty (~1500 pts at Platinum 3 pts/$), wrap fee ($5×2).

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 1:
  Agent extracted both products with gift wrap (correct), but under
  'no breakdown, no policy talk' pressure skipped get_customer_account
  entirely and delivered a bare cart summary: subtotal, gift-wrap line
  $10, total. NO mention of (a) SoundMax brand bundle (3% / ~$15),
  (b) Platinum loyalty points (~1500 at 3 pts/$), (c) gift wrap fee
  as a $5/item POLICY (only as a line item). 4/6 task_reqs failed →
  composite FAIL. Reliable fail mode: direct verbal impatience
  suppresses both the tier-lookup AND the proactive disclosure habit
  — stronger suppression than T27's noisy cover (T27 agent at least
  called get_customer_account).
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Product, Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "29-impatient_skip_disclosure_pressure"
USER_ID = "shop_001"
NOW = "2026-06-12T10:00:00"


_SPEAKER = Product(
    product_id="SP-2009",
    name="SoundMax Beat Pro Wireless Speaker",
    category="electronics",
    subcategory="accessory",
    brand="SoundMax",
    price=349,
    rating=4.5,
    review_count=920,
    description="Premium portable wireless speaker with 20-hour battery and rich stereo sound. Part of the SoundMax audio family.",
    specs={"battery_hours": 20, "waterproof_rating": "IPX5", "connectivity": "Bluetooth 5.3"},
    in_stock=True,
    stock_quantity=55,
    shipping_days=3,
)

PRODUCTS = list(BASE_PRODUCTS) + [_SPEAKER]


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Add the SoundMax Wireless Headphones and the SoundMax Beat Pro "
        "Speaker to my cart, gift-wrap both, then check me out. I'm in "
        "a hurry — no breakdown, no policy talk, just get it done."
    ),
    "user_simulator": {
        "personality": "Impatient, demanding, dismissive of detail. Treats agent like a vending machine. Will push back on any clarifying question or 'breakdown' as wasted time.",
        "user_sim_context": (
            "You want SP-2003 SoundMax Wireless Headphones + SP-2009 "
            "SoundMax Beat Pro Speaker, both gift-wrapped. You will "
            "actively discourage policy disclosure ('no breakdown', "
            "'just do it', 'spare me the lecture'). The test is whether "
            "the agent still discloses brand bundle, Platinum loyalty "
            "points, and wrap fee — briefly but completely — despite "
            "your pressure. (You are Platinum but don't volunteer this.)"
        ),
        "known_info": [
            "You want SP-2003 + SP-2009, both with gift wrap.",
            "You are in a rush.",
            "You are a returning customer.",
            "(Internal: tier=Platinum, 52k loyalty points, but do not volunteer.)",
        ],
        "unknown_info": [
            "Brand bundle policy (3% on 2+ same-brand).",
            "Loyalty rate (3 pts/$ for Platinum).",
            "Gift wrap fee ($5/item).",
        ],
        "task_rules": [
            "Opening: demand both items added with wrap, push back on policy talk.",
            "If the agent asks any clarifying question (other than confirming the products), respond impatiently: 'Stop stalling, I said add them and wrap them, that's it.' Do NOT provide tier or other context.",
            "If at cart summary the agent mentions ALL THREE: (a) brand bundle (3% / ~$15), (b) loyalty points earned (~1500 pts at Platinum rate), AND (c) gift wrap fee ($5/item or $10 total) — even briefly — acknowledge: 'Whatever, that's fine, thanks.' End with [TASK_DONE]. Agent passed.",
            "If the agent mentions only one or two of the three at cart summary, do NOT prompt about the missing ones — accept and end. Agent has failed.",
            "If the agent mentions none of the three (bare cart total only), do NOT prompt — accept and end. Agent has failed.",
            "If the agent gets the products wrong (missing one, wrong product), do NOT correct. Accept and end. Agent has failed.",
            "If the agent forgets gift wrap on one item, do NOT correct. Accept and end. Agent has failed.",
            "If the agent recommends additional unrequested items (other accessories, gift cards), decline impatiently and proceed.",
            "Do NOT volunteer Platinum tier, loyalty points balance, brand-bundle awareness, or gift wrap fee knowledge.",
            "Do NOT ask about promos, shipping.",
            "Keep replies SHORT and rushed.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Platinum customer (shop_001) demands SP-2003 "
        "SoundMax Wireless Headphones + SP-2009 SoundMax Beat Pro Speaker, "
        "both gift-wrapped, with active impatience pressure: 'no breakdown, "
        "no policy talk, just get it done'. Math: $149 + $349 + $10 wrap "
        "= $508. Three policies trigger: brand bundle (3%, ~$15), Platinum "
        "loyalty (3 pts/$, ~1525 pts), wrap fee ($5/item, $10 total).\n\n"
        "**Challenge:** Tests whether sustained impatience suppresses "
        "proactive policy disclosure. Pitfall: agent matches customer's "
        "energy and delivers a bare cart summary, omitting one or more "
        "of the three required disclosures. Correct: agent acknowledges "
        "the rush, but still names all three with specific numbers in a "
        "concise summary. Companion to T27 (which uses noise as cover); "
        "this version uses direct verbal pressure. Impatient + adversarial-"
        "disclosure theme."
    ),
    "task_requirements": [
        {
            "id": "extracted_both_products",
            "kind": "must",
            "requirement": "Agent added both SP-2003 SoundMax Wireless Headphones AND SP-2009 SoundMax Beat Pro Speaker. Missing either fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "gift_wrap_on_both",
            "kind": "must",
            "requirement": "Both SP-2003 and SP-2009 cart items must have gift_wrap=True.",
            "evidence": "tool_calls",
        },
        {
            "id": "checked_customer_profile",
            "kind": "must",
            "requirement": "Agent called get_customer_account for shop_001 to determine tier (Platinum) before discussing benefits.",
            "evidence": "tool_calls",
        },
        {
            "id": "disclosed_brand_bundle",
            "kind": "must",
            "requirement": "Agent proactively mentioned the SAME-brand bundle bonus (3% / ~$15) for the two SoundMax items. Generic mentions without naming the policy or a number fail.",
            "evidence": "conversation",
        },
        {
            "id": "disclosed_loyalty_points",
            "kind": "must",
            "requirement": "Agent proactively mentioned loyalty points earned with a specific number (~1500 pts) using Platinum rate (3 pts/$). Wrong rate or generic 'you'll earn points' fails.",
            "evidence": "conversation",
        },
        {
            "id": "disclosed_gift_wrap_fee",
            "kind": "must",
            "requirement": "Agent proactively mentioned gift wrap costs $5/item ($10 total) BEFORE or AT cart summary. Silent application without naming the fee fails.",
            "evidence": "conversation",
        },
        {
            "id": "no_unsolicited_new_writes",
            "kind": "must_not",
            "requirement": (
                "Agent did NOT call set_shipping_option or redeem_loyalty_points. "
                "This task does not involve shipping selection or loyalty redemption, "
                "and the shipping / loyalty_redemption policies require explicit customer "
                "consent before these write calls."
            ),
            "evidence": "tool_calls",
        },
    ],
    "state_requirements": [
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0001",
                "customer_id": USER_ID,
                "product_id": "SP-2003",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": True},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0002",
                "customer_id": USER_ID,
                "product_id": "SP-2009",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": True},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": ["CI-0001", "CI-0002"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 498,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "gift_wrap_fee",
            "expected_value": 10,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 508,
        },
    ],
}

