"""Task 47 — Progressive reveal aggregation across 6+ turns.

Pitfall category: pre-seeded cart with a laptop. Customer
reveals one new discount / context signal per turn — a promo
code, a gift context, their Platinum loyalty — across 4+ turns.
Agent must re-aggregate the cart after EACH reveal and
produce a final breakdown that correctly stacks all 3 signals.

Multi-turn structure (6+ turns):
  Pre-seeded: SP-1002 ProBook Laptop 13-inch $999 in cart.

  Turn 1 (user): 'can you finalize my cart?'
  Turn 2 (agent): confirms cart state
  Turn 3 (user): 'oh, I have a promo code SAVE10 — apply it'
  Turn 4 (agent): applies promo → -$99.90 (say $100)
  Turn 5 (user): 'and it's actually a gift for my dad — can
    you wrap it?'
  Turn 6 (agent): adds wrap +$5
  Turn 7 (user): 'oh, and I'm Platinum — do I get points?'
  Turn 8 (agent): should cite Platinum rate (3 pts/$) on
    post-discount total, confirm final breakdown.

Math:
  Subtotal: $999
  SAVE10 (10%): -$99 (integer)
  Post-promo subtotal: $900
  Gift wrap fee: $5
  Total: $905
  Points earned (Platinum, 3 pts/$): 3 × 905 = 2715 pts
    (Or per-category policy — verify with loyalty policy)

Pitfalls:
  (a) Agent's turn-8 summary omits the promo (didn't track).
  (b) Agent recomputes from scratch at turn 8 and gets wrong
      numbers because it forgot gift wrap was added.
  (c) Agent mentions points but uses wrong tier rate (1 or 2
      pts/$ instead of 3).
  (d) Agent applies Platinum rate to pre-discount amount
      ($999) instead of post-discount+wrap total ($905).
  (e) Agent adds wrap UNILATERALLY without confirming.
  (f) Agent computes points before adding them as a discount,
      or tries to apply points as a credit (not how the
      system works).

Scenario:
- Customer: shop_001 (Jordan Martinez, Platinum, returning,
  52k pts). Platinum = 3 pts/$ loyalty.
- Pre-seeded cart: SP-1002 ProBook Laptop 13-inch $999.
- Catalog: T1 BASE_PRODUCTS.
- Promotions: SAVE10 (10% any order).
- now=2026-06-12.

Dual-axis scoring:
- state_requirements: cart has SP-1002 qty=1 gift_wrap=True,
  subtotal $999, discount $99, gift_wrap_fee $5, total $905,
  applied_promo_codes=['SAVE10'].
- task_requirements: agent aggregated all 3 reveals
  correctly, final summary includes promo + wrap + points
  with accurate numbers.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 1:
  Agent cleanly applied SAVE10 (-$99), then added gift wrap
  (+$5) after the gift reveal. On the Platinum points ask at
  turn 4, agent responded with HYPOTHETICAL ranges: '1.5x
  ≈ 1350 points, 2x ≈ 1810 points', and explicitly said the
  exact earn-rate was unknown. The loyalty_points policy
  specifies Platinum = 3 pts/$ — but the agent treated it as
  unknown rather than consulting the policy via
  get_policy/read_policies or applying the stated rate. Also,
  the agent's final summary separated the loyalty discussion
  from the cart totals — no single response tied all four
  pieces (promo, wrap, total, points) together with specific
  numbers. 2/4 task_reqs passed. Composite FAIL. Reliable
  fail mode: gpt-5.1 treats policy-derived rates as
  uncertain when not explicitly provided in the conversation,
  even though the policy is accessible via tools. Combined
  with the multi-turn reveal structure, this produces a
  final breakdown that's incomplete — the customer would
  leave without knowing their actual points earned. Tests
  policy-tool consultation + multi-turn aggregation.
"""

from __future__ import annotations

from domains.shopping_assistant.schemas import (
    Cart,
    CartItem,
    Promotion,
    SAEnvironmentData,
)
from domains.shopping_assistant.task_registry._builders import (
    build_customer_record,
)
from domains.shopping_assistant.task_registry.task_1_recommend_college_laptop import (
    PRODUCTS,
)

TASK_ID = "47-progressive_reveal_aggregation"
USER_ID = "shop_001"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = [
    Promotion(
        promo_code="SAVE10",
        description="10% off any order.",
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
        "Can you finalize my cart? I'm ready to check out."
    ),
    "user_simulator": {
        "personality": "Absent-minded — remembers things gradually, one per turn.",
        "user_sim_context": (
            "Your cart has a ProBook Laptop. You want to finalize. "
            "Across 3 follow-up turns you'll reveal (one at a time, "
            "not volunteered upfront): (1) you have promo code "
            "SAVE10, (2) the laptop is a gift for your dad — please "
            "wrap it, (3) you're a Platinum-tier loyalty member "
            "and want to know about points. You expect the agent "
            "to re-aggregate the cart after each reveal and give "
            "you an accurate final breakdown that cites the promo "
            "discount, wrap fee, AND points earned at the correct "
            "Platinum tier rate (3 pts/$ per policy)."
        ),
        "known_info": [
            "You have a ProBook in your cart.",
            "You have a SAVE10 promo code.",
            "It's a gift for your dad.",
            "You're a Platinum-tier customer (52k existing points).",
        ],
        "unknown_info": [
            "Specific prices / math.",
            "Whether Platinum points are 2 or 3 pts/$ (you trust agent to know).",
        ],
        "task_rules": [
            "Opening: 'can you finalize my cart? I'm ready to check out.'",
            "Turn 2: after agent confirms cart, reveal promo: 'oh wait — I have a promo code, SAVE10. Can you apply it?'. Do NOT reveal gift or Platinum yet.",
            "Turn 3: after agent applies promo and gives updated total, reveal gift: 'and actually — it's a gift for my dad. Can you wrap it?'. Do NOT reveal Platinum yet.",
            "If agent wraps unilaterally without confirming (e.g. adds wrap without asking), that's on the gift context cue so it's fine. If agent ASKS confirmation first, also fine.",
            "Turn 4: after agent confirms wrap added, reveal loyalty: 'oh, and I'm Platinum — do I earn points on this order?'.",
            "Turn 5: agent should now give a final breakdown citing: subtotal, SAVE10 discount (-$99), wrap fee (+$5), total ($905), and Platinum points earned (3 pts/$ × $905 ≈ 2700-2715 pts, or comparable formula explicitly stated).",
            "If the final breakdown includes ALL FOUR pieces (promo discount with amount, wrap fee with amount, final total, Platinum points with specific number), reply: 'perfect, thanks' and next turn [TASK_DONE].",
            "If the final breakdown OMITS one of the four pieces (e.g. doesn't mention promo was applied, or doesn't mention points), accept and end. Agent failed — missed aggregating the full picture.",
            "If agent uses WRONG Platinum rate (e.g. says 1 or 2 pts/$), accept and end. Failed — tier rate error.",
            "If agent applies Platinum rate to PRE-discount amount ($999) instead of post-discount+wrap ($905), accept and end. Failed — applied rate to wrong base.",
            "If agent uses WRONG discount amount (e.g. says discount is $100 or $99.90), be lenient if within $1 of $99 (integer division of 999*0.10). If off by $10+, push back once: 'that math doesn't look right'.",
            "Do NOT volunteer the tier rate, the discount math, or the wrap fee amount. Do NOT reveal more than one signal per turn.",
            "Keep replies short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Platinum customer (shop_001) has a "
        "pre-seeded cart with SP-1002 ProBook Laptop 13-inch "
        "($999). They ask to finalize, then reveal over 3 turns: "
        "(1) promo SAVE10 (-$99), (2) it's a gift → wrap (+$5), "
        "(3) Platinum tier → points earned at 3 pts/$ on "
        "post-discount+wrap total ($905 × 3 = 2715 pts). Final "
        "breakdown must correctly aggregate all three reveals.\n\n"
        "**Challenge:** Multi-turn progressive aggregation over "
        "5+ turns. Pitfall: agent's turn-8 summary omits promo "
        "or wrap; applies Platinum rate to pre-discount total "
        "instead of post-discount+wrap; uses wrong tier rate; "
        "loses track of what was added across 3 mutations. "
        "Correct: re-aggregate after each reveal, final summary "
        "cites all 3 signals with correct math. Tests "
        "conversational state retention + correct policy math "
        "across 5+ turns. Distinct from T18 (platinum + shipping "
        "on single ask) — T47 is reveal-paced with 3 separate "
        "aggregation steps."
    ),
    "task_requirements": [
        {
            "id": "applied_save10",
            "kind": "must",
            "requirement": "Agent called apply_promo for SAVE10 after the customer revealed the code at turn 2. The applied_promo_codes list must contain SAVE10 at the end.",
            "evidence": "tool_calls",
        },
        {
            "id": "added_wrap_on_gift_cue",
            "kind": "must",
            "requirement": "Agent called update_cart_item (or equivalent) to set gift_wrap=True for the ProBook after the customer revealed it's a gift. Final cart_item.gift_wrap must be True.",
            "evidence": "tool_calls",
        },
        {
            "id": "cited_platinum_points_correctly",
            "kind": "must",
            "requirement": "When the customer asked about points, agent cited the Platinum tier rate of 3 points per $1 AND applied it to the post-discount+wrap total ($905), arriving at ~2715 points. Using the wrong tier rate (1 or 2 pts/$) fails. Applying the rate to pre-discount $999 fails. Omitting points entirely fails.",
            "evidence": "conversation",
        },
        {
            "id": "final_breakdown_complete",
            "kind": "must",
            "requirement": "Agent's final summary (after all 3 reveals) explicitly includes ALL four items with specific numbers: (1) promo discount amount (~$99), (2) gift wrap fee ($5), (3) final total ($905), (4) Platinum points earned (~2715). Missing any of the four fails.",
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
            "record_key": "CI-A1",
            "field": "gift_wrap",
            "expected_value": True,
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
            "field": "discount_amount",
            "expected_value": 99,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "gift_wrap_fee",
            "expected_value": 5,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 905,
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1"],
        subtotal=999,
        discount_amount=0,
        gift_wrap_fee=0,
        total=999,
        applied_promo_codes=[],
    )
    laptop = CartItem(
        cart_item_id="CI-A1",
        customer_id=USER_ID,
        product_id="SP-1002",
        quantity=1,
        gift_wrap=False,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[laptop],
        promotions=PROMOTIONS,
    )

