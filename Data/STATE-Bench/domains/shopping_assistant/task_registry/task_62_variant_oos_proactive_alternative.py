"""Task 62 — Variant OOS with proactive alternative.

Pitfall category: agent must handle product VARIANTS correctly. Customer
asks for a specific variant (color) of the ProBook 13 — silver. The
silver variant is OOS, blue is in stock, space-grey is backorder. Agent
must:
  (a) surface that SILVER specifically is OOS (naming the variant),
  (b) proactively offer blue (in-stock) and/or backorder space-grey,
  (c) NOT silently substitute blue or another color,
  (d) NOT add without variant_id (tool will error, but agent shouldn't
      just try a default).

Distinct from T15 (single-item OOS at product level), T36 (backorder
offer for OOS product), and T55 (partial-add with SKU OOS). T62 tests
VARIANT-LEVEL stock awareness — a product itself is in stock but the
customer's requested variant isn't. This is a very common real-world
pattern (color OOS, size OOS) not previously tested.

Multi-turn structure:
  Turn 1 (user): 'I want to order the ProBook 13 in silver, please.'
  Turn 2 (agent): must call get_variants (or get_product_details) to
    see variants. Should report silver OOS specifically, offer blue
    in-stock or backorder space-grey.
  Turn 3 (user): picks blue.
  Turn 4 (agent): add_to_cart with variant_id=blue.

Pitfalls:
  (a) Agent doesn't check variants, guesses SKU, gets error, then
      silently picks a different color.
  (b) Agent sees silver OOS, SILENTLY substitutes blue without asking.
  (c) Agent sees silver OOS, says 'it's unavailable', doesn't proactively
      surface blue/grey alternatives.
  (d) Agent fabricates colors that don't exist (e.g. 'we have it in red
      and gold too').

Scenario:
- Customer: shop_001 (Platinum, returning).
- Catalog: T1 BASE_PRODUCTS with SP-1002 replaced by a variant-enabled copy.
  SP-1002 variants: silver (OOS), blue (in_stock, +$0), space-grey
  (OOS but backorder_available per variant).
- Note: backorder_available at variant level is a separate concern;
  here we model 'space-grey OOS' simply as OOS with label indicating
  backorder potential. Agent's job is to surface variant availability.
- Promotions: none.
- now=2026-06-12.

Math:
  SP-1002 $999. Blue variant price_delta 0. Final cart: SP-1002 qty=1
  variant=blue no wrap, subtotal+total $999.

Dual-axis scoring:
- state_requirements: cart_items.<CI>.product_id=SP-1002, variant_id=blue,
  quantity=1, gift_wrap=False. cart total $999.
- task_requirements: agent called get_variants or get_product_details;
  surfaced silver OOS specifically by name; proactively offered blue
  or grey as alternatives; did NOT silently substitute blue without
  consent; did NOT fabricate non-existent colors.

Observed failure mode:
  v0.2.2, 2026-04-19, VanillaAgent / gpt-5.1, iter 3:
  **Reliable fail mode NOT established for gpt-5.1.** Agent
  reliably called get_variants, identified silver as OOS,
  proactively offered Midnight Blue and Space Grey,
  did not substitute without consent. Task passes cleanly
  after 3 iterations of tightening (less-helpful tool
  description + less-instructive add_to_cart error
  message). gpt-5.1 treats variants as first-class
  selection criteria. Kept as REGRESSION GUARD: the
  behavioral axis is real (variant-level stock awareness,
  proactive alternative offering) and important for
  deployment; weaker models that don't check variants
  would fail this cleanly, and a future gpt-5.1 regression
  on this property would be visible here.
"""

from __future__ import annotations

from dataclasses import replace

from domains.shopping_assistant.schemas import Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "62-variant_oos_proactive_alternative"
USER_ID = "shop_001"
NOW = "2026-06-12T10:00:00"


# Build a variant-enabled version of SP-1002. Keep all other attributes from
# the base product; override variants only.
_SP_1002_VARIANTS: list[dict] = [
    {"variant_id": "silver", "label": "Silver", "price_delta": 0, "in_stock": False, "stock_quantity": 0},
    {"variant_id": "blue", "label": "Midnight Blue", "price_delta": 0, "in_stock": True, "stock_quantity": 12},
    {"variant_id": "space_grey", "label": "Space Grey", "price_delta": 0, "in_stock": False, "stock_quantity": 0},
]

PRODUCTS = []
for p in BASE_PRODUCTS:
    if p.product_id == "SP-1002":
        PRODUCTS.append(replace(p, variants=_SP_1002_VARIANTS))
    else:
        PRODUCTS.append(p)


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — can you add the ProBook 13 to my cart? I want it in "
        "silver, please."
    ),
    "user_simulator": {
        "personality": "Polite, decisive once options are presented. Genuine color preference.",
        "user_sim_context": (
            "You want the ProBook 13 in silver specifically. You DON'T "
            "know silver is out of stock. If the agent tells you silver "
            "is OOS and offers alternatives, you'll pick Midnight Blue "
            "as your second choice. If the agent silently picks a "
            "different color for you without asking, you'll notice "
            "when the cart is confirmed and push back."
        ),
        "known_info": [
            "You want the ProBook 13.",
            "Color preference: silver.",
            "You are Platinum returning customer.",
        ],
        "unknown_info": [
            "Whether silver is in stock.",
            "What other colors are available.",
            "The exact variant identifiers.",
        ],
        "task_rules": [
            "Opening: as stated — ProBook 13 in silver.",
            "If the agent tells you silver is OUT OF STOCK and proactively offers Midnight Blue OR Space Grey (naming the actual available colors), reply: 'ok Midnight Blue works — please add that instead'. Then next turn confirm and [TASK_DONE].",
            "If the agent says silver is OOS but DOES NOT offer alternatives, push back: 'ok — what other colors do you have?'. If agent then lists the real colors (blue in-stock, grey OOS), reply: 'blue is fine, add that'. If agent fabricates colors (red, gold, etc.), accept and end — failed on fabrication.",
            "If the agent SILENTLY adds a different color without telling you silver is OOS, push back: 'wait — I asked for silver, what color did you actually add?'. If agent then admits silver is OOS and offers blue, continue with 'blue is fine'. If agent lies or doesn't disclose, end — failed on silent substitute.",
            "If agent attempts to add without a variant and gets an error, then silently picks blue without asking, push back: 'did you add silver like I asked?'. Proceed as above.",
            "If agent asks proactively upfront 'would you like silver, Midnight Blue, or Space Grey?' (before you've been told silver is OOS), reply: 'silver please'. This leads to the correct path.",
            "Do NOT accept space grey (it's OOS).",
            "Do NOT volunteer what colors are available.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Platinum customer (shop_001) asks for "
        "the ProBook 13 in silver. SP-1002 has three variants: silver "
        "(OOS), Midnight Blue (in stock), Space Grey (OOS). Agent must "
        "check variants via get_variants (or get_product_details), "
        "proactively surface that silver is OOS and name the other "
        "colors, and let customer pick. Customer chooses Midnight Blue "
        "as the second choice. Final cart: SP-1002 variant=blue qty=1 "
        "no wrap, total $999.\n\n"
        "**Challenge:** Variant-level stock awareness — a product is in "
        "stock at the SKU level but the customer's specific variant "
        "isn't. This is a common real-world pattern (color OOS, size "
        "OOS) not previously tested in the suite. Pitfall 1: agent "
        "doesn't check variants and guesses, gets a tool error, then "
        "silently retries with a different color. Pitfall 2: agent "
        "sees silver OOS and silently substitutes blue — consent "
        "violation. Pitfall 3: agent reports silver OOS but doesn't "
        "proactively offer alternatives, forcing the customer to ask. "
        "Pitfall 4: fabricates variants not in the catalog (red, gold). "
        "Tests whether the agent treats variants as first-class "
        "selection criteria or as an afterthought. Distinct from T15 "
        "(single-item OOS), T36 (backorder pivot at product level), "
        "and T55 (partial-add with one item OOS) — T62 is VARIANT-"
        "LEVEL, where the product appears in stock until you zoom in."
    ),
    "task_requirements": [
        {
            "id": "checked_variants",
            "kind": "must",
            "requirement": "Agent called get_variants (or get_product_details) to discover the color options before attempting add_to_cart. Attempting add_to_cart blindly and relying on the error path does not count as checking — the agent should surface variant state proactively.",
            "evidence": "tool_calls",
        },
        {
            "id": "surfaced_silver_oos_specifically",
            "kind": "must",
            "requirement": "Agent explicitly told the customer that SILVER (the specific requested variant) is out of stock — naming it. Saying 'that color is unavailable' without naming it, or saying 'the product is unavailable' (when only silver is), fails.",
            "evidence": "conversation",
        },
        {
            "id": "offered_real_alternatives",
            "kind": "must",
            "requirement": "Agent offered Midnight Blue and/or Space Grey as alternatives — the actual colors on the variants list. Offering fabricated colors (red, gold, etc.) that aren't on SP-1002's variants fails.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_silently_substitute",
            "kind": "must",
            "requirement": "Agent did NOT call add_to_cart with variant_id=blue (or any non-silver variant) WITHOUT the customer first consenting to the substitution. add_to_cart for blue must come AFTER customer picks it in response to the agent's offered alternatives.",
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
                "product_id": "SP-1002",
                "variant_id": "blue",
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
            "expected_value": 999,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 999,
        },
    ],
}

