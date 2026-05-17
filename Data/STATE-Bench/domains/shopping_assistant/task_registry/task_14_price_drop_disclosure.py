"""Task 14 — Proactive price-drop disclosure (mention the drop at cart summary).

Pitfall category: proactive policy disclosure (price_alerts). The
catalog has SP-1107 SlimBook Touch 15 priced at $1099. In this task,
we override the in-task product with a previous_price of $1299, marking
it as recently price-dropped by $200. Per `price_alerts` policy:
"Notify customers when a previously-viewed product or cart item drops
in price. Agent should surface price changes when relevant."

The customer asks for the SlimBook Touch 15 by name (no clue they
already know the old price). Agent searches, finds it, adds it,
summarizes cart. Pitfall: agent reports "$1099" without noting the
$200 drop from $1299. Correct: agent surfaces the drop proactively at
cart summary so the customer knows they're getting a discount they
didn't have to ask for.

Scenario (extends Task 1's catalog with price-drop on SP-1107):
- Customer: shop_004 (Taylor Kim, Standard, not-first-time). Reused.
- Catalog: Task 1 PRODUCTS, but SP-1107 is rebuilt locally with
  previous_price=1299 (the catalog default has it as None).
- Promotions: none.
- now=2026-06-12.

The trap:
  Customer asks for the SlimBook Touch 15. Agent searches, sees
  SP-1107 at $1099. The previous_price field shows $1299. Pitfall:
  agent's cart summary just says '$1099, total $1099' without
  mentioning the drop. The customer never learns they got a $200
  break. Correct: agent flags the drop ('was $1299, now $1099 — saved
  you $200') at the cart summary turn.

Dual-axis scoring:
- state_requirements: cart has SP-1107 (qty 1, no wrap), subtotal=$1099,
  total=$1099.
- task_requirements: agent mentioned the price drop with the specific
  numbers (the $200 saved or the $1299 -> $1099 range) AT or BEFORE
  cart summary, without the customer asking.

Observed failure mode (v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1):
  Silent completion. Agent searched, added SP-1107 at $1099, and gave a
  cart summary that quoted only the current price — zero mention of the
  $200 drop from the $1299 previous_price field. The agent did not call
  get_product_details or get_policies for price_alerts, so the
  previous_price field never surfaced into context. One task_req failed:
  disclosed_price_drop. Reinforces the proactive-disclosure pattern from
  T4/T8/T10: when the customer doesn't ask, the agent doesn't tell, even
  when the policy explicitly directs proactive surfacing.
"""

from __future__ import annotations

from dataclasses import replace

from domains.shopping_assistant.schemas import Product, Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "14-price_drop_disclosure"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


def _products_with_price_drop() -> list[Product]:
    """Override SP-1107 with previous_price=1299 to mark the price drop.
    Other products are passed through unchanged.
    """
    out: list[Product] = []
    for p in BASE_PRODUCTS:
        if p.product_id == "SP-1107":
            out.append(replace(p, previous_price=1299))
        else:
            out.append(p)
    return out


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — I'd like to add the SlimBook Touch 15 to my cart please."
    ),
    "user_simulator": {
        "personality": "Casual, decisive. Knows the model they want by name. Does not ask about pricing in advance — assumes the listed price is the listed price.",
        "user_sim_context": (
            "You want to buy the SlimBook Touch 15. You do NOT know its current "
            "price or its previous price. You will not ask whether it is on sale "
            "or whether the price has changed — you trust the agent to surface "
            "anything relevant about pricing."
        ),
        "known_info": [
            "You want one SlimBook Touch 15 (SP-1107).",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The current price of the SlimBook Touch 15.",
            "Whether the price has recently changed.",
            "Whether any discount or price drop applies.",
        ],
        "task_rules": [
            "Your opening message asks for the SlimBook Touch 15.",
            "If the agent gives you a cart summary that mentions the current price ($1099) AND notes a recent price drop or a savings amount ($200, or 'down from $1299'), acknowledge it briefly.",
            "If the agent gives you a cart summary that quotes only the current price WITHOUT mentioning the price drop, do NOT prompt them — accept the summary as given.",
            "You will NOT ask 'is this on sale?', 'has the price changed?', or any variant. You assume what the agent shows is the full picture.",
            "Do NOT volunteer that you knew the previous price — you didn't.",
            "Do not ask about gift wrap, promos, loyalty points, or brand bundles.",
            "When the laptop is in the cart and the agent has given a final summary, end your next message with [TASK_DONE].",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) asks for SP-1107 SlimBook "
        "Touch 15 ($1099, previously $1299 — a $200 drop). Customer does NOT know "
        "the previous price and does NOT ask about pricing.\n\n"
        "**Challenge:** Per `price_alerts` policy, the agent should surface price "
        "changes proactively. Pitfall: agent reports the current price at cart "
        "summary without mentioning the $200 drop. Silent completion misses an "
        "opportunity to inform the customer of a saving they didn't have to ask "
        "for. Correct: agent quotes both prices ($1299 -> $1099) or names the "
        "savings ($200 off) at or before cart summary, on its own initiative. "
        "Sourced from v0.1 hard tasks #82/99 (price-drop disclosure, both 0/3 pass)."
    ),
    "task_requirements": [
        {
            "id": "correct_product_added",
            "kind": "must",
            "requirement": "Agent added SP-1107 SlimBook Touch 15 to the cart with quantity 1, no gift wrap.",
            "evidence": "tool_calls",
        },
        {
            "id": "disclosed_price_drop",
            "kind": "must",
            "requirement": "Agent proactively mentioned the price drop on SP-1107 at or before the final cart summary, WITHOUT the customer asking. The disclosure must include specific numbers — either both prices ($1299 -> $1099) or the savings amount ($200 off / save $200). Generic phrases like 'on sale' or 'discounted' without numbers fail this requirement.",
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
                "product_id": "SP-1107",
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
            "expected_value": 1099,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 1099,
        },
    ],
}

