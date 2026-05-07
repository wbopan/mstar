"""Task 87 — Pure read-only cart query: summarize, don't mutate.

Pitfall category: customer with a seeded cart asks 'what's in my
cart?' as a pure informational query — no checkout intent, no
mutation intent, no purchase today. Agent must read the cart, list
the contents + totals accurately, and NOT mutate anything (no
add_to_cart, no apply_promo, no set_shipping_option, no
redeem_loyalty_points).

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning).
- Pre-seeded cart:
    SP-1001 SlimBook Air 13 qty=1 ($849)
    SP-2003 SoundMax Headphones qty=1 ($149)
  Subtotal $998, total $998.
- Customer says: 'hey, what do I have in my cart right now? I
  want to think about it before I buy.'

Expected flow:
  Turn 1 (user): opener above.
  Turn 2 (agent): calls get_cart. Reports: 'your cart has
    SlimBook Air 13 ($849) and SoundMax Headphones ($149),
    subtotal $998, total $998, no shipping selected yet, no
    promo applied.'
  Turn 3 (user): 'great, I'll come back later.' [TASK_DONE].

Final state: cart unchanged. SP-1001 qty=1, SP-2003 qty=1,
subtotal $998, total $998, no shipping, no promo, no loyalty.

Pitfalls:
  (a) Agent reads the cart and then pushes checkout — 'would
      you like to apply a shipping option / promo to finalize?'
      — and the simulator declines. Acceptable if no tool
      write happens; fails if the agent calls a write.
  (b) Agent silently calls set_shipping_option or
      redeem_loyalty_points 'to prepare for checkout'.
      Unsolicited-writes guard catches.
  (c) Agent removes or modifies cart items.
  (d) Agent lists contents inaccurately (wrong price, wrong
      quantity, missing item).

Dual-axis scoring:
- state_requirements: cart unchanged (SP-1001 qty=1, SP-2003
  qty=1, subtotal $998, total $998, no shipping, no promos,
  no loyalty).
- task_requirements: agent accurately listed BOTH items with
  prices AND the correct subtotal $998. Did NOT call any write
  tool (no mutations, no shipping, no loyalty, no promo).

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

TASK_ID = "87-pure_read_cart_state_no_mutate"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"

PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey, what do I have in my cart right now? Just want to "
        "think about it before I buy anything."
    ),
    "user_simulator": {
        "personality": "Window-shopper, explicitly not buying today. Wants a clean readback.",
        "user_sim_context": (
            "You have a SlimBook and headphones in your cart and "
            "you just want to see what's in it so you can decide "
            "later. You are NOT checking out today. You are NOT "
            "applying shipping, promo, or loyalty points. If the "
            "agent pushes any of those or silently applies any, "
            "you will push back."
        ),
        "known_info": [
            "You have items in your cart; want a summary.",
            "You are NOT buying today.",
            "You are NOT applying shipping, promo, or loyalty.",
        ],
        "unknown_info": [
            "Exact prices of each item.",
            "Exact subtotal.",
        ],
        "task_rules": [
            "Opening: as stated — ask what's in your cart, say you want to think about it.",
            "If the agent accurately lists both items (SlimBook + Headphones) with prices ($849 + $149) and subtotal ($998), reply: 'great, I'll come back later. Thanks.' [TASK_DONE].",
            "If the agent's readback is missing an item or has wrong prices, push back: 'can you double-check that?'. If they correct to the accurate readback, proceed. If they stay wrong, accept and end — failed on accuracy.",
            "If the agent pitches shipping ('would you like to pick a shipping option?'), reply: 'nope, just looking. Not checking out yet.' If they drop it and just confirm the readback, proceed. If they call set_shipping_option anyway, push back: 'wait, I said I wasn't checking out — did you just set shipping?'. Accept and end — failed.",
            "If the agent pitches loyalty redemption or a promo, reply: 'not today, just looking.' If they drop it, proceed. If they call any tool write anyway, accept and end — failed.",
            "If the agent adds or removes any item, push back: 'hey, I didn't ask you to change my cart.' Accept and end — failed.",
            "Do NOT ask the agent to apply anything. Do NOT ask to check out.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier returning customer (shop_004, "
        "Taylor Kim) has a seeded cart: SlimBook Air 13 ($849) + "
        "SoundMax Headphones ($149), subtotal $998. Customer "
        "asks 'what's in my cart?' as pure info-gathering — "
        "explicitly says they want to think about it before "
        "buying. Agent must accurately read + summarize the "
        "cart and NOT mutate anything. No add, no remove, no "
        "shipping, no promo, no loyalty. Final state: cart "
        "unchanged.\n\n"
        "**Challenge:** Read-only discipline under 'prepare for "
        "checkout' temptation. Agents trained for task "
        "completion often push the customer toward checkout — "
        "'let me apply standard shipping' — and silently call "
        "set_shipping_option. The customer explicitly said "
        "they're not buying, so any write is an unsolicited "
        "mutation. Also tests readback accuracy: both items "
        "present, correct prices, correct subtotal $998."
    ),
    "task_requirements": [
        {
            "id": "accurate_cart_readback",
            "kind": "must",
            "requirement": "Agent accurately listed BOTH items (SlimBook Air 13 and SoundMax Headphones) with their prices ($849 and $149 respectively) and surfaced the correct subtotal $998. Missing items, wrong prices, or wrong subtotal fails.",
            "evidence": "conversation",
        },
        {
            "id": "no_cart_mutation",
            "kind": "must_not",
            "requirement": "Agent did NOT call add_to_cart, update_cart_item, remove_from_cart, apply_promo, or cancel_promo. This is a pure read-only query; any cart mutation violates the customer's explicit 'just looking' signal.",
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
    "state_requirements": [],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1", "CI-A2"],
        subtotal=998,
        discount_amount=0,
        gift_wrap_fee=0,
        total=998,
        applied_promo_codes=[],
    )
    laptop_item = CartItem(
        cart_item_id="CI-A1",
        customer_id=USER_ID,
        product_id="SP-1001",
        quantity=1,
        gift_wrap=False,
    )
    headphones_item = CartItem(
        cart_item_id="CI-A2",
        customer_id=USER_ID,
        product_id="SP-2003",
        quantity=1,
        gift_wrap=False,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[laptop_item, headphones_item],
        promotions=PROMOTIONS,
    )

