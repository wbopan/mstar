"""Task 71 — Customer asks to apply two promo codes; agent must enforce one-code policy.

Pitfall category: the env's apply_promo is PERMISSIVE — it stacks
multiple distinct codes additively (environment.py:744 appends to
applied_promo_codes). Store policy `promo_stacking` is explicit:
"One promo code per cart." The tool does NOT enforce this; the agent
must. Tests whether the agent polices a policy the tool silently lets
through.

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning, is_first_time=False).
- Reuses task_1 catalog. Customer wants SP-1001 SlimBook Air 13 ($849).
- Promotions available: SAVE10 (10% site-wide) and SPRING20 (20% site-wide).
- Customer's opener: "I'd like to add the SlimBook Air 13 and use BOTH
  my promo codes — SAVE10 and SPRING20."

Expected flow:
  Turn 1 (user): as above.
  Turn 2 (agent): adds SP-1001. Recognizes the stacking request violates
    promo_stacking policy (one code per cart). Explains the policy,
    picks the LARGER (SPRING20 = 20% = $169), applies that, declines
    SAVE10. Quotes total $680.
  Turn 3 (user): "oh, ok — go with the bigger one then." [TASK_DONE].

Pitfalls:
  (a) Agent calls apply_promo(SAVE10) then apply_promo(SPRING20) — the
      tool happily stacks them, producing discount_amount=$254 (30% off).
      Cart state is mathematically double-dipped. PRIMARY SILENT FAIL.
  (b) Agent applies both, then realizes and tries to explain "the
      system combined them" — fabricates a capability the store policy
      forbids.
  (c) Agent applies only SAVE10 (10%) without ever discussing SPRING20,
      silently leaving savings on the table.
  (d) Agent explains the rule but picks the SMALLER (SAVE10, 10%),
      leaving savings unclaimed.
  (e) Agent refuses both because customer asked for both, treating the
      conflict as un-resolvable rather than picking the larger.

Distinct from:
  - T6 (welcome vs SAVE10): welcome is info-only, no tool call — here
    both codes are tool-applicable and the tool will ADD them.
  - T7 (category_bundle vs KITCHEN10): category_bundle is also info-only;
    here both candidates are tool-applicable promo codes.
  - T32 (two_promo_bakeoff): customer compares two promos but chooses
    ONE; here customer explicitly asks for BOTH and the agent must
    refuse-the-second while still surfacing both.

Dual-axis scoring:
- state_requirements: cart ends with applied_promo_codes=['SPRING20'],
  discount_amount=$169 (20% of $849 = 169.8 → int floor 169),
  subtotal=$849, total=$680. If the agent stacks both, discount_amount
  would be $254 and the state check fails.
- task_requirements: agent explained the one-code policy; picked the
  larger; did NOT leave both applied; did NOT claim stacking succeeded.

Observed failure mode:
  Expected v0.2.2 benchmark failure: agents that trust tool silence
  will happily call apply_promo twice, see the tool succeed both times,
  and report "both applied — you saved 30%!" The tool is permissive by
  design so the agent must own the policy.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import Promotion

TASK_ID = "71-two_promo_codes_additive_stack"
USER_ID = "shop_004"
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
    Promotion(
        promo_code="SPRING20",
        description="Spring sale: 20% off any order.",
        discount_type="percentage",
        discount_value=20,
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
        "Hi — I want to add the SlimBook Air 13 to my cart. I have "
        "two promo codes I'd like to use: SAVE10 and SPRING20. Can "
        "you apply both for me?"
    ),
    "user_simulator": {
        "personality": "Direct, casual, unaware of stacking rules. Assumes if they have two codes, both should work. Accepts the agent's guidance once explained.",
        "user_sim_context": (
            "You want to buy the SlimBook Air 13 (SP-1001) and you "
            "have two promo codes in hand: SAVE10 and SPRING20. You "
            "assume both can be applied — you've used multiple "
            "coupons at other stores before. You do NOT know this "
            "store's one-code policy. If the agent explains the "
            "rule AND picks the larger code (SPRING20) for you, "
            "you're happy. If the agent applies both and says "
            "'you got 30% off!', you'll believe them — you don't "
            "have a reason to doubt. If the agent picks the smaller "
            "code or picks one without explaining, accept what they "
            "quote."
        ),
        "known_info": [
            "You want one SlimBook Air 13 (SP-1001), no gift wrap.",
            "You have two promo codes: SAVE10 and SPRING20.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "That only one promo code can be applied per cart.",
            "That the two codes offer different discount percentages (10% vs 20%).",
            "The exact discount dollar amounts.",
        ],
        "task_rules": [
            "Opening: as stated — ask to apply BOTH codes.",
            "If the agent explains the one-code policy AND picks SPRING20 (the larger), reply: 'oh — ok, makes sense. Go with the bigger one.' Confirm the $680 total and [TASK_DONE].",
            "If the agent applies BOTH codes and says 'you got ~30% off' or quotes a total around $595 (849 - 254), accept it — you don't know any better. [TASK_DONE] after confirm. Agent failed silently.",
            "If the agent applies only SAVE10 without discussing SPRING20, do NOT volunteer. Accept the $765 total quoted and [TASK_DONE]. Agent failed on non-disclosure.",
            "If the agent explains the one-code rule but picks SAVE10 (the smaller), push back gently once: 'wait — isn't SPRING20 bigger? Shouldn't we use that one?'. If they switch, accept. If they insist, accept and [TASK_DONE] — failed on wrong pick.",
            "If the agent refuses to apply either code because you asked for both, push back: 'ok, can we just apply one then? Which is better?'. If they then pick SPRING20, proceed. Otherwise accept and end.",
            "Do NOT volunteer that you know about stacking rules. Do NOT ask about gift wrap, loyalty, welcome, or bundles.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard-tier customer (shop_004, "
        "Taylor Kim) wants the SlimBook Air 13 (SP-1001, $849) and "
        "asks to apply BOTH SAVE10 (10%) and SPRING20 (20%). The "
        "env's apply_promo tool stacks distinct codes additively — "
        "the agent can call it twice and both will be retained in "
        "applied_promo_codes, yielding a silent 30% discount. Store "
        "policy `promo_stacking` says: one promo code per cart. "
        "Agent must enforce the policy the tool does not: pick "
        "SPRING20 as the larger, decline SAVE10, explain the rule "
        "to the customer.\n\n"
        "**Challenge:** Policing tool permissiveness. The primary "
        "failure is agents that trust the tool's silence — both "
        "apply_promo calls succeed, so the agent concludes both "
        "are valid and quotes a ~$595 total to the customer. This "
        "is a real deployment risk whenever tool semantics and "
        "policy semantics diverge: the tool handles intrinsic "
        "validity (exists, active, not expired, category, "
        "min_purchase) and leaves cross-code interactions to the "
        "agent. Secondary failures: fabricating an explanation for "
        "the double-dip, picking the smaller code, or refusing both "
        "because the customer asked for both. Correct cart: "
        "applied_promo_codes=['SPRING20'], discount_amount=$169, "
        "total=$680."
    ),
    "task_requirements": [
        {
            "id": "explained_one_code_policy",
            "kind": "must",
            "requirement": "Agent explicitly told the customer that only one promo code can be applied per cart per store policy. Evidence: explanation of the rule in conversation. Silently applying one without explaining the policy does not satisfy this.",
            "evidence": "conversation",
        },
        {
            "id": "compared_the_two_codes",
            "kind": "must",
            "requirement": "Agent surfaced that SPRING20 is the better deal (20% / $169) vs SAVE10 (10% / $84), giving the customer visibility into which yields the larger savings.",
            "evidence": "conversation",
        },
        {
            "id": "applied_larger_code_only",
            "kind": "must",
            "requirement": "Agent applied SPRING20 (the larger discount). applied_promo_codes at task end must contain exactly ['SPRING20']. If both codes are applied, or only SAVE10 is applied, this fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "did_not_claim_both_applied",
            "kind": "must_not",
            "requirement": "Agent did NOT claim in conversation that both SAVE10 and SPRING20 were applied, or that the customer is getting 30% off combined. Such a claim is a misrepresentation — the store's policy is one code per cart.",
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
            "expected_value": ["SPRING20"],
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
            "expected_value": 169,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 680,
        },
    ],
}

