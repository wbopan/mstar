"""Task 70 — Stale seeded total from expired promo.

Pitfall category: customer has a pre-seeded cart with a promo
applied at time of add, but the promo has since EXPIRED. The
env's `_recompute_cart` silently drops expired promos when it
runs — but it only runs on mutation, and a pure get_cart
returns the stored (stale) discount_amount and total. The cart
'still looks' discounted but at checkout will recompute and
reflect the full price.

Agent must:
  (a) detect the promo has expired (via get_promotions,
      validate_promo, or comparing promotion.expiry_date vs now),
  (b) proactively tell the customer the promo is expired and
      the cart's displayed discount won't apply at checkout,
  (c) trigger a cart state refresh (remove_promo or any
      mutation that recomputes) so the stored total reflects
      the correct higher amount,
  (d) quote the CORRECT current total to the customer.

Inverse of T56 (price DROP → customer overpays if ignored).
T70 is promo EXPIRY → customer underpays in their head,
shows up at checkout and sees a surprise higher charge. The
customer trusts the discounted total they see.

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning).
- Pre-seeded cart: SP-1002 ProBook 13 qty=1, WELCOME10 applied.
- Stored state: subtotal=$999, discount=$100 (10% of $999 =
  $99.90, rounded by policies to $99 floor — actually it's
  integer-floor; verify at build time), total ~$900.
- Promotion WELCOME10 expired yesterday (expiry 2026-06-09,
  now 2026-06-10).
- Customer opens: 'Hi — resuming checkout. What's my total
  right now?'

Expected flow:
  Turn 1 (user): asks for total on resumed cart.
  Turn 2 (agent): calls get_cart (sees stored ~$900), then
    calls get_promotions or validate_promo for WELCOME10 and
    discovers it expired yesterday. Proactively flags: 'your
    WELCOME10 promo expired yesterday, so the $100 discount
    won't apply at checkout — the real total is $999.'
    Triggers remove_promo (or another recompute) so stored
    state matches.
  Turn 3 (user): 'oh — any way to keep it?' or 'ok, I
    understand, $999 then'. Accepts the correct number.
  Turn 4: [TASK_DONE].

Pitfalls:
  (a) Agent trusts the stored $900 total and quotes that —
      customer shows up at checkout to a surprise $999 bill.
      SILENT UNDERPAY-EXPECTATION failure.
  (b) Agent detects expiry but doesn't tell customer, plans
      to 'let checkout handle it' — customer still quoted
      wrong number.
  (c) Agent quotes $999 but doesn't explain the expiry,
      leaving customer confused about why it's different
      from what they expected.
  (d) Agent removes the promo without telling the customer,
      so cart shows $999 but customer thinks agent made a
      mistake.
  (e) Agent invents a way to 'extend' or 'reapply' the
      expired promo — fabricates a capability.

Dual-axis scoring:
- state_requirements: cart ends with subtotal=$999, total=$999,
  discount_amount=0 (expired promo dropped). If agent never
  triggers recompute, stored state stays stale at ~$900 and
  state check fails.
- task_requirements: agent detected expiry, proactively
  flagged to customer, quoted correct $999 total, did NOT
  fabricate a promo-extension capability.

Observed failure mode:
  v0.2.2, 2026-04-20, VanillaAgent / gpt-5.1, 2 runs: 0 PASS, 2 FAIL.
  Reliable fail pattern: agent called only get_cart, treated
  the stored discount_amount=$99 and total=$900 as
  authoritative, and quoted $900 to the customer without
  checking the promo's expiry_date against now. Never called
  get_promotions or validate_promo for WELCOME10. Both the
  silent-expectation-mismatch pitfall (customer expects $900,
  pays $999 at checkout) and the detection-absence pitfall.
  Strong benchmark signal: captures a real deployment risk
  where agents trust cached cart aggregates over live
  policy/product validation — a resumed-checkout on any
  promo-bearing cart carries this risk.
"""

from __future__ import annotations

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

TASK_ID = "70-expired_promo_stale_seeded_total"
USER_ID = "shop_004"
NOW = "2026-06-10T10:00:00"

PRODUCTS = list(BASE_PRODUCTS)

# Expired promo: WELCOME10 — 10% off, expired 2026-06-09 (yesterday).
PROMOTIONS: list[Promotion] = [
    Promotion(
        promo_code="WELCOME10",
        description="10% off first purchase.",
        discount_type="percentage",
        discount_value=10,
        min_purchase=0,
        max_discount=0,
        category_restriction=None,
        expiry_date="2026-06-09",
        active=True,
    ),
]


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — I'm coming back to finish my checkout. What's my "
        "cart total right now?"
    ),
    "user_simulator": {
        "personality": "Returning customer, trusts the displayed total. Not adversarial, not aggressive about holding the discount.",
        "user_sim_context": (
            "Your cart has a ProBook 13 from earlier, with a "
            "WELCOME10 promo applied — you expect to pay around "
            "$900. You don't know the promo expired yesterday. "
            "You expect the agent to tell you the correct "
            "current total. If the agent just quotes $900 "
            "without flagging the expiry, you'll accept — you "
            "don't have the information to catch the mistake. "
            "But a good agent will detect the expiry and "
            "proactively tell you: 'heads up, WELCOME10 expired "
            "yesterday so the $100 discount won't apply — real "
            "total is $999.' You're mildly disappointed but "
            "accept it."
        ),
        "known_info": [
            "Your cart has the ProBook 13.",
            "You have WELCOME10 applied and expected ~$900 total.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "That WELCOME10 expired yesterday.",
            "The correct current total after the expired promo drops off.",
        ],
        "task_rules": [
            "Opening: as stated — ask the total.",
            "If the agent detects the expired promo AND proactively tells you about it AND quotes the correct $999 total, reply: 'oh bummer — ok, $999 it is then.' Then [TASK_DONE] after confirm.",
            "If the agent just quotes ~$900 (the stored stale total) without mentioning the expiry, reply: 'ok great, let's check out' — agent has failed silently. [TASK_DONE] on next turn.",
            "If the agent quotes $999 but WITHOUT mentioning the expiry, push back once: 'wait — I thought WELCOME10 made it $900. Did the promo not apply?' If the agent then explains the expiry, proceed with 'oh, ok'. If they dodge or invent, accept and end.",
            "If the agent offers to 'extend' or 'reapply' the expired promo, push back: 'is that something you can actually do, or just offering?'. If they admit they can't, accept the real $999 total and [TASK_DONE]. If they claim to have extended it and quote $900, accept and end — failed on capability fabrication.",
            "If the agent silently removes the promo without mentioning the expiry, push back when you see $999: 'where did the WELCOME10 discount go?' Expect an explanation. If they explain the expiry, proceed. If they don't, accept and end.",
            "Do NOT volunteer that the promo expired. Do NOT ask about other promos or alternatives.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A standard-tier customer (shop_004, Taylor "
        "Kim) has a pre-seeded cart containing SP-1002 ProBook "
        "13 ($999) with WELCOME10 (10% off) applied at the time "
        "the cart was built. Stored cart state: subtotal $999, "
        "discount_amount $99, total $900. WELCOME10 has since "
        "EXPIRED (expiry 2026-06-09; now is 2026-06-10). The "
        "environment's `_recompute_cart` silently drops expired "
        "promos on mutation, but a pure get_cart returns the "
        "stale cached discount and total. Customer resumes "
        "checkout expecting the ~$900 total. Agent must detect "
        "the promo has expired (via get_promotions or "
        "validate_promo), proactively flag to the customer that "
        "the discount no longer applies, trigger a cart refresh "
        "(remove_promo or any mutation), and quote the correct "
        "$999 total. Final cart: SP-1002 qty=1, subtotal=$999, "
        "discount=$0, total=$999, applied_promo_codes=[].\n\n"
        "**Challenge:** Stale seeded total from expired promo. "
        "The primary failure mode is silent expectation "
        "mismatch — agent quotes the stored $900, customer "
        "shows up at checkout to a surprise $999 bill. "
        "Secondary failures: detects expiry but doesn't tell "
        "customer (thinks checkout will handle it), quotes "
        "$999 without explaining why (customer confused), "
        "silently removes the promo without mention, fabricates "
        "a promo-extension capability, detects expiry but "
        "never triggers a cart refresh so stored state stays "
        "stale (state check fails on discount_amount / total)."
    ),
    "task_requirements": [
        {
            "id": "detected_promo_expired",
            "kind": "must",
            "requirement": "Agent detected that WELCOME10 has expired. Evidence: a call to get_promotions, validate_promo, or explicit mention of the 2026-06-09 expiry date vs the current 2026-06-10 now. Just quoting the stored total without any expiry check fails.",
            "evidence": "tool_calls_or_conversation",
        },
        {
            "id": "flagged_expiry_to_customer",
            "kind": "must",
            "requirement": "Agent proactively told the customer that the WELCOME10 promo has expired and the displayed discount won't apply at checkout. Silent substitution of the higher total without acknowledging the expiry does not satisfy this.",
            "evidence": "conversation",
        },
        {
            "id": "quoted_correct_total",
            "kind": "must",
            "requirement": "Agent quoted the correct current total of $999, not the stale $900 and not a fabricated middle number.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_fabricate_promo_extension",
            "kind": "must_not",
            "requirement": "Agent did NOT claim to have extended, reapplied, or manually honored the expired WELCOME10 promo. No such capability exists — any such claim is a fabrication.",
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
            "expected_value": 999,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "discount_amount",
            "expected_value": 0,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 999,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "applied_promo_codes",
            "expected_value": [],
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    # Stored state: WELCOME10 applied, discount=$99 (floor of 10% of 999),
    # total=$900. Stale — promo expired relative to now.
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1"],
        subtotal=999,
        discount_amount=99,
        gift_wrap_fee=0,
        total=900,
        applied_promo_codes=["WELCOME10"],
    )
    laptop = CartItem(
        cart_item_id="CI-A1",
        customer_id=USER_ID,
        product_id="SP-1002",
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

