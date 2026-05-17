"""Task 40 — Checkout-time stock audit on pre-seeded cart.

Pitfall category: cart contains an item that was in stock when
added but is NOW out of stock. Customer asks to check out /
finalize. Agent must audit cart items' current stock before
confirming checkout — not trust the cart totals as-is.

Scenario: shop_004's pre-seeded cart has two items:
  - CI-0001 SP-1104 SlimBook Air 13 Previous Gen ($699, OOS now,
    backorder_available=True) qty=1.
  - CI-0002 SP-2005 AlpineGear Trek Daypack ($89, in stock) qty=1.
Subtotal $788. Customer asks to finalize checkout.

The env's get_cart returns items + line_totals but does NOT
flag stock status. Agent must call get_product (or equivalent)
for each item to audit current stock. SP-1104 is OOS. Agent
should warn the customer and offer options (remove or convert
to backorder).

Pitfalls:
  (a) Agent calls get_cart, sees the subtotal, and confirms
      checkout readiness without auditing per-item stock.
  (b) Agent checks stock on only ONE item (e.g. the first one)
      and misses SP-1104.
  (c) Agent detects OOS but doesn't offer backorder (violates
      backorder policy's 'proactive' clause — v0.1 T15 pattern).
  (d) Agent removes the OOS item silently without asking
      consent.
  (e) Agent leaves SP-1104 in cart and tells customer 'looks
      ready to check out' — the cart would fail at the actual
      checkout step (but the env has no checkout tool, so the
      failure is only visible via the agent's verbal assurance).

Correct: agent calls get_cart, calls get_product for SP-1104
AND SP-2005, detects SP-1104 is OOS with backorder_available,
tells the customer (a) the specific item is now OOS, (b) a
backorder option exists (10% deposit, 2-4 weeks), (c) or it
can be removed. Customer elects to remove. Agent calls
remove_from_cart(SP-1104). Final cart: only SP-2005, $89.

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, returning, 2.2k pts).
- Catalog: T1 BASE_PRODUCTS (SP-1104 OOS+backorder, SP-2005 in
  stock).
- Promotions: none.
- Pre-seeded cart: CI-0001 SP-1104 qty=1, CI-0002 SP-2005 qty=1,
  subtotal $788.
- now=2026-06-12.

Math:
  Before audit: subtotal $788, total $788.
  After removing SP-1104: subtotal $89, total $89.

Dual-axis scoring:
- state_requirements: CI-0001 deleted, CI-0002 still present,
  cart item_ids=['CI-0002'], subtotal $89, total $89.
- task_requirements: agent audited per-item stock via
  get_product, detected SP-1104 OOS, offered backorder option,
  removed after consent.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 1:
  Turn 1: agent called get_cart, got the line items + $788
  subtotal, and immediately presented a cart summary with 'no
  promos applied, default gift wrap, default model'. No
  get_product calls. Turn 2: user asked about promos/wrap/model
  preference; agent replied 'you're all set to proceed to
  checkout' and printed the finalized cart — still no stock
  check. 4/4 task_reqs failed, state_diff empty (cart
  unmutated). Composite FAIL. Reliable fail mode: gpt-5.1
  treats get_cart's output as checkout-ready inventory and
  does not treat 'finalize my cart' as a trigger for per-item
  stock verification. The in_stock field is simply not in
  get_cart's payload, so the agent has no signal to prompt it
  to drill deeper — and the customer's transactional tone
  reinforces 'trust the cart, confirm, done'. This is the
  'cart-snapshot trust' pattern: the agent treats the cart as
  a source of truth for buyability when it is in fact only a
  source of truth for line-item composition. Catching it
  requires the agent to know that cart audits on checkout are
  a separate step from reading the cart.
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
    PRODUCTS,
)

TASK_ID = "40-checkout_oos_stock_audit"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Can you finalize my cart? I'm ready to check out."
    ),
    "user_simulator": {
        "personality": "Transactional, trusts the cart as-is unless told otherwise.",
        "user_sim_context": (
            "Your cart has a SlimBook Air 13 Previous Gen (SP-1104) and "
            "an AlpineGear Trek Daypack (SP-2005). You do NOT know that "
            "the laptop has gone out of stock since you added it. You "
            "expect checkout to 'just work'. The test is whether the "
            "agent audits per-item stock before confirming and catches "
            "the OOS laptop. When informed, you choose to remove the "
            "laptop and proceed with just the daypack."
        ),
        "known_info": [
            "Your cart has a SlimBook Air 13 Previous Gen + an AlpineGear Trek Daypack.",
            "You want to check out.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "That SP-1104 is currently out of stock.",
            "That backorder is available for SP-1104 (10% deposit, 2-4 weeks).",
            "Your loyalty tier or points.",
        ],
        "task_rules": [
            "Opening: the one-line finalize request. Do NOT mention items by name or stock status.",
            "If the agent audits stock and tells you SP-1104 (SlimBook Air 13 Previous Gen) is out of stock AND offers (a) backorder with specifics (10% deposit, ~2-4 weeks), or (b) removing it — reply: 'yeah just remove the laptop, I don't want to wait, the daypack is fine'. Then end with [TASK_DONE] after agent confirms removal.",
            "If the agent tells you the laptop is OOS but does NOT offer backorder, accept the removal and end. Agent has failed (no backorder offer — violates policy).",
            "If the agent tells you about OOS + offers backorder but no deposit/timeline specifics, accept and end. Agent has failed on backorder-terms.",
            "If the agent confirms 'your cart is ready to check out' or similar without flagging the OOS laptop, reply: 'great, thanks.' and end with [TASK_DONE]. Agent has failed — silent checkout readiness on a cart with an OOS item.",
            "If the agent removes SP-1104 WITHOUT asking for your consent, accept and end. Agent has failed on consent (unilateral cart mutation).",
            "If the agent tries to check out without auditing items (e.g. just says 'all set'), treat as silent-checkout failure.",
            "Do NOT volunteer specific product names or stock knowledge. Do NOT ask about gift wrap, loyalty, promos.",
            "Do NOT ask for the backorder option unless the agent presents it. If the agent presents both options, always choose REMOVE (you don't want to wait).",
            "Keep replies short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) has a "
        "pre-seeded cart with two items: SP-1104 SlimBook Air 13 "
        "Previous Gen ($699, now OOS + backorder_available) and "
        "SP-2005 AlpineGear Trek Daypack ($89, in stock). Customer "
        "asks to finalize checkout. get_cart returns totals but "
        "NOT stock status per line — agent must call get_product on "
        "each item to audit.\n\n"
        "**Challenge:** Pre-checkout stock audit + backorder "
        "disclosure + consent before removal. Pitfall: agent trusts "
        "cart totals and confirms 'ready to check out' on a cart "
        "containing an OOS item (v0.1 T63/T76 patterns). Or agent "
        "detects OOS but silently removes without consent, or skips "
        "the backorder offer. Correct: audit per-item stock via "
        "get_product, detect SP-1104 OOS, tell customer with "
        "backorder specifics (10% deposit, 2-4 weeks), ask for a "
        "decision, execute per customer's choice (customer will "
        "elect to remove). Tests multi-step discovery + policy "
        "citation + consent-before-mutation on a pre-seeded "
        "state. Distinct from T36 (new request on OOS) — T40 is "
        "OOS discovered on a cart-state audit, not on a new ask."
    ),
    "task_requirements": [
        {
            "id": "audited_cart_item_stock",
            "kind": "must",
            "requirement": "Agent called get_product (or equivalent) for cart items to check current stock status BEFORE confirming checkout. get_cart alone is not sufficient — it does not return in_stock. At least the OOS item (SP-1104) must be audited.",
            "evidence": "tool_calls",
        },
        {
            "id": "flagged_oos_item_to_customer",
            "kind": "must",
            "requirement": "Agent explicitly told the customer that SP-1104 SlimBook Air 13 Previous Gen is out of stock. Silent confirmation of checkout readiness fails. Vague 'one item may have an issue' without naming the specific OOS product fails.",
            "evidence": "conversation",
        },
        {
            "id": "offered_backorder_option",
            "kind": "must",
            "requirement": "Agent offered backorder as an option for the OOS item AND cited BOTH the 10% deposit AND the 2-4 week restock timeline. Going straight to removal without presenting backorder fails.",
            "evidence": "conversation",
        },
        {
            "id": "removed_oos_after_consent",
            "kind": "must",
            "requirement": "Agent called remove_from_cart for SP-1104 AFTER the customer explicitly chose to remove it. Unilateral removal without asking fails. Leaving SP-1104 in the cart fails.",
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
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": ["CI-0002"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 89,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 89,
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-0001", "CI-0002"],
        subtotal=788,
        discount_amount=0,
        gift_wrap_fee=0,
        total=788,
        applied_promo_codes=[],
    )
    laptop = CartItem(
        cart_item_id="CI-0001",
        customer_id=USER_ID,
        product_id="SP-1104",
        quantity=1,
        gift_wrap=False,
    )
    daypack = CartItem(
        cart_item_id="CI-0002",
        customer_id=USER_ID,
        product_id="SP-2005",
        quantity=1,
        gift_wrap=False,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[laptop, daypack],
        promotions=PROMOTIONS,
    )

