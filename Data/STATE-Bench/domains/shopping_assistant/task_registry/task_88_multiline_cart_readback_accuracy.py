"""Task 88 — Complex cart readback accuracy: every line + fee + discount.

Pitfall category: complex seeded cart with multiple items, one
gift-wrapped, a promo applied, and a specific subtotal/discount/total
pattern. Customer asks 'can you read back my cart — item by item,
with the discount and everything?'. Agent must accurately enumerate
every line (SKU, qty, unit price, gift-wrap flag), the gift-wrap
fee, the promo discount, the subtotal, and the final total.

Read-only turn: NO mutation, pure readback.

Scenario:
- Customer shop_004 (Taylor Kim, Standard, returning).
- Pre-seeded cart with 3 lines:
    SP-1001 SlimBook Air 13 qty=1 ($849), no wrap
    SP-2003 SoundMax Headphones qty=1 ($149), GIFT-WRAPPED (+$5)
    SP-2005 PixelShot Webcam qty=2 ($79 each, line $158), no wrap
  Subtotal: $849 + $149 + $158 = $1,156
  Gift wrap fee: $5 (1 wrapped item)
  Promo SAVE50 applied: $50 off flat
  Total: 1156 + 5 - 50 = $1,111

Expected agent behavior:
  - Calls get_cart (and get_product_details as needed for names).
  - Reports every line with qty and unit price.
  - Mentions the 1 gift-wrapped item AND the $5 wrap fee.
  - Mentions the SAVE50 promo AND the $50 discount.
  - Quotes subtotal $1,156 AND total $1,111.

Pitfalls:
  (a) Agent misses one of the three items (rushes the readback).
  (b) Agent misses the gift wrap or the fee.
  (c) Agent misses the promo or the discount.
  (d) Agent misquotes subtotal or total.
  (e) Agent mutates the cart (adds, removes, reapplies promo —
      unsolicited write).

Dual-axis scoring:
- state_requirements: cart unchanged. All 3 lines present with
  correct qty and gift_wrap flags; subtotal $1,156; gift_wrap_fee
  $5; discount $50; applied_promo_codes ['SAVE50']; total $1,111.
- task_requirements: agent accurately surfaced every line AND
  the gift wrap fee AND the promo discount AND the correct
  totals. Did NOT mutate.

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

TASK_ID = "88-multiline_cart_readback_accuracy"
USER_ID = "shop_004"
NOW = "2026-06-12T10:00:00"

PROMOTIONS: list[Promotion] = [
    Promotion(
        promo_code="SAVE50",
        description="$50 off any order",
        discount_type="fixed",
        discount_value=50,
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
        "Hey — can you read back my cart for me, item by item? "
        "Include the gift wrap and the promo discount so I can "
        "double-check the math."
    ),
    "user_simulator": {
        "personality": "Detail-oriented, wants line-by-line accuracy. Won't tolerate handwaving.",
        "user_sim_context": (
            "You have a cart with three items — a SlimBook, "
            "SoundMax Headphones (one is a gift and should be "
            "wrapped), and two PixelShot webcams. You applied "
            "SAVE50 for $50 off. You want the agent to read "
            "back EVERY line with price and quantity, AND confirm "
            "the gift wrap fee AND the SAVE50 discount, AND give "
            "you the subtotal and final total. You are NOT "
            "making changes — just verifying."
        ),
        "known_info": [
            "You have three items: SlimBook, SoundMax Headphones, and PixelShot Webcam(s).",
            "One headphone is gift-wrapped.",
            "SAVE50 is applied for $50 off.",
            "You are NOT making changes — read-only.",
        ],
        "unknown_info": [
            "Exact subtotal ($1,156) and total ($1,111).",
            "Gift wrap fee amount.",
            "Exact per-item prices.",
        ],
        "task_rules": [
            "Opening: as stated — ask for an item-by-item readback including gift wrap and promo.",
            "If the agent reads back all 3 items with quantities (qty=2 webcams noted) AND the 1 gift-wrapped item AND the $5 wrap fee AND the $50 SAVE50 discount AND subtotal $1,156 AND total $1,111, reply: 'perfect, that matches what I expected. Thanks.' [TASK_DONE].",
            "If the agent misses any item in the readback, push back: 'wait, you missed one — can you redo it?'. If they correct completely, proceed. If they still miss, accept and end — failed.",
            "If the agent omits the gift wrap or the $5 fee, push back: 'what about the gift wrap — is that reflected?'. If they cite the $5 fee and the wrapped item, proceed. If they stay vague, accept and end.",
            "If the agent omits the SAVE50 or the $50 discount, push back: 'did you include the SAVE50 discount? What's my discount amount?'. If they confirm $50 and total $1,111, proceed. If not, accept and end.",
            "If the agent quotes a wrong subtotal or total, push back: 'that doesn't match my math. Can you double-check — subtotal and total?'. If they correct to $1,156 / $1,111, proceed. If not, accept and end.",
            "If the agent adds, removes, or modifies any item, push back: 'hey, I didn't ask you to change anything. Please revert.' Accept and end — failed on mutation.",
            "Do NOT volunteer the exact numbers. Let the agent surface them.",
            "Keep replies short — 1-2 sentences.",
        ],
    },
    "task_summary": (
        "**Task:** A Standard-tier returning customer (shop_004, "
        "Taylor Kim) has a complex seeded cart: SlimBook Air 13 "
        "($849 × 1), SoundMax Headphones ($149 × 1, "
        "gift-wrapped), PixelShot Webcam ($79 × 2 = $158). "
        "Gift-wrap fee $5, SAVE50 applied for $50 off. Subtotal "
        "$1,156, total $1,111. Customer asks for an "
        "item-by-item readback including gift wrap and discount. "
        "Agent must accurately enumerate every line AND surface "
        "the fee / discount / subtotal / total. Read-only turn; "
        "no mutations. Final state: cart unchanged.\n\n"
        "**Challenge:** Readback completeness and accuracy on a "
        "dense cart. Failure modes: skipping an item (3-line "
        "readback becomes 2), omitting the gift-wrap fee, "
        "omitting the promo discount, misquoting subtotal or "
        "total, or silently mutating (re-applying the promo, "
        "auto-adding shipping, etc.). Tests whether the agent "
        "can faithfully serialize a complex cart state back to "
        "the customer without losing information."
    ),
    "task_requirements": [
        {
            "id": "listed_all_three_items",
            "kind": "must",
            "requirement": "Agent listed all three items in the readback: SlimBook Air 13 (qty 1), SoundMax Headphones (qty 1), and PixelShot Webcam (qty 2). Missing any item fails.",
            "evidence": "conversation",
        },
        {
            "id": "surfaced_gift_wrap_fee",
            "kind": "must",
            "requirement": "Agent mentioned the gift-wrapped headphones and the $5 gift-wrap fee. Missing the wrap status or the $5 fee fails.",
            "evidence": "conversation",
        },
        {
            "id": "surfaced_promo_discount",
            "kind": "must",
            "requirement": "Agent mentioned SAVE50 and the $50 discount. Missing either fails.",
            "evidence": "conversation",
        },
        {
            "id": "correct_totals",
            "kind": "must",
            "requirement": "Agent quoted subtotal $1,156 AND total $1,111. Either missing or wrong fails.",
            "evidence": "conversation",
        },
        {
            "id": "no_cart_mutation",
            "kind": "must_not",
            "requirement": "Agent did NOT call add_to_cart, update_cart_item, remove_from_cart, apply_promo, or cancel_promo. This is a pure readback; any mutation violates the customer's explicit 'just verifying' intent.",
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
    # subtotal = 849 + 149 + (79*2) = 1156
    # gift_wrap_fee = 5 (only SP-2003 wrapped)
    # discount = 50
    # total = 1156 + 5 - 50 = 1111
    cart = Cart(
        cart_id=f"CART-{USER_ID}",
        customer_id=USER_ID,
        item_ids=["CI-A1", "CI-A2", "CI-A3"],
        subtotal=1156,
        discount_amount=50,
        gift_wrap_fee=5,
        total=1111,
        applied_promo_codes=["SAVE50"],
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
        gift_wrap=True,
    )
    webcam_item = CartItem(
        cart_item_id="CI-A3",
        customer_id=USER_ID,
        product_id="SP-2005",
        quantity=2,
        gift_wrap=False,
    )
    return SAEnvironmentData(
        products=PRODUCTS,
        customers=[customer],
        carts=[cart],
        cart_items=[laptop_item, headphones_item, webcam_item],
        promotions=PROMOTIONS,
    )

