"""Task 42 — Build-a-setup: running total across 7+ turns.

Pitfall category: customer wants a home-office bundle within a
$1200 budget, revealed one item-need per turn. The agent must
maintain a RUNNING TOTAL in context across turns and warn
BEFORE any single item would push the cart over budget. If the
agent just adds items as asked without tracking cumulative
cost, the cart ends over budget — a silent overage.

Multi-turn structure (7+ turns):
  Turn 1 (user): 'help me set up a home office under $1200'
  Turn 2 (user after agent responds): 'I need a chair first'
  Turn 3 (user): 'now a desk'
  Turn 4 (user): 'and a monitor'
  Turn 5 (user): 'and headphones for calls'
  Turn 6 (user): 'wrap all of it'  (if agent doesn't flag over-budget)
  Turn 7 (user): final confirmation

Catalog (using scenario-local products for variety):
  - SP-3004 ErgoDesk Mesh Chair $329 (existing)
  - SP-3003 ErgoDesk Standing Desk $449 (existing)
  - SP-4001 ErgoDesk 27-inch Monitor $279 (scenario-local)
  - SP-2003 SoundMax Wireless Headphones $149 (existing)

Running math (cumulative, no wrap):
  After chair:                 $329
  After desk:                  $329+$449  = $778
  After monitor:               $778+$279  = $1057
  After headphones:            $1057+$149 = $1206  ← OVERAGE by $6
  With gift wrap on all 4:     $1206+$20  = $1226  ← additional overage

Correct trajectory: when the customer asks to add the FOURTH
item (headphones) at $149, the agent must recognize $1057+$149
= $1206 > $1200 and SURFACE it BEFORE adding, giving the
customer a choice: skip headphones, pick cheaper alternative,
or accept the overage.

Pitfalls:
  (a) Agent adds each item in isolation without tracking
      running total; realizes too late or never.
  (b) Agent tracks total mentally but forgets earlier items by
      turn 5 (context-loss signal).
  (c) Agent asks the customer to 're-confirm what you've
      added' at turn 5 — failure to retain state.
  (d) Agent adds headphones silently to $1206, then confirms
      'all set, your total is $1206' without flagging the
      overage.
  (e) Agent proposes gift wrap which adds $20 without
      surfacing the additional cost.

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, returning, 2.2k pts).
- Catalog: T1 BASE_PRODUCTS + 1 scenario-local monitor.
- Promotions: none.
- now=2026-06-12.

Correct outcome: customer accepts overage at turn ~5 OR
swaps headphones for something cheaper. Sim rule: if agent
surfaces the overage at or before adding headphones, customer
says 'ok skip the headphones'. Final cart: chair+desk+monitor,
subtotal $1057, total $1057.

Dual-axis scoring:
- state_requirements: cart has SP-3004, SP-3003, SP-4001
  (three items), no headphones, subtotal $1057, total $1057,
  no wrap.
- task_requirements: agent tracked running total across
  turns, warned BEFORE adding headphones would overshoot,
  added exactly the 3 items under budget.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 2:
  Agent added chair ($329), failed to find desk via search
  (over-restrictive filter), the sim said 'just assume $180
  and move on', agent proceeded to monitor ($279, found
  SP-4001), ran total as $329+$180(phantom)+$279=$788,
  remaining $412. Added headphones $149 silently, claiming
  new total $937 / remaining $263. BUT the ACTUAL cart was
  $329+$279+$149=$757 and the actual desk would have been
  $449, making the real total $1206 (over by $6). Agent's
  running total was based on a phantom assumption, not on
  actual committed-to-cart costs. State_diff: 3 items but
  wrong set (chair+monitor+headphones instead of
  chair+desk+monitor). All 4 task_reqs failed. Reliable fail
  mode: gpt-5.1's running-total tracking is brittle when any
  item in the sequence is not actually purchased — it keeps
  tracking against an imagined plan rather than the real
  cart state. Iter 3 passed after sim was tightened to force
  desk add from this store. The core pitfall — running-total
  math breaking down across turns — is reproducible but
  requires all items to be actually addable.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Product, Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "42-build_a_setup_running_total"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


# Scenario-local monitor product so the 4-item accumulation math lands.
_MONITOR = Product(
    product_id="SP-4001",
    name="ErgoDesk 27-inch Monitor",
    category="home_office",
    subcategory="monitor",
    brand="ErgoDesk",
    price=279,
    rating=4.4,
    review_count=720,
    description="27-inch QHD monitor with adjustable stand. USB-C and HDMI inputs.",
    in_stock=True,
    stock_quantity=30,
    shipping_days=4,
)

PRODUCTS: list[Product] = BASE_PRODUCTS + [_MONITOR]

PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "I want to set up a home office. My total budget is $1200, "
        "and I'll tell you what I need piece by piece."
    ),
    "user_simulator": {
        "personality": "Organized but doesn't track math on their own. Reveals item needs one per turn. Trusts the agent to flag budget issues proactively.",
        "user_sim_context": (
            "You are setting up a home office. Your total budget across "
            "EVERYTHING is $1200. You will reveal item needs ONE PER "
            "TURN in this order: (1) chair, (2) desk, (3) monitor, "
            "(4) headphones for calls. You are NOT tracking the running "
            "cost yourself — you expect the agent to warn you BEFORE "
            "any item pushes the total over $1200. The trap: the first "
            "three items sum to $1057, and headphones at $149 would "
            "push to $1206 ($6 overage). If the agent warns before "
            "adding headphones, you'll skip them."
        ),
        "known_info": [
            "Your total budget is $1200.",
            "You want chair, desk, monitor, headphones in that order (one per turn).",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The specific prices of each item.",
            "The running total after each add.",
            "That headphones will push you over budget.",
        ],
        "task_rules": [
            "Opening: state the $1200 total budget and 'piece by piece' framing.",
            "All items must be bought from THIS store. If the agent says it can't find something, push back: 'please look again, I'd like everything from one place'. Do NOT let the agent skip items or tell you to buy elsewhere.",
            "Turn 2: reveal item 1 — 'let's start with a chair'. No specific brand or price.",
            "Turn 3: reveal item 2 — 'now I need a desk. Nothing fancy, just a basic standing or fixed-height desk, whatever ErgoDesk has'. The agent should find SP-3003 ErgoDesk Standing Desk $449.",
            "If the agent's desk recommendation is NOT SP-3003 (e.g. agent says 'no desk in catalog'), reply: 'I think ErgoDesk has a standing desk — can you search by brand?'. Do not proceed to monitor until agent adds SP-3003.",
            "Turn 4: reveal item 3 — 'now a 27-inch monitor'. Agent should find SP-4001.",
            "Turn 5: reveal item 4 — 'and headphones for calls'. This is the trap — agent must now realize adding any headphone at $149 would overshoot the $1200 budget (chair $329 + desk $449 + monitor $279 = $1057; +$149 = $1206).",
            "If the agent proactively flags the overage BEFORE adding headphones (e.g. 'heads up — you're at $1057; headphones at $149 would put you at $1206, $6 over your $1200 budget') AND offers a choice (skip / cheaper alt / accept overage), reply: 'ok skip the headphones, three items is fine'. Do NOT include [TASK_DONE] here — wait for agent to confirm final state.",
            "Once the agent confirms the final cart (3 items, $1057), reply: 'thanks, that works. [TASK_DONE]'.",
            "If the agent adds headphones at turn 5 WITHOUT flagging the overage, accept the add and reply 'thanks' at the next turn, then end with [TASK_DONE]. Agent has failed — silent over-budget add.",
            "If the agent asks 'what did we add so far?' or 'can you remind me what's in your cart?' at any point, that's a context-loss signal — just repeat the list but this counts against them.",
            "If the agent quotes a running total incorrectly at any turn (e.g. says $800 when it's actually $1057), do not correct — let them proceed. Incorrect math = failure.",
            "If the agent adds gift wrap without asking, push back: 'I didn't ask for gift wrap, please remove it'.",
            "Do NOT volunteer the running total yourself. Do NOT ask about promos, loyalty, shipping proactively.",
            "Keep replies short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) wants to "
        "build a home-office setup within a $1200 total budget, "
        "revealing one item need per turn: chair ($329) → desk "
        "($449) → monitor ($279) → headphones ($149). The first "
        "three items sum to $1057; adding $149 headphones would push "
        "to $1206 ($6 overage). Agent must maintain a running total "
        "across turns and warn BEFORE adding the headphones.\n\n"
        "**Challenge:** Multi-turn cumulative-cost tracking. Pitfall: "
        "agent adds each item on its own without tracking the "
        "running total, and ends with a $1206 cart silently over "
        "budget. Or agent tracks but forgets by turn 5 and asks "
        "customer to re-list. Correct: track cumulative after each "
        "add, warn at turn 5 BEFORE adding headphones, let customer "
        "choose. Tests state retention over 5+ turns + proactive "
        "budget math. Distinct from T9 (single-item over-budget) — "
        "T42 is multi-item accumulation where no single item is "
        "over budget but the sum is."
    ),
    "task_requirements": [
        {
            "id": "tracked_running_total",
            "kind": "must",
            "requirement": "Agent explicitly stated or implied a running total after at least 2 of the first 3 adds (e.g. 'you're at $778 with chair+desk' or 'running total: $1057'). Silent adds with no cumulative-cost commentary fail. Asking the customer to repeat what's in the cart fails.",
            "evidence": "conversation",
        },
        {
            "id": "flagged_budget_overage_before_headphones",
            "kind": "must",
            "requirement": "BEFORE adding any headphone to the cart, agent explicitly warned that adding $149 headphones would push the total over the $1200 budget (cited the running total, the headphone price, and the overage). Adding headphones silently and flagging after fails. Adding without flagging at all fails.",
            "evidence": "conversation",
        },
        {
            "id": "headphones_not_added",
            "kind": "must",
            "requirement": "No headphone (SP-2003 or any other headphone) was added to the cart, because the customer chose to skip after the overage warning.",
            "evidence": "tool_calls",
        },
        {
            "id": "correct_three_items_added",
            "kind": "must",
            "requirement": "Agent added exactly these 3 items: SP-3004 ErgoDesk Mesh Chair, SP-3003 ErgoDesk Standing Desk, SP-4001 ErgoDesk 27-inch Monitor. Each qty=1, gift_wrap=False. Final cart subtotal $1057.",
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
                "product_id": "SP-3004",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0002",
                "customer_id": USER_ID,
                "product_id": "SP-3003",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "cart_items",
            "match_fields": {
                "cart_item_id": "CI-0003",
                "customer_id": USER_ID,
                "product_id": "SP-4001",
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
            "expected_value": 1057,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 1057,
        },
    ],
}

