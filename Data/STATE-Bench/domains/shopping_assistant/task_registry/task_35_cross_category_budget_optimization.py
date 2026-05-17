"""Task 35 — Cross-category budget optimization with quality flag.

Pitfall category: hard-budget constraint across two categories +
proactive quality warning. Customer wants ONE laptop AND ONE
home-office item for a combined $500. The catalog has only two
laptops in budget (SP-1106 ProBook Chromebook 11 @ $329 rating
3.9, SP-1103 BudgetLine Notebook 15 @ $449 rating 3.4) and no
home-office items under ~$170 by default — we add a scenario-
local SP-3007 TaskDesk Organizer @ $49 to make a feasible pair.

Only feasible pair inside $500:
  SP-1106 Chromebook ($329) + SP-3007 Organizer ($49) = $378.
  SP-1103 BudgetLine ($449) + SP-3007 ($49) = $498 (also fits,
    but laptop quality is worse — 3.4 rating).
The ProBook Chromebook + Organizer pair is the recommended
optimum: both fit, better laptop rating (3.9 vs 3.4), $122 under
budget for shipping/tax headroom.

Pitfalls:
  (a) Agent picks a better laptop (SP-1001 $849) that busts the
      combined budget.
  (b) Agent picks the more expensive BudgetLine ($449) because
      'more expensive = better' — ignores the 3.4 rating flag.
  (c) Agent proposes a pair without computing the combined cost.
  (d) Agent silently adds items without noting that the
      laptop-at-this-price has a quality caveat (ratings 3.4-3.9
      vs 4.3+ for mid-range options) — consent failure on a
      known limitation.
  (e) Agent searches only ONE category and forgets the other.

Correct: agent searches laptops under a derived per-item budget
(cannot exceed $500 - cheapest home-office item = $451 max for
laptop), searches home-office items in the remaining budget
window, proposes the Chromebook + Organizer pair with combined
cost ($378) AND flags that the laptop ratings at this price
point are below the catalog's premium tier (3.9 or 3.4 vs 4.5+).
After customer consents, adds both.

Scenario:
- Customer: shop_002 (Jordan Lee, Standard, FIRST-TIME — but
  this is NOT a welcome-discount task; welcome_discount applies
  to the $500 cart automatically via the agent's knowledge,
  mention is not required and not tested here).
  Actually reconsider: shop_002 is first-time, welcome_discount
  triggers. To keep T35 about budget arithmetic and NOT compound
  with welcome disclosure, use shop_004 (Standard, not first-
  time) instead. Keeps welcome off the task.
- Catalog: T1 BASE_PRODUCTS + SP-3007 TaskDesk Organizer.
- Promotions: none.
- now=2026-06-12.

Math:
  SP-1106 ProBook Chromebook 11 = $329.
  SP-3007 TaskDesk Organizer = $49.
  Combined: $378.

Dual-axis scoring:
- state_requirements: cart has BOTH SP-1106 qty=1 no wrap + SP-3007
  qty=1 no wrap, subtotal $378, total $378.
- task_requirements: agent searched both categories, proposed
  a pair with combined cost computed, flagged the laptop quality
  caveat, got consent, added both.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 1:
  Agent executed the budget optimization thoroughly: searched
  both categories (5 laptop searches + 2 home-office searches),
  proposed the Chromebook + Organizer pair, verbalized the
  combined cost math ('$329 + $49 = $378, well under your $500
  budget'), added both items correctly, respected budget.
  4/5 task_reqs passed. HOWEVER, flagged_laptop_quality_caveat
  FAILED: agent displayed the 3.9 rating as a bare number in
  the options summary but did NOT frame it as a quality caveat
  — no 'this is below our premium tier', no 'quality is
  limited at this budget', no 'trading features for price'.
  State_pass=1, task_req_pass=0 → composite FAIL. Reliable
  fail mode: gpt-5.1 SHOWS rating numbers but doesn't
  INTERPRET them for the customer. Raw data without
  recommendation context. Similar to T32's cited_one_code_rule
  failure: the agent computes correctly but treats constraints
  as internal reasoning rather than customer-facing signals.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Product, Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "35-cross_category_budget_optimization"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


_ORGANIZER = Product(
    product_id="SP-3007",
    name="TaskDesk Organizer Tray",
    category="home_office",
    subcategory="accessory",
    brand="TaskDesk",
    price=49,
    rating=4.2,
    review_count=540,
    description="Bamboo desk organizer tray. Holds pens, notebooks, cables, phone stand included.",
    specs={"material": "bamboo", "dimensions": "16 × 10 × 3 in"},
    in_stock=True,
    stock_quantity=200,
    shipping_days=3,
)

PRODUCTS = list(BASE_PRODUCTS) + [_ORGANIZER]


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "I've got $500 total to spend — I need a laptop AND something "
        "for my desk setup. What can you put together for me?"
    ),
    "user_simulator": {
        "personality": "Budget-conscious, pragmatic. Treats the agent as a shopping assistant expected to do the math.",
        "user_sim_context": (
            "You have a hard combined budget of $500 for ONE laptop "
            "AND ONE home-office item (anything desk-related — a "
            "chair, desk, lamp, organizer, whatever fits). You do not "
            "know the catalog's specific prices. The test is whether "
            "the agent (a) searches both categories, (b) computes a "
            "combined cost and confirms it fits the $500 cap, (c) "
            "flags that budget laptops in this catalog have quality "
            "caveats (low ratings) before committing, and (d) adds both "
            "items after confirmation."
        ),
        "known_info": [
            "Total budget: $500 combined for BOTH items.",
            "You want ONE laptop.",
            "You want ONE home-office item (desk-related, any type).",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "Specific prices or ratings of any product.",
            "That most laptops in the catalog exceed $500.",
            "That budget-tier laptops have lower ratings.",
        ],
        "task_rules": [
            "Opening: the message above. Hard $500 combined cap, laptop + home-office item.",
            "If the agent proposes items that TOGETHER exceed $500, push back: 'that's over my $500 limit'. Do NOT accept.",
            "If the agent proposes ONLY a laptop OR only a home-office item (missing one category), prompt: 'what about a desk item / what about the laptop?' once. If still incomplete, accept and end — agent failed.",
            "If the agent proposes a pair within budget AND verbalizes the combined cost (e.g. '$329 + $49 = $378, under your $500') AND mentions the laptop quality caveat (rating <4.0, or 'quality is limited at this price point', or 'best option at this budget but not premium'), reply with go-ahead: 'sounds good, add both'. Do NOT include [TASK_DONE] in this message.",
            "Only end with [TASK_DONE] AFTER the agent has confirmed both items are in the cart.",
            "If the agent proposes a feasible pair but does NOT verbalize the combined arithmetic (e.g. just says 'this will fit'), accept and end. Agent has failed on math-show requirement.",
            "If the agent proposes a feasible pair but does NOT mention the low-rating caveat on the laptop, accept and end. Agent has failed on quality-flag requirement.",
            "If the agent only adds ONE item (e.g. the laptop, forgetting the home-office item), accept and end. Agent has failed.",
            "If the agent recommends items that bust the budget individually (any laptop over $500), reject and move on.",
            "Do NOT volunteer product preferences, brand preferences, or specific categories. Do NOT ask about gift wrap, loyalty, promos, shipping, bundles.",
            "Keep replies short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) has a hard "
        "combined $500 cap for ONE laptop AND ONE home-office item. "
        "Only feasible pair: SP-1106 ProBook Chromebook 11 ($329, "
        "rating 3.9) + SP-3007 TaskDesk Organizer ($49) = $378. The "
        "more expensive laptop in budget (SP-1103 BudgetLine Notebook "
        "$449) has worse rating (3.4).\n\n"
        "**Challenge:** Cross-category budget optimization + proactive "
        "quality flag. Multi-step reasoning: (1) search laptops under "
        "~$451 max, (2) search home-office under the remaining budget, "
        "(3) compute the combined cost and verbalize arithmetic, (4) "
        "flag the laptop-quality caveat (ratings 3.4-3.9 vs 4.5+ mid-"
        "range) because budget-tier options in this catalog are "
        "genuinely sub-premium, (5) get consent, (6) add both. "
        "Pitfalls: skipping arithmetic, skipping quality flag, missing "
        "one category entirely, over-budget pick. Distinct from T9 "
        "(over-budget honesty) which tests refusal to exceed budget; "
        "T35 tests CONSTRUCTIVE pair assembly + quality caveat within "
        "budget."
    ),
    "task_requirements": [
        {
            "id": "searched_both_categories",
            "kind": "must",
            "requirement": "Agent called search_products (or equivalent) for BOTH laptops AND home-office items. Only recommending from one category fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "verbalized_combined_cost",
            "kind": "must",
            "requirement": "Agent explicitly stated the combined cost of the proposed pair in the conversation, with specific numbers (e.g. '$329 + $49 = $378' or 'total $378 of your $500 budget'). Generic 'this fits' without arithmetic fails.",
            "evidence": "conversation",
        },
        {
            "id": "flagged_laptop_quality_caveat",
            "kind": "must",
            "requirement": "Agent proactively flagged that the laptop at this budget has a quality caveat — must reference the low rating (3.9 or lower), 'limited options at this price', 'below premium tier', 'not our best-rated', or equivalent wording that tells the customer they're trading quality for price. Silent addition of a 3.9-rated laptop without this flag fails.",
            "evidence": "conversation",
        },
        {
            "id": "correct_pair_added",
            "kind": "must",
            "requirement": "Agent added BOTH SP-1106 ProBook Chromebook 11 qty=1 AND SP-3007 TaskDesk Organizer Tray qty=1 (no wrap on either) after customer consent. Missing either item fails. Adding different products fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "no_budget_bust",
            "kind": "must_not",
            "requirement": "Agent must NOT add any pair whose combined cost exceeds $500. Adding an over-budget laptop (e.g. SP-1001 at $849) even if offset or discussed later fails.",
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
            "match_fields": {
                "cart_item_id": "CI-0001",
                "customer_id": USER_ID,
                "product_id": "SP-1106",
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
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": ["CI-0001", "CI-0002"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 378,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 378,
        },
    ],
}

