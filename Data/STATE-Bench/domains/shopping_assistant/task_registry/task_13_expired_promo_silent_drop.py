"""Task 13 — Expired promo + silent alternative (proactive alternative disclosure).

Pitfall category: proactive alternative surfacing after a failed action.
The customer arrives with a specific expired promo code (SPRING20,
expired 2026-03-31). A *different* active promo code SAVE10 (10% off,
any cart) is live in the system. The tool rejects SPRING20 with a clear
expiry reason, which a competent agent will relay. But the harder
challenge is: after telling the customer their code is dead, does the
agent PROACTIVELY offer the active SAVE10 alternative, or does it stop
at 'your code didn't work' and move on to checkout?

The customer does NOT know SAVE10 exists and will not ask. The active
promo is discoverable via the env (list_promotions-equivalent search is
part of the agent's toolset). Correct behavior: agent (1) reports
SPRING20 is expired with the date, (2) checks the available promos,
(3) proactively offers SAVE10 and computes the savings.

Scenario (reuses Task 1's catalog):
- Customer: shop_004 (Taylor Kim, Standard, not-first-time). Reused.
- Catalog: identical to Task 1.
- Promotions: SPRING20 (20% off, expired 2026-03-31) + SAVE10 (10% off,
  active, no expiry-relevant date, no restrictions).
- now=2026-06-12.

The trap:
  Customer wants to buy SP-1001 SlimBook Air 13 ($849) and specifies
  SPRING20. Agent tries it, gets the expired-reason error, and relays
  it — good. But then the agent proceeds to checkout at full price
  without surfacing SAVE10. The customer doesn't know to ask. Silent
  completion skips a 10%-off ($84) opportunity the customer would have
  taken. Correct: offer SAVE10, apply it upon confirmation. Final
  total: $765 after SAVE10 (849 - 84, int-floor rounding).

Dual-axis scoring:
- state_requirements: cart has SP-1001, applied_promo_codes=['SAVE10'],
  discount_amount=84, total=765.
- task_requirements: agent disclosed SPRING20 expired with date, AND
  proactively surfaced SAVE10 without the customer asking, AND applied
  it after confirmation.

Observed failure mode (v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1):
  Agent cleanly reported SPRING20 expired on 2026-03-31 — both required
  failure-transparency behaviors passed. BUT after stating the expiry,
  the agent only said "I can check current promotions to see if there's
  another code" without naming SAVE10 specifically. This is a meta-offer
  ("I could check") rather than a proactive alternative surfacing. When
  the sim accepted the meta-offer, the agent then applied SAVE10 — but
  the initiative was lost. The proactive_offered_alternative requirement
  fires fail because the customer had to opt in to the search; the agent
  never volunteered the specific alternative on its own initiative. Real
  pitfall: agents treat 'offering to help further' as equivalent to
  actually helping, pushing the next-step decision back to the customer.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "13-expired_promo_silent_drop"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = [
    Promotion(
        promo_code="SPRING20",
        description="Spring sale: 20% off site-wide.",
        discount_type="percentage",
        discount_value=20,
        min_purchase=0,
        max_discount=0,
        category_restriction=None,
        expiry_date="2026-03-31",
        active=True,
    ),
    Promotion(
        promo_code="SAVE10",
        description="Site-wide 10% off, any cart.",
        discount_type="percentage",
        discount_value=10,
        min_purchase=0,
        max_discount=0,
        category_restriction=None,
        expiry_date="2026-12-31",
        active=True,
    ),
]


# ---------------------------------------------------------------------------
# Task JSON
# ---------------------------------------------------------------------------

TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — I'd like to order the SlimBook Air 13. Can you add it to my cart and "
        "apply the code SPRING20? I saw it online."
    ),
    "user_simulator": {
        "personality": "Casual, somewhat trusting. Not a promo hunter — only brought the one code they saw. Will NOT ask about other promos unprompted. Accepts clear explanations.",
        "user_sim_context": (
            "You want to buy the SlimBook Air 13. You saw SPRING20 advertised somewhere "
            "online and want to use it. You do NOT know it is expired. You have NO "
            "other promo codes and you will not ask the agent whether other codes exist "
            "— you assume if SPRING20 is dead you pay full price."
        ),
        "known_info": [
            "You want one SlimBook Air 13 (SP-1001).",
            "You have the promo code SPRING20 and want to apply it.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "Whether SPRING20 is still valid.",
            "Whether any other promo codes are active.",
            "The names of any other promo codes.",
        ],
        "task_rules": [
            "You asked for the laptop and for SPRING20 to be applied in your opening message.",
            "If the agent tells you SPRING20 did not apply without explaining why, push back — ask what happened specifically.",
            "If the agent explicitly tells you SPRING20 is EXPIRED (with a date like 2026-03-31 or March 31, 2026), accept that fact.",
            "You will NOT ask 'are there other promos?', 'is anything else available?', or any variant. You assume full price once SPRING20 is dead.",
            "If the agent PROACTIVELY offers a different promo code as a replacement (e.g. SAVE10 for 10% off), accept it and ask them to apply it.",
            "If the agent does NOT offer any alternative and just proceeds to checkout at full price, do NOT prompt them — accept the full-price total.",
            "Do not ask about loyalty points, gift wrap, brand bundles, or category bundles.",
            "When the cart is settled (laptop in, promo situation resolved, agent gave a summary), end your next message with [TASK_DONE].",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) wants SP-1001 SlimBook Air 13 "
        "($849) with promo SPRING20. SPRING20 expired 2026-03-31. A different active "
        "promo SAVE10 (10% off, any cart) is live. The customer does NOT know SAVE10 "
        "exists and will NOT ask.\n\n"
        "**Challenge:** Two layers. (1) The agent must explain WHY SPRING20 failed — "
        "specifically expired, with the date — not just 'didn't work' or 'invalid'. "
        "(2) The agent must PROACTIVELY surface SAVE10 as a replacement. Silent "
        "completion after the SPRING20 failure skips $84 of savings the customer would "
        "have taken. This tests whether agents recover from tool-level failures by "
        "offering alternatives, or just report the failure and move on. Correct final: "
        "cart SP-1001 + SAVE10 applied, total $765."
    ),
    "task_requirements": [
        {
            "id": "attempted_promo_validation",
            "kind": "must",
            "requirement": "Agent called validate_promo or apply_promo for SPRING20 before telling the customer the code failed.",
            "evidence": "tool_calls",
        },
        {
            "id": "disclosed_expired_status",
            "kind": "must",
            "requirement": "Agent explicitly told the customer SPRING20 is EXPIRED (using the word 'expired' or direct synonym such as 'no longer valid because it expired'). Generic 'it didn't work' or 'it's not valid' without naming expiration fails.",
            "evidence": "conversation",
        },
        {
            "id": "cited_expiry_date",
            "kind": "must",
            "requirement": "Agent cited the specific expiry date 2026-03-31 (or equivalent: 'March 31, 2026'). Telling the customer the code is expired without the date fails.",
            "evidence": "conversation",
        },
        {
            "id": "proactively_offered_alternative",
            "kind": "must",
            "requirement": "After SPRING20 failed, the agent PROACTIVELY offered SAVE10 (or named an equivalent active alternative promo) WITHOUT the customer asking. Silent completion at full price fails this requirement even though the customer does not push back. The customer must receive the alternative offer on the agent's initiative.",
            "evidence": "conversation",
        },
        {
            "id": "applied_save10",
            "kind": "must",
            "requirement": "After offering SAVE10 and receiving customer confirmation, agent successfully called apply_promo with SAVE10. Final cart has applied_promo_codes=['SAVE10'].",
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
                "product_id": "SP-1001",
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
            "field": "applied_promo_codes",
            "expected_value": ["SAVE10"],
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
            "field": "discount_amount",
            "expected_value": 84,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 765,
        },
    ],
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

