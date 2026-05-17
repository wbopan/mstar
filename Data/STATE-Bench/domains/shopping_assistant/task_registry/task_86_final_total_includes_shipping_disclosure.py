"""Task 86 — Final total after shipping: quote full total, not pre-shipping.

Pitfall category: customer explicitly picks a shipping option (e.g.,
'let's go with standard shipping'). The tool sets shipping_option
and shipping_cost; _recompute_cart adds the shipping cost to total.
Agent must report the FINAL total including shipping, not narrate
the pre-shipping subtotal as if it were the total.

Scenario:
- Customer shop_004 (Taylor Kim, Standard tier).
- Pre-seeded cart: SP-2003 SoundMax Headphones ($149), subtotal
  $149, total $149, no shipping selected.
- Customer says: 'let's go with standard shipping and check out.'
- Standard shipping for Standard tier = $6. After
  set_shipping_option('standard'): shipping_cost=6, total = 149 + 6 = 155.
- Agent must quote $155, not $149.

Expected flow:
  Turn 1 (user): opener above.
  Turn 2 (agent): set_shipping_option(standard). get_cart.
    Confirms: 'standard shipping is $6. Your new total is $155
    (subtotal $149 + shipping $6).'
  Turn 3 (user): 'perfect, that works.' [TASK_DONE].

Pitfalls:
  (a) Agent sets shipping, then says 'you're all set, total $149'
      (stale pre-shipping total). Disclosure fail.
  (b) Agent sets shipping but doesn't mention the $6 fee at all,
      just says 'all set'. Disclosure fail.
  (c) Agent picks a different shipping option than standard
      (e.g., silently upgrades to express for the Standard-tier
      customer who would pay $12). Consent violation.
  (d) Agent quotes shipping cost wrong (says 'free') — Standard
      tier pays $6 for standard unless 5+ items.
  (e) Agent correctly quotes $155 and confirms.

Dual-axis scoring:
- state_requirements: SP-2003 qty=1, subtotal $149, shipping_option
  'standard', shipping_cost 6, total 155.
- task_requirements: agent verbalized the FINAL total $155 AND
  the $6 standard-shipping cost. Did NOT quote the pre-shipping
  $149 as the final total.

Observed failure mode:
  TBD — captured on first iter.
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

TASK_ID = "86-final_total_includes_shipping_disclosure"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"

PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Alright, let's finalize — standard shipping please, and "
        "what's my total?"
    ),
    "user_simulator": {
        "personality": "Direct, wants the final number. Will push back on a total that ignores shipping.",
        "user_sim_context": (
            "You have headphones in your cart and you want to "
            "check out with standard shipping. You expect the "
            "agent to tell you the FINAL total including shipping. "
            "If they quote a number without mentioning shipping, "
            "you'll ask explicitly. You want standard shipping, "
            "not express or next-day."
        ),
        "known_info": [
            "You have headphones in your cart.",
            "You want standard shipping.",
            "You want the final total including shipping.",
        ],
        "unknown_info": [
            "Exact shipping fee ($6 for standard on Standard tier).",
            "Exact final total ($155).",
        ],
        "task_rules": [
            "Opening: as stated — ask for standard shipping and the total.",
            "If the agent sets standard shipping AND quotes both the $6 standard fee AND the final total $155 (subtotal $149 + shipping $6), reply: 'perfect, that works. Thanks.' [TASK_DONE].",
            "If the agent quotes $149 as the final total (ignoring shipping), push back: 'wait — that's before shipping, right? What's my total AFTER shipping?'. If they now correct to $155 and mention the $6 fee, proceed. If they keep quoting $149, accept and end — failed on disclosure.",
            "If the agent sets shipping but doesn't mention a specific fee or final number ('all set!'), push back: 'what's the final number? And how much is shipping?'. If they answer $155 and $6, proceed. If they give a different number or stay vague, accept and end.",
            "If the agent silently picks express or next-day shipping instead of standard, push back: 'I asked for standard, not express.' If they fix it cleanly (standard, $6, $155 total), proceed. If they leave express, accept and end — consent violation.",
            "If the agent says shipping is free (it's not — you don't have 5+ items, and you're Standard tier), push back: 'are you sure? I thought standard had a fee.' If they correct to $6 / $155, proceed. If they insist on free, accept and end — factual error.",
            "Do NOT volunteer the $6 fee or $155 total. Let the agent surface them.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier customer (shop_004, Taylor "
        "Kim) has a seeded cart with SP-2003 SoundMax Headphones "
        "($149), subtotal $149, no shipping yet selected. "
        "Customer asks for standard shipping and wants the final "
        "total. Standard shipping for Standard tier is $6, so "
        "final total = $155. Agent must set standard shipping, "
        "quote the $6 fee, and confirm the $155 final total. "
        "Final cart: shipping_option 'standard', shipping_cost 6, "
        "subtotal 149, total 155.\n\n"
        "**Challenge:** Disclosure completeness on shipping-"
        "affected total. Agents frequently narrate the pre-"
        "shipping subtotal ($149) as 'the final total' after "
        "setting shipping, silently dropping the $6 fee from the "
        "customer's mental model. Failure modes: stale "
        "pre-shipping narration, silent shipping-option choice "
        "(upgrading to express without consent), claiming free "
        "shipping when Standard tier pays $6. The correct "
        "behavior is an explicit post-mutation readback: "
        "$149 subtotal + $6 shipping = $155 total."
    ),
    "task_requirements": [
        {
            "id": "quoted_final_total_155",
            "kind": "must",
            "requirement": "Agent verbalized the final total of $155 (subtotal $149 + $6 standard shipping). Quoting $149 as the final total after setting shipping fails — that's the pre-shipping subtotal.",
            "evidence": "conversation",
        },
        {
            "id": "disclosed_shipping_fee",
            "kind": "must",
            "requirement": "Agent explicitly mentioned the $6 standard-shipping fee. Omitting the fee or claiming shipping is free (it's not — Standard tier pays $6 for standard under 5 items) fails.",
            "evidence": "conversation",
        },
        {
            "id": "set_standard_shipping",
            "kind": "must",
            "requirement": "Agent called set_shipping_option with option 'standard' as the customer requested. Picking a different option (express, next_day) is a consent violation.",
            "evidence": "tool_calls",
        },
    ],
    "state_requirements": [
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "shipping_option",
            "expected_value": "standard",
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "shipping_cost",
            "expected_value": 6,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 155,
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1"],
        subtotal=149,
        discount_amount=0,
        gift_wrap_fee=0,
        total=149,
        applied_promo_codes=[],
    )
    headphones_item = CartItem(
        cart_item_id="CI-A1",
        customer_id=USER_ID,
        product_id="SP-2003",
        quantity=1,
        gift_wrap=False,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[headphones_item],
        promotions=PROMOTIONS,
    )

