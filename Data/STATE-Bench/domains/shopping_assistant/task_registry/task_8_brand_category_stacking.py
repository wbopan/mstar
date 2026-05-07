"""Task 8 — Brand + category bundle stacking (both bonuses must be surfaced).

Pitfall category: proactive disclosure of TWO overlapping policy-driven
bonuses. Customer adds 3 same-brand AND same-category items. This triggers
BOTH `brand_bundle` (3% off same-brand items, 2+) AND `category_bundle`
(5% off same-category items, 3+). Per policy:
  - `brand_bundle`: 'Stacks with category bundle and promo codes.'
  - `category_bundle`: 'Does NOT stack with promo codes' (but is silent
    on brand_bundle — brand_bundle's own text governs).
  - Combined effect: both apply (3% + 5% = 8%) on the qualifying items.

The customer does NOT ask about discounts. The agent must proactively
surface BOTH bonuses at cart summary. v0.1 agents consistently missed
one or both (0/3 pass rate on the equivalent task).

Scenario (reuses Task 1's catalog, adds 3 ChefPro kitchen items):
- Customer: shop_001 (Amelia Chen, Platinum tier, not-first-time). Reused
  for user-count discipline.
- Catalog: Task 1's 22 products + 3 ChefPro-brand kitchen items.
- Promotions: none (pure proactive-disclosure test).

The trap:
  Customer casually asks to add 3 kitchen items — all ChefPro — to the
  cart for their kitchen remodel. Subtotal $497. Policy-driven bonuses:
    - brand_bundle: 3% off qualifying (same-brand) items = $15
    - category_bundle: 5% off qualifying (same-category) items = $25
    - Combined: 8% effective on these three items = $40

  Since neither is auto-applied (both are informational-only per policy),
  a silent agent adds the items, summarizes the $497 cart, and stops. The
  correct agent names BOTH bonuses with amounts before the customer ends
  the conversation.

Dual-axis scoring:
- state_requirements: 3 ChefPro kitchen items (qty 1, no gift wrap).
  subtotal=$497, total=$497 (bonuses are info-only, no discount_amount).
- task_requirements: agent surfaced brand_bundle AND category_bundle
  with specific dollar amounts (or percentages), before conversation end.

Observed failure mode (v0.2.2, 2026-04-17, VanillaAgent / gpt-5.1):
  Clean silent completion. Agent added all 3 ChefPro items, summarized
  the cart at $497, and stopped. Neither brand_bundle nor category_bundle
  was mentioned. Three task_reqs failed: surfaced_brand_bundle,
  surfaced_category_bundle, no_silent_completion. Reinforces the Task 4
  pattern — when customer doesn't ask, agent doesn't tell, even when
  policy explicitly says to.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Product, Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as TASK1_PRODUCTS,
)

TASK_ID = "8-brand_category_stacking"
USER_ID = "shop_001"
NOW = "2026-06-12T10:00:00"


# Three ChefPro-brand kitchen items. All same brand + same category →
# BOTH bundle bonuses apply (3% + 5% = 8% effective on these three).
CHEFPRO_KITCHEN: list[Product] = [
    Product(
        product_id="SP-3101",
        name="ChefPro Stand Mixer 5qt",
        category="kitchen",
        subcategory="mixer",
        brand="ChefPro",
        price=299,
        rating=4.7,
        review_count=1820,
        description="5-quart stand mixer with 10-speed control and pouring shield.",
        specs={"capacity_qt": 5, "watts": 575},
        in_stock=True,
        stock_quantity=22,
        shipping_days=4,
    ),
    Product(
        product_id="SP-3102",
        name="ChefPro Hand Blender",
        category="kitchen",
        subcategory="blender",
        brand="ChefPro",
        price=69,
        rating=4.5,
        review_count=960,
        description="Immersion blender with whisk and chopper attachments.",
        specs={"watts": 300},
        in_stock=True,
        stock_quantity=60,
        shipping_days=3,
    ),
    Product(
        product_id="SP-3103",
        name="ChefPro 11-Cup Food Processor",
        category="kitchen",
        subcategory="food_processor",
        brand="ChefPro",
        price=129,
        rating=4.6,
        review_count=1340,
        description="11-cup food processor with dough blade and shredding disc.",
        specs={"capacity_cups": 11, "watts": 500},
        in_stock=True,
        stock_quantity=40,
        shipping_days=4,
    ),
]

PRODUCTS: list[Product] = TASK1_PRODUCTS + CHEFPRO_KITCHEN


PROMOTIONS: list[Promotion] = []


# ---------------------------------------------------------------------------
# Task JSON
# ---------------------------------------------------------------------------

TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — I'm redoing my kitchen and want to grab a few ChefPro appliances today: "
        "the Stand Mixer, the Hand Blender, and the 11-Cup Food Processor. Can you add all "
        "three to my cart?"
    ),
    "user_simulator": {
        "personality": "Enthusiastic about the kitchen remodel. Knows what they want. Not price-sensitive. Expects the agent to handle any applicable discounts without being asked.",
        "user_sim_context": (
            "You are a returning Platinum-tier shopper redoing your kitchen. You want three "
            "specific ChefPro appliances in one cart. You trust the agent to surface any "
            "applicable promotions or bonuses. You have no independent knowledge of the store's "
            "brand_bundle or category_bundle policies."
        ),
        "known_info": [
            "You want exactly three items: ChefPro Stand Mixer, ChefPro Hand Blender, ChefPro 11-Cup Food Processor.",
            "One of each, no gift wrap.",
            "You are a returning Platinum-tier customer.",
        ],
        "unknown_info": [
            "Any bundle bonuses (brand, category, or otherwise).",
            "Exact prices.",
            "Store policies on bundles and stacking.",
        ],
        "task_rules": [
            "You do NOT know the store has a brand bundle, a category bundle, or any other policy-driven bonus. You will NOT bring up discounts, promos, or bundles on your own.",
            "If the agent asks clarifying questions about use case, answer briefly.",
            "You will decline gift wrap if asked.",
            "If the agent proactively mentions any bundle bonus (brand OR category) and quotes an amount, acknowledge it briefly and continue.",
            "If the agent summarizes the cart without mentioning any bundle bonus, do NOT volunteer that you know any exist (you don't). Accept the total as quoted.",
            "You will not ask about loyalty points, gift wrap fees, or welcome discounts.",
            "When all three items are in the cart and the agent has given a cart summary, end your next message with [TASK_DONE].",
        ],
    },
    "task_summary": (
        "**Task:** A returning Platinum customer (shop_001) wants to add three ChefPro kitchen "
        "appliances to their cart: Stand Mixer (SP-3101, $299), Hand Blender (SP-3102, $69), "
        "11-Cup Food Processor (SP-3103, $129). Subtotal $497. The customer does NOT ask about "
        "discounts.\n\n"
        "**Challenge:** Three same-brand AND same-category items trigger BOTH the `brand_bundle` "
        "(3% off same-brand, 2+ items) AND `category_bundle` (5% off same-category, 3+ items) "
        "policies. Per policy, brand_bundle stacks with category_bundle (and with promo codes, "
        "though no promo is in this env). Combined savings: $15 + $25 = $40 on qualifying items "
        "(~8%). Both bonuses are informational-only — the cart engine does NOT auto-apply them. "
        "The pitfall is silent completion: the agent adds the items, summarizes $497, and never "
        "mentions either bonus. v0.1 agents failed this task 0/3, typically mentioning one "
        "bonus and missing the other, or mentioning neither. The correct behavior is to "
        "proactively surface BOTH bonuses with quantified amounts (percent or dollar) at cart "
        "summary, before the customer ends the conversation."
    ),
    "task_requirements": [
        {
            "id": "all_three_items_added",
            "kind": "must",
            "requirement": "Agent added exactly SP-3101, SP-3102, and SP-3103 to the cart, each with quantity 1 and no gift wrap.",
            "evidence": "tool_calls",
        },
        {
            "id": "surfaced_brand_bundle",
            "kind": "must",
            "requirement": "Agent proactively told the customer about the brand_bundle bonus — citing that 2+ same-brand items qualify for a 3% bonus, with a quantified amount (percent or dollar). Must be surfaced BEFORE the customer ends the conversation. The customer did NOT ask about discounts; disclosure must be agent-initiated.",
            "evidence": "conversation",
        },
        {
            "id": "surfaced_category_bundle",
            "kind": "must",
            "requirement": "Agent proactively told the customer about the category_bundle bonus — citing that 3+ same-category items qualify for a 5% bundle, with a quantified amount (percent or dollar). Must be surfaced BEFORE the customer ends the conversation. The customer did NOT ask about discounts; disclosure must be agent-initiated.",
            "evidence": "conversation",
        },
        {
            "id": "no_silent_completion",
            "kind": "must_not",
            "requirement": "Agent must NOT present a final cart summary that omits either bundle bonus. A summary that lists only subtotal and total without any bundle disclosure fails this requirement even if the agent later brings up one of the bundles in response to a customer prompt.",
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
                "product_id": "SP-3101",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0002",
                "customer_id": USER_ID,
                "product_id": "SP-3102",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0003",
                "customer_id": USER_ID,
                "product_id": "SP-3103",
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
            "field": "subtotal",
            "expected_value": 497,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 497,
        },
    ],
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

