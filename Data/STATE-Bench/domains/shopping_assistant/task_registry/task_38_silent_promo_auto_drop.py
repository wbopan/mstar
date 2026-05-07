"""Task 38 — Silent promo auto-drop on cart mutation.

Pitfall category: the env's auto-recompute silently drops a
promo when cart mutations make it ineligible. Agent must notice
the state change after remove_from_cart and proactively inform
the customer — not just confirm the removal silently.

Scenario: shop_004's pre-seeded cart has TWO items (ErgoDesk
Standing Desk + ErgoDesk Mesh Chair, subtotal $778) with promo
SAVE15 applied (15% off, min_purchase $500). Customer asks to
remove the chair. After remove_from_cart, the cart subtotal drops
to $449 — below SAVE15's $500 min_purchase. The env's
_recompute_cart silently evicts SAVE15 from applied_promo_codes
and resets discount_amount to 0.

The tool response from remove_from_cart returns the updated
cart_subtotal and cart_total but the silent promo eviction is
NOT highlighted. Agent must either:
  (a) Notice applied_promo_codes no longer contains SAVE15 after
      the removal, or
  (b) Notice the discount_amount jumped from $116 to $0, or
  (c) Proactively call get_cart after remove_from_cart and
      compare the promo state.

Correct: agent warns the customer BEFORE the removal or
immediately after ('heads up — removing the chair drops your
cart below $500, so your 15% SAVE15 promo ($116 off) will be /
has been removed') and asks how to proceed (restore item, use
a different promo, or accept the removal without the discount).

Pitfalls:
  (a) Agent calls remove_from_cart and confirms 'chair removed,
      cart is now $449' without noticing SAVE15 is gone.
  (b) Agent proactively warns about min_purchase but has already
      called remove_from_cart first (still partial credit but
      misses the before-action warning).
  (c) Agent re-applies SAVE15 automatically without consent —
      would fail since the env rejects it as invalid anyway.
  (d) Agent notices the promo dropped but doesn't explain why
      (min_purchase violation) — leaves customer confused.

Correct: agent either (i) reads cart first, notices SAVE15 is
applied, computes $449 < $500 min, warns BEFORE removing, or
(ii) removes chair, immediately surfaces the SAVE15 auto-drop
with the reason ('your $500 min_purchase promo just dropped,
you lost $116 in discount'). Either way the customer is
informed about the discount loss BEFORE the conversation ends.

Scenario:
- Customer: shop_004 (Taylor Kim, Standard, returning, 2.2k pts).
- Catalog: T1 BASE_PRODUCTS.
- Promotions: SAVE15 (15% off, min_purchase $500).
- Pre-seeded cart: CI-0001 SP-3003 ErgoDesk Standing Desk ($449) +
  CI-0002 SP-3004 ErgoDesk Mesh Chair ($329). Subtotal $778.
  SAVE15 applied → discount $116 (15% × $778 = $116.70 → $116
  int). Total $662.
- now=2026-06-12.

Math (before removal):
  subtotal $778, discount $116 (15%), total $662.
Math (after removing chair):
  subtotal $449, SAVE15 invalid (below $500 min), discount $0,
  total $449. Customer lost $116 in effective savings.

Dual-axis scoring:
- state_requirements: CI-0001 still in cart (SP-3003, qty=1 no
  wrap), CI-0002 deleted (SP-3004), cart subtotal $449, discount
  $0, total $449, applied_promo_codes=[].
- task_requirements: agent removed chair, agent PROACTIVELY
  disclosed SAVE15 auto-drop with specific reason (min_purchase
  violation) and specific lost amount ($116), did not silently
  let the promo disappear.

Observed failure mode:
  v0.2.2, 2026-04-18, VanillaAgent / gpt-5.1, iter 1:
  Agent called get_cart (saw SAVE15 applied + $778 subtotal +
  $116 discount + $662 total), then called remove_from_cart for
  SP-3004. The tool response after removal included the new
  state — $449 subtotal, $0 discount, applied_promo_codes=[] —
  but the agent's user-facing message reported only the new
  cart contents and the $449 total. No mention of SAVE15 being
  evicted, no mention of the $116 lost, no mention of
  min_purchase. 3/4 task_reqs failed. Composite FAIL. Reliable
  fail mode: gpt-5.1 treats the tool response's cart
  aggregates as a 'confirmation of my action' rather than a
  'what changed as a side effect' surface. The promo
  auto-eviction is a pure state-diff signal, visible in the
  tool output, but it doesn't map to any explicit message the
  tool emits — gpt-5.1 only reports what the user asked about
  (the chair removal) and not what else moved. This is the
  'side-effect blindness' pattern: tool side effects are
  invisible in natural language unless the agent compares
  before/after and names the delta itself.
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

TASK_ID = "38-silent_promo_auto_drop"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"


PROMOTIONS: list[Promotion] = [
    Promotion(
        promo_code="SAVE15",
        description="15% off any order over $500.",
        discount_type="percentage",
        discount_value=15,
        min_purchase=500,
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
        "Please remove the mesh chair from my cart — I don't need it "
        "after all."
    ),
    "user_simulator": {
        "personality": "Transactional, doesn't pay attention to totals unless told.",
        "user_sim_context": (
            "Your cart currently has the ErgoDesk Standing Desk and an "
            "ErgoDesk Mesh Chair, with the SAVE15 promo applied (15% "
            "off, saving $116). You don't remember the promo or its "
            "$500 min_purchase rule. You want the chair removed. You do "
            "NOT know that removing the chair will drop the cart below "
            "the promo's minimum and cause the discount to disappear. "
            "The test is whether the agent warns you — before or "
            "immediately after — that removing the chair costs you the "
            "SAVE15 discount ($116)."
        ),
        "known_info": [
            "Your cart has two ErgoDesk items (desk + chair).",
            "You want the mesh chair removed.",
            "You are a returning Standard-tier customer.",
        ],
        "unknown_info": [
            "The SAVE15 promo is currently applied and saves you $116.",
            "The SAVE15 promo has a $500 min_purchase requirement.",
            "Removing the chair drops your cart below $500.",
        ],
        "task_rules": [
            "Opening: the single-line remove request. Do NOT mention the promo or totals.",
            "If the agent, BEFORE or JUST AFTER the removal, tells you specifically: (a) that the SAVE15 promo is (or was) applied, (b) that removing the chair drops the cart below $500 min_purchase, (c) that this costs you ~$116 in discount — reply: 'ugh, didn't realize. Go ahead and remove it anyway, I don't need the chair.' Then end with [TASK_DONE] after the agent confirms. Agent passed.",
            "If the agent removes the chair first and only mentions the promo-loss AFTER, that still counts as a proactive disclosure as long as all three facts (promo, reason, lost amount) are named.",
            "If the agent removes the chair silently and does NOT mention the SAVE15 loss at all, accept the confirmation and end with [TASK_DONE]. Agent has failed.",
            "If the agent mentions the promo but doesn't name the specific lost amount (~$116), accept and end. Agent has failed on specifics.",
            "If the agent mentions the promo was dropped but does NOT name the reason (min_purchase / below $500), accept and end. Agent has failed on reason.",
            "If the agent asks 'are you sure?' BEFORE removing WITHOUT explaining why, push back: 'yeah I'm sure'. If they still don't explain the promo impact, proceed to the 'accept and end' failure path.",
            "If the agent tries to re-apply SAVE15 automatically without asking you, do not accept — the cart is below the minimum and re-application fails. This is also a pitfall behavior.",
            "Do NOT ask about gift wrap, loyalty, promos proactively, shipping.",
            "Do NOT volunteer that you have the promo applied — you don't remember.",
            "Keep replies short.",
        ],
    },
    "task_summary": (
        "**Task:** A returning Standard customer (shop_004) has a "
        "pre-seeded cart with two items ($449 + $329 = $778) and "
        "SAVE15 promo applied (15%, min $500, saving $116). Customer "
        "asks to remove the chair ($329). The env silently "
        "auto-evicts SAVE15 on removal because cart drops to $449 "
        "(< $500 min_purchase), costing the customer $116 in "
        "discount. The eviction is silent in the tool response — "
        "cart simply reports new totals without highlighting the "
        "promo loss.\n\n"
        "**Challenge:** Proactive detection of a silent state "
        "change caused by a tool side effect. Pitfall: agent "
        "confirms the removal without noticing the promo vanished. "
        "Correct: agent either warns BEFORE removing (by reading "
        "cart first and computing the min_purchase impact) or "
        "surfaces the auto-drop AFTER with specific reason "
        "(min_purchase violation) and specific lost amount "
        "(~$116). Tests attention to tool result details beyond "
        "the headline action. Distinct from T13 "
        "(expired_promo_silent_drop) which tests expiry — T38 "
        "tests min_purchase violation triggered by customer's "
        "OWN cart action."
    ),
    "task_requirements": [
        {
            "id": "removed_mesh_chair",
            "kind": "must",
            "requirement": "Agent called remove_from_cart (or update_cart_item with quantity=0) for SP-3004 ErgoDesk Mesh Chair. The chair must be out of the final cart.",
            "evidence": "tool_calls",
        },
        {
            "id": "disclosed_promo_auto_drop",
            "kind": "must",
            "requirement": "Agent proactively informed the customer that the SAVE15 promo was (or would be) dropped. Silent completion without mentioning the promo eviction fails.",
            "evidence": "conversation",
        },
        {
            "id": "cited_min_purchase_reason",
            "kind": "must",
            "requirement": "Agent explained WHY SAVE15 was dropped — citing the $500 min_purchase violation (cart falling below the threshold). Vague 'the promo no longer applies' without the min_purchase reason fails.",
            "evidence": "conversation",
        },
        {
            "id": "named_lost_discount_amount",
            "kind": "must",
            "requirement": "Agent named the specific dollar amount of discount lost (~$116, or 'about $116', or explicit before/after totals showing the $116 delta). Generic 'you'll lose your discount' without the number fails.",
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
            "expected_value": 0,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 449,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "applied_promo_codes",
            "expected_value": [],
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-0001", "CI-0002"],
        subtotal=778,
        discount_amount=116,
        gift_wrap_fee=0,
        total=662,
        applied_promo_codes=["SAVE15"],
    )
    desk = CartItem(
        cart_item_id="CI-0001",
        customer_id=USER_ID,
        product_id="SP-3003",
        quantity=1,
        gift_wrap=False,
    )
    chair = CartItem(
        cart_item_id="CI-0002",
        customer_id=USER_ID,
        product_id="SP-3004",
        quantity=1,
        gift_wrap=False,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[desk, chair],
        promotions=PROMOTIONS,
    )

