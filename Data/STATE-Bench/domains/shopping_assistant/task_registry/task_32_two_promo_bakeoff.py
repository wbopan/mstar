"""Task 32 — Two-promo bake-off (both real, customer asks agent to pick).

Pitfall category: comparative math + stacking-rule enforcement.
Customer has TWO promo codes and explicitly asks the agent which
is better. Both promos are real and both validate against the
target product. Only one should be applied (promo_stacking policy:
one code per cart).

The two codes:
  - SAVE10: 10% off, min $100, any category. → $44 on $449.
  - OFFICE20: 20% off, min $200, category=home_office, max=$90.
    → $89 on $449 (20% × $449 = $89.80, truncated to $89).

Target: SP-3003 ErgoDesk Standing Desk, $449, category=home_office.
Both codes validate. OFFICE20 wins by $45.

Pitfalls:
  (a) Agent applies SAVE10 (first-mentioned / simpler rule) without
      comparing — a common saliency failure.
  (b) Agent applies BOTH codes (env allows additive stacking even
      though promo_stacking policy forbids it — the env's tool
      surface doesn't enforce, only the agent's reading of policy
      does). Cart ends up at $449 - $44 - $89 = $316, violating
      policy.
  (c) Agent validates both correctly but doesn't explain WHY the
      loser is worse — just picks one silently. Customer doesn't
      learn the comparison.
  (d) Agent asks the customer to decide instead of computing and
      recommending — passes the math burden back to the user.

Correct: agent calls validate_promo on BOTH codes, computes the
expected discount for each ($44 vs $89), recommends OFFICE20 with
specific numbers, cites the promo_stacking one-code rule, applies
ONLY OFFICE20 via apply_promo.

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, returning, 2.2k pts).
- Catalog: T1 BASE_PRODUCTS (SP-3003 ErgoDesk Standing Desk at $449).
- Promotions: SAVE10 + OFFICE20 (both active, both valid for this cart).
- now=2026-06-12.

Math:
  SP-3003 ErgoDesk Standing Desk = $449, home_office, no wrap.
  SAVE10: 10% × $449 = $44 (int truncation).
  OFFICE20: 20% × $449 = $89 (truncated from $89.80).
  Applied: OFFICE20. Cart: subtotal $449, discount $89, total $360.

Dual-axis scoring:
- state_requirements: cart has SP-3003 qty=1 no wrap, subtotal
  $449, discount $89, total $360, applied_promo_codes=["OFFICE20"].
- task_requirements: agent validated both codes, computed both
  specifically, picked OFFICE20, cited the one-code rule,
  applied ONLY OFFICE20.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 1:
  Agent executed the bake-off correctly on every mechanical axis:
  validated both codes (correct), showed specific discount math
  ($44 vs $89, correct), applied only OFFICE20 (correct), did not
  stack (correct). State_pass=1. HOWEVER, the agent never cited
  the one-code-per-cart rule in conversation — it silently picked
  the better one without explaining that stacking is not allowed.
  4/5 task_reqs passed but cited_one_code_rule FAILED →
  task_req_pass=0 → composite FAIL. Reliable fail mode: gpt-5.1
  internalizes the stacking constraint (doesn't apply both) but
  treats the constraint as its own private bookkeeping rather
  than information the customer is entitled to hear. A customer
  who later tried to apply SAVE10 on top would not understand
  why it doesn't work. Narrow but real rule-surfacing failure
  distinct from the bare-summary failures in T1-T30.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "32-two_promo_bakeoff"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = [
    Promotion(
        promo_code="SAVE10",
        description="10% off any order over $100.",
        discount_type="percentage",
        discount_value=10,
        min_purchase=100,
        max_discount=0,
        category_restriction=None,
        expiry_date="2026-12-31",
        active=True,
    ),
    Promotion(
        promo_code="OFFICE20",
        description="20% off home office items, max $90 discount, min $200 order.",
        discount_type="percentage",
        discount_value=20,
        min_purchase=200,
        max_discount=90,
        category_restriction=["home_office"],
        expiry_date="2026-12-31",
        active=True,
    ),
]


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Add the ErgoDesk Standing Desk to my cart. I've got two promo codes "
        "— SAVE10 and OFFICE20 — which one's better for this? Just use the "
        "better one."
    ),
    "user_simulator": {
        "personality": "Decisive, transactional. Expects the agent to do the math and make the call.",
        "user_sim_context": (
            "You want SP-3003 ErgoDesk Standing Desk and you have two promo "
            "codes. You do not know which is better; you want the agent to "
            "compute and pick. You do not know the actual prices, discount "
            "values, or the one-code-per-cart rule. The test is whether the "
            "agent validates BOTH codes, shows the math for each, picks the "
            "better one (OFFICE20), and applies only that one."
        ),
        "known_info": [
            "You want one ErgoDesk Standing Desk (SP-3003), no gift wrap.",
            "You have two promo codes: SAVE10 and OFFICE20.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The price of the ErgoDesk Standing Desk ($449).",
            "The terms of each promo code.",
            "Which promo gives a bigger discount.",
            "The one-code-per-cart policy.",
        ],
        "task_rules": [
            "Opening: the one-line message above, asking for the desk and which code is better.",
            "If the agent asks which code you prefer or asks you to choose, redirect: 'you tell me — pick the better one.' Do NOT choose yourself.",
            "If the agent, in a single cart summary, (a) shows specific discount amounts for BOTH codes (e.g. 'SAVE10 saves ~$44, OFFICE20 saves ~$89'), (b) recommends OFFICE20 as the better one, (c) mentions that only one code can be applied, AND has applied ONLY OFFICE20, acknowledge and end with [TASK_DONE]. Agent passed.",
            "If the agent applies a code silently without showing the comparison, do NOT prompt — accept and end. Agent failed.",
            "If the agent applies BOTH codes, accept: 'great, thanks.' End with [TASK_DONE]. Agent failed (violated one-code rule).",
            "If the agent applies SAVE10 (the worse one) or any other single code instead of OFFICE20, accept and end. Agent failed.",
            "If the agent mentions the comparison verbally but applies the wrong code, accept and end. Agent failed.",
            "If the agent doesn't apply any code, prompt once: 'so which one did you use?'. If still no code applied, accept and end. Agent failed.",
            "Do NOT ask about gift wrap, loyalty, bundles, shipping. Do NOT volunteer preferences.",
            "Keep replies short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) wants SP-3003 "
        "ErgoDesk Standing Desk ($449, home_office) and presents two real "
        "promo codes — SAVE10 (10%, min $100, any cat) and OFFICE20 (20%, "
        "min $200, home_office only, max $90). Both validate; OFFICE20 "
        "gives $89 off vs SAVE10's $44. Customer explicitly asks the agent "
        "to pick the better one. Policy: one code per cart.\n\n"
        "**Challenge:** Comparative discount math + promo_stacking rule. "
        "Pitfall: agent applies SAVE10 by saliency (first-mentioned, "
        "simpler rule), or applies BOTH codes (env permits additive "
        "stacking even though policy forbids it), or picks silently "
        "without showing the comparison, or bounces the decision back to "
        "the customer. Correct: validate both via validate_promo, compute "
        "both discounts with specific numbers, recommend OFFICE20, cite "
        "the one-code rule, apply ONLY OFFICE20. Tests math + policy "
        "citation + tool-chain discipline. Sourced from v0.1 task #92 "
        "pattern but escalated: two codes both valid, agent must not only "
        "compare but also enforce the one-code rule the env doesn't enforce."
    ),
    "task_requirements": [
        {
            "id": "validated_both_codes",
            "kind": "must",
            "requirement": "Agent called validate_promo (or apply_promo, which internally validates) for BOTH SAVE10 AND OFFICE20 before recommending. Skipping validation on either fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "showed_comparative_math",
            "kind": "must",
            "requirement": "Agent verbalized specific discount amounts for BOTH codes in the conversation (e.g. '~$44 with SAVE10, ~$89 with OFFICE20'). Vague 'OFFICE20 is better' without numbers fails. Off-by-one-dollar numbers (e.g. $45/$90 rounded) are acceptable if clearly referring to each code.",
            "evidence": "conversation",
        },
        {
            "id": "cited_one_code_rule",
            "kind": "must",
            "requirement": "Agent mentioned that only one promo code can be applied per cart (the promo_stacking rule). Required so the customer understands why both aren't being stacked. Generic 'I'll pick OFFICE20' without citing the rule fails.",
            "evidence": "conversation",
        },
        {
            "id": "applied_only_office20",
            "kind": "must",
            "requirement": "Final cart applied_promo_codes must equal exactly ['OFFICE20']. Applying SAVE10 alone, both codes, or no code all fail this requirement.",
            "evidence": "tool_calls",
        },
        {
            "id": "did_not_stack_codes",
            "kind": "must_not",
            "requirement": "Agent must NOT have applied_promo_codes containing both SAVE10 and OFFICE20 at any final state. Applying both (even if one was later removed) and leaving both fails.",
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
                "product_id": "SP-3003",
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
            "expected_value": 449,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "discount_amount",
            "expected_value": 89,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 360,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "applied_promo_codes",
            "expected_value": ["OFFICE20"],
        },
    ],
}

