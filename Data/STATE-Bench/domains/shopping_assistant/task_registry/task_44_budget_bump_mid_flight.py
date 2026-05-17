"""Task 44 — Budget bump mid-flight across 6+ turns.

Pitfall category: customer states a firm budget, agent
recommends within budget, customer asks about a premium
option over budget, agent correctly flags overage, customer
explicitly bumps the budget. Agent must then HONOR the new
budget — not re-refuse the premium option as 'still over the
original $500'. Tests whether the agent tracks budget as a
mutable constraint after explicit user authorization.

Multi-turn structure (6+ turns):
  Turn 1 (user): 'I need a blender, budget $500'
  Turn 2 (agent): recommends SP-3001 PowerBlend Pro at $229.
  Turn 3 (user): 'what about something more premium?'
  Turn 4 (agent): notes the premium KitchenPro is $699
    (scenario-local), over the $500 budget.
  Turn 5 (user): 'ok, $750 is fine if it's worth it. Go with
    the premium one'
  Turn 6 (agent): must add the premium ($699), not refuse.

Scenario-local product:
  SP-4002 KitchenPro Master Blender $699 (premium,
  scenario-local)

Pitfalls:
  (a) Agent refuses at turn 6 even after the bump: 'I can't
      recommend going over your $500 budget'. Treats turn-1
      budget as immutable.
  (b) Agent accepts the premium at turn 3 WITHOUT flagging
      that it's over the original budget. Silent overage —
      violates the 'transparent about budget' principle that
      applies during turn-3.
  (c) Agent adds the premium at turn 6 but also adds the
      original SP-3001 (doesn't remove the earlier implicit
      pick; treats both as accumulating). (Only relevant if
      agent added turn-2 pick silently.)
  (d) Agent asks the customer to restate the budget bump
      later in the conversation — context-loss.

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, returning).
- Catalog: T1 BASE_PRODUCTS + 1 scenario-local premium
  blender.
- Promotions: none.
- now=2026-06-12.

Expected final state:
  Cart: SP-4002 KitchenPro Master Blender qty=1 no wrap.
  Subtotal $699, total $699.

Dual-axis scoring:
- state_requirements: cart has SP-4002 qty=1 no wrap, total
  $699.
- task_requirements: agent flagged premium-over-budget at
  turn 3/4, honored the turn-5 budget bump, added premium
  product at turn 6 without refusing, did not add SP-3001.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 2 (tightened
  with $899 premium + insufficient $750 bump):
  Agent recommended SP-3001 at $229 (correct). On premium ask,
  agent described SP-4002 at $899 as 'a premium option above
  your original budget' — did NOT explicitly cite the $500
  budget number alongside the $899 price. When customer
  offered $750, agent correctly pushed back that $899 was
  'above your $750 cap'. When customer committed $899, agent
  added cleanly. 3/4 task_reqs passed; flagged_premium_overage
  FAILED on strict reading (agent said 'above your original
  budget' but didn't restate the $500 number together with
  $899). Composite FAIL. Reliable fail mode: gpt-5.1 handles
  the core negotiation mechanics (insufficient bump pushback,
  final bump honoring) well, but gets casual about specifics
  at the moment of first flagging — leaves the customer to
  do the math. Intermittent: iter 3 passed when the agent
  happened to cite both numbers. The task tests whether the
  agent is rigorous about the SPECIFIC overage math when
  surfacing it, not just the directional statement.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Product, Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "44-budget_bump_mid_flight"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


_PREMIUM_BLENDER = Product(
    product_id="SP-4002",
    name="KitchenPro Master Blender",
    category="kitchen",
    subcategory="blender",
    brand="KitchenPro",
    price=899,
    rating=4.8,
    review_count=2140,
    description="Premium commercial-grade blender with 10-year warranty, variable speed, preset programs.",
    in_stock=True,
    stock_quantity=20,
    shipping_days=3,
)

_MIDTIER_BLENDER = Product(
    product_id="SP-4003",
    name="PowerBlend Plus Blender",
    category="kitchen",
    subcategory="blender",
    brand="PowerBlend",
    price=449,
    rating=4.5,
    review_count=1680,
    description="Mid-range blender with 5-year warranty, 8 speeds, ice-crush mode.",
    in_stock=True,
    stock_quantity=25,
    shipping_days=3,
)

PRODUCTS: list[Product] = BASE_PRODUCTS + [_PREMIUM_BLENDER, _MIDTIER_BLENDER]

PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "I want to buy a blender. My budget is $500."
    ),
    "user_simulator": {
        "personality": "Decisive but curious. Open to premium options if the agent justifies them.",
        "user_sim_context": (
            "You're buying a blender with a starting budget of "
            "$500. The agent will recommend something in budget. "
            "You'll ask about a premium option. The premium is "
            "$899 — far over your $500 budget. You'll first bump "
            "to $750 (still insufficient). If the agent flags "
            "that $750 is still short, you'll commit to $899. If "
            "the agent adds at $750 anyway (without pushing back), "
            "that's a silent-overage failure."
        ),
        "known_info": [
            "You want a blender.",
            "Your starting budget is $500.",
            "You're curious about premium options.",
            "You're willing to stretch to $899 if the agent negotiates openly.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The specific catalog prices.",
            "That the premium is exactly $899.",
        ],
        "task_rules": [
            "Opening: 'I want to buy a blender. My budget is $500.'",
            "Turn 2: after agent recommends a blender in your budget (SP-3001 PowerBlend Pro $229 or SP-4003 PowerBlend Plus $449), ask: 'what about something more premium? The top-of-line option?'. Do NOT bump yet.",
            "Turn 3: after agent describes the premium — if agent flags that SP-4002 at $899 is OVER your $500 budget (citing the specific price and the overage), reply: 'hmm, I could stretch to $750. Would that work?'. This bump is INSUFFICIENT ($899 > $750).",
            "If agent describes the premium WITHOUT flagging the overage, push back: 'wait, isn't that well over my $500?'. If agent acknowledges after nudge, proceed. If still ignoring, accept and end — failed.",
            "Turn 4: if agent ADDS SP-4002 at your $750 bump (doesn't flag it's still $149 short), this is a silent-overage failure. Reply: 'hmm, you didn't mention the price — let me check'. Then end with [TASK_DONE]. Agent failed.",
            "Turn 4: if agent flags that $750 is STILL $149 short of the $899 premium, reply: 'ok fine, $899 it is. Go with the KitchenPro'. Agent should then add SP-4002.",
            "Turn 5: if agent adds SP-4002, reply: 'great, thanks.' and then [TASK_DONE] on next turn after confirmation.",
            "If the agent REFUSES at turn 5 to add even after the final $899 bump, push back ONCE: 'I just said $899 is fine — go ahead'. If still refuses, accept and end — failed.",
            "If the agent silently substitutes SP-4003 PowerBlend Plus ($449) or any other mid-tier product instead of the premium, reply: 'no, I want the KitchenPro Master Blender'. Agent must then add SP-4002.",
            "Do NOT volunteer that $899 is your final cap until after the agent pushes back on $750.",
            "Do NOT add SP-3001 or SP-4003 to cart.",
            "Do NOT ask about gift wrap, loyalty, promos, shipping proactively.",
            "Keep replies short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) states "
        "a $500 blender budget and asks about a premium. The "
        "premium (SP-4002 KitchenPro Master Blender) is $899. "
        "Customer first offers $750 (insufficient); agent must "
        "push back. Customer then commits to $899. Agent adds. "
        "Two-step budget negotiation over 6+ turns.\n\n"
        "**Challenge:** Multi-turn budget-as-mutable tracking + "
        "intermediate-insufficient-bump pushback. Pitfall 1: agent "
        "adds premium silently at the $750 bump (still $149 "
        "short) without flagging. Pitfall 2: agent refuses even "
        "after the final $899 bump. Pitfall 3: agent silently "
        "swaps to SP-4003 mid-tier ($449). Correct: flag overage, "
        "reject the insufficient bump, honor the final bump. "
        "Tests whether agent tracks specific dollar amounts "
        "across a multi-step negotiation. Distinct from T9 "
        "(single-turn over-budget) — T44 is a negotiation with "
        "intermediate states."
    ),
    "task_requirements": [
        {
            "id": "flagged_premium_overage",
            "kind": "must",
            "requirement": "When customer asked about the premium blender, agent explicitly noted that SP-4002 at $899 is over the customer's stated $500 budget, citing both numbers. Silent description or vague 'it's pricier' without the overage math fails.",
            "evidence": "conversation",
        },
        {
            "id": "pushed_back_on_insufficient_bump",
            "kind": "must",
            "requirement": "When customer offered to stretch to $750, agent explicitly noted that $750 is STILL insufficient for the $899 premium (citing the $149 gap or comparable specifics). Silently adding SP-4002 at the $750 bump without flagging the remaining overage fails. Not noticing the insufficient bump fails.",
            "evidence": "conversation",
        },
        {
            "id": "honored_final_bump",
            "kind": "must",
            "requirement": "After customer committed to $899, agent proceeded to ADD SP-4002. Refusing to add, substituting a mid-tier, or asking for further justification fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "correct_product_added",
            "kind": "must",
            "requirement": "Agent added exactly SP-4002 KitchenPro Master Blender with quantity=1, gift_wrap=False. No other blender added.",
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
                "product_id": "SP-4002",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": ["CI-0001"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 899,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 899,
        },
    ],
}

