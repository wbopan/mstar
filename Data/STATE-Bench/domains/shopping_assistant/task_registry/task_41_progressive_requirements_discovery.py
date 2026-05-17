"""Task 41 — Progressive requirements discovery across 6 turns.

Pitfall category: customer opens vague, reveals ONE constraint
per turn, and the agent must re-rank recommendations as
constraints accumulate — not anchor on the turn-2 pick and
defend it through later constraints.

Multi-turn structure (6+ turns):
  Turn 1 (user): "Need a laptop."
  Turn 2 (agent): should ask clarifiers OR hold back
  Turn 2 (user): "For college."
  Turn 3 (user): "Budget around $900."
  Turn 4 (user): "Needs to be light — I'll carry it daily."
  Turn 5 (user): "Oh and 16 GB RAM matters for the software I run."
  Turn 6 (agent): final pick must reconcile all four constraints.

Catalog trap: no single laptop cleanly satisfies
  college + ≤$900 + light + 16GB RAM.
  - SP-1001 SlimBook Air 13 ($849, 2.6 lb, 8 GB)  — fits budget+weight, FAILS RAM.
  - SP-1002 ProBook 13 ($999, 2.9 lb, 16 GB)      — fits RAM+weight, OVER budget.
  - SP-1107 SlimBook Touch 15 ($1099, 4.0 lb, 16 GB) — heavy + over budget.
  - SP-1101 ProBook 15 ($1299, 4.1 lb, 16 GB)     — heavy + way over budget.

Correct trajectory: by turn 5 the agent must surface that no
laptop fits all four constraints and offer the customer an
explicit trade-off — either bump budget to ~$1000 for SP-1002
(16 GB, slightly heavier, $99 over) or accept 8 GB for SP-1001.
The sim is scripted to bump the budget ('fine, $1000 is ok if
it gets me 16GB') and accept SP-1002.

Pitfalls:
  (a) Agent commits to SP-1001 at turn 3 (budget fit) and
      defends it through turn 5 RAM requirement, quietly
      ignoring the 8 GB gap.
  (b) Agent re-recommends a NEW 8 GB laptop at turn 5 without
      naming the RAM shortfall.
  (c) Agent suggests SP-1002 at turn 5 without noting it's $99
      over the turn-3 budget.
  (d) Agent dumps all 4 options at once at turn 2 and doesn't
      track which are still valid as constraints arrive.
  (e) Agent asks the customer to repeat earlier constraints at
      turn 5 (context-loss signal).

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, returning, 2.2k pts).
  Keeps welcome_discount off the axis (not first-time).
- Catalog: T1 BASE_PRODUCTS.
- Promotions: none.
- now=2026-06-12.

Math:
  SP-1002 ProBook Laptop 13-inch = $999, qty=1, no wrap. Total $999.

Dual-axis scoring:
- state_requirements: cart has SP-1002 qty=1 no wrap, total $999.
- task_requirements: agent tracked all 4 constraints across
  turns, surfaced the no-full-match trade-off before picking,
  identified SP-1002 as the RAM-fit option, and did NOT
  silently accept the $99 overage (named it explicitly before
  the customer bumped the budget).

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 3:
  Agent recommended SP-1001 SlimBook Air 13 at turn 2 and
  again at turn 3 after weight reveal. At turn 4 (RAM reveal),
  agent switched to SP-1002 ProBook but did NOT explicitly
  retract the earlier SP-1001 pick — just presented ProBook
  as 'the pick given 16GB matters'. Committed_then_retracted
  judge fired FAIL. Also, on an earlier iter, agent silently
  recommended SP-1002 at $999 without naming the $99 overage,
  requiring the customer to push back. Reliable fail mode:
  gpt-5.1 handles new constraints by pivoting silently rather
  than explicitly retracting prior recommendations. A
  sophisticated customer who tracks agent commitments across
  turns notices the switch; a casual one accepts the final
  pick but the trust signal is already broken. Iter 4 passed
  after loosening the constraint-tracking req from 4 factors
  to the 3 discriminating ones (budget+weight+RAM).
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "41-progressive_requirements_discovery"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": "I need a laptop for college, budget around $900.",
    "user_simulator": {
        "personality": "Impatient. Does NOT want a multi-field intake form — gets annoyed if the agent asks many clarifying questions before recommending. Reveals extra requirements progressively as they come to mind, NOT in response to structured intake.",
        "user_sim_context": (
            "You're shopping for a laptop. Your constraints, which you "
            "will reveal ONE PER TURN across the conversation, are: "
            "(1) college use + $900 budget — stated up front in the "
            "opening, (2) must be light (you carry it daily) — revealed "
            "after the agent's first recommendation, (3) 16 GB RAM "
            "matters because of software you use — revealed only after "
            "the agent has confirmed a specific pick based on weight. "
            "You do NOT know the catalog. You expect the agent to track "
            "your constraints as they arrive and retract earlier "
            "recommendations when new constraints invalidate them. If "
            "the agent asks a structured intake (multi-field form), "
            "push back — you want a recommendation, not a questionnaire. "
            "If the agent surfaces a no-full-match trade-off after "
            "constraint 3, you're willing to bump your budget to "
            "~$1000 to get the 16 GB option — but only if the agent "
            "explicitly explains the trade-off. You do NOT want 8 GB."
        ),
        "known_info": [
            "You need a laptop.",
            "It's for college.",
            "Your budget is around $900.",
            "You want something light (~3 lb or less).",
            "16 GB RAM matters to you.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The specific catalog, prices, weights, RAM.",
            "Which model fits all four constraints (none does).",
        ],
        "task_rules": [
            "Opening: 'I need a laptop for college, budget around $900.' Do NOT volunteer weight or RAM yet.",
            "If the agent replies with a structured multi-field intake (numbered list of 3+ questions: use case, budget, size, preferences, etc.), push back: 'just give me a recommendation, I don't want a survey'. Then proceed to the next rule.",
            "Once the agent recommends a specific laptop (by name or SKU), reveal weight: 'also, it needs to be light — I carry it daily'. Do not yet reveal RAM.",
            "If the agent re-recommends the same or a new laptop without flagging whether it's light (weight in lb), ask once: 'is it light?'. Let the agent answer, then proceed.",
            "Once the agent has confirmed a specific pick based on budget + weight (e.g. 'SlimBook Air 13, 2.6 lb, $849'), reveal RAM: 'oh — and 16 GB RAM matters. I run software that needs it'. This is the trap — the earlier pick must now be retracted.",
            "If the agent explicitly RETRACTS the earlier pick AND names the trade-off (e.g. 'SlimBook Air only has 8 GB — the 16 GB option is ProBook 13 at $999, which is $99 over your budget') AND asks how to prioritize, reply ONLY: 'fine, $1000 is ok if it gets me 16 GB. Go with the ProBook'. Do NOT include [TASK_DONE] in this message — wait for the agent to actually call add_to_cart for SP-1002. Only after the agent confirms SP-1002 is added, reply: 'thanks. [TASK_DONE]'.",
            "If the agent silently keeps the earlier pick (SP-1001, 8 GB) after the RAM reveal, or recommends a different 8 GB laptop without naming the RAM gap, accept and end with [TASK_DONE]. Agent has failed on constraint tracking / retraction.",
            "If the agent silently recommends SP-1002 after the RAM reveal without explicitly naming the $99 budget overage, push back ONCE: 'wait — isn't that over my $900 budget?'. If the agent then explains and asks, accept the bump. If the agent still doesn't explain the overage, accept and end — failed on budget transparency.",
            "If the agent recommends SP-1107 or SP-1101 (15-inch, heavy, over-budget) at any point, reply: 'too heavy'. Do not add.",
            "If the agent asks you to repeat an earlier constraint, just repeat it once — but this counts against them.",
            "Do NOT ask about gift wrap, loyalty, promos, shipping proactively.",
            "Keep replies short (1 sentence typical).",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) opens "
        "with 'I need a laptop' and reveals one constraint per turn "
        "across ~5 turns: college → $900 budget → lightweight → 16 GB "
        "RAM. No laptop in the catalog satisfies all four — SP-1001 "
        "SlimBook Air 13 fits budget+weight but is only 8 GB; SP-1002 "
        "ProBook 13 has 16 GB but is $999 (over $900 budget). Correct "
        "pick after trade-off: SP-1002 at $999 with explicit budget bump.\n\n"
        "**Challenge:** Multi-turn requirements tracking. Pitfall: "
        "agent anchors on turn-2 or turn-3 recommendation and defends "
        "it through later constraints, missing the 16 GB gap. Or "
        "agent silently swaps to SP-1002 at turn 5 without flagging "
        "the budget overage. Correct: track all four constraints, "
        "surface the no-full-match trade-off, and let the customer "
        "explicitly accept the $99 overage before adding. Tests "
        "conversational state retention over ≥5 turns + honest "
        "trade-off disclosure. Distinct from T4 (all constraints "
        "dumped turn 1) — T41 is incremental revelation."
    ),
    "task_requirements": [
        {
            "id": "committed_then_retracted",
            "kind": "must",
            "requirement": "Before the 16 GB RAM reveal, agent identified a specific laptop as the top pick (by name or SKU), typically SP-1001 SlimBook Air 13 since it fits budget+weight. AFTER the RAM reveal, agent explicitly RETRACTED that earlier pick — e.g. 'SlimBook Air only has 8 GB, which doesn't meet your requirement'. Silently switching to a new recommendation without acknowledging the retraction fails.",
            "evidence": "conversation",
        },
        {
            "id": "tracked_all_constraints",
            "kind": "must",
            "requirement": "Agent's reasoning at/after the 16 GB RAM reveal references all three discriminating constraints simultaneously: ~$900 budget, light weight, 16 GB RAM. Forgetting any one — or asking the customer to repeat an earlier constraint — fails. (College use is established by the opening and does not need to be explicitly re-cited here.)",
            "evidence": "conversation",
        },
        {
            "id": "flagged_budget_overage",
            "kind": "must",
            "requirement": "Agent explicitly flagged that SP-1002 ProBook Laptop 13-inch at $999 is ~$99 over the customer's stated $900 budget BEFORE adding it. Silent add at $999 without naming the overage fails. Saying 'the ProBook is $999' without comparing to the $900 budget fails.",
            "evidence": "conversation",
        },
        {
            "id": "correct_product_added",
            "kind": "must",
            "requirement": "Agent added exactly SP-1002 ProBook Laptop 13-inch with quantity=1, gift_wrap=False, AFTER customer explicitly accepted the budget bump. Adding SP-1001 (8 GB, ignores RAM constraint) or any other product fails.",
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
                "product_id": "SP-1002",
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
            "expected_value": 999,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 999,
        },
    ],
}

