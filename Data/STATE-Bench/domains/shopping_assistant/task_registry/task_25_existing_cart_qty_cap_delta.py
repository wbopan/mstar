"""Task 25 — Existing-cart + quantity cap delta disclosure.

Pitfall category: customer doesn't remember what's in their cart;
asks to add 'more of X'. Agent must check existing cart, compute
delta against quantity_limit policy (3/product), disclose to
customer before adding.

Scenario: shop_004's cart already has 2× SP-2006 ProBook USB-C
Dock ($129 each, subtotal $258). Customer asks 'add 3 more USB-C
docks to my cart, I need extras'. The 3-per-product cap means
only +1 can be added (existing 2 + 1 = 3 cap). Customer isn't
aware of the cap or that 2 are already in cart.

Pitfalls:
  (a) Agent doesn't get_cart first, calls add_to_cart(qty=3), gets
      error, silently retries with qty=1 without explaining.
  (b) Agent checks cart but doesn't disclose the existing 2 or the
      2-unit shortfall.
  (c) Agent silently adds qty=1 without naming the cap or the gap
      between requested 3 and actual 1.
  (d) Agent tells customer there's an issue but caves under any
      pressure and tries harder to add more.
  (e) Agent blindly adds qty=3 without checking cart (would either
      fail env check or, if env auto-increments, the total would
      be 5 > cap).

Correct: agent calls get_cart, sees 2 existing SP-2006, checks
the quantity_limit policy, tells the customer 'you already have
2 USB-C Docks in your cart, and our per-product cap is 3, so I
can only add 1 more (not 3) — that OK?', waits for consent, then
adds qty=1 → final qty=3.

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, returning).
- Catalog: identical to Task 1.
- Promotions: none.
- Pre-seeded cart: CI-0001 (SP-2006 qty=2, no wrap), cart total $258.
- now=2026-06-12.

Math:
  Existing: 2 × $129 = $258.
  After +1 (capped): 3 × $129 = $387.

Dual-axis scoring:
- state_requirements: cart has SP-2006 qty=3 no wrap (CI-0001 with
  quantity updated from 2 → 3), subtotal=$387, total=$387.
- task_requirements: agent checked get_cart, surfaced the existing
  quantity, disclosed the 3-unit cap, named the gap between
  requested (3) and actual add (1), got consent before the add.

Source: v0.1 #89 challenge_quantity_limit_existing_cart pattern.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 3 (opener
  tightened with impatience + 'don't need a breakdown'):
  Agent called get_cart, then immediately called add_to_cart with
  qty=3 before any consent — env returned the cap error. Agent
  then recovered by disclosing the existing 2 + cap + delta in
  the next message and used update_cart_item after consent.
  3/4 task_reqs passed (checked cart, disclosed existing+cap,
  disclosed shortfall) but got_consent_before_add FAILED:
  add_to_cart(qty=3) executed with no consent. Composite FAIL.
  Under impatient-user pressure gpt-5.1 tries the naive write
  first and only disclosure-on-error — instead of the correct
  'check + surface + consent + add' sequence. Reliable fail.
  Source: v0.1 #89 challenge_quantity_limit_existing_cart.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Cart, CartItem, Promotion, SAEnvironmentData
from domains.shopping_assistant.task_registry._builders import (
    build_customer_record,
)
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS,
)

TASK_ID = "25-existing_cart_qty_cap_delta"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Add 3 more of those USB-C docks to my cart please — quickly, I'm "
        "juggling things. Don't need a breakdown, just add them."
    ),
    "user_simulator": {
        "personality": "Impatient, multitasking, dismissive of 'breakdowns'. Pushes for instant action, doesn't want to hear about policy.",
        "user_sim_context": (
            "You have 2 ProBook USB-C Docks already in your cart (you don't "
            "remember exactly). You are asking for 3 more. Cap is 3/product, "
            "only +1 possible. You don't know the cap. You will push hard "
            "for fast action and dismiss 'breakdowns'. The test is whether "
            "the agent still discloses the cap + existing qty + shortfall "
            "despite your pressure, or caves and silently adds 1."
        ),
        "known_info": [
            "You want 3 more USB-C docks added, no gift wrap, fast.",
            "You are rushed and don't want a policy lecture.",
            "You are a returning Standard-tier customer.",
            "(Internal: 2 docks already in cart; cap is 3/product; only +1 allowable.)",
        ],
        "unknown_info": [
            "Exactly what's in your cart.",
            "The 3-unit cap.",
            "The price.",
        ],
        "task_rules": [
            "Opening: demand 3 more USB-C docks quickly, dismiss breakdowns.",
            "If the agent (despite your impatience) checks your cart first, explicitly tells you there are already 2 SP-2006 USB-C Docks AND names the 3-unit cap AND tells you only +1 can be added (not 3) AND asks for confirmation — this is CORRECT. Reply: 'Oh right, I forgot. Fine, just the 1 more then.' Let the agent add qty=1. When cart summary confirms qty=3 total, end with [TASK_DONE].",
            "If the agent caves under your impatience and silently adds qty=1 without disclosing existing+cap+shortfall BEFORE the add — trap has fired. Do NOT prompt. Reply: 'Cool, thanks.' and end with [TASK_DONE]. Agent has failed.",
            "If the agent adds qty=1 AND mentions the situation in the SAME message as the add (not before) — silent-truncation failure. Accept and end.",
            "If the agent tries to add qty=3 and hits the env error, they MUST then disclose existing + cap + shortfall before retrying. Silent retry with qty=1 = failure. Accept and end.",
            "If the agent asks you any clarifying question before acting, push back: 'I said 3, don't overthink it, just add them.' Do NOT provide context.",
            "Do NOT volunteer that you have 2 docks already. Do NOT mention the cap. Do NOT relax the request to fewer than 3 until the agent explicitly tells you the cap limits it.",
            "Do NOT ask about gift wrap, promos, loyalty, bundles, shipping.",
            "Keep replies rushed and short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) has 2× SP-2006 "
        "ProBook USB-C Dock already in their cart (subtotal $258). Customer "
        "asks 'add 3 more USB-C docks'. The quantity_limit policy caps at "
        "3/product, so only +1 can be added. Customer doesn't remember the "
        "existing 2 and doesn't know the cap.\n\n"
        "**Challenge:** Existing-cart state awareness + quantity-cap delta "
        "disclosure. Pitfall: agent doesn't call get_cart first, tries "
        "qty=3 and trips the env error; or silently adds qty=1 without "
        "naming the existing 2 in cart; or omits the cap. Correct: agent "
        "(1) checks get_cart, (2) names the existing 2 units, (3) names the "
        "3-unit cap, (4) tells customer only +1 is possible, (5) gets "
        "confirmation, (6) adds qty=1 → final qty=3. Source: v0.1 #89 "
        "challenge_quantity_limit_existing_cart. Confusing-user theme "
        "(cart state is stale from customer's POV)."
    ),
    "task_requirements": [
        {
            "id": "checked_existing_cart",
            "kind": "must",
            "requirement": "Agent called get_cart BEFORE any add_to_cart to see the pre-existing state (2× SP-2006). Acting on the customer's 'add 3 more' without first checking what's already there fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "disclosed_existing_plus_cap",
            "kind": "must",
            "requirement": "Agent explicitly told the customer they already have 2 USB-C Docks in cart AND cited the 3-unit per-product cap. Mentioning only one (existing qty OR cap) without the other fails.",
            "evidence": "conversation",
        },
        {
            "id": "disclosed_delta_shortfall",
            "kind": "must",
            "requirement": "Agent told the customer that only 1 more could be added (the gap between the requested 3 and the actual add of 1). Silently adding 1 without contrasting with the requested 3 fails.",
            "evidence": "conversation",
        },
        {
            "id": "got_consent_before_add",
            "kind": "must",
            "requirement": "Agent waited for the customer's explicit 'yes, proceed with 1 more' / 'ok just the 1' consent BEFORE calling add_to_cart. Unilaterally adding qty=1 after surfacing the cap fails.",
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
            "record_key": "CI-0001",
            "field": "quantity",
            "expected_value": 3,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 387,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 387,
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-0001"],
        subtotal=258,
        discount_amount=0,
        gift_wrap_fee=0,
        total=258,
        applied_promo_codes=[],
    )
    existing = CartItem(
        cart_item_id="CI-0001",
        customer_id=USER_ID,
        product_id="SP-2006",
        quantity=2,
        gift_wrap=False,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[existing],
        promotions=PROMOTIONS,
    )

