"""Task 56 — Stale-seeded cart total (price drop since add).

Pitfall category: customer has a pre-seeded cart whose
stored subtotal is STALE — one item's price has since
DROPPED, but the cart record still shows the old higher
total. The env's _recompute_cart only runs on mutation,
so reading get_cart returns the stale cached numbers.
Agent must detect the discrepancy via get_product, flag
the price drop to the customer, and ensure the customer
pays the CORRECT (lower) current price, not the stale
seeded total.

Inverse of T49 (price INCREASE on resumed cart — agent
must flag so customer isn't blindsided by higher bill).
T56 is price DECREASE on resumed cart — stale total is
HIGHER than current price; if agent trusts the seeded
number, customer overpays.

Multi-turn structure:
  Pre-seeded: SP-1001 SlimBook Air 13 in cart.
    - Stored cart subtotal: $849 (old price at time of add).
    - Current product price: $799 (dropped from $849).
    - previous_price field = $849 to signal the drop.

  Turn 1 (user): 'hi — I'm resuming my checkout. What's
    my cart total?'
  Turn 2 (agent): SHOULD call get_product for SP-1001 to
    verify current price, discover $799 current vs $849
    stored subtotal. SHOULD proactively flag the price
    drop and offer the lower price.
  Turn 3 (user): depending on agent — accepts the lower
    total if flagged; else asks to verify total matches.

Pitfalls:
  (a) Agent trusts the seeded get_cart subtotal ($849)
      and quotes that as the total. Customer overpays
      by $50. Silent — customer has no way to know.
  (b) Agent notices the drop via get_product but
      DOESN'T tell the customer (thinks the env 'will
      handle it at checkout').
  (c) Agent tells customer the RIGHT current price but
      doesn't trigger a cart recompute (e.g. via a
      dummy mutation), leaving the stored cart total
      wrong for the actual checkout.
  (d) Agent invents a wrong old/new pair ('was $899
      now $849').

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, returning).
- Pre-seeded cart: SP-1001 qty=1 no wrap, stored
  subtotal=$849, total=$849.
- Catalog: T1 BASE_PRODUCTS with SP-1001 overridden to
  price=$799, previous_price=$849 (drop signal).
- Promotions: none.
- now=2026-06-12.

Math:
  Stored subtotal: $849 (stale).
  Current SP-1001: $799.
  True current total: $799.
  Delta: -$50 (customer's benefit).

Dual-axis scoring:
- state_requirements: cart ends with SP-1001 qty=1 and
  AFTER any recompute, subtotal/total reflect $799
  current. If agent causes no mutation, seeded $849
  stays — this is a fail mode.
- task_requirements: agent called get_product for
  SP-1001, detected the price drop (previous_price vs
  current), proactively flagged it to the customer,
  quoted the correct $799 total.

Observed failure mode:
  v0.2.2, 2026-04-19, VanillaAgent / gpt-5.1, iter 1:
  Agent called get_cart, which returned items_view with
  unit_price=$799 (live from products table) AND stored
  subtotal=$849 (stale cached). Agent noticed the
  discrepancy — customer even flagged it in turn 2. In
  response, agent SIDED WITH THE STORED TOTAL: 'You'll
  be charged $849 at checkout' and rationalized the
  $799 unit price as 'display-only'. This is the
  worst-case failure: agent detected the stale cache
  but trusted the stored number over the live
  product price. Customer overcharged by $50.
  state_pass=0 (cart stayed $849 — no repair
  mutation), task_req=0. Reliable fail pattern:
  gpt-5.1 treats cart subtotal/total as
  authoritative even when live unit prices in the
  same response contradict it. Tests whether the
  agent recognizes that cart aggregates only refresh
  on mutation and live prices are the source of
  truth. A real deployment risk — customers
  resuming checkouts after a price drop would
  silently pay the old higher price without any
  recourse.
"""

from __future__ import annotations

from dataclasses import replace

from domains.shopping_assistant.schemas import (
    Cart,
    CartItem,
    Promotion,
    SAEnvironmentData,
)
from domains.shopping_assistant.task_registry._builders import (
    build_customer_record,
)
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "56-stale_seeded_total_price_drop"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


# Override SP-1001: current $799, previous $849 — price drop since add.
PRODUCTS = [
    replace(p, price=799, previous_price=849) if p.product_id == "SP-1001" else p
    for p in BASE_PRODUCTS
]


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — I'm coming back to finish my checkout. Can you tell "
        "me what my cart total is right now?"
    ),
    "user_simulator": {
        "personality": "Returning customer, trusts the system's number. Not adversarial.",
        "user_sim_context": (
            "Your cart has a SlimBook Air 13 from earlier. You "
            "DON'T know the price has since dropped from $849 "
            "to $799. You expect the agent to tell you the "
            "correct current total. If the agent just quotes "
            "$849 without mentioning anything, you'll accept — "
            "you don't have the information to correct them. "
            "But a good agent will check current prices and "
            "proactively flag the drop ('good news — the "
            "SlimBook went on sale, you'll pay $799 not $849')."
        ),
        "known_info": [
            "Your cart has the SlimBook Air 13.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The current price ($799) vs. what you paid when you added it ($849).",
            "Whether the agent checked current prices.",
        ],
        "task_rules": [
            "Opening: as stated — ask the total.",
            "If agent quotes $799 AND proactively mentions the price drop ('good news, went from $849 to $799'), reply: 'oh nice — ok let's go with that'. Next turn [TASK_DONE] after confirm.",
            "If agent quotes $849 (the stale number) without flagging any drop, reply: 'ok that works, let's check out'. Then [TASK_DONE]. Agent has failed — silent overcharge.",
            "If agent quotes $799 but WITHOUT mentioning the drop (just quotes the lower number), reply: 'oh — was it $849 before? I thought it was $849'. If agent then explains the drop, continue with 'ok great'. If agent dodges or invents, accept and end.",
            "If agent fabricates a different previous price ('was $899 now $849' or similar), accept and end — failed on accuracy.",
            "If agent says 'I'll apply the current price at checkout' but doesn't actually do anything to update the cart, push back: 'can you confirm the total I'll actually be charged?'. If agent then actually fixes the cart ($799 stored), continue. If not, end — failed.",
            "Do NOT volunteer the price change. Do NOT ask about wrap, promos, loyalty.",
            "Keep replies short — 1 sentence.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) has "
        "a pre-seeded cart with SP-1001 SlimBook Air 13. The "
        "cart's stored subtotal is STALE at $849; the current "
        "price has dropped to $799 (previous_price=$849). "
        "Customer asks for the total. Agent must verify current "
        "prices via get_product, detect the price drop via "
        "previous_price field, proactively tell customer about "
        "the drop, and ensure final cart reflects $799.\n\n"
        "**Challenge:** Stale-seeded total on price drop — "
        "INVERSE of T49 (price increase). Pitfall 1: agent "
        "trusts get_cart's stale $849 subtotal and silently "
        "overcharges. Pitfall 2: agent sees the drop but "
        "doesn't surface it. Pitfall 3: agent states $799 "
        "without recomputing the stored cart total. "
        "Pitfall 4: agent fabricates the price history. "
        "Tests whether agent treats seeded cart numbers as "
        "authoritative vs. as cached values that need "
        "price-recheck on resumption. A deployment risk: "
        "customers who come back after a price drop should "
        "benefit from the lower price, not pay the stale "
        "higher one."
    ),
    "task_requirements": [
        {
            "id": "checked_current_price_via_tool",
            "kind": "must",
            "requirement": "Agent called get_product (or equivalent) for SP-1001 — not just get_cart. Relying only on get_cart's cached subtotal fails the price-recheck requirement.",
            "evidence": "tool_calls",
        },
        {
            "id": "detected_and_flagged_price_drop",
            "kind": "must",
            "requirement": "Agent proactively told the customer that SP-1001's price dropped from $849 (previous) to $799 (current). Must cite both numbers or the $50 delta. Silent substitution of the lower price without acknowledging the drop is acceptable but sub-optimal; failing to cite the drop explicitly when quoting the total fails. Quoting the stale $849 without flagging also fails.",
            "evidence": "conversation",
        },
        {
            "id": "quoted_correct_current_total",
            "kind": "must",
            "requirement": "When asked the total, agent gave the correct CURRENT total of $799 — not the stale $849, not a fabricated middle number.",
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
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 799,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 799,
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    # Stored subtotal/total deliberately STALE at $849 (old price).
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1"],
        subtotal=849,
        discount_amount=0,
        gift_wrap_fee=0,
        total=849,
        applied_promo_codes=[],
    )
    laptop = CartItem(
        cart_item_id="CI-A1",
        customer_id=USER_ID,
        product_id="SP-1001",
        quantity=1,
        gift_wrap=False,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[laptop],
        promotions=PROMOTIONS,
    )

