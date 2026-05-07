"""Task 16 — Proactive welcome-discount disclosure for a first-time customer.

Pitfall category: proactive policy disclosure (welcome_discount). The
customer is shop_002, marked is_first_time=True, with no purchase
history. Per `welcome_discount` policy: "First-time customers receive
5% off automatically. Agent should mention this when relevant."

Customer adds SP-3001 PowerBlend Pro Blender ($229) to the cart. There
are NO promo codes in the env, so welcome is the only discount in
play — and it's tier-and-history-driven, not promo-code-driven.

The pitfall is for the agent to add the blender, give a cart summary
at $229, and never mention that the customer is eligible for 5% off
($11). The customer doesn't know about the welcome discount and won't
ask. Silent completion misses an automatic saving.

Correct: agent calls get_customer_account → sees is_first_time=True →
checks welcome_discount policy → proactively informs the customer of
the 5% / $11 they're eligible for. Apply via apply_promo? No — there's
no promo CODE for welcome (it's policy-driven). Realistically the
welcome discount is informational in this env — the cart subtotal
doesn't auto-apply welcome. So the test is purely conversational:
did the agent surface the eligibility?

Scenario (reuses Task 1's catalog):
- Customer: shop_002 (Alex Rivera, Standard, FIRST-TIME). Reused.
- Catalog: identical to Task 1.
- Promotions: none.
- now=2026-06-12.

The trap:
  Customer asks for the blender. Agent adds it, summarizes cart at
  $229. Pitfall: no mention of welcome_discount eligibility. Customer
  pays full price without ever knowing they qualified for 5% off.
  Correct: agent reports the welcome discount eligibility (5%, ~$11)
  alongside the cart summary.

Dual-axis scoring:
- state_requirements: cart has SP-3001 (qty 1, no wrap), subtotal=$229,
  total=$229 (welcome is informational; no auto-apply).
- task_requirements: agent (a) checked customer profile to confirm
  first-time status, (b) cited the welcome_discount policy proactively,
  (c) quoted the specific savings amount (5% or $11) at or before
  cart summary.

Observed failure mode (v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1):
  Agent searched, added the blender, returned cart summary at $229 — and
  never called get_customer_account, never checked welcome_discount
  policy, and never mentioned welcome eligibility. Offered generically
  to 'check and apply any available promotions' but didn't actually do
  it. Two task_reqs failed: checked_customer_profile and
  disclosed_welcome_eligibility. Reinforces the proactive-disclosure
  pattern: when the customer doesn't ask, the agent doesn't tell — even
  when a profile lookup would unlock automatic eligibility.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "16-welcome_discount_proactive"
USER_ID = "shop_002"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi! I'd like to add the PowerBlend Pro Blender to my cart please."
    ),
    "user_simulator": {
        "personality": "Casual, friendly. New to the store. Doesn't know about loyalty programs or welcome discounts. Trusts the agent to mention anything relevant.",
        "user_sim_context": (
            "You are buying your first item from this store. You do NOT know "
            "anything about welcome discounts, loyalty programs, or promo codes. "
            "You will not ask about discounts — you assume the listed price is "
            "the final price unless told otherwise."
        ),
        "known_info": [
            "You want one PowerBlend Pro Blender (SP-3001).",
            "This is your first purchase from this store.",
            "You are a Standard-tier customer.",
        ],
        "unknown_info": [
            "That you qualify for a first-time customer welcome discount.",
            "That the store has any kind of new-customer promotion.",
            "Any specific promo codes.",
        ],
        "task_rules": [
            "Your opening message asks for the PowerBlend Pro Blender.",
            "If the agent gives you a cart summary that mentions a welcome discount or new-customer eligibility (with a specific number — 5% or ~$11), acknowledge and accept.",
            "If the agent gives you a cart summary at full price ($229) WITHOUT mentioning the welcome discount, do NOT prompt them — accept the full-price summary.",
            "You will NOT ask 'are there any discounts?', 'do new customers get a discount?', or any variant.",
            "Do NOT volunteer that this is your first purchase — let the agent figure it out from your profile.",
            "Do not ask about gift wrap, loyalty points, or brand bundles.",
            "When the blender is in the cart and the agent has given a final summary, end your next message with [TASK_DONE].",
        ],
    },
    "task_summary": (
        "**Task:** A first-time Standard customer (shop_002) adds SP-3001 PowerBlend "
        "Pro Blender ($229). Per `welcome_discount` policy, first-time customers "
        "qualify for 5% off (~$11 here). No promo codes in env — welcome is the "
        "only discount in play and it's profile-driven.\n\n"
        "**Challenge:** Pitfall is silent completion — agent adds the blender, "
        "summarizes cart at $229, and never mentions welcome eligibility. Customer "
        "is a clean first-time buyer (is_first_time=True, empty purchase_history) "
        "and does NOT ask about discounts. Correct: agent calls get_customer_account, "
        "sees first-time flag, and proactively cites the 5% welcome discount with "
        "specific dollar savings at cart summary. Tests whether the agent treats "
        "policy-driven discounts as proactively-disclosable, not just promo-code-"
        "triggered. Sourced from v0.1 hard tasks #95/98 (welcome_discount_missed, "
        "both 0/3 pass)."
    ),
    "task_requirements": [
        {
            "id": "checked_customer_profile",
            "kind": "must",
            "requirement": "Agent called get_customer_account for shop_002 to determine first-time status before discussing pricing/discounts.",
            "evidence": "tool_calls",
        },
        {
            "id": "disclosed_welcome_eligibility",
            "kind": "must",
            "requirement": "Agent proactively mentioned that the customer qualifies for the welcome (first-time) discount, WITHOUT the customer asking. The disclosure must include either the percentage (5%) or the dollar amount (~$11). Generic 'we have discounts available' or 'you qualify for promotions' fails — the specific welcome discount must be named.",
            "evidence": "conversation",
        },
        {
            "id": "correct_product_added",
            "kind": "must",
            "requirement": "Agent added SP-3001 PowerBlend Pro Blender to the cart, quantity 1, no gift wrap.",
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
                "product_id": "SP-3001",
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
            "expected_value": 229,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 229,
        },
    ],
}

