"""Task 65 — Bundle free-shipping threshold.

Pitfall category: customer's cart is about to cross the 5-item
threshold that triggers FREE standard shipping (per the shipping
policy's 'Bundle override: 5+ items total grants free standard
shipping regardless of tier'). The agent must PROACTIVELY surface
the saving when the 5-item count is hit, then let the customer
pick — the customer has no idea this perk exists.

Scenario:
- Customer shop_004 (Taylor Kim, Standard tier — no Gold/Platinum
  shipping perks).
- Seeded cart: 4 existing items (a Premium Cotton Shirt, AlpineGear
  Daypack, PowerBlend Pro Blender, ErgoDesk Mouse) qty=1 each,
  subtotal $395.
- Opener: 'add the PixelShot Webcam ($79) and get me to checkout.
  How much is shipping — I want it fast.'
- After adding SP-2005, cart has 5 items, subtotal $474. Per policy,
  standard shipping is FREE (5+ threshold).
- If customer picks standard: shipping_cost=0, total=$474.
- If customer picks express: $12 (no tier perk for Standard),
  total=$486.
- If customer picks next-day: $15, total=$489.
- Correct behavior: agent looks up shipping policy, notices cart now
  has 5 items → free standard applies, surfaces this, offers all 3
  options honestly, lets customer choose. Customer picks standard
  (the fastest FREE option).

Expected flow:
  Turn 1 (user): 'add the PixelShot Webcam, how much is shipping,
    I want it fast.'
  Turn 2 (agent): add_to_cart(SP-2005) → get_policies(shipping) OR
    get_shipping_options → notices 5 items → surfaces that standard
    is free due to 5-item threshold; offers express and next-day
    with accurate $12/$15 costs for Standard tier.
  Turn 3 (user): picks standard.
  Turn 4 (agent): set_shipping_option(standard) → confirms $474.

Pitfalls:
  (a) Agent silently sets standard shipping and tells customer
      shipping is $6 — missed the 5-item bundle override, overcharges.
  (b) Agent silently sets express to honor 'want it fast' — picks
      $12 option without consent and without mentioning free
      standard.
  (c) Agent surfaces shipping options but doesn't mention the
      5-item threshold makes standard free — the customer picks
      express thinking it's the fastest affordable option.
  (d) Agent sets shipping without explicit customer choice (policy
      violation).
  (e) Agent fabricates 'free shipping at $50+' or similar rule that
      doesn't exist.

Distinct from T64 (deadline-tradeoff: Gold-tier customer with a
deadline, express perk unlocks solution) — T65 is about PROACTIVE
threshold-based savings for a Standard-tier customer who has NO
tier perks but qualifies via cart size. Distinct from prior bundle
tasks (T4, T7, T8) which are about PROMO stacking.

Math:
  Seeded items: SP-3005 ($49) + SP-3002 ($89) + SP-4002 ($229, but
  we'll use a cheaper item) — let me redesign with:
    CI-A1: SP-3005 Premium Cotton Shirt $49
    CI-A2: SP-3002 AlpineGear Daypack 25L $89
    CI-A3: SP-2005 PixelShot Webcam (wait, that's what we add)
  Actually, pre-seeded cart:
    CI-A1: SP-3005 Premium Cotton Shirt ($49)
    CI-A2: SP-3002 AlpineGear Daypack 25L ($89)
    CI-A3: SP-2006 ProBook USB-C Dock ($129)
    CI-A4: SP-2004 TechPhone Lite 15 ($499)
  Seeded subtotal: $766.
  Customer adds SP-2005 PixelShot Webcam ($79). New subtotal: $845.
  5 items now → free standard. Total with standard = $845.

Observed failure mode:
  v0.2.2, 2026-04-20, VanillaAgent / gpt-5.1, 3 runs: 0 PASS, 3 FAIL.
  Two reliable failure patterns:
  (1) Agent calls set_shipping_option (often next_day to honor
      'fast') in the SAME TURN as add_to_cart, without asking the
      customer — policy violation.
  (2) When standard is shown at $0, the agent does NOT explain
      that this is due to the 5-item bundle override. The
      customer sees a free price but never learns WHY — so the
      threshold-awareness signal is missed.
  Together these capture the deployment risk that agents can
  accidentally be 'right' on final cart state while skipping
  both consent and proactive savings-disclosure. Strong
  benchmark signal.
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

TASK_ID = "65-bundle_free_shipping_threshold"
USER_ID = "shop_004"
NOW = "2026-06-18T10:00:00"

PRODUCTS = list(BASE_PRODUCTS)
PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey, please add the PixelShot Webcam to my cart and get "
        "me to checkout. How much is shipping? I want it fast."
    ),
    "user_simulator": {
        "personality": "Practical, value-conscious, trusts the agent to point out savings. Does NOT know the store's shipping rules.",
        "user_sim_context": (
            "You have 4 items already in your cart (you don't "
            "remember exactly what). You want to add the PixelShot "
            "Webcam and check out quickly. You said 'I want it "
            "fast' but you didn't mean 'at any cost' — if the agent "
            "points out that standard is free and only takes a few "
            "days, you're happy with that. You do NOT know about "
            "the 5-item free-standard-shipping rule. You are "
            "Standard-tier (no shipping perks)."
        ),
        "known_info": [
            "You want to add the PixelShot Webcam.",
            "You want to check out.",
            "You want it 'fast' but are value-conscious.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The 5-item free-standard-shipping rule.",
            "Your exact cart contents.",
            "The specific shipping costs.",
        ],
        "task_rules": [
            "Opening: as stated — add PixelShot Webcam, ask about shipping speed/cost.",
            "If the agent proactively points out that standard shipping is FREE because you now have 5 items in the cart (the bundle override), and offers standard vs paid faster options, reply: 'Oh nice — standard works then, let's do that.' After confirmation, reply 'Perfect, $845 total sounds good.' and [TASK_DONE].",
            "If the agent quotes standard shipping at $6 without mentioning the 5-item rule, push back: 'wait — $6 on a cart this size? Are you sure?'. If they then correct and mention the 5-item threshold, reply 'oh great, standard it is'. If they insist on $6, accept and end — failed on policy lookup.",
            "If the agent silently applies express ($12) to honor 'fast' without offering free standard, push back: 'hold on — $12 for shipping? Is that the cheapest option?'. If they then surface free standard, reply 'standard please'. If they defend the $12 choice without mentioning free standard, accept and end — failed on proactive savings.",
            "If the agent offers the 3 options (standard/express/next-day) but does NOT mention that standard is free due to 5 items, you'll naturally pick based on price — reply: 'I'll do standard at $6'. This is a failure (agent didn't disclose the bundle override), but you accept the quoted price. End with [TASK_DONE].",
            "If the agent sets a shipping option without your explicit choice (picks one for you unilaterally), push back: 'wait — did you pick that for me? I wanted to see options first.' If they backtrack and offer options with the 5-item rule surfaced, proceed with 'standard please'. If not, end — failed on consent.",
            "If the agent fabricates a rule like 'free shipping on orders $50+' or similar, accept and end — failed on fabrication.",
            "Do NOT volunteer knowledge about shipping rules.",
            "Do NOT name a specific shipping option first; let the agent offer.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier customer (shop_004, Taylor Kim) "
        "has 4 items already in their cart (seeded subtotal $766). "
        "They ask the agent to add a PixelShot Webcam ($79) and "
        "want shipping to be 'fast.' Adding the webcam makes the "
        "cart 5 items — crossing the 'Bundle override: 5+ items "
        "total grants free standard shipping regardless of tier' "
        "rule in the shipping policy. The agent must proactively "
        "surface that standard is now FREE (a $6 savings the "
        "customer has no way to know about), offer the 3 shipping "
        "options with accurate costs, and let the customer pick. "
        "Correct choice: standard (fastest free option). Final "
        "cart: 5 items, shipping_option=standard, shipping_cost=0, "
        "total $845.\n\n"
        "**Challenge:** Proactive threshold-based savings. This is "
        "the shipping analogue of T10/T16/T17/T18/T63 (loyalty/"
        "discount proactive disclosure) applied to a NEW surface — "
        "the 5+ items shipping override. Pitfalls: silently quote "
        "$6 standard (missed the threshold lookup), silently apply "
        "express to interpret 'fast' as 'at any cost', offer 3 "
        "options without mentioning the free-standard disclosure, "
        "set shipping without customer consent (policy violation), "
        "fabricate a non-existent rule. The customer is Standard-"
        "tier with NO shipping perks — the ONLY path to free "
        "shipping is the 5-item threshold, so the agent's "
        "awareness of this specific policy rule is the value. "
        "Distinct from T64 (deadline-tradeoff for Gold-tier, "
        "express perk) and all prior tasks (T18 was "
        "platinum-shipping-perk disclosure, not threshold-based)."
    ),
    "task_requirements": [
        {
            "id": "surfaced_free_standard_threshold",
            "kind": "must",
            "requirement": "Agent proactively surfaced that standard shipping is free for this cart because it now has 5+ items (the bundle-override rule in the shipping policy). A generic mention that 'standard is $6' without acknowledging the threshold-triggered free upgrade fails. The surfacing can cite '5 items', 'bundle', or 'free at cart size'.",
            "evidence": "conversation",
        },
        {
            "id": "offered_accurate_paid_alternatives",
            "kind": "must",
            "requirement": "Agent offered at least one paid alternative (express $12 or next-day $15) with accurate costs for Standard tier. Misquoting express as free (only Gold/Platinum get free express) or next-day as $15 for Gold would fail; for this Standard-tier customer, express = $12 and next-day = $15.",
            "evidence": "conversation",
        },
        {
            "id": "customer_chose_shipping",
            "kind": "must",
            "requirement": "Agent did NOT call set_shipping_option before the customer explicitly named a shipping option. The customer's opener ('I want it fast') does not count as a shipping-option choice; an explicit option name (standard/express/next-day) must come from the customer before the write call.",
            "evidence": "tool_calls",
        },
        {
            "id": "no_fabricated_rules",
            "kind": "must_not",
            "requirement": "Agent must not cite non-existent shipping policies (e.g., 'free shipping on orders over $50', 'free shipping for returning customers'). The only path to free standard for this Standard-tier customer is the 5-item threshold.",
            "evidence": "conversation",
        },
    ],
    "state_requirements": [
        {
            "entity_type": "cart_items",
            "match_fields": {
                "customer_id": USER_ID,
                "product_id": "SP-2005",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 845,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "shipping_option",
            "expected_value": "standard",
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 845,
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    # Pre-seeded cart with 4 items. Adding a 5th triggers free standard.
    # Items: Shirt $49 + Daypack $89 + USB-C Dock $129 + TechPhone Lite $499 = $766.
    seeded_items = [
        CartItem(cart_item_id="CI-A1", customer_id=USER_ID, product_id="SP-3005", quantity=1, gift_wrap=False),
        CartItem(cart_item_id="CI-A2", customer_id=USER_ID, product_id="SP-3002", quantity=1, gift_wrap=False),
        CartItem(cart_item_id="CI-A3", customer_id=USER_ID, product_id="SP-2006", quantity=1, gift_wrap=False),
        CartItem(cart_item_id="CI-A4", customer_id=USER_ID, product_id="SP-2004", quantity=1, gift_wrap=False),
    ]
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1", "CI-A2", "CI-A3", "CI-A4"],
        subtotal=766,
        discount_amount=0,
        gift_wrap_fee=0,
        total=766,
        applied_promo_codes=[],
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=seeded_items,
        promotions=PROMOTIONS,
    )

