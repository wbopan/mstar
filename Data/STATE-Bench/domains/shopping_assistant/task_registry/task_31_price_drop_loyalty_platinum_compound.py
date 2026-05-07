"""Task 31 — Price-drop + loyalty compound disclosure (Platinum, no welcome).

Pitfall category: proactive compound disclosure WITHOUT any
welcome-discount axis. Two hidden signals both need to surface
on a bare one-line request:
  1. `previous_price` on the product indicates a recent price drop
     ($150 saving). Agent must notice via get_product / search_products.
  2. Customer is Platinum (3 pts/$) — loyalty_points policy says
     agent should mention points earned at cart completion.

Customer asks with no price framing, no tier mention, no promo
discussion: 'Add the TechPhone Lite 15 to my cart.' Both signals
must come from the agent's own discovery work.

Distinct from T14 (price-drop alone, Standard, SP-1107) and from
T17/T18 (which involved welcome or shipping). T31 is the pure
price-drop + loyalty two-beat test.

Pitfalls:
  (a) Agent quotes the current price at cart summary without
      mentioning the drop (T14-style failure, but now in the
      compound context).
  (b) Agent completes the purchase without mentioning loyalty
      points at all (T10-style failure reframed).
  (c) Agent mentions ONE of the two but not the other (partial
      compound failure — most likely price drop visible in
      search_products output and mentioned, but loyalty requires
      a separate get_customer_account call that gets skipped).
  (d) Agent mentions loyalty at wrong tier rate (1 pts/$ generic
      instead of 3 pts/$ Platinum) because skipped tier lookup.

Correct: agent calls search_products or get_product (sees
previous_price=$649 vs price=$499 → $150 drop, ~23% off), calls
get_customer_account (sees Platinum → 3 pts/$), adds the item,
and at cart summary names BOTH (a) the $150 price drop with
specific numbers and (b) ~1497 points earned at Platinum rate.

Scenario:
- Customer: shop_005 (Morgan Patel, Platinum, 104k pts, returning).
- Catalog: T1 BASE_PRODUCTS with SP-2004 TechPhone Lite 15
  overridden to previous_price=649 (current price=499).
- Promotions: none.
- now=2026-06-12.

Math:
  SP-2004 TechPhone Lite 15 current=$499, previous=$649.
  Price drop: $150 savings (~23%).
  Platinum loyalty: 3 pts/$ × $499 = 1497 points earned.
  Cart: subtotal $499, total $499.

Dual-axis scoring:
- state_requirements: cart has SP-2004 qty=1 no wrap, total $499.
- task_requirements: correct_product_added, disclosed_price_drop
  (with numbers), disclosed_loyalty_points (with Platinum rate +
  specific total), checked_customer_profile (tool evidence).

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 1:
  Agent did the bare minimum: search_products, add_to_cart, one-
  turn cart summary with current price $499 only. Did NOT call
  get_customer_account (so never surfaced Platinum 3 pts/$ /
  ~1497 pts). Did NOT mention previous_price or $150 drop —
  even though search_products returns previous_price in the
  product record. 3/4 task_reqs failed; composite FAIL. Reliable
  fail mode: on a terse one-line 'add X' request, gpt-5.1
  collapses to the mechanical minimum and skips both the tier
  lookup AND the price-history surfacing, despite both signals
  being trivially available from tools the agent already calls.
  Noise-free version of the same proactive-disclosure gap seen
  in T27/T29.
"""

from __future__ import annotations

from dataclasses import replace

from domains.shopping_assistant.schemas import Product, Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "31-price_drop_loyalty_platinum_compound"
USER_ID = "shop_005"
NOW = "2026-06-12T10:00:00"


def _products_with_phone_drop() -> list[Product]:
    """Override SP-2004 TechPhone Lite 15 with previous_price=649."""
    out: list[Product] = []
    for p in BASE_PRODUCTS:
        if p.product_id == "SP-2004":
            out.append(replace(p, previous_price=649))
        else:
            out.append(p)
    return out


PRODUCTS = _products_with_phone_drop()

PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Add the TechPhone Lite 15 to my cart."
    ),
    "user_simulator": {
        "personality": "Terse, decisive, knows what they want by name. Treats the agent as an order-taker unless the agent volunteers something interesting.",
        "user_sim_context": (
            "You want to buy the TechPhone Lite 15. You do not know its "
            "current price, do not know it recently dropped $150, do not "
            "know your Platinum loyalty rate (3 pts/$), and do not know "
            "how many points this purchase will earn. You will not ask "
            "about any of these. You trust the agent to surface anything "
            "that materially affects the transaction."
        ),
        "known_info": [
            "You want one TechPhone Lite 15 (SP-2004).",
            "You are a returning customer.",
            "(Internal: you are Platinum tier, 104k loyalty points, but you do not volunteer this.)",
        ],
        "unknown_info": [
            "The current price of the TechPhone Lite 15.",
            "That the price recently dropped $150 (was $649, now $499).",
            "Your loyalty rate (3 pts/$ for Platinum).",
            "Points you will earn on this purchase (~1497).",
        ],
        "task_rules": [
            "Opening is the one-line add request. Keep it as-is, do not elaborate.",
            "Do NOT ask about price history, sales, discounts, loyalty, points, promos, bundles, shipping, or gift wrap. Do not volunteer your tier.",
            "If the agent asks a clarifying question (color, storage, use case), respond briefly and redirect to just adding it: 'just the standard one, please.'",
            "If the agent, at cart summary, mentions BOTH (a) the price drop with specific numbers ($649 -> $499, or '$150 off', or 'saved $150 vs the previous price') AND (b) loyalty points earned with a specific number (~1497 pts, or the formula 3 pts/$ × $499), acknowledge briefly and end with [TASK_DONE]. Agent passed.",
            "If the agent mentions only ONE of the two (price drop OR loyalty), do NOT prompt about the missing one — accept the partial summary and end with [TASK_DONE]. Agent has failed.",
            "If the agent mentions NEITHER (bare cart total only), do NOT prompt — accept and end. Agent has failed.",
            "If the agent mentions loyalty with the wrong rate (1 pts/$, 2 pts/$, or a generic 'you'll earn points' without numbers), treat that as missing the loyalty disclosure.",
            "If the agent recommends additional items (cases, chargers), decline and redirect to the phone only.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Platinum customer (shop_005) asks with one "
        "line to add SP-2004 TechPhone Lite 15 to cart. The product "
        "currently costs $499, down from a previous_price of $649 — a "
        "$150 (~23%) drop. The customer is Platinum (3 pts/$), so this "
        "purchase earns ~1497 loyalty points. Customer asks about "
        "neither signal.\n\n"
        "**Challenge:** Compound proactive disclosure without welcome-"
        "discount axis. Pitfall: agent quotes current price at cart "
        "summary, skips price drop AND/OR skips loyalty disclosure. "
        "Tests whether the agent independently runs both discoveries "
        "(read product previous_price via search/get_product, read tier "
        "via get_customer_account) on a bare one-line request. Correct: "
        "surface the $150 drop with specific numbers AND ~1497 points "
        "earned at Platinum rate. Distinct from T14 (price-drop only, "
        "Standard) and from T17/T18 (which involved welcome or "
        "shipping axes)."
    ),
    "task_requirements": [
        {
            "id": "correct_product_added",
            "kind": "must",
            "requirement": "Agent added SP-2004 TechPhone Lite 15 to the cart with quantity=1 and gift_wrap=False.",
            "evidence": "tool_calls",
        },
        {
            "id": "checked_customer_profile",
            "kind": "must",
            "requirement": "Agent called get_customer_account for shop_005 before discussing loyalty benefits. Citing Platinum rate without the lookup (or wrong rate) fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "disclosed_price_drop",
            "kind": "must",
            "requirement": "Agent proactively mentioned the price drop on SP-2004 at or before the final cart summary, WITHOUT the customer asking. Must include specific numbers — either both prices ($649 -> $499) or the savings amount ('$150 off' / 'save $150'). Generic phrases ('on sale', 'discounted') without numbers fail.",
            "evidence": "conversation",
        },
        {
            "id": "disclosed_loyalty_points",
            "kind": "must",
            "requirement": "Agent proactively mentioned loyalty points earned with a specific number (~1497 pts) using the Platinum rate (3 pts/$). Wrong tier rate (1 or 2 pts/$) or generic 'you'll earn points' without a number fails.",
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
                "product_id": "SP-2004",
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
            "expected_value": 499,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 499,
        },
    ],
}

