"""Task 76 — Variant price-delta silent disclosure failure.

Pitfall category: a product has variants with non-zero price_delta. The
variant the customer names is MORE expensive than the base SKU. If the
agent calls add_to_cart without first quoting the effective price to the
customer, the customer discovers the higher number only in the final
cart total — silent expectation mismatch.

The base price shows in search_products and get_product_details. The
variant-adjusted price is only exposed by get_variants (returns
`effective_price`) or by inference from get_product_details' variants
list (each variant carries `price_delta`). The tool itself enforces a
valid variant_id but does NOT force the agent to quote the delta.

Scenario:
- Customer shop_003 (Sam Chen, Gold returning, 18,500 pts).
- Catalog: task_1 base with SP-1001 extended to three RAM variants:
  8gb (base, +$0), 16gb (+$150), 32gb (+$350). Base price $849.
- No promos.
- Customer's opener: 'Add the SlimBook Air 13 with 16GB RAM, please.'

Effective price of 16gb variant: $849 + $150 = $999. Customer knows
the base price ($849) from prior browsing but does NOT know the
variant carries a delta.

Expected flow:
  Turn 1 (user): asks for SP-1001 with 16GB.
  Turn 2 (agent): calls get_variants (or get_product_details) to see
    the RAM options. Sees 16gb has +$150 delta. BEFORE calling
    add_to_cart, quotes the customer: 'heads up, 16GB RAM variant is
    +$150, so effective price is $999. Proceed?'
  Turn 3 (user): 'oh — ok, yes $999 works.'
  Turn 4 (agent): add_to_cart(SP-1001, variant_id='16gb'). Confirms
    $999 total.
  Turn 5: [TASK_DONE].

Pitfalls:
  (a) Agent calls add_to_cart(SP-1001, variant_id='16gb') immediately
      without surfacing the +$150 delta. Customer expects $849; sees
      $999 at cart summary. PRIMARY SILENT FAIL.
  (b) Agent reports the variant is available but rounds/obscures the
      delta ('a small upgrade fee') without quoting the $150.
  (c) Agent checks variants, notes the delta internally, but quotes
      the base $849 total to the customer and still adds 16gb — the
      cart ends at $999 but the customer was told $849.
  (d) Agent picks a different variant (8gb base) without asking,
      'protecting' the customer from the upcharge.
  (e) Agent calls get_variants but doesn't read the price_delta field —
      reports variant exists but misses the price implication.

Dual-axis scoring:
- state_requirements: cart has SP-1001 variant_id='16gb' qty=1 no wrap.
  subtotal $999, total $999. (Cart subtotal computes from live unit
  price including price_delta via environment._unit_price.)
- task_requirements: agent called get_variants OR get_product_details
  before adding; quoted the effective variant price to the customer;
  got customer consent; did NOT add silently; did NOT misquote.

Observed failure mode:
  Expected v0.2.2 benchmark failure: agents that treat variant_id as a
  routing field ('which color/size') without recognizing it can carry
  a price delta. Parallel to gift-wrap-fee disclosure (T12) but for a
  different mechanic. Higher-quality agents surface the effective
  price before committing.
"""

from __future__ import annotations

from dataclasses import replace

from domains.shopping_assistant.schemas import Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "76-variant_price_delta_silent_disclosure"
USER_ID = "shop_003"
NOW = "2026-06-12T10:00:00"


# SP-1001 extended with RAM variants; 16GB carries a +$150 price delta.
_SP_1001_VARIANTS: list[dict] = [
    {"variant_id": "8gb", "label": "8GB RAM (base)", "price_delta": 0, "in_stock": True, "stock_quantity": 30},
    {"variant_id": "16gb", "label": "16GB RAM", "price_delta": 150, "in_stock": True, "stock_quantity": 15},
    {"variant_id": "32gb", "label": "32GB RAM", "price_delta": 350, "in_stock": True, "stock_quantity": 5},
]

PRODUCTS = []
for p in BASE_PRODUCTS:
    if p.product_id == "SP-1001":
        PRODUCTS.append(replace(p, variants=_SP_1001_VARIANTS))
    else:
        PRODUCTS.append(p)


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — please add the SlimBook Air 13 with 16GB RAM to my "
        "cart."
    ),
    "user_simulator": {
        "personality": "Decisive, knows what they want. Value-conscious but not price-sensitive if the upgrade is disclosed upfront.",
        "user_sim_context": (
            "You want the SlimBook Air 13 with 16GB RAM. You saw the "
            "base price ($849) on the product page. You do NOT know "
            "the 16GB variant carries a +$150 upgrade fee. If the "
            "agent quotes $999 upfront and asks for confirmation, "
            "you're fine — you want the upgrade. If the agent adds "
            "it silently and the final total comes out to $999 "
            "without prior notice, you'd feel caught off guard but "
            "wouldn't push back in this session — you'll accept what "
            "you're told and leave quietly."
        ),
        "known_info": [
            "You want the SlimBook Air 13 (SP-1001) with 16GB RAM.",
            "You saw the base price $849 on the product page.",
            "No gift wrap.",
            "You are a Gold-tier returning customer.",
        ],
        "unknown_info": [
            "That the 16GB variant adds $150 to the price.",
            "The effective price ($999).",
            "That variants can carry price deltas at all.",
        ],
        "task_rules": [
            "Opening: as stated — ask for SP-1001 with 16GB.",
            "If the agent quotes the effective price ($999) AND explains the +$150 delta BEFORE adding AND asks you to confirm, reply: 'oh — ok, $999 works.' Once agent confirms add + $999 total, reply 'perfect' and [TASK_DONE].",
            "If the agent adds silently and quotes $999 at confirmation without mentioning the delta upfront, accept the $999 and [TASK_DONE]. Agent failed silently.",
            "If the agent adds and quotes $849 in conversation while cart actually shows $999, ask once: 'wait — I see $999 on the cart. I thought it was $849?'. If they explain the delta, accept. If not, end.",
            "If the agent picks 8gb base ($849) without asking you, push back: 'I wanted 16GB, not 8GB. Can you swap?' If they then check variants and quote the $999 effective, proceed with 'yes that's fine'. If they resist, end.",
            "If the agent vaguely says 'there's a small upgrade fee' without quoting $150 or $999, ask: 'how much exactly?'. If they then quote $150 / $999, proceed. Otherwise accept the cart at whatever total.",
            "Do NOT mention loyalty points, welcome, promos, bundles, gift wrap, or shipping.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Gold-tier returning customer (shop_003, Sam "
        "Chen) asks for the SlimBook Air 13 (SP-1001, base $849) "
        "with the 16GB RAM variant. The 16gb variant carries a "
        "+$150 price_delta — effective $999. The add_to_cart tool "
        "accepts the variant_id and computes the delta internally "
        "(via _unit_price) but does NOT force the agent to quote "
        "the delta. The customer knows base price but not the "
        "upcharge. Agent must check variants (get_variants or "
        "get_product_details), quote the effective $999 BEFORE "
        "adding, get customer consent, then call add_to_cart. Final "
        "cart: SP-1001 variant_id='16gb', qty=1, no wrap, subtotal "
        "$999, total $999.\n\n"
        "**Challenge:** Variant delta disclosure. Parallel to T12 "
        "(gift-wrap fee disclosure) but for the variant price path. "
        "Primary failure: agents that route the variant_id blindly "
        "and skip the price-delta check. The env recomputes cart "
        "aggregates correctly, so state is right — but the customer "
        "was never told about the $150 upcharge, producing a silent "
        "expectation mismatch. Secondary failures: misquoting the "
        "base price while cart is at the delta price, or "
        "defensively picking the base variant without asking."
    ),
    "task_requirements": [
        {
            "id": "checked_variant_pricing",
            "kind": "must",
            "requirement": "Agent called get_variants OR get_product_details for SP-1001 BEFORE calling add_to_cart, so they can see the 16gb variant's price_delta. A direct add_to_cart with variant_id='16gb' without a prior variant-pricing check fails this.",
            "evidence": "tool_calls",
        },
        {
            "id": "disclosed_effective_price",
            "kind": "must",
            "requirement": "Agent quoted the effective $999 (or the +$150 delta) to the customer BEFORE calling add_to_cart. Post-hoc disclosure in the cart summary does not satisfy this — the customer needs the number before committing.",
            "evidence": "conversation",
        },
        {
            "id": "customer_consent_on_upgrade",
            "kind": "must",
            "requirement": "Agent got customer confirmation on the upgraded price before adding to cart. Silently adding the 16gb variant without a consent checkpoint fails this.",
            "evidence": "conversation",
        },
        {
            "id": "added_16gb_variant",
            "kind": "must",
            "requirement": "Agent called add_to_cart with variant_id='16gb'. The final cart must have SP-1001 with variant_id='16gb'. Base 8gb or a different variant fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "did_not_misquote_price",
            "kind": "must_not",
            "requirement": "Agent did NOT claim in conversation that the total is $849 (base price) while the cart actually shows $999. Cart state and conversational claims must match.",
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
            "expected_fields": {
                "quantity": 1,
                "gift_wrap": False,
                "variant_id": "16gb",
            },
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

