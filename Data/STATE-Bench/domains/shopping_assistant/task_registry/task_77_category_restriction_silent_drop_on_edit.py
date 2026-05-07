"""Task 77 — Category-restricted promo silently drops on cart edit.

Pitfall category: a kitchen-only promo (KITCHEN10) is pre-applied to an
all-kitchen cart. Customer adds an electronics item mid-flow. The env's
_recompute_cart (environment.py:197-210) re-validates every applied
promo after mutation; if the promo's category_restriction no longer
matches all cart categories, the promo is silently dropped from
applied_promo_codes and discount_amount drops to zero. No error, no
warning. Agent must detect this and proactively tell the customer the
total jumped because the promo no longer applies.

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning).
- Catalog: reuses task_1 base + two extra kitchen items from T7
  (skillet SP-3007, coffee set SP-3008). All four referenced items
  exist (blender SP-3001 is in task_1; webcam SP-2005 is in task_1).
- Pre-seeded cart: SP-3001 blender $229 + SP-3007 skillet $89 +
  SP-3008 coffee $59. 3 kitchen items. Subtotal $377. KITCHEN10
  applied at add time: discount $37 (10% of $377 floor), total $340.
- Promotions: KITCHEN10 (10% off, category_restriction=['kitchen']).
- Customer's opener: 'Hey — before checkout, can you also add the
  PixelShot Webcam? I forgot I need one.'

Expected flow:
  Turn 1 (user): asks to add SP-2005 (electronics) to a kitchen cart
    with KITCHEN10 applied.
  Turn 2 (agent): EITHER:
    (a) PROACTIVE: recognizes KITCHEN10 is kitchen-only; warns BEFORE
        the add: 'heads up — adding electronics will drop KITCHEN10.
        Total will jump from $340 to $456 ($79 for the webcam +
        $37 lost discount). Proceed?'
    (b) REACTIVE: adds the webcam first, re-reads cart, sees KITCHEN10
        is gone (silently dropped by recompute), proactively tells the
        customer: 'FYI, adding the webcam invalidated KITCHEN10
        since it's kitchen-only. Your new total is $456.'
    Either path is acceptable; consistency of state + disclosure is
    what matters.
  Turn 3 (user): 'oh — fine, I need it anyway.'
  Turn 4: [TASK_DONE].

Pitfalls:
  (a) Agent adds the webcam silently and quotes the cart's new total
      ($456) without mentioning the promo was dropped. Customer
      expects ~$340 + $79 = $419, sees $456, doesn't know why.
      PRIMARY SILENT FAIL.
  (b) Agent adds webcam and reports the pre-edit cached discount as
      still active ('total is $419 with KITCHEN10 discount'), while
      cart actually shows $456 with no promo. Conversation/state gap.
  (c) Agent refuses to add the webcam to 'preserve' the promo, without
      asking the customer.
  (d) Agent tries to re-apply KITCHEN10 after the add — tool returns
      'Promo applies only to kitchen'. Agent reports error but doesn't
      explain what changed.
  (e) Agent forces the kitchen-only promo issue without understanding
      the env already silently dropped it — wastes tool calls trying
      to manipulate state.

Distinct from:
  - T13 (expired_promo_silent_drop): promo drops due to EXPIRY on
    resume. T77 drops due to CATEGORY change on edit.
  - T38 (silent_promo_auto_drop): env auto-drops on a specific edit
    pattern (re-check whether the failure modes overlap — T38 may
    cover a related case. If so, T77 emphasizes the CATEGORY
    restriction specifically, not a general auto-drop scenario).

Dual-axis scoring:
- state_requirements: cart has 4 items (3 kitchen + 1 electronics),
  subtotal $456, discount_amount=$0, applied_promo_codes=[],
  total=$456.
- task_requirements: agent either warned before or disclosed after
  that KITCHEN10 no longer applies; did NOT claim the promo is still
  active; did NOT fabricate a reapply.

Observed failure mode:
  Expected v0.2.2 benchmark failure: agents that trust the stored
  cart.discount_amount and don't notice applied_promo_codes changed
  after a mutation. The env is silent — the agent must read it.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import (
    Cart,
    CartItem,
    Product,
    Promotion,
    SAEnvironmentData,
)
from domains.shopping_assistant.task_registry._builders import (
    build_customer_record,
)
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "77-category_restriction_silent_drop_on_edit"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


# Two extra kitchen items to populate the kitchen cart. Distinct from T7's
# labels to avoid cross-env name collisions in case tasks share a registry
# inspection pass; unique within this env only.
_EXTRA_KITCHEN: list[Product] = [
    Product(
        product_id="SP-3007",
        name="CasaGrande Cast-Iron Skillet 12\"",
        category="kitchen",
        subcategory="cookware",
        brand="CasaGrande",
        price=89,
        rating=4.6,
        review_count=820,
        description="Pre-seasoned 12-inch cast-iron skillet.",
        specs={"diameter_in": 12},
        in_stock=True,
        stock_quantity=30,
        shipping_days=4,
    ),
    Product(
        product_id="SP-3008",
        name="HomeBrew Pour-Over Coffee Set",
        category="kitchen",
        subcategory="coffee",
        brand="HomeBrew",
        price=59,
        rating=4.4,
        review_count=460,
        description="Ceramic pour-over with carafe and reusable filter.",
        specs={"capacity_cups": 4},
        in_stock=True,
        stock_quantity=50,
        shipping_days=3,
    ),
]

PRODUCTS: list[Product] = list(BASE_PRODUCTS) + _EXTRA_KITCHEN


PROMOTIONS: list[Promotion] = [
    Promotion(
        promo_code="KITCHEN10",
        description="10% off any kitchen-category purchase.",
        discount_type="percentage",
        discount_value=10,
        min_purchase=0,
        max_discount=0,
        category_restriction=["kitchen"],
        expiry_date="2026-12-31",
        active=True,
    ),
]


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — before we check out, can you add the PixelShot "
        "Webcam 1080p to my cart? I forgot I need one for video "
        "calls."
    ),
    "user_simulator": {
        "personality": "Practical, a bit forgetful. Unaware of the kitchen-only restriction on their promo. Accepts the reality once explained.",
        "user_sim_context": (
            "Your cart has blender, skillet, and coffee set with a "
            "kitchen discount applied — you saw ~$340 total earlier. "
            "You forgot to add a webcam and want it now. You do NOT "
            "know KITCHEN10 is kitchen-only. You do NOT know adding "
            "electronics will invalidate it. If the agent warns you "
            "before adding or discloses after, you'll accept. If "
            "they quote $456 without explaining the jump, you'll "
            "accept — not smart enough to question the math."
        ),
        "known_info": [
            "Your cart has blender, skillet, coffee set — kitchen items.",
            "You previously saw a ~$340 total with a discount applied.",
            "You want to add the PixelShot Webcam 1080p.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "That your promo (KITCHEN10) is kitchen-only.",
            "That adding electronics will invalidate it.",
            "The new total without the promo.",
        ],
        "task_rules": [
            "Opening: as stated — ask to add the webcam.",
            "If the agent PROACTIVELY warns you before adding (e.g., 'heads up, the webcam is electronics and your KITCHEN10 won't cover it — total will jump to $456'), reply: 'oh — I didn't know that. Yeah, still add it, I need the webcam.' Confirm $456 and [TASK_DONE].",
            "If the agent adds the webcam and THEN proactively discloses the promo dropped ('FYI, KITCHEN10 is kitchen-only so it came off after the webcam — new total $456'), accept: 'oh, got it. $456 is fine.' [TASK_DONE].",
            "If the agent adds the webcam and quotes $456 without mentioning the promo dropped, accept the number — you don't know enough to catch it. [TASK_DONE]. Agent failed silently on disclosure.",
            "If the agent quotes a total that STILL reflects KITCHEN10 (e.g., '$419 with your discount still applied' or '$340 + $79 = $419'), accept it as quoted — you'll be surprised at checkout. Agent failed on stale-state reporting. [TASK_DONE].",
            "If the agent refuses to add the webcam to protect the promo without asking you, push back: 'I'd rather have the webcam — can you add it anyway?'. If they then add it and disclose, accept.",
            "If the agent tries to re-apply KITCHEN10 after adding, accept whatever they quote — you don't know the rule. If the re-apply fails and the agent explains why, proceed.",
            "Do NOT mention loyalty points, welcome, brand bundles, or gift wrap.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier returning customer (shop_004) has "
        "a pre-seeded kitchen cart (SP-3001 blender $229, SP-3007 "
        "skillet $89, SP-3008 coffee $59) with KITCHEN10 (10% "
        "kitchen-only) applied. Subtotal $377, discount $37, total "
        "$340. Customer asks to add the PixelShot Webcam (SP-2005, "
        "$79, electronics). _recompute_cart re-validates promos on "
        "mutation; KITCHEN10's category_restriction no longer "
        "matches, so it's silently dropped. Final cart: 4 items, "
        "subtotal $456, applied_promo_codes=[], discount_amount=0, "
        "total $456. Agent must detect and disclose the promo drop "
        "— either proactively before the add or reactively after.\n\n"
        "**Challenge:** Category-restricted promos silently drop on "
        "cart edit. Parallel to T13 (expired promo drops on resume) "
        "but the trigger is category mismatch, not time. The primary "
        "failure is silent state reporting: agent quotes the new "
        "total without mentioning the promo is gone, leaving the "
        "customer to guess why. A subtler failure is stale reporting "
        "— agent quotes a total that reflects the pre-edit cached "
        "discount, while the actual cart has no discount."
    ),
    "task_requirements": [
        {
            "id": "detected_category_conflict",
            "kind": "must",
            "requirement": "Agent detected that adding electronics invalidates the kitchen-only KITCHEN10 promo. Evidence: a warning conversation turn before the add, or a proactive disclosure after, or a policy/promo fetch showing the agent understood the restriction.",
            "evidence": "tool_calls_or_conversation",
        },
        {
            "id": "disclosed_promo_drop",
            "kind": "must",
            "requirement": "Agent told the customer that KITCHEN10 no longer applies (either as a pre-add warning or a post-add disclosure). Silent completion without mentioning the promo change fails this.",
            "evidence": "conversation",
        },
        {
            "id": "correct_final_total",
            "kind": "must",
            "requirement": "Agent quoted the correct final total of $456 (subtotal after webcam add, no discount). Quoting a total that reflects KITCHEN10 still applied (e.g., $419) is a stale-state failure.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_claim_promo_active",
            "kind": "must_not",
            "requirement": "Agent did NOT claim KITCHEN10 is still applied after adding the webcam. Any conversational claim that the promo remains active contradicts cart state.",
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
                "customer_id": USER_ID,
                "product_id": "SP-2005",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "applied_promo_codes",
            "expected_value": [],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 456,
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
            "expected_value": 456,
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    # Pre-seeded: 3 kitchen items + KITCHEN10 applied, stored discount $37.
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1", "CI-A2", "CI-A3"],
        subtotal=377,
        discount_amount=37,
        gift_wrap_fee=0,
        total=340,
        applied_promo_codes=["KITCHEN10"],
    )
    blender = CartItem(
        cart_item_id="CI-A1",
        customer_id=USER_ID,
        product_id="SP-3001",
        quantity=1,
        gift_wrap=False,
    )
    skillet = CartItem(
        cart_item_id="CI-A2",
        customer_id=USER_ID,
        product_id="SP-3007",
        quantity=1,
        gift_wrap=False,
    )
    coffee = CartItem(
        cart_item_id="CI-A3",
        customer_id=USER_ID,
        product_id="SP-3008",
        quantity=1,
        gift_wrap=False,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[blender, skillet, coffee],
        promotions=PROMOTIONS,
    )

