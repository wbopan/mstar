"""Task 61 — Mid-flow constraint reveal (video editing + portability).

Pitfall category: customer starts with ONE constraint (video
editing), agent recommends based on it, then customer REVEALS a
second constraint mid-flow (must be under 3 lbs for travel). The
initial recommendation no longer satisfies both. Agent must
recognize the conflict and pivot to a NEW product that satisfies
BOTH — not stick with the initial pick, not ignore the new
constraint, not pick a lighter but spec-insufficient option.

Scenario:
- Customer shop_001 (Alex Rivera, Platinum, returning).
- Turn 1: asks for hobby video editing laptop recommendation
  among BudgetLine / ProBook 15 / CreatorStudio 15.
- Agent (expected): recommends SP-1101 ProBook 15 ($1299, 16GB
  RAM, 4.1 lb) — correct for video editing.
- Turn 2: customer reveals: 'oh actually I travel a lot, I need
  under 3 lbs. Does the ProBook 15 work?'
- ProBook 15 is 4.1 lb — FAILS new constraint.
- Options under 3 lb with at least 16GB RAM:
    SP-1002 ProBook 13 ($999, 16GB RAM, 2.9 lb) — fits BOTH.
- Options under 3 lb but < 16GB RAM (insufficient for video):
    SP-1001 SlimBook Air 13 ($849, 8GB RAM, 2.6 lb) — INADEQUATE
    SP-1003 SlateTab Studyline 14 ($749, 8GB RAM, 3.2 lb) — also
      over 3 lb but close
    SP-1104 SlimBook Air 13 Previous Gen (OOS)
    SP-1106 ProBook Chromebook 11 ($329, 4GB RAM, 2.2 lb) — way
      under-specced
- Correct pivot: SP-1002 ProBook 13 — same 16GB RAM satisfies
  video editing AND 2.9 lb satisfies travel constraint.

Expected flow:
  Turn 1 (user): 'hobby video editing — BudgetLine / ProBook 15 /
    CreatorStudio 15 — which?'
  Turn 2 (agent): recommends ProBook 15 with reasoning (ruled out
    BudgetLine's 4GB RAM, CreatorStudio 32GB overkill). Adds
    SP-1101.
  Turn 3 (user): 'oh actually I travel a lot — need under 3 lbs.
    Does this work?'
  Turn 4 (agent): recognizes ProBook 15 is 4.1 lb → doesn't fit.
    Pivots: 'ProBook 15 is 4.1 lb so no, but ProBook 13 (same
    brand, same 16GB RAM — good for hobby video editing — and
    2.9 lb so it meets your weight target) is a better fit for
    your travel need. It's $300 less too.' Removes SP-1101,
    adds SP-1002.
  Turn 5 (user): confirms.

Pitfalls:
  (a) Sticks with ProBook 15 — claims 4.1 lb 'is still
      portable' or similar — violates stated constraint.
  (b) Pivots to SlimBook Air 13 (SP-1001, 2.6 lb) — meets weight
      but only 8GB RAM, insufficient for video editing. Agent
      SACRIFICED the original constraint.
  (c) Pivots to ProBook Chromebook 11 (SP-1106, 2.2 lb, 4GB) —
      same failure mode, way worse.
  (d) Says 'we don't have a laptop that meets both' when SP-1002
      actually does — false negative.
  (e) Asks customer to pick a priority ('do you care more about
      video or travel?') without surfacing ProBook 13 as the
      both-constraint solution.
  (f) Silently keeps SP-1101 in cart without pivoting (state
      won't reflect the switch).

Math:
  SP-1002 $999 single-item cart. No wrap, no shipping, no loyalty.
  Final subtotal+total = $999.

Distinct from T1 (weight constraint revealed upfront) and T44
(mid-flight budget bump) — T61's novelty: the mid-flow reveal
CONFLICTS with an already-made recommendation, and the solution
requires preserving the ORIGINAL spec constraint while
satisfying the NEW one. Tests whether the agent holds BOTH
requirements in memory after a context shift.

Observed failure mode:
  v0.2.2, 2026-04-20, VanillaAgent / gpt-5.1, 2 runs: 0 PASS, 2 FAIL.
  Interesting fail pattern: agent DOES pivot correctly on the mid-flow
  reveal (removes ProBook 15, adds ProBook 13, preserves RAM — state
  passes cleanly both runs), but fails on the INITIAL recommendation
  requirement. Both runs the agent oversells CreatorStudio 15 as 'top
  choice if you can afford it' and frames 32GB RAM as 'ideal' rather
  than overkill for hobby video editing, refusing to make ProBook 15
  the single explicit pick. This captures a real deployment risk:
  agents hedging on recommendations when multiple options are
  plausible, pushing the decision burden back to the customer instead
  of owning a specific pick based on the stated use case. Task_req
  fail on initial_probook15_recommendation, state_req pass.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "61-mid_flow_constraint_pivot"
USER_ID = "shop_001"
NOW = "2026-06-10T10:00:00"

PRODUCTS = list(BASE_PRODUCTS)
PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — I'm picking between three laptops for hobby video "
        "editing: the BudgetLine Notebook 15, the ProBook 15, and "
        "the CreatorStudio 15. Which one should I get?"
    ),
    "user_simulator": {
        "personality": "Thoughtful, trusts the agent's reasoning, reveals constraints incrementally as they come to mind.",
        "user_sim_context": (
            "You want hobby video editing (travel/family/YouTube "
            "1080p). You also travel a LOT and your current laptop "
            "is painful to carry — you need under 3 lbs. But you "
            "don't think to mention the travel constraint until "
            "AFTER you see the agent's first recommendation. Your "
            "budget is up to $1500. You care about BOTH "
            "constraints equally; don't let the agent talk you "
            "into sacrificing one."
        ),
        "known_info": [
            "You want hobby video editing (1080p, not pro 4K).",
            "You travel a lot, need under 3 lbs.",
            "Budget up to $1500.",
            "Both constraints matter equally.",
        ],
        "unknown_info": [
            "Which laptops meet both constraints.",
            "Specific weight/RAM values in the catalog.",
        ],
        "task_rules": [
            "Turn 1 opener: as stated — hobby video editing between BudgetLine / ProBook 15 / CreatorStudio 15. Do NOT mention weight or travel yet.",
            "If the agent recommends ProBook 15 with correct reasoning (4GB insufficient / 32GB overkill for hobby), reply: 'Makes sense, let's go with the ProBook 15.' Wait for the agent to confirm add_to_cart.",
            "If the agent recommends BudgetLine, push back: 'isn't 4GB low for video editing?' — expect a pivot to ProBook 15.",
            "If the agent recommends CreatorStudio, push back: 'I think 32GB is overkill for hobby — is there a middle option?' — expect a pivot to ProBook 15.",
            "AFTER the agent confirms adding ProBook 15 to cart, reveal the second constraint: 'Oh wait — I also travel a lot, I need something under 3 lbs. Does the ProBook 15 work?'",
            "If the agent pivots to ProBook 13 (SP-1002) citing same 16GB RAM AND 2.9 lb AND removes the ProBook 15 and adds ProBook 13, reply: 'Perfect, that works — let's go with the ProBook 13.' After final confirmation, reply 'Total looks good.' and [TASK_DONE].",
            "If the agent sticks with ProBook 15 claiming 4.1 lb 'is still portable', push back: 'no, 3 lbs is a firm limit for me — my current one is 4 lbs and it's too heavy.' If the agent then pivots correctly, proceed. If not, accept and end — failed on constraint respect.",
            "If the agent pivots to SlimBook Air 13 (SP-1001) without flagging the RAM change, push back: 'wait — doesn't SlimBook Air only have 8GB? You said earlier 16GB was the minimum for video editing.' If the agent then pivots to ProBook 13, proceed. If they insist SlimBook Air is fine for video editing, accept and end — failed on preserving the original constraint.",
            "If the agent declares 'no laptop in the catalog fits both under-3-lb and 16GB RAM', push back: 'really? The ProBook 13 is 16GB, I thought it might be lighter than the 15-inch.' Expect pivot. If agent stays negative, accept and end — failed on catalog search.",
            "If the agent asks you to pick between video editing and travel as priorities, push back: 'both matter — isn't there a laptop that does both?' Expect pivot to ProBook 13. If they avoid, accept and end — failed on both-constraint solution.",
            "Do NOT suggest ProBook 13 by name — let the agent find it.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Platinum returning customer (shop_001) first "
        "asks for a hobby video editing laptop among BudgetLine / "
        "ProBook 15 / CreatorStudio 15. The agent should "
        "recommend ProBook 15 ($1299, 16GB RAM) — correct for "
        "video editing. After the customer confirms adding "
        "ProBook 15, they reveal a SECOND constraint: 'I travel a "
        "lot, need under 3 lbs.' ProBook 15 is 4.1 lb — fails "
        "the new constraint. Agent must pivot to SP-1002 ProBook "
        "13 ($999, same 16GB RAM, 2.9 lb) which satisfies BOTH "
        "the video editing requirement and the weight limit. "
        "Must remove SP-1101 and add SP-1002. Final cart: SP-1002 "
        "qty=1, total $999.\n\n"
        "**Challenge:** Mid-flow constraint reveal + original-"
        "constraint preservation. The agent must hold BOTH "
        "requirements in memory after a context shift — not "
        "abandon the RAM requirement when the weight constraint "
        "arrives, not abandon the weight constraint to preserve "
        "the existing cart. Pitfalls: (1) sticks with ProBook 15 "
        "despite weight mismatch, (2) pivots to SlimBook Air 13 "
        "(only 8GB, insufficient for video) — meets weight but "
        "sacrifices video editing, (3) declares no laptop fits "
        "both when ProBook 13 does, (4) asks customer to "
        "prioritize instead of finding the both-constraint "
        "solution, (5) silently keeps ProBook 15 in cart."
    ),
    "task_requirements": [
        {
            "id": "initial_probook15_recommendation",
            "kind": "must",
            "requirement": "Agent initially recommended ProBook 15 (SP-1101) for hobby video editing, with reasoning about why BudgetLine's 4GB is insufficient and CreatorStudio's 32GB is overkill. This is the setup for the mid-flow reveal.",
            "evidence": "conversation_or_tool_calls",
        },
        {
            "id": "recognized_weight_conflict",
            "kind": "must",
            "requirement": "When the customer revealed the under-3-lbs travel constraint, the agent explicitly acknowledged that ProBook 15 (4.1 lb) does NOT meet this constraint. Silent pivot or ignoring the new constraint fails.",
            "evidence": "conversation",
        },
        {
            "id": "pivoted_to_probook13",
            "kind": "must",
            "requirement": "Agent pivoted to SP-1002 ProBook 13 (2.9 lb, 16GB RAM). The recommendation must tie the pivot to BOTH constraints: the 16GB RAM preserves video editing suitability, and the 2.9 lb meets the travel requirement. Pivoting to SlimBook Air (SP-1001, 8GB RAM) fails because it sacrifices the original RAM requirement.",
            "evidence": "conversation",
        },
        {
            "id": "cart_switched",
            "kind": "must",
            "requirement": "Agent removed the initial SP-1101 from the cart and added SP-1002 via the cart tools. The final cart must contain only SP-1002 (1 item), NOT both or just SP-1101.",
            "evidence": "tool_calls",
        },
        {
            "id": "did_not_sacrifice_ram",
            "kind": "must_not",
            "requirement": "Agent must not recommend SP-1001 SlimBook Air 13 (8GB RAM) as the pivot. Its weight satisfies the travel constraint but its RAM is insufficient for video editing per the agent's own earlier reasoning.",
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
                "product_id": "SP-1002",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
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

