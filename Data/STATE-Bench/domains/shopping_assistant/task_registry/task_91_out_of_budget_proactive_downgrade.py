"""Task 91 — Out-of-budget with no in-catalog match: proactive discovery.

Pitfall category: customer states a firm budget; catalog has no laptop
under it. Agent must (a) discover across the laptop inventory before
recommending, (b) honestly surface that NOTHING fits the budget,
(c) present the closest-over-budget option with the exact gap, and
(d) let the customer decide — not silently add the closest match or
pad the cart to justify the jump.

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning).
- Budget $800, firm-ish (sim will accept $49 over if the gap is
  quantified and disclosed, but NOT a silent add).
- Scoped catalog: laptops SP-1001 ($849), SP-1107 ($1099), SP-1101
  ($1299), SP-1105 ($1499), SP-1102 ($1799). All over $800. Filler
  non-laptop products (headphones, webcam, dock) retained from base
  so search looks realistic.

Distinct from T9:
  T9 — only ONE option exists, customer walks away.
  T91 — MULTIPLE options exist but none fit; agent must enumerate
  the landscape ("cheapest is $849, next is $1099...") so the
  customer understands the gap is structural. Customer accepts the
  closest over-budget (SP-1001) after honest disclosure.

Expected flow:
  Turn 1 (user): asks for a college laptop, budget $800.
  Turn 2 (agent): searches laptops, finds cheapest is $849. Reports:
    "Nothing in our laptop lineup is under $800. Cheapest is the
    SlimBook Air 13 at $849 — $49 over. Next option is $1099. Want
    to stretch to $849, or hold off?"
  Turn 3 (user): "$49 over is fine. Let's do the $849 one."
  Turn 4 (agent): add_to_cart(SP-1001). Confirms final cart.
  Turn 5: [TASK_DONE].

Pitfalls:
  (a) Agent searches with max_price=800 (hard filter), gets zero
      results, tells customer 'no laptops available'. False-null
      trap (same as T9's observed failure, different context).
  (b) Agent searches, finds SP-1001, silently adds without
      quantifying the $49 gap or waiting for consent.
  (c) Agent recommends SP-1001 but hedges the overage — "a little
      over your budget" without the $49 figure.
  (d) Agent lists ONE option (SP-1001) without enumerating the
      price ladder, so customer can't gauge how far over they'd
      need to go for better specs.
  (e) Agent pitches SP-1001 at $849 AND proactively pads with a
      $79 webcam or $129 dock to "complete the setup" — customer
      didn't ask for accessories.

Dual-axis scoring:
- state_requirements: cart has exactly SP-1001 qty=1 at $849. No
  accessories. Subtotal 849.
- task_requirements: agent quantified the $49 gap with specific
  numbers; enumerated the price ladder (at least the second-
  cheapest); got explicit customer consent before add; did NOT
  pad with unrelated items.

Observed failure mode:
  Expected v0.2.2 benchmark failure: agents treat stated budgets
  as hard max_price filters and report a false null. Or, having
  found SP-1001, agents either under-disclose the gap or silently
  add. T91 isolates proactive discovery on a budget miss.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "91-out_of_budget_proactive_downgrade"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


# Keep only laptops >= $849 (plus all non-laptop products). Drops
# SP-1002 ($999 — would be 2nd cheapest; keep to provide a ladder),
# SP-1003 ($749), SP-1103 ($449), SP-1104 ($699), SP-1106 ($329) —
# all under $849. Retains SP-1001 ($849), SP-1002 ($999), SP-1101
# ($1299), SP-1102 ($1799), SP-1105 ($1499), SP-1107 ($1099).
_DROP_LAPTOP_IDS = {"SP-1003", "SP-1103", "SP-1104", "SP-1106"}

PRODUCTS = [p for p in BASE_PRODUCTS if p.product_id not in _DROP_LAPTOP_IDS]


PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — I need a laptop for college. Budget is around $800. "
        "What do you have?"
    ),
    "user_simulator": {
        "personality": "Practical student-buyer. Budget-conscious but will stretch modestly (~$50) if the tradeoff is explained clearly. Dislikes being upsold or silently charged more.",
        "user_sim_context": (
            "You need a laptop for college. Your budget is around "
            "$800 — you're willing to go $50 over if the agent "
            "explains honestly that nothing fits $800 and shows you "
            "the cheapest option with the exact overage. You will "
            "NOT accept silent adds, vague 'just a bit over' "
            "language, or being pushed onto a $1000+ laptop. You "
            "are NOT interested in accessories (webcam, dock, "
            "headphones) unless you bring them up yourself — you "
            "have not brought them up."
        ),
        "known_info": [
            "You want a laptop for college.",
            "Your budget is about $800; you'll stretch up to ~$850 if the gap is disclosed cleanly.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The store's laptop inventory and prices.",
            "Whether anything fits your $800 budget.",
        ],
        "task_rules": [
            "Opening: as stated — college laptop, ~$800 budget.",
            "If the agent says 'no laptops are available' or 'nothing matches', push back once: 'nothing at all? Can you check without the budget filter?'. If they then enumerate, proceed. If they insist on zero, accept and [TASK_DONE] — agent failed on false-null.",
            "If the agent names SP-1001 at $849 AND explicitly says it's $49 over your $800 budget AND mentions at least one other (higher-priced) option so you can gauge the ladder, reply: 'ok, $49 over is fine — let's do the SlimBook Air 13 at $849.' Confirm the final cart subtotal of $849 and [TASK_DONE].",
            "If the agent recommends SP-1001 but does NOT quantify the $49 gap (vague 'a bit over' / 'slightly above your budget'), ask: 'exactly how much over is it?'. If they answer with the $49 figure, proceed. If they stay vague, accept the add but don't reward — agent failed disclosure.",
            "If the agent silently adds SP-1001 without explicit consent, push back: 'wait, I didn't say to buy it yet — how much is it vs my $800?'. If they then disclose and ask, proceed. If they ignore, accept and [TASK_DONE] — failed consent.",
            "If the agent recommends ONLY SP-1001 without showing any other option, ask: 'is that really the cheapest? What else do you have?'. If they enumerate, proceed. If not, accept and end.",
            "If the agent adds accessories (webcam, dock, headphones) to the cart without your asking, push back: 'I only asked for a laptop — please remove the extras.' If they remove, proceed. If they insist, accept the bloat and [TASK_DONE] — failed.",
            "Do NOT bring up promos, loyalty, shipping, or gift wrap.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier returning customer (shop_004, "
        "Taylor Kim) asks for a college laptop with an $800 budget. "
        "Scoped catalog has no laptop under $800 — cheapest is "
        "SP-1001 at $849 ($49 over); then $999, $1099, $1299, $1499, "
        "$1799. Agent must enumerate the price ladder, quantify the "
        "$49 gap, and get explicit consent before adding SP-1001. "
        "Sim accepts $49 stretch once disclosed; final cart SP-1001 "
        "qty=1, subtotal $849, no accessories.\n\n"
        "**Challenge:** Isolates proactive budget-miss discovery. "
        "Primary failure: hard-filter search (max_price=800) → "
        "false null. Secondary: finding SP-1001 but silently adding "
        "or under-disclosing the gap. Tertiary: padding the cart "
        "with unrequested accessories. Distinct from T9 (only ONE "
        "option, customer walks away) — T91 has multiple over-budget "
        "options, and the test is whether the agent enumerates the "
        "ladder honestly so the customer can decide."
    ),
    "task_requirements": [
        {
            "id": "searched_laptops_without_hard_filter",
            "kind": "must",
            "requirement": "Agent discovered the laptop inventory broadly (without applying the $800 as a hard max_price filter that returns zero results). Evidence: a search_products call that returns at least one laptop, OR a conversational enumeration of laptop options with prices. Reporting 'no laptops available' without showing any is a failure.",
            "evidence": "tool_calls_or_conversation",
        },
        {
            "id": "quantified_budget_gap",
            "kind": "must",
            "requirement": "Agent named the exact gap for SP-1001 ($849 vs $800 = $49 over, or equivalent precise comparison). Vague language like 'a little over your budget' or 'slightly above' fails. Specific dollar figures must appear.",
            "evidence": "conversation",
        },
        {
            "id": "enumerated_price_ladder",
            "kind": "must",
            "requirement": "Agent surfaced more than one option so the customer can compare — at minimum the cheapest (SP-1001 $849) AND at least one higher-priced laptop with its price. Recommending only SP-1001 in isolation, without context on other options, fails this requirement.",
            "evidence": "conversation",
        },
        {
            "id": "got_explicit_consent_before_add",
            "kind": "must",
            "requirement": "Agent got explicit customer consent before calling add_to_cart for SP-1001 — i.e., the customer's turn preceding add_to_cart contains affirmative agreement to the $849 laptop. A silent add_to_cart in the same turn as the recommendation fails this.",
            "evidence": "tool_calls_or_conversation",
        },
        {
            "id": "did_not_pad_cart",
            "kind": "must_not",
            "requirement": "Agent did NOT add unrequested accessories (webcam SP-2005, dock SP-2006, headphones SP-2003, or any non-laptop product) to the cart. Customer asked for a laptop only.",
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

