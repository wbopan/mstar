"""Task 84 — Remove scope: 'remove the webcam' means all units, not one.

Pitfall category: customer has multiple units of a single SKU in the
cart and says 'remove the webcam'. Natural-language scope is
ambiguous between 'remove one unit' and 'remove the line item
entirely'. For a returning customer on a single SKU line with qty=2,
the most common human reading is 'take it out of my cart' = remove
the whole line. Agent should either:
  (a) remove the entire line (preferred default for this phrasing), OR
  (b) explicitly clarify ('did you want to remove one unit or both?')
      before acting.
Silently decrementing by 1 without clarifying is the failure mode.

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning).
- Pre-seeded cart:
    SP-1001 SlimBook Air 13 qty=1 ($849)
    SP-2005 PixelShot Webcam qty=2 ($79 each, line $158)
  Subtotal $1,007, total $1,007.
- Customer says: 'please remove the webcam from my cart, I changed
  my mind.'

Expected flow:
  Turn 1 (user): opener above.
  Turn 2 (agent): either (a) remove_from_cart(SP-2005) — removes all
    — and confirms, or (b) asks: 'you have 2 webcams in the cart —
    did you want to remove both, or just one?'
  Turn 3: if (a), customer confirms. If (b), customer says 'both'
    and agent removes.
  Turn 4: final cart SP-1001 qty=1, subtotal $849, total $849.
  [TASK_DONE].

Pitfalls:
  (a) Agent silently decrements webcam qty from 2 to 1 via
      update_cart_item, leaving 1 webcam in cart. State fails —
      SP-2005 still present. Customer meant 'take it out entirely'.
  (b) Agent removes only one webcam and confirms 'done, removed
      the webcam'. Same silent-scope-narrowing failure.
  (c) Agent removes the webcam correctly but also touches the
      SlimBook (accidental broad remove). State fails.
  (d) Agent asks clarifying question once, customer says 'both',
      agent removes cleanly — acceptable path.

Dual-axis scoring:
- state_requirements: SP-1001 qty=1 (unchanged), SP-2005 NOT in
  cart (all units removed), subtotal $849, total $849.
- task_requirements: agent either removed the full webcam line
  on first try, OR asked a single clarifying question before
  acting. Did NOT silently decrement to qty=1.

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

TASK_ID = "84-remove_qty_scope_all_vs_one"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"

PROMOTIONS: list[Promotion] = []


TASK_JSON: dict = {
    "task_id": TASK_ID,

    "user_id": USER_ID,
    "now": NOW,
    "opening_message": (
        "Hey — please remove the webcam from my cart, I changed my "
        "mind, I don't want it anymore."
    ),
    "user_simulator": {
        "personality": "Direct, not tracking quantities in their head. Says 'the webcam' meaning the whole line.",
        "user_sim_context": (
            "You have a SlimBook and two webcams in your cart. You "
            "no longer want the webcams — you want them out of the "
            "cart entirely. You don't remember you had 2 webcams; "
            "you just say 'remove the webcam' meaning take it out. "
            "If the agent asks whether you want both removed or "
            "just one, you'll clarify 'both, take the webcams out "
            "entirely'. If they silently leave one in cart, you "
            "may or may not notice — you'll check the cart summary."
        ),
        "known_info": [
            "You have a SlimBook and webcams in your cart.",
            "You don't want any webcams — remove them entirely.",
            "You do want to keep the SlimBook.",
        ],
        "unknown_info": [
            "That you have 2 webcams (not 1).",
            "The exact cart subtotal.",
        ],
        "task_rules": [
            "Opening: as stated — ask to remove the webcam.",
            "If the agent asks to clarify scope ('both webcams or just one?'), reply: 'both, please — I don't want any webcams.' Then wait for them to remove all units and show the cart.",
            "If the agent removes cleanly (final cart SlimBook only, $849) on first try without asking, reply: 'perfect, that's what I wanted.' [TASK_DONE].",
            "If the agent reports 'removed the webcam' but the cart summary still shows 1 webcam at $79, push back: 'wait — there's still a webcam in my cart. I want them ALL out.' If the agent now removes the remaining unit cleanly (final $849), reply 'thanks, that's right.' [TASK_DONE]. If they leave it there, accept and end — failed.",
            "If the agent silently decrements to qty=1 WITHOUT saying anything about qty and you only see 'done', ask: 'can you show me the cart — what's left?'. If the readback shows 1 webcam still there, follow the above rule.",
            "If the agent removes the SlimBook by mistake, push back: 'no no, I want to keep the SlimBook — the webcams are the ones going.' If they fix it cleanly, proceed. If they don't, accept and end.",
            "If the final cart shows only the SlimBook at $849, confirm: 'sounds good, thanks.' [TASK_DONE].",
            "Do NOT mention '2 webcams' or specific quantities. Let the agent surface the qty.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier returning customer (shop_004, "
        "Taylor Kim) has a seeded cart with a SlimBook Air 13 "
        "($849) and 2 PixelShot Webcams ($79 each, line $158), "
        "subtotal $1,007. The customer says 'remove the webcam' — "
        "a phrasing that is ambiguous on a qty=2 line between "
        "'one unit' and 'the whole line'. The natural reading is "
        "'take the webcams out entirely'. The agent must either "
        "remove the full webcam line or ask one clarifying "
        "question before acting. Silently decrementing qty 2 → 1 "
        "while narrating 'removed the webcam' is the failure. "
        "Final cart: SlimBook only, subtotal $849, total $849.\n\n"
        "**Challenge:** Scope disambiguation on a mutation verb. "
        "Agents that implement 'remove X' as a blind qty-1 "
        "decrement produce a cart that does NOT match the "
        "customer's intent — and silently report success. "
        "Correct behavior: treat 'remove the webcam' on a single "
        "SKU line as 'remove the line', or ask one clarifying "
        "question about scope before acting."
    ),
    "task_requirements": [
        {
            "id": "removed_full_webcam_line",
            "kind": "must",
            "requirement": "The final cart has ZERO units of SP-2005. Either the agent called remove_from_cart(SP-2005) or called update_cart_item to set its quantity to 0, or used equivalent means. Leaving qty=1 or more of the webcam after the remove action fails this requirement.",
            "evidence": "tool_calls",
        },
        {
            "id": "did_not_silently_narrow_scope",
            "kind": "must_not",
            "requirement": "Agent did NOT narrate 'removed the webcam' while actually leaving 1 unit in cart. Scope narration must match final cart state. Asking a clarifying question before acting is acceptable and does NOT violate this requirement.",
            "evidence": "conversation",
        },
        {
            "id": "kept_slimbook",
            "kind": "must",
            "requirement": "Agent did NOT remove or modify SP-1001 (the SlimBook). Final cart has SP-1001 qty=1 unchanged.",
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
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "subtotal",
            "expected_value": 849,
        },
        {
            "entity_type": "carts",
            "record_key": f"CART-{USER_ID}",
            "field": "total",
            "expected_value": 849,
        },
    ],
}


def _build_seeded_env() -> SAEnvironmentData:
    customer = build_customer_record(USER_ID)
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1", "CI-A2"],
        subtotal=1007,
        discount_amount=0,
        gift_wrap_fee=0,
        total=1007,
        applied_promo_codes=[],
    )
    laptop_item = CartItem(
        cart_item_id="CI-A1",
        customer_id=USER_ID,
        product_id="SP-1001",
        quantity=1,
        gift_wrap=False,
    )
    webcam_item = CartItem(
        cart_item_id="CI-A2",
        customer_id=USER_ID,
        product_id="SP-2005",
        quantity=2,
        gift_wrap=False,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[laptop_item, webcam_item],
        promotions=PROMOTIONS,
    )

