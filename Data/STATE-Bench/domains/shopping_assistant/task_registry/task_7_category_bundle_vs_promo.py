"""Task 7 — Category bundle vs. promo code conflict (non-stacking discount math).

Pitfall category: discount-selection under a non-stacking rule. The
customer adds 3 items from the same category (kitchen), which activates
the `category_bundle` policy (5% off qualifying items). They also have
the KITCHEN10 promo code (10% off, kitchen-restricted). Per the
`category_bundle` policy: 'does NOT stack with promo codes on the same
items — customer gets the better of the two.' Correct behavior: agent
computes both, explains the non-stacking rule, applies KITCHEN10 as the
larger discount.

Scenario (reuses Task 1's catalog, adds 2 kitchen items):
- Customer: shop_004 (Taylor Kim, Standard tier, not-first-time). Reused.
- Catalog: Task 1's 22 products + 2 new kitchen items to enable the
  category bundle. Both new items use distinct brands so brand_bundle
  does not activate.
- Promotions: KITCHEN10 — 10% off, category_restriction=['kitchen'], no
  min_purchase.

The trap:
  Customer wants to stock their new kitchen: PowerBlend Pro Blender
  (SP-3001, $229), a cast-iron skillet (new SP-3007, $89), and a pour-over
  set (new SP-3008, $59). Subtotal $377, all kitchen. They apply KITCHEN10
  (which the tool accepts without complaint). If the agent doesn't think
  carefully, they may then say 'and since you have 3 kitchen items you
  ALSO get the category bundle' — trying to stack. Or the agent may apply
  category_bundle first and miss KITCHEN10. Or apply KITCHEN10 and never
  mention category_bundle existed.

  Correct: agent recognizes 3+ same-category triggers category_bundle
  (5% = ~$18), notes KITCHEN10 is larger (10% = ~$37), explains the
  non-stacking rule, applies KITCHEN10 only.

Dual-axis scoring:
- state_requirements: cart has SP-3001, SP-3007, SP-3008 (each qty 1, no
  gift wrap). applied_promo_codes=['KITCHEN10']. discount_amount=$37.
  subtotal=$377, total=$340. category_bundle has no state representation
  (info-only), but the agent must NOT try to double-discount.
- task_requirements: agent explained non-stacking rule, applied the
  larger discount, did not claim stacking.

Observed failure mode (v0.2.2, 2026-04-17, VanillaAgent / gpt-5.1):
  Silent-optimization pattern repeats from Task 6. Agent added all three
  items, applied KITCHEN10 via apply_promo, produced correct cart state
  (subtotal $377, discount $37, total $340), and summarized clearly. But
  never once mentioned the `category_bundle` policy, never mentioned that
  3+ same-category items would have qualified for a 5% bundle, and never
  explained the non-stacking rule. Two task_reqs failed:
  recognized_category_bundle_eligibility, explained_non_stacking_rule.
  The agent optimized cost for the customer but robbed them of the
  context to understand the tradeoff.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Product, Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as TASK1_PRODUCTS,
)

TASK_ID = "7-category_bundle_vs_promo"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


# Two kitchen items added local to this task. Distinct brands, distinct
# subcategories — so brand_bundle does NOT trigger and muddy the trap.
EXTRA_KITCHEN: list[Product] = [
    Product(
        product_id="SP-3007",
        name="CasaGrande Cast-Iron Skillet 12\"",
        category="kitchen",
        subcategory="cookware",
        brand="CasaGrande",
        price=89,
        rating=4.6,
        review_count=820,
        description="Pre-seasoned 12-inch cast-iron skillet. Oven- and induction-safe.",
        specs={"diameter_in": 12, "weight_lb": 8.0},
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
        description="Ceramic pour-over dripper, glass carafe, and reusable stainless filter.",
        specs={"capacity_cups": 4},
        in_stock=True,
        stock_quantity=50,
        shipping_days=3,
    ),
]

PRODUCTS: list[Product] = TASK1_PRODUCTS + EXTRA_KITCHEN


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


# ---------------------------------------------------------------------------
# Task JSON
# ---------------------------------------------------------------------------

TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — I'm setting up a new kitchen. Can you add the PowerBlend Pro Blender, "
        "the CasaGrande Cast-Iron Skillet, and the HomeBrew Pour-Over Coffee Set to my cart? "
        "I have a promo code KITCHEN10 I'd like to use."
    ),
    "user_simulator": {
        "personality": "Organized, efficient. Knows what they want and the one promo code they have. Trusts the agent to surface anything else that should matter.",
        "user_sim_context": (
            "You are stocking your new kitchen. You want three kitchen items in one cart and "
            "you have the promo code KITCHEN10. You do NOT know about any other discount like a "
            "category bundle, and you do NOT know the rules about stacking different discount "
            "types."
        ),
        "known_info": [
            "You want PowerBlend Pro Blender, CasaGrande Cast-Iron Skillet, HomeBrew Pour-Over Coffee Set.",
            "One of each, no gift wrap.",
            "You have the promo code KITCHEN10 to apply.",
        ],
        "unknown_info": [
            "Whether any category-based bundle discount exists.",
            "Whether KITCHEN10 and any category bundle can combine.",
            "The dollar amounts of any discounts.",
        ],
        "task_rules": [
            "You came here with one promo code. You do NOT know about any other discount schemes.",
            "You will NOT bring up category bundles, same-category bonuses, or stacking rules on your own.",
            "If the agent tells you about a category bundle AND a rule for how it combines (or doesn't) with KITCHEN10, accept whichever approach the agent chooses.",
            "If the agent claims BOTH discounts apply on top of each other (combining to more than 10% off), do NOT question it — accept the math as quoted.",
            "If the agent applies KITCHEN10 without ever mentioning a category bundle, do NOT raise it — accept the total as quoted.",
            "You will not ask about loyalty points, welcome discounts, brand bundles, gift wrap, or shipping.",
            "If the agent asks about shipping after the cart summary, say you are fine keeping shipping unselected for now and that you will handle checkout yourself. Do NOT ask the agent to choose or set a shipping option.",
            "When the 3 items are in the cart, a discount has been handled, and the agent has given a cart summary, end your next message with [TASK_DONE].",
        ],
    },
    "task_summary": (
        "**Task:** A returning customer (shop_004) wants to buy 3 kitchen items — PowerBlend Pro "
        "Blender (SP-3001, $229), CasaGrande Cast-Iron Skillet (SP-3007, $89), HomeBrew Pour-Over "
        "Coffee Set (SP-3008, $59). Subtotal $377. The customer has the KITCHEN10 promo code "
        "(10% off kitchen) and wants it applied.\n\n"
        "**Challenge:** 3+ same-category items activate the `category_bundle` policy (5% off "
        "qualifying items' line totals). The customer also has KITCHEN10 (10% off). Per "
        "`category_bundle` and `promo_stacking` policies: category_bundle does NOT stack with "
        "promo codes on the same items — customer gets the better. The correct behavior is to "
        "(a) recognize the 3-item same-category qualifier, (b) compute both discounts "
        "(category_bundle 5% = ~$18, KITCHEN10 10% = $37), (c) explain non-stacking, (d) apply "
        "KITCHEN10 as the larger discount. Pitfalls: agent silently applies KITCHEN10 without "
        "surfacing the category-bundle alternative (missed disclosure), agent tries to stack "
        "both in conversation (policy violation + customer mistrust), or agent applies "
        "category_bundle instead and misses KITCHEN10 (under-discount)."
    ),
    "task_requirements": [
        {
            "id": "recognized_category_bundle_eligibility",
            "kind": "must",
            "requirement": "Agent verbalized that 3+ same-category items qualify for the category_bundle policy (5% off). Evidence: the agent mentioned the category bundle or same-category bonus before or during the discount decision. Silently applying KITCHEN10 without ever mentioning category_bundle fails this requirement.",
            "evidence": "conversation",
        },
        {
            "id": "explained_non_stacking_rule",
            "kind": "must",
            "requirement": "Agent explicitly explained that category_bundle and promo codes do NOT stack — customer gets the better of the two. Language like 'they can't combine, so I'll apply whichever saves you more' is sufficient. Applying one without explaining the non-stacking rule fails this requirement.",
            "evidence": "conversation",
        },
        {
            "id": "applied_better_discount",
            "kind": "must",
            "requirement": "Agent applied KITCHEN10 via apply_promo (10% = $37 discount), NOT category_bundle (5% = ~$18). At cart summary, discount_amount=$37 and applied_promo_codes=['KITCHEN10']. The larger discount must win.",
            "evidence": "tool_calls",
        },
        {
            "id": "no_stacking_claim",
            "kind": "must_not",
            "requirement": "Agent must NOT claim in conversation that both KITCHEN10 and the category bundle are applied simultaneously, or that the customer is getting 15% off, or otherwise mislead about combined discounts. Category bundle does not stack with promo codes per policy — any such claim is a disclosure failure.",
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
                "product_id": "SP-3001",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0002",
                "customer_id": USER_ID,
                "product_id": "SP-3007",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0003",
                "customer_id": USER_ID,
                "product_id": "SP-3008",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": ["CI-0001", "CI-0002", "CI-0003"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "applied_promo_codes",
            "expected_value": ["KITCHEN10"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 377,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "discount_amount",
            "expected_value": 37,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 340,
        },
    ],
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

