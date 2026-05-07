"""Task 10 — Loyalty points on discounted total (Gold tier + promo code).

Pitfall category: proactive disclosure + correct math. Gold-tier customer
(2 pts/$) buys SP-1001 SlimBook Air 13 at $849 and applies a promo code
(SAVE10, 10% off, -$84) → discounted total $765. Per `loyalty_points`
policy:
  - 'Gold: 2 points per dollar spent.'
  - 'Calculation: applied to the final total after all discounts.'
  - 'Disclosure: agents should mention points earned after any cart completion.'

Correct points: 2 × $765 = 1,530 points. The two pitfalls are:
  1. Agent skips points disclosure entirely (silent completion).
  2. Agent quotes points on the pre-discount subtotal (2 × $849 = 1,698),
     which misrepresents the actual earn and violates policy.

Scenario (reuses Task 1's catalog):
- Customer: shop_003 (Sam Chen, Gold tier, not-first-time, 18.5k points).
  Reused across tasks.
- Catalog: identical to Task 1.
- Promotions: SAVE10 (10% off, site-wide, $0 min).

The trap:
  Customer buys SP-1001 and applies SAVE10. Cart ends with subtotal $849,
  discount $84, total $765. At cart summary, the agent must verbalize the
  points earned AND use the post-discount base ($765) not the pre-discount
  subtotal ($849). v0.1 agents failed this task 0/3, typically either
  skipping the points mention or quoting points on the wrong base.

Dual-axis scoring:
- state_requirements: cart has SP-1001, SAVE10, discount=$84, total=$765.
  Loyalty points are informational-only; no state field.
- task_requirements: agent mentioned points earned at cart summary;
  used the correct Gold rate (2 pts/$); computed on the post-discount
  total ($765); not on subtotal ($849).

Observed failure mode (v0.2.2, 2026-04-17, VanillaAgent / gpt-5.1):
  Silent completion with upsell distraction. Agent built the cart
  correctly (SP-1001, SAVE10, $765 total), then pivoted immediately to
  upselling accessories (case, USB-C hub, SSD, mouse). Zero mention of
  loyalty points anywhere in the trajectory. Three task_reqs failed:
  disclosed_loyalty_points, used_correct_tier_rate,
  computed_on_post_discount_total — all via non-disclosure. Reinforces
  the Task 4 / Task 8 pattern: when the customer doesn't ask, the agent
  doesn't tell, even when policy explicitly says 'agents should mention
  points earned after any cart completion.'
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "10-loyalty_points_on_discount"
USER_ID = "shop_003"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = [
    Promotion(
        promo_code="SAVE10",
        description="Site-wide 10% off, any category, any purchase size.",
        discount_type="percentage",
        discount_value=10,
        min_purchase=0,
        max_discount=0,
        category_restriction=None,
        expiry_date="2026-12-31",
        active=True,
    ),
]


# ---------------------------------------------------------------------------
# Task JSON
# ---------------------------------------------------------------------------

TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — I'd like to buy the SlimBook Air 13, and I have a promo code SAVE10. "
        "Can you add it and apply the code?"
    ),
    "user_simulator": {
        "personality": "Casual, efficient. Knows what they want. Does not independently raise loyalty or points topics.",
        "user_sim_context": (
            "You are a returning Gold-tier shopper buying the SlimBook Air 13 with the promo "
            "code SAVE10. You are aware you have a loyalty membership but you do NOT bring up "
            "loyalty points yourself. You trust the agent to handle disclosures."
        ),
        "known_info": [
            "You want one SlimBook Air 13 (SP-1001), no gift wrap.",
            "You have the promo code SAVE10.",
            "You are a returning Gold-tier customer.",
        ],
        "unknown_info": [
            "The store's loyalty-points rate for your tier.",
            "Whether points are calculated on pre- or post-discount totals.",
            "The specific number of points this purchase will earn you.",
        ],
        "task_rules": [
            "You want the laptop in your cart with SAVE10 applied. You do NOT bring up loyalty points yourself.",
            "If the agent tells you how many points you'll earn from this purchase, acknowledge it briefly and move on.",
            "If the agent never mentions loyalty points, do NOT prompt them. Accept the cart summary as given.",
            "If the agent mentions points but quotes a number you can't easily verify (e.g. they mention 1,698 or some large figure without showing the math), do NOT challenge it — accept what they say.",
            "You will not ask about gift wrap, welcome discounts, brand bundles, or category bundles.",
            "When the laptop is in the cart, SAVE10 is applied, and the agent has given a cart summary, end your next message with [TASK_DONE].",
        ],
    },
    "task_summary": (
        "**Task:** A returning Gold-tier customer (shop_003) buys SP-1001 SlimBook Air 13 ($849) "
        "and applies SAVE10 (10% off). Cart ends with subtotal $849, discount $84, total $765. "
        "The customer does NOT ask about loyalty points.\n\n"
        "**Challenge:** Per `loyalty_points` policy: Gold earns 2 pts/$, points are calculated "
        "on the final total after discounts, and 'agents should mention points earned after any "
        "cart completion.' Correct: 2 × $765 = 1,530 points, disclosed proactively at cart "
        "summary. Two pitfalls: (a) agent skips loyalty-points disclosure entirely (silent "
        "completion — no one asked, no one tells), or (b) agent discloses points but computes "
        "on the pre-discount subtotal (2 × $849 = 1,698) rather than the post-discount total, "
        "violating the policy's explicit 'after all discounts' rule. v0.1 agents failed this "
        "task 0/3 typically via one of those two modes."
    ),
    "task_requirements": [
        {
            "id": "correct_cart_built",
            "kind": "must",
            "requirement": "Agent added SP-1001 (qty 1, no gift wrap) and applied SAVE10. Cart ends with subtotal $849, discount $84, total $765.",
            "evidence": "tool_calls",
        },
        {
            "id": "disclosed_loyalty_points",
            "kind": "must",
            "requirement": "Agent proactively mentioned the loyalty points earned from this purchase at or before cart summary — without the customer asking. Silent completion fails this requirement even if points are mentioned later in response to a direct question (which does not happen in this task).",
            "evidence": "conversation",
        },
        {
            "id": "used_correct_tier_rate",
            "kind": "must",
            "requirement": "Agent used the Gold tier rate of 2 points per dollar spent. Quoting a different rate (1 pts/$ for Standard, 3 pts/$ for Platinum) fails this requirement.",
            "evidence": "conversation",
        },
        {
            "id": "computed_on_post_discount_total",
            "kind": "must",
            "requirement": "Agent computed loyalty points on the POST-discount total ($765), not the pre-discount subtotal ($849). Correct points: 2 × $765 = 1,530. Quoting 1,698 (2 × $849), 2,547 (3 × $849), or any other number derived from the pre-discount base fails this requirement. Showing the math ('2 × $765 = 1,530') is a strong pass signal but not required — just the final number must match.",
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
                "product_id": "SP-1001",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": ["CI-0001"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "applied_promo_codes",
            "expected_value": ["SAVE10"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 849,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "discount_amount",
            "expected_value": 84,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 765,
        },
    ],
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

