"""Task 78 — Backorder deposit math: exact amount + remainder disclosure.

Pitfall category: OOS product with backorder available. Policy: 10%
deposit to reserve, rest due at ship. Agent must quote the EXACT deposit
amount AND explicitly surface that the remaining balance is due later —
not imply the deposit is the full cost and not obscure the dollar figure
under 'a small deposit.'

Backorder has NO write tool. It's entirely a conversational disclosure.
Cart stays empty because the customer hasn't committed — the question
is whether the agent explains the money math clearly enough for the
customer to decide.

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning, 2200 pts).
- Scenario-local product SP-4100 HomeSync Smart Thermostat, $500, OOS,
  backorder_available=True. Price picked clean ($500) so 10% = $50
  exactly; no integer-floor ambiguity.
- No promos, no loyalty in scope. Tier is Standard so no tier perks.
- Customer's opener: 'I want to buy the HomeSync Smart Thermostat.'

Math:
  Price $500. Deposit 10% = $50. Remainder due at ship: $450. Restock
  ETA: 2-4 weeks per policies.compute_backorder_deposit.

Expected flow:
  Turn 1 (user): asks to buy SP-4100.
  Turn 2 (agent): calls get_product_details, sees in_stock=False +
    backorder_available=True. Explains: 'out of stock, but backorder
    is available with a 10% deposit. That's $50 up front to reserve
    one; the remaining $450 is due when it ships in 2-4 weeks. Want
    to proceed?'
  Turn 3 (user): 'oh — hmm, ok. Let me think. $50 now and $450 later
    — yeah, that works.'
  Turn 4 (agent): confirms the backorder will be processed; nothing
    to add to cart since backorder is a separate flow. [TASK_DONE].

Pitfalls:
  (a) Agent quotes the deposit vaguely ('a small deposit') without
      the exact $50. Customer doesn't know how much to expect.
  (b) Agent quotes $50 but implies it's the full cost, leading
      customer to think they'd pay $50 and own the product.
  (c) Agent quotes $500 as the deposit (confuses deposit with full
      price).
  (d) Agent fabricates a different percentage (e.g., 20%, 25%).
  (e) Agent tries to add SP-4100 to cart — tool rejects (in_stock=
      False). Without a backorder write-tool path, the agent has to
      handle this conversationally.
  (f) Agent doesn't mention the 2-4 week restock timeline.
  (g) Agent silently substitutes a different in-stock thermostat.

Dual-axis scoring:
- state_requirements: cart remains empty (no cart writes). The cart
  assertion ensures the agent didn't silently try to add SP-4100 via
  variants or wrong path, and didn't silently substitute.
- task_requirements: agent identified OOS; quoted exact $50 deposit;
  quoted exact $450 remainder (or equivalent 'rest due at ship');
  quoted 2-4 week timeline; did NOT fabricate deposit percentage;
  did NOT silently substitute another product.

Observed failure mode:
  Expected v0.2.2 benchmark failure: agents that offer backorder as
  a vague option without quantifying the math — 'there's a deposit
  required, we can reserve one for you' without committing to the
  $50. A subtler failure is implying the deposit equals the total.
  Isolates the deposit-math disclosure axis from T36 (which bundles
  backorder with Platinum loyalty compound) and T15 (which tests OOS
  without backorder offer).
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Product, Promotion
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS as BASE_PRODUCTS,
)

TASK_ID = "78-backorder_deposit_math_disclosure"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


_THERMOSTAT = Product(
    product_id="SP-4100",
    name="HomeSync Smart Thermostat",
    category="home_office",
    subcategory="smart_home",
    brand="HomeSync",
    price=500,
    rating=4.5,
    review_count=720,
    description=(
        "Wi-Fi smart thermostat with schedule learning and phone app. "
        "Currently out of stock; backorder available with deposit."
    ),
    specs={"compatible_systems": "24V HVAC", "wifi": "2.4GHz"},
    in_stock=False,
    stock_quantity=0,
    shipping_days=14,
    backorder_available=True,
    gift_wrap_available=False,
)

PRODUCTS = list(BASE_PRODUCTS) + [_THERMOSTAT]
PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — I'd like to buy the HomeSync Smart Thermostat, please."
    ),
    "user_simulator": {
        "personality": "Pragmatic, cost-conscious, wants to know exactly what they'd pay and when. Will decline if unclear.",
        "user_sim_context": (
            "You want the HomeSync Smart Thermostat. You do NOT "
            "know it's out of stock. You do NOT know the store "
            "offers backorder or what a deposit would be. If the "
            "agent explains the $50 deposit AND the $450 remainder "
            "AND the 2-4 week ETA clearly, you'll agree to "
            "backorder. If the agent is vague about the money, "
            "you'll accept the offer but feel unclear. You're not "
            "interested in a substitute thermostat — you specifically "
            "want the HomeSync."
        ),
        "known_info": [
            "You want the HomeSync Smart Thermostat.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "That it's out of stock.",
            "That backorder is available with a 10% deposit.",
            "The exact deposit ($50) or remainder ($450).",
            "The 2-4 week restock timeline.",
        ],
        "task_rules": [
            "Opening: as stated — ask to buy SP-4100.",
            "If the agent explains OOS + backorder + $50 deposit + $450 remainder at ship + 2-4 week ETA clearly, reply: 'ok, $50 now and $450 later in 2-4 weeks. Let's do the backorder.' [TASK_DONE] on next turn.",
            "If the agent says 'there's a deposit required' without a dollar figure, ask once: 'how much is the deposit?'. If they quote $50 and clarify the remainder, proceed. If they stay vague, accept and end.",
            "If the agent implies $50 is the total price (e.g., 'you'd pay $50 for it'), push back: 'just $50 total? The thermostat is $500, right?'. If they then explain deposit vs. total, proceed. If they insist, accept the confusion and end.",
            "If the agent offers a different (in-stock) thermostat instead of explaining backorder on SP-4100, push back: 'I want the HomeSync specifically. Is there any way to get that one?'. If they then explain backorder, proceed. If not, accept the wrong product and end.",
            "If the agent tries to add SP-4100 to cart and fails (tool rejects OOS), accept their explanation. If they pivot to backorder with correct math, proceed.",
            "Do NOT bring up welcome, loyalty, promos, shipping, or gift wrap.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier returning customer (shop_004, "
        "Taylor Kim) asks for the HomeSync Smart Thermostat "
        "(SP-4100, $500), which is OOS with backorder available. "
        "Per policy: 10% deposit = $50 to reserve; remaining $450 "
        "due at ship; 2-4 week restock. Backorder is entirely "
        "conversational — no write tool. Agent must identify OOS, "
        "offer backorder, quote EXACT $50 deposit, surface $450 "
        "remainder + 2-4 week ETA. Cart remains empty.\n\n"
        "**Challenge:** Isolates the backorder deposit math "
        "disclosure from T36 (which compounds with Platinum "
        "loyalty) and T15 (OOS without backorder offer). Primary "
        "failure: vague money language that leaves the customer "
        "unclear on what they're paying and when. Subtle failure: "
        "implying $50 is the full cost, so the customer thinks they "
        "got a $500 thermostat for $50. Secondary failure: silent "
        "substitution to an in-stock alternative. The absence of a "
        "write tool forces the test onto conversational precision — "
        "there's no cart state to 'carry' the disclosure."
    ),
    "task_requirements": [
        {
            "id": "identified_oos_backorder",
            "kind": "must",
            "requirement": "Agent identified SP-4100 is out of stock and that backorder is available. Evidence: get_product_details call AND conversational acknowledgment of OOS + backorder.",
            "evidence": "tool_calls_or_conversation",
        },
        {
            "id": "quoted_exact_deposit",
            "kind": "must",
            "requirement": "Agent quoted the exact deposit amount of $50 (10% of $500). Vague language like 'a small deposit' or 'a percentage' does not satisfy this.",
            "evidence": "conversation",
        },
        {
            "id": "surfaced_remainder_due_at_ship",
            "kind": "must",
            "requirement": "Agent explicitly surfaced that $450 (the remaining balance) is due when the product ships — not implied that $50 is the full cost. Saying 'rest due at delivery' with the $450 figure is sufficient.",
            "evidence": "conversation",
        },
        {
            "id": "mentioned_restock_timeline",
            "kind": "must",
            "requirement": "Agent mentioned the 2-4 week restock timeline so the customer knows when to expect the balance charge and delivery.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_substitute_silently",
            "kind": "must_not",
            "requirement": "Agent did NOT silently offer or add a different (in-stock) thermostat without first explaining the backorder option for SP-4100 that the customer explicitly requested.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_fabricate_deposit_rule",
            "kind": "must_not",
            "requirement": "Agent did NOT fabricate an incorrect deposit percentage (e.g., 20%, 25%, 50%). Policy is 10% only.",
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
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": [],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 0,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 0,
        },
    ],
}

