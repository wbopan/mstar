"""Task 39 — Promo upgrade opportunity detection.

Pitfall category: the customer has a promo applied and asks to
add an item. Adding the item makes the cart newly eligible for a
BETTER promo they also have available. Agent must detect the
upgrade opportunity post-add and recommend the swap — not just
confirm the add silently.

Scenario: shop_004's pre-seeded cart has SP-3003 ErgoDesk
Standing Desk ($449, home_office) with SAVE10 applied (10% off,
any category, min $100, discount $44). Customer asks to add
SP-3004 ErgoDesk Mesh Chair ($329, home_office). New cart would
be $778 home_office subtotal.

Available promos in env:
  SAVE10: 10% off, min $100, any category, no max → $77 on $778.
  OFFICE20: 20% off, min $500, home_office only, max $150 →
    capped $150 on $778.

After the add, the agent must:
  1. Perform the add.
  2. Notice the cart now meets OFFICE20's $500 min AND stays
     fully home_office, so OFFICE20 now qualifies.
  3. Compare: SAVE10 gives $77 at new cart size; OFFICE20 gives
     $150 (capped). OFFICE20 is $73 better.
  4. Cite promo_stacking: only one code at a time.
  5. Recommend removing SAVE10 and applying OFFICE20.
  6. Execute after consent.

Customer never mentions the promos — they forgot about them.
Agent must proactively detect the opportunity from cart state.

Pitfalls:
  (a) Agent adds the chair, confirms cart update with SAVE10
      still applied, never notices OFFICE20 now qualifies.
  (b) Agent validates OFFICE20 in its head but doesn't bring it
      up because the customer didn't ask.
  (c) Agent mentions OFFICE20 but doesn't compare savings
      explicitly ($77 vs $150 / $73 more).
  (d) Agent applies OFFICE20 on top of SAVE10 (stacks both —
      env allows this mechanically but policy forbids it).
  (e) Agent recommends swap but doesn't actually execute
      remove_promo + apply_promo.

Correct: after add_to_cart, agent calls validate_promo (or
knows from env state) that OFFICE20 now qualifies, computes
both discounts ($77 vs $150), cites one-code rule, recommends
swap, and after customer consents: remove_promo(SAVE10) +
apply_promo(OFFICE20). Final cart: $778 subtotal, $150 discount,
$628 total, applied_promo_codes=['OFFICE20'].

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, returning).
- Catalog: T1 BASE_PRODUCTS.
- Promotions: SAVE10 + OFFICE20 (OFFICE20 max_discount raised to
  $150 so it wins clearly at $778 cart size).
- Pre-seeded cart: CI-0001 SP-3003 ($449), SAVE10 applied,
  discount $44, total $405.
- now=2026-06-12.

Math:
  Before add: $449 subtotal, SAVE10 $44 discount, $405 total.
  After add: $778 subtotal.
    With SAVE10: $77 discount, $701 total.
    With OFFICE20: $155 → cap $150 discount, $628 total.
  Correct final: $778 subtotal, OFFICE20 applied, $150 discount,
  $628 total.

Dual-axis scoring:
- state_requirements: both cart items present (SP-3003 + SP-3004),
  subtotal $778, OFFICE20 applied only, discount $150, total $628.
- task_requirements: agent added chair, detected OFFICE20 upgrade
  opportunity, computed both discounts with specifics, cited
  one-code rule, executed the swap (remove_promo + apply_promo).

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 1:
  Agent added the chair (correct) and, when asked for a cart
  summary, showed the post-add state with SAVE10 still applied
  ($77 discount, $701 total). Never called validate_promo on
  OFFICE20 despite it now qualifying. Never suggested an
  upgrade. Offered only a passive 'I can look for other promos
  if you want'. 4/5 task_reqs failed. Composite FAIL. Reliable
  fail mode: gpt-5.1 does not proactively re-evaluate promo
  eligibility after a cart mutation. It treats the existing
  applied_promo_codes as settled and does not re-run discount
  math against other available promos unless the customer
  asks. The $73 opportunity ($150 - $77) is invisible to the
  agent because it never probes. Distinct from T32
  (bake-off when customer presents both codes) and T38
  (side-effect-blindness on promo auto-drop) — T39 tests
  PROACTIVE PROMO SHOPPING, which gpt-5.1 does not do on cart
  growth.
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

TASK_ID = "39-promo_upgrade_opportunity"
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
        description="20% off home office orders over $500, max $150 discount.",
        discount_type="percentage",
        discount_value=20,
        min_purchase=500,
        max_discount=150,
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
        "Add the ErgoDesk Mesh Chair to my cart please, I want it "
        "alongside the desk I already have in there."
    ),
    "user_simulator": {
        "personality": "Casual, transactional. Doesn't think about promos unless reminded.",
        "user_sim_context": (
            "Your cart currently has an ErgoDesk Standing Desk with the "
            "SAVE10 promo applied (you don't remember applying it or "
            "its terms). You want to add an ErgoDesk Mesh Chair. You "
            "are NOT aware that OFFICE20 exists or that it would give "
            "a bigger discount once both items are in the cart. You "
            "expect the agent to handle optimization. The test is "
            "whether the agent, after adding the chair, detects that "
            "OFFICE20 now qualifies and gives a better discount, "
            "recommends the swap, and executes it."
        ),
        "known_info": [
            "Your cart already has an ErgoDesk Standing Desk.",
            "You want to add the ErgoDesk Mesh Chair.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The SAVE10 promo is currently applied.",
            "The OFFICE20 promo exists and would give a better discount after the chair is added.",
            "The math: SAVE10 at new cart = $77; OFFICE20 = $150; difference = $73.",
            "The one-code-per-cart rule.",
        ],
        "task_rules": [
            "Opening: the one-line add request above. Do NOT mention promos, totals, or discounts.",
            "If the agent adds the chair AND proactively surfaces the OFFICE20 upgrade opportunity with specific numbers (e.g. 'you currently have SAVE10 saving $77; OFFICE20 would save $150 on this $778 home_office cart — $73 more — and only one code applies, so want me to swap?'), reply: 'yes please, switch to OFFICE20'. Then end with [TASK_DONE] after agent confirms.",
            "If the agent adds the chair but only mentions OFFICE20 vaguely ('there's a better promo') without specific numbers, push back ONCE: 'how much better?'. If agent then provides specifics, accept and let them swap. If no specifics, accept and end — agent failed on math.",
            "If the agent adds the chair and makes no mention of OFFICE20 at all, accept the cart confirmation and end. Agent has failed.",
            "If the agent adds the chair AND tries to apply OFFICE20 on top of SAVE10 (stacking both), refuse: 'wait, can I actually use both?'. If the agent acknowledges only one code allowed and removes SAVE10, proceed. If the agent leaves both applied, accept and end — agent failed on stacking.",
            "If the agent does NOT apply OFFICE20 even after recommending the swap and getting your consent, accept and end. Agent failed on execution.",
            "Do NOT volunteer 'check for promos' — the customer doesn't think about promos. Do NOT ask about gift wrap, loyalty, shipping.",
            "If the agent seems confused or misses the opportunity, do not help — the test is their proactive detection.",
            "Keep replies short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) has a "
        "pre-seeded cart with SP-3003 ErgoDesk Standing Desk ($449) "
        "and SAVE10 applied ($44 off, $405 total). Customer asks to "
        "add SP-3004 ErgoDesk Mesh Chair ($329). After the add, cart "
        "is $778 home_office. The env has a second promo OFFICE20 "
        "(20% off home_office, min $500, max $150 discount) that NOW "
        "qualifies. OFFICE20 = $150 discount; SAVE10 at new size = "
        "$77. OFFICE20 beats by $73.\n\n"
        "**Challenge:** Proactive promo-upgrade detection. Pitfall: "
        "agent adds the chair and silently confirms the cart (SAVE10 "
        "still applied, $77 discount, $701 total) — missing that "
        "OFFICE20 now gives $73 more. Correct: after add, run "
        "validate_promo on OFFICE20, compare discounts with specific "
        "numbers, cite one-code rule, execute remove_promo(SAVE10) + "
        "apply_promo(OFFICE20) after consent. Tests attention to "
        "post-mutation promo eligibility + comparative math + tool "
        "chaining. Distinct from T32 (two promos both available from "
        "customer on initial ask) and T38 (silent promo AUTO-DROP); "
        "T39 tests silent promo AUTO-UPGRADE-OPPORTUNITY."
    ),
    "task_requirements": [
        {
            "id": "added_mesh_chair",
            "kind": "must",
            "requirement": "Agent called add_to_cart for SP-3004 ErgoDesk Mesh Chair with quantity=1, gift_wrap=False.",
            "evidence": "tool_calls",
        },
        {
            "id": "detected_office20_upgrade",
            "kind": "must",
            "requirement": "Agent proactively surfaced that OFFICE20 now qualifies on the enlarged cart. Must be done WITHOUT the customer asking about promos or alternate discounts. Silent completion fails.",
            "evidence": "conversation",
        },
        {
            "id": "compared_specific_discounts",
            "kind": "must",
            "requirement": "Agent verbalized specific discount amounts for both codes at the new cart size — SAVE10 ~$77 AND OFFICE20 $150 (or equivalent numbers with stated savings delta ~$73). Generic 'OFFICE20 is better' without numbers fails.",
            "evidence": "conversation",
        },
        {
            "id": "executed_promo_swap",
            "kind": "must",
            "requirement": "Agent called remove_promo for SAVE10 AND apply_promo for OFFICE20 (in either order) after customer consent. Merely recommending the swap without executing fails. Leaving both codes applied fails.",
            "evidence": "tool_calls",
        },
        {
            "id": "did_not_stack_codes",
            "kind": "must_not",
            "requirement": "Agent must NOT leave both SAVE10 and OFFICE20 applied simultaneously in the final cart. Final applied_promo_codes must equal exactly ['OFFICE20'].",
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
                "cart_item_id": "CI-0002",
                "customer_id": USER_ID,
                "product_id": "SP-3004",
            },
            "expected_fields": {"quantity": 1, "gift_wrap": False},
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "item_ids",
            "expected_value": ["CI-0001", "CI-0002"],
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 778,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "discount_amount",
            "expected_value": 150,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 628,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "applied_promo_codes",
            "expected_value": ["OFFICE20"],
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-0001"],
        subtotal=449,
        discount_amount=44,
        gift_wrap_fee=0,
        total=405,
        applied_promo_codes=["SAVE10"],
    )
    desk = CartItem(
        cart_item_id="CI-0001",
        customer_id=USER_ID,
        product_id="SP-3003",
        quantity=1,
        gift_wrap=False,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[desk],
        promotions=PROMOTIONS,
    )

