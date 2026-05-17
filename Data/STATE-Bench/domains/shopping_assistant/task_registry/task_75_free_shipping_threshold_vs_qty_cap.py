"""Task 75 — Free-shipping threshold collides with per-product quantity cap.

Pitfall category: customer's pre-seeded cart has 4 units across 2
products. Free standard shipping triggers at 5+ units. Customer's
instinct is to duplicate the cheapest high-qty item — but that item is
already at the 3-per-cart cap. Agent must detect the collision, refuse
the suggested add, and pivot to a different item (or accept the $6
standard fee).

Scenario:
- Customer shop_004 (Taylor Kim, Standard returning, 2200 pts).
- Pre-seeded cart: 3x SP-2006 ProBook USB-C Dock ($129 ea) + 1x SP-2005
  PixelShot Webcam 1080p ($79). Subtotal $466, 4 units, 1 item short
  of the 5-unit free-standard threshold.
- No promos. Not first-time. No loyalty-compound hooks.
- Customer's opener: 'what's shipping on this cart? And is there a way
  to make it free?'

Expected flow:
  Turn 1 (user): asks about shipping + cheapest path.
  Turn 2 (agent): calls get_cart (4 units) and get_shipping_options
    (standard = $6 at 4 units). Explains the 5+ threshold. Surfaces:
    adding 1 more item would make standard free.
  Turn 3 (user): 'oh — just add another dock then.'
  Turn 4 (agent): either checks get_cart first (sees dock at cap=3)
    or tries update_cart_item(SP-2006, qty=4) → tool returns 'Maximum
    3 of the same product per cart'. Either way, agent must pivot:
    'docks are capped at 3 per cart. Want another webcam instead?
    You'd pay $79 more but shipping becomes free, net $73 savings.'
  Turn 5 (user): 'yes, another webcam'.
  Turn 6 (agent): update_cart_item(SP-2005, qty=2) → subtotal $545,
    5 units. Calls set_shipping_option(standard), cost $0. Confirms
    total $545.
  Turn 7: [TASK_DONE].

Pitfalls:
  (a) Agent blindly calls update_cart_item(SP-2006, qty=4), tool
      rejects, agent reports error and stops ('couldn't add another
      dock'). Never pivots to alternative. Customer stuck with $6 fee.
  (b) Agent silently accepts $6 standard without mentioning the 5+
      threshold at all.
  (c) Agent recommends express shipping (not free at Standard tier)
      or next_day (not free) — misreading the tier-perk rules.
  (d) Agent duplicates the dock attempt 2-3 times hoping the cap will
      yield — no understanding of the policy.
  (e) Agent pivots but adds an expensive item that overshoots the
      'net savings' calculation (e.g., adds another $129 dock via a
      different product_id, or a $500 item, when the $79 webcam is
      the cheapest net-positive path).
  (f) Agent forgets to call set_shipping_option(standard) after
      reaching 5 items — cart.shipping_cost stays at 0 but
      shipping_option=None, so state_req fails.

Dual-axis scoring:
- state_requirements: dock qty unchanged at 3; webcam qty=2;
  subtotal=$545, shipping_option='standard', shipping_cost=0,
  total=$545.
- task_requirements: agent explained the 5+ threshold; recognized
  dock was at cap; pivoted to a different item; got customer consent
  on the pivot; did NOT attempt illegal dock-qty updates repeatedly.

Observed failure mode:
  Expected v0.2.2 benchmark failure: agents that treat tool errors as
  terminal ('can't do that') rather than as a signal to pivot. Also
  agents that skip the threshold analysis entirely and just quote
  standard at the $6 rate.
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

TASK_ID = "75-free_shipping_threshold_vs_qty_cap"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"

PRODUCTS = list(BASE_PRODUCTS)
PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — what's shipping going to cost me on this cart? "
        "And is there a way to make it free?"
    ),
    "user_simulator": {
        "personality": "Practical, cost-conscious, will follow the agent's suggestion if it saves money. Not adversarial.",
        "user_sim_context": (
            "Your cart has 3 docks and 1 webcam from earlier. You "
            "want to know shipping and will adjust the cart if "
            "there's a way to get free shipping. You do NOT know "
            "about the 3-per-product cap OR the 5+ free-shipping "
            "threshold. Your first instinct for 'add an item' will "
            "be to duplicate the dock (since that's what you have "
            "most of)."
        ),
        "known_info": [
            "Your cart has docks and a webcam.",
            "You want free shipping if possible.",
            "You're a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The 5-unit threshold for free standard shipping.",
            "The 3-per-product cap.",
            "That your dock is already at the cap.",
            "Express/next_day fees and tier perks.",
        ],
        "task_rules": [
            "Opening: as stated — ask about shipping and free options.",
            "If the agent explains the 5+ threshold and says 'one more item = free shipping', reply: 'oh — ok, just add another dock then.' (Your first instinct.)",
            "If the agent then explains the dock is at the 3-per-cart cap AND suggests adding a different item (e.g., another webcam), accept: 'sure, another webcam works.' After agent confirms $545 with free standard, reply 'perfect' and [TASK_DONE].",
            "If the agent tries and fails to add another dock without pivoting (e.g., 'sorry, can't add another dock — sticking with $6 shipping'), reply 'ok, fine' and [TASK_DONE]. Agent failed to pivot.",
            "If the agent quotes the $6 standard fee without surfacing the 5+ threshold at all, reply 'ok, let's just check out' and [TASK_DONE]. Agent failed silently on disclosure.",
            "If the agent suggests express or next_day as the free option (they aren't free for Standard tier), accept whatever they quote — you don't know the tier rules. [TASK_DONE] with whatever cost. Agent failed.",
            "If the agent picks a much more expensive pivot product (e.g., a $500 item instead of the $79 webcam) without explaining why, push back once: 'is there a cheaper item I could add to hit the threshold?'. If they then suggest the webcam, accept.",
            "If the agent reaches 5 items but the total still shows $6 shipping or shipping_option is unset, ask: 'is shipping free now?'. If they then set standard to free, accept. If they don't, accept whatever they quote and end.",
            "Do NOT mention loyalty points, promos, bundles, or gift wrap.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier returning customer (shop_004) "
        "has a pre-seeded cart: 3x SP-2006 ProBook USB-C Dock "
        "($129) + 1x SP-2005 PixelShot Webcam ($79). 4 units total, "
        "subtotal $466. Free standard shipping requires 5+ units. "
        "Customer asks about shipping and how to make it free. Agent "
        "surfaces the threshold; customer suggests duplicating the "
        "dock (already at 3-per-cart cap); agent must detect the "
        "collision, pivot to a different product (second webcam), "
        "get consent, update cart, and set standard shipping. Final "
        "cart: dock qty=3, webcam qty=2, subtotal $545, "
        "shipping_option='standard', shipping_cost=0, total $545.\n\n"
        "**Challenge:** Two policies collide (qty cap + "
        "free-shipping threshold). The primary failure is agents "
        "that treat the qty-cap error as terminal and never pivot. "
        "Also agents that skip the threshold analysis entirely. A "
        "subtle failure is forgetting to call set_shipping_option "
        "after crossing the threshold — the tool doesn't "
        "auto-recompute shipping on cart mutation."
    ),
    "task_requirements": [
        {
            "id": "explained_5plus_threshold",
            "kind": "must",
            "requirement": "Agent surfaced that standard shipping becomes free with 5 or more units in the cart, giving the customer the option to cross the threshold.",
            "evidence": "conversation",
        },
        {
            "id": "detected_dock_cap",
            "kind": "must",
            "requirement": "Agent recognized (either via get_cart + policy knowledge, or via a rejected update_cart_item attempt) that the dock is at the 3-per-cart cap and cannot be incremented further.",
            "evidence": "tool_calls_or_conversation",
        },
        {
            "id": "pivoted_to_alternative",
            "kind": "must",
            "requirement": "Agent suggested adding a different product (the webcam, already in cart) rather than giving up. The suggestion must be a concrete product the customer can agree to, not a vague 'try something else'.",
            "evidence": "conversation",
        },
        {
            "id": "crossed_threshold_and_set_shipping",
            "kind": "must",
            "requirement": "Agent updated cart to 5+ units (webcam qty=2) AND called set_shipping_option with 'standard'. The final cart must have shipping_option='standard' and shipping_cost=0.",
            "evidence": "tool_calls",
        },
        {
            "id": "did_not_retry_dock_add",
            "kind": "must_not",
            "requirement": "Agent did NOT repeatedly call update_cart_item or add_to_cart for SP-2006 beyond the first attempt that revealed the cap. Retrying the same capped operation is a failure mode.",
            "evidence": "tool_calls",
        },
    ],
    "state_requirements": [
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-A1",
                "customer_id": USER_ID,
                "product_id": "SP-2006",
            },
            "expected_fields": {"quantity": 3, "gift_wrap": False},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-A2",
                "customer_id": USER_ID,
                "product_id": "SP-2005",
            },
            "expected_fields": {"quantity": 2, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 545,
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
            "field": "shipping_cost",
            "expected_value": 0,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 545,
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1", "CI-A2"],
        subtotal=466,
        discount_amount=0,
        gift_wrap_fee=0,
        total=466,
        applied_promo_codes=[],
    )
    dock_item = CartItem(
        cart_item_id="CI-A1",
        customer_id=USER_ID,
        product_id="SP-2006",
        quantity=3,
        gift_wrap=False,
    )
    webcam_item = CartItem(
        cart_item_id="CI-A2",
        customer_id=USER_ID,
        product_id="SP-2005",
        quantity=1,
        gift_wrap=False,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[dock_item, webcam_item],
        promotions=PROMOTIONS,
    )

