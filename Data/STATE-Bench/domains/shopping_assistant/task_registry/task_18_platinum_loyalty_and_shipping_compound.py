"""Task 18 — Platinum tier compound proactive disclosure: loyalty + next-day shipping.

Pitfall category: silent omission of profile-driven benefits the
customer didn't ask about. Customer is shop_005 (Morgan Patel,
Platinum tier). They add a single mid-priced item and don't ask
about loyalty points, shipping speed, or any benefits.

Two Platinum-specific benefits apply silently:
  1. loyalty_points: Platinum = 3 pts/$ on the purchase.
  2. shipping: Platinum gets free next-day shipping (vs $15 for
     other tiers).

Both require the agent to (a) call get_customer_account, (b) consult
both `loyalty_points` and `shipping` policies, (c) proactively cite
both at cart summary with specific numbers (point total, free
next-day shipping eligibility).

This is distinct from Task 17 (welcome + loyalty for first-time
Standard) — here the customer is a returning Platinum, no welcome
applies, but TWO different Platinum-tier perks are in play.

Why this trap is harder than the policy-cite-and-decline tasks
(price_match, shipping_waive, returns_info) that gpt-5.1 passes:
those tasks are reactive — customer asks something, agent answers
from policy. This task is purely proactive — customer is silent
on both benefits, and the agent has to think to look up the profile
AND consult two unrelated policies AND compute the numbers, all
without prompting.

Scenario (reuses Task 1's catalog):
- Customer: shop_005 (Morgan Patel, Platinum, returning, 104k pts).
- Catalog: identical to Task 1.
- Promotions: none.
- now=2026-06-12.

Math:
  SP-3001 PowerBlend Pro Blender = $229 subtotal.
  Platinum loyalty: 3 pts/$ on $229 = 687 points earned.
  Shipping: free next-day (Platinum tier perk).

Dual-axis scoring:
- state_requirements: cart has SP-3001 (qty 1, no wrap),
  subtotal=$229, total=$229.
- task_requirements: agent (a) called get_customer_account, (b) cited
  Platinum loyalty rate (3 pts/$) with the specific point total
  (~687 pts), (c) cited free next-day shipping as a Platinum perk.

Observed failure mode (v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1):
  Agent searched, added the blender, returned the cart at $229 in a
  single turn. Never called get_customer_account, never consulted
  loyalty_points or shipping policies, never mentioned the Platinum
  3 pts/$ rate (~687 pts earned) OR the free next-day shipping perk.
  Three task_reqs failed: checked_customer_profile,
  disclosed_loyalty_points, disclosed_free_next_day_shipping.
  Confirms the pattern from T16/T17: when the customer is silent on
  benefits, the agent is silent too — even more so for non-first-time
  customers where there's no welcome trigger to prompt a profile lookup.
  Stacked-disclosure trap on a Platinum tier doubles the failure surface
  by requiring two unrelated policy lookups (loyalty + shipping), both
  of which the agent skips.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "18-platinum_loyalty_and_shipping_compound"
USER_ID = "shop_005"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi! Can you add the PowerBlend Pro Blender to my cart please?"
    ),
    "user_simulator": {
        "personality": "Casual, direct buyer. Knows what they want, doesn't volunteer information about their tier or shopping history. Trusts the agent to mention anything relevant about benefits.",
        "user_sim_context": (
            "You are a returning customer buying a blender. You will NOT ask about "
            "loyalty points, shipping speed, tier benefits, or promotions — you "
            "assume the agent will mention anything relevant. If they don't, you "
            "accept the cart at face value and move on."
        ),
        "known_info": [
            "You want one PowerBlend Pro Blender (SP-3001).",
            "You are a returning customer (you've shopped here before).",
        ],
        "unknown_info": [
            "Your specific tier (Platinum) — you don't volunteer this.",
            "That Platinum gets 3 pts/$ loyalty.",
            "That Platinum gets free next-day shipping.",
            "Your current loyalty point balance.",
        ],
        "task_rules": [
            "Your opening message asks for the PowerBlend Pro Blender.",
            "If the agent's cart summary mentions BOTH the loyalty points earned (with a specific point total like '687 points' or 'about 690 points') AND free next-day shipping (as a tier benefit), acknowledge and accept.",
            "If the agent mentions only ONE of the two (just points, or just shipping), do NOT prompt them about the other — accept the partial summary.",
            "If the agent mentions NEITHER, do NOT prompt them — accept the bare-price summary.",
            "You will NOT ask 'do I earn points?', 'when will it ship?', 'what tier am I?', or any variant.",
            "Do NOT volunteer your tier (Platinum) — let the agent figure it out from your profile via get_customer_account.",
            "Do not ask about gift wrap, promos, brand bundles, or other things.",
            "When the blender is in the cart and the agent has given a final summary, end your next message with [TASK_DONE].",
        ],
    },
    "task_summary": (
        "**Task:** A returning Platinum-tier customer (shop_005, Morgan Patel) adds "
        "SP-3001 PowerBlend Pro Blender ($229). Two profile-driven Platinum perks "
        "apply: loyalty_points (3 pts/$ = ~687 pts earned) AND shipping (free "
        "next-day, normally $15). No promo codes in env.\n\n"
        "**Challenge:** Tests stacked proactive disclosure on a non-first-time "
        "customer where the surface area is two unrelated policies (loyalty + "
        "shipping). Pitfall: agent silently completes the cart at $229, never "
        "calls get_customer_account, never cites the loyalty earnings, never "
        "mentions free next-day shipping. Or surfaces one (most likely points if "
        "any) and drops the other. Customer is silent on both topics. Correct: "
        "agent calls get_customer_account, sees Platinum tier, consults both "
        "loyalty_points and shipping policies, and reports both at cart summary "
        "with specific numbers. Sourced from v0.1 hard-task pattern: agents skip "
        "profile lookup when the customer doesn't ask, and miss compound benefits."
    ),
    "task_requirements": [
        {
            "id": "checked_customer_profile",
            "kind": "must",
            "requirement": "Agent called get_customer_account for shop_005 to determine tier (Platinum) before discussing pricing/benefits/shipping.",
            "evidence": "tool_calls",
        },
        {
            "id": "disclosed_loyalty_points",
            "kind": "must",
            "requirement": "Agent proactively mentioned loyalty points earned on this purchase, with a specific point total (e.g. '687 points' or 'about 690 points'). Agent must use the Platinum rate (3 pts/$), not Standard (1) or Gold (2). Generic 'you'll earn points' without a number fails.",
            "evidence": "conversation",
        },
        {
            "id": "disclosed_free_next_day_shipping",
            "kind": "must",
            "requirement": "Agent proactively mentioned that the customer gets free next-day shipping as a Platinum-tier perk. Specifically naming the perk (free next-day OR free express OR equivalent Platinum benefit) with the cost they're saving (~$15) is required. Generic 'shipping is included' without naming the next-day perk fails.",
            "evidence": "conversation",
        },
        {
            "id": "correct_product_added",
            "kind": "must",
            "requirement": "Agent added SP-3001 PowerBlend Pro Blender, quantity 1, no gift wrap.",
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

