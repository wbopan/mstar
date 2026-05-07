"""Task 68 — 3-brand comparison for traveling consultant persona.

Pitfall category: customer has a CLEAR persona — traveling
consultant — but describes it qualitatively ('I fly every week,
my current laptop's battery dies on me during 4-hour client
blocks, and it got cracked last quarter'). The persona implies
specific priorities: weight, battery life, durability.
CPU/RAM are NOT what should drive the pick. Agent must:
  (a) extract the 3 persona-relevant criteria,
  (b) build a focused side-by-side comparison on those criteria,
  (c) recommend ONE specific laptop with persona-matched
      reasoning,
  (d) NOT dump every spec in a wall-of-text,
  (e) NOT default to a RAM-first framing (spec-sheet default).

Candidate laptops and ACTUAL persona-relevant specs:
  SP-1002 ProBook 13         $999   2.9 lb  12hr battery  16GB RAM
  SP-1001 SlimBook Air 13    $849   2.6 lb  14hr battery   8GB RAM
  SP-1107 SlimBook Touch 15 $1099   4.0 lb   9hr battery  16GB RAM

Analysis (persona-weighted: weight + battery + durability):
  Weight: SlimBook Air (2.6) < ProBook 13 (2.9) < SlimBook Touch (4.0)
  Battery: SlimBook Air (14h) > ProBook 13 (12h) > SlimBook Touch (9h)

Correct pick: SP-1001 SlimBook Air 13. Reasoning:
  (i) 14hr battery is the LONGEST and easily covers a 4-hour
      client block with margin for flights,
  (ii) 2.6 lb is the LIGHTEST, ideal for weekly air travel,
  (iii) SlimBook Touch 15 is ruled out on BOTH axes (4.0 lb +
       9hr battery — worst for the persona),
  (iv) ProBook 13 has 16GB RAM (double the SlimBook Air) but the
       persona here is consulting (slides + spreadsheets), not
       video editing or dev — 8GB is sufficient. The agent
       SHOULD flag the RAM tradeoff so the customer can weigh
       it, but the right default for the stated persona is
       SlimBook Air.

Expected flow:
  Turn 1 (user): states the persona + 3-way choice.
  Turn 2 (agent): calls get_product_details / search_products,
    builds a persona-weighted comparison focused on weight,
    battery, durability. Recommends SlimBook Air 13 with
    specific numbers tied to the persona, flags 8GB RAM as the
    tradeoff but defends it given the use case.
  Turn 3 (user): 'Great, let's go with SlimBook Air.'
  Turn 4 (agent): add_to_cart SP-1001, confirms total $849.
  Turn 5 (user): 'Total looks good.' [TASK_DONE]

Pitfalls:
  (a) Agent dumps every spec for all 3 laptops in a wall-of-text
      (information overload — the whole point of hiring an agent
      is to do the synthesis).
  (b) Agent recommends ProBook 13 because '16GB is better' —
      missing that the persona is consulting (weight + battery
      dominate) and the 8GB tradeoff is acceptable.
  (c) Agent recommends SlimBook Touch 15 for bigger screen —
      missing BOTH weight AND battery constraints.
  (d) Agent fabricates a 'durability rating' that doesn't exist
      in the catalog.
  (e) Agent asks 'which matters most to you?' instead of
      reasoning from the persona — the persona already answered
      that.
  (f) Agent picks SlimBook Air but doesn't flag the 8GB RAM
      tradeoff at all — should surface it so customer can
      decide.

Dual-axis scoring:
- state_requirements: cart contains SP-1001 qty=1, no wrap,
  total $849.
- task_requirements: agent extracted persona criteria (weight,
  battery, durability), built a focused comparison on those
  criteria, recommended SlimBook Air with persona-tied reasoning,
  flagged the 8GB RAM tradeoff; did NOT dump a full spec-sheet
  for 3 laptops.

Observed failure mode:
  v0.2.2, 2026-04-20, VanillaAgent / gpt-5.1, 2 runs: 2 PASS, 0 FAIL.
  REGRESSION GUARD (not a fail-mode task). gpt-5.1 handled the
  persona-driven synthesis cleanly both runs: extracted weight /
  battery / durability from the narrative, recommended SlimBook
  Air 13 with specific numbers, did not dump a full spec sheet.
  Keeping as a regression guard — if a future model drifts
  toward spec-sheet defaults or away from persona-driven
  synthesis, this task will flip to fail.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "68-persona_driven_comparison_traveling_consultant"
USER_ID = "shop_001"
NOW = "2026-06-10T10:00:00"

PRODUCTS = list(BASE_PRODUCTS)
PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — I'm a consulting partner. I'm on a plane every "
        "week, my current laptop's battery dies halfway through "
        "a 4-hour client block, and I've already cracked one "
        "laptop this year. I'm looking at ProBook 13, SlimBook "
        "Air 13, or SlimBook Touch 15 — which should I pick?"
    ),
    "user_simulator": {
        "personality": "Busy consultant, wants a specific recommendation with reasoning tied to their use case — not a spec dump.",
        "user_sim_context": (
            "You are a consulting partner who flies every week, "
            "has experienced battery dying during 4-hour client "
            "blocks, and has cracked a laptop this year. You want "
            "the agent to PICK one of the three — ProBook 13, "
            "SlimBook Air 13, SlimBook Touch 15 — and explain "
            "WHY in terms of your persona. You do NOT want a "
            "spec-sheet dump. You do NOT want the agent to push "
            "the decision back to you ('which matters most?'). "
            "You trust the agent to synthesize based on what you "
            "told them. Your work is slides, spreadsheets, and "
            "video calls — NOT video editing or dev. Budget is "
            "not a concern up to ~$1500."
        ),
        "known_info": [
            "You fly weekly — weight matters for carrying through airports.",
            "Battery dies during 4-hour client blocks — you need more.",
            "You've cracked a laptop this year — durability matters.",
            "Your workload is slides, spreadsheets, calls — not video editing.",
            "Budget up to ~$1500.",
        ],
        "unknown_info": [
            "Specific weight, battery, or RAM numbers in the catalog.",
            "Which of the 3 candidates actually matches best.",
        ],
        "task_rules": [
            "Opening: as stated. Wait for the agent's recommendation.",
            "If the agent recommends SlimBook Air 13 with reasoning tied to your persona (longest battery covers 4hr blocks, lightest for weekly travel) AND names specific numbers (weight, battery hours), reply: 'Great, let's go with SlimBook Air.' After add_to_cart and a cart confirmation, reply 'Total looks good.' and [TASK_DONE].",
            "If the agent recommends ProBook 13 for its 16GB RAM, push back: 'does the RAM really matter for my use case? My work is slides, spreadsheets, and calls — is 16GB needed, or is the better battery and lighter weight a better tradeoff here?' If they pivot to SlimBook Air 13 for your persona, proceed. If they insist 16GB is needed, accept and end — failed on persona weighting.",
            "If the agent recommends SlimBook Touch 15, push back: 'isn't the Touch 15 the heaviest and does it have the worst battery? That sounds bad for my weekly travel and 4hr blocks.' If they pivot to SlimBook Air 13, proceed. If they insist on SlimBook Touch, accept and end — failed on constraint respect.",
            "If the agent dumps a full spec sheet for all 3 without a clear recommendation, push back: 'can you just pick one based on what I told you? I don't have time to read all that.' If they then recommend SlimBook Air 13, proceed. If they still don't synthesize, accept the eventual pick and end — failed on synthesis.",
            "If the agent asks 'which is more important to you — weight, battery, or durability?', push back: 'honestly all three matter for my job — I was hoping you could pick based on what I described.' If they then recommend SlimBook Air 13, proceed. If they keep deferring, accept and end.",
            "If the agent recommends SlimBook Air but does NOT mention that it has 8GB RAM (half of ProBook 13's 16GB) as a tradeoff, accept the recommendation but do not reveal you know. This is a secondary concern — state check passes; task_req flags the omission.",
            "Do NOT volunteer specific weight/battery/RAM numbers.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Platinum returning customer (shop_001, Alex "
        "Rivera) describes a traveling-consultant persona — "
        "weekly flights, current laptop's battery dies during "
        "4-hour client blocks, cracked a laptop this year — and "
        "asks the agent to pick between SP-1002 ProBook 13 (2.9 "
        "lb, 12hr, 16GB), SP-1001 SlimBook Air 13 (2.6 lb, 14hr, "
        "8GB), and SP-1107 SlimBook Touch 15 (4.0 lb, 9hr, "
        "16GB). Correct pick is SP-1001 SlimBook Air 13: "
        "LONGEST battery (14hr vs 12hr ProBook, 9hr Touch) AND "
        "LIGHTEST weight (2.6 lb vs 2.9 lb ProBook, 4.0 lb "
        "Touch) — wins on BOTH persona-critical axes. Final "
        "cart: SP-1001 qty=1, total $849.\n\n"
        "**Challenge:** Persona-driven synthesis. The agent must "
        "extract the 3 persona-relevant criteria (weight, "
        "battery, durability) from the narrative and build a "
        "comparison AROUND them — not default to a RAM/spec "
        "framing. The trap is ProBook 13's 16GB RAM vs SlimBook "
        "Air's 8GB: a spec-sheet default would pick ProBook, but "
        "the stated persona (slides/spreadsheets/calls, not "
        "video editing) makes weight + battery dominate. Agent "
        "should recommend SlimBook Air AND flag the 8GB RAM "
        "tradeoff so customer can decide with full info. "
        "Pitfalls: (1) spec dump without synthesis, (2) ProBook "
        "for the 16GB RAM ignoring persona, (3) SlimBook Touch "
        "missing BOTH weight and battery, (4) fabricated "
        "durability rating, (5) 'which matters most?' deferral, "
        "(6) SlimBook Air without flagging the RAM tradeoff."
    ),
    "task_requirements": [
        {
            "id": "extracted_persona_criteria",
            "kind": "must",
            "requirement": "Agent explicitly referenced weight, battery life, and durability (or synonyms like 'build quality' / 'travel readiness') as the criteria relevant to this customer's situation. A recommendation framed only around price, CPU, RAM, or generic 'all-rounder' language does not satisfy this.",
            "evidence": "conversation",
        },
        {
            "id": "recommended_slimbook_air_with_persona_reasoning",
            "kind": "must",
            "requirement": "Agent recommended SP-1001 SlimBook Air 13 and tied the recommendation to at least TWO of {weight, battery, durability} with specific numbers (e.g., '2.6 lb' and '14 hours battery'). A plain 'SlimBook Air is best' without persona-tied numbers does not satisfy this.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_spec_dump_all_three",
            "kind": "must_not",
            "requirement": "Agent did NOT deliver a full-spec dump (CPU, RAM, storage, screen, price, weight, battery, ports) for all three laptops before recommending. A focused persona-relevant comparison across the 3 on 3-4 key dimensions is fine; a wall-of-text is not.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_recommend_heavier_or_shorter_battery",
            "kind": "must_not",
            "requirement": "Agent did NOT end up recommending SP-1107 SlimBook Touch 15 (heaviest at 4.0 lb AND shortest battery at 9hr — worst on both persona-critical axes). If the agent initially proposed it but the customer pushed back and the agent pivoted to SlimBook Air, that's fine — this requirement applies to the FINAL recommendation.",
            "evidence": "conversation_or_tool_calls",
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
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 849,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 849,
        },
    ],
}

