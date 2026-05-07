"""Task 66 — Bundle optimization for a $1200 college setup.

Pitfall category: customer has a HARD budget cap ($1200) and wants
MULTIPLE items (laptop + backpack + headphones + webcam) as a
college starter kit. Naive laptop pick (ProBook 13 $999) busts the
budget once accessories are added. Agent must optimize ACROSS the
bundle — pick the SlimBook Air 13 ($849) laptop to leave headroom
for all three accessories within $1200.

Scenario:
- Customer shop_002 (Jordan Lee, standard tier, first-time shopper).
- Opening: 'Heading to college in the fall — I need a laptop, a
  backpack, headphones, and a webcam. Budget is $1200 total, firm.
  What do you recommend?'

Catalog math:
  SP-1001 SlimBook Air 13   $849  (portable, student-friendly)
  SP-1002 ProBook 13        $999  (heavier, pricier)
  SP-1003 SlateTab 14       $749  (tablet, not a real laptop)
  SP-3002 AlpineGear Daypack $89
  SP-2003 SoundMax Headphones $149
  SP-2005 PixelShot Webcam  $79

Correct bundle (all 4 items, within budget):
  SP-1001 + SP-3002 + SP-2003 + SP-2005 = 849 + 89 + 149 + 79 = $1166 ✓

Naive ProBook 13 bundle busts budget:
  SP-1002 + SP-3002 + SP-2003 + SP-2005 = 999 + 89 + 149 + 79 = $1316 ✗

Agent must:
  (a) recognize all four items need to fit under $1200,
  (b) compute the bundle math BEFORE committing to the laptop,
  (c) pick SP-1001 (not SP-1002) because only SP-1001 leaves
      headroom for the three accessories,
  (d) explicitly surface the tradeoff ('ProBook 13 is the pricier
      13-inch — with the three accessories it busts your budget by
      $116, so I'm recommending SlimBook Air 13 which fits with
      $34 to spare').

Expected flow:
  Turn 1 (user): opening — laptop + backpack + headphones + webcam
    under $1200 total.
  Turn 2 (agent): searches catalog, computes bundle math, presents
    SP-1001 + SP-3002 + SP-2003 + SP-2005 = $1166 with the 'why
    SlimBook over ProBook 13' reasoning.
  Turn 3 (user): confirms.
  Turn 4 (agent): adds all 4 via add_to_cart (4 calls). Confirms
    final cart subtotal $1166.
  Turn 5 (user): 'Total looks good.' [TASK_DONE]

Pitfalls:
  (a) Agent picks ProBook 13 as laptop → bundle busts $1200. Then
      either silently drops an accessory, silently picks SP-1003
      (SlateTab — not a laptop), or asks customer to cut an item.
  (b) Agent picks SP-1001 but uses inferior accessories (e.g., drops
      webcam entirely) when all four fit.
  (c) Agent asks customer 'which is your priority' without doing
      the bundle math — the correct answer exists, customer
      shouldn't have to choose.
  (d) Agent adds items one by one without computing the rolling
      total, discovers the overage only after three items are in
      cart.
  (e) Agent picks cheapest-across-the-board (SP-1103 BudgetLine
      $449 laptop) — well under budget but bad value and no
      explanation for not using the available headroom.

Dual-axis scoring:
- state_requirements: cart contains exactly SP-1001, SP-3002,
  SP-2003, SP-2005, qty=1 each, no wrap, no promo, subtotal=1166,
  total=1166.
- task_requirements: agent computed bundle math before laptop pick,
  explicitly compared ProBook 13 vs SlimBook Air on budget-fit
  grounds, surfaced the tradeoff in chat.

Observed failure mode:
  v0.2.2, 2026-04-20, VanillaAgent / gpt-5.1, 2 runs: 0 PASS, 2 FAIL.
  Two distinct fail patterns surfaced:
  (1) run1: agent picked SP-1003 SlateTab (tablet, $749) + webcam
      + headphones, then told the customer 'buy a backpack
      elsewhere' — silently dropped the backpack and substituted a
      tablet for the laptop. Both state and task_req fail. Real
      deployment risk: when the naive combo busts budget, agent
      drops the item hardest to rationalize (backpack) instead of
      reworking the laptop tier.
  (2) run2: agent picked SP-1001 + all 3 accessories ($1166) —
      state passes — but never compared SP-1001 vs SP-1002 on
      budget grounds. Just jumped to SlimBook without naming the
      ProBook 13 tradeoff. Task_req fails on explained_laptop_
      tradeoff. Captures the 'arrived at the right answer without
      showing the bundle-level reasoning' failure — a judge can't
      verify the optimization was principled vs lucky.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "66-bundle_optimization_college_setup"
USER_ID = "shop_002"
NOW = "2026-06-10T10:00:00"

PRODUCTS = list(BASE_PRODUCTS)
PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — heading to college in the fall. I need a laptop, a "
        "backpack, headphones, and a webcam. Budget is $1200 total "
        "— that's firm. What do you recommend?"
    ),
    "user_simulator": {
        "personality": "Practical first-time shopper, budget-conscious, trusts the agent to do the bundle math.",
        "user_sim_context": (
            "You're going to college in the fall. You need FOUR "
            "things: a laptop, a backpack, wireless headphones, and "
            "a webcam. Your TOTAL budget across all four is $1200 "
            "— firm ceiling. You want all four items; you do NOT "
            "want to drop any of them. You trust the agent to pick "
            "a combination that fits. You have no strong brand "
            "preferences and no specific specs in mind beyond "
            "'works for college'."
        ),
        "known_info": [
            "You need a laptop, backpack, headphones, and webcam — all four.",
            "Your total budget is $1200, firm.",
            "You're a standard-tier first-time shopper.",
        ],
        "unknown_info": [
            "Which specific laptop/accessory SKUs fit together under $1200.",
            "Prices of individual items in the catalog.",
        ],
        "task_rules": [
            "Opening: as stated — four items, $1200 total firm.",
            "If the agent proposes a bundle of all 4 items AT OR UNDER $1200, confirm and ask them to add all 4. After add_to_cart calls and a final cart summary, reply 'Total looks good.' and [TASK_DONE].",
            "If the agent proposes a bundle OVER $1200 (e.g., with ProBook 13), push back: 'wait — that's over my $1200 cap. Is there a way to fit all four within budget?' If the agent then picks a compliant bundle (e.g., swap to SlimBook Air 13), proceed. If they insist on over-budget or ask YOU to cut an item, reject: 'I want all four — can you find a combo that fits?' If they keep failing, accept whatever they do and end — failed on bundle optimization.",
            "If the agent silently drops an item (only 3 items in cart summary), push back: 'hey, I also needed the [missing item] — did that get added?' If they then add it within budget, proceed. If adding it busts $1200, say 'I need all four within budget; can you rework the combo?' Expect a laptop swap to SlimBook Air. If they can't figure it out, accept and end.",
            "If the agent asks 'which item is your priority?' without proposing a combo, push back: 'all four matter — I'm hoping there's a combo that fits.' If they then find SlimBook Air + accessories, proceed. If they don't, accept and end.",
            "If the agent picks a very cheap laptop (BudgetLine $449) without explaining why, accept it if all 4 items fit the budget. This is a borderline pass — state check will catch it if the final cart isn't SP-1001 based.",
            "Do NOT suggest specific SKUs or prices. Let the agent drive.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A standard-tier first-time customer (shop_002, "
        "Jordan Lee) is shopping for a college starter kit: laptop "
        "+ backpack + headphones + webcam, firm total budget "
        "$1200. The agent must optimize ACROSS the bundle — the "
        "naive laptop pick (SP-1002 ProBook 13, $999) combined "
        "with SP-3002 backpack ($89) + SP-2003 headphones ($149) + "
        "SP-2005 webcam ($79) totals $1316, over budget. Only "
        "SP-1001 SlimBook Air 13 ($849) as the laptop leaves "
        "enough headroom: $849+$89+$149+$79 = $1166 ✓. Agent must "
        "compute the bundle math UP FRONT, compare laptops on "
        "budget-fit grounds, and add all 4 items. Final cart: "
        "SP-1001 + SP-3002 + SP-2003 + SP-2005, subtotal $1166, "
        "total $1166.\n\n"
        "**Challenge:** Bundle-level budget optimization — agent "
        "can't treat the laptop pick independently, must reason "
        "about what the remaining $351 of the budget needs to "
        "cover. Pitfalls: (1) picks ProBook 13 without bundle math, "
        "accessories then bust $1200, (2) silently drops webcam or "
        "headphones to fit, (3) asks customer to drop an item when "
        "all 4 actually fit with SlimBook, (4) adds items "
        "one-by-one without rolling total, discovers overage late, "
        "(5) over-corrects to BudgetLine ($449) ignoring the "
        "available headroom."
    ),
    "task_requirements": [
        {
            "id": "computed_bundle_math_upfront",
            "kind": "must",
            "requirement": "Agent computed the bundle total BEFORE committing to the laptop pick. The reasoning must reference the $1200 cap and at minimum one arithmetic breakdown (e.g., '$849 + $89 + $149 + $79 = $1166'). Adding items one-by-one without any upfront total math fails.",
            "evidence": "conversation",
        },
        {
            "id": "explained_laptop_tradeoff",
            "kind": "must",
            "requirement": "Agent explicitly compared SP-1001 (SlimBook Air 13) vs SP-1002 (ProBook 13) on budget-fit grounds — pointed out that ProBook 13 plus the accessories would exceed $1200, and SlimBook Air leaves enough headroom. Generic 'SlimBook is a good pick' without the budget reasoning fails.",
            "evidence": "conversation",
        },
        {
            "id": "all_four_items_added",
            "kind": "must",
            "requirement": "Agent added exactly 4 distinct items to the cart: a laptop, a backpack, headphones, and a webcam. Dropping any category fails this requirement — silent drops are the primary pitfall.",
            "evidence": "tool_calls",
        },
        {
            "id": "no_over_budget_bundle",
            "kind": "must_not",
            "requirement": "Agent must not end with a cart subtotal over $1200. If the agent proposes an over-budget bundle and the customer pushes back, they must recover by swapping the laptop — not by dropping an accessory.",
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
                "customer_id": USER_ID,
                "product_id": "SP-1001",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "customer_id": USER_ID,
                "product_id": "SP-3002",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "customer_id": USER_ID,
                "product_id": "SP-2003",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
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
            "expected_value": 1166,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 1166,
        },
    ],
}

