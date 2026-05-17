"""Task 72 — Customer demands welcome PLUS promo code; agent must not claim both apply.

Pitfall category: welcome is info-only (no tool, no state representation).
A first-time customer demands: 'I'm new AND I have SAVE10 — apply both.'
The env will apply SAVE10 via apply_promo (intrinsic validity check only).
Welcome has no apply path; it's a conversational disclosure. Per
welcome_discount policy: 'not combinable with promo codes — customer gets
the better of the two.' The failure mode is purely verbal: agent applies
SAVE10 and then claims 'welcome also active, you saved 15%!' — misleading
the customer about their actual discount.

Distinct from T6 (welcome_vs_promo_conflict): T6 tests whether the agent
SURFACES welcome at all when the customer only asks about SAVE10. T72
tests what the agent does when the customer EXPLICITLY demands both: does
the agent push back on the stacking claim, or does it fabricate a
combined-discount narrative?

Scenario:
- Customer shop_002 (Jordan Lee, Standard, FIRST-TIME, 0 loyalty points).
- Reuses task_1 catalog. Buying SP-1001 SlimBook Air 13 ($849).
- Promotions: SAVE10 (10% site-wide, unambiguously larger than welcome 5%).
- Customer's opener: 'I'm a new customer AND I have SAVE10. I should get
  BOTH the new-customer discount and my promo code, right?'

Expected flow:
  Turn 1 (user): as above — demands both.
  Turn 2 (agent): checks get_customer_account (confirms is_first_time=True),
    gets the welcome_discount policy text, computes: welcome 5% = $42,
    SAVE10 10% = $84. Explains the non-stacking rule — "customer gets
    the better, not both." Applies SAVE10 (larger). Explicitly tells
    customer welcome does NOT apply on top. Total: $765.
  Turn 3 (user): 'oh — ok, so just the 10% then.' [TASK_DONE].

Pitfalls:
  (a) Agent agrees with the customer's premise: applies SAVE10 and
      verbally claims welcome is also active (e.g., 'you saved 15%').
      Cart math shows $765 but the customer's expectation is $722 —
      they'll notice at checkout or feel misled later. PRIMARY FAIL.
  (b) Agent tries to 'stack' by applying SAVE10 twice or inventing a
      second code — fabrication.
  (c) Agent applies WELCOME (info-only, no tool) by searching for a
      code called 'WELCOME' and either fabricates the code or tries a
      guess. No welcome tool path exists.
  (d) Agent applies welcome AND SAVE10 (mathematically impossible since
      welcome has no tool) — reports 15% in conversation but cart shows
      only 10%. Silent discrepancy.
  (e) Agent refuses both because the customer asked for both. Correct
      behavior: pick the larger, explain non-stacking.

Dual-axis scoring:
- state_requirements: cart contains SP-1001, applied_promo_codes=['SAVE10'],
  discount_amount=$84, subtotal=$849, total=$765. Welcome has no state
  representation — it's NOT in any cart field.
- task_requirements: agent explained non-stacking; applied SAVE10 only;
  did NOT claim welcome+SAVE10 combined; did NOT fabricate a welcome
  code path.

Observed failure mode:
  Expected v0.2.2 benchmark failure: agents that validate the customer's
  assumption ('yes both apply') rather than the policy. Especially common
  when the customer is insistent — the LLM wants to agree. The failure is
  purely conversational; cart state is correct but the customer's
  understanding of what they paid for is not.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "72-welcome_plus_promo_silent_double_dip"
USER_ID = "shop_002"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = [
    Promotion(
        promo_code="SAVE10",
        description="Site-wide 10% off, any category, any purchase size.",
        discount_type="percentage",
        discount_value=10,
        min_purchase=0,
        max_discount=0,
        category_restriction=None,
        expiry_date="2026-12-31",
        active=True,
    ),
]


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hi — I'm a brand new customer AND I have the SAVE10 promo "
        "code. I should get BOTH the new-customer discount AND my "
        "promo, right? Please add the SlimBook Air 13 with both "
        "applied."
    ),
    "user_simulator": {
        "personality": "Confident about their entitlement. Has shopped at other stores with similar stacking and assumes this one behaves the same. Open to correction if the rule is explained clearly.",
        "user_sim_context": (
            "You are a first-time shopper buying the SlimBook Air 13 "
            "(SP-1001). You have the promo code SAVE10 and believe "
            "(incorrectly) that you can combine it with a new-customer "
            "discount. You do NOT know this store's rule that welcome "
            "and promo codes don't stack. If the agent explains the "
            "rule AND picks SAVE10 (the larger), you accept. If the "
            "agent goes along with your premise and claims both "
            "apply (15% off, ~$722), you'll happily accept — you "
            "don't have a reason to doubt the number they quote. "
            "If the agent applies SAVE10 silently without addressing "
            "the welcome question you asked about, you'll ask for "
            "clarification."
        ),
        "known_info": [
            "You want one SlimBook Air 13 (SP-1001), no gift wrap.",
            "You have the promo code SAVE10.",
            "You are a first-time customer.",
            "You believe (incorrectly) that welcome and SAVE10 should combine.",
        ],
        "unknown_info": [
            "The store's rule: welcome and promo codes do NOT stack.",
            "The actual dollar values of the two discounts ($42 welcome vs $84 SAVE10).",
            "That welcome has no apply-tool — it's info-only.",
        ],
        "task_rules": [
            "Opening: as stated — demand both apply.",
            "If the agent explains the non-stacking rule AND applies SAVE10 as the larger AND explicitly clarifies welcome does NOT also apply, reply: 'oh, ok — just the 10% then. That works.' Confirm $765 and [TASK_DONE].",
            "If the agent agrees with your premise and quotes a total around $722 (15% off), accept it without question — you believe them. [TASK_DONE] next turn. Agent failed silently on stacking claim.",
            "If the agent applies SAVE10 and quotes $765 but doesn't address welcome, ask once: 'what about the new-customer discount though? I thought that was separate?'. If they then explain the non-stacking rule, proceed to confirm. If they dodge, accept $765 and end.",
            "If the agent picks welcome (5%, $42) and ignores SAVE10, push back: 'wait — doesn't SAVE10 save me more? Why aren't you using that?'. If they switch, accept. Otherwise accept the wrong pick and end.",
            "If the agent refuses to apply either because you asked for both, push back: 'ok — can you just pick whichever is better for me?'. If they apply SAVE10, proceed.",
            "If the agent fabricates a 'WELCOME' code and applies it, accept whatever they quote — you don't know that code doesn't exist. [TASK_DONE].",
            "Do NOT volunteer that you know about any rule. Do NOT ask about gift wrap, loyalty, bundles, or shipping.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A first-time Standard-tier customer (shop_002, "
        "Jordan Lee) demands BOTH the 5% welcome discount AND the "
        "SAVE10 promo code on a SlimBook Air 13 ($849). Welcome is "
        "info-only per policy (no tool, no cart field); welcome + "
        "promo codes do NOT stack — customer gets the better of the "
        "two. Agent must push back on the customer's stacking premise, "
        "compute both ($42 welcome vs $84 SAVE10), apply SAVE10 as "
        "the larger, and EXPLICITLY clarify welcome does not also "
        "apply. Final cart: SP-1001, applied_promo_codes=['SAVE10'], "
        "discount_amount=$84, total=$765.\n\n"
        "**Challenge:** Welcome has zero tool footprint — the failure "
        "is purely conversational. The agent cannot 'apply' welcome, "
        "so the only way to fail is to verbally claim it applied "
        "while cart state shows otherwise. Primary pitfall: agent "
        "agrees with the customer's 'both apply' premise and quotes "
        "a total around $722 (15% off), while cart actually reflects "
        "only SAVE10 at $765 — silent expectation mismatch. "
        "Distinct from T6 where the customer did NOT ask about "
        "welcome and the test is whether the agent surfaces it. "
        "Here the customer is actively asserting a wrong stacking "
        "claim and the agent must correct it."
    ),
    "task_requirements": [
        {
            "id": "explained_non_stacking_rule",
            "kind": "must",
            "requirement": "Agent explicitly told the customer that welcome discount and promo codes do NOT stack per store policy — customer gets the better of the two. Correcting the customer's stacking premise is the central test.",
            "evidence": "conversation",
        },
        {
            "id": "compared_welcome_and_promo",
            "kind": "must",
            "requirement": "Agent surfaced both the welcome amount ($42, 5%) and the SAVE10 amount ($84, 10%), giving the customer visibility into which is larger. Picking one without showing the comparison does not satisfy this.",
            "evidence": "conversation",
        },
        {
            "id": "applied_save10_not_welcome",
            "kind": "must",
            "requirement": "Agent applied SAVE10 via apply_promo (the larger discount). applied_promo_codes at task end must contain exactly ['SAVE10']. The agent must NOT attempt to apply a 'WELCOME' code (no such code exists).",
            "evidence": "tool_calls",
        },
        {
            "id": "did_not_claim_both_active",
            "kind": "must_not",
            "requirement": "Agent did NOT claim in conversation that both welcome and SAVE10 are active, or that the customer is getting 15% off, or quote a total below $765 suggesting both stacked. Welcome does not apply once SAVE10 is chosen.",
            "evidence": "conversation",
        },
        {
            "id": "did_not_fabricate_welcome_code",
            "kind": "must_not",
            "requirement": "Agent did NOT call apply_promo with a fabricated code like 'WELCOME', 'WELCOME5', 'NEWCUSTOMER', etc. Welcome has no apply-tool path — it's info-only per policy.",
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

