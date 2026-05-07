"""Task 92 — Comparison frame lost: ambiguous 'better' after a tradeoff compare.

Pitfall category: customer asks for a head-to-head comparison on
multiple axes, then says 'go with the better one.' Neither option
dominates — it's a tradeoff. Agent must restate the tradeoff and ask
which axis the customer weights BEFORE adding, not silently pick by
price (cheaper = 'better') or specs (pricier = 'better').

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning).
- Catalog: task_1 base. Two comparable laptops in scope:
    SP-1001 SlimBook Air 13: $849, 8GB RAM, 256GB SSD, 14h battery,
      2.6lb.
    SP-1002 ProBook Laptop 13-inch: $999, 16GB RAM, 512GB SSD,
      12h battery, 2.9lb.
  Genuinely Pareto-incomparable: SP-1001 wins price/battery/weight,
  SP-1002 wins RAM/storage.
- No promos.

Expected flow:
  Turn 1 (user): 'Can you compare the SlimBook Air 13 and the ProBook
    13-inch on price, RAM, and battery? I want to pick one.'
  Turn 2 (agent): searches / get_product_details. Presents the
    tradeoff: SlimBook cheaper ($849 vs $999), longer battery
    (14h vs 12h), lighter (2.6 vs 2.9lb). ProBook more RAM (16 vs 8)
    and more storage (512 vs 256).
  Turn 3 (user): 'ok — go with the better one.'
  Turn 4 (agent): RESTATES the tradeoff in one line and asks which
    axis matters most: 'Which matters more to you — the cheaper /
    lighter / longer-battery SlimBook, or the more-RAM / more-
    storage ProBook? They're not strictly better than each other.'
  Turn 5 (user): 'hmm, I want more RAM for my coding classes. ProBook.'
  Turn 6 (agent): add_to_cart(SP-1002 qty=1). Confirms.
  Turn 7: [TASK_DONE].

Pitfalls:
  (a) Agent silently picks SP-1001 (cheaper = 'better'). PRIMARY FAIL.
  (b) Agent silently picks SP-1002 (pricier = 'better'). FAIL.
  (c) Agent picks one with a one-sided justification ('SlimBook is
      better because it's cheaper and lighter') without surfacing
      the RAM/storage tradeoff.
  (d) Agent asks 'which do you want?' without restating the tradeoff,
      forcing the customer to re-derive the comparison from memory.
  (e) Agent treats 'better' as an objective property of laptops
      rather than preference-dependent.

Distinct from:
  - T46 (comparison_set_retention): tests remembering the compared
    set, not resolving the ambiguous selector.
  - T22 (ambiguous_slimbook_reference): ambiguity is about WHICH
    product; here ambiguity is about WHICH AXIS.
  - T68 (persona_driven_comparison): the persona reveals the right
    axis. T92 has no persona hint — customer genuinely hasn't
    decided, and 'better' is a linguistic shortcut.

Dual-axis scoring:
- state_requirements: final cart has exactly the laptop the customer
  named AFTER clarification (SP-1002). One item, subtotal $999.
- task_requirements: agent surfaced the tradeoff on both axes;
  re-asked which axis matters when customer said 'better'; did NOT
  silently pick by price or specs.

Observed failure mode:
  Expected v0.2.2 benchmark failure: agents treat 'better' as
  resolvable — usually by picking cheaper (people-pleaser bias) or
  the one they last described positively. The test is whether the
  agent recognizes 'better' is ambiguous in a tradeoff context and
  bounces the question back WITH the tradeoff restated.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "92-ambiguous_better_tradeoff_clarify"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"

PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — can you compare the SlimBook Air 13 and the ProBook "
        "Laptop 13-inch on price, RAM, and battery? I want to "
        "pick one."
    ),
    "user_simulator": {
        "personality": "Thoughtful buyer who wants a clean comparison. Uses the word 'better' loosely as shorthand for 'pick for me', expects the agent to clarify if it's ambiguous.",
        "user_sim_context": (
            "You want ONE 13-inch laptop — either the SlimBook Air "
            "13 or the ProBook Laptop 13-inch. You care about RAM "
            "most (you have coding classes) but you have NOT yet "
            "said that. When the agent presents both laptops, you "
            "will say 'go with the better one' — this is a shorthand, "
            "not a real instruction. If the agent restates the "
            "tradeoff and asks which axis matters, you'll reveal RAM "
            "matters most and pick the ProBook ($999). If the agent "
            "picks one without asking, you'll accept the choice but "
            "it was wrong to assume."
        ),
        "known_info": [
            "You want a 13-inch laptop — either SlimBook Air 13 or ProBook 13-inch.",
            "You secretly care most about RAM (for coding classes), but have not said so yet.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The exact prices, RAM, and battery of each.",
            "Which one wins on which axis.",
        ],
        "task_rules": [
            "Opening: as stated — ask to compare SlimBook Air 13 vs ProBook Laptop 13-inch on price, RAM, and battery.",
            "After the agent presents the comparison (both products' specs on all 3 axes), reply: 'ok — go with the better one, please.'",
            "If the agent RESTATES the tradeoff (e.g., 'SlimBook wins price/battery/weight, ProBook wins RAM/storage — which matters more to you?') AND asks which axis you care about, reply: 'I need more RAM for my coding classes — let's do the ProBook.' Then if they add SP-1002 with confirmation, say: 'perfect, $999 works. [TASK_DONE]'.",
            "If the agent SILENTLY picks one (adds to cart without asking which axis you value, or without restating the tradeoff), push back: 'wait — why that one? Can you walk me through why it's better?'. If they then restate both sides of the tradeoff and ask, proceed to reveal RAM → ProBook. If they defend the pick without surfacing the other axis, accept and [TASK_DONE] — agent failed.",
            "If the agent recommends one with a one-sided justification (e.g., 'the ProBook is better because it has more RAM' without mentioning SlimBook's price/battery/weight advantages), push back: 'but isn't the SlimBook cheaper and has longer battery? How do you decide?'. If they then surface the tradeoff and ask, proceed. If they restate one-sided, accept and end.",
            "If the agent asks 'which do you want?' WITHOUT restating the tradeoff (e.g., just 'which would you like — SlimBook or ProBook?'), push back gently: 'remind me — what's the tradeoff again?'. If they then restate both sides and ask, proceed. If they give another cursory summary, accept one pick and end.",
            "Do NOT bring up promos, loyalty, shipping, gift wrap, or third products.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier returning customer (shop_004, "
        "Taylor Kim) asks for a 3-axis comparison of SlimBook Air 13 "
        "($849) and ProBook Laptop 13-inch ($999). They're Pareto-"
        "incomparable: SlimBook wins price/battery/weight; ProBook "
        "wins RAM/storage. Customer says 'go with the better one.' "
        "Agent must restate the tradeoff and ask which axis matters "
        "before adding. Customer reveals RAM matters → picks "
        "ProBook. Final cart: SP-1002 qty=1, $999.\n\n"
        "**Challenge:** Isolates the 'better = ambiguous in a "
        "tradeoff' failure. Primary failure: treating 'better' as "
        "resolvable and silently picking by price (cheaper bias) or "
        "by specs (pricier bias). Secondary failure: picking one "
        "with a one-sided justification that hides the other axis. "
        "Tertiary failure: asking 'which do you want?' without "
        "re-surfacing the tradeoff, forcing the customer to re-derive "
        "the comparison. Distinct from T46 (comparison set memory), "
        "T22 (which product), T68 (persona-hinted comparison)."
    ),
    "task_requirements": [
        {
            "id": "presented_both_axes_in_compare",
            "kind": "must",
            "requirement": "When presenting the initial comparison, agent showed BOTH products' values on all three requested axes (price, RAM, battery) so the tradeoff is visible. Listing only one product's specs, or skipping an axis, fails.",
            "evidence": "conversation",
        },
        {
            "id": "clarified_ambiguous_better",
            "kind": "must",
            "requirement": "When the customer said 'go with the better one', the agent did NOT immediately commit to either product. Instead, the agent restated the tradeoff (both sides — one product's advantages AND the other product's advantages) and asked the customer which axis they weight most. A one-sided justification ('the X is better because of [single axis]') without surfacing the other product's advantages fails this requirement.",
            "evidence": "conversation",
        },
        {
            "id": "got_explicit_axis_or_product_confirmation",
            "kind": "must",
            "requirement": "Before calling add_to_cart, the agent had the customer's explicit confirmation of which product (or which axis) they actually want. Silently adding a product on the 'better' message alone fails this.",
            "evidence": "tool_calls_or_conversation",
        },
        {
            "id": "did_not_silently_pick",
            "kind": "must_not",
            "requirement": "Agent did NOT call add_to_cart for either SP-1001 or SP-1002 in the turn immediately after the customer said 'go with the better one' without first restating the tradeoff and getting explicit customer selection.",
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

