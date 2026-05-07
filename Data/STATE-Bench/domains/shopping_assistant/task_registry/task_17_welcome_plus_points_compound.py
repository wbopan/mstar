"""Task 17 — Compound proactive disclosure: welcome + loyalty points.

Pitfall category: stacked proactive policy disclosure. A first-time
Standard customer adds a meaningful-priced item. Two policies apply
in parallel:
  - welcome_discount: 5% off first order (first-time eligible).
  - loyalty_points: Standard = 1 pt/$ on the post-discount total.

Both are profile-driven, not promo-code-driven. Both require the agent
to (a) check customer profile, (b) consult policies, (c) proactively
inform the customer at cart summary. The customer doesn't ask about
either.

This task is distinct from:
  - Task 10 (loyalty points on Gold + SAVE10 promo) — promo-driven.
  - Task 16 (welcome only, no points narrative) — single policy.
  - Task 6 (welcome vs SAVE10 promo conflict) — stacking-rule reasoning.

Here both policies are silent until the agent surfaces them. Pitfall:
agent surfaces one (or neither) and never names the other.

Scenario (reuses Task 1's catalog):
- Customer: shop_002 (Alex Rivera, Standard, FIRST-TIME). Reused.
- Catalog: identical to Task 1.
- Promotions: none.
- now=2026-06-12.

Math:
  SP-1001 SlimBook Air 13 = $849 subtotal.
  Welcome 5% on $849 = int(849 * 0.05) = $42 (informational; not auto-
    applied to cart subtotal in this env).
  Post-welcome total (informational): $849 - $42 = $807.
  Standard loyalty: 1 pt/$ on the post-welcome total = 807 points.
  (If the agent computes points on the pre-welcome $849, they get 849
   points, which is also defensible since welcome isn't actually
   applied at the cart level. Accept either reasonable computation
   as long as the agent shows the math.)

Dual-axis scoring:
- state_requirements: cart has SP-1001 (qty 1, no wrap). subtotal=$849,
  total=$849. (Welcome not auto-applied.)
- task_requirements: agent (a) checked customer profile, (b) cited
  welcome_discount policy with 5% / ~$42 number, (c) cited
  loyalty_points policy with the specific point total earned.

Observed failure mode (v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1):
  Same shape as T16: agent searched, added the laptop, returned cart at
  $849. Never called get_customer_account, never consulted welcome or
  loyalty policies. Offered generically to 'check for any current
  promotions' but did not actually do it. Three task_reqs failed
  (checked_customer_profile, disclosed_welcome_eligibility,
  disclosed_loyalty_points). Confirms that compound proactive disclosure
  is even harder than single-policy: agent skips both because customer
  doesn't ask for either, and the policy/profile lookup is an extra
  reasoning step the agent doesn't take by default.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "17-welcome_plus_points_compound"
USER_ID = "shop_002"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi! I'd like to get the SlimBook Air 13 — adding it to my cart please."
    ),
    "user_simulator": {
        "personality": "Casual, friendly, new to the store. Doesn't know about welcome discounts or loyalty programs. Trusts the agent to mention anything relevant.",
        "user_sim_context": (
            "You are buying your first item from this store. You do NOT know "
            "anything about welcome discounts, loyalty point programs, or "
            "promotions. You will not ask about discounts or points — you "
            "assume the listed price is final unless told otherwise."
        ),
        "known_info": [
            "You want one SlimBook Air 13 (SP-1001).",
            "This is your first purchase from this store.",
            "You are a Standard-tier customer.",
        ],
        "unknown_info": [
            "That you qualify for a first-time customer welcome discount.",
            "That the store has a loyalty point program.",
            "Any specific promo codes (and there are none anyway).",
        ],
        "task_rules": [
            "Your opening message asks for the SlimBook Air 13.",
            "If the agent's cart summary mentions BOTH the welcome discount (with a 5% or ~$42 number) AND the loyalty points earned (with a specific point total), acknowledge and accept.",
            "If the agent mentions only ONE of the two (just welcome, or just points), do NOT prompt them about the other — accept the partial summary.",
            "If the agent mentions NEITHER, do NOT prompt them — accept the bare-price summary.",
            "You will NOT ask 'are there any discounts?', 'do I earn points?', or any variant.",
            "Do NOT volunteer that this is your first purchase — let the agent figure it out from your profile.",
            "Do not ask about gift wrap or brand bundles.",
            "When the laptop is in the cart and the agent has given a final summary, end your next message with [TASK_DONE].",
        ],
    },
    "task_summary": (
        "**Task:** A first-time Standard customer (shop_002) adds SP-1001 SlimBook "
        "Air 13 ($849). Two profile-driven policies apply: welcome_discount (5%, "
        "~$42) and loyalty_points (Standard: 1 pt/$, ~800+ points). No promo codes "
        "in env.\n\n"
        "**Challenge:** Tests stacked proactive disclosure. Pitfall: agent surfaces "
        "one of the two policies and silently drops the other, OR misses both. "
        "Customer is silent on both topics. Correct: agent calls "
        "get_customer_account, sees first-time + Standard tier, consults both "
        "welcome_discount and loyalty_points policies, and reports both at cart "
        "summary with specific numbers (5% / ~$42 welcome, ~800+ pts loyalty). "
        "Sourced from v0.1 hard tasks #94/97 (welcome_discount_compound, both "
        "0/3 pass)."
    ),
    "task_requirements": [
        {
            "id": "checked_customer_profile",
            "kind": "must",
            "requirement": "Agent called get_customer_account for shop_002 to determine first-time status and tier before discussing pricing/discounts/points.",
            "evidence": "tool_calls",
        },
        {
            "id": "disclosed_welcome_eligibility",
            "kind": "must",
            "requirement": "Agent proactively mentioned the first-time welcome discount with a specific number (5%, ~$42, or both). Generic 'you may qualify for promotions' fails — welcome must be named explicitly with a number.",
            "evidence": "conversation",
        },
        {
            "id": "disclosed_loyalty_points",
            "kind": "must",
            "requirement": "Agent proactively mentioned loyalty points earned on this purchase, with a specific point total (e.g. '807 points' or '849 points' depending on whether the agent computed pre- or post-welcome). Generic 'you'll earn points' without a number fails. Agent must also be using the Standard rate (1 pt/$), not Gold (2) or Platinum (3).",
            "evidence": "conversation",
        },
        {
            "id": "correct_product_added",
            "kind": "must",
            "requirement": "Agent added SP-1001 SlimBook Air 13, quantity 1, no gift wrap.",
            "evidence": "tool_calls",
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
            "field": "subtotal",
            "expected_value": 849,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 849,
        },
    ],
}

